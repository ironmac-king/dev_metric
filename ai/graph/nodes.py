"""
LangGraph 对话节点 - 优化版
"""
import re
import os
import calendar
from typing import Dict, Any, Optional, List
from ai.graph.state import ConversationState, IntentResult, SQLGenerationResult, ClarificationDecision, ThinkingStep, ConversationContext
from ai.engine.rule_engine import RuleEngine
from ai.engine.llm import LLMEngine
from ai.sql_gen.generator import SQLGenerator
from ai.client.metric_client import MetricClient
from ai.client.dim_value_client import DimValueClient
from ai.config.logging_config import get_logger

logger = get_logger("ai.nodes")


# 延迟导入 Neo4j 相关模块，避免启动时必须连接
def _get_graph_query():
    """延迟加载 GraphQuery，避免 Neo4j 未启动时影响整体功能"""
    try:
        from ai.knowledge_graph.query import GraphQuery
        return GraphQuery()
    except Exception as e:
        if os.getenv("DEBUG"):
            logger.warning(f"GraphQuery 加载失败: {e}")
        return None


class ConversationNodes:
    """对话节点"""

    def __init__(self):
        self.rule_engine = RuleEngine()
        self.llm_engine = LLMEngine()
        self.sql_generator = SQLGenerator()
        self.metric_client = MetricClient()

    def _add_thinking_step(self, state: ConversationState, step: str, status: str = "completed", content: str = None, llm_used: bool = False):
        """记录思考步骤"""
        state.thinking_steps.append(ThinkingStep(
            step=step,
            status=status,
            content=content,
            llm_used=llm_used
        ))

    def intent_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        意图识别节点 - 纯 LLM 架构
        直接调用 LLM 进行意图识别和实体提取，不再使用规则/语义/TF-IDF 降级
        """
        last_message = state.messages[-1].content if state.messages else ""

        # ========== Step 0: 处理对追问/满意确认的回复 ==========
        # 场景A: 上一轮问了意图选择，用户选"指标值"/"趋势"等
        # 场景B: 上一轮返回"暂无数据"后，用户回复短词（如"指标值"），表示确认/重试
        prev_clar_type = getattr(state, '_prev_clarification_type', None)
        ctx = getattr(state, 'conversation_context', None)
        is_satisfaction_reply = (
            prev_clar_type == 'intent' or  # 场景A
            (len(last_message.strip()) <= 4 and ctx is not None)  # 场景B
        )
        logger.debug(f"[intent_node Step0] msg='{last_message}' len={len(last_message.strip())} prev_clar={prev_clar_type} ctx={ctx} is_satis={is_satisfaction_reply}")

        if is_satisfaction_reply:
            intent_map = {
                "指标值": "query_value", "数值": "query_value", "值": "query_value",
                "趋势": "query_trend", "走势": "query_trend",
                "对比": "query_comparison", "比较": "query_comparison",
            }
            matched_intent = None
            for keyword, intent in intent_map.items():
                if keyword in last_message:
                    matched_intent = intent
                    break

            # 场景B：用户回复很短但有历史上下文
            if not matched_intent and len(last_message.strip()) <= 4:
                # 用户说"环比呢"/"同比呢"，用 LLM 补齐为完整问题
                if last_message.strip() in ["环比呢", "同比呢", "环比", "同比"]:
                    ctx = getattr(state, 'conversation_context', None)
                    if ctx and ctx.current_metric_name:
                        # 用 LLM 补齐短文本
                        comparison_type = "环比" if "环比" in last_message else "同比"
                        expanded = self.llm_engine.expand_followup_question(
                            last_message, ctx.current_metric_name, ctx.current_time_expr, comparison_type
                        )
                        logger.info(f"[intent_node] LLM补齐: '{last_message}' → '{expanded}'")
                        # 更新用户消息
                        state.messages[-1].content = expanded
                        self._add_thinking_step(state, "意图理解", "completed",
                            f"LLM补齐追问：'{expanded}'")
                        # 从 conversation_context 恢复指标和时间上下文
                        restored_entities = {
                            "metric_name": ctx.current_metric_name,
                            "metric_code": ctx.current_metric_code,
                        }
                        if ctx.current_time_expr:
                            restored_entities["time_range"] = ctx.current_time_expr
                        state.entities.update(restored_entities)
                        # 补齐后直接返回，让后续流程处理完整问题
                        return {
                            "current_intent": "query_comparison",
                            "entities": restored_entities
                        }
                    else:
                        matched_intent = "query_value"
                else:
                    matched_intent = "query_value"

            # 如果 matched_intent 已确定（非短文本追问），走原有逻辑
            if matched_intent and not (len(last_message.strip()) <= 4 and last_message.strip() in ["环比呢", "同比呢", "环比", "同比"]):
                state.needs_clarification = False
                state.clarification_type = None
                state.clarification_message = None
                state._prev_clarification_type = None
                state._prev_clarification_message = None
                # 标记：Step 0 已确认意图并恢复了上下文，entity_node 不要清除这些字段
                state._intent_confirmed_from_context = True

                # 从 conversation_context 恢复指标和时间上下文
                ctx = getattr(state, 'conversation_context', None)
                restored_entities = {}
                if ctx:
                    if ctx.current_metric_name:
                        restored_entities["metric_name"] = ctx.current_metric_name
                    if ctx.current_metric_code:
                        restored_entities["metric_code"] = ctx.current_metric_code
                    if ctx.current_time_expr:
                        restored_entities["time_range"] = ctx.current_time_expr
                    for dim_key, dim_val in (ctx.current_dimensions or {}).items():
                        if dim_val and dim_key not in restored_entities:
                            restored_entities[dim_key] = dim_val

                state.entities.update(restored_entities)
                self._add_thinking_step(state, "意图理解", "completed",
                    f"用户确认意图：{matched_intent}（{'追问回复' if prev_clar_type == 'intent' else '满意度确认'}）")
                return {"current_intent": matched_intent, "entities": restored_entities}

        # ========== Step 1: 复用上下文 ==========
        inherited_context = getattr(state, 'conversation_context', None) or ConversationContext()
        inherited_entities = {}
        if inherited_context.current_metric_name:
            inherited_entities = {
                "inherited_metric": inherited_context.current_metric_name,
                "inherited_metric_name": inherited_context.current_metric_name,
            }

        logger.debug(f"[intent_node] 输入: {last_message}")

        # ========== Step 2: 直接调用 LLM 进行意图识别 ==========
        # 不再使用规则层 → 语义搜索 → TF-IDF 的降级架构
        # 直接使用 LLM recognize_intent_enhanced，传入上下文和指标库信息
        available_metrics_info = self.rule_engine.metric_templates if hasattr(self.rule_engine, 'metric_templates') else {}

        try:
            # 调用 LLM recognize_intent_enhanced 进行意图识别
            intent_result = self.llm_engine.recognize_intent_enhanced(
                text=last_message,
                inherited_entities=inherited_entities
            )
            logger.debug(f"[intent_node] LLM 识别结果: intent={intent_result.intent}, confidence={intent_result.confidence}, entities={intent_result.entities}")

            # 如果置信度太低，标记为需要追问
            if intent_result.confidence < 0.4:
                state.needs_clarification = True
                state.clarification_type = "intent"
                state.clarification_message = "抱歉，我没理解您的意思。您是想查询指标值、趋势、还是对比数据呢？"
                self._add_thinking_step(state, "意图理解", "requires_clarification",
                    f"LLM 置信度 {intent_result.confidence:.2f} < 0.4，需要追问")
                return {"current_intent": None, "entities": intent_result.entities}

            # 补充 time_info（LLM 可能只返回 time_range 字符串，没有 time_info 对象）
            if intent_result.entities.get("time_range") and not intent_result.entities.get("time_info"):
                time_info = self._extract_time_info(last_message)
                if time_info:
                    intent_result.entities["time_info"] = time_info
                    logger.debug(f"[intent_node] 补充 time_info: {time_info}")

            # 检查用户输入是否真的包含时间词（防止 LLM 错误推断）
            has_explicit_time = bool(re.search(
                r'昨天|今日|明日|昨日|本周|本月|上周|上月|去年|今年|明年|上个月|'
                r'近几|最近|过去|前几|天前|月前|周前|年前|'
                r'\d+月|\d+天|\d+周',
                last_message
            ))
            if intent_result.entities.get("time_range") and not has_explicit_time:
                # 用户没说时间，LLM 不应该推断，清除并触发追问
                logger.debug(f"[intent_node] 用户未明确时间，清除 LLM 推断的 time_range")
                intent_result.entities.pop("time_range", None)
                intent_result.entities.pop("time_info", None)
                intent_result.entities.pop("time_key", None)

            # 补充 top_n 排名信息（检测"前三"、"前十"、"前13"等模式）
            if not intent_result.entities.get("top_n"):
                top_n = self._extract_top_n(last_message)
                if top_n:
                    intent_result.entities["top_n"] = top_n
                    logger.debug(f"[intent_node] 检测到 top_n: {top_n}")

        except Exception as e:
            logger.error(f"[intent_node] LLM 意图识别失败: {e}")
            # LLM 失败时，使用默认值
            intent_result = IntentResult(
                intent="query_value",
                confidence=0.3,
                entities={}
            )

        # ========== 更新上下文 ==========
        self._update_context(state, intent_result.entities)

        # 记录思考步骤
        intent_desc = {
            "query_value": "查询数值",
            "query_trend": "查询趋势",
            "query_comparison": "对比分析",
            "query_metadata": "查询元数据",
            "greeting": "问候",
            "thanks": "感谢",
            "bye": "告别",
        }.get(intent_result.intent, intent_result.intent)

        self._add_thinking_step(state, "意图理解", "completed",
            f"LLM 识别为「{intent_desc}」，置信度 {intent_result.confidence:.2f}")

        return {
            "current_intent": intent_result.intent,
            "entities": intent_result.entities,
        }

    def _llm_review_intent(self, state: ConversationState, semantic_intent: str, similarity: float):
        """LLM 审核意图（中等置信度时调用）"""
        last_message = state.messages[-1].content if state.messages else ""
        available_metrics_info = self.rule_engine.metric_templates if hasattr(self.rule_engine, 'metric_templates') else {}

        # 构建候选意图
        candidate_intent = semantic_intent

        intent_result = self.llm_engine.validate_and_correct_intent(
            text=last_message,
            rule_intent=candidate_intent,
            rule_entities={},
            available_metrics_info=available_metrics_info,
            inherited_entities={},
            metric_context=None
        )

        # 补充 time_info（validate_and_correct_intent 只返回 time_range 字符串，没有 time_info 对象）
        if intent_result.entities.get("time_range") and not intent_result.entities.get("time_info"):
            time_info = self._extract_time_info(last_message)
            if time_info:
                intent_result.entities["time_info"] = time_info
                logger.debug(f"[_llm_review_intent] 补充 time_info: {time_info}")

        # 补充 top_n 排名信息（检测"前三"、"前十"、"前13"等模式）
        if not intent_result.entities.get("top_n"):
            top_n = self._extract_top_n(last_message)
            if top_n:
                intent_result.entities["top_n"] = top_n
                logger.debug(f"[_llm_review_intent] 检测到 top_n: {top_n}")

        self._update_context(state, intent_result.entities)
        self._add_thinking_step(state, "意图理解", "completed",
            f"LLM审核确认「{intent_result.intent}」，原始相似度 {similarity:.2f}")

        return intent_result

    def _update_context(self, state: ConversationState, entities: Dict[str, Any]):
        """更新对话上下文"""
        ctx = getattr(state, 'conversation_context', None) or ConversationContext()

        # 更新指标信息
        if entities.get("metric_name"):
            ctx.current_metric_name = entities.get("metric_name")
        if entities.get("metric_code"):
            ctx.current_metric_code = entities.get("metric_code")

        # 更新时间表达式
        if entities.get("time_range"):
            ctx.current_time_expr = entities.get("time_range")

        # 更新维度
        for dim_key in ["platform", "region", "department", "site", "category", "device"]:
            if entities.get(dim_key):
                ctx.current_dimensions[dim_key] = entities.get(dim_key)

        state.conversation_context = ctx

    def _extract_potential_dim_values(self, text: str, entities: Dict) -> List[str]:
        """
        从用户输入中提取可能是维度值的词
        排除：指标名、时间、已识别的维度
        策略：优先提取完整的维度值（4-8字），避免将 "笔记本支架" 拆成 "笔记本"
        """
        import re
        metric_name = entities.get("metric_name", "") or ""

        # 使用重叠匹配来提取所有可能的维度值
        # (?=...) 是 lookahead，不消耗字符，所以可以重叠匹配
        results = []

        # 提取4-8字的完整维度值（更可能精确匹配）
        for length in [8, 7, 6, 5, 4]:
            # 使用 lookahead 实现重叠匹配
            pattern = re.compile(rf'(?=[\u4e00-\u9fa5]{{{length}}})[\u4e00-\u9fa5]')
            for match in pattern.finditer(text):
                start, _ = match.span()
                segment = text[start:start + length]
                # 跳过时间词和指标名
                if self._is_time_word(segment):
                    continue
                if segment in metric_name or metric_name in segment:
                    continue
                if segment not in results:  # 避免重复
                    results.append(segment)

        # 如果没有找到4-8字的词，尝试提取2-3字的短词
        if not results:
            for length in [3, 2]:
                pattern = re.compile(rf'(?=[\u4e00-\u9fa5]{{{length}}})[\u4e00-\u9fa5]')
                for match in pattern.finditer(text):
                    start, _ = match.span()
                    segment = text[start:start + length]
                    if self._is_time_word(segment):
                        continue
                    if segment in metric_name or metric_name in segment:
                        continue
                    if segment not in results:
                        results.append(segment)

        # 提取数字/字母混合序列（SKU、ASIN等），长度为3-20
        # 注意：无论是否找到中文候选，都需要提取数字/字母序列
        # 因为"上月1011"中的"1011"应该被提取
        alphanum_pattern = re.compile(r'[A-Za-z0-9]{3,20}')
        for match in alphanum_pattern.finditer(text):
            segment = match.group()
            # 跳过时间相关的数字（如月份、日期）
            if self._is_time_word(segment):
                continue
            # 跳过紧跟"年"或"月"的4位年份数字（如"2024年"），但不跳过"上月1011"中的"1011"
            # 检查数字前面的字符，如果是"月"或"年"需要确认它是否属于时间词的一部分
            start_idx = match.start()
            if start_idx > 0:
                prev_char = text[start_idx - 1]
                if re.match(r'^\d{4}$', segment) and prev_char in '年月':
                    # 检查前面的2个字符是否构成时间词（如"上月"、"本月"、"去年"等）
                    two_chars_before = text[max(0, start_idx-2):start_idx]
                    time_words_with_suffix = ['上月', '本月', '下月', '去年', '今年', '明年', '上月']
                    if two_chars_before not in time_words_with_suffix:
                        # 不是时间词的一部分，是真正的年份/月份数字，跳过
                        continue
            # 跳过指标名中包含的数字
            if segment in metric_name or metric_name in segment:
                continue
            if segment not in results:
                results.append(segment)

        return results

    def _is_time_word(self, text: str) -> bool:
        """判断是否是完全由时间词组成"""
        time_words = ["昨天", "今天", "明天", "上周", "本周", "下周", "上月", "本月", "下月",
                      "去年", "今年", "明年", "前天", "后天", "日前", "近日",
                      "一号", "二号", "三号", "四号", "五号", "六号", "七号", "八号", "九号", "十号",
                      "1号", "2号", "3号", "4号", "5号", "6号", "7号", "8号", "9号", "10号",
                      "11号", "12号", "13号", "14号", "15号", "16号", "17号", "18号", "19号", "20号",
                      "21号", "22号", "23号", "24号", "25号", "26号", "27号", "28号", "29号", "30号", "31号"]
        # 只检查片段是否完全等于时间词（不是包含关系）
        return text in time_words

    def entity_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        实体链接节点 - 增强版
        支持多轮上下文继承
        """
        entities = state.entities.copy()

        # ========== 获取对话上下文 ==========
        ctx = getattr(state, 'conversation_context', None)

        # ========== 继承上轮的指标信息 ==========
        if ctx and not entities.get("metric_code") and not entities.get("metric_name"):
            if ctx.current_metric_name or ctx.current_metric_code:
                entities.setdefault("metric_name", ctx.current_metric_name)
                entities.setdefault("metric_code", ctx.current_metric_code)
                logger.debug(f"[entity_node] 继承上轮指标: {ctx.current_metric_name}")

        # ========== 继承上轮的时间表达式 ==========
        if ctx and not entities.get("time_range") and ctx.current_time_expr:
            # 检查用户是否明确指定了新的时间
            last_message = state.messages[-1].content if state.messages else ""
            has_explicit_time = any(kw in last_message for kw in ["昨天", "今日", "本周", "本月", "去年"])
            # 特殊处理：环比/同比追问应该继承时间，保持和上轮一样的时间周期
            is_comparison_followup = any(kw in last_message for kw in ["环比呢", "同比呢", "环比", "同比"])
            if not has_explicit_time:
                entities.setdefault("time_range", ctx.current_time_expr)
                logger.debug(f"[entity_node] 继承上轮时间: {ctx.current_time_expr}")
                if is_comparison_followup:
                    logger.debug(f"[entity_node] 环比/同比追问，继承时间用于环比计算")

        # ========== 继承上轮的维度 ==========
        if ctx:
            for dim_key, dim_value in ctx.current_dimensions.items():
                if dim_key not in entities and dim_value:
                    entities[dim_key] = dim_value
                    logger.debug(f"[entity_node] 继承上轮维度: {dim_key}={dim_value}")

        last_message = state.messages[-1].content if state.messages else ""

        # 检查是否是回应上轮的 metric_enum 追问（用户选择指标）
        user_just_selected_metric = False  # 标记用户是否刚选择了指标
        logger.debug(f"[entity_node] 检查 metric_enum: clarification_type={getattr(state, 'clarification_type', None)}, matched_metrics存在={getattr(state, 'matched_metrics', None) is not None}")
        if getattr(state, 'clarification_type', None) == 'metric_enum' and getattr(state, 'matched_metrics', None) is not None:
            # 用户在选择指标
            logger.debug(f"[entity_node] matched_metrics内容: {state.matched_metrics[:2] if state.matched_metrics else None}")
            chosen_metric = self._parse_metric_choice(last_message, state.matched_metrics)
            logger.debug(f"[entity_node] _parse_metric_choice结果: {chosen_metric}")
            if chosen_metric:
                entities.update(chosen_metric)
                logger.debug(f"[entity_node] 用户选择了指标: {chosen_metric.get('metric_name')}")
                state.matched_metrics = None  # 清除选择状态
                state.needs_clarification = False  # 清除追问状态
                state.clarification_type = None  # 清除追问类型
                state.clarification_message = None  # 清除追问消息
                user_just_selected_metric = True  # 标记用户刚选择了指标

        # 检查是否是回应上轮的 dimension_value 追问（用户选择维度值）
        if getattr(state, 'clarification_type', None) == 'dimension_value' and hasattr(state, 'dimension_value_candidates'):
            # 用户在选择维度值
            candidates = state.dimension_value_candidates
            logger.debug(f"[entity_node] dimension_value_candidates: {candidates}")
            chosen_dim = self._parse_dimension_value_choice(last_message, candidates)
            logger.debug(f"[entity_node] _parse_dimension_value_choice结果: {chosen_dim}")
            if chosen_dim:
                state.selected_dimension_field = chosen_dim["dimension_field"]
                state.selected_dimension_value = chosen_dim["dimension_value"]
                entities[chosen_dim["dimension_field"]] = chosen_dim["dimension_value"]
                logger.info(f"[entity_node] 用户选择了维度值: {chosen_dim['dimension_field']}={chosen_dim['dimension_value']}")
                state.dimension_value_candidates = None  # 清除候选
                state.needs_clarification = False  # 清除追问状态
                state.clarification_type = None  # 清除追问类型
                state.clarification_message = None  # 清除追问消息

        # 链接业务术语到指标
        term_links = self.rule_engine.link_business_terms_enhanced(
            last_message,
            entities
        )

        # 如果实体链接返回空，检查是否是新的指标查询
        # 新指标查询的特征：包含指标相关的词（如"数"、"量"、"用户"等）
        # 如果是新的指标查询，即使 metric_id 已设置，也要清除（因为这是不同的指标）
        if not term_links:
            follow_up_only_indicators = ["定义", "口径", "规则", "怎么", "如何", "环比", "同比"]
            # 注意：环比/同比是意图词，不是指标名，不要加入 contains_metric_reference
            contains_metric_reference = any(word in last_message for word in ["数", "量", "额", "率", "次数", "人数", "销售额", "订单", "转化", "访客", "用户"])

            # 只有当查询只包含 follow-up 指示词，且不包含指标名时，才保留继承的指标
            is_pure_followup = any(ind in last_message for ind in follow_up_only_indicators) and not contains_metric_reference

            # 检查是否从上一轮继承了指标
            inherited_metric = entities.get("metric_name") or entities.get("metric_code")

            # 清除继承指标的条件：
            # 1. 用户说了明确的 follow-up 词（如"定义呢"、"口径呢"），保留继承
            # 2. 用户说了新的指标相关词，但规则没匹配到，清除继承
            # 3. 用户输入很短（小于4个字符）且不是时间词，清除继承（新指标可能没配置）
            message_len = len(last_message.strip())
            is_short_input = message_len < 4 and message_len > 0
            # 使用正则匹配动态时间词（支持"最近8天"、"近几月"、"前几年"等所有动态时间）
            is_time_word = bool(re.search(
                r'昨天|今天|明日|昨日|本周|本月|上周|上月|去年|今年|'  # 固定时间词
                r'近几?(?:天|周|月|年)|前几?(?:天|周|月|年)|'  # 近几/前几 + 天/周/月/年
                r'最近\d+(?:天|周|月|年)|过去\d+(?:天|周|月|年)|'  # 最近N天/周/月/年、过去N天/周/月/年
                r'\d+(?:天|周|月|年)(?:前|内)|'
                r'上?(?:一|这)?(?:周|月|年)',  # 本周、本月、上周、上月等
                last_message
            ))

            # 只有不是 follow-up 且有继承指标时，才考虑清除
            # 但如果用户刚选择了指标（user_just_selected_metric），不能清除刚设置的指标
            # 确认词（如"是的"、"好"等）也不应该清除继承的指标
            # 来自 Step 0 的意图确认也不清除（Step 0 已从 context 恢复了指标）
            confirmation_words = ["是的", "好", "可以", "对的", "没错", "确定", "行", "ok", "yeah", "yes"]
            is_confirmation = last_message.strip() in confirmation_words or last_message.strip().lower() in ["ok", "yes", "yeah", "y"]
            intent_confirmed_from_context = getattr(state, '_intent_confirmed_from_context', False)
            if not is_pure_followup and inherited_metric and not user_just_selected_metric and not is_confirmation and not intent_confirmed_from_context:
                if contains_metric_reference or (is_short_input and not is_time_word):
                    # 用户说了指标相关词但没匹配到，或者输入很短且不是时间词，清除继承
                    entities["metric_name"] = None
                    entities["metric_code"] = None
                    entities["unit"] = None
                    entities["starrocks_sql"] = None

            # 确认时清除 dimension，因为用户已确认具体指标，不需要多维度分解
            if is_confirmation:
                entities.pop("dimension", None)

            # 关键优化：当规则引擎匹配不到时，尝试用 LLM 识别短输入中的指标
            # 比如用户说"sku"，LLM 可以识别出可能是"缺货SKU数"
            # 但如果用户已经提供了时间词（如"最近7天"）且有继承的指标，不要让 LLM 猜测新指标
            should_extract_metric = is_short_input or (not term_links and not is_pure_followup)
            is_primary_time_input = is_time_word and inherited_metric
            llm_result = None  # Initialize for scope
            if should_extract_metric and not is_primary_time_input:
                llm_result = self.llm_engine.extract_metric_from_text(last_message)
                if llm_result and llm_result.get("confidence", 0) > 0.5:
                    # LLM 识别到了可能的指标
                    matched_metric = llm_result.get("metric_name", "")
                    # 用 LLM 识别的指标名再尝试匹配一次
                    term_links = self.rule_engine.link_business_terms_enhanced(
                        matched_metric,
                        entities
                    )
                    if term_links:
                        logger.debug(f"[entity_node] LLM 识别到指标: {matched_metric}, confidence: {llm_result.get('confidence')}")

        entities.update(term_links)

        # 识别"按X查看"模式，设置时间维度（用于 GROUP BY）
        dim_match = re.search(r"按([日月年天周])查看", last_message)
        if dim_match:
            time_dim_char = dim_match.group(1)
            # 映射到维度配置中的维度名
            dim_map = {"日": "日", "天": "日", "月": "月", "年": "年", "周": "周"}
            if time_dim_char in dim_map:
                entities["dimension"] = dim_map[time_dim_char]
                logger.debug(f"[entity_node] 识别时间维度: {entities['dimension']}")

        # 如果没有匹配到指标但有时间范围，也要提取
        if not term_links and not entities.get("time_range"):
            time_range = self._extract_time_range(last_message)
            if time_range:
                entities["time_range"] = time_range
                logger.debug(f"[entity_node] 提取到时间范围: {time_range}")

        # 提取完整时间信息（用于追问和SQL组装）
        time_info = self._extract_time_info(last_message)
        if time_info:
            entities["time_info"] = time_info
            logger.debug(f"[entity_node] 提取到完整时间信息: {time_info}")

        # 检查是否是业务术语查询（ASIN、SKU等）
        business_term_info = self.rule_engine.recognize_business_term(last_message)
        if business_term_info:
            # 设置业务术语标记，让后续节点知道这是业务术语查询
            entities["is_business_term"] = True
            entities["business_term_name"] = business_term_info.get("term")
            entities["business_term_description"] = business_term_info.get("description")
            entities["business_term_intent"] = business_term_info.get("intent")
            logger.debug(f"[entity_node] 识别到业务术语查询: {business_term_info.get('term')}")

        # 如果成功链接到指标，保存到 last_valid_metric（不轻易清除）
        if entities.get("metric_name") or entities.get("metric_code"):
            state.last_valid_metric = {
                "metric_name": entities.get("metric_name"),
                "metric_code": entities.get("metric_code"),
                "metric_id": entities.get("metric_id"),
                "unit": entities.get("unit"),
                "starrocks_sql": entities.get("starrocks_sql"),
            }

            # 从知识图谱查询关联指标，增强上下文
            metric_code = entities.get("metric_code")
            if metric_code:
                graph_query = _get_graph_query()
                if graph_query:
                    try:
                        # 查询上游、下游、相关指标
                        context = graph_query.get_metric_context(metric_code)
                        if context:
                            # 保存关联指标到 state.context
                            state.context = state.context or {}
                            state.context["metric_context"] = context
                            if os.getenv("DEBUG"):
                                logger.debug(f"[GraphQuery] Found context for {metric_code}: "
                                      f"upstream={len(context.get('upstream', []))}, "
                                      f"downstream={len(context.get('downstream', []))}, "
                                      f"correlated={len(context.get('correlated', []))}")
                    except Exception as e:
                        if os.getenv("DEBUG"):
                            logger.warning(f"[GraphQuery] Query failed: {e}")
                graph_query = None

        # 保存当前实体供下一轮使用
        state.previous_entities = entities.copy()

        # 记录思考步骤：实体识别
        metric_name = entities.get("metric_name") or entities.get("metric_code") or "未识别"
        time_range = entities.get("time_range") or "未识别"
        dimension = entities.get("dimension") or "未指定"

        content_parts = []
        if entities.get("metric_name"):
            content_parts.append(f"指标：{entities.get('metric_name')}")
        # 优先使用 time_info（完整时间信息），否则用 time_range
        time_info = entities.get("time_info")
        if time_info:
            content_parts.append(f"时间：{time_info.get('original', time_info.get('start', ''))}")
        elif entities.get("time_range"):
            content_parts.append(f"时间：{entities.get('time_range')}")
        if entities.get("dimension"):
            content_parts.append(f"维度：{entities.get('dimension')}")
        if entities.get("platform"):
            content_parts.append(f"平台：{entities.get('platform')}")
        if entities.get("region"):
            content_parts.append(f"地区：{entities.get('region')}")

        entity_content = " | ".join(content_parts) if content_parts else "未识别到具体实体"
        if 'llm_result' in dir() and llm_result and llm_result.get("metric_name"):
            entity_content += "（LLM辅助识别）"
        self._add_thinking_step(state, "实体识别", "completed", entity_content)

        # ========== 维度值识别 ==========
        # 从用户消息中提取可能的维度值
        dim_value_client = DimValueClient()
        unmatched_texts = self._extract_potential_dim_values(last_message, entities)
        logger.info(f"[entity_node] 维度值提取结果: unmatched_texts={unmatched_texts}, metric_name={entities.get('metric_name', '')}")

        for text in unmatched_texts:
            candidates = dim_value_client.search_dimension_values(text, limit=3)
            if candidates:
                # 优先使用精确匹配
                exact_matches = [c for c in candidates if c.get("match_type") == "exact"]
                if len(exact_matches) == 1:
                    # 唯一精确匹配，直接使用
                    matched = exact_matches[0]
                    entities[matched["dimension_field"]] = matched["dimension_value"]
                    logger.info(f"[entity_node] 识别维度值: {text} -> {matched['dimension_field']}={matched['dimension_value']} (精确匹配)")
                elif len(candidates) == 1:
                    # 唯一匹配（可能是前缀或模糊），直接使用
                    matched = candidates[0]
                    entities[matched["dimension_field"]] = matched["dimension_value"]
                    logger.info(f"[entity_node] 识别维度值: {text} -> {matched['dimension_field']}={matched['dimension_value']}")
                else:
                    # 多个候选且无精确匹配，需要用户确认
                    state.needs_clarification = True
                    state.clarification_type = "dimension_value"
                    state.clarification_message = f"您说的是哪个维度：{[c['dimension_value'] for c in candidates]}？"
                    state.dimension_value_candidates = candidates  # 保存候选列表供后续解析
                    state.dimension_value_matched_text = text  # 保存匹配的原始文本（如"1011"）
                    return {"entities": entities}

        return {"entities": entities}

    def check_metric_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        指标验证节点 - 工具调用
        检查指标是否存在，如果存在则返回完整指标信息
        """
        metric_name = state.entities.get("metric_name")
        metric_code = state.entities.get("metric_code")

        # 如果已有完整的 starrocks_sql，说明已经验证过
        if state.entities.get("starrocks_sql"):
            return {"metric_valid": True, "metric_info": state.entities}

        # 尝试从数据库查询指标信息
        try:
            metadata_result = self.sql_generator.query_metadata(
                metric_name=metric_name,
                metric_code=metric_code
            )

            if metadata_result.get("type") == "error":
                return {
                    "metric_valid": False,
                    "error": metadata_result.get("error", "指标不存在"),
                }

            if metadata_result.get("type") == "list":
                # 多个指标匹配
                return {
                    "metric_valid": False,
                    "multiple_matches": True,
                    "metrics": metadata_result.get("metrics", []),
                }

            # 保存指标信息
            if metadata_result.get("starrocks_sql"):
                state.entities["starrocks_sql"] = metadata_result["starrocks_sql"]
            if metadata_result.get("metric_code"):
                state.entities["metric_code"] = metadata_result["metric_code"]
            if metadata_result.get("id"):
                state.entities["metric_id"] = metadata_result["id"]
            if metadata_result.get("unit"):
                state.entities["unit"] = metadata_result["unit"]

            # 更新 last_valid_metric
            state.last_valid_metric = {
                "metric_name": metadata_result.get("metric_name", metric_name),
                "metric_code": metadata_result.get("metric_code", metric_code),
                "metric_id": metadata_result.get("id"),
                "unit": metadata_result.get("unit"),
                "starrocks_sql": metadata_result.get("starrocks_sql"),
            }

            return {
                "metric_valid": True,
                "metric_info": metadata_result,
            }

        except Exception as e:
            return {
                "metric_valid": False,
                "error": f"指标验证失败: {str(e)}",
            }

    def clarification_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        追问决策节点 - LLM 驱动的智能澄清
        1. 分析当前状态，确定缺失字段
        2. 调用 LLM 决定是否追问
        3. 处理追问次数限制和默认值兜底
        """
        metric_name = state.entities.get("metric_name")
        time_range = state.entities.get("time_range")
        time_info = state.entities.get("time_info")  # 完整时间信息

        # 确定缺失字段
        missing_fields = []
        if not metric_name:
            missing_fields.append("metric_name")
        if not time_range:
            missing_fields.append("time_range")

        # 检查是否需要追问年份（绝对月份如"7月"没有明确年份）
        needs_year_clarification = False
        if time_info:
            from ai.engine.time_parser import TimeParser
            parser = TimeParser()
            needs_year_clarification = parser.needs_year_clarification(time_info)
            if needs_year_clarification:
                missing_fields.append("year")

        # 如果没有缺失，不需要追问
        if not missing_fields:
            return {
                "needs_clarification": False,
                "skip_clarification_reason": "信息完整",
            }

        # 按字段检查是否已问过（避免重复追问同一个字段）
        newly_asked_fields = [f for f in missing_fields if f not in state.asked_fields]

        # 如果所有缺失字段都已问过，使用默认值兜底
        if not newly_asked_fields:
            return self._apply_default_values(state, missing_fields)

        # 调用 LLM 决策
        decision = self.llm_engine.decide_clarification(state, newly_asked_fields)

        if not decision.needs_clarification:
            return {
                "needs_clarification": False,
                "skip_clarification_reason": decision.reason,
            }

        # 检查是否超过最大追问次数
        if state.clarification_count >= state.max_clarification_turns:
            return self._apply_default_values(state, missing_fields)

        # 更新状态
        state.clarification_count += 1
        state.asked_fields.extend(decision.missing_fields)
        state.pending_clarification = {
            "missing_fields": decision.missing_fields,
            "question": decision.question,
            "clarification_type": decision.clarification_type,
            "suggested_defaults": decision.suggested_defaults,
        }

        return {
            "needs_clarification": True,
            "clarification_message": decision.question,
            "clarification_type": decision.clarification_type,
            "clarification_reason": decision.reason,
            "suggested_defaults": decision.suggested_defaults,
            "asked_fields": state.asked_fields,
        }

    def _apply_default_values(self, state: ConversationState, missing_fields: list, suggested_defaults: dict = None) -> Dict[str, Any]:
        """应用默认值兜底"""
        default_values = state.default_values.copy()
        # 优先使用 LLM 建议的默认值
        if suggested_defaults:
            default_values.update(suggested_defaults)

        applied_defaults = {}

        for field in missing_fields:
            if field in default_values:
                state.entities[field] = default_values[field]
                applied_defaults[field] = default_values[field]

        if applied_defaults:
            logger.debug(f"[clarification] 应用默认值: {applied_defaults}")

        return {
            "needs_clarification": False,
            "applied_defaults": applied_defaults,
            "skip_clarification_reason": f"使用默认值: {applied_defaults}",
        }

    def sql_gen_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        SQL 生成节点 - 核心流程
        1. greeting/thanks/bye -> 跳过 SQL 生成
        2. query_metadata -> 查 PostgreSQL 元数据
        3. query_value/trend/comparison -> 查 StarRocks 数值
        """
        logger.debug(f"[sql_gen] intent={state.current_intent}, entities={state.entities}")

        # 非查询意图：跳过 SQL 生成
        non_query_intents = ["greeting", "thanks", "bye", "unknown"]
        if state.current_intent in non_query_intents:
            return {"skip_sql_generation": True, "generated_sql": None}

        # 元数据查询意图：查业务口径、技术口径、指标定义等
        metadata_intents = ["query_metadata", "query_definition", "query_rule",
                          "query_business_rule", "query_technical_rule"]
        if state.current_intent in metadata_intents:
            state.intent_is_metadata_query = True
            # 如果没有 metric_name/code，尝试从 previous_entities 获取
            if not state.entities.get("metric_name") and not state.entities.get("metric_code"):
                prev = getattr(state, 'previous_entities', {})
                if prev and (prev.get("metric_name") or prev.get("metric_code")):
                    state.entities["metric_name"] = prev.get("metric_name")
                    state.entities["metric_code"] = prev.get("metric_code")
                    logger.debug(f"[sql_gen] 继承上轮实体: {state.entities}")
                else:
                    # 尝试从 last_valid_metric 获取（用于follow-up但中间有失败的查询）
                    last_metric = getattr(state, 'last_valid_metric', {})
                    if last_metric and (last_metric.get("metric_name") or last_metric.get("metric_code")):
                        state.entities["metric_name"] = last_metric.get("metric_name")
                        state.entities["metric_code"] = last_metric.get("metric_code")
                        state.entities["metric_id"] = last_metric.get("metric_id")
                        state.entities["unit"] = last_metric.get("unit")
                        state.entities["starrocks_sql"] = last_metric.get("starrocks_sql")
                        logger.debug(f"[sql_gen] 继承last_valid_metric: {state.entities}")

            # 记录思考步骤：SQL 生成
            metric_name = state.entities.get("metric_name")
            metric_code = state.entities.get("metric_code")
            self._add_thinking_step(state, "SQL 生成", "completed",
                f"元数据查询：{metric_name or metric_code or '未知指标'}")
            return {"generated_sql": "METADATA_QUERY", "skip_execution": False}

        # query_value：查 StarRocks 数值
        if state.current_intent == "query_value":
            state.intent_is_metadata_query = False
            return self._build_value_sql(state)

        # 其他意图（趋势、对比等）也查数值
        return self._build_value_sql(state)

    def _build_value_sql(self, state: ConversationState) -> Dict[str, Any]:
        """构建数值查询 SQL - 支持维度参数调整"""
        metric_code = state.entities.get("metric_code")
        metric_id = state.entities.get("metric_id")
        metric_name = state.entities.get("metric_name")
        starrocks_sql = state.entities.get("starrocks_sql")
        time_range = state.entities.get("time_range")
        time_info = state.entities.get("time_info")  # 来自 TimeParser 的完整时间信息

        logger.info(f"[_build_value_sql] 开始构建SQL: metric={metric_name}({metric_code}), starrocks_sql={repr(starrocks_sql)[:100] if starrocks_sql else 'None'}")
        logger.info(f"[_build_value_sql] time_info: {time_info}, time_range: {time_range}")

        # 提取维度参数
        dimensions = self._extract_sql_dimensions(state.entities)
        logger.debug(f"[_build_value_sql] 提取的维度参数: {dimensions}")

        # 校验维度是否在 dimensions 表配置中
        dims_valid, error_msg = self._validate_extracted_dimensions(state)
        if not dims_valid:
            state.needs_clarification = True
            state.clarification_type = "invalid_dimension"
            state.clarification_message = error_msg
            return {
                "needs_clarification": True,
                "clarification_message": error_msg,
                "clarification_type": "invalid_dimension",
            }

        # Step 1: 优先使用预置 SQL
        if starrocks_sql:
            # 如果有预置 SQL，应用维度参数调整
            adjusted_sql = self._apply_dimensions_to_sql(starrocks_sql, dimensions, state.entities, time_info)
            logger.debug(f"[_build_value_sql] 维度调整后的SQL: {adjusted_sql}")

            # 如果有预置 SQL，先尝试补充缺失参数
            if not time_range and not time_info:
                # 调用 LLM 追问决策
                clarification_result = self.clarification_node(state)
                if clarification_result.get("needs_clarification"):
                    # 检查是否有默认值应用
                    applied_defaults = clarification_result.get("applied_defaults", {})
                    if applied_defaults:
                        # 应用默认值，继续执行
                        return {
                            "generated_sql": adjusted_sql,
                            "sql_params": {"metric_id": metric_id, "metric_code": metric_code},
                            "applied_defaults": applied_defaults,
                        }
                    # 没有默认值，需要追问
                    return {
                        "needs_clarification": True,
                        "clarification_message": clarification_result.get("clarification_message"),
                        "clarification_type": clarification_result.get("clarification_type"),
                    }
                # 无需追问，继续执行

            # 记录思考步骤：SQL 生成
            self._add_thinking_step(state, "SQL 生成", "completed",
                f"基于预置 SQL 模板，指标：{metric_name or '未知指标'}")

            return {
                "generated_sql": adjusted_sql,
                "sql_params": {"metric_id": metric_id, "metric_code": metric_code},
            }

        # Step 2: 规则引擎兜底
        # 如果用户输入是简单确认词（如"是的"），且 starrocks_sql 为空，跳过规则引擎直接用 fallback
        last_message_for_step2 = state.messages[-1].content if state.messages else ""
        confirmation_words_for_step2 = ["是的", "好", "可以", "对的", "没错", "确定", "行", "ok", "yeah", "yes"]
        is_simple_confirmation = (
            last_message_for_step2.strip() in confirmation_words_for_step2 or
            last_message_for_step2.strip().lower() in ["ok", "yes", "yeah", "y"]
        )
        # 如果是简单确认且 metric 有空 starrocks_sql，跳过规则引擎
        skip_rule_engine = is_simple_confirmation and not starrocks_sql

        sql_result = None
        if not skip_rule_engine:
            sql_result = self.rule_engine.try_match_sql(
                intent=state.current_intent,
                entities=state.entities
            )

        if sql_result and sql_result.is_safe:
            # 应用维度参数
            adjusted_sql = self._apply_dimensions_to_sql(sql_result.sql, dimensions, state.entities, time_info)
            # 记录思考步骤：SQL 生成
            self._add_thinking_step(state, "SQL 生成", "completed",
                f"基于 {metric_name or '未知指标'} 生成 SQL 查询")
            return {
                "generated_sql": sql_result.sql,
                "sql_params": sql_result.params,
            }

        # Step 3: 识别到了指标但没有 starrocks_sql
        if metric_code or metric_name:
            # 检查用户输入是否模糊（很短或者包含"费"、"数"等泛化词）
            last_message = state.messages[-1].content if state.messages else ""
            is_vague_input = len(last_message.strip()) <= 2  # 短输入如"费"、"数"

            # 如果 starrocks_sql 为空，检查是否包含时间词（可能是时间限定而不是新查询）
            contains_time_word = bool(re.search(
                r"昨天|今日|明日|昨日|本周|本月|上周|上月|去年|今年|明年|上个月|近几|最近|过去|前几",
                last_message
            ))

            # 如果用户输入包含时间词且已经有指标，说明是时间限定，不应该重新搜索指标
            if contains_time_word and (metric_code or metric_name):
                # 这是时间限定查询，构建一个基于 metric_code 的查询 SQL
                # 尝试从 metric_client 获取 starrocks_sql
                logger.debug(f"[sql_gen] contains_time_word=True, metric_code={metric_code}, metric_name={metric_name}, metric_id={metric_id}")
                actual_starrocks_sql = None
                if metric_id:
                    try:
                        metric_info = self.metric_client.get_metric(metric_id)
                        logger.debug(f"[sql_gen] get_metric({metric_id}) returned: starrocks_sql={repr(metric_info.get('starrocks_sql', 'NOT_FOUND')[:100] if metric_info.get('starrocks_sql') else 'EMPTY')}")
                        if metric_info and metric_info.get("starrocks_sql"):
                            actual_starrocks_sql = metric_info.get("starrocks_sql")
                    except Exception as e:
                        logger.debug(f"[sql_gen] 获取指标详情失败: {e}")

                if actual_starrocks_sql:
                    # 使用指标的实际 SQL 模板
                    adjusted_sql = self._apply_dimensions_to_sql(actual_starrocks_sql, dimensions, state.entities, time_info)
                    return {
                        "generated_sql": adjusted_sql,
                        "sql_params": {"metric_id": metric_id, "metric_code": metric_code},
                        "intent_is_metadata_query": False,
                    }
                else:
                    # starrocks_sql 为空，尝试 fallback 查询
                    if metric_id:
                        # 尝试使用通用 SQL 查询 metric_data 表
                        fallback_sql = f"SELECT date, value FROM metric_data WHERE metric_id = {metric_id} ORDER BY date DESC LIMIT 10"
                        # 清除追问状态，因为我们要执行 fallback 查询
                        state.needs_clarification = False
                        state.clarification_type = None
                        state.clarification_message = None
                        state.matched_metrics = None
                        return {
                            "generated_sql": fallback_sql,
                            "sql_params": {"metric_id": metric_id, "metric_code": metric_code},
                            "intent_is_metadata_query": False,
                        }
                    # 没有 metric_id，触发指标追问
                    logger.debug(f"[sql_gen] metric_code={metric_code}, metric_id={metric_id}, metric_name={metric_name}")
                    # 如果有 metric_code，优先用 metric_code 查询指标详情
                    if metric_code and metric_id:
                        try:
                            metric_info = self.metric_client.get_metric(metric_id)
                            logger.debug(f"[sql_gen] get_metric result: {metric_info.get('name') if metric_info else 'None'}")
                            if metric_info:
                                # 用 metric_code 找到了指标，但 starrocks_sql 为空，说明这个指标没有查询SQL
                                # 搜索相关指标给用户选择
                                matched_metrics = self.metric_client.search_metrics(metric_name or last_message, limit=8)
                                logger.debug(f"[sql_gen] matched_metrics count={len(matched_metrics)}")
                                if matched_metrics and len(matched_metrics) > 0:
                                    metric_list = "\n".join([
                                        f"{i+1}. **{m.get('name')}** ({m.get('metric_code', 'N/A')})"
                                        for i, m in enumerate(matched_metrics[:8])
                                    ])
                                    state.needs_clarification = True
                                    state.clarification_message = f"您是否想查询以下相关指标？\n\n{metric_list}\n\n请选择或描述更具体一些"
                                    state.clarification_type = "metric_enum"
                                    return {
                                        "needs_clarification": True,
                                        "clarification_message": state.clarification_message,
                                        "clarification_type": "metric_enum",
                                        "matched_metrics": matched_metrics,
                                    }
                        except Exception as e:
                            logger.debug(f"[sql_gen] get_metric失败: {e}")

                    # 降级：用 metric_name 或用户输入搜索
                    search_query = metric_name if metric_name else last_message
                    matched_metrics = self.metric_client.search_metrics(search_query, limit=8)
                    logger.debug(f"[sql_gen] fallback search_query={search_query}, matched_metrics count={len(matched_metrics)}")
                    if matched_metrics and len(matched_metrics) > 0:
                        metric_list = "\n".join([
                            f"{i+1}. **{m.get('name')}** ({m.get('metric_code', 'N/A')})"
                            for i, m in enumerate(matched_metrics[:8])
                        ])
                        state.needs_clarification = True
                        state.clarification_message = f"您是否想查询以下相关指标？\n\n{metric_list}\n\n请选择或描述更具体一些"
                        state.clarification_type = "metric_enum"
                        return {
                            "needs_clarification": True,
                            "clarification_message": state.clarification_message,
                            "clarification_type": "metric_enum",
                            "matched_metrics": matched_metrics,
                        }
                    else:
                        # 真的找不到，通用回复
                        state.needs_clarification = True
                        state.clarification_message = f"抱歉，系统中没有找到与「{metric_name}」相关的指标，请尝试更具体的描述"
                        state.clarification_type = "scope_too_broad"
                        return {
                            "error": "无法生成 SQL",
                            "needs_clarification": True,
                            "clarification_message": state.clarification_message,
                            "clarification_type": "scope_too_broad",
                        }

            # 如果用户输入模糊，即使匹配到指标也要列出相关指标让用户确认
            # 但如果 skip_rule_engine=True（简单确认词+空starrocks_sql），应该直接用 fallback SQL，不应该追问
            if (is_vague_input or not starrocks_sql) and not (skip_rule_engine and metric_id):
                # 先搜索相关指标列表
                # 使用 metric_name（如果有的话）而不是完整的用户输入来搜索
                search_query = metric_name if metric_name else last_message
                matched_metrics = self.metric_client.search_metrics(search_query, limit=8)
                if matched_metrics and len(matched_metrics) > 0:
                    # 列出相关指标让用户选择
                    metric_list = "\n".join([
                        f"{i+1}. **{m.get('name')}** ({m.get('metric_code', 'N/A')})"
                        for i, m in enumerate(matched_metrics[:8])
                    ])
                    state.needs_clarification = True
                    state.clarification_message = f"您是否想查询以下相关指标？\n\n{metric_list}\n\n请选择或描述更具体一些"
                    state.clarification_type = "metric_enum"
                    return {
                        "needs_clarification": True,
                        "clarification_message": state.clarification_message,
                        "clarification_type": "metric_enum",
                        "matched_metrics": matched_metrics,
                    }

            # 如果不是模糊输入且有完整参数，调用 LLM 追问决策
            # 但如果 skip_rule_engine=True（简单确认词+空starrocks_sql），应该直接用 fallback SQL，不应该追问
            if skip_rule_engine and metric_id:
                # 直接返回 fallback SQL，不调用 LLM 追问
                fallback_sql = f"SELECT date, value FROM metric_data WHERE metric_id = {metric_id} ORDER BY date DESC LIMIT 10"
                state.needs_clarification = False
                state.clarification_type = None
                state.clarification_message = None
                state.matched_metrics = None
                return {
                    "generated_sql": fallback_sql,
                    "sql_params": {"metric_id": metric_id, "metric_code": metric_code},
                    "intent_is_metadata_query": False,
                }
            clarification_result = self.clarification_node(state)
            if clarification_result.get("needs_clarification"):
                # 检查是否有默认值应用
                applied_defaults = clarification_result.get("applied_defaults", {})
                if applied_defaults:
                    # 应用默认值，继续执行
                    state.intent_is_metadata_query = True
                    return {
                        "generated_sql": "METADATA_QUERY",
                        "skip_execution": False,
                        "applied_defaults": applied_defaults,
                    }
                # 没有默认值，需要追问
                return {
                    "needs_clarification": True,
                    "clarification_message": clarification_result.get("clarification_message"),
                    "clarification_type": clarification_result.get("clarification_type"),
                }

            # 有完整参数但没有 starrocks_sql，尝试查询元数据获取更多信息
            state.intent_is_metadata_query = True
            return {
                "generated_sql": "METADATA_QUERY",
                "skip_execution": False,
            }

        # Step 4: 无法生成 SQL 且没有指标信息 - 尝试搜索指标库
        last_message = state.messages[-1].content if state.messages else ""
        matched_metrics = self.metric_client.search_metrics(last_message, limit=5)

        if matched_metrics:
            # 找到匹配的指标，生成枚举式追问
            metric_list = "\n".join([
                f"{i+1}. **{m.get('name')}** (`{m.get('metric_code')}`)"
                for i, m in enumerate(matched_metrics)
            ])
            state.needs_clarification = True
            state.clarification_message = f"您是否想查询以下相关指标？\n\n{metric_list}\n\n请选择或描述更具体一些"
            state.clarification_type = "metric_enum"
            return {
                "error": "无法生成 SQL",
                "needs_clarification": True,
                "clarification_message": state.clarification_message,
                "clarification_type": "metric_enum",
                "matched_metrics": matched_metrics,
            }
        else:
            # 真的找不到，通用回复
            state.needs_clarification = True
            state.clarification_message = "抱歉，无法理解您的问题，请尝试描述具体一些"
            state.clarification_type = "scope_too_broad"
            return {
                "error": "无法生成 SQL",
                "needs_clarification": True,
                "clarification_message": state.clarification_message,
                "clarification_type": "scope_too_broad",
            }

    def _parse_metric_choice(self, user_input: str, matched_metrics: list) -> Optional[Dict[str, Any]]:
        """
        解析用户对 metric_enum 追问的选择
        用户可以说 "1"、"2" 等数字，也可以说指标名称
        """
        import re
        user_input = user_input.strip()

        # 尝试数字选择（如 "1", "2"）
        num_match = re.match(r'^(\d+)$', user_input)
        if num_match:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(matched_metrics):
                m = matched_metrics[idx]
                return {
                    "metric_name": m.get("name"),
                    "metric_code": m.get("metric_code"),
                    "metric_id": m.get("id"),
                    "starrocks_sql": m.get("starrocks_sql"),
                    "unit": m.get("unit"),
                }

        # 尝试指标名称匹配
        user_lower = user_input.lower()
        for m in matched_metrics:
            name_lower = (m.get("name") or "").lower()
            name_en_lower = (m.get("name_en") or "").lower()
            if name_lower == user_lower or name_en_lower == user_lower or user_lower in name_lower:
                return {
                    "metric_name": m.get("name"),
                    "metric_code": m.get("metric_code"),
                    "metric_id": m.get("id"),
                    "starrocks_sql": m.get("starrocks_sql"),
                    "unit": m.get("unit"),
                }

        return None

    def _parse_dimension_value_choice(self, user_input: str, candidates: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        解析用户对 dimension_value 追问的选择
        用户可以说数字（如"1"、"2"）或直接说维度值名称
        """
        import re
        user_input = user_input.strip()

        # 尝试数字选择（如 "1", "2"）
        num_match = re.match(r'^(\d+)$', user_input)
        if num_match:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx]

        # 尝试维度值名称匹配
        user_lower = user_input.lower()
        for c in candidates:
            dim_value = (c.get("dimension_value") or "").lower()
            if dim_value == user_lower or user_lower in dim_value:
                return c

        return None

    # 维度配置缓存（避免每次查询都调 API）
    _table_dimensions_cache: Dict[str, Dict[str, Dict]] = {}

    def _get_table_dimensions_cached(self, table_name: str) -> Dict[str, Dict]:
        """获取表的维度配置，带缓存"""
        import json
        if table_name in self._table_dimensions_cache:
            return self._table_dimensions_cache[table_name]
        try:
            configs = self.metric_client.get_dimension_configs(table_name)
            result = {}
            for cfg in configs:
                if cfg.get("status") == 1:
                    result[cfg["dimension_name"]] = {
                        "column_name": cfg["column_name"],
                        "values": json.loads(cfg["dimension_values"]) if cfg.get("dimension_values") else []
                    }
            self._table_dimensions_cache[table_name] = result
        except Exception as e:
            logger.warning(f"获取维度配置失败: {e}")
            self._table_dimensions_cache[table_name] = {}
        return self._table_dimensions_cache[table_name]

    def _extract_table_name(self, sql: str) -> str:
        """从 SQL 中提取表名（FROM 后第一个表名）"""
        match = re.search(r'FROM\s+([^\s,;]+)', sql, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_sql_dimensions(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 entities 中提取可用于 SQL 的维度参数
        返回: {"platform": "amazon", "region": "east_china", ...}
        """
        dimensions = {}

        # 平台维度
        if entities.get("platform"):
            dimensions["platform"] = entities.get("platform")

        # 地区维度
        if entities.get("region"):
            dimensions["region"] = entities.get("region")

        # 部门维度
        if entities.get("department"):
            dimensions["department"] = entities.get("department")

        # 站点维度
        if entities.get("site"):
            dimensions["site"] = entities.get("site")

        # 品类维度
        if entities.get("category"):
            dimensions["category"] = entities.get("category")

        # 设备维度
        if entities.get("device"):
            dimensions["device"] = entities.get("device")

        # 品类维度 (GROUP_1, GROUP_2, GROUP_3)
        if entities.get("GROUP_1"):
            dimensions["GROUP_1"] = entities.get("GROUP_1")
        if entities.get("GROUP_2"):
            dimensions["GROUP_2"] = entities.get("GROUP_2")
        if entities.get("GROUP_3"):
            dimensions["GROUP_3"] = entities.get("GROUP_3")

        # SKU, ASIN 等维度
        if entities.get("SKU"):
            dimensions["SKU"] = entities.get("SKU")
        if entities.get("ASIN"):
            dimensions["ASIN"] = entities.get("ASIN")

        # 时间维度（日、月、年）- 用于 GROUP BY
        for dim_key in ["日", "月", "年", "天", "周"]:
            if entities.get(dim_key):
                dimensions[dim_key] = entities.get(dim_key)

        return dimensions

    def _validate_extracted_dimensions(self, state: ConversationState) -> tuple:
        """
        校验提取的维度是否在 dimensions 表配置中
        失败时返回错误消息，触发用户追问
        返回: (is_valid, error_message)
        """
        dimensions = self._extract_sql_dimensions(state.entities)
        if not dimensions:
            return True, None

        invalid_dims = []
        # 品类维度（GROUP_1/2/3, SKU, ASIN）来自 StarRocks dim_value_mapping，不在此验证
        skip_validation_keys = ["GROUP_1", "GROUP_2", "GROUP_3", "SKU", "ASIN", "日", "月", "年", "天", "周"]

        for dim_key, dim_value in dimensions.items():
            # 跳过非维度参数（如时间维度和品类维度）
            if dim_key in skip_validation_keys:
                continue
            if not self._is_dimension_registered(dim_key, dim_value):
                invalid_dims.append(f"{dim_key}={dim_value}")

        if invalid_dims:
            return False, f"抱歉，暂时没有配置这些维度：{', '.join(invalid_dims)}"
        return True, None

    def _is_dimension_registered(self, dim_type: str, dim_value: str) -> bool:
        """检查维度值是否在 dimensions 表配置中注册"""
        dim_map = self.rule_engine._get_dimension_mapping(dim_type)
        return dim_value in dim_map.values() or dim_value in dim_map.keys()

    def _apply_dimensions_to_sql(self, sql: str, dimensions: Dict[str, Any], entities: Dict[str, Any], time_info: Dict = None) -> str:
        """
        将维度参数应用到 SQL 模板中
        支持:
          - {dimension} 动态 GROUP BY (如 department)
          - {start_date}, {end_date} 时间范围替换
          - {platform} 等维度占位符替换
          - 无 dimension 时默认聚合 (去掉 GROUP BY)
        """
        if not sql:
            return sql

        adjusted_sql = sql

        logger.info(f"[_apply_dimensions_to_sql] time_info={time_info}, SQL原始={repr(sql)[:150]}")

        # 从 SQL 提取表名
        table_name = self._extract_table_name(sql)

        # === 1. 处理时间范围（占位符替换 + 自动注入）===
        if time_info:
            start_date = time_info.get("start")
            end_date = time_info.get("end")
            logger.info(f"[_apply_dimensions_to_sql] start_date={start_date}, end_date={end_date}")
            # 先替换占位符
            if start_date:
                adjusted_sql = adjusted_sql.replace("{start_date}", f"'{start_date}'")
            if end_date:
                adjusted_sql = adjusted_sql.replace("{end_date}", f"'{end_date}'")
            # 如果没有占位符，自动追加到 WHERE
            if table_name and ("{start_date}" not in adjusted_sql and "{end_date}" not in adjusted_sql):
                if start_date:
                    # 从维度配置获取时间列名（使用大写列名：FDATE, MONTHS）
                    dim_configs = self._get_table_dimensions_cached(table_name)
                    time_type = time_info.get("type", "date_range")

                    # 根据时间类型选择正确的列和条件（只加一个，不三个都加）
                    if time_type in ("date_range", "relative"):
                        # 日期范围用 FDATE 列
                        col = dim_configs.get("日", {}).get("column_name", "FDATE")
                        time_cond = f"{col} >= '{start_date}' AND {col} <= '{end_date}'"
                    elif time_type in ("absolute_month", "quarter"):
                        # 月份/季度用 MONTHS 列
                        col = dim_configs.get("月", {}).get("column_name", "MONTHS")
                        time_cond = f"{col} = '{start_date[:7]}'"
                    else:
                        # 默认用 FDATE
                        col = dim_configs.get("日", {}).get("column_name", "FDATE")
                        time_cond = f"{col} >= '{start_date}' AND {col} <= '{end_date}'"

                    if "WHERE" in adjusted_sql.upper():
                        adjusted_sql += f" AND {time_cond}"
                    else:
                        adjusted_sql += f" WHERE {time_cond}"

        # === 1.5 处理 SKU 占位符 ===
        # 如果没有指定 SKU，移除 SKU 相关的过滤条件
        sku_value = entities.get("sku")
        if not sku_value:
            # 移除 sku = '${SKU}' 或 sku = '{SKU}' 等条件
            adjusted_sql = re.sub(r'\s*AND\s+sku\s*=\s*[\'"]?\{?SKU\}?[\'"]?', '', adjusted_sql, flags=re.IGNORECASE)
            adjusted_sql = re.sub(r'\s*AND\s+sku\s*=\s*\$\{SKU\}', '', adjusted_sql, flags=re.IGNORECASE)
            adjusted_sql = adjusted_sql.rstrip()

        # === 2. 处理动态维度 (GROUP BY) ===
        dimension = entities.get("dimension")  # 如 "department"
        # 时间维度（日、月、年）直接注入 GROUP BY
        time_dimension_keys = ["日", "月", "年", "day", "month", "year"]
        if dimension in time_dimension_keys:
            # 统一为中文键
            dim_key = "日" if dimension in ["日", "day"] else "月" if dimension in ["月", "month"] else "年" if dimension in ["年", "year"] else dimension
            # 从配置获取实际的列名（大写：FDATE, MONTHS）
            if table_name:
                dim_configs = self._get_table_dimensions_cached(table_name)
                col = dim_configs.get(dim_key, {}).get("column_name", dim_key.upper())
            else:
                col = dim_key.upper()
            # 注入 GROUP BY（避免重复）
            if "GROUP BY" not in adjusted_sql.upper():
                adjusted_sql += f" GROUP BY {col}"
            return adjusted_sql

        if dimension:
            # 有维度，保留 GROUP BY，从配置查列名
            if table_name:
                dim_configs = self._get_table_dimensions_cached(table_name)
                # 优先精确匹配
                matched_dim = None
                if dimension in dim_configs:
                    matched_dim = dimension
                else:
                    # 模糊匹配：用户说"品类"应该匹配"三级品类"
                    for dim_name in dim_configs:
                        # 检查任意一方是否包含另一方
                        if dimension in dim_name or dim_name in dimension:
                            matched_dim = dim_name
                            break
                    # 再次尝试：如果 dim_name 是 dimension 的子串（如"三级品类"包含"品类"）
                    if not matched_dim:
                        for dim_name in dim_configs:
                            if dim_name in dimension:
                                matched_dim = dim_name
                                break
                if matched_dim:
                    column = dim_configs[matched_dim].get("column_name", matched_dim)
                else:
                    column = dimension
            else:
                column = dimension
            adjusted_sql = adjusted_sql.replace("{dimension}", column)
            # 如果有维度但 SQL 中没有 GROUP BY 占位符，手动添加 GROUP BY
            if dimension and "GROUP BY" not in adjusted_sql.upper():
                adjusted_sql = adjusted_sql.rstrip() + f" GROUP BY {column}"
        else:
            # 无维度，去掉 GROUP BY 相关
            adjusted_sql = adjusted_sql.replace("{dimension}", "*")
            adjusted_sql = re.sub(r'\s*GROUP\s+BY\s+\{[^}]*\}', '', adjusted_sql, flags=re.IGNORECASE)
            adjusted_sql = re.sub(r'\s*GROUP\s+BY\s+\*', '', adjusted_sql, flags=re.IGNORECASE)
            adjusted_sql = re.sub(r'\s*HAVING\s+\{[^}]*\}\s*IS\s+NOT\s+NULL', '', adjusted_sql, flags=re.IGNORECASE)
            adjusted_sql = re.sub(r'\s*HAVING\s+\*\s*IS\s+NOT\s+NULL', '', adjusted_sql, flags=re.IGNORECASE)

        # === 3. 处理其他维度参数（使用配置而非硬编码）===
        if table_name:
            dim_configs = self._get_table_dimensions_cached(table_name)
        else:
            dim_configs = {}

        for dim_key, dim_value in dimensions.items():
            if not dim_value or dim_key == "dimension":
                continue

            # 从配置获取列名，没有则用 dim_key 本身
            if dim_key in dim_configs:
                column = dim_configs[dim_key].get("column_name", dim_key)
            else:
                column = dim_key

            # 替换 SQL 中的占位符
            for pattern in [f"{{{dim_key}}}", f"{{{{{dim_key}}}}}", f"{{{dim_key}_name}}"]:
                if pattern in adjusted_sql:
                    if dim_value.startswith("'") and dim_value.endswith("'"):
                        adjusted_sql = adjusted_sql.replace(pattern, dim_value)
                    else:
                        adjusted_sql = adjusted_sql.replace(pattern, f"'{dim_value}'")

            # 如果 SQL 中没有占位符，追加到 WHERE 条件
            if f"{{{dim_key}}}" not in adjusted_sql and f"{{{{{dim_key}}}}}" not in adjusted_sql:
                if "WHERE" in adjusted_sql.upper():
                    adjusted_sql += f" AND {column} = '{dim_value}'"
                else:
                    adjusted_sql += f" WHERE {column} = '{dim_value}'"

        # === 4. 清理未替换的占位符 ===
        adjusted_sql = re.sub(r'\{[^}]+\}', '', adjusted_sql)

        # === 5. 处理 top N 排名 ===
        top_n = entities.get("top_n")
        if top_n:
            # 获取指标列名（用于 ORDER BY）
            metric_col = "SESSIONS_TOTAL"  # 默认指标列
            if "sum(" in adjusted_sql.lower() or "avg(" in adjusted_sql.lower():
                # 从 SELECT 子句中提取指标列
                col_match = re.search(r'(sum|avg)\s*\(\s*(\w+)\s*\)', adjusted_sql, re.IGNORECASE)
                if col_match:
                    metric_col = col_match.group(2)
            # 获取 GROUP BY 列（如果有的话）
            group_col = None
            group_match = re.search(r'GROUP\s+BY\s+(\w+)', adjusted_sql, re.IGNORECASE)
            if group_match:
                group_col = group_match.group(1)
            # 添加 ORDER BY 和 LIMIT
            if group_col:
                adjusted_sql = re.sub(r'\s*$', '', adjusted_sql)  # 去掉末尾空白
                if "ORDER BY" not in adjusted_sql.upper():
                    adjusted_sql += f" ORDER BY {metric_col} DESC"
                if "LIMIT" not in adjusted_sql.upper():
                    adjusted_sql += f" LIMIT {top_n}"

        return adjusted_sql

    def _extract_time_from_text(self, text: str) -> Optional[str]:
        """从文本中提取时间范围（支持所有动态时间表达）"""
        from ai.engine.time_parser import TimeParser

        parser = TimeParser()
        result = parser.parse(text)

        if result:
            return result.get('time_key')

        return None

    def _extract_time_info(self, text: str) -> Optional[Dict]:
        """从文本中提取完整时间信息（用于追问和SQL组装）"""
        from ai.engine.time_parser import TimeParser

        parser = TimeParser()
        return parser.parse(text)

    def _extract_top_n(self, text: str) -> Optional[int]:
        """从文本中提取 top N 排名信息（如"前三"、"前十"、"前13名"、"十三级"等）"""
        import re
        # 中文数字映射
        chinese_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '零': 0}
        # 匹配"前"+"数字/中文数字"+"名"或"级"等
        patterns = [
            r'前(\d+)名',                  # 前10名、前13名
            r'前(\d+)级',                  # 前10级
            r'前([一二三四五六七八九十零]+)名',  # 前三名、前十名
            r'前([一二三四五六七八九十]+)',     # 前三、前十
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1)
                if num_str.isdigit():
                    return int(num_str)
                # 中文数字转换
                if num_str in chinese_nums:
                    return chinese_nums[num_str]
                # 处理"十三"这种复合中文数字（十+数字）
                if len(num_str) >= 1 and num_str[0] == '十':
                    result = 10
                    for c in num_str[1:]:
                        result += chinese_nums.get(c, 0)
                    return result if result > 10 else chinese_nums.get(num_str, 0)
        return None

    def _extract_time_range(self, text: str) -> Optional[str]:
        """从文本中提取时间范围（内部格式）"""
        return self._extract_time_from_text(text)

    def _build_sql_from_template(self, starrocks_sql: str, state: ConversationState) -> str:
        """从预置 SQL 模板构建查询"""
        # 如果预置 SQL 已经是完整查询，直接返回
        if "metric_id" in starrocks_sql.lower() or "metric_code" in starrocks_sql.lower():
            return starrocks_sql
        return starrocks_sql

    async def execute_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        执行查询节点
        - skip_sql_generation=True -> 跳过执行（非查询意图）
        - intent_is_metadata_query=True -> 查 PostgreSQL 元数据
        - intent_is_metadata_query=False -> 查 StarRocks 数值
        """
        if state.needs_clarification:
            self._add_thinking_step(state, "数据查询", "pending", "等待追问确认")
            return {"skip_execution": True}

        # 非查询意图：跳过执行
        non_query_intents = ["greeting", "thanks", "bye", "unknown"]
        if state.current_intent in non_query_intents:
            return {"skip_execution": True}

        metric_name = state.entities.get("metric_name")
        metric_code = state.entities.get("metric_code")

        # 元数据查询 -> 查 PostgreSQL
        if getattr(state, 'intent_is_metadata_query', False):
            try:
                metadata_result = self.sql_generator.query_metadata(
                    metric_name=metric_name,
                    metric_code=metric_code
                )

                if metadata_result.get("type") == "error":
                    state.error = metadata_result.get("error", "未找到该指标")
                    return {"error": state.error, "needs_clarification": True}

                if metadata_result.get("type") == "list":
                    state.sql_result = metadata_result
                    self._add_thinking_step(state, "数据查询", "completed",
                        f"找到 {len(metadata_result.get('metrics', []))} 个匹配的指标")
                    return {"sql_result": metadata_result, "multiple_matches": True}

                state.sql_result = metadata_result
                state.generated_sql = "SELECT * FROM metrics WHERE metric_code = ?"

                # 保存 starrocks_sql 供后续使用
                if metadata_result.get("starrocks_sql"):
                    state.entities["starrocks_sql"] = metadata_result["starrocks_sql"]

                # 保存有效的指标信息到 last_valid_metric（用于follow-up）
                if metadata_result.get("metric_name") or metadata_result.get("metric_code"):
                    state.last_valid_metric = {
                        "metric_name": metadata_result.get("metric_name"),
                        "metric_code": metadata_result.get("metric_code"),
                        "metric_id": metadata_result.get("id"),
                        "unit": metadata_result.get("unit"),
                        "starrocks_sql": metadata_result.get("starrocks_sql"),
                    }

                return {"sql_result": metadata_result, "is_metadata": True}

            except Exception as e:
                state.error = f"元数据查询失败: {str(e)}"
                return {"error": state.error, "needs_clarification": True}

        # 数值查询 -> 查 StarRocks（如果配置了 execute 接口）
        if state.generated_sql and state.generated_sql != "METADATA_QUERY":
            try:
                result = await self.sql_generator.execute(
                    sql=state.generated_sql,
                    params=state.sql_params
                )
                state.sql_result = result
                # 记录思考步骤：数据查询
                data_count = len(result.get("data", [])) if isinstance(result, dict) else 0
                self._add_thinking_step(state, "数据查询", "completed",
                    f"查询到 {data_count} 条数据" if data_count > 0 else "暂无数据")
                return {"sql_result": result, "is_metadata": False}
            except Exception as e:
                # StarRocks 查询失败，记录但继续（可能是没数据）
                state.sql_result = {"data": [], "message": f"暂无数据或查询失败: {str(e)}"}
                self._add_thinking_step(state, "数据查询", "error", f"查询失败: {str(e)}")
                return {"sql_result": state.sql_result, "is_metadata": False}

        # 没有 SQL 生成
        return {"skip_execution": True}

    async def comparison_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        对比计算节点 - 处理同比环比计算

        当意图为 query_comparison 时：
        1. 获取当前查询结果（当前周期值）
        2. 根据对比类型和时间范围计算对比周期
        3. 查询对比周期的值
        4. 计算涨跌幅
        """
        # 只有 query_comparison 意图才需要对比计算
        if state.current_intent != "query_comparison":
            logger.info("[comparison] 非query_comparison意图，跳过")
            return {"skip_comparison": True}

        # 没有查询结果，跳过
        if not state.sql_result or not state.sql_result.get("data"):
            logger.info("[comparison] 无查询结果，跳过")
            return {"skip_comparison": True}

        # 获取当前查询结果的数值
        current_value = self._extract_metric_value(state.sql_result)
        logger.info(f"[comparison] current_value={current_value}")
        if current_value is None:
            logger.info("[comparison] 无法提取当前值，跳过")
            return {"skip_comparison": True}

        # 从用户消息中判断是对比类型
        last_message = state.messages[-1].content if state.messages else ""
        comparison_type = "环比" if "环比" in last_message else "同比"

        # 从 time_info 中提取时间范围
        time_info = state.entities.get("time_info", {})
        time_range = state.entities.get("time_range", {})

        # 优先用 time_info 的 start/end
        if time_info:
            start_date = time_info.get("start")
            end_date = time_info.get("end")
        elif time_range:
            start_date = time_range.get("start")
            end_date = time_range.get("end")
        else:
            start_date = None
            end_date = None

        logger.info(f"[comparison] time_info={time_info}, start_date={start_date}, end_date={end_date}")

        if not start_date or not end_date:
            logger.warning("[comparison] 无法从 time_info 提取时间范围，跳过对比计算")
            result = {"skip_comparison": True, "reason": "无法提取时间范围"}
            logger.info(f"[comparison] 返回: {result}")
            return result

        # 计算对比周期
        import re
        from datetime import datetime
        try:
            # 解析开始和结束日期
            start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
            end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")

            # 判断原始时间范围是否是完整月份（结束日期是该月最后一天）
            is_full_month = end_dt.day == calendar.monthrange(end_dt.year, end_dt.month)[1]
            logger.info(f"[comparison] is_full_month={is_full_month} (end_dt.day={end_dt.day})")

            if comparison_type == "环比":
                # 环比：上月同日（保持日期天数一致）
                if start_dt.month == 1:
                    comp_start_year = start_dt.year - 1
                    comp_start_month = 12
                else:
                    comp_start_year = start_dt.year
                    comp_start_month = start_dt.month - 1

                if end_dt.month == 1:
                    comp_end_year = end_dt.year - 1
                    comp_end_month = 12
                else:
                    comp_end_year = end_dt.year
                    comp_end_month = end_dt.month - 1

                if is_full_month:
                    # 整月查询：起始日期保持，结束日期用对比月月末
                    comparison_start = f"{comp_start_year}-{comp_start_month:02d}-{start_dt.day:02d}"
                    comp_end_day = calendar.monthrange(comp_end_year, comp_end_month)[1]
                    comparison_end = f"{comp_end_year}-{comp_end_month:02d}-{comp_end_day:02d}"
                else:
                    # 非整月（如4月2日）：保持原始日期不变
                    comparison_start = f"{comp_start_year}-{comp_start_month:02d}-{start_dt.day:02d}"
                    comparison_end = f"{comp_end_year}-{comp_end_month:02d}-{end_dt.day:02d}"
            else:
                # 同比：去年同期
                comp_start_year = start_dt.year - 1
                comp_end_year = end_dt.year - 1
                if is_full_month:
                    # 整月查询：起始日期保持，结束日期用对比月月末
                    comparison_start = f"{comp_start_year}-{start_dt.month:02d}-{start_dt.day:02d}"
                    comp_end_day = calendar.monthrange(comp_end_year, end_dt.month)[1]
                    comparison_end = f"{comp_end_year}-{end_dt.month:02d}-{comp_end_day:02d}"
                else:
                    # 非整月（如4月2日）：保持原始日期不变
                    comparison_start = f"{comp_start_year}-{start_dt.month:02d}-{start_dt.day:02d}"
                    comparison_end = f"{comp_end_year}-{end_dt.month:02d}-{end_dt.day:02d}"
        except Exception as e:
            logger.error(f"[comparison] 日期计算失败: {str(e)}")
            return {"skip_comparison": True}

        logger.info(f"[comparison] comparison_type={comparison_type}, comparison_start={comparison_start}, comparison_end={comparison_end}")

        # 构建对比SQL（替换时间条件）
        original_sql = state.generated_sql
        if not original_sql or original_sql == "METADATA_QUERY":
            logger.info("[comparison] original_sql无效，跳过")
            return {"skip_comparison": True}

        # 替换开始日期 (处理 >= 和 = 两种格式)
        # FDATE >= '2026-01-01' 或 FDATE = '2026-01-01'
        # 注意：使用 lambda 避免 f-string 中 \1 的转义问题
        comparison_sql = re.sub(
            r"(\w+)\s*>=\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?",
            lambda m: f"{m.group(1)} >= '{comparison_start}'",
            original_sql,
            flags=re.IGNORECASE
        )
        # 替换结束日期
        comparison_sql = re.sub(
            r"(\w+)\s*<=\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?",
            lambda m: f"{m.group(1)} <= '{comparison_end}'",
            comparison_sql,
            flags=re.IGNORECASE
        )

        # 移除 LIMIT 和 OFFSET（用于对比查询）
        comparison_sql = re.sub(r'\s+LIMIT\s+\d+\s*(OFFSET\s+\d+)?', '', comparison_sql, flags=re.IGNORECASE)
        comparison_sql = re.sub(r'\s+OFFSET\s+\d+', '', comparison_sql, flags=re.IGNORECASE)
        logger.info(f"[comparison] 生成的对比SQL: {comparison_sql}")

        try:
            logger.info(f"[comparison] 对比SQL: {comparison_sql}")
            # 执行对比查询
            comparison_result = await self.sql_generator.execute(
                sql=comparison_sql,
                params=state.sql_params
            )
            logger.info(f"[comparison] 对比查询结果: {comparison_result}")

            comparison_value = self._extract_metric_value(comparison_result)
            logger.info(f"[comparison] 提取的对比值: {comparison_value}")

            if comparison_value is not None and comparison_value != 0:
                # 计算涨跌幅
                change_rate = (current_value - comparison_value) / comparison_value * 100

                state.comparison_result = {
                    "current_value": current_value,
                    "comparison_value": comparison_value,
                    "comparison_date": f"{comparison_start} 至 {comparison_end}",
                    "comparison_type": comparison_type,
                    "change_rate": change_rate,
                    "comparison_sql": comparison_sql,
                }

                self._add_thinking_step(state, "对比计算", "completed",
                    f"当前值={current_value}，{comparison_type}={comparison_value}，"
                    f"涨跌幅={change_rate:+.2f}%")

                result = {"comparison_result": state.comparison_result}
                logger.info(f"[comparison] 成功返回: {result}")
                return result
            else:
                self._add_thinking_step(state, "对比计算", "completed", "对比数据为空")
                logger.info("[comparison] 对比数据为空，跳过")
                return {"skip_comparison": True}

        except Exception as e:
            logger.error(f"[comparison] 查询对比数据失败: {str(e)}")
            self._add_thinking_step(state, "对比计算", "error", f"对比查询失败: {str(e)}")
            logger.info(f"[comparison] 异常跳过: {str(e)}")
            return {"skip_comparison": True}

    def _extract_metric_value(self, sql_result: Dict) -> Optional[float]:
        """从SQL查询结果中提取指标数值"""
        if not sql_result:
            return None

        data = sql_result.get("data")
        if not data:
            return None

        # 处理嵌套结构: {"data": {"count": 1, "data": [...]}}
        # 外层 {"count": ..., "data": [...}} 包装，需要提取内层的 data
        if isinstance(data, dict) and "data" in data:
            inner_data = data["data"]
            if isinstance(inner_data, list) and inner_data:
                data = inner_data
            elif isinstance(inner_data, dict):
                # 内层也是包装结构，递归处理
                return self._extract_metric_value({"data": inner_data})

        # 判断 data 是列表还是单个字典
        if isinstance(data, list):
            if not data:
                return None
            row = data[0]
        elif isinstance(data, dict):
            row = data
        else:
            return None

        # 尝试从不同可能的字段名提取值
        value_fields = ["value", "metric_value", "total", "amount", "cnt", "count", "num", "page_views", "sessions_total"]
        for field in value_fields:
            # 不区分大小写匹配
            for key in row.keys():
                if key.lower() == field.lower() and row[key] is not None:
                    try:
                        val = row[key]
                        if isinstance(val, str):
                            val = val.replace(",", "").strip()
                        return float(val)
                    except (ValueError, TypeError):
                        continue

        # 如果都没找到，尝试取第一个数值类型的值
        for key, val in row.items():
            if isinstance(val, (int, float)):
                return float(val)
            # 处理字符串形式的数字
            if isinstance(val, str):
                try:
                    return float(val.replace(",", "").strip())
                except (ValueError, TypeError):
                    continue

        return None

    def response_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        生成回答节点
        - 元数据查询：展示业务口径、技术口径等
        - 数值查询：展示实际数据或"暂无数据"
        """
        # 需要追问的情况
        if state.needs_clarification:
            # metric_enum 类型：直接显示匹配指标列表
            clarification_type = getattr(state, 'clarification_type', None)
            if clarification_type == "metric_enum":
                return {
                    "answer": state.clarification_message,
                    "suggest_questions": getattr(state, 'suggest_questions', []) or self._generate_suggestions(state),
                    "needs_clarification": True,
                }
            # 其他追问类型：优先使用 state.error
            error_msg = getattr(state, 'error', None)
            if error_msg:
                return {
                    "answer": f"抱歉，{error_msg}",
                    "suggest_questions": getattr(state, 'suggest_questions', []) or self._generate_suggestions(state),
                    "needs_clarification": True,
                }
            # 使用 clarification_message 作为追问内容
            return {
                "answer": state.clarification_message or "抱歉，我需要更多信息来回答您的问题",
                "suggest_questions": getattr(state, 'suggest_questions', []) or self._generate_suggestions(state),
                "needs_clarification": True,
            }

        # 打招呼
        if state.current_intent == "greeting":
            return {
                "answer": "您好！我是智能问数助手，可以帮您查询指标信息。请问您想查询哪个指标？",
                "suggest_questions": ["昨天的访客数是多少", "本周订单量如何", "查看销售额指标"],
                "needs_clarification": False,
            }

        # 感谢
        if state.current_intent == "thanks":
            return {
                "answer": "不客气！很高兴能帮到您。有什么其他问题随时问我～",
                "suggest_questions": ["昨天的访客数是多少", "本周订单量如何", "查看销售额指标"],
                "needs_clarification": False,
            }

        # 告别
        if state.current_intent == "bye":
            return {
                "answer": "再见！如有需要随时召唤我～",
                "suggest_questions": [],
                "needs_clarification": False,
            }

        # 业务术语查询 - 直接返回术语解释
        if state.entities.get("is_business_term") or state.current_intent == "query_term_definition":
            term_name = state.entities.get("business_term_name", "")
            term_desc = state.entities.get("business_term_description", "")
            if term_desc:
                return {
                    "answer": f"**{term_name}**\n\n{term_desc}",
                    "suggest_questions": [
                        "帮我查一下总销售额",
                        "什么是转化率",
                        "查看更多指标定义"
                    ],
                    "needs_clarification": False,
                }
            else:
                return {
                    "answer": f"抱歉，暂时没有关于 {term_name} 的详细解释",
                    "suggest_questions": ["帮我查指标数据", "什么是转化率"],
                    "needs_clarification": False,
                }

        # 获取查询结果
        sql_result = getattr(state, 'sql_result', None)

        # 多个指标匹配的情况
        if isinstance(sql_result, dict) and sql_result.get("type") == "list":
            metrics = sql_result.get("metrics", [])
            if metrics:
                metric_list = "\n".join([f"{i+1}. {m.get('name')} ({m.get('metric_code')})" for i, m in enumerate(metrics[:5])])
                return {
                    "answer": f"找到多个匹配的指标，请选择：\n{metric_list}",
                    "suggest_questions": [f"查看{metrics[0].get('name')}" if metrics else "告诉我具体指标名称"],
                    "needs_clarification": True,
                }

        # 元数据查询结果 - 展示业务口径、技术口径等
        if getattr(state, 'intent_is_metadata_query', False):
            if isinstance(sql_result, dict) and sql_result.get("type") == "metric_info":
                return self._format_metric_response(sql_result, state)
            # 没有找到元数据
            metric_name = state.entities.get("metric_name", "")
            return {
                "answer": f"未找到 {metric_name} 的详细信息，请确认指标名称是否正确",
                "suggest_questions": self._generate_suggestions(state),
                "needs_clarification": False,
            }

        # 数值查询结果
        if sql_result:
            # 检查是否没有数据
            if isinstance(sql_result, dict):
                data = sql_result.get("data", [])
                message = sql_result.get("message", "")
                if not data or message and "无数据" in message:
                    metric_name = state.entities.get("metric_name", "")
                    time_range = state.entities.get("time_range", "") or (state.entities.get("time_info", {}).get("original") if state.entities.get("time_info") else "")
                    # 调用 LLM 生成智能追问
                    followup_result = self.llm_engine.generate_empty_result_followup(
                        question=state.messages[-1].content if state.messages else "",
                        metric_name=metric_name,
                        time_range=time_range,
                        sql=state.generated_sql or "",
                    )
                    # 兼容 suggestions 格式：可能是 [{"text": "..."}] 也可能是 ["字符串"]
                    raw_suggestions = followup_result.get("suggestions", []) if isinstance(followup_result, dict) else []
                    suggestions = []
                    for s in raw_suggestions:
                        if isinstance(s, str):
                            suggestions.append(s)
                        elif isinstance(s, dict):
                            text = s.get("text", "") or s.get("suggestion", "") or s.get("reply", "")
                            if text:
                                suggestions.append(text)
                    analysis = followup_result.get("analysis", "数据为空") if isinstance(followup_result, dict) else "数据为空"
                    needs_clar = followup_result.get("needs_clarification", False) if isinstance(followup_result, dict) else False
                    # 保存当前指标/时间到上下文，供下一轮追问恢复
                    self._update_context(state, state.entities)
                    return {
                        "answer": f"抱歉，没有查到 {metric_name or '该指标'} 的数据。\n\n{analysis}\n\n您可以尝试：\n" + "\n".join([f"- {s}" for s in suggestions[:3]]) if suggestions else f"抱歉，没有查到 {metric_name or '该指标'} 的数据。",
                        "suggest_questions": suggestions[:3] if suggestions else [f"{metric_name}的业务口径" if metric_name else "帮我查其他指标"],
                        "needs_clarification": needs_clar,
                    }
                elif data:
                    # 有数据，调用 LLM 生成自然语言回答
                    metric_name = state.entities.get("metric_name", "该指标")
                    unit = state.entities.get("unit", "")
                    answer = self.llm_engine.generate_response(
                        question=state.messages[-1].content if state.messages else "",
                        sql=state.generated_sql or "",
                        result=data,
                        metric_name=metric_name,
                        unit=unit,
                    )

                    # 如果有对比计算结果，添加到 result_data 每行
                    comparison_result = getattr(state, 'comparison_result', None)
                    if comparison_result:
                        comp_type = comparison_result.get("comparison_type", "对比")
                        comp_date = comparison_result.get("comparison_date", "")
                        comp_value = comparison_result.get("comparison_value", 0)
                        change_rate = comparison_result.get("change_rate", 0)
                        current_value = comparison_result.get("current_value", 0)

                        # 格式化数值
                        def format_value(val, unit):
                            if isinstance(val, (int, float)):
                                if unit == "%":
                                    return f"{val:.2f}%"
                                elif unit in ("元", "万美元", "亿美元"):
                                    return f"¥{val:,.2f}"
                                else:
                                    return f"{val:,.2f}"
                            return str(val)

                        current_str = format_value(current_value, unit)
                        comp_str = f"{int(comp_value):,}" if isinstance(comp_value, (int, float)) and comp_value == int(comp_value) else format_value(comp_value, unit)

                        # 添加到 result_data 每行（用于前端表格展示）
                        # 处理 Go 返回的嵌套格式: {"count": N, "data": [...]} 或直接的 list/dict
                        rows_to_process = data
                        if isinstance(data, dict):
                            if "data" in data:
                                # Go 返回的嵌套格式，解开外层包装
                                rows_to_process = data["data"]
                            else:
                                # 单行 dict 结果，包装成 list
                                rows_to_process = [data]
                        # rows_to_process 现在应该是 list
                        if isinstance(rows_to_process, list):
                            for row in rows_to_process:
                                if isinstance(row, dict):
                                    if comp_type == "同比":
                                        row["去年同期"] = comp_str
                                    else:
                                        row["上月同期"] = comp_str
                        # 更新 data 为处理后的结果（返回扁平数组供 API 使用）
                        if isinstance(data, dict) and "data" in data:
                            # 原为嵌套格式，解包后返回内层扁平数组
                            data = rows_to_process
                        else:
                            data = rows_to_process


                        if comp_type == "同比":
                            comp_period = f"去年同期（{comp_date[:7]}）" if comp_date else "去年同期"
                        else:
                            comp_period = f"上月同期（{comp_date[:7]}）" if comp_date else "上月同期"

                        change_emoji = "↑" if change_rate > 0 else ("↓" if change_rate < 0 else "→")
                        change_color = "上涨" if change_rate > 0 else ("下跌" if change_rate < 0 else "持平")

                        # 对比摘要（可选，保留在 answer 里供参考）
                        answer += f"\n\n📊 **对比结果**\n"
                        answer += f"| 指标 | 数值 |\n"
                        answer += f"|------|------|\n"
                        answer += f"| {metric_name}（当期） | {current_str} |\n"
                        answer += f"| {comp_period} | {comp_str} |\n"
                        answer += f"| {comp_type}变化 | {change_emoji} {abs(change_rate):.2f}%（{change_color}）|\n"

                    # 保存当前指标/时间到上下文
                    self._update_context(state, state.entities)

                    # 用户选择了某个维度值后，更新频次
                    if getattr(state, 'selected_dimension_field', None) and getattr(state, 'selected_dimension_value', None):
                        dim_value_client = DimValueClient()
                        dim_value_client.increment_frequency(
                            state.selected_dimension_field,
                            state.selected_dimension_value
                        )
                        logger.info(f"[response_node] 更新维度值频次: {state.selected_dimension_field}={state.selected_dimension_value}")

                    # 处理嵌套格式，确保 result_data 是 list
                    result_data = data
                    if isinstance(data, dict) and "data" in data:
                        result_data = data["data"]
                    return {
                        "answer": answer,
                        "suggest_questions": self._generate_suggestions(state),
                        "needs_clarification": False,
                        "result_data": result_data,
                        "comparison_result": getattr(state, 'comparison_result', None),
                    }

        # 没有结果
        self._update_context(state, state.entities)
        return {
            "answer": "抱歉，未能获取到有效数据",
            "suggest_questions": self._generate_suggestions(state),
            "needs_clarification": False,
        }

    def _format_metric_response(self, metric_info: Dict[str, Any], state: ConversationState) -> Dict[str, Any]:
        """格式化指标信息响应"""
        lines = [
            f"**{metric_info.get('metric_name', '未知指标')}**",
            f"- 指标编号：`{metric_info.get('metric_code', 'N/A')}`",
            f"- 所属域：{metric_info.get('domain', 'N/A')}",
            f"- 指标分类：{metric_info.get('category_1', 'N/A')}",
            f"- 计量单位：{metric_info.get('unit', 'N/A')}",
            f"- 统计频度：{metric_info.get('frequency', 'N/A')}",
        ]

        if metric_info.get('business_definition'):
            lines.append(f"\n**业务定义：**\n{metric_info.get('business_definition')}")

        if metric_info.get('business_rule'):
            lines.append(f"\n**业务口径：**\n{metric_info.get('business_rule')}")

        if metric_info.get('technical_rule'):
            lines.append(f"\n**技术口径：**\n{metric_info.get('technical_rule')}")

        return {
            "answer": "\n".join(lines),
            "suggest_questions": [
                f"查看{metric_info.get('metric_name')}的近期数据",
                "查看其他指标",
            ],
            "needs_clarification": False,
        }

    def _generate_suggestions(self, state: ConversationState) -> List[str]:
        """生成后续问题建议"""
        suggestions = []
        metric_name = state.entities.get("metric_name", "")

        if metric_name:
            suggestions = [
                f"查看{metric_name}的本周数据",
                f"查看{metric_name}的趋势变化",
                f"对比{metric_name}的环比数据",
            ]
        else:
            suggestions = [
                "昨天的访客数是多少",
                "本周的订单量如何",
                "本月销售额趋势",
            ]

        return suggestions

    def intent_feedback_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        意图反馈节点 - 检测用户纠正并记录反馈
        当用户说"不对"、"不是的"、"应该是XX"时触发
        """
        last_message = state.messages[-1].content if state.messages else ""

        # 纠正模式检测
        correction_patterns = [
            r"不对", r"不是的", r"应该是", r"不是([^叫]|$)", r"我说的是",
            r"其实(是|要)", r"错了", r"纠正"
        ]

        is_correction = any(re.search(p, last_message) for p in correction_patterns)

        if not is_correction:
            return {"intent_feedback": None}

        logger.debug(f"[intent_feedback] 检测到用户纠正: {last_message}")

        # 提取用户想要的意图
        correct_intent = self._extract_intent_from_feedback(last_message)

        if correct_intent:
            # 调用 Go API 记录反馈
            self._record_intent_feedback(
                user_input=last_message,
                predicted_intent=state.current_intent or "",
                correct_intent=correct_intent,
                session_id=state.session_id
            )
            logger.debug(f"[intent_feedback] 记录反馈: predicted={state.current_intent}, correct={correct_intent}")

        # 设置追问，让用户确认正确意图
        state.needs_clarification = True
        state.clarification_type = "intent_feedback"
        state.clarification_message = "抱歉，您是想查询指标值、趋势、还是对比数据呢？"

        return {"intent_feedback": {"correct_intent": correct_intent}}

    def _extract_intent_from_feedback(self, text: str) -> Optional[str]:
        """从用户纠正文本中提取正确意图"""
        # 意图关键词映射
        intent_keywords = {
            "query_value": ["数值", "值", "多少", "多少数据", "是多少"],
            "query_trend": ["趋势", "变化", "走向", "走势", "增长", "下降"],
            "query_comparison": ["对比", "比较", "差异", "哪个高", "哪个好"],
            "query_metadata": ["口径", "定义", "业务口径", "技术口径", "元数据"],
        }

        text = text.lower()
        for intent, keywords in intent_keywords.items():
            if any(kw in text for kw in keywords):
                return intent

        return None

    def _record_intent_feedback(self, user_input: str, predicted_intent: str, correct_intent: str, session_id: str):
        """调用 Go API 记录意图反馈"""
        try:
            import httpx
            api_base = os.getenv("AI_API_BASE", "http://localhost:8080")
            url = f"{api_base}/api/v1/feedback/intent"

            payload = {
                "user_input": user_input,
                "predicted_intent": predicted_intent,
                "correct_intent": correct_intent,
                "session_id": session_id,
            }

            httpx.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.debug(f"[intent_feedback] 记录反馈失败: {e}")


# 全局节点实例
conversation_nodes = ConversationNodes()
