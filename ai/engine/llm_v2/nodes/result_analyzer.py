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

    def _get_time_context(self, mql: MQLSchema) -> str:
        """从 MQL 获取时间上下文，用于建议问题拼接"""
        if mql.time and mql.time.original:
            return mql.time.original
        return "本月"

    def _get_dim_label_from_service(self) -> Dict[str, str]:
        """从 DimensionService 获取用户友好的维度名称映射"""
        try:
            from ai.services.dimension_service import DimensionService
            svc = DimensionService()
            options = svc.get_ranking_options()
            result = {}
            for opt in options:
                col = opt.get("value", "")
                label = opt.get("label", "")
                if label.startswith("按"):
                    label = label[1:]
                if col and label:
                    result[col.upper()] = label
            return result
        except Exception:
            return {}

    def _get_alternative_dimensions(self, current_dim_type: str = None) -> tuple:
        """
        获取与当前维度不同的替代维度，用于建议问题生成。

        优先级：站点 > 三级品类 > 二级品类 > 一级品类
        即：如果当前是站点 → 推荐三级品类
            如果当前是三级品类 → 推荐站点
            ...
        """
        dim_priority = ["FSITE", "GROUP_3", "GROUP_2", "GROUP_1"]
        # 中文类型名 → 英文字段名 映射
        dim_type_to_col = {
            "站点": "FSITE", "FSITE": "FSITE",
            "三级品类": "GROUP_3", "GROUP_3": "GROUP_3",
            "二级品类": "GROUP_2", "GROUP_2": "GROUP_2",
            "一级品类": "GROUP_1", "GROUP_1": "GROUP_1",
            "四级品类": "GROUP_4", "GROUP_4": "GROUP_4",
            "ASIN": "ASIN", "SKU": "SKU",
            "平台": "PLATFORM", "PLATFORM": "PLATFORM",
        }
        label_map = self._get_dim_label_from_service()

        if not current_dim_type:
            dim_col = dim_priority[0]
        else:
            # 将中文/英文类型名统一转换为英文字段名
            current_col = dim_type_to_col.get(current_dim_type, current_dim_type.upper())
            candidates = [d for d in dim_priority if d != current_col]
            dim_col = candidates[0] if candidates else dim_priority[0]

        dim_label = label_map.get(dim_col, dim_col)
        return dim_col, dim_label

    async def analyze(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
        is_generic_result: bool = False,
        clarification_message: str = "",
        clarification_options: List[Dict[str, Any]] = None,
        analysis: Dict[str, Any] = None,
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
            analysis: 触发分析结果（可选）

        Returns:
            {
                "answer": str,
                "suggestions": List[str],
                "analysis": Dict (如果有触发分析),
                "mode": "triggered" or "direct",
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

        # 5. 添加触发分析结果
        if analysis:
            result["analysis"] = analysis
            result["mode"] = "triggered"
        else:
            result["mode"] = "direct"

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
        time_context = self._get_time_context(mql)

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
                    # 维度列（如SKU、日期）不格式化，保持原样
                    if self._is_metric_column(col_name):
                        formatted_value = self._format_value(value)
                        parts.append(f"{col_name}: {formatted_value}")
                    else:
                        parts.append(f"{col_name}: {value}")
                answer = " | ".join(parts)
                # 收集所有指标名用于建议
                metric_names = [mql.metric.name] if mql.metric else []
                metric_names.extend([m.name for m in mql.metrics if m.name])
                _, alt_label = self._get_alternative_dimensions(None)
                return {
                    "answer": answer,
                    "suggestions": [
                        f"查看{time_context}各{alt_label}{metric_names[0]}趋势变化" if metric_names else f"查看{time_context}各{alt_label}趋势变化",
                        f"按{alt_label}维度对比上月" if metric_names else f"按{alt_label}维度对比上月",
                    ],
                }
            else:
                # 单指标查询
                value = list(row.values())[0] if row else 0
                formatted_value = self._format_value(value)
                _, alt_label = self._get_alternative_dimensions(None)
                return {
                    "answer": f"{metric_name}为 {formatted_value}",
                    "suggestions": [
                        f"查看{time_context}各{alt_label}{metric_name}趋势变化",
                        f"按{alt_label}维度对比上月",
                    ],
                }

        # 多行数据
        metric_name = mql.metric.name if mql.metric else "指标值"
        # 获取指标列名（用于判断哪些列需要格式化）
        metric_columns = set()
        if mql.metric and mql.metric.name:
            # 尝试从 starrocks_sql 或 field 中推断指标列名
            pass
        if mql.metrics:
            for m in mql.metrics:
                if m.name:
                    metric_columns.add(m.name)
        if mql.metric and mql.metric.name:
            metric_columns.add(mql.metric.name)

        lines = []
        for row in data[:5]:
            parts = []
            for k, v in row.items():
                # 只有指标列才格式化（数值格式化），维度列（如SKU、日期）保持原样
                if k in metric_columns or self._is_metric_column(k):
                    parts.append(f"{k}: {self._format_value(v)}")
                else:
                    parts.append(f"{k}: {v}")
            lines.append(" | ".join(parts))

        answer = "查询结果：\n" + "\n".join(lines)
        if len(data) > 5:
            answer += f"\n... 还有 {len(data) - 5} 条数据"

        # 生成带维度上下文的建议（维度错开，时间一致）
        time_context = self._get_time_context(mql)
        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)

        return {
            "answer": answer,
            "suggestions": [
                f"查看{time_context}各{alt_label}{metric_name}排名前10",
                f"按{alt_label}维度分析{metric_name}",
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
        metric_name = mql.metric.name if mql.metric else "指标值"

        # 检查是否是 MoM/YOY 格式的单行数据（包含 current_val 和 compare_val，或新的 mom_val/yoy_val）
        row = data[0] if data else {}
        is_mom_yoy_format = (
            len(data) == 1 and
            isinstance(row, dict) and
            'current_val' in row and
            ('compare_val' in row or 'mom_val' in row or 'yoy_val' in row)
        )

        if is_mom_yoy_format:
            # MoM/YOY 单行数据：current_val 和 compare_val 在同一行，或者新的 mom_val/yoy_val
            current_val = float(row.get('current_val', 0) or 0)

            # 优先使用新的 mom_val/yoy_val 格式，其次使用旧的 compare_val 格式
            mom_val = float(row.get('mom_val', 0) or 0) if 'mom_val' in row else None
            yoy_val = float(row.get('yoy_val', 0) or 0) if 'yoy_val' in row else None
            compare_val = float(row.get('compare_val', 0) or 0) if 'compare_val' in row else None

            mom_change = row.get('mom_change', '')
            yoy_change = row.get('yoy_change', '')
            change_rate = row.get('change_rate', '')
            trend = row.get('trend', '')

            # 生成描述
            unit = mql.metric.unit if mql.metric and mql.metric.unit else ""

            # 判断是 MoM 还是 YoY
            is_yoy = mql.has_yoy
            is_mom = mql.has_mom

            if is_yoy and yoy_val is not None and yoy_val != 0:
                # 同比数据
                if yoy_change:
                    change_desc = f"同比{'上升' if float(str(yoy_change).replace('%','')) > 0 else '下降'}了 {abs(float(str(yoy_change).replace('%','')))}%"
                else:
                    change_desc = ""
                if unit:
                    compare_str = f"{yoy_val:,.2f}{unit}"
                else:
                    compare_str = f"{yoy_val:,.2f}"
                answer = f"{metric_name}整体同比{'上升' if float(str(yoy_change).replace('%','')) > 0 else '下降' if yoy_change else '持平'}，{change_desc}（当前：{current_val:,.2f}{unit}，去年同期：{compare_str}）"
            elif is_mom and mom_val is not None and mom_val != 0:
                # 环比数据
                if mom_change:
                    change_desc = f"环比{'上升' if float(str(mom_change).replace('%','')) > 0 else '下降'}了 {abs(float(str(mom_change).replace('%','')))}%"
                else:
                    change_desc = ""
                if unit:
                    compare_str = f"{mom_val:,.2f}{unit}"
                else:
                    compare_str = f"{mom_val:,.2f}"
                answer = f"{metric_name}整体环比{'上升' if float(str(mom_change).replace('%','')) > 0 else '下降' if mom_change else '持平'}，{change_desc}（当前：{current_val:,.2f}{unit}，上期：{compare_str}）"
            else:
                # 旧格式 fallback
                if trend == '增长':
                    trend_desc = "增长"
                    change_desc = f"上升了 {change_rate}%" if change_rate else ""
                elif trend == '下降':
                    trend_desc = "下降"
                    change_desc = f"下降了 {change_rate}%" if change_rate else ""
                else:
                    trend_desc = "持平"
                    change_desc = ""

                if unit:
                    current_str = f"{current_val:,.2f}{unit}"
                    compare_str = f"{compare_val:,.2f}{unit}" if compare_val else "N/A"
                else:
                    current_str = f"{current_val:,.2f}"
                    compare_str = f"{compare_val:,.2f}" if compare_val else "N/A"

                answer = f"{metric_name}整体{trend_desc}，{change_desc}（当前：{current_str}，对比期：{compare_str}）"

            current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
            _, alt_label = self._get_alternative_dimensions(current_dim)

            # 获取多个替代维度（三级品类 + 二级品类 + 一级品类）
            dim_priority = ["FSITE", "GROUP_3", "GROUP_2", "GROUP_1"]
            label_map = self._get_dim_label_from_service()
            dim_type_to_col = {
                "站点": "FSITE", "FSITE": "FSITE",
                "三级品类": "GROUP_3", "GROUP_3": "GROUP_3",
                "二级品类": "GROUP_2", "GROUP_2": "GROUP_2",
                "一级品类": "GROUP_1", "GROUP_1": "GROUP_1",
            }
            current_col = dim_type_to_col.get(current_dim, current_dim.upper()) if current_dim else "FSITE"
            # 过滤掉当前维度，取后续所有维度
            alt_dims = [d for d in dim_priority if d != current_col]

            # 用户问环比 → 推荐同比+异维度；用户问同比 → 推荐环比+异维度
            if is_mom:
                alt_type = "同比"
                same_type = "环比"
            else:
                alt_type = "环比"
                same_type = "同比"

            # 第一建议：当前维度的另一种对比类型（如 同比 → 环比）
            # 第二、三建议：其他维度 + 当前对比类型（提供不同视角）
            suggestions = [
                f"查看各{alt_label}{metric_name}{alt_type}变化",
            ]
            for dim_col in alt_dims[:2]:  # 最多加两个异维度建议
                dim_lbl = label_map.get(dim_col, dim_col)
                suggestions.append(f"查看各{dim_lbl}{metric_name}{same_type}变化")

            return {
                "answer": answer,
                "suggestions": suggestions,
            }

        # 原始时间序列趋势分析（多行数据）
        if len(data) < 2:
            return {
                "answer": "数据点不足，无法分析趋势",
                "suggestions": [],
            }

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

        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)
        return {
            "answer": answer,
            "suggestions": [
                f"查看各{alt_label}{metric_name}同比变化",
                f"查看各{alt_label}{metric_name}环比变化",
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
        time_context = self._get_time_context(mql)

        # 检查是否是 MoM/YOY 格式的单行数据（包含 current_val 和 compare_val，或新的 mom_val/yoy_val）
        # 注意：SQL 生成器使用中文列名（当前值/环比值/同比值），需要同时兼容英文和中文列名
        row = data[0] if data else {}
        is_mom_format = (
            len(data) == 1 and
            isinstance(row, dict) and
            ('current_val' in row or '当前值' in row) and
            ('compare_val' in row or 'mom_val' in row or 'yoy_val' in row or
             '环比值' in row or '同比值' in row)
        )

        if is_mom_format:
            # MoM/YOY 单行数据：current_val 和 compare_val 在同一行，或者新的 mom_val/yoy_val
            # 支持中英文列名
            current_val = float(row.get('current_val') or row.get('当前值') or 0)

            # 优先使用新的 mom_val/yoy_val 格式，其次使用旧的 compare_val 格式，最后尝试中文列名
            mom_val = float(row.get('mom_val') or row.get('环比值') or 0) if 'mom_val' in row or '环比值' in row else None
            yoy_val = float(row.get('yoy_val') or row.get('同比值') or 0) if 'yoy_val' in row or '同比值' in row else None
            compare_val = float(row.get('compare_val', 0) or 0) if 'compare_val' in row else None

            mom_change = row.get('mom_change', row.get('环比变化', ''))
            yoy_change = row.get('yoy_change', row.get('同比变化', ''))
            change_rate = row.get('change_rate', '')
            trend = row.get('trend', '')

            # 判断是环比(MoM)还是同比(YoY)
            is_yoy = mql.has_yoy
            is_mom = mql.has_mom
            period_label = "同比" if is_yoy else ("环比" if is_mom else "")

            # 从 MQL time 提取实际期间描述
            time_start = mql.time.start if mql.time else ""

            # 格式化期间名称（取开始时间的年月）
            def format_period(start_str):
                if not start_str:
                    return "上期"
                try:
                    import datetime
                    dt = datetime.datetime.strptime(start_str[:10], "%Y-%m-%d")
                    return f"{dt.year}年{dt.month}月"
                except:
                    return start_str[:7] if start_str else "上期"

            current_period = format_period(time_start)

            # 生成回答
            if is_yoy and yoy_val is not None and yoy_val != 0:
                # 同比数据
                compare_period = format_period(mql.comparison.compare_period_start) if mql.comparison and mql.comparison.compare_period_start else "去年同期"
                if yoy_change:
                    change_desc = f"{yoy_change}%"
                else:
                    change_desc = ""
                answer = f"{metric_name}同比{'上升' if float(str(yoy_change).replace('%','')) > 0 else '下降' if yoy_change else '持平'}{change_desc}。{current_period}为 {int(current_val):,}，{compare_period}为 {int(yoy_val):,}。"
            elif is_mom and mom_val is not None and mom_val != 0:
                # 环比数据
                compare_period = format_period(mql.comparison.compare_period_start) if mql.comparison and mql.comparison.compare_period_start else "上期"
                if mom_change:
                    change_desc = f"{mom_change}%"
                else:
                    change_desc = ""
                answer = f"{metric_name}环比{'上升' if float(str(mom_change).replace('%','')) > 0 else '下降' if mom_change else '持平'}{change_desc}。{current_period}为 {int(current_val):,}，{compare_period}为 {int(mom_val):,}。"
            else:
                # 旧格式 fallback
                if trend == '增长':
                    trend_desc = "增长"
                    change_desc = f"{change_rate}%" if change_rate else ""
                elif trend == '下降':
                    trend_desc = "下降"
                    change_desc = f"{change_rate}%" if change_rate else ""
                else:
                    trend_desc = "持平"
                    change_desc = ""
                compare_period = "对比期"
                answer = f"{metric_name}{period_label}{trend_desc}{change_desc}。{current_period}为 {int(current_val):,}，{compare_period}为 {int(compare_val or 0):,}。"

            current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
            _, alt_label = self._get_alternative_dimensions(current_dim)

            # 获取多个替代维度
            dim_priority = ["FSITE", "GROUP_3", "GROUP_2", "GROUP_1"]
            label_map = self._get_dim_label_from_service()
            dim_type_to_col = {
                "站点": "FSITE", "FSITE": "FSITE",
                "三级品类": "GROUP_3", "GROUP_3": "GROUP_3",
                "二级品类": "GROUP_2", "GROUP_2": "GROUP_2",
                "一级品类": "GROUP_1", "GROUP_1": "GROUP_1",
            }
            current_col = dim_type_to_col.get(current_dim, current_dim.upper()) if current_dim else "FSITE"
            alt_dims = [d for d in dim_priority if d != current_col]

            # 用户问环比 → 推荐同比+异维度；用户问同比 → 推荐环比+异维度
            if is_mom:
                alt_type = "同比"
                same_type = "环比"
            else:
                alt_type = "环比"
                same_type = "同比"

            suggestions = [
                f"查看{time_context}各{alt_label}{metric_name}{alt_type}变化",
            ]
            for dim_col in alt_dims[:2]:
                dim_lbl = label_map.get(dim_col, dim_col)
                suggestions.append(f"查看{time_context}各{dim_lbl}{metric_name}{same_type}变化")

            return {
                "answer": answer,
                "suggestions": suggestions,
            }

        # 传统对比查询（两行数据）
        if len(data) < 2:
            return {
                "answer": "数据不足，无法进行对比",
                "suggestions": [],
            }

        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)
        return {
            "answer": f"对比结果已生成，详见数据",
            "suggestions": [
                f"查看{time_context}各{alt_label}{metric_name}详细数据",
                f"查看{time_context}各{alt_label}{metric_name}趋势变化",
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
        time_context = self._get_time_context(mql)

        lines = ["排名结果："]
        for i, row in enumerate(data[:10], 1):
            parts = [f"{k}: {self._format_value(v)}" for k, v in row.items()]
            lines.append(f"{i}. " + " | ".join(parts))

        metric_name = mql.metric.name if mql.metric else "指标值"

        # 生成维度错开的建议
        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)

        return {
            "answer": "\n".join(lines),
            "suggestions": [
                f"查看更多{time_context}各{alt_label}{metric_name}排名",
                f"查看{time_context}各{alt_label}{metric_name}占比分布",
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
        time_context = self._get_time_context(mql)

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

        # 生成维度错开的建议
        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)

        return {
            "answer": "\n".join(lines),
            "suggestions": [
                f"查看{time_context}各{alt_label}{metric_name}详细数据",
                f"查看{time_context}各{alt_label}{metric_name}趋势变化",
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

    def _is_metric_column(self, column_name: str) -> bool:
        """判断是否为指标列（需要格式化的数值列）"""
        # 常见的指标列名后缀/模式
        metric_patterns = [
            "SALES", "AMOUNT", "COUNT", "NUM", "QTY", "ORDER",
            "REVENUE", "PROFIT", "GMV", "UV", "PV", "CLICK",
            "RATE", "RATIO", "PERCENT", "PCT",
        ]
        # 常见维度列名前缀（不应该格式化的）
        dimension_prefixes = [
            "SKU", "DATE", "TIME", "DT", "FSITE", "CHANNEL",
            "STORE", "SHOP", "CITY", "REGION", "COUNTRY",
            "PRODUCT", "CATEGORY", "BRAND", "CAMPAIGN",
        ]

        upper_name = column_name.upper()

        # 维度列不格式化
        for prefix in dimension_prefixes:
            if upper_name.startswith(prefix):
                return False

        # 指标列模式匹配
        for pattern in metric_patterns:
            if pattern in upper_name:
                return True

        # 默认：如果列名全是大写且像代码，不格式化
        if column_name.isdigit() or (len(column_name) <= 10 and not any(c.isalpha() for c in column_name)):
            return False

        return False

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
