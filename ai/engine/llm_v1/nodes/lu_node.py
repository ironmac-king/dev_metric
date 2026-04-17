"""
LUNode - 意图识别节点（Node1）
输入：用户自然语言查询
输出：{ intent_type, confidence, slots, reasoning }
依赖：指标语义RAG库（pgvector 111个指标向量）
置信度 < 0.7 → 触发澄清
"""
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ..config_loader import get_config_loader
from ..rag.metric_index import get_metric_index
from ..rag.retrieval import get_retrieval
from ..state.session_store import get_session_store, ConversationMessage
from ..prompts.lu_prompt import LU_PROMPT

logger = logging.getLogger("ai.llm_v1.lu_node")


@dataclass
class LUOutput:
    """LU 节点输出"""
    intent_type: str
    confidence: float
    slots: Dict[str, Any]
    reasoning: str
    needs_clarification: bool = False
    clarification_type: Optional[str] = None
    clarification_message: Optional[str] = None


class LUNode:
    """
    意图识别节点（LU - Language Understanding）

    职责：
    1. 意图分类（query_value / query_ranking / compare / trend 等）
    2. 槽位提取（metric / dimensions / time_range / filters / aggregations / operations）
    3. 置信度评估
    4. 多轮对话上下文继承
    """

    def __init__(self):
        self._config_loader = get_config_loader()
        self._metric_index = get_metric_index()
        self._retrieval = get_retrieval()
        self._session_store = get_session_store()
        self._llm_engine = None  # TODO: 后续初始化 LLMEngine

    async def process(
        self,
        question: str,
        session_id: Optional[str] = None,
    ) -> LUOutput:
        """
        处理用户问题，识别意图并提取槽位

        Args:
            question: 用户问题
            session_id: 会话ID（用于多轮对话）

        Returns:
            LUOutput: 意图识别结果
        """
        # 去除多余空格：统一空格为单个空格，去除首尾空白
        question = " ".join(question.split())
        logger.info(f"[LUNode] 处理问题: {question}, session_id={session_id}")

        # Step 1: 获取多轮对话上下文
        context = None
        if session_id:
            context = self._session_store.get_context(session_id)
            logger.info(f"[LUNode] 上下文: {context}")

        # Step 1.5: 同义词预处理 - 将用户输入中的同义词替换为标准术语
        # 例如："不含税收入" -> "未税收入"
        config_loader = get_config_loader()
        resolved_question = config_loader.resolve_synonym(question)
        if resolved_question != question:
            logger.info(f"[LUNode] 同义词替换: '{question}' -> '{resolved_question}'")
        else:
            # 如果没有匹配到同义词，尝试更激进的替换（匹配同义词中的任意一个词）
            business_terms = config_loader.get_config().business_terms
            for syn, standard in business_terms.items():
                if syn in question:
                    resolved_question = question.replace(syn, standard)
                    logger.info(f"[LUNode] 部分同义词替换: '{question}' -> '{resolved_question}'")
                    break

        # Step 2: RAG 检索相关指标（使用替换后的文本）
        metric_context = await self._retrieve_metric_context(resolved_question if resolved_question != question else question)
        logger.info(f"[LUNode] 检索到指标上下文: {metric_context}")

        # Step 3: 构建 Prompt
        prompt = self._build_prompt(question, metric_context, context)

        # Step 4: 调用 LLM
        response_text = await self._call_llm(prompt)
        logger.info(f"[LUNode] LLM 响应: {response_text[:200]}...")

        # Step 5: 解析 LLM 输出
        output = self._parse_llm_response(response_text)

        # Step 6: 处理多轮继承
        if context and not output.slots.get("metric") and context.current_metric:
            output = self._apply_context_inheritance(output, context)

        # Step 7: 置信度检查
        output = self._check_confidence(output)

        # Step 8: 记录历史
        if session_id:
            msg = ConversationMessage(
                role="user",
                content=question,
                slots=output.slots,
                node="LU",
            )
            self._session_store.append_history(session_id, msg)

        logger.info(f"[LUNode] 输出: intent={output.intent_type}, confidence={output.confidence}")
        return output

    def _safe_format_template(self, template: str, vars: dict) -> str:
        """
        安全格式化模板，处理以下情况：
        1. 已知占位符 {var} → 替换为变量值
        2. 转义花括号 {{ }} → 替换为字面 { }
        3. 未知占位符（如 SQL 中的 {dimension}）→ 保持原样
        """
        # 第一步：将转义的花括号 {{ }} 替换为临时占位符
        ESCAPE_PLACEHOLDER = "\x00ESCAPE\x00"
        result = template.replace("{{", ESCAPE_PLACEHOLDER).replace("}}", ESCAPE_PLACEHOLDER)

        # 第二步：替换已知的占位符
        for key, value in vars.items():
            result = result.replace(f"{{{key}}}", str(value))

        # 第三步：将转义占位符替换回花括号
        result = result.replace(ESCAPE_PLACEHOLDER, "}")

        return result

    async def _retrieve_metric_context(self, question: str) -> str:
        """检索指标上下文"""
        try:
            # 搜索相关指标
            search_results = await self._metric_index.search_metric(question, top_k=3)
            if not search_results:
                return ""

            # 构建上下文文本
            contexts = []
            for result in search_results:
                ctx = self._metric_index.build_metric_context_for_prompt(result.metric_info)
                contexts.append(ctx)

            return "\n\n".join(contexts)
        except Exception as e:
            logger.error(f"[LUNode] 检索指标上下文失败: {e}")
            return ""

    def _build_prompt(
        self,
        question: str,
        metric_context: str,
        context: Optional[Any],
    ) -> str:
        """构建 Prompt"""
        # 获取意图类型列表
        intent_types = self._config_loader.get_intent_types()
        intent_types_str = ", ".join(f"'{t}'" for t in intent_types) if intent_types else "query_value, query_ranking, compare, trend, other"

        # 获取当前日期
        from datetime import datetime
        today = datetime.now()
        current_date = today.strftime("%Y-%m-%d")
        current_year = today.year
        current_month = today.month
        # 计算本月第一天
        month_start = today.replace(day=1).strftime("%Y-%m-%d")
        # 计算上月
        if today.month == 1:
            last_month_year = today.year - 1
            last_month = 12
        else:
            last_month_year = today.year
            last_month = today.month - 1
        import calendar
        last_month_days = calendar.monthrange(last_month_year, last_month)[1]
        last_month_start = f"{last_month_year}-{last_month:02d}-01"
        last_month_end = f"{last_month_year}-{last_month:02d}-{last_month_days}"
        # 计算近7天
        days_ago_7 = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        # 计算上周
        days_since_monday = today.weekday()
        last_monday = (today - timedelta(days=days_since_monday + 7)).strftime("%Y-%m-%d")
        last_sunday = (today - timedelta(days=days_since_monday + 1)).strftime("%Y-%m-%d")

        # 格式化上下文
        context_section = ""
        if context:
            context_section = f"## 上一轮上下文（复用这些信息）\n{self._format_context(context)}"
        else:
            context_section = ""

        # 准备模板变量
        template_vars = {
            "intent_types_str": intent_types_str,
            "current_date": current_date,
            "month_start": month_start,
            "last_month_start": last_month_start,
            "last_month_end": last_month_end,
            "days_ago_7": days_ago_7,
            "last_monday": last_monday,
            "last_sunday": last_sunday,
            "current_year": current_year,
            "metric_context": metric_context if metric_context else "（无相关指标信息）",
            "context_section": context_section,
            "question": question,
        }

        # 尝试从数据库加载 prompt
        prompt_template = self._config_loader.get_prompt_template("llm_v1_lu")
        if prompt_template and prompt_template.content:
            # 使用数据库中的 prompt 模板
            try:
                prompt = self._safe_format_template(prompt_template.content, template_vars)
                return prompt
            except Exception as e:
                logger.warning(f"[LUNode] 格式化 prompt 失败: {e}，使用默认 prompt")

        # 降级到硬编码的默认 prompt
        prompt = f"""你是一个意图识别专家。根据用户问题识别其查询意图并提取槽位。

## 意图类型
{intent_types_str}

## 槽位定义

- metric: 指标名称
- metric_code: 指标代码
- dimensions: 维度列表（中文维度名）
- time_range: 时间范围，包含 start, end, original
- filters: 筛选条件
- aggregations: 聚合方式（默认 SUM）
- operations: 操作（如 order_by, limit, compare, percentage）

## 时间转换规则

将自然语言时间转换为具体日期（当前日期: {current_date}）：
- "本月" → start: {month_start}, end: {current_date}
- "上月" → start: {last_month_start}, end: {last_month_end}
- "近7天" → start: {days_ago_7}, end: {current_date}
- "上周" → start: {last_monday}, end: {last_sunday}
- "本季度" → start: {current_year}-01-01（季度初）, end: {current_date}

## 时间维度映射（重要！）

**用户提到时间粒度时，必须正确识别并输出对应的维度名：**

| 用户表达 | 正确维度名 | 说明 |
|---------|-----------|------|
| 每日、每天、日、天、日期 | 日期 | 用于 GROUP BY FDATE |
| 每月、月、月度、月份 | 月份 | 用于 GROUP BY MONTHS |
| 每年、年、年度 | 年度 | 用于 GROUP BY YEARS |
| 每周、周、周次 | 周 | 用于 GROUP BY WEEKS |

**重要：用户说"每日"、"每天"查询趋势时，必须：**
1. 在 dimensions 中输出 "日期"（不是"月份"）
2. time_range 使用具体日期范围

## 维度映射（用于输出 slots，SQL 中使用列名）

| 中文维度名 | 数据库列名 |
|-----------|-----------|
| 三级品类 | GROUP_3 |
| 二级品类 | GROUP_2 |
| 一级品类 | GROUP_1 |
| 店铺 | FSITE |
| 站点 | FSITECODE |
| 平台 | PLATFORM |
| SKU | SKU |
| ASIN | ASIN |

## 相关指标上下文
{metric_context if metric_context else '（无相关指标信息）'}

## 多轮对话处理

{context_section}

## 输出要求

输出 JSON 格式，包含：
- intent_type: 识别的意图类型
- confidence: 置信度（0-1）
- slots: 提取的槽位信息
- reasoning: 推理过程

当需要澄清时（confidence < 0.7）：
- needs_clarification: true
- clarification_type: "metric|time_range|dimension"
- clarification_message: 澄清问题

现在请处理用户问题：
问题：{question}
"""

        return prompt

    def _format_context(self, context) -> str:
        """格式化上下文为文本"""
        if not context:
            return ""

        parts = []
        if context.current_metric:
            parts.append(f"- 上一轮指标：{context.current_metric}")
        if context.current_time:
            parts.append(f"- 上一轮时间：{context.current_time}")
        if context.current_dimensions:
            parts.append(f"- 上一轮维度：{', '.join(context.current_dimensions)}")

        return "\n".join(parts) if parts else "（无）"

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        from ..llm_client import get_llm_client

        llm_client = get_llm_client()
        return await llm_client.call(prompt, temperature=0.7, max_tokens=4000)

    def _parse_llm_response(self, response_text: str) -> LUOutput:
        """解析 LLM 输出"""
        logger.info(f"[LUNode] LLM 原始响应: {response_text[:500]}")
        try:
            # 提取 JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                logger.info(f"[LUNode] 解析后 slots: {data.get('slots', {})}")

                # 检查是否需要澄清
                if data.get("needs_clarification"):
                    return LUOutput(
                        intent_type=data.get("intent_type", "other"),
                        confidence=data.get("confidence", 0.5),
                        slots=data.get("slots", {}),
                        reasoning=data.get("reasoning", ""),
                        needs_clarification=True,
                        clarification_type=data.get("clarification_type"),
                        clarification_message=data.get("clarification_message"),
                    )

                return LUOutput(
                    intent_type=data.get("intent_type", "other"),
                    confidence=data.get("confidence", 0.5),
                    slots=data.get("slots", {}),
                    reasoning=data.get("reasoning", ""),
                )
        except json.JSONDecodeError as e:
            logger.error(f"[LUNode] JSON 解析失败: {e}")

        # 解析失败时的默认返回
        return LUOutput(
            intent_type="other",
            confidence=0.0,
            slots={},
            reasoning="解析失败",
            needs_clarification=True,
            clarification_type="parse_error",
            clarification_message="抱歉，我无法理解您的问题，请重新描述。",
        )

    def _apply_context_inheritance(self, output: LUOutput, context) -> LUOutput:
        """应用多轮对话上下文继承"""
        slots = output.slots.copy() if output.slots else {}

        # 如果当前 slots 没有 metric，尝试从上下文继承
        if not slots.get("metric") and context.current_metric:
            slots["metric"] = context.current_metric
            slots["metric_code"] = context.current_metric_code

        if not slots.get("time_range") and context.current_time:
            slots["time_range"] = {"original": context.current_time}

        if not slots.get("dimensions") and context.current_dimensions:
            slots["dimensions"] = context.current_dimensions

        # 更新输出
        return LUOutput(
            intent_type=output.intent_type,
            confidence=output.confidence,
            slots=slots,
            reasoning=output.reasoning + " [从上下文继承缺失槽位]",
            needs_clarification=output.needs_clarification,
            clarification_type=output.clarification_type,
            clarification_message=output.clarification_message,
        )

    def _check_confidence(self, output: LUOutput) -> LUOutput:
        """置信度检查"""
        threshold = self._config_loader.get_clarification_threshold()

        if output.confidence < threshold:
            output.needs_clarification = True
            output.clarification_type = "low_confidence"
            output.clarification_message = (
                f"我不太确定您的问题（置信度 {output.confidence:.0%}），"
                f"请您确认一下您想知道的是："
            )
            if not output.slots.get("metric"):
                output.clarification_message += "哪个指标？"
            elif not output.slots.get("time_range"):
                output.clarification_message += "什么时间范围？"
            else:
                output.clarification_message += "能否详细描述一下？"

        return output


# 全局实例
_lu_node: Optional[LUNode] = None


def get_lu_node() -> LUNode:
    """获取 LU 节点单例"""
    global _lu_node
    if _lu_node is None:
        _lu_node = LUNode()
    return _lu_node
