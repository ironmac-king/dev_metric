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
        # 策略：优先匹配更长的同义词，避免部分匹配问题
        config_loader = get_config_loader()
        business_terms = config_loader.get_config().business_terms

        # 按长度降序排列，优先匹配更长的词
        sorted_terms = sorted(business_terms.items(), key=lambda x: len(x[0]), reverse=True)

        resolved_question = question
        for syn, standard in sorted_terms:
            if syn in question:
                resolved_question = question.replace(syn, standard)
                logger.info(f"[LUNode] 同义词替换: '{question}' -> '{resolved_question}' (matched: '{syn}' -> '{standard}')")
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

        # 始终保存原始问题到 slots（供后续节点检测占比等关键词）
        if output.slots is None:
            output.slots = {}
        output.slots["original_question"] = question
        # 只有在有同义词替换时才保存 resolved_question
        if resolved_question != question:
            output.slots["resolved_question"] = resolved_question
            logger.info(f"[LUNode] 保存 resolved_question 到 slots: {resolved_question}")

        # Step 6: 处理多轮继承
        # 继承条件：
        # 1. 当前没有 metric → 继承上轮 metric
        # 2. 当前输入只有维度词（如"三级品类"、"二级品类"）→ 强制继承上轮 metric
        # 3. 当前输入是意图追问文本（如"同比环比变化对比看"、"查看趋势"）→ 强制继承上轮 metric
        if context and context.current_metric:
            is_dimension_only = self._is_dimension_only_question(question)
            is_intent_followup, followup_operations = self._is_intent_followup_question(question)
            if is_dimension_only:
                logger.info(f"[LUNode] 检测到仅维度问题，强制继承上轮 metric: {context.current_metric}")
            elif is_intent_followup:
                logger.info(f"[LUNode] 检测到意图追问，强制继承上轮 metric: {context.current_metric}")
            if not output.slots.get("metric") or is_dimension_only or is_intent_followup:
                output = self._apply_context_inheritance(output, context, force_override_metric=is_intent_followup)

            # 如果检测到意图追问且有特定操作类型（如 compare、trend），设置 operations
            if is_intent_followup and followup_operations:
                output.slots["operations"] = followup_operations
                logger.info(f"[LUNode] 设置 operations: {followup_operations}")

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

    def _apply_context_inheritance(self, output: LUOutput, context, force_override_metric: bool = False) -> LUOutput:
        """应用多轮对话上下文继承

        Args:
            output: LU 输出
            context: 会话上下文
            force_override_metric: 是否强制覆盖 metric（用于意图追问场景）
        """
        slots = output.slots.copy() if output.slots else {}

        # 如果当前 slots 没有 metric，或者强制要求覆盖，则从上下文继承
        if (not slots.get("metric") or force_override_metric) and context.current_metric:
            slots["metric"] = context.current_metric
            slots["metric_code"] = context.current_metric_code

        if not slots.get("time_range") and context.current_time:
            slots["time_range"] = {"original": context.current_time}

        if not slots.get("dimensions") and context.current_dimensions:
            slots["dimensions"] = context.current_dimensions

        # 防御性检查：当问题包含"分布"类关键词但维度是"日期"时，清除维度让 SF 节点重新映射
        # 例如 "本月销售额分布在哪？" 不应该继承上轮的日期维度，而应该映射到平台/站点
        original_question = slots.get("original_question", "")
        if "分布" in original_question and slots.get("dimensions") == ["日期"]:
            logger.info(f"[LUNode] 检测到'分布'追问但维度为日期，清除维度让 SF 节点重新映射")
            slots["dimensions"] = None

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

    def _is_dimension_only_question(self, question: str) -> bool:
        """
        检测是否为仅维度问题（没有指标名，只有维度词）

        例如：
        - "三级品类" → True
        - "二级品类" → True
        - "一级品类" → True
        - "平台" → True
        - "店铺" → True
        - "销售额" → False（有指标名）
        - "本月销售额" → False（有指标名）
        """
        if not question:
            return False

        question = question.strip().lower()

        # 纯维度词列表（按长度降序排列）
        dimension_words = [
            "三级品类", "二级品类", "一级品类",
            "品类", "类目", "商品类", "产品类",
            "平台", "站点",
            "店铺", "商店",
            "sku", "asin",
            "月份", "年度", "季度", "周",
            "日期", "每日", "每天",
        ]

        # 清理问题文本（去除时间词等修饰词）
        cleaned = question
        time_words = ["本月", "上月", "近7天", "近30天", "上周", "本周", "昨天", "今天"]
        for tw in time_words:
            cleaned = cleaned.replace(tw, "")

        cleaned = cleaned.strip()

        # 如果清理后只剩下维度词，则是纯维度问题
        for dim in dimension_words:
            if dim in cleaned:
                # 进一步检查：清理后不包含明显的指标关键词
                metric_keywords = ["销售额", "收入", "利润", "成本", "订单", "点击", "转化", "会话",
                                   "退款", "退货", "广告", "花费", "运费", "费率", "客单价", "产出"]
                for kw in metric_keywords:
                    if kw in cleaned:
                        return False
                return True

        return False

    def _is_intent_followup_question(self, question: str) -> tuple:
        """
        检测是否为意图追问（点击建议按钮时发送的纯意图文本）

        返回: (is_intent_followup: bool, operations: list or None)
        如果返回的 operations 不为 None，说明需要设置特定操作类型

        例如：
        - "同比环比变化对比看" → (True, [{"type": "compare", "compare_type": "同比环比"}])
        - "查看趋势" → (True, [{"type": "trend"}])
        - "本月销售额是多少" → (False, None)
        - "三级品类" → (False, None)
        """
        if not question:
            return False, None

        question = question.strip()

        logger.info(f"[_is_intent_followup_question] 检查追问模式: question='{question}', len={len(question)}")

        # 意图追问关键词（按长度降序排列）
        intent_followup_patterns = [
            "同比环比变化对比看", "同比环比对比看", "同比环比",
            "对比看", "对比分析",
            "查看趋势", "看趋势", "趋势分析",
            "变化趋势", "涨跌情况",
            "本月销售占比分布全览", "销售占比分布全览",
            "销售额本月走势", "本月走势",
            "分布如何", "占比如何", "占比情况",
            "哪个最高", "哪个最低", "最高的是",
            "明细查看", "查看明细",
            "拆解分析", "结构分析",
        ]

        # 直接匹配完整的追问文本
        for pattern in intent_followup_patterns:
            if pattern in question:
                # 检查是否包含同比/环比关键词
                has_yoy = "同比" in question
                has_mom = "环比" in question
                if has_yoy or has_mom:
                    # 同时包含同比和环比时，返回两个独立操作
                    if has_yoy and has_mom:
                        return True, [
                            {"type": "compare", "compare_type": "同比"},
                            {"type": "compare", "compare_type": "环比"}
                        ]
                    elif has_yoy:
                        return True, [{"type": "compare", "compare_type": "同比"}]
                    else:
                        return True, [{"type": "compare", "compare_type": "环比"}]
                if "趋势" in question or "走势" in question:
                    return True, [{"type": "trend"}]
                if "占比" in question or "比例" in question:
                    return True, [{"type": "percentage"}]
                return True, None

        # 检查是否只有意图动词（很短的问题）
        if len(question) <= 10:
            intent_verbs = ["对比", "比较", "趋势", "变化", "涨跌", "分布", "占比", "最高", "最低", "明细", "拆解", "分析"]
            for verb in intent_verbs:
                if verb in question:
                    # 特别处理同比/环比
                    has_yoy = "同比" in question
                    has_mom = "环比" in question
                    if has_yoy or has_mom:
                        if has_yoy and has_mom:
                            return True, [
                                {"type": "compare", "compare_type": "同比"},
                                {"type": "compare", "compare_type": "环比"}
                            ]
                        elif has_yoy:
                            return True, [{"type": "compare", "compare_type": "同比"}]
                        else:
                            return True, [{"type": "compare", "compare_type": "环比"}]
                    if "趋势" in question or "走势" in question:
                        return True, [{"type": "trend"}]
                    return True, None

        return False, None

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
