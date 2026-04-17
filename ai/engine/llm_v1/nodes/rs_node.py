"""
RSNode - 报告生成节点（Node8）
输入：Node6 结果 + Node7 图表配置 + 原始 slots
输出：{ answer, chart_config, suggestions }
职责：
1. 简单结果 → 模板生成回答
2. 复杂结果 → LLM 生成自然语言
3. 维度名反向映射（铁律四）
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..config_loader import get_config_loader
from ..state.session_store import get_session_store, ConversationMessage
from ..recommendation_engine import get_recommendation_engine
from .chart_node import ChartOutput

logger = logging.getLogger("ai.llm_v1.rs_node")


@dataclass
class RSOutput:
    """RS 节点输出"""
    answer: str  # 自然语言回答
    thinking_steps: List[Dict[str, str]]  # 分析步骤（可折叠）
    sql: str  # 生成的 SQL
    chart_config: Dict[str, Any]  # 图表配置
    suggestions: List[str]  # 追问建议
    anomaly_warnings: List[str]  # 异常警告


class RSNode:
    """
    报告生成节点（RS - Report Summary）

    职责：
    1. **结果描述生成**：
       - 简单结果 → 模板生成
       - 复杂结果 → LLM 生成

    2. **维度名反向映射**（铁律四）：
       - 将 column_name 反向映射为 dimension_name
       - 仅用于展示

    3. **追问建议生成**：
       - 基于当前结果生成可能的追问方向
    """

    def __init__(self):
        self._config_loader = get_config_loader()
        self._session_store = get_session_store()
        self._recommendation_engine = get_recommendation_engine()
        self._llm_engine = None  # TODO: 后续初始化

    async def process(
        self,
        ex_output,  # EXOutput
        rv_output,  # RVOutput
        chart_output,  # ChartOutput
        slots: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> RSOutput:
        """
        生成报告

        Args:
            ex_output: EX 节点输出
            rv_output: RV 节点输出
            chart_output: Chart 节点输出
            slots: 原始槽位信息
            session_id: 会话ID

        Returns:
            RSOutput: 报告输出
        """
        logger.info(f"[RSNode] 生成报告: rows={ex_output.row_count}")

        # Step 1: 反向映射维度名（用于展示）
        display_columns = self._reverse_map_dimensions(ex_output.columns)

        # Step 2: 生成分析步骤
        thinking_steps = self._build_thinking_steps(ex_output, display_columns, slots)

        # Step 3: 生成回答（只包含最终结果）
        answer = await self._generate_answer(
            ex_output, rv_output, display_columns, slots
        )

        # Step 4: 构建图表配置
        chart_config = self._build_chart_config(chart_output, display_columns)

        # Step 5: 生成追问建议
        suggestions = await self._generate_suggestions(ex_output, slots)

        # Step 6: 提取异常警告
        anomaly_warnings = [
            flag.get("message", "")
            for flag in rv_output.anomaly_flags
        ]

        output = RSOutput(
            answer=answer,
            thinking_steps=thinking_steps,
            sql=ex_output.sql,
            chart_config=chart_config,
            suggestions=suggestions,
            anomaly_warnings=anomaly_warnings,
        )

        logger.info(f"[RSNode] 生成回答: {answer[:100]}...")

        # Step 7: 保存到会话历史
        if session_id:
            msg = ConversationMessage(
                role="assistant",
                content=answer,
                sql=ex_output.sql,
                answer=answer,
                chart_config=chart_config,
                thinking_steps=output.thinking_steps,
                result_data=ex_output.data,
                suggestions=output.suggestions,
                node="RS",
            )
            self._session_store.append_history(session_id, msg)

        return output

    def _reverse_map_dimensions(self, columns: List[str]) -> List[str]:
        """
        维度名反向映射（铁律四）
        将 column_name 反向映射为 dimension_name（仅用于展示）
        """
        reverse_map = self._config_loader.get_reverse_dimension_map()
        display_columns = []

        for col in columns:
            display_name = reverse_map.get(col, col)
            display_columns.append(display_name)

        return display_columns

    def _build_thinking_steps(
        self,
        ex_output,
        display_columns: List[str],
        slots: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """构建分析步骤（用于可折叠展示）"""
        steps = []
        metric = slots.get("metric", "指标")
        time_range = slots.get("time_range", {}).get("original", "")
        time_start = slots.get("time_range", {}).get("start", "")
        time_end = slots.get("time_range", {}).get("end", "")
        dimensions = slots.get("dimensions", [])

        # 步骤1：查询条件
        step1_content = f"查询条件：{time_range}"
        if time_start and time_end:
            step1_content += f"\n时间范围：{time_start} 至 {time_end}"
        if dimensions:
            dim_str = "、".join([str(d) for d in dimensions]) if isinstance(dimensions, list) else str(dimensions)
            step1_content += f"\n维度筛选：{dim_str}"
        else:
            step1_content += "\n维度筛选：无（汇总统计）"
        steps.append({
            "step": "查询条件",
            "status": "completed",
            "content": step1_content
        })

        # 步骤2：数据来源
        steps.append({
            "step": "数据来源",
            "status": "completed",
            "content": f"数据表：ids.IDS_AMZ_COMPREHENSIVE_DI"
        })

        # 步骤3：计算方式
        steps.append({
            "step": "计算方式",
            "status": "completed",
            "content": f"对 ORDER_PRODUCTSALES 字段求和（SUM）"
        })

        # 步骤4：查询结果
        if ex_output.row_count == 0:
            steps.append({
                "step": "查询结果",
                "status": "completed",
                "content": f"在{time_range}内没有找到{metric}的相关数据"
            })
        else:
            data = ex_output.data
            if len(data) == 1:
                row = data[0]
                value = row.get(ex_output.columns[-1], 0)
                try:
                    num_value = float(value)
                    steps.append({
                        "step": "查询结果",
                        "status": "completed",
                        "content": f"{time_range}{metric}为 {num_value:,.2f}"
                    })
                except (ValueError, TypeError):
                    steps.append({
                        "step": "查询结果",
                        "status": "completed",
                        "content": f"{time_range}{metric}为 {value}"
                    })
            else:
                steps.append({
                    "step": "查询结果",
                    "status": "completed",
                    "content": f"共 {len(data)} 条数据"
                })

        return steps

    async def _generate_answer(
        self,
        ex_output,
        rv_output,
        display_columns: List[str],
        slots: Dict[str, Any],
    ) -> str:
        """生成回答"""
        # 空数据处理
        if ex_output.row_count == 0:
            return self._generate_empty_answer(slots)

        # 简单结果（少量数据）→ 模板生成
        if ex_output.row_count <= 3:
            return self._generate_template_answer(ex_output, display_columns, slots)

        # 复杂结果 → LLM 生成
        return await self._generate_llm_answer(ex_output, display_columns, rv_output, slots)

    def _generate_empty_answer(self, slots: Dict[str, Any]) -> str:
        """生成空数据回答"""
        metric = slots.get("metric", "该指标")
        time_range = slots.get("time_range", {}).get("original", "")
        time_start = slots.get("time_range", {}).get("start", "")
        time_end = slots.get("time_range", {}).get("end", "")

        analysis_parts = []
        analysis_parts.append("【分析过程】")
        analysis_parts.append(f"1. 查询条件：{time_range}")
        if time_start and time_end:
            analysis_parts.append(f"   - 时间范围：{time_start} 至 {time_end}")
        analysis_parts.append(f"2. 数据来源：ids.IDS_AMZ_COMPREHENSIVE_DI")
        analysis_parts.append(f"3. 计算方式：对 ORDER_PRODUCTSALES 字段求和（SUM）")
        analysis_parts.append("")
        analysis_parts.append("【查询结果】")
        analysis_parts.append(f"抱歉，在{time_range}内没有找到{metric}的相关数据。")
        analysis_parts.append("")
        analysis_parts.append("【可能原因】")
        analysis_parts.append("1. 时间范围内确实没有数据")
        analysis_parts.append("2. 请确认查询的时间范围是否正确")
        analysis_parts.append("3. 指标口径可能发生了变化")
        analysis_parts.append("")
        analysis_parts.append("【建议】")
        analysis_parts.append("- 尝试扩大时间范围")
        analysis_parts.append("- 检查指标配置是否正确")

        return "\n".join(analysis_parts)

    def _strip_markdown(self, text: str) -> str:
        """去除 Markdown 格式标记，转换为纯文本"""
        # 去除粗体 **text** -> text
        while '**' in text:
            text = text.replace('**', '')
        return text

    def _generate_template_answer(
        self,
        ex_output,
        display_columns: List[str],
        slots: Dict[str, Any],
    ) -> str:
        """模板生成简单回答（只返回最终结果，不包含分析过程）"""
        metric = slots.get("metric", "指标")
        time_range = slots.get("time_range", {}).get("original", "")
        data = ex_output.data

        if len(data) == 1:
            # 单值查询 - 只返回结果
            row = data[0]
            value = row.get(ex_output.columns[-1], 0)
            try:
                num_value = float(value)
                return f"{time_range}{metric}为 {num_value:,.2f}"
            except (ValueError, TypeError):
                return f"{time_range}{metric}为 {value}"

        # 多行数据
        result_lines = [f"共 {len(data)} 条数据："]
        for i, row in enumerate(data, 1):
            parts = []
            for j, col in enumerate(ex_output.columns):
                display_name = display_columns[j] if j < len(display_columns) else col
                value = row.get(col, "N/A")
                try:
                    num_val = float(value)
                    parts.append(f"{display_name}={num_val:,.2f}")
                except (ValueError, TypeError):
                    parts.append(f"{display_name}={value}")
            result_lines.append(f"{i}. " + ", ".join(parts))

        return "\n".join(result_lines)

    async def _generate_llm_answer(
        self,
        ex_output,
        display_columns: List[str],
        rv_output,
        slots: Dict[str, Any],
    ) -> str:
        """LLM 生成复杂回答"""
        from ..llm_client import get_llm_client

        # 构建 Prompt
        prompt = self._build_llm_answer_prompt(ex_output, display_columns, rv_output, slots)

        # 调用 LLM
        llm_client = get_llm_client()
        try:
            answer = await llm_client.call(prompt, temperature=0.7, max_tokens=2000)
            return answer
        except Exception as e:
            logger.error(f"[RSNode] LLM 生成回答失败: {e}")
            # 降级到模板生成
            return self._generate_template_answer(ex_output, display_columns, slots)

    def _build_llm_answer_prompt(
        self,
        ex_output,
        display_columns: List[str],
        rv_output,
        slots: Dict[str, Any],
    ) -> str:
        """构建 LLM 回答 Prompt"""
        metric = slots.get("metric", "指标")
        time_range = slots.get("time_range", {}).get("original", "")

        # 构建数据预览
        data_preview = []
        for row in ex_output.data[:5]:
            data_preview.append(", ".join(f"{display_columns[i]}={row.get(col, 'N/A')}"
                                         for i, col in enumerate(ex_output.columns)))
        data_preview_text = "\n".join(data_preview)

        prompt = f"""你是一个数据分析助手。用户查询了「{metric}」，时间范围是「{time_range}」。

