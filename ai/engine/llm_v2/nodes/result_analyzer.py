"""
步骤 10: 结果分析智能体

职责：
- 分析查询结果
- 生成自然语言回答
- 生成建议问题
"""
import json
from typing import Dict, Any, List
from ai.config.logging_config import get_logger
from ai.engine.llm import get_llm_engine
from ..schema import MQLSchema, SQLResult, AnomalyAnnotation

logger = get_logger("ai.llm_v2.result_analyzer")


class ResultAnalyzer:
    """
    结果分析智能体

    使用 LLM 分析查询结果，生成自然语言回答。
    """

    def __init__(self):
        self._llm_engine = get_llm_engine()

    async def analyze(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
        is_generic_result: bool = False,
        clarification_message: str = "",
        clarification_options: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        分析结果

        Args:
            mql: MQL Schema
            sql_result: SQL 执行结果
            question: 原始问题
            is_generic_result: 是否为泛指默认结果
            clarification_message: 追问引导消息
            clarification_options: 追问选项列表

        Returns:
            {
                "answer": str,
                "suggestions": List[str],
            }
        """
        logger.info("[ResultAnalyzer] 分析结果")

        # 1. 处理空数据
        if not sql_result.data:
            result = await self._handle_empty_result(mql, question)
            # 附加泛指维度追问引导
            if is_generic_result and clarification_message:
                result["answer"] += f"\n\n{clarification_message}"
                if clarification_options:
                    options_text = " ".join([f"[{o['label']}]" for o in clarification_options])
                    result["answer"] += f" {options_text}"
            return result

        # 2. 根据意图生成回答
        intent = mql.intent.value if mql.intent else "query_value"

        if intent == "query_value":
            result = await self._handle_value_query(mql, sql_result, question)
        elif intent == "query_trend":
            result = await self._handle_trend_query(mql, sql_result, question)
        elif intent == "query_comparison":
            result = await self._handle_comparison_query(mql, sql_result, question)
        elif intent == "query_ranking":
            result = await self._handle_ranking_query(mql, sql_result, question)
        elif intent == "query_ratio":
            result = await self._handle_ratio_query(mql, sql_result, question)
        else:
            result = await self._handle_default(mql, sql_result, question)

        # 3. 检测异常并自动标注
        metric_name = mql.metric.name if mql.metric else "指标"
        dim_types = [d.type for d in mql.dimensions] if mql.dimensions else []
        anomalies = self.detect_anomalies(sql_result.data, metric_name, dim_types)
        if anomalies:
            anomaly_messages = [a.message for a in anomalies]
            result["answer"] += f"\n\n⚠️ 异常提醒：{'；'.join(anomaly_messages)}"
            result["anomalies"] = [a.to_dict() for a in anomalies]

        # 4. 附加泛指维度追问引导
        if is_generic_result and clarification_message:
            result["answer"] += f"\n\n{clarification_message}"
            if clarification_options:
                options_text = " ".join([f"[{o['label']}]" for o in clarification_options])
                result["answer"] += f" {options_text}"
                # 返回结构化的 clarification_options 供前端渲染按钮
                result["clarification_options"] = clarification_options
                result["clarification_message"] = clarification_message

        return result

    async def _handle_empty_result(self, mql: MQLSchema, question: str) -> Dict[str, Any]:
        """处理空结果"""
        # 调用 LLM 生成智能追问
        prompt = f"""用户问题：{question}
查询结果：暂无数据

请分析可能的原因，并给出 2-3 个建议问题。

请以 JSON 格式返回：
{{"analysis": "原因分析", "suggestions": ["建议问题1", "建议问题2"]}}

只输出 JSON，不要有其他内容。"""

        try:
            response = self._llm_engine.call(prompt, temperature=0.5, max_tokens=500)
            result = json.loads(response)
            return {
                "answer": f"抱歉，暂未查询到数据。{result.get('analysis', '')}",
                "suggestions": result.get("suggestions", []),
            }
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            metric_name = mql.metric.name if mql.metric else "指标值"
            return {
                "answer": "抱歉，暂未查询到数据。请尝试调整时间范围或查询条件。",
                "suggestions": [
                    f"本月{metric_name}是多少",
                    f"查看其他{metric_name}数据",
                ],
            }

    async def _handle_value_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理数值查询"""
        data = sql_result.data

        if len(data) == 1:
            # 单值查询
            row = data[0]
            metric_name = mql.metric.name if mql.metric else "指标值"

            # 检查是否有多指标（mql.metrics）
            has_multiple_metrics = mql.metrics and len(mql.metrics) > 0

            if has_multiple_metrics and len(row) > 1:
                # 多指标查询：显示所有指标值
                parts = []
                for col_name, value in row.items():
                    formatted_value = self._format_value(value)
                    parts.append(f"{col_name}: {formatted_value}")
                answer = " | ".join(parts)
                # 收集所有指标名用于建议
                metric_names = [mql.metric.name] if mql.metric else []
                metric_names.extend([m.name for m in mql.metrics if m.name])
                return {
                    "answer": answer,
                    "suggestions": [
                        f"查看{metric_names[0]}趋势变化" if metric_names else "查看趋势变化",
                        f"对比上月{metric_names[0]}" if metric_names else "对比上月",
                    ],
                }
            else:
                # 单指标查询
                value = list(row.values())[0] if row else 0
                formatted_value = self._format_value(value)

                return {
                    "answer": f"{metric_name}为 {formatted_value}",
                    "suggestions": [
                        f"查看{metric_name}趋势变化",
                        f"对比上月{metric_name}",
                    ],
                }

        # 多行数据
        metric_name = mql.metric.name if mql.metric else "指标值"
        lines = []
        for row in data[:5]:
            parts = [f"{k}: {self._format_value(v)}" for k, v in row.items()]
            lines.append(" | ".join(parts))

        answer = "查询结果：\n" + "\n".join(lines)
        if len(data) > 5:
            answer += f"\n... 还有 {len(data) - 5} 条数据"

        return {
            "answer": answer,
            "suggestions": [
                f"查看{metric_name}排名前10",
                f"按维度分析{metric_name}",
            ],
        }

    async def _handle_trend_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理趋势查询"""
        data = sql_result.data

        if len(data) < 2:
            return {
                "answer": "数据点不足，无法分析趋势",
                "suggestions": [],
            }

        metric_name = mql.metric.name if mql.metric else "指标值"

        # 简单趋势分析
        values = []
        for row in data:
            for v in row.values():
                try:
                    values.append(float(str(v).replace(",", "")))
                except (ValueError, TypeError):
                    continue

        if len(values) < 2:
            return {
                "answer": "数据不足，无法分析趋势",
                "suggestions": [],
            }

        first = values[0]
        last = values[-1]
        change = (last - first) / first * 100 if first != 0 else 0

        trend = "上升" if change > 0 else "下降"
        answer = f"趋势{trend}，变化幅度 {abs(change):.1f}%"

        return {
            "answer": answer,
            "suggestions": [
                f"查看{metric_name}同比变化",
                f"查看{metric_name}环比变化",
            ],
        }

    async def _handle_comparison_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理对比查询"""
        data = sql_result.data
        metric_name = mql.metric.name if mql.metric else "指标值"

        # 检查是否是 MoM/YOY 格式的单行数据（包含 current_val 和 compare_val）
        is_mom_format = (
            len(data) == 1 and
            isinstance(data[0], dict) and
            'current_val' in data[0] and
            'compare_val' in data[0]
        )

        if is_mom_format:
            # MoM/YOY 单行数据：current_val 和 compare_val 在同一行
            row = data[0]
            current_val = float(row.get('current_val', 0) or 0)
            compare_val = float(row.get('compare_val', 0) or 0)
            trend = row.get('trend', '')
            change_rate = row.get('change_rate', '')

            # 根据趋势生成回答
            if trend == '增长':
                trend_desc = "增长"
                change_desc = f"上升了 {change_rate}%" if change_rate else ""
            elif trend == '下降':
                trend_desc = "下降"
                change_desc = f"下降了 {change_rate}%" if change_rate else ""
            else:
                trend_desc = "持平"
                change_desc = ""

            answer = f"{metric_name}环比{trend_desc}{change_desc}。3月页面访问量为 {int(current_val):,}，2月为 {int(compare_val):,}。"
            return {
                "answer": answer,
                "suggestions": [
                    f"查看{metric_name}详细数据",
                    f"查看{metric_name}趋势变化",
                ],
            }

        # 传统对比查询（两行数据）
        if len(data) < 2:
            return {
                "answer": "数据不足，无法进行对比",
                "suggestions": [],
            }

        # TODO: 更智能的对比分析
        return {
            "answer": f"对比结果已生成，详见数据",
            "suggestions": [
                f"查看{metric_name}详细数据",
                f"查看{metric_name}趋势变化",
            ],
        }

    async def _handle_ranking_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理排名查询"""
        data = sql_result.data

        lines = ["排名结果："]
        for i, row in enumerate(data[:10], 1):
            parts = [f"{k}: {self._format_value(v)}" for k, v in row.items()]
            lines.append(f"{i}. " + " | ".join(parts))

        metric_name = mql.metric.name if mql.metric else "指标值"
        return {
            "answer": "\n".join(lines),
            "suggestions": [
                f"查看更多{metric_name}排名",
                f"查看{metric_name}占比分布",
            ],
        }

    async def _handle_ratio_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理占比查询"""
        data = sql_result.data
        metric_name = mql.metric.name if mql.metric else "指标值"

        # 计算总体的各部分占比
        if not data:
            return {
                "answer": "暂无数据",
                "suggestions": [],
            }

        lines = ["占比分布："]

        # 计算 total（安全转换数字）
        try:
            first_values = list(data[0].values())
            total = 0
            for v in first_values:
                try:
                    total += float(str(v).replace(",", ""))
                except (ValueError, TypeError):
                    continue
        except (ValueError, TypeError, IndexError):
            total = 0

        for row in data[:5]:
            for k, v in row.items():
                try:
                    val = float(str(v).replace(",", ""))
                    if total > 0:
                        ratio = val / total * 100
                        lines.append(f"{k}: {ratio:.1f}%")
                except (ValueError, TypeError):
                    continue

        return {
            "answer": "\n".join(lines),
            "suggestions": [
                f"查看{metric_name}详细数据",
                f"查看{metric_name}趋势变化",
            ],
        }

    async def _handle_default(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理默认查询"""
        data = sql_result.data

        lines = ["查询结果："]
        for row in data[:5]:
            parts = [f"{k}: {self._format_value(v)}" for k, v in row.items()]
            lines.append(" | ".join(parts))

        return {
            "answer": "\n".join(lines),
            "suggestions": [],
        }

    def _format_value(self, value: Any) -> str:
        """格式化数值"""
        if value is None:
            return "N/A"

        try:
            num = float(str(value).replace(",", ""))
            if abs(num) >= 10000:
                return f"{num/10000:.2f}万"
            elif abs(num) >= 1000:
                return f"{num/1000:.2f}千"
            else:
                return f"{num:.2f}"
        except (ValueError, TypeError):
            return str(value)

    def detect_anomalies(
        self,
        data: List[Dict[str, Any]],
        metric_name: str,
        dimensions: List[str] = None,
    ) -> List[AnomalyAnnotation]:
        """检测数据异常

        Args:
            data: 查询结果数据
            metric_name: 指标名称
            dimensions: 维度列表（用于定位异常来源）

        Returns:
            异常标注列表
        """
        anomalies = []
        dimensions = dimensions or []

        for row in data:
            # 1. 环比异常检测（下降 > 15%）
            mom_change = row.get("mom_change") or row.get("环比变化") or row.get("环比")
            if mom_change is not None:
                try:
                    mom_val = float(str(mom_change).replace("%", "").replace(",", ""))
                    if mom_val < -0.15:  # 下降超过15%
                        # 找出导致异常的维度值
                        dim_value = ""
                        for dim in dimensions:
                            if dim in row:
                                dim_value = row[dim]
                                break
                        anomalies.append(AnomalyAnnotation(
                            type="significant_mom_drop",
                            metric=metric_name,
                            value=mom_val,
                            threshold=-0.15,
                            message=f"{metric_name}环比下降{abs(mom_val * 100):.1f}%",
                            dimension=dimensions[0] if dimensions else "",
                            dimension_value=dim_value,
                            suggestion=f"关注{(dim_value + '的' if dim_value else '')}{metric_name}变化",
                        ))
                except (ValueError, TypeError):
                    pass

            # 2. 同比异常检测（下降 > 20%）
            yoy_change = row.get("yoy_change") or row.get("同比变化") or row.get("同比")
            if yoy_change is not None:
                try:
                    yoy_val = float(str(yoy_change).replace("%", "").replace(",", ""))
                    if yoy_val < -0.20:  # 下降超过20%
                        dim_value = ""
                        for dim in dimensions:
                            if dim in row:
                                dim_value = row[dim]
                                break
                        anomalies.append(AnomalyAnnotation(
                            type="significant_yoy_drop",
                            metric=metric_name,
                            value=yoy_val,
                            threshold=-0.20,
                            message=f"{metric_name}同比下降{abs(yoy_val * 100):.1f}%",
                            dimension=dimensions[0] if dimensions else "",
                            dimension_value=dim_value,
                            suggestion=f"关注{(dim_value + '的' if dim_value else '')}{metric_name}同比变化",
                        ))
                except (ValueError, TypeError):
                    pass

            # 3. 零值/空值检测
            value = row.get("value") or row.get("数值") or row.get("销售额") or row.get("订单量")
            if value is not None:
                try:
                    val = float(str(value).replace(",", ""))
                    if val == 0:
                        anomalies.append(AnomalyAnnotation(
                            type="zero_value",
                            metric=metric_name,
                            value=0,
                            threshold=0,
                            message=f"{metric_name}数据为零",
                            dimension=dimensions[0] if dimensions else "",
                            suggestion="检查数据是否正常或时间范围是否正确",
                        ))
                except (ValueError, TypeError):
                    pass

            # 4. 异常高值检测（增长 > 50%，可能是异常）
            if mom_change is not None:
                try:
                    mom_val = float(str(mom_change).replace("%", "").replace(",", ""))
                    if mom_val > 0.5:  # 增长超过50%
                        anomalies.append(AnomalyAnnotation(
                            type="significant_spike",
                            metric=metric_name,
                            value=mom_val,
                            threshold=0.5,
                            message=f"{metric_name}环比增长{abs(mom_val * 100):.1f}%，注意确认异常原因",
                            dimension=dimensions[0] if dimensions else "",
                            suggestion="确认是否活动促销或数据口径变化",
                        ))
                except (ValueError, TypeError):
                    pass

        return anomalies