查询结果如下：
{data_preview_text}

请根据查询结果，用自然语言向用户解释数据。注意：
1. 突出关键数据点
2. 如有异常，在回答中提醒用户
3. 回答要简洁明了

请生成回答："""

        return prompt

    def _build_chart_config(
        self,
        chart_output: ChartOutput,
        display_columns: List[str],
    ) -> Dict[str, Any]:
        """构建图表配置"""
        if chart_output.chart_type == "none":
            return {}

        # 替换列为中文名
        config = chart_output.echarts_config.copy()

        if config.get("bar"):
            if "xAxis" in config["bar"]:
                config["bar"]["xAxis"]["name"] = self._to_display_name(
                    config["bar"]["xAxis"].get("name", "")
                )
        elif config.get("line"):
            if "xAxis" in config["line"]:
                config["line"]["xAxis"]["name"] = self._to_display_name(
                    config["line"]["xAxis"].get("name", "")
                )

        return config

    def _to_display_name(self, name: str) -> str:
        """转换为展示名"""
        reverse_map = self._config_loader.get_reverse_dimension_map()
        return reverse_map.get(name, name)

    async def _generate_suggestions(
        self,
        ex_output,
        slots: Dict[str, Any],
    ) -> List[str]:
        """
        生成追问建议（规则骨架 + LLM 润色混合架构）

        1. 生成结构化意图（下钻/排行/趋势/对比）
        2. LLM 润色为口语化的自然语言
        3. 失败时降级到模板生成
        """
        # 调试日志
        logger.info(f"[RSNode] _generate_suggestions called: metric={slots.get('metric')}, dimensions={slots.get('dimensions')}, row_count={getattr(ex_output, 'row_count', 0)}")

        # 1. 生成结构化意图
        intents = self._recommendation_engine.generate_intents(slots, ex_output)
        logger.info(f"[RSNode] generate_intents returned: {len(intents)} intents")

        if not intents:
            return []

        # 2. LLM 润色
        suggestions = await self._recommendation_engine.polish_with_llm(intents)
        logger.info(f"[RSNode] polish_with_llm returned: {suggestions}")

        if suggestions:
            logger.info(f"[RSNode] LLM 润色建议: {suggestions}")
            return suggestions

        # 3. 降级到模板生成
        logger.info("[RSNode] LLM 润色失败，降级到模板生成")
        template_suggestions = self._recommendation_engine.generate_suggestions_template(slots, ex_output)
        logger.info(f"[RSNode] template returned: {template_suggestions}")
        return template_suggestions


# 全局实例
_rs_node: Optional[RSNode] = None


def get_rs_node() -> RSNode:
    """获取 RS 节点单例"""
    global _rs_node
    if _rs_node is None:
        _rs_node = RSNode()
    return _rs_node
