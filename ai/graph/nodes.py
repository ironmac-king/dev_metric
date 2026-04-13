"""
LangGraph 对话节点 - 优化版
"""
import re
import os
import asyncio
import calendar
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List
from ai.graph.state import ConversationState, IntentResult, SQLGenerationResult, ClarificationDecision, ThinkingStep, ConversationContext
from ai.engine.rule_engine import RuleEngine
from ai.engine.llm import LLMEngine
from ai.sql_gen.generator import SQLGenerator
from ai.sql_gen.query_builder import QueryBuilder, QueryState, QueryDimension, TimeSpec, ComparisonSpec, PaginationSpec, QueryIntent
from ai.client.metric_client import MetricClient
from ai.client.dim_value_client import DimValueClient
from ai.config.logging_config import get_logger
from ai.graph._dimension_resolver import DimensionResolver
from ai.graph._sql_builder import SQLBuilder
from ai.graph._result_formatter import ResultFormatter
from ai.ner.ner_service import get_ner_service

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

    # 业务维度别名映射（用于当 dimension_configs 中没有直接配置时）
    BIZ_DIM_ALIASES = {
        "平台": "平台",  # "平台" 别名映射到 "店铺"
    }

    def __init__(self):
        self.rule_engine = RuleEngine()
        self.llm_engine = LLMEngine()
        self.sql_generator = SQLGenerator()
        self.metric_client = MetricClient()
        self.dimension_resolver = DimensionResolver(metric_client=self.metric_client)
        self.sql_builder = SQLBuilder(metric_client=self.metric_client, dimension_resolver=self.dimension_resolver)
        self.result_formatter = ResultFormatter(metric_client=self.metric_client, dimension_resolver=self.dimension_resolver)
        self.ner_service = get_ner_service()  # NER 服务

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

        # ========== Step 0.5: 闲聊意图检查（优先于满意度确认）==========
        # 从 rule_engine 加载的 intent_templates 配置检查闲聊意图
        import re
        msg_clean = re.sub(r'^[\s,，。、；：""''【】（ ）_\-+]+|[\s,，。、；：""''【】（ ）_\-+]+$', '', last_message.strip())

        # 模型问题（不在 intent_templates 里，需要硬编码）
        model_question_patterns = ["什么模型", "什么LLM", "什么AI", "你叫什么"]
        for pat in model_question_patterns:
            if pat in msg_clean:
                logger.info(f"[intent_node] 闲聊模型问题: '{last_message}'")
                self._add_thinking_step(state, "意图理解", "completed", f"闲聊模型问题")
                return {"current_intent": "greeting", "entities": {}}

        # 使用 rule_engine 的意图配置检查闲聊意图
        rule_intent_result = self.rule_engine.recognize_intent(msg_clean)
        if rule_intent_result and rule_intent_result.intent in ["greeting", "thanks", "bye"]:
            logger.info(f"[intent_node] 闲聊意图(Rule): '{last_message}' -> {rule_intent_result.intent}")
            self._add_thinking_step(state, "意图理解", "completed", f"闲聊{rule_intent_result.intent}")
            return {"current_intent": rule_intent_result.intent, "entities": {}}

        # 闲聊意图检查完成，继续满意度确认检查
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
            is_comparison_followup = last_message.strip() in ["环比呢", "同比呢", "环比", "同比"]
            ctx_check = getattr(state, 'conversation_context', None)
            logger.info(f"[intent_node Step0] last_msg='{last_message}' is_comparison={is_comparison_followup} ctx={ctx_check} ctx_metric={ctx_check.current_metric_name if ctx_check else None}")
            if (not matched_intent or is_comparison_followup) and len(last_message.strip()) <= 4:
                # 用户说"环比呢"/"同比呢"，用 LLM 补齐为完整问题
                if is_comparison_followup:
                    ctx = getattr(state, 'conversation_context', None)
                    logger.info(f"[intent_node] 环比/同比追问检测到, ctx={ctx}, current_metric={ctx.current_metric_name if ctx else None}")
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
                        logger.info(f"[intent_node] 恢复实体: {restored_entities}")
                        # 补齐后直接返回，让后续流程处理完整问题
                        return {
                            "current_intent": "query_comparison",
                            "entities": restored_entities
                        }
                    else:
                        logger.warning(f"[intent_node] 环比/同比追问但conversation_context为空，检查state.entities是否有继承指标")
                        # ctx 为 None 但 state.entities 可能包含从上一个恢复周期继承的指标信息
                        logger.info(f"[intent_node] state.entities内容: {state.entities}")
                        inherited_metric = state.entities.get("metric_name")
                        inherited_code = state.entities.get("metric_code")
                        logger.info(f"[intent_node] inherited_metric={inherited_metric}, inherited_code={inherited_code}")
                        if inherited_metric:
                            logger.info(f"[intent_node] 从state.entities恢复指标: metric_name={inherited_metric}, metric_code={inherited_code}")
                            comparison_type = "环比" if "环比" in last_message else "同比"
                            expanded = self.llm_engine.expand_followup_question(
                                last_message, inherited_metric, state.entities.get("time_range"), comparison_type
                            )
                            logger.info(f"[intent_node] LLM补齐(继承实体): '{last_message}' → '{expanded}'")
                            # 更新用户消息
                            state.messages[-1].content = expanded
                            self._add_thinking_step(state, "意图理解", "completed",
                                f"LLM补齐追问(继承实体)：'{expanded}'")
                            # 从 state.entities 恢复指标
                            restored_entities = {
                                "metric_name": inherited_metric,
                                "metric_code": inherited_code,
                            }
                            if state.entities.get("time_range"):
                                restored_entities["time_range"] = state.entities.get("time_range")
                            state.entities.update(restored_entities)
                            logger.info(f"[intent_node] 恢复实体(继承): {restored_entities}")
                            # 补齐后直接返回
                            return {
                                "current_intent": "query_comparison",
                                "entities": restored_entities
                            }
                        matched_intent = "query_value"
                else:
                    matched_intent = "query_value"

            # 如果 matched_intent 已确定（非短文本追问），走原有逻辑
            # 但如果消息中包含对比关键词，不在这里直接返回，而是继续到 Step 2 做完整识别
            has_comparison_kw = any(kw in last_message for kw in ["同比", "环比", "对比", "比较", "去年同期", "上月同期", "比去年同期", "比上月"])
            # 关键修复：如果消息同时有意图关键词和对比关键词（如"指标值，同比环比咋样"），
            # 不能直接返回matched_intent，要让Step 2识别出query_comparison意图
            if matched_intent and not (len(last_message.strip()) <= 4 and last_message.strip() in ["环比呢", "同比呢", "环比", "同比"]) and not (has_comparison_kw and matched_intent != "query_comparison"):
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
                else:
                    # ctx 为 None 时，检查 state.entities 是否有从上一个恢复周期继承的指标信息
                    inherited_metric = state.entities.get("metric_name")
                    inherited_code = state.entities.get("metric_code")
                    logger.info(f"[intent_node] ctx为空，从state.entities恢复: metric_name={inherited_metric}, metric_code={inherited_code}")
                    if inherited_metric:
                        restored_entities["metric_name"] = inherited_metric
                    if inherited_code:
                        restored_entities["metric_code"] = inherited_code
                    if state.entities.get("time_range"):
                        restored_entities["time_range"] = state.entities.get("time_range")

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
        else:
            # conversation_context 为空但 state.entities 可能有继承的指标信息
            inherited_metric = state.entities.get("metric_name")
            inherited_code = state.entities.get("metric_code")
            logger.info(f"[intent_node Step1] ctx为空,检查state.entities: metric_name={inherited_metric}, metric_code={inherited_code}")
            if inherited_metric:
                inherited_entities = {
                    "inherited_metric": inherited_metric,
                    "inherited_metric_name": inherited_metric,
                }
                # 同时更新 inherited_context 以便后续使用
                inherited_context.current_metric_name = inherited_metric
                inherited_context.current_metric_code = inherited_code
                inherited_context.current_time_expr = state.entities.get("time_range")
                logger.info(f"[intent_node Step1] 从state.entities恢复上下文: metric_name={inherited_metric}")

        logger.debug(f"[intent_node] 输入: {last_message}")

        # ========== Step 1.5: 短文本追问检测与扩展 ==========
        # 如果用户输入是"同比呢"/"环比呢"这类极短文本，先用 expand_followup_question 补齐
        is_comparison_short = last_message.strip() in ["环比呢", "同比呢", "环比", "同比"]
        if is_comparison_short and inherited_context.current_metric_name:
            comparison_type = "环比" if "环比" in last_message else "同比"
            expanded = self.llm_engine.expand_followup_question(
                last_message, inherited_context.current_metric_name,
                inherited_context.current_time_expr, comparison_type
            )
            logger.info(f"[intent_node] 短文本追问扩展: '{last_message}' → '{expanded}'")
            # 更新用户消息
            state.messages[-1].content = expanded
            # 扩展后的问题直接用于后续处理
            last_message = expanded

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

            # ========== Bug Fix 1: 先提取时间信息（不依赖 confidence） ==========
            formula_match = None  # 初始化，避免在 try 块外引用

            # 检查用户输入是否包含时间词
            has_explicit_time = bool(re.search(
                r'昨天|今日|明日|昨日|本周|本月|当月|上周|上月|去年|今年|明年|上个月|'
                r'近几|最近|过去|前几|天前|月前|周前|年前|'
                r'\d+月|\d+天|\d+周',
                last_message
            ))

            # 如果用户没有明确说时间，清除 LLM 推断的时间
            if intent_result.entities.get("time_range") and not has_explicit_time:
                logger.debug(f"[intent_node] 用户未明确时间，清除 LLM 推断的 time_range")
                intent_result.entities.pop("time_range", None)
                intent_result.entities.pop("time_info", None)
                intent_result.entities.pop("time_key", None)

            # 如果用户说了时间，提取 time_info（不依赖 confidence）
            if has_explicit_time:
                time_info = self._extract_time_info(last_message)
                if time_info:
                    intent_result.entities["time_info"] = time_info
                    # 如果 LLM 返回的 time_range 与实际解析的时间不一致，覆盖为正确的时间表达
                    llm_time_range = intent_result.entities.get("time_range", "")
                    parsed_time_original = time_info.get("original", "")
                    if llm_time_range and parsed_time_original and llm_time_range != parsed_time_original:
                        logger.info(f"[intent_node] 时间修正: LLM返回={llm_time_range}, 实际解析={parsed_time_original}, 覆盖为正确值")
                        intent_result.entities["time_range"] = parsed_time_original
                    elif not llm_time_range:
                        intent_result.entities["time_range"] = parsed_time_original
                    logger.info(f"[intent_node] 时间解析: {time_info.get('time_key')}, original={time_info.get('original')}")

            # ========== Bug Fix 2: 公式语法匹配修正 intent ==========
            formula_match = self._match_formula_syntax(intent_result.intent, last_message)
            final_intent = intent_result.intent
            if formula_match:
                formula_intent = formula_match.get("intent_type")
                if formula_intent and formula_intent != intent_result.intent:
                    logger.info(f"[intent_node] 公式修正: {intent_result.intent} → {formula_intent}, matched={formula_match.get('name')}")
                    final_intent = formula_intent
                    state.matched_formula_syntax = formula_match

            # ========== Bug Fix 3: 置信度检查（formula_match 可以修正 intent） ==========
            # 先检查是否包含对比关键词（需要在置信度检查之前处理）
            has_comparison_kw = any(kw in last_message for kw in ["同比", "环比", "对比", "比较", "去年同期", "上月同期", "比去年同期", "比上月"])
            # 如果有对比关键词，先覆盖 intent 为 query_comparison（即使置信度低）
            if has_comparison_kw and intent_result.intent not in ["query_comparison", "query_trend"]:
                logger.info(f"[intent_node] 检测到对比关键词，覆盖 intent: {intent_result.intent} → query_comparison")
                intent_result.intent = "query_comparison"
                final_intent = "query_comparison"  # 同时修改 final_intent
                intent_result.confidence = max(intent_result.confidence, 0.5)  # 提高置信度
            # 如果有对比关键词但没有明确时间，设置默认时间范围（昨天）以避免追问
            if has_comparison_kw and not has_explicit_time and not intent_result.entities.get("time_range"):
                intent_result.entities["time_range"] = "昨天"
                logger.info(f"[intent_node] 对比关键词检测但无明确时间，设置默认时间范围: 昨天")

            # ========== Bug Fix: 时间查询意图但包含指标词，强制转为 query_value ==========
            # "昨天的访客数" -> query_yesterday 是错的，应该用 query_value
            # 因为 "访客数" 是明确的指标，时间只是修饰词
            time_only_intents = ["query_yesterday", "query_today", "query_this_week", "query_this_month"]
            contains_metric_reference = any(word in last_message for word in ["数", "量", "额", "率", "次数", "人数", "销售额", "订单", "转化", "访客", "用户", "销量", "收入", "利润", "成本"])
            if intent_result.intent in time_only_intents and contains_metric_reference:
                logger.info(f"[intent_node] 时间意图但包含指标词，修正: {intent_result.intent} → query_value")
                intent_result.intent = "query_value"
                final_intent = "query_value"
                intent_result.confidence = max(intent_result.confidence, 0.5)

            # 置信度检查：只有既没有 formula_match 也没有明确时间且没有对比关键词且不是闲聊意图时才追问
            # greeting/thanks/bye 等闲聊意图直接放行，不走置信度检查
            non_metric_intents = ["greeting", "thanks", "bye", "unknown"]
            if intent_result.confidence < 0.4 and not formula_match and not has_explicit_time and not has_comparison_kw and intent_result.intent not in non_metric_intents:
                state.needs_clarification = True
                state.clarification_type = "intent"
                state.clarification_message = "抱歉，我没理解您的意思。您是想查询指标值、趋势、还是对比数据呢？"
                self._add_thinking_step(state, "意图理解", "requires_clarification",
                    f"LLM 置信度 {intent_result.confidence:.2f} < 0.4，需要追问")
                # 【修复】早期返回前保存上下文，确保 dimension 等信息不丢失
                self._update_context(state, intent_result.entities)
                return {"current_intent": None, "entities": intent_result.entities}

            # 补充 top_n 排名信息（检测"前三"、"前十"、"前13"等模式）
            # 规则引擎优先：当检测到"最高的"（无具体数字）模式时，即使 LLM 返回 top_n=1 也用规则引擎结果覆盖
            rule_top_n = self._extract_top_n(last_message)
            logger.info(f"[intent_node] _extract_top_n('{last_message}') = {rule_top_n}")

            llm_top_n = intent_result.entities.get("top_n")
            # 规则引擎检测到"最高的"无具体数字（默认10），但LLM返回top_n=1，用规则引擎覆盖
            if rule_top_n and rule_top_n == 10 and llm_top_n == 1:
                intent_result.entities["top_n"] = rule_top_n
                self._add_thinking_step(state, "排名信息", "completed",
                    f"LLM top_n=1 不合理，用规则引擎覆盖为 {rule_top_n}")
                logger.info(f"[intent_node] LLM top_n=1 不合理，覆盖为 {rule_top_n}")
            elif not llm_top_n and rule_top_n:
                intent_result.entities["top_n"] = rule_top_n
                self._add_thinking_step(state, "排名信息", "completed",
                    f"检测到 top_n: {rule_top_n}，将添加排序")
                logger.debug(f"[intent_node] 检测到 top_n: {rule_top_n}")

            # 补充排名维度信息（检测"最高的+维度词"模式，如"最高的品类"）
            # 当公式语法匹配到排名意图时，自动提取分组维度
            if not intent_result.entities.get("dimension") and not intent_result.entities.get("category"):
                detected_dim = self.dimension_resolver.extract_ranking_dimension(last_message, final_intent)
                if detected_dim:
                    intent_result.entities["dimension"] = detected_dim
                    logger.debug(f"[intent_node] 检测到排名维度: {detected_dim}")

            # ========== 再次检查对比关键词（用于确保最终 intent 正确）==========
            # 注意：此时 has_comparison_kw 已在前面定义并处理过，这里仅用于日志
            if has_comparison_kw and final_intent not in ["query_comparison"]:
                logger.info(f"[intent_node] 检测到对比关键词，override intent: {final_intent} → query_comparison")
                final_intent = "query_comparison"

        except Exception as e:
            logger.error(f"[intent_node] LLM 意图识别失败: {e}")
            # LLM 失败时，使用默认值
            intent_result = IntentResult(
                intent="query_value",
                confidence=0.3,
                entities={}
            )
            final_intent = "query_value"

        # ========== 更新上下文 ==========
        self._update_context(state, intent_result.entities)

        # 记录思考步骤
        intent_desc = {
            "query_value": "查询数值",
            "query_trend": "查询趋势",
            "query_comparison": "对比分析",
            "query_metadata": "查询元数据",
            "query_ranking": "排名分析",
            "query_ratio": "占比分析",
            "query_retention": "留存分析",
            "greeting": "问候",
            "thanks": "感谢",
            "bye": "告别",
        }.get(final_intent, final_intent)

        formula_note = f", 公式修正" if formula_match else ""
        self._add_thinking_step(state, "意图理解", "completed",
            f"LLM 识别为「{intent_desc}」，置信度 {intent_result.confidence:.2f}{formula_note}")

        return {
            "current_intent": final_intent,
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
            logger.info(f"[_update_context] 保存 metric_name: {entities.get('metric_name')}")
        if entities.get("metric_code"):
            ctx.current_metric_code = entities.get("metric_code")
            logger.info(f"[_update_context] 保存 metric_code: {entities.get('metric_code')}")

        # 更新多指标信息（用于环比/同比追问时恢复多指标查询）
        if entities.get("metrics") and len(entities.get("metrics", [])) >= 2:
            ctx.current_metrics = entities.get("metrics")
            logger.info(f"[_update_context] 保存 metrics: {[m.get('metric_name') for m in ctx.current_metrics]}")

        # 更新时间表达式（只接受字符串类型，防止 LLM 返回 dict 污染）
        time_range_val = entities.get("time_range")
        if time_range_val and isinstance(time_range_val, str):
            ctx.current_time_expr = time_range_val

        # 更新维度（同时保存业务维度名和数据库列名）
        for dim_key in ["platform", "region", "department", "site", "category", "device"]:
            if entities.get(dim_key):
                ctx.current_dimensions[dim_key] = entities.get(dim_key)

        # 保存数据库维度列（从动态维度字段获取）
        all_dim_keys = self._get_all_dimension_keys()
        for dim_key in all_dim_keys:
            if entities.get(dim_key):
                ctx.current_dimensions[dim_key] = entities.get(dim_key)
                logger.info(f"[_update_context] 保存数据库维度: {dim_key}={entities.get(dim_key)}")

        # 保存 GROUP BY 维度（dimension 用于单维度，dimensions 用于多维度）
        # 例如：用户问"哪个品类"，entities = {"dimension": "GROUP_3"}
        if entities.get("dimension"):
            ctx.current_dimensions["dimension"] = entities.get("dimension")
            state.entities["dimension"] = entities.get("dimension")  # 同时更新 state.entities，防止被清除
            logger.info(f"[_update_context] 保存 dimension: {entities.get('dimension')}")
        if entities.get("dimensions"):
            ctx.current_dimensions["dimensions"] = entities.get("dimensions")
            state.entities["dimensions"] = entities.get("dimensions")  # 同时更新 state.entities，防止被清除
            logger.info(f"[_update_context] 保存 dimensions: {entities.get('dimensions')}")

        state.conversation_context = ctx

    def _extract_potential_dim_values(self, text: str, entities: Dict) -> List[str]:
        """
        从用户输入中提取可能是维度值的词
        排除：指标名、时间、已识别的维度
        策略：优先提取完整的维度值（4-8字），避免将 "笔记本支架" 拆成 "笔记本"
        """
        import re
        metric_name = entities.get("metric_name", "") or ""
        logger.info(f"[_extract_potential_dim_values] 输入: text={text}, metric_name={metric_name}")

        # 使用重叠匹配来提取所有可能的维度值
        # (?=...) 是 lookahead，不消耗字符，所以可以重叠匹配
        results = []

        # 提取4-8字的完整维度值（更可能精确匹配）
        for length in [8, 7, 6, 5, 4]:
            # 使用重叠匹配提取固定长度的中文字符串
            # 直接匹配 length 个连续汉字，match.group() 返回完整的 length 字符
            pattern = re.compile(r'[\u4e00-\u9fa5]{' + str(length) + '}')
            for match in pattern.finditer(text):
                segment = match.group()  # 直接获取匹配到的 length 个字符
                start = match.start()
                # 跳过时间词和指标名
                if self._is_time_word(segment):
                    continue
                if segment in metric_name or metric_name in segment:
                    continue
                # 过滤包含"中的/占比/比例"等关键词的片段（这些是占比表达式的一部分，不是维度）
                for keyword in ["中的", "占比", "比例"]:
                    if keyword in segment:
                        break
                else:
                    if segment not in results:  # 避免重复
                        results.append(segment)

        # 如果没有找到4-8字的词，尝试提取2-3字的短词
        if not results:
            for length in [3, 2]:
                pattern = re.compile(r'[\u4e00-\u9fa5]{' + str(length) + '}')
                for match in pattern.finditer(text):
                    segment = match.group()
                    start = match.start()
                    if self._is_time_word(segment):
                        continue
                    if segment in metric_name or metric_name in segment:
                        continue
                    # 过滤包含"中的/占比/比例"等关键词的片段
                    for keyword in ["中的", "占比", "比例"]:
                        if keyword in segment:
                            break
                    else:
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

        logger.info(f"[_extract_potential_dim_values] 返回: results={results}")
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

    def query_state_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        QueryState 生成节点 - LLM 生成结构化查询描述

        使用 LLM 将用户问题转换为 QueryState JSON，然后补充 metric 元数据
        """
        last_message = state.messages[-1].content if state.messages else ""

        # 调用 LLM 生成 QueryState
        context = None
        # 如果有上一轮的 QueryState，传入上下文
        if hasattr(state, '_query_state') and state._query_state:
            context = state._query_state

        query_state = self.llm_engine.generate_query_state(
            question=last_message,
            session_id=state.session_id,
            context=context
        )

        if not query_state:
            self._add_thinking_step(state, "QueryState 生成", "failed", "LLM 生成 QueryState 失败")
            return {"needs_clarification": True, "clarification_message": "无法理解您的问题，请换一种方式描述"}

        # 记录思考步骤
        self._add_thinking_step(state, "QueryState 生成", "completed",
            f"意图: {query_state.get('intent')}, 指标: {query_state.get('metric', {}).get('name', '未知')}",
            llm_used=True)

        # 保存 QueryState 到 state
        state._query_state = query_state

        # 补充 metric 元数据（从 metric_client 获取）
        metric_code = query_state.get("metric", {}).get("code")
        if metric_code:
            metric = self.metric_client.get_metric_by_code(metric_code)
            if metric:
                query_state["metric"]["starrocks_table"] = metric.get("starrocks_table")
                query_state["metric"]["starrocks_sql"] = metric.get("starrocks_sql")
                query_state["metric"]["unit"] = metric.get("unit")

        # 转换 metric 为 QueryMetric 格式
        metric_info = query_state.get("metric", {})
        if metric_info.get("starrocks_sql"):
            # 从 starrocks_sql 解析字段
            from ai.sql_gen.query_builder import QueryBuilder
            builder = QueryBuilder()
            field_mapping = builder._parse_starrocks_sql(metric_info["starrocks_sql"])
            for f in field_mapping.get("select_fields", []):
                if f.get("aggregation"):
                    query_state.setdefault("metrics", []).append({
                        "name": f["alias"],
                        "display_name": f["alias"],
                        "aggregation": f["aggregation"],
                        "field": f["field"],
                        "alias": f["alias"]
                    })

        return {"query_state": query_state}

    def entity_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        实体链接节点 - 增强版
        支持多轮上下文继承
        """
        logger.info(f"[entity_node] START session_id={getattr(state, 'session_id', None)}")
        entities = state.entities.copy()

        # ========== 获取对话上下文 ==========
        ctx = getattr(state, 'conversation_context', None)

        # ========== 继承上轮的指标信息 ==========
        if ctx and not entities.get("metric_code") and not entities.get("metric_name"):
            if ctx.current_metric_name or ctx.current_metric_code:
                entities.setdefault("metric_name", ctx.current_metric_name)
                entities.setdefault("metric_code", ctx.current_metric_code)
                logger.debug(f"[entity_node] 继承上轮指标: {ctx.current_metric_name}")

        # ========== 继承上轮的多指标信息（用于环比/同比追问）==========
        # 当用户问"环比呢"时，如果上一轮是多指标查询，应该继承多指标信息
        if ctx and ctx.current_metrics and not entities.get("metrics"):
            entities["metrics"] = ctx.current_metrics
            logger.info(f"[entity_node] 继承上轮多指标: {[m.get('metric_name') for m in ctx.current_metrics]}")

        # ========== 继承上轮的时间表达式 ==========
        # 检查用户是否明确指定了新的时间
        last_message = state.messages[-1].content if state.messages else ""
        has_explicit_time = any(kw in last_message for kw in ["昨天", "今日", "本周", "本月", "当月", "去年", "上月"])
        # 特殊处理：环比/同比追问应该继承时间，保持和上轮一样的时间周期
        is_comparison_followup = any(kw in last_message for kw in ["环比呢", "同比呢", "环比", "同比"])

        # 如果是纯追问（环比/同比追问），强制继承上下文时间，不使用 LLM 识别的错误时间
        if is_comparison_followup and ctx and ctx.current_time_expr and isinstance(ctx.current_time_expr, str):
            entities["time_range"] = ctx.current_time_expr
            # 同时提取 time_info（用于对比计算）
            time_info = self._extract_time_info(ctx.current_time_expr)
            if time_info:
                entities["time_info"] = time_info
            logger.info(f"[entity_node] 环比/同比追问，强制继承上轮时间: {ctx.current_time_expr}, time_info={time_info}")
        elif ctx and not entities.get("time_range") and ctx.current_time_expr and isinstance(ctx.current_time_expr, str):
            if not has_explicit_time:
                entities.setdefault("time_range", ctx.current_time_expr)
                logger.debug(f"[entity_node] 继承上轮时间: {ctx.current_time_expr}")

        # ========== 继承上轮的维度 ==========
        if ctx:
            for dim_key, dim_value in ctx.current_dimensions.items():
                if dim_key not in entities and dim_value:
                    entities[dim_key] = dim_value
                    logger.debug(f"[entity_node] 继承上轮维度: {dim_key}={dim_value}")

        last_message = state.messages[-1].content if state.messages else ""

        # ========== 清除维度值选择状态（新问数时）==========
        # 如果当前不是在回应 dimension_value 追问，则清除上轮残留的维度选择状态
        # 避免上一轮选择的维度值（如 GROUP_3='智能云存储'）污染新问数
        if getattr(state, 'clarification_type', None) != 'dimension_value':
            if hasattr(state, 'selected_dimension_field'):
                logger.info(f"[entity_node] 清除残留维度选择状态: selected_dimension_field={state.selected_dimension_field}")
                state.selected_dimension_field = None
                state.selected_dimension_value = None
            if hasattr(state, 'dimension_value_candidates'):
                state.dimension_value_candidates = None

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

                # 【修复】用户选择指标后，恢复上轮的 GROUP BY 维度（如"哪个品类"→GROUP_3）
                # 因为 chosen_metric 不包含 dimension/dimensions，需要从 context 恢复
                logger.info(f"[entity_node] 恢复dimension检查: state.entities.dimension={getattr(state, 'entities', {}).get('dimension')}, ctx.dimension={getattr(ctx, 'current_dimensions', {}).get('dimension') if ctx else 'ctx is None'}")
                if ctx and ctx.current_dimensions:
                    if ctx.current_dimensions.get("dimension") and not entities.get("dimension"):
                        entities["dimension"] = ctx.current_dimensions.get("dimension")
                        logger.info(f"[entity_node] 从context恢复dimension: {entities['dimension']}")
                    if ctx.current_dimensions.get("dimensions") and not entities.get("dimensions"):
                        entities["dimensions"] = ctx.current_dimensions.get("dimensions")
                        logger.info(f"[entity_node] 从context恢复dimensions: {entities['dimensions']}")

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

        # ========== 占比公式处理：提取分子/分母指标信息 ==========
        # 当 entities 中有 molecule_metric 时（ratio 查询），需要链接分子和分母指标
        molecule_metric = entities.get("molecule_metric", "")
        denominator_metric = entities.get("denominator_metric", "")
        if molecule_metric and denominator_metric:
            logger.info(f"[entity_node] 占比公式: molecule={molecule_metric}, denominator={denominator_metric}")

            # 链接分子指标
            molecule_links = self.rule_engine.link_business_terms_enhanced(
                molecule_metric,
                {}
            )
            # 链接分母指标
            denominator_links = self.rule_engine.link_business_terms_enhanced(
                denominator_metric,
                {}
            )

            if molecule_links:
                entities["molecule_metric_info"] = molecule_links
                logger.info(f"[entity_node] 分子指标链接成功: {molecule_links.get('metric_name')}")
            if denominator_links:
                entities["denominator_metric_info"] = denominator_links
                logger.info(f"[entity_node] 分母指标链接成功: {denominator_links.get('metric_name')}")

            # 【修复】当检测到占比公式时，修正被污染的 dimension
            # 如果 dimension 包含"中的"、"占比"等ratio关键词，说明 LLM 把整个短语当成了 dimension
            # 需要提取真正的分组维度（如"店铺"）
            current_dim = entities.get("dimension", "")
            if current_dim and any(kw in current_dim for kw in ["中的", "占比", "比例"]):
                # 尝试提取真正的维度：查找常见的分组维度词
                valid_dims = ["店铺", "站点", "平台", "渠道", "品类", "商品", "SKU", "ASIN", "国家", "地区", "区域", "部门"]
                for dim in valid_dims:
                    if dim in current_dim:
                        # 找到了真正的维度，设置正确的 dimension
                        entities["dimension"] = dim
                        logger.info(f"[entity_node] 占比公式修正dimension: '{current_dim}' -> '{dim}'")
                        break
                    else:
                        # 没找到已知维度，清除错误的 dimension
                        entities.pop("dimension", None)
                        logger.info(f"[entity_node] 占比公式清除错误dimension: '{current_dim}'")

        # 是否为纯追问（只有定义/口径/环比/同比等词，没有指标名）
        follow_up_only_indicators = ["定义", "口径", "规则", "怎么", "如何", "环比", "同比"]
        # 注意：环比/同比是意图词，不是指标名，不要加入 contains_metric_reference
        contains_metric_reference = any(word in last_message for word in ["数", "量", "额", "率", "次数", "人数", "销售额", "订单", "转化", "访客", "用户"])

        # 只有当查询只包含 follow-up 指示词，且不包含指标名时，才保留继承的指标
        is_pure_followup = any(ind in last_message for ind in follow_up_only_indicators) and not contains_metric_reference

        # 检查是否从上一轮继承了指标
        inherited_metric = entities.get("metric_name") or entities.get("metric_code")

        # 清除继承指标的条件：
        # 1. 用户说了明确的 follow-up 词（如"定义呢"、"口径呢"），保留继承
        # 2. 用户说了新的指标相关词，清除继承
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

        # 检查是否提到了维度相关词（从 business_terms 动态获取）
        # 当用户提到维度词时，应该清除旧的维度过滤
        dimension_keywords = []
        if hasattr(self.rule_engine, 'business_terms'):
            for term_key, term_info in self.rule_engine.business_terms.items():
                # 只获取有 dimension_field 的业务术语（表示这是维度相关的同义词）
                if term_info.get("dimension_field"):
                    dimension_keywords.append(term_key)
                    # 同时加入 synonyms
                    synonyms = term_info.get("synonyms", [])
                    if isinstance(synonyms, list):
                        dimension_keywords.extend([s.lower() for s in synonyms])
                    else:
                        logger.warning(f"[entity_node] synonyms 不是列表类型: {synonyms}, term_key={term_key}")
        # Fallback：如果 business_terms 为空或没加载，使用硬编码的常见维度词
        if not dimension_keywords:
            dimension_keywords = [
                "类目", "品类", "种类", "分类", "商品", "产品",
                "SKU", "sku", "款号", "ASIN", "asin",
                "品牌", "牌子", "站点", "平台", "渠道",
                "地区", "区域", "地域", "省份", "国家",
                "部门", "科室", "设备", "广告",
            ]
        contains_dimension_keyword = any(dim_kw in last_message for dim_kw in dimension_keywords)

        logger.info(f"[entity_node] 清除检查: is_pure_followup={is_pure_followup}, inherited_metric={inherited_metric}, contains_dimension_keyword={contains_dimension_keyword}, is_short_input={is_short_input}, term_links={bool(term_links)}, last_message={last_message}")

        # 无论 term_links 是否为空，只要用户提到了新的指标或维度词，就应该清除旧的维度过滤
        # 这样可以避免上一轮的维度值（如 SKU=70312）污染新查询
        # 当用户指定了新的维度值（如"美国站"）时，也应该清除旧的维度过滤
        has_new_dimension_value = bool(entities.get("dimension_values"))
        if not is_pure_followup and inherited_metric and not user_just_selected_metric and not is_confirmation and not intent_confirmed_from_context:
            if contains_metric_reference or contains_dimension_keyword or has_new_dimension_value or (is_short_input and not is_time_word):
                # 用户说了指标相关词、维度词，或输入很短且不是时间词，清除继承
                entities["metric_name"] = None
                entities["metric_code"] = None
                entities["unit"] = None
                entities["starrocks_sql"] = None
                # 同时清除旧的维度过滤条件，避免污染新问题
                # 从 business_terms 和 _dimension_cache 动态获取所有维度字段
                dim_filter_keys = set()  # 使用 set 去重
                # 从 business_terms 获取 dimension_field、synonyms 及其大小写变体
                if hasattr(self.rule_engine, 'business_terms'):
                    for term_key, term_info in self.rule_engine.business_terms.items():
                        dim_field = term_info.get("dimension_field")
                        if dim_field:
                            dim_filter_keys.add(dim_field)
                            dim_filter_keys.add(dim_field.upper())
                            dim_filter_keys.add(dim_field.lower())
                        # 添加 synonyms（业务术语的同义词，如 sku、款号 等）
                        synonyms = term_info.get("synonyms", [])
                        for syn in synonyms:
                            if syn:
                                dim_filter_keys.add(syn)
                                dim_filter_keys.add(syn.upper())
                                dim_filter_keys.add(syn.lower())
                # 从 _dimension_cache 获取所有维度列名
                if hasattr(self.rule_engine, '_dimension_cache'):
                    for dim_name, dim_mapping in self.rule_engine._dimension_cache.items():
                        for col_name in dim_mapping.values():
                            if col_name:
                                dim_filter_keys.add(col_name)
                                dim_filter_keys.add(col_name.upper())
                                dim_filter_keys.add(col_name.lower())
                dim_filter_keys = list(dim_filter_keys)
                logger.info(f"[entity_node] 准备清除维度, dim_filter_keys={dim_filter_keys}, 当前entities={entities}")
                for dim_key in dim_filter_keys:
                    if dim_key in entities:
                        entities[dim_key] = None
                        logger.info(f"[entity_node] 清除旧维度过滤: {dim_key}")
                # 【修复】只清除 dimensions 列表（过滤条件），保护 dimension（GROUP BY 维度）
                # dimension 是语义维度（如 GROUP_3），不应该被清除，否则"哪个品类"等 GROUP BY 语义会丢失
                entities["dimensions"] = []
                logger.info(f"[entity_node] 清除 dimensions 列表，保留 dimension={entities.get('dimension')}")

        # 如果实体链接返回空，检查是否是新的指标查询
        # 新指标查询的特征：包含指标相关的词（如"数"、"量"、"用户"等）
        # 如果是新的指标查询，即使 metric_id 已设置，也要清除（因为这是不同的指标）
        if not term_links:

            # 确认时清除 dimension，因为用户已确认具体指标，不需要多维度分解
            # 只有非时间维度才能清除（时间维度如"日"需要保留用于 GROUP BY）
            if is_confirmation:
                time_dims = ['日', '月', '年', '天', '周']
                if entities.get("dimension") not in time_dims:
                    entities.pop("dimension", None)

            # 关键优化：当规则引擎匹配不到时，尝试用 LLM 识别短输入中的指标
            # 比如用户说"sku"，LLM 可以识别出可能是"缺货SKU数"
            # 但如果用户已经提供了时间词（如"最近7天"）且有继承的指标，不要让 LLM 猜测新指标
            # 另外：如果是环比/同比追问且已有继承指标，不要用 LLM 猜测新指标
            is_comparison_followup = any(kw in last_message for kw in ["环比呢", "同比呢", "环比", "同比"])
            should_extract_metric = (is_short_input or (not term_links and not is_pure_followup)) and not (is_comparison_followup and inherited_metric)
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

        # ========== 占比公式维度修正：在 term_links 更新之后处理 ==========
        # 当有 molecule_metric 时（ratio 查询），dimension 可能被污染为"店铺退款数量在销量中"
        # 需要修正为正确的分组维度（如"店铺"）
        molecule_metric = entities.get("molecule_metric", "")
        denominator_metric = entities.get("denominator_metric", "")
        if molecule_metric and denominator_metric:
            current_dim = entities.get("dimension", "")
            logger.info(f"[entity_node] 占比公式检查: dimension='{current_dim}', molecule={molecule_metric}, denominator={denominator_metric}")
            if current_dim and any(kw in current_dim for kw in ["中的", "占比", "比例"]):
                valid_dims = ["店铺", "站点", "平台", "渠道", "品类", "商品", "SKU", "ASIN", "国家", "地区", "区域", "部门"]
                dim_fixed = False
                for dim in valid_dims:
                    if dim in current_dim:
                        entities["dimension"] = dim
                        logger.info(f"[entity_node] 占比公式修正dimension: '{current_dim}' -> '{dim}'")
                        dim_fixed = True
                        break
                if not dim_fixed:
                    entities.pop("dimension", None)
                    logger.info(f"[entity_node] 占比公式清除错误dimension: '{current_dim}'")

        # ========== 多指标检测：支持"本月销售额跟页面访问量是多少"类型查询 ==========
        multi_metrics = term_links.get("_multi_metrics", [])
        # 只有当查询中包含明确的多指标连接词时才触发多指标模式
        # 排除"总和"等包含"和"字的词语中的"和"
        has_multi_conjunction = False
        for c in ['跟', '和', '以及']:
            if c in last_message:
                # 进一步检查：确保"和"不是"总和"的一部分
                if c == '和':
                    idx = last_message.find('和')
                    # 检查是否是"总和"模式（和前面是量词/数词）
                    if idx > 0 and last_message[idx-1] in ['总', '计', '合', '共']:
                        continue  # 不是连接词，是词语的一部分
                    # 检查"X和Y"模式 - X和Y都应该是独立的词
                    if idx > 0 and idx < len(last_message) - 1:
                        prev_char = last_message[idx-1]
                        next_char = last_message[idx+1]
                        # 如果前后都是汉字/数字/字母，认为是连接词
                        if prev_char.isalnum() and next_char.isalnum():
                            has_multi_conjunction = True
                else:
                    has_multi_conjunction = True
        logger.info(f"[entity_node] 多指标检测: last_message={last_message!r}, has_multi_conjunction={has_multi_conjunction}, multi_metrics_count={len(multi_metrics)}")
        if len(multi_metrics) >= 2 and has_multi_conjunction:
            # 取前两个最高分的指标（来自不同 metric_name）
            top_metrics = []
            seen_names = set()
            for m in multi_metrics:
                name = m.get("metric_name", "")
                if name not in seen_names:
                    seen_names.add(name)
                    top_metrics.append(m)
                if len(top_metrics) >= 2:
                    break

            if len(top_metrics) >= 2:
                # 检查是否是不同概念（如一个销售额相关，一个页面访问量相关）
                m1_name = top_metrics[0].get("metric_name", "")
                m2_name = top_metrics[1].get("metric_name", "")
                # 如果两个指标名称核心词不同（不是同一指标的不同变体），视为多指标查询
                # 例如：页面访问量 vs 销售额 是不同概念
                # 页面访问量 vs 页面访问量-网页端 是同一概念的不同粒度
                concept_keywords_1 = set(m1_name.replace("-", "").replace("_", ""))
                concept_keywords_2 = set(m2_name.replace("-", "").replace("_", ""))
                # 如果两个名称的字符集重叠少于70%，认为是不同概念
                overlap = len(concept_keywords_1 & concept_keywords_2) / max(len(concept_keywords_1 | concept_keywords_2), 1)

                if overlap < 0.7:
                    logger.info(f"[entity_node] 检测到多指标查询: {m1_name} + {m2_name}")
                    entities["metrics"] = [
                        {
                            "metric_name": m.get("metric_name"),
                            "metric_code": m.get("metric_code"),
                            "metric_id": m.get("metric_id"),
                            "starrocks_sql": m.get("starrocks_sql"),
                            "unit": m.get("unit"),
                        }
                        for m in top_metrics
                    ]
                    # 清除单指标字段
                    entities.pop("metric_name", None)
                    entities.pop("metric_code", None)
                    entities.pop("metric_id", None)
                    entities.pop("starrocks_sql", None)
                    entities.pop("unit", None)

        # 处理 LLM 识别的 dimension_values（如 dimension_values='智能云存储'）
        # 转换为具体的 dimension_field（如 GROUP_3='智能云存储'）
        if entities.get("dimension_values") and not any(entities.get(k) for k in self._get_all_dimension_keys()):
            dim_value = entities.get("dimension_values")
            dim_type = entities.get("dimension")  # 如 "品类"
            logger.info(f"[entity_node] LLM 识别到 dimension_values={dim_value}, dimension={dim_type}，搜索对应字段")

            # 先检查 dim_type 是否是某个维度的同义词（如"平台"是"店铺"的同义词）
            actual_dim_type = dim_type
            if dim_type:
                # 遍历 business_terms 查找 dim_type 是否是某个维度的同义词
                for term_key, term_info in self.rule_engine.business_terms.items():
                    synonyms = term_info.get("synonyms", [])
                    dimension_field = term_info.get("dimension_field", "")
                    if dimension_field and any(dim_type == syn for syn in synonyms):
                        # 找到匹配：dim_type 是 term_key 的同义词
                        actual_dim_type = term_key
                        logger.info(f"[entity_node] 维度同义词映射: {dim_type} -> {term_key} (field={dimension_field})")
                        # 设置 dimension_field 和更新 dimension 名称
                        entities[dimension_field] = ""
                        entities["dimension"] = term_key  # 更新为实际维度名
                        break

            try:
                dim_value_client = DimValueClient()
                results = dim_value_client.search_dimension_values(dim_value, None, 3)
                if results:
                    # 优先精确匹配
                    exact_matches = [r for r in results if r.get("match_type") == "exact"]
                    if exact_matches:
                        matched = exact_matches[0]
                    else:
                        matched = results[0]
                    entities[matched["dimension_field"]] = matched["dimension_value"]
                    entities.pop("dimension_values", None)  # 清除旧的
                    # 只有非时间维度才能清除（时间维度如"日"需要保留用于 GROUP BY）
                    time_dims = ['日', '月', '年', '天', '周']
                    current_dim = entities.get("dimension")
                    logger.info(f"[entity_node] dimension_values 转换: current dimension={current_dim}, time_dims check: {current_dim in time_dims}")
                    if current_dim not in time_dims:
                        entities.pop("dimension", None)
                    logger.info(f"[entity_node] dimension_values 转换: {matched['dimension_field']}={matched['dimension_value']}, remaining dimension={entities.get('dimension')}")
            except Exception as e:
                logger.warning(f"[entity_node] dimension_values 转换失败: {e}")

        # 识别"按X查看"模式，设置时间维度（用于 GROUP BY）- 支持多维度
        # 匹配所有"按X查看"模式
        time_dim_map = {"日": "日", "天": "日", "月": "月", "年": "年", "周": "周"}

        # 匹配时间维度：按日查看、按月查看、每天、每月、每年等
        # 修复：只匹配明确的"按X查看"或"每X"模式，不匹配"今年"、"本月"等时间范围表达
        time_dim_pattern = r"(?:按|每)([日月年天周]+)(?:查看)?"
        time_matches = re.findall(time_dim_pattern, last_message)

        # 匹配业务维度：按平台查看、按部门查看、每个平台、每部门等
        # 支持"按X查看"和"每个/各X"两种模式
        # 使用 [^的查看]+ 来匹配连续的汉字（排除"的"和"查看"）
        # 【修复】排除包含"占比""比例""比率""中的""之中的"等计算表达式的匹配
        ratio_exclude_pattern = r"(?:占比|比例|比率|中的|之中的)"
        if re.search(ratio_exclude_pattern, last_message):
            # 如果包含计算表达式，不使用"各X"模式匹配，因为它会错误匹配"各店铺退款数量在销量中"
            biz_matches = []
        else:
            biz_dim_pattern = r"(?:按|每个|各)([^的查看]+)"
            biz_matches = re.findall(biz_dim_pattern, last_message)

        # 匹配"X对应的"模式（如"三级品类对应的"），这表示 GROUP BY
        # "上个月三级品类对应的销售额" -> 三级品类 是 GROUP BY 维度
        # 使用 jieba 分词来准确找到维度词边界
        import jieba
        words = list(jieba.cut(last_message))
        group_by_matches = []

        for i, word in enumerate(words):
            # 情况1: "对应" + "的" 相邻
            if word == "对应" and i + 1 < len(words) and words[i + 1] == "的":
                if i > 0:
                    # 往前最多取2个连续中文词合并（避免把"上个月"等时间词也合并进来）
                    chinese_parts = []
                    for j in range(i - 1, -1, -1):
                        w = words[j]
                        if re.match(r'^[\u4e00-\u9fa5]+$', w):
                            chinese_parts.insert(0, w)
                            if len(chinese_parts) >= 2:
                                break
                        else:
                            break
                    # 合并后的中文词
                    merged = ''.join(chinese_parts)
                    if 2 <= len(merged) <= 8:
                        group_by_matches.append(merged)
            # 情况2: "对应的" 作为一个词（jieba可能没分开），前面的词是维度名
            elif word == "对应的" and i > 0:
                merged = ''.join([w for w in words[i - 1:i] if re.match(r'^[\u4e00-\u9fa5]+$', w)])
                if 2 <= len(merged) <= 8:
                    group_by_matches.append(merged)

        logger.info(f"[entity_node] GROUP BY 模式匹配（jieba分词）: words={words}, group_by_matches={group_by_matches}")
        # 将匹配结果合并到 biz_matches
        for gm in group_by_matches:
            if gm and gm not in biz_matches:
                biz_matches.append(gm)

        # 过滤掉时间维度的匹配（因为已经单独处理了）
        all_dims = []
        for tm in time_matches:
            if tm in time_dim_map:
                all_dims.append(time_dim_map[tm])

        # 【修复】使用 jieba 分词精确提取"各X"模式的维度词
        # 例如："各站点" -> "站点"（jieba分词为["各", "站点"]）
        # 问题：正则 biz_dim_pattern 会贪婪匹配"各站点上个月不含税收入"
        # 解决：检测到"各"后，提取紧跟的下一个词作为维度词
        ge_prefix_words = ["各", "每个", "各个"]
        for i, word in enumerate(words):
            if word in ge_prefix_words and i + 1 < len(words):
                next_word = words[i + 1]
                # 验证这是有效的维度词（2-6个中文字，不含时间词）
                if 2 <= len(next_word) <= 6 and re.match(r'^[\u4e00-\u9fa5]+$', next_word):
                    if not any(time_kw in next_word for time_kw in ["最近", "天", "日", "月", "年", "周", "今日", "昨日", "明日", "本周", "本月", "去年", "今日", "上个月", "下个月"]):
                        if next_word not in biz_matches:
                            biz_matches.append(next_word)
                            logger.info(f"[entity_node] 【修复】从jieba分词提取'各X'维度: {next_word} (from '各' + {words[i+1]})")
        # 【修复结束】

        # 输出原始字节，避免中文显示乱码
        print(f"[DEBUG entity_node] time_matches={time_matches}, biz_matches={biz_matches}")
        for i, bm in enumerate(biz_matches):
            print(f"[DEBUG entity_node] biz_matches[{i}] chars={[hex(ord(c)) for c in bm]}")

        # SQL关键字过滤器：排除排序相关的词，这些不是维度
        SQL_ORDER_KEYWORDS = [
            "降序", "升序", "排序", "降序排列", "升序排列",
            "从大到小", "从小到大", "按降序", "按升序",
            "排列", "顺序", "倒序", "正序",
            "照", "按照", "按着"  # "照...排列" 是排序指令，不是维度
        ]

        # 计算表达式过滤器：排除比率/占比相关的词，这些不是维度
        RATIO_KEYWORDS = ["占比", "比例", "比率", "在...中", "在...里", "中的", "之中的"]

        # 时间词过滤器：包含时间词的匹配结果不是业务维度
        TIME_KEYWORDS = ["最近", "天", "日", "月", "年", "周", "今日", "昨日", "明日", "本周", "本月", "去年"]

        # 量词前缀过滤器：这些前缀单独出现不是有效维度
        DIMENSION_PREFIXES = ["个", "只", "台", "款", "条", "件"]

        for bm in biz_matches:
            # 排除已经是时间维度的词
            if bm not in time_dim_map:
                # 去掉常见的量词前缀，避免"每个平台"、"各平台"、"个店铺"等被当作维度名
                cleaned_dim = bm
                # 先去掉"每个/各/各个"前缀
                for prefix in ["每个", "各", "各个"]:
                    if cleaned_dim.startswith(prefix):
                        cleaned_dim = cleaned_dim[len(prefix):]
                        break
                # 再去掉单个量词前缀（如"个店铺" -> "店铺"）
                for prefix in ["个", "只", "台", "款", "条", "件"]:
                    if cleaned_dim.startswith(prefix):
                        cleaned_dim = cleaned_dim[len(prefix):]
                        break
                # 过滤掉SQL排序关键字（精确匹配或包含）
                if any(kw in cleaned_dim for kw in SQL_ORDER_KEYWORDS):
                    print(f"[DEBUG entity_node] 过滤SQL排序关键字: {cleaned_dim}")
                    continue
                # 过滤掉包含时间词的匹配结果（如"个店铺最近7天"）
                if any(time_kw in cleaned_dim for time_kw in TIME_KEYWORDS):
                    print(f"[DEBUG entity_node] 过滤时间词维度: {cleaned_dim}")
                    continue
                # 过滤掉包含比率/占比关键词的匹配结果（如"退款数量在销量中"）
                if any(ratio_kw in cleaned_dim for ratio_kw in RATIO_KEYWORDS):
                    print(f"[DEBUG entity_node] 过滤比率关键词维度: {cleaned_dim}")
                    continue
                # 过滤掉过长的匹配结果（可能是错误的贪婪匹配）
                if len(cleaned_dim) > 10:
                    print(f"[DEBUG entity_node] 过滤过长维度: {cleaned_dim}")
                    continue
                # 过滤掉过短的匹配结果（可能是错误的匹配，如"个"）
                if len(cleaned_dim) < 2:
                    print(f"[DEBUG entity_node] 过滤过短维度: {cleaned_dim}")
                    continue
                # 过滤掉以量词开头的匹配结果（如"个店铺"）
                if any(cleaned_dim.startswith(p) for p in DIMENSION_PREFIXES):
                    print(f"[DEBUG entity_node] 过滤量词前缀维度: {cleaned_dim}")
                    continue
                # 打印所有检查的结果
                in_sql_kw = cleaned_dim in SQL_ORDER_KEYWORDS
                in_time_kw = any(time_kw in cleaned_dim for time_kw in TIME_KEYWORDS)
                len_gt10 = len(cleaned_dim) > 10
                len_lt2 = len(cleaned_dim) < 2
                has_prefix = any(cleaned_dim.startswith(p) for p in DIMENSION_PREFIXES)
                print(f"[DEBUG entity_node] 维度检查: cleaned_dim={cleaned_dim!r}, in_sql_kw={in_sql_kw}, in_time_kw={in_time_kw}, len_gt10={len_gt10}, len_lt2={len_lt2}, has_prefix={has_prefix}")
                if not any([in_sql_kw, in_time_kw, len_gt10, len_lt2, has_prefix]):
                    print(f"[DEBUG entity_node] bm={bm!r}, cleaned_dim={cleaned_dim!r} -> 追加到all_dims")
                if cleaned_dim:
                    all_dims.append(cleaned_dim)
                else:
                    all_dims.append(bm)  # 清理后为空则保留原值

        print(f"[DEBUG entity_node] all_dims={all_dims}")

        # 【重要】如果没有任何 all_dims，但有 __SYNONYM__ 标记的维度
        # 说明用户提到了维度类型但没有指定具体值（如"哪个ASIN"）
        # 应该把这个维度加入 dimensions 列表
        if not all_dims:
            synonym_dims = []
            for k, v in entities.items():
                if v == "__SYNONYM__":
                    synonym_dims.append(k)
            if synonym_dims:
                all_dims = synonym_dims
                entities["dimensions"] = all_dims
                entities["dimension"] = all_dims[0]  # 兼容旧逻辑
                logger.info(f"[entity_node] 检测到维度类型（__SYNONYM__）但无具体值，自动设置 dimension={all_dims}")

        # 【修复】过滤 LLM 直接设置的"按X"时间维度（不是业务维度）
        # 支持"按月"、"按月份"、"按月查看"等多种变体
        if entities.get("dimension"):
            dim = entities["dimension"]
            if re.match(r'^按[日月年周天]', dim) or '月份' in dim or '年份' in dim or '周日' in dim:
                logger.info(f"[entity_node] 清除LLM设置的时间维度: {dim}")
                entities.pop("dimension", None)

        # 【修复】过滤 LLM 直接设置的包含排序关键词的 dimension（如"照销售额降序排列"）
        if entities.get("dimension"):
            dim = entities["dimension"]
            if any(kw in dim for kw in SQL_ORDER_KEYWORDS):
                logger.info(f"[entity_node] 清除LLM设置的排序维度: {dim}")
                entities.pop("dimension", None)
            # 【防御】过滤过长的 dimension（超过10个字符的很可能是错误匹配）
            elif len(dim) > 10:
                entities.pop("dimension", None)
            # 【防御】过滤包含比率/占比关键词的 dimension（如"退款数量在销量中"）
            # 直接检查"退款数量在销量中"这个特定错误模式
            if '退款数量在销量中' in dim or '中的' in dim or '占比' in dim or '比例' in dim:
                entities.pop("dimension", None)
            elif any(kw in dim for kw in RATIO_KEYWORDS):
                entities.pop("dimension", None)

        if all_dims:
            # 多维度支持：存储为列表，同时兼容单维度
            entities["dimensions"] = all_dims
            entities["dimension"] = all_dims[0]  # 兼容旧逻辑
            logger.debug(f"[entity_node] 识别多维度: {entities['dimensions']}")

            # 校验维度名是否在 dimension_configs 中注册
            # 获取 starrocks_table 用于查询维度配置
            starrocks_table = state.entities.get("starrocks_table")
            if not starrocks_table and state.entities.get("starrocks_sql"):
                from_match = re.search(r'FROM\s+([a-zA-Z0-9_.]+)', state.entities.get("starrocks_sql"), re.IGNORECASE)
                if from_match:
                    starrocks_table = from_match.group(1).strip()

            unregistered_dims = []
            for dim in all_dims:
                # 跳过时间维度（日、月、年等）
                if dim in ["日", "月", "年", "天", "周", "day", "month", "year"]:
                    continue
                # 跳过"按X"格式的时间维度（如"按月"、"按日"），这不是业务维度
                if re.match(r'^按[日月年周天]$', dim):
                    logger.info(f"[entity_node] 跳过'按X'格式时间维度: {dim}")
                    continue
                if not self._is_dimension_name_registered(dim, starrocks_table):
                    unregistered_dims.append(dim)

            if unregistered_dims:
                logger.warning(f"[entity_node] 发现未注册的维度: {unregistered_dims}")
                # 设置追问状态，提示用户
                state.needs_clarification = True
                state.clarification_type = "invalid_dimension"
                state.clarification_message = f"抱歉，暂时没有配置「{unregistered_dims[0]}」维度，您可以尝试：站点、平台、品类等维度"
                logger.info(f"[entity_node] 设置追问状态: {state.clarification_message}")

        # 如果没有匹配到指标但有时间范围，也要提取
        if not entities.get("time_range"):
            time_range = self._extract_time_range(last_message)
            if time_range:
                entities["time_range"] = time_range

        # 提取完整时间信息（用于追问和SQL组装）
        # 优先使用 intent_node 中 LLM 已提取的 time_info（不受 Redis 编码损坏影响）
        # 只有当 LLM 未提取时才尝试解析，但 last_message 可能已乱码
        time_info = entities.get("time_info") or self._extract_time_info(last_message)
        if time_info:
            entities["time_info"] = time_info

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

        # ========== NER 维度识别（优先使用已知词典） ==========
        # 先用 NER 从 business_terms 中匹配已知的维度值
        ner_results = self.ner_service.recognize(last_message)
        logger.info(f"[entity_node] NER识别结果: {ner_results}")

        # 如果 NER 识别到维度，直接使用（优先级最高）
        if ner_results:
            # 获取唯一的维度字段（排除 __METRIC__ 类型，因为那是指标不是维度）
            ner_fields = list(set(r["dim_field"] for r in ner_results if r["dim_field"] and r["dim_field"] != "__METRIC__"))
            logger.info(f"[entity_node] NER识别到维度字段（排除指标后）: {ner_fields}")

            # 如果识别到有效的维度字段，设置它（即使没有具体值）
            # 这可以防止后续正则错误提取"退款数量在销量中"这种东西
            if len(ner_fields) == 1 and ner_fields[0]:
                ner_dim = ner_fields[0]
                # 收集该字段下的所有维度值（可能有值，也可能没有）
                dim_values = list(set(r["dim_value"] for r in ner_results if r["dim_field"] == ner_dim and r["dim_value"]))
                entities["dimension"] = ner_dim
                if dim_values:
                    entities["dimensions"] = dim_values
                    logger.info(f"[entity_node] NER设置dimension: {ner_dim}={dim_values}")
                else:
                    logger.info(f"[entity_node] NER识别到维度类型: {ner_dim}（无具体值，将通过后续搜索获取）")

        # ========== 维度值识别（并发优化） ==========
        # 提取未匹配的文本用于搜索维度值
        unmatched_texts = self._extract_potential_dim_values(last_message, entities)
        logger.info(f"[entity_node] 维度值提取结果: unmatched_texts={unmatched_texts}, metric_name={entities.get('metric_name', '')}")

        # 若 metric_code 已确定但没有未匹配文本，跳过维度值搜索
        if entities.get("metric_code") and not unmatched_texts:
            # 【修复】返回前恢复 dimension
            ctx = getattr(state, 'conversation_context', None)
            if ctx and ctx.current_dimensions.get("dimension") and not entities.get("dimension"):
                entities["dimension"] = ctx.current_dimensions.get("dimension")
                logger.info(f"[entity_node] RETURN前恢复dimension: {entities['dimension']}")
            logger.info(f"[entity_node] metric_code已确定但无未匹配文本，跳过维度值搜索")
            logger.info(f"[entity_node] RETURN")
            return {"entities": entities}

        # 并发搜索所有候选维度值（避免48次串行HTTP调用）
        candidate_results: List[tuple] = []
        dim_value_client = DimValueClient()
        if unmatched_texts:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {
                    executor.submit(dim_value_client.search_dimension_values, text, None, 3): text
                    for text in unmatched_texts
                }
                for future in as_completed(futures):
                    text = futures[future]
                    try:
                        candidates = future.result()
                    except Exception:
                        candidates = []
                    candidate_results.append((text, candidates))

        # 按提取顺序处理结果（保持优先级）
        for text, candidates in candidate_results:
            if candidates:
                # 优先使用精确匹配
                exact_matches = [c for c in candidates if c.get("match_type") == "exact"]
                if len(exact_matches) == 1:
                    # 唯一精确匹配，直接使用
                    matched = exact_matches[0]
                    entities[matched["dimension_field"]] = matched["dimension_value"]
                    # 清除泛指的 dimension，因为具体维度值已经确定
                    # 避免 SQL 生成时同时执行 GROUP BY 和 WHERE
                    # 只有非时间维度才能清除（时间维度如"日"需要保留用于 GROUP BY）
                    time_dims = ['日', '月', '年', '天', '周']
                    if entities.get("dimension") not in time_dims:
                        entities.pop("dimension", None)
                    logger.info(f"[entity_node] 识别维度值: {text} -> {matched['dimension_field']}={matched['dimension_value']} (精确匹配)")
                elif len(candidates) == 1:
                    # 唯一匹配（可能是前缀或模糊），直接使用
                    matched = candidates[0]
                    entities[matched["dimension_field"]] = matched["dimension_value"]
                    # 清除泛指的 dimension，因为具体维度值已经确定
                    # 只有非时间维度才能清除（时间维度如"日"需要保留用于 GROUP BY）
                    time_dims = ['日', '月', '年', '天', '周']
                    if entities.get("dimension") not in time_dims:
                        entities.pop("dimension", None)
                    logger.info(f"[entity_node] 识别维度值: {text} -> {matched['dimension_field']}={matched['dimension_value']}")
                else:
                    # 【重要】如果是排名查询（如"最高的XXX"），不应该追问维度值候选
                    # 而应该直接执行 GROUP BY 查询，让用户看到排名结果
                    is_ranking_query = state.current_intent == "query_ranking"
                    has_ranking_keywords = any(kw in last_message for kw in ["最高", "最低", "最多", "最少", "第一名", "前", "排名", "降低", "降低大", "降幅最大", "降幅最大", "增长", "增长大", "增幅最大"])
                    # 动态从 dimension_configs 获取所有已注册的维度名称
                    try:
                        all_dim_names = [cfg.get("dimension_name", "") for cfg in self.metric_client.get_dimension_configs() if cfg.get("status") == 1]
                        is_dimension_type_query = text in all_dim_names or text.upper() in [d.upper() for d in all_dim_names if d]
                    except:
                        is_dimension_type_query = text.upper() in ["SKU", "ASIN", "品类", "品牌", "渠道", "地区", "平台"]

                    if is_ranking_query or (has_ranking_keywords and is_dimension_type_query):
                        # 排名查询场景：直接跳过追问，将此作为 GROUP BY 维度处理
                        logger.info(f"[entity_node] 排名查询检测到维度类型词 '{text}'，跳过维度值追问，作为 GROUP BY 维度处理")
                        # 将 text 作为 dimension 存入 entities（如 "SKU"）
                        entities["dimension"] = text
                    else:
                        # 非排名查询：多个候选且无精确匹配，需要用户确认
                        state.needs_clarification = True
                        state.clarification_type = "dimension_value"
                        state.clarification_message = f"您说的是哪个维度：{[c['dimension_value'] for c in candidates]}？"
                        state.dimension_value_candidates = candidates  # 保存候选列表供后续解析
                        state.dimension_value_matched_text = text  # 保存匹配的原始文本（如"1011"）
                        # 【修复】返回前恢复 dimension
                        ctx = getattr(state, 'conversation_context', None)
                        if ctx and ctx.current_dimensions.get("dimension") and not entities.get("dimension"):
                            entities["dimension"] = ctx.current_dimensions.get("dimension")
                            logger.info(f"[entity_node] RETURN前恢复dimension: {entities['dimension']}")
                        logger.info(f"[entity_node] RETURN(dim_val_clar)")
                        return {"entities": entities}

        # 【修复】返回前：从 ctx 恢复 dimension 到 entities，防止被清除的 GROUP BY 维度丢失
        ctx = getattr(state, 'conversation_context', None)
        if ctx and ctx.current_dimensions.get("dimension"):
            if not entities.get("dimension"):
                entities["dimension"] = ctx.current_dimensions.get("dimension")
                logger.info(f"[entity_node] RETURN前恢复dimension: {entities['dimension']}")

        logger.info(f"[entity_node] RETURN")
        return {"entities": entities}

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

        # [DEBUG] clarification 时间检查日志
        logger.info(f"[clarification_node] time检查 | metric_name={metric_name} | time_range={time_range} | time_info={time_info} | current_intent={state.current_intent}")

        # 如果是 query_comparison 意图但缺少时间，设置默认时间范围（昨天）以继续执行
        if state.current_intent == "query_comparison" and not time_range and not time_info:
            logger.info(f"[clarification_node] query_comparison意图但缺少时间，设置默认时间范围: 昨天")
            return {
                "needs_clarification": False,
                "applied_defaults": {"time_range": "昨天"},
                "skip_clarification_reason": "query_comparison意图使用默认时间",
            }

        # 确定缺失字段
        missing_fields = []
        if not metric_name:
            missing_fields.append("metric_name")
        if not time_range and not time_info:
            missing_fields.append("time_range")
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

            # === 应用公式语法配置 ===
            last_message = state.messages[-1].content if state.messages else ""
            formula_config = self._match_formula_syntax(state.current_intent, last_message)
            if formula_config:
                adjusted_sql = self._apply_formula_syntax(adjusted_sql, formula_config, state.entities)

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
            # === 应用公式语法配置 ===
            last_message = state.messages[-1].content if state.messages else ""
            formula_config = self._match_formula_syntax(state.current_intent, last_message)
            if formula_config:
                adjusted_sql = self._apply_formula_syntax(adjusted_sql, formula_config, state.entities)
            return {
                "generated_sql": adjusted_sql,
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
                    # === 应用公式语法配置 ===
                    last_message = state.messages[-1].content if state.messages else ""
                    formula_config = self._match_formula_syntax(state.current_intent, last_message)
                    if formula_config:
                        adjusted_sql = self._apply_formula_syntax(adjusted_sql, formula_config, state.entities)
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
            # 【修复】早期返回前保存上下文，确保 dimension 等信息不丢失
            self._update_context(state, entities)
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

    def _sql_build_by_template(self, state: ConversationState) -> Dict[str, Any]:
        """
        SQL 构建节点 - 使用 SQL 模板引擎 (A/B Test)

        当 sql_mode == 'template' 时使用此方法:
        1. 直接使用 intent_node 识别到的 intent
        2. 调用 sql_template_engine 生成 SQL
        3. 替换占位符
        """
        try:
            from ai.sql_template_engine import generate_sql
        except ImportError:
            logger.warning("[_sql_build_by_template] sql_template_engine 未安装，降级到规则引擎")
            return {"generated_sql": None, "skip_execution": False}

        intent = getattr(state, 'current_intent', None)
        if not intent:
            logger.warning("[_sql_build_by_template] 未识别到意图，降级到规则引擎")
            return {"generated_sql": None, "skip_execution": False}

        # 非查询意图跳过
        non_query_intents = ["greeting", "thanks", "bye", "unknown"]
        if intent in non_query_intents:
            return {"skip_sql_generation": True, "generated_sql": None}

        # 构建 entities 上下文
        entities = state.entities or {}
        metric_code = entities.get("metric_code", "")
        metric_name = entities.get("metric_name", "")

        # 从 starrocks_sql 提取 field 和 table
        starrocks_sql = entities.get("starrocks_sql", "")
        field = "*"
        table = "metric_table"

        if starrocks_sql:
            import re
            # 提取 SELECT 字段
            select_match = re.search(r'SELECT\s+(.+?)\s+FROM\s+', starrocks_sql, re.IGNORECASE | re.DOTALL)
            if select_match:
                field = select_match.group(1).strip()
            # 提取表名
            table_match = re.search(r'FROM\s+([^\s;]+)', starrocks_sql, re.IGNORECASE)
            if table_match:
                table = table_match.group(1).strip()

        # 获取时间范围
        time_info = entities.get("time_info", {})
        start_date = time_info.get("start_date", "2026-01-01")
        end_date = time_info.get("end_date", "2026-04-12")

        # 构建上下文 - 传递 starrocks_sql 让 engine._build_context 重新解析
        # 同时传递已解析的 field/table 作为后备
        context = {
            "metric_code": metric_code,
            "starrocks_sql": starrocks_sql,  # 让 engine 重新解析
            "time_info": time_info,  # 传递完整 time_info
            "start_date": start_date,
            "end_date": end_date,
            "date_column": entities.get("date_column", "FDATE"),  # 日期列
            "dimension": entities.get("dimension"),  # 不设默认值，让 engine 处理
            "top_n": entities.get("top_n", "10")
        }

        # 下钻维度
        drill_dims = getattr(state, 'drill_down_dims', None)
        drill_dims_list = []
        if drill_dims and isinstance(drill_dims, list):
            drill_dims_list = [d.get("dim_name", "") for d in drill_dims if d.get("dim_name")]

        # 生成 SQL
        logger.info(f"[_sql_build_by_template] intent={intent}, metric={metric_name}({metric_code})")
        generated_sql = generate_sql(intent, context, drill_dims_list)

        if generated_sql:
            logger.info(f"[_sql_build_by_template] 模板生成SQL成功 (前100字符): {generated_sql[:100]}")

            # 记录思考步骤
            self._add_thinking_step(state, "SQL生成(模板)", "completed",
                f"使用SQL模板生成，指标: {metric_name or '未知指标'}")

            return {
                "generated_sql": generated_sql,
                "sql_params": {"metric_code": metric_code},
                "skip_execution": False,
                "sql_source": "template"  # 标记SQL来源
            }
        else:
            logger.warning(f"[_sql_build_by_template] 模板未匹配到 intent={intent}，降级到规则引擎")
            return {"generated_sql": None, "skip_execution": False}

    def sql_build_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        SQL 构建节点 - 使用 QueryBuilder 替代 _build_value_sql
        实现 LangGraph 多轮能力 + QueryBuilder 确定性 SQL

        流程:
        1. 从 entities 构建 QueryState
        2. 调用 QueryBuilder.build_sql()
        3. 后处理（SKU占位符移除等）
        """

        # ========== SQL 模板模式 (A/B Test) ==========
        sql_mode = getattr(state, 'sql_mode', 'llm')
        if sql_mode == 'template':
            return self._sql_build_by_template(state)

        metric_code = state.entities.get("metric_code")
        metric_id = state.entities.get("metric_id")
        metric_name = state.entities.get("metric_name")
        starrocks_sql = state.entities.get("starrocks_sql")
        starrocks_table = state.entities.get("starrocks_table")
        time_info = state.entities.get("time_info")  # 来自 TimeParser 的完整时间信息
        time_range = state.entities.get("time_range")
        dimension = state.entities.get("dimension")  # GROUP BY 维度

        # ========== QueryIntent 构建（Phase 1: 构建但不使用，保持向后兼容）==========
        query_intent = self._conversation_state_to_query_intent(state)
        logger.info(f"[sql_build_node] QueryIntent构建: intent_type={query_intent.intent_type}, metric_code={query_intent.metric_code}")

        # ========== 多指标支持 ==========
        multi_metrics = state.entities.get("metrics", [])
        if multi_metrics and len(multi_metrics) >= 2:
            logger.info(f"[sql_build_node] 检测到多指标查询: {[m.get('metric_name') for m in multi_metrics]}")
            # 多指标：需要合并多个 starrocks_sql 的 SELECT 列
            # 检查是否来自同一张表
            tables = set()
            all_select_parts = []  # [(alias, sql_fragment), ...]
            base_where = None

            for m in multi_metrics:
                m_sql = m.get("starrocks_sql", "")
                if not m_sql:
                    # 尝试从 metric_code 获取
                    try:
                        m_info = self.metric_client.get_metric_by_code(m.get("metric_code"))
                        if m_info:
                            m_sql = m_info.get("starrocks_sql", "")
                    except:
                        pass
                if m_sql:
                    # 解析 starrocks_sql 提取表名和 SELECT 部分
                    table_match = re.search(r'FROM\s+([^\s;]+)', m_sql, re.IGNORECASE)
                    if table_match:
                        tables.add(table_match.group(1).strip())
                    # 提取 SELECT 和 FROM 之间的内容
                    select_match = re.search(r'SELECT\s+(.+?)\s+FROM\s+', m_sql, re.IGNORECASE | re.DOTALL)
                    if select_match:
                        select_part = select_match.group(1).strip()
                        # 移除多余空白
                        select_part = re.sub(r'\s+', ' ', select_part)
                        all_select_parts.append((m.get('metric_name'), select_part, m_sql))
                    # 提取 WHERE 条件（假设相同）
                    where_match = re.search(r'WHERE\s+(.+?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s*$)', m_sql, re.IGNORECASE | re.DOTALL)
                    if where_match and not base_where:
                        base_where = where_match.group(1).strip()

            if len(tables) == 1 and len(all_select_parts) >= 2:
                # 同一张表，可以合并
                starrocks_table = list(tables)[0]
                # 合并 SELECT 部分，用中文 metric_name 作为别名
                combined_select = []
                for m_name, select_part, original_sql in all_select_parts:
                    # 提取原始的列表达式（如 SUM(col) 或 sum(col)）
                    col_match = re.search(r'(sum|avg|count|max|min)\s*\(\s*(\w+)\s*\)', select_part, re.IGNORECASE)
                    if col_match:
                        # 直接用中文名作为别名，替换整个表达式
                        new_select = f"{col_match.group(1)}({col_match.group(2)}) AS `{m_name}`"
                    else:
                        # 没有聚合函数，直接用 metric_name 作为别名
                        new_select = f"{select_part} AS `{m_name}`"
                    combined_select.append(new_select)
                starrocks_sql = f"SELECT {', '.join(combined_select)} FROM {starrocks_table}"
                if base_where:
                    starrocks_sql += f" WHERE {base_where}"
                logger.info(f"[sql_build_node] 多指标合并 SQL: {starrocks_sql[:200]}")
            else:
                # 不同表，降级到单指标（取第一个）
                logger.warning(f"[sql_build_node] 多指标来自不同表，降级到单指标: tables={tables}")
                multi_metrics = []

        logger.info(f"[sql_build_node] metric={metric_name}({metric_code}), time_info={time_info}, dimension={dimension}, starrocks_table={starrocks_table}")

        # 提取维度参数（用于验证）
        dimensions = self._extract_sql_dimensions(state.entities)

        # 如果没有 starrocks_sql 但有 metric_code，尝试获取
        if not starrocks_sql and metric_code:
            try:
                metric_info = self.metric_client.get_metric_by_code(metric_code)
                if metric_info:
                    starrocks_sql = metric_info.get("starrocks_sql", "")
                    starrocks_table = metric_info.get("starrocks_table", "")
                    logger.info(f"[sql_build_node] 从 metric_code 获取到 starrocks_sql: {repr(starrocks_sql)[:80] if starrocks_sql else 'None'}")
            except Exception as e:
                logger.warning(f"[sql_build_node] 获取 metric_info 失败: {e}")

        # 如果还是没有 starrocks_sql，降级到规则引擎
        if not starrocks_sql:
            logger.info("[sql_build_node] 无 starrocks_sql，降级到规则引擎")
            return self._build_value_sql(state)

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

        # 补充 metric 元数据（从 starrocks_sql 解析 table_name）
        if not starrocks_table and starrocks_sql:
            table_match = re.search(r'FROM\s+([^\s;]+)', starrocks_sql, re.IGNORECASE)
            if table_match:
                starrocks_table = table_match.group(1)

        # 构建 TimeSpec
        if time_info:
            time_spec = TimeSpec(
                type=time_info.get("type", "date_range"),
                start=time_info.get("start"),
                end=time_info.get("end"),
                original_expr=time_info.get("original_expr") or time_range
            )
        else:
            time_spec = TimeSpec(type="date_range", original_expr=time_range or "last_7_days")

        # 构建 dimensions（需要映射中文维度名到数据库列名）
        query_dimensions = []

        # 如果已有具体的维度值（如 GROUP_3=智能云存储），跳过泛指的 dimension GROUP BY
        # 避免同时出现 WHERE GROUP_3='智能云存储' 和 GROUP BY 品类
        # 但时间维度（日、月、年）不受此限制，即使有具体维度值也应该 GROUP BY
        time_dimensions = ['日', '月', '年', '天', '周']
        dimensions_list = state.entities.get("dimensions", [])  # 支持多维度
        logger.info(f"[sql_build_node] dimension={dimension}, dimensions_list={dimensions_list}, state.entities={state.entities}")

        # 确定要 GROUP BY 的维度列表
        dims_to_process = []
        if dimensions_list:
            # 使用 dimensions_list（支持多维度）
            dims_to_process = dimensions_list
        elif dimension:
            # 兼容单维度
            dims_to_process = [dimension]

        # 过滤掉已有具体值的非时间维度
        # 注意：__SYNONYM__ 是"识别了维度类型但无具体值"的标记，不是具体值
        filtered_dims = []
        specific_dim_keys = list(self._get_all_dimension_keys())
        for dim in dims_to_process:
            is_time_dim = dim in time_dimensions
            if not is_time_dim:
                has_specific_dim_value = any(
                    state.entities.get(k) and state.entities.get(k) != '__SYNONYM__'
                    for k in specific_dim_keys
                )
                if has_specific_dim_value:
                    logger.info(f"[sql_build_node] 已有具体维度值，跳过泛指的 dim={dim} GROUP BY")
                    continue
            filtered_dims.append(dim)

        # 处理每个维度
        dim_configs = None
        if filtered_dims and starrocks_table:
            dim_configs = self._get_table_dimensions_cached(starrocks_table)
            logger.info(f"[sql_build_node] dim_configs={dim_configs}, filtered_dims={filtered_dims}")

        for dim in filtered_dims:
            mapped_dim = dim
            # 模糊匹配：用户说"品类"应该匹配"三级品类"
            if dim_configs:
                matched_dim = None
                # 首先尝试直接匹配
                if dim in dim_configs:
                    matched_dim = dim
                else:
                    # 尝试别名映射
                    aliased_dim = self.BIZ_DIM_ALIASES.get(dim, dim)
                    if aliased_dim in dim_configs:
                        matched_dim = aliased_dim
                    else:
                        # 模糊匹配
                        candidates = [d for d in dim_configs if dim in d or d in dim]
                        if candidates:
                            matched_dim = max(candidates, key=len)  # 选最长的
                        if not matched_dim:
                            for d in dim_configs:
                                if d in dim:
                                    matched_dim = d
                                    break
                if matched_dim:
                    mapped_dim = dim_configs[matched_dim].get("column_name", matched_dim)
            logger.info(f"[sql_build_node] 添加 GROUP BY 维度: dim={dim} -> mapped_dim={mapped_dim}")
            query_dimensions.append(QueryDimension(
                type=dim,
                column=dim,
                field=mapped_dim,
                value=None
            ))

        # 动态检查 entities 中的具体维度值（WHERE 条件）
        # 从 dimension_configs 获取所有 column_name，遍历 state.entities 检查是否有匹配的 key
        # 如果 starrocks_table 为空但 starrocks_sql 非空，尝试从 SQL 提取表名
        table_for_dim = starrocks_table
        if not table_for_dim and starrocks_sql:
            from_match = re.search(r'FROM\s+([a-zA-Z0-9_.]+)', starrocks_sql, re.IGNORECASE)
            if from_match:
                table_for_dim = from_match.group(1).strip()
                logger.info(f"[sql_build_node] 从 starrocks_sql 提取表名: {table_for_dim}")

        logger.info(f"[sql_build_node] table_for_dim={table_for_dim}, starrocks_table={starrocks_table}")
        if table_for_dim:
            dim_configs = self._get_table_dimensions_cached(table_for_dim)
            all_columns = [cfg["column_name"] for cfg in dim_configs.values()]  # 动态获取
            logger.info(f"[sql_build_node] all_columns={all_columns}")
            logger.info(f"[sql_build_node] state.entities keys={list(state.entities.keys())}")

            for key, value in state.entities.items():
                # 跳过 __SYNONYM__ 占位符（识别了维度类型但无具体值，应该用于 GROUP BY 不是 WHERE）
                if key in all_columns and value and value != '__SYNONYM__':
                    # 这是一个具体的维度值，添加为 WHERE 条件
                    for dim_name, cfg in dim_configs.items():
                        if cfg["column_name"] == key:
                            query_dimensions.append(QueryDimension(
                                type=dim_name,
                                column=key,
                                field=key,
                                value=value
                            ))
                            logger.info(f"[sql_build_node] 添加维度值 WHERE 条件: {key}={value}")
                            break

        # 构建 QueryState
        query_state = QueryState(
            version="1.0",
            session_id=state.session_id,
            intent=state.current_intent or "query_value",
            confidence=0.9,
            metric={
                "code": metric_code or "",
                "name": metric_name or "",
                "starrocks_table": starrocks_table or "",
                "starrocks_sql": starrocks_sql or "",
            },
            time=time_spec,
            dimensions=query_dimensions,
            pagination=PaginationSpec(
                page=getattr(state, 'page', 1),
                page_size=min(state.entities.get("top_n") or getattr(state, 'page_size', 100), 1000)
            ),
            comparison=ComparisonSpec(
                enabled=state.current_intent in ["query_comparison", "query_trend"],
                types=["同比", "环比"] if state.current_intent == "query_comparison" else []
            )
        )

        # 调用 QueryBuilder
        builder = QueryBuilder()
        result = builder.build_sql(query_state)

        generated_sql = result.get("sql", "")
        thinking_steps = result.get("thinking_steps", [])

        # ========== Phase 2: QueryIntent 对比验证 ==========
        try:
            result_from_intent = builder.build_sql_from_intent(query_intent)
            sql_old = result.get("sql", "")
            sql_new = result_from_intent.get("sql", "")

            if sql_old != sql_new:
                logger.warning(f"[sql_build_node] QueryIntent对比: SQL不一致!")
                thinking_steps.append({
                    "step": "query_intent_compare",
                    "status": "warning",
                    "content": f"两种方式SQL不同: old={sql_old[:80] if sql_old else 'empty'}..., new={sql_new[:80] if sql_new else 'empty'}..."
                })
            else:
                logger.info(f"[sql_build_node] QueryIntent对比: SQL一致")
                thinking_steps.append({
                    "step": "query_intent_compare",
                    "status": "completed",
                    "content": "两种方式SQL输出一致"
                })
        except Exception as e:
            logger.warning(f"[sql_build_node] QueryIntent对比失败: {e}")
            thinking_steps.append({
                "step": "query_intent_compare",
                "status": "error",
                "content": f"QueryIntent对比异常: {str(e)[:100]}"
            })
        field_mapping = result.get("field_mapping", {})

        logger.info(f"[sql_build_node] field_mapping group_by_fields: {field_mapping.get('group_by_fields', [])}")
        logger.info(f"[sql_build_node] query_state.dimensions: {[(d.type, d.field, d.value) for d in query_state.dimensions]}")

        # 后处理：SKU 占位符移除
        sku_value = state.entities.get("sku")
        if not sku_value and generated_sql:
            generated_sql = re.sub(r'\s*AND\s+sku\s*=\s*[\'"]?\{?SKU\}?[\'"]?', '', generated_sql, flags=re.IGNORECASE)
            generated_sql = re.sub(r'\s*AND\s+sku\s*=\s*\$\{SKU\}', '', generated_sql, flags=re.IGNORECASE)
            generated_sql = generated_sql.rstrip()

        # 处理 ORDER BY（当有 top_n 排名需求时）
        top_n = state.entities.get("top_n")
        logger.info(f"[sql_build_node] DEBUG: top_n={top_n}, type={type(top_n)}, entities keys={list(state.entities.keys())}")
        if top_n and top_n > 0 and "ORDER BY" not in generated_sql.upper():
            # 获取指标列名（用于 ORDER BY）
            metric_col = "ORDERED_PRODUCTSALES"  # 默认指标列
            col_match = re.search(r'(sum|avg)\s*\(\s*(\w+)\s*\)', generated_sql, re.IGNORECASE)
            if col_match:
                metric_col = col_match.group(2)
            generated_sql = generated_sql.rstrip() + f" ORDER BY {metric_col} DESC"
            logger.info(f"[sql_build_node] 添加 ORDER BY {metric_col} DESC for top_n={top_n}")

        # === B方案：统一后处理 ===
        # 1. 维度后处理：多维度 GROUP BY + 列名映射
        if generated_sql:
            time_info = state.entities.get("time_info")
            dimensions_list = state.entities.get("dimensions", [])
            single_dimension = state.entities.get("dimension")
            table_name = self._extract_table_name(generated_sql)
            logger.info(f"[sql_build_node] B方案调试: generated_sql前='{generated_sql[:200]}', single_dimension={single_dimension}, dimensions_list={dimensions_list}")

            adjusted = self._apply_dimensions_to_sql(
                generated_sql,
                dimensions={},
                entities={
                    "dimensions": dimensions_list,
                    "dimension": single_dimension,
                    "top_n": state.entities.get("top_n")
                },
                time_info=time_info
            )
            logger.info(f"[sql_build_node] B方案调试: adjusted后='{adjusted[:200] if adjusted else None}'")
            if adjusted and adjusted != generated_sql:
                logger.info(f"[sql_build_node] 维度后处理完成，SQL: {adjusted[:200]}...")
                generated_sql = adjusted

        # 2. 公式语法匹配和应用
        last_message = state.messages[-1].content if state.messages else ""
        formula_config = self._match_formula_syntax(state.current_intent, last_message)
        if formula_config:
            generated_sql = self._apply_formula_syntax(generated_sql, formula_config, state.entities)
            self._add_thinking_step(state, "formula_syntax", "completed",
                f"应用公式语法: {formula_config.get('name', 'unknown')}")
            logger.info(f"[sql_build_node] 应用公式语法: {formula_config.get('name')}, SQL: {generated_sql[:200]}...")

        # 记录思考步骤
        for step in thinking_steps:
            self._add_thinking_step(state, step.get("step", ""), step.get("status", "completed"), step.get("detail", ""))

        # 记录 SQL 生成步骤
        self._add_thinking_step(state, "sql_gen", "completed",
            f"使用 QueryBuilder 生成 SQL，指标：{metric_name or '未知指标'}")

        # === SQL 校验 ===
        verify_result = self._sql_verify(generated_sql)
        if not verify_result["valid"]:
            logger.warning(f"[sql_build_node] SQL校验失败: {verify_result['error']}, SQL: {generated_sql[:200] if generated_sql else 'empty'}")
            self._add_thinking_step(state, "sql_verify", "failed", verify_result["error"])
            return {
                "generated_sql": generated_sql,
                "sql_params": {"metric_id": metric_id, "metric_code": metric_code},
                "needs_clarification": True,
                "clarification_type": "invalid_sql",
                "clarification_message": f"生成的SQL有问题: {verify_result['error']}",
                "thinking_steps": thinking_steps,
            }
        self._add_thinking_step(state, "sql_verify", "passed", "SQL校验通过")

        # 记录格式化后的 SQL（便于阅读）
        formatted_sql = self._format_sql_for_display(generated_sql)
        self._add_thinking_step(state, "generated_sql", "completed", formatted_sql)

        # 【防御性修复】最终检查：如果 generated_sql 仍然包含无效的 dimension（如"店铺退款数量在销量中"），清理它
        invalid_dim_in_sql = "店铺退款数量在销量中"
        if invalid_dim_in_sql in generated_sql:
            logger.warning(f"[sql_build_node] 清理SQL中的无效dimension: {invalid_dim_in_sql}")
            # 使用简单字符串操作清理，避免正则转义问题
            # 移除 "店铺退款数量在销量中" 以及它前面可能的逗号和空格
            generated_sql = generated_sql.replace(f", `{invalid_dim_in_sql}`", "")
            generated_sql = generated_sql.replace(f"`{invalid_dim_in_sql}`,", "")
            generated_sql = generated_sql.replace(f"`{invalid_dim_in_sql}`", "")
            generated_sql = generated_sql.replace(f", {invalid_dim_in_sql}", "")
            generated_sql = generated_sql.replace(f"{invalid_dim_in_sql},", "")
            generated_sql = generated_sql.replace(invalid_dim_in_sql, "")
            generated_sql = generated_sql.strip()
            # 修复可能的语法错误（移除多余的逗号）
            generated_sql = re.sub(r'SELECT\s+,', 'SELECT ', generated_sql, flags=re.IGNORECASE)
            generated_sql = re.sub(r',\s*GROUP BY', ' GROUP BY', generated_sql, flags=re.IGNORECASE)
            generated_sql = re.sub(r',\s*LIMIT', ' LIMIT', generated_sql, flags=re.IGNORECASE)
            generated_sql = re.sub(r',\s*$', '', generated_sql)  # 移除末尾逗号

        return {
            "generated_sql": generated_sql,
            "sql_params": {"metric_id": metric_id, "metric_code": metric_code},
            "needs_clarification": False,
            "thinking_steps": thinking_steps,
        }

    def _sql_verify(self, sql: str) -> Dict[str, Any]:
        """SQL校验，确保生成的SQL安全且合理

        返回: {"valid": bool, "error": str}
        """
        if not sql or not sql.strip():
            return {"valid": False, "error": "SQL为空"}

        sql_upper = sql.upper()

        # 1. 注入检测
        dangerous_keywords = ['DELETE', 'DROP', 'TRUNCATE', 'ALTER', 'INSERT', 'UPDATE', 'EXEC', 'EXECUTE']
        for kw in dangerous_keywords:
            if kw in sql_upper:
                return {"valid": False, "error": f"危险关键字: {kw}"}

        # 2. 基本语法检查
        if 'SELECT' not in sql_upper:
            return {"valid": False, "error": "缺少 SELECT 关键字"}
        if 'FROM' not in sql_upper:
            return {"valid": False, "error": "缺少 FROM 关键字"}

        # 3. GROUP BY 语法检查 - GROUP BY 后面应该是列名或列别名，不应该有复杂表达式
        # 如果 GROUP BY 后面包含函数调用或运算符，可能是公式语法拼错了
        group_by_match = re.search(r'GROUP\s+BY\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|\s+;|$)', sql_upper)
        if group_by_match:
            group_by_clause = group_by_match.group(1).strip()
            # 检查是否包含不应该在 GROUP BY 中的内容
            invalid_patterns = [
                r'\(',           # 函数调用，如 SUM(col)
                r'\+.*\+',       # 运算符，如 col1 + col2
                r'-.*-',         # 减法
                r'\*.*\*',       # 乘法
                r'\/.*\/',       # 除法
                r'DISTINCT',     # DISTINCT 不应该在 GROUP BY 中
            ]
            for pattern in invalid_patterns:
                if re.search(pattern, group_by_clause):
                    return {"valid": False, "error": f"GROUP BY 子句异常: 可能包含非列名内容"}

        # 4. ORDER BY 语法检查 - ORDER BY 后面应该是列名或列别名，不应该有复杂表达式
        order_by_match = re.search(r'ORDER\s+BY\s+(.+?)(?:\s+LIMIT|\s+;|$)', sql_upper)
        if order_by_match:
            order_by_clause = order_by_match.group(1).strip()
            invalid_patterns = [
                r'\(',           # 函数调用
                r'[+\-*/].*[+\-*/]',  # 运算符
            ]
            for pattern in invalid_patterns:
                if re.search(pattern, order_by_clause):
                    return {"valid": False, "error": f"ORDER BY 子句异常: 可能包含非列名内容"}

        # 5. 时间范围合理性检查
        fdate_matches = re.findall(r"FDATE\s*>=?\s*'?(\d{4}-\d{2}-\d{2})'?", sql)
        if fdate_matches:
            try:
                from datetime import datetime
                dates = [datetime.strptime(d, '%Y-%m-%d') for d in fdate_matches]
                if dates:
                    date_range_days = (max(dates) - min(dates)).days
                    if date_range_days > 730:  # 超过2年
                        return {"valid": False, "error": f"时间范围超过2年: {date_range_days}天"}
            except Exception:
                pass  # 日期解析失败不阻挡，继续其他检查

        return {"valid": True, "error": ""}

    def _format_sql_for_display(self, sql: str) -> str:
        """格式化 SQL 为易读形式（添加换行和缩进）"""
        if not sql:
            return ""

        # 按关键字换行
        sql = re.sub(r'\s+', ' ', sql).strip()  # 先合并多余空格

        # 在主要关键字前添加换行
        formatted = sql
        for keyword in ['SELECT ', 'FROM ', 'WHERE ', 'GROUP BY ', 'ORDER BY ', 'HAVING ', 'LIMIT ', 'AND ', 'OR ']:
            formatted = formatted.replace(keyword, '\n' + keyword)

        # 缩进（第一行不加缩进，后续行加缩进）
        lines = formatted.split('\n')
        result_lines = []
        for i, line in enumerate(lines):
            if i == 0:
                result_lines.append(line.strip())
            else:
                result_lines.append('  ' + line.strip())

        return '\n'.join(result_lines)

    # 维度配置缓存（避免每次查询都调 API）
    _table_dimensions_cache: Dict[str, Dict[str, Dict]] = {}

    # 公式语法配置缓存
    _formula_syntax_cache: List[Dict[str, Any]] = []
    _formula_syntax_loaded: bool = False

    def _get_formula_syntax_configs(self) -> List[Dict[str, Any]]:
        """获取公式语法配置，带缓存"""
        if self._formula_syntax_loaded:
            logger.info(f"[_get_formula_syntax_configs] 使用缓存, count={len(self._formula_syntax_cache)}")
            return self._formula_syntax_cache
        try:
            configs = self.metric_client.get_formula_syntax_configs()
            self._formula_syntax_cache = configs
            self._formula_syntax_loaded = True
            logger.info(f"[_get_formula_syntax_configs] 首次加载成功, count={len(configs)}")
        except Exception as e:
            logger.warning(f"获取公式语法配置失败: {e}")
            self._formula_syntax_cache = []
            self._formula_syntax_loaded = True
        return self._formula_syntax_cache

    def _conversation_state_to_query_intent(self, state: ConversationState) -> QueryIntent:
        """
        将 ConversationState 转换为 QueryIntent

        这是从 entities dict 到结构化 QueryIntent 的转换。
        目的是：
        1. 让 SQL 构建的输入更清晰
        2. 为后续 LLM 生成 QueryIntent 打基础

        Args:
            state: 对话状态

        Returns:
            QueryIntent 结构化的查询意图
        """
        entities = state.entities

        # 1. 解析意图类型
        intent_type = state.current_intent or "query_value"

        # 2. 提取时间维度
        time_info = entities.get("time_info", {})
        time_range = None
        if time_info:
            time_range = {
                "start": time_info.get("start"),
                "end": time_info.get("end")
            }

        # 3. 提取分组维度
        dimensions_list = entities.get("dimensions", [])
        single_dimension = entities.get("dimension")
        group_by_dims = dimensions_list if dimensions_list else ([single_dimension] if single_dimension else [])

        # 【修复】将中文维度名映射为数据库列名（如"站点"→"FSITECODE"）
        if group_by_dims:
            # 获取 starrocks_table
            starrocks_table = entities.get("starrocks_table")
            if not starrocks_table:
                starrocks_sql = entities.get("starrocks_sql", "")
                from_match = re.search(r'FROM\s+([a-zA-Z0-9_.]+)', starrocks_sql, re.IGNORECASE)
                if from_match:
                    starrocks_table = from_match.group(1).strip()

            # 获取维度配置映射，将中文维度名转为列名
            if starrocks_table:
                dim_configs = self._get_table_dimensions_cached(starrocks_table)
                if dim_configs:
                    mapped_dims = []
                    for dim in group_by_dims:
                        if dim in dim_configs:
                            mapped_dims.append(dim_configs[dim].get("column_name", dim))
                        else:
                            mapped_dims.append(dim)
                    group_by_dims = mapped_dims

        # 4. 提取过滤条件（使用动态维度字段）
        filters = []
        all_dim_keys = self._get_all_dimension_keys()
        for key in all_dim_keys:
            if entities.get(key):
                filters.append({
                    "field": key,
                    "operator": "=",
                    "value": entities.get(key)
                })

        # 5. 提取对比配置
        comparison_enabled = intent_type in ["query_comparison", "query_trend"]
        comparison_types = ["同比", "环比"] if intent_type == "query_comparison" else []

        return QueryIntent(
            intent_type=intent_type,
            metric_code=entities.get("metric_code"),
            metric_name=entities.get("metric_name"),
            metric_id=entities.get("metric_id"),
            aggregation=None,  # 可从 starrocks_sql 解析
            time_dimension=entities.get("time_dimension"),
            time_range=time_range,
            time_expr=entities.get("time_range"),
            group_by_dims=group_by_dims,
            filters=filters,
            comparison_enabled=comparison_enabled,
            comparison_types=comparison_types,
            top_n=entities.get("top_n"),
            multi_metrics=entities.get("metrics", []),
            raw_starrocks_sql=entities.get("starrocks_sql"),
            raw_starrocks_table=entities.get("starrocks_table"),
            raw_entities=entities,  # 保留原始 entities 用于调试
        )

    def _match_formula_syntax(self, intent: str, text: str) -> Optional[Dict[str, Any]]:
        """根据用户输入文本匹配公式语法配置（不限制 intent_type）"""
        configs = self._get_formula_syntax_configs()
        if not configs:
            return None

        import re
        text_lower = text.lower()
        best_match = None
        best_priority = -1

        for cfg in configs:
            keywords = cfg.get("keywords", "")
            if not keywords:
                continue
            # 检查关键词是否在用户输入中（整词匹配，支持中文）
            keyword_list = [k.strip() for k in keywords.split(",")]
            for kw in keyword_list:
                if not kw:
                    continue
                kw_lower = kw.lower()
                # 整词匹配：关键词必须是独立的词（用 \b 边界，中文按字符边界处理）
                # 使用 (?<!\w) 和 (?!\w) 确保不是其他词的子串
                pattern = re.compile(rf'(?<!\w){re.escape(kw_lower)}(?!\w)', re.UNICODE)
                if pattern.search(text_lower):
                    priority = cfg.get("priority", 0)
                    # 优先匹配优先级高的配置
                    if priority > best_priority:
                        best_match = cfg
                        best_priority = priority
                    break
        return best_match

    def _apply_formula_syntax(self, sql: str, config: Dict[str, Any], entities: Dict[str, Any]) -> str:
        """将公式语法配置应用到 SQL"""
        if not sql or not config:
            return sql

        pattern = config.get("sql_pattern", "")
        if not pattern:
            return sql

        # 替换占位符
        result_sql = pattern

        # {metric} -> 指标列名
        metric_col = "value"  # 默认指标列
        col_match = re.search(r'(sum|avg)\s*\(\s*(\w+)\s*\)', sql, re.IGNORECASE)
        if col_match:
            metric_col = col_match.group(2)
        result_sql = result_sql.replace("{metric}", metric_col)
        logger.info(f"[_apply_formula_syntax] metric_col={metric_col}, result_sql={result_sql}, original_sql={sql[:200]}")

        # {n} -> top_n 值（默认10）
        top_n = entities.get("top_n")
        if top_n:
            result_sql = result_sql.replace("{n}", str(top_n))
        else:
            # 默认返回前10名
            result_sql = result_sql.replace("{n}", "10")

        # {molecule_col} 和 {denominator_col} -> 占比公式的分子/分母列名
        if '{molecule_col}' in result_sql and '{denominator_col}' in result_sql:
            molecule_info = entities.get('molecule_metric_info', {})
            denominator_info = entities.get('denominator_metric_info', {})

            # 从 molecule_metric_info 提取列名
            molecule_col = "molecule_value"
            if molecule_info:
                starrocks_sql = molecule_info.get('starrocks_sql', '')
                if starrocks_sql:
                    col_match = re.search(r'(sum|avg|count|min|max)\s*\(\s*(\w+)\s*\)', starrocks_sql, re.IGNORECASE)
                    if col_match:
                        molecule_col = col_match.group(2)
                    else:
                        # 没有聚合函数，尝试直接提取列名
                        select_match = re.search(r'select\s+.+?\s+from', starrocks_sql, re.IGNORECASE)
                        if select_match:
                            molecule_col = select_match.group(0).replace('select', '').replace('from', '').strip().split(',')[0].strip()
                if not molecule_col or molecule_col == 'molecule_value':
                    molecule_col = molecule_info.get('metric_name', 'molecule_value')

            # 从 denominator_metric_info 提取列名
            denominator_col = "denominator_value"
            if denominator_info:
                starrocks_sql = denominator_info.get('starrocks_sql', '')
                if starrocks_sql:
                    col_match = re.search(r'(sum|avg|count|min|max)\s*\(\s*(\w+)\s*\)', starrocks_sql, re.IGNORECASE)
                    if col_match:
                        denominator_col = col_match.group(2)
                    else:
                        select_match = re.search(r'select\s+.+?\s+from', starrocks_sql, re.IGNORECASE)
                        if select_match:
                            denominator_col = select_match.group(0).replace('select', '').replace('from', '').strip().split(',')[0].strip()
                if not denominator_col or denominator_col == 'denominator_value':
                    denominator_col = denominator_info.get('metric_name', 'denominator_value')

            result_sql = result_sql.replace("{molecule_col}", molecule_col)
            result_sql = result_sql.replace("{denominator_col}", denominator_col)
            logger.info(f"[_apply_formula_syntax] 占比公式: molecule_col={molecule_col}, denominator_col={denominator_col}")

        # 清理其他未替换的占位符
        result_sql = re.sub(r'\{[^}]+\}', '', result_sql)

        # === 检查公式是否包含聚合函数（AVG/SUM/COUNT等）===
        formula_has_agg = re.search(r'(sum|avg|count|min|max)\s*\(', result_sql, re.IGNORECASE)
        formula_agg_func = formula_has_agg.group(1).upper() if formula_has_agg else None

        # === 避免重复追加 ORDER BY/LIMIT ===
        # 如果 SQL 已经包含 ORDER BY，不重复追加 ORDER BY 部分
        if "ORDER BY" in sql.upper():
            # 去掉 pattern 中的 ORDER BY 部分（如果 pattern 包含的话）
            result_sql = re.sub(r'ORDER\s+BY\s+[^\s]+\s+(ASC|DESC)?\s*', '', result_sql, flags=re.IGNORECASE).strip()

        # 如果 SQL 已经包含 LIMIT，用公式的 LIMIT 替换（排名公式需要正确的 LIMIT 值）
        if "LIMIT" in sql.upper():
            # 检查公式 pattern 是否有 LIMIT
            formula_limit_match = re.search(r'LIMIT\s+(\d+)', result_sql, re.IGNORECASE)
            if formula_limit_match:
                # 提取公式的 LIMIT 值
                formula_limit = formula_limit_match.group(1)

                # 检查原 SQL 是否有 OFFSET（如果有，需要处理顺序问题）
                has_offset = "OFFSET" in sql.upper()
                has_order_by = "ORDER BY" in sql.upper()

                # 重新排列 SQL 语法的顺序：正确顺序应该是 GROUP BY ... ORDER BY ... LIMIT n OFFSET m
                # 而错误的顺序是 GROUP BY ... LIMIT n OFFSET m ORDER BY ...
                if has_offset and has_order_by:
                    # 原 SQL 是 LIMIT...OFFSET...ORDER BY，需要重新排列
                    # 1. 提取 ORDER BY 子句
                    order_by_match = re.search(r'ORDER\s+BY\s+.+?(?=\s*(?:GROUP\s+BY|LIMIT|WHERE|$))', sql, re.IGNORECASE | re.DOTALL)
                    order_by_clause = order_by_match.group(0).strip() if order_by_match else None

                    # 2. 提取 LIMIT...OFFSET
                    limit_offset_match = re.search(r'LIMIT\s+\d+\s+OFFSET\s+\d+', sql, re.IGNORECASE)
                    limit_offset_clause = limit_offset_match.group(0).strip() if limit_offset_match else None

                    if order_by_clause and limit_offset_clause:
                        # 重新组装：GROUP BY ... ORDER BY ... LIMIT n (不带 OFFSET)
                        sql = sql.replace(order_by_clause, "").replace(limit_offset_clause, "").strip()
                        # 去掉末尾可能的 AND
                        sql = re.sub(r'\s+AND\s+$', '', sql, flags=re.IGNORECASE).strip()
                        sql = f"{sql} {order_by_clause} LIMIT {formula_limit}"
                        logger.info(f"[_apply_formula_syntax] 重新排列 SQL 语序: {sql[:200]}")
                    else:
                        # 只替换 LIMIT 值
                        sql = re.sub(r'LIMIT\s+\d+', f'LIMIT {formula_limit}', sql, flags=re.IGNORECASE)
                else:
                    # 简单替换 LIMIT 值
                    sql = re.sub(r'LIMIT\s+\d+', f'LIMIT {formula_limit}', sql, flags=re.IGNORECASE)

                logger.info(f"[_apply_formula_syntax] 排名公式替换 LIMIT 为 {formula_limit}")
                # 公式的 LIMIT 已处理完毕，不需要再追加
                result_sql = re.sub(r'LIMIT\s+\d+', '', result_sql, flags=re.IGNORECASE).strip()
            else:
                # 公式没有 LIMIT，保留原 SQL 的 LIMIT
                result_sql = re.sub(r'LIMIT\s+\d+', '', result_sql, flags=re.IGNORECASE).strip()

        # 如果处理后 result_sql 为空，直接返回原始 SQL
        if not result_sql.strip():
            logger.info(f"[_apply_formula_syntax] SQL已包含ORDER BY/LIMIT，跳过追加")
            return sql

        # 将公式语法插入到 SELECT 子句，而不是追加到 SQL 末尾
        # 在 SELECT ... FROM 之间插入公式作为新列
        select_pattern = r'(SELECT\s+)(.*?)(\s+FROM\s+)'
        select_match = re.search(select_pattern, sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            # 如果公式包含聚合函数，需要替换原始聚合，而不是追加
            if formula_agg_func:
                # 找到原始的聚合函数（如 SUM(col) AS alias）并替换
                original_agg_pattern = r'(SUM|AVG|COUNT|MIN|MAX)\s*\(\s*' + re.escape(metric_col) + r'\s*\)(\s+AS\s+`?' + re.escape(metric_col) + r'`?)?'
                if re.search(original_agg_pattern, sql, re.IGNORECASE):
                    # 替换原始聚合为公式
                    sql = re.sub(
                        original_agg_pattern,
                        result_sql,
                        sql,
                        flags=re.IGNORECASE
                    )
                    logger.info(f"[_apply_formula_syntax] 替换原始聚合: {config.get('name')}, SQL: {sql}")
                else:
                    # 追加公式到 SELECT
                    sql = re.sub(
                        select_pattern,
                        r'\1\2, ' + result_sql + r' \3',
                        sql,
                        flags=re.IGNORECASE | re.DOTALL
                    )
                    logger.info(f"[_apply_formula_syntax] 追加公式到SELECT: {config.get('name')}, SQL: {sql}")
            else:
                # 在 FROM 前插入公式列
                sql = re.sub(
                    select_pattern,
                    r'\1\2, ' + result_sql + r' \3',
                    sql,
                    flags=re.IGNORECASE | re.DOTALL
                )
                logger.info(f"[_apply_formula_syntax] 应用公式语法到SELECT: {config.get('name')}, SQL: {sql}")
        else:
            # Fallback: 追加到末尾
            sql = sql.rstrip().rstrip(";") + " " + result_sql
            logger.info(f"[_apply_formula_syntax] 应用公式语法(append): {config.get('name')}, SQL: {sql}")

        # === 修复：将 GROUP BY 列添加到 SELECT ===
        group_cols = []
        group_match = re.search(r'GROUP\s+BY\s+([\w,\s]+?)(?=\s*(?:ORDER|GROUP|LIMIT|$))', sql, re.IGNORECASE)
        if group_match:
            group_by_clause = group_match.group(1)
            for col in group_by_clause.split(','):
                col = col.strip()
                if col:
                    group_cols.append(col)

        if group_cols:
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_clause = select_match.group(1)
                cols_to_add = []
                for col in group_cols:
                    if col.upper() not in select_clause.upper():
                        cols_to_add.append(col)
                if cols_to_add:
                    sql = re.sub(
                        r'(SELECT\s+)(.*?)(\s+FROM)',
                        r'\1' + ', '.join(cols_to_add) + r', \2\3',
                        sql,
                        flags=re.IGNORECASE | re.DOTALL
                    )
                    logger.info(f"[_apply_formula_syntax] 添加GROUP BY列到SELECT: {cols_to_add}")

        return sql

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

    def _get_all_dimension_keys(self) -> set:
        """
        从 business_terms 和 _dimension_cache 动态获取所有维度字段
        用于替代写死的维度列表
        """
        dim_keys = set()
        # 从 business_terms 获取 dimension_field、synonyms 及其大小写变体
        if hasattr(self.rule_engine, 'business_terms'):
            for term_key, term_info in self.rule_engine.business_terms.items():
                dim_field = term_info.get("dimension_field")
                if dim_field:
                    dim_keys.add(dim_field)
                    dim_keys.add(dim_field.upper())
                    dim_keys.add(dim_field.lower())
                # 添加 synonyms
                synonyms = term_info.get("synonyms", [])
                for syn in synonyms:
                    if syn:
                        dim_keys.add(syn)
                        dim_keys.add(syn.upper())
                        dim_keys.add(syn.lower())
        # 从 _dimension_cache 获取所有维度列名
        if hasattr(self.rule_engine, '_dimension_cache'):
            for dim_name, dim_mapping in self.rule_engine._dimension_cache.items():
                for col_name in dim_mapping.values():
                    if col_name:
                        dim_keys.add(col_name)
                        dim_keys.add(col_name.upper())
                        dim_keys.add(col_name.lower())
        return dim_keys

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

        # 动态获取所有维度字段，从 entities 中提取有值的维度
        all_dim_keys = self._get_all_dimension_keys()
        for dim_key in all_dim_keys:
            if entities.get(dim_key):
                dimensions[dim_key] = entities.get(dim_key)

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
        # 时间维度跳过验证
        time_dims = ['日', '月', '年', '天', '周']
        # 从动态维度字段获取品类维度，跳过验证
        skip_validation_keys = set(self._get_all_dimension_keys())
        skip_validation_keys.update(time_dims)

        for dim_key, dim_value in dimensions.items():
            # 跳过时间维度和品类维度
            if dim_key in skip_validation_keys:
                continue
            if not self._is_dimension_registered(dim_key, dim_value):
                invalid_dims.append(f"{dim_key}={dim_value}")

        if invalid_dims:
            return False, f"抱歉，暂时没有配置这些维度：{', '.join(invalid_dims)}"
        return True, None

    def _is_dimension_name_registered(self, dim_name: str, table_name: str = None) -> bool:
        """
        检查维度名是否在 dimension_configs 表中注册
        dim_name: 维度名称（如"店铺"、"站点"、"品类"、"三级品类"）
        返回: True=已注册，False=未注册
        """
        try:
            dim_configs = self.metric_client.get_dimension_configs(table_name)
            # 检查是否在 dimension_name 中（精确匹配）
            for cfg in dim_configs:
                if cfg.get("dimension_name") == dim_name and cfg.get("status") == 1:
                    return True
            # 检查别名映射（BIZ_DIM_ALIASES）
            aliased_name = self.BIZ_DIM_ALIASES.get(dim_name, dim_name)
            if aliased_name != dim_name:
                for cfg in dim_configs:
                    if cfg.get("dimension_name") == aliased_name and cfg.get("status") == 1:
                        return True
            return False
        except Exception as e:
            logger.warning(f"[_is_dimension_name_registered] 检查维度失败: {e}")
            return True  # 检查失败时放行，避免阻断用户

    def _is_dimension_registered(self, dim_type: str, dim_value: str) -> bool:
        """检查维度值是否在 dimensions 表配置中注册"""
        dim_map = self.rule_engine._get_dimension_mapping(dim_type)
        return dim_value in dim_map.values() or dim_value in dim_map.keys()

    def _find_matching_dimension(self, dim: str, dim_configs: Dict[str, Any]) -> Optional[str]:
        """从 dim_configs 中查找匹配的维度列名"""
        if not dim_configs:
            return dim
        # dim_configs 可能是 Dict 或 List[Dict]
        # 如果是 Dict（来自 _get_table_dimensions_cached），key 是 dimension_name
        # 如果是 List[Dict]（来自 get_dimension_configs），需要先转换
        if isinstance(dim_configs, list):
            # List[Dict] 格式：转换为 Dict
            cfg_dict = {cfg.get("dimension_name", ""): cfg for cfg in dim_configs if cfg.get("dimension_name")}
        else:
            # Dict 格式：直接使用
            cfg_dict = dim_configs

        # 精确匹配
        if dim in cfg_dict:
            return cfg_dict[dim].get("column_name", dim) if isinstance(cfg_dict[dim], dict) else cfg_dict[dim]
        # 别名映射
        aliased_dim = self.BIZ_DIM_ALIASES.get(dim, dim)
        if aliased_dim in cfg_dict:
            return cfg_dict[aliased_dim].get("column_name", aliased_dim) if isinstance(cfg_dict[aliased_dim], dict) else cfg_dict[aliased_dim]
        return dim  # 找不到就返回原始维度名

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

        # 【防御性修复】过滤无效的 dimension（如果 entities 传入了无效 dimension，直接清除）
        # 无效 dimension 包括：包含比率关键词、过长、包含排序关键词等
        invalid_dim_patterns = [
            r'占比', r'比例', r'比率', r'中的', r'之中的',  # 比率表达
            r'降序', r'升序', r'排序', r'排列',            # 排序关键词
            r'^按.*$',                                     # 以"按"开头的表达
        ]
        dim_to_check = entities.get("dimension")
        if dim_to_check:
            is_invalid = any(re.search(p, dim_to_check) for p in invalid_dim_patterns)
            if is_invalid:
                logger.info(f"[_apply_dimensions_to_sql] 清除无效dimension: {dim_to_check}")
                # 清除 entities 中的无效 dimension，防止后续逻辑使用
                entities.pop("dimension", None)
                entities.pop("dimensions", None)
                dim_to_check = None

        # === 0. 防御性修复：检测并修复 "LIMIT ... GROUP BY" 这种错误顺序 ===
        # 有时 build_sql_from_intent 会生成 "LIMIT 10 OFFSET 0 GROUP BY GROUP_3" 这种错误顺序
        # GROUP BY 应该在 LIMIT 之前，需要修复
        logger.info(f"[_apply_dimensions_to_sql] 入口SQL: {repr(adjusted_sql)[:250]}")
        limit_group_by_match = re.search(r'(.*?)(\s+LIMIT\s+\d+\s+OFFSET\s+\d+)\s+GROUP\s+BY\s+(.+?)$', adjusted_sql, re.IGNORECASE | re.DOTALL)
        if limit_group_by_match:
            logger.info(f"[_apply_dimensions_to_sql] 检测到错误的 LIMIT...GROUP BY 顺序，修复中")
            sql_before_limit = limit_group_by_match.group(1).rstrip()
            limit_clause = limit_group_by_match.group(2).strip()
            group_by_cols = limit_group_by_match.group(3).strip()
            # 修复：将 GROUP BY 移到 LIMIT 之前
            adjusted_sql = f"{sql_before_limit} GROUP BY {group_by_cols} {limit_clause}"
            logger.info(f"[_apply_dimensions_to_sql] 修复后SQL: {adjusted_sql[:200]}")

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

                    # 检查时间条件是否已存在于 WHERE 子句中
                    if time_cond in adjusted_sql:
                        logger.info(f"[_apply_dimensions_to_sql] 时间条件已存在于 WHERE，跳过: {time_cond}")
                    elif "WHERE" in adjusted_sql.upper():
                        # 找到 WHERE 子句的位置，在 GROUP BY/LIMIT/ORDER 之前插入
                        # 使用正则找到 WHERE 后的第一个 GROUP BY/LIMIT/ORDER/EOF
                        where_match = re.search(r'WHERE\s+(.+?)(?=\s*(?:GROUP\s+BY|ORDER\s+BY|LIMIT|$))', adjusted_sql, re.IGNORECASE | re.DOTALL)
                        if where_match:
                            # 在 WHERE 条件后、GROUP BY 之前插入
                            existing_where = where_match.group(1).strip()
                            insert_pos = where_match.end()
                            adjusted_sql = adjusted_sql[:insert_pos] + f" AND {time_cond}" + adjusted_sql[insert_pos:]
                        else:
                            # 兜底：直接追加（不应该走到这里）
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

        # === 2. 处理动态维度 (GROUP BY) - 支持多维度 ===
        # 获取维度列表（兼容单维度和多维度）
        dimensions_list = entities.get("dimensions", [])
        if table_name:
            dim_configs = self._get_table_dimensions_cached(table_name)
        else:
            dim_configs = {}
        single_dimension = entities.get("dimension")
        if not dimensions_list and single_dimension:
            dimensions_list = [single_dimension]

        time_dimension_keys = ["日", "月", "年", "day", "month", "year"]

        # === 收集所有需要 GROUP BY 的列 ===
        group_by_cols = []

        # 2.1 处理时间维度
        for dim in dimensions_list:
            if dim in time_dimension_keys:
                dim_key = "日" if dim in ["日", "day"] else "月" if dim in ["月", "month"] else "年"
                if table_name:
                    col = dim_configs.get(dim_key, {}).get("column_name", dim_key.upper())
                else:
                    col = dim_key.upper()
                if col and col.upper() not in [c.upper() for c in group_by_cols]:
                    group_by_cols.append(col)

        # 2.2 处理业务维度（平台、店铺、部门、渠道等）
        for dim in dimensions_list:
            if dim not in time_dimension_keys:
                matched_col = self._find_matching_dimension(dim, dim_configs) if dim_configs else dim
                if matched_col and matched_col.upper() not in [c.upper() for c in group_by_cols]:
                    group_by_cols.append(matched_col)

        # === 修正已有的 GROUP BY 列名 ===
        # 例如 starrocks_sql 中有 "GROUP BY 日"，需要替换为 "FDATE"
        # 注意：只有当 GROUP BY 包含中文维度名时才需要替换
        # 如果已经是英文列名（如 MONTHS），不需要替换
        for time_key in time_dimension_keys:
            # 只匹配中文维度名，不匹配英文
            if time_key in ["day", "month", "year"]:
                continue  # 跳过英文，直接用英文列名
            pattern = rf'GROUP\s+BY\s+[`]?{time_key}[`]?(?:\s*,|\s+|$)'
            if re.search(pattern, adjusted_sql, re.IGNORECASE):
                dim_key = "日" if time_key in ["日", "day"] else "月" if time_key in ["月", "month"] else "年"
                col = dim_configs.get(dim_key, {}).get("column_name", dim_key.upper()) if dim_configs else dim_key.upper()
                adjusted_sql = re.sub(pattern, f'GROUP BY {col}', adjusted_sql, flags=re.IGNORECASE)

        # === 追加缺失的 GROUP BY 列 ===
        if group_by_cols:
            # 先找出现有的 GROUP BY 子句及其所有列
            group_by_match = re.search(r'GROUP\s+BY\s+(.+?)(?=\s*(?:ORDER|LIMIT|WHERE|$))', adjusted_sql, re.IGNORECASE | re.DOTALL)
            if group_by_match:
                # 提取现有 GROUP BY 的列（可能包含 AND 条件，需要分离）
                group_by_content = group_by_match.group(1).strip()
                # 分割出列名部分（去掉可能的 AND 条件）
                existing_cols_raw = re.split(r'\s+AND\s+', group_by_content, maxsplit=1)[0]
                existing_cols = [c.strip().strip('`').strip('[').strip(']') for c in existing_cols_raw.split(',')]
                existing_cols = [c for c in existing_cols if c]  # 去除空字符串

                # 添加缺失的列
                cols_to_add = []
                for col in group_by_cols:
                    if col.upper() not in [c.upper() for c in existing_cols]:
                        cols_to_add.append(col)
                        existing_cols.append(col)

                if cols_to_add:
                    # 替换 GROUP BY 子句
                    new_group_by = f"GROUP BY {', '.join(existing_cols)}"
                    adjusted_sql = re.sub(
                        r'GROUP\s+BY\s+.+?(?=\s*(?:ORDER|LIMIT|WHERE|$))',
                        new_group_by,
                        adjusted_sql,
                        flags=re.IGNORECASE | re.DOTALL
                    )

                    # 【重要】同步更新 SELECT 列表，添加缺失的 GROUP BY 列
                    # 找到 SELECT ... FROM 模式，在聚合函数前插入新列
                    select_pattern = r'(SELECT\s+)(.*?)(\s+FROM\s+)'
                    select_match = re.search(select_pattern, adjusted_sql, re.IGNORECASE | re.DOTALL)
                    if select_match:
                        select_prefix = select_match.group(1)  # "SELECT "
                        select_content = select_match.group(2)  # SELECT 和 FROM 之间的内容
                        from_suffix = select_match.group(3)  # " FROM "

                        # 检查 cols_to_add 中的列是否已存在于 select_content
                        cols_to_add_to_select = []
                        for col in cols_to_add:
                            col_name = f"`{col}`"
                            if col_name.upper() not in select_content.upper() and col.upper() not in select_content.upper():
                                cols_to_add_to_select.append(col_name)

                        if cols_to_add_to_select:
                            # 在 FROM 前插入新列
                            cols_str = ", ".join(cols_to_add_to_select) + ", "
                            new_select = select_prefix + cols_str + select_content.strip() + from_suffix
                            adjusted_sql = new_select + adjusted_sql[select_match.end():]
                            logger.info(f"[_apply_dimensions_to_sql] SELECT 已更新，添加列: {cols_to_add_to_select}")
            else:
                adjusted_sql += f" GROUP BY {', '.join(group_by_cols)}"

        # === 如果有单维度但列表为空，处理单维度的情况（兼容旧逻辑）===
        if not group_by_cols and single_dimension:
            if single_dimension in time_dimension_keys:
                dim_key = "日" if single_dimension in ["日", "day"] else "月" if single_dimension in ["月", "month"] else "年"
                if table_name:
                    dim_configs = self._get_table_dimensions_cached(table_name)
                    col = dim_configs.get(dim_key, {}).get("column_name", dim_key.upper())
                else:
                    col = dim_key.upper()
                if "GROUP BY" not in adjusted_sql.upper():
                    adjusted_sql += f" GROUP BY {col}"
            elif single_dimension:
                # 有维度，保留 GROUP BY，从配置查列名
                if table_name:
                    dim_configs = self._get_table_dimensions_cached(table_name)
                else:
                    dim_configs = {}
                # 优先精确匹配
                matched_dim = None
                if dim_configs and single_dimension in dim_configs:
                    matched_dim = single_dimension
                elif dim_configs:
                    # 模糊匹配：收集所有匹配项，优先选最长的（最具体的）
                    candidates = []
                    for dim_name in dim_configs:
                        if single_dimension in dim_name or dim_name in single_dimension:
                            candidates.append(dim_name)
                    if candidates:
                        matched_dim = max(candidates, key=len)
                    if not matched_dim:
                        for dim_name in dim_configs:
                            if dim_name in single_dimension:
                                matched_dim = dim_name
                                break
                if matched_dim and dim_configs:
                    column = dim_configs[matched_dim].get("column_name", matched_dim)
                else:
                    column = single_dimension
            else:
                column = single_dimension
            adjusted_sql = adjusted_sql.replace("{dimension}", column)
            # 如果已有具体的维度值（如 GROUP_3='智能云存储'），不应该再加 GROUP BY
            # 因为 WHERE 条件已经筛选了这个具体值
            # 注意：__SYNONYM__ 不是具体值，是"识别了维度类型但无具体值"的标记
            specific_dim_keys = list(self._get_all_dimension_keys())
            has_specific_dim_value = any(
                entities.get(k) and entities.get(k) != '__SYNONYM__'
                for k in specific_dim_keys
            )
            time_dimensions = ['日', '月', '年', '天', '周']
            is_time_dim = single_dimension in time_dimensions
            if single_dimension:
                # 先检查是否 GROUP BY 在 LIMIT 之后（错误位置），需要修复
                limit_before_group_by = re.search(r'\s+LIMIT\s+\d+\s+OFFSET\s+\d+\s+GROUP\s+BY\s+', adjusted_sql, re.IGNORECASE)
                if limit_before_group_by:
                    logger.info(f"[_apply_dimensions_to_sql] 检测到 GROUP BY 在 LIMIT 之后（错误），修复")
                    # 重新排列为 GROUP BY ... LIMIT ...
                    sql_before_limit = adjusted_sql[:limit_before_group_by.start()].rstrip()
                    limit_and_offset = limit_before_group_by.group().strip()
                    group_by_part = adjusted_sql[limit_before_group_by.end():].strip()
                    adjusted_sql = f"{sql_before_limit} GROUP BY {group_by_part} {limit_and_offset}"
                    logger.info(f"[_apply_dimensions_to_sql] 修复后SQL: {adjusted_sql[:200]}")
                elif "GROUP BY" not in adjusted_sql.upper():
                    logger.info(f"[_apply_dimensions_to_sql] 单维度分支: single_dimension={single_dimension}, column={column}, has_specific_dim_value={has_specific_dim_value}")
                    if has_specific_dim_value and not is_time_dim:
                        logger.info(f"[_apply_dimensions_to_sql] 已有具体维度值，跳过 GROUP BY {column}")
                    else:
                        # 追加 GROUP BY 时，需要在 LIMIT 之前插入
                        # 必须匹配完整的 LIMIT...OFFSET 模式，否则插入位置会错误
                        limit_match = re.search(r'(\s+LIMIT\s+\d+\s+(?:OFFSET\s+\d+)?)', adjusted_sql, re.IGNORECASE)
                        logger.info(f"[_apply_dimensions_to_sql] LIMIT匹配: limit_match={limit_match.group(1) if limit_match else None}")
                        if limit_match:
                            # LIMIT 之前的位置插入 GROUP BY
                            insert_pos = limit_match.start()
                            adjusted_sql = adjusted_sql[:insert_pos].rstrip() + f" GROUP BY {column}" + adjusted_sql[insert_pos:]
                            logger.info(f"[_apply_dimensions_to_sql] 修复后SQL: {adjusted_sql[:200]}")
                        else:
                            adjusted_sql = adjusted_sql.rstrip() + f" GROUP BY {column}"
                            logger.info(f"[_apply_dimensions_to_sql] 无LIMIT，直接追加GROUP BY: {adjusted_sql[:200]}")
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
            # 跳过空值、dimension 占位符、__SYNONYM__ 占位符
            if not dim_value or dim_key == "dimension" or dim_value == "__SYNONYM__":
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

            # === 修复：支持多列 GROUP BY ===
            group_cols = []  # 改为列表，支持多列
            # 支持反引号``、方括号[]、无引号等多种 GROUP BY 列名格式
            # 注意：(?=\s*(?:ORDER|LIMIT|WHERE|$)) 中的 ORDER/LIMIT/WHERE 是 SQL 关键字，
            # 不会出现在 GROUP BY 列名中，所以不会产生歧义
            group_match = re.search(r'GROUP\s+BY\s+([\w`\[\],\s]+?)(?=\s*(?:ORDER|LIMIT|WHERE|$))', adjusted_sql, re.IGNORECASE)
            if group_match:
                group_by_clause = group_match.group(1)
                # 解析所有列（逗号分隔），并去除反引号、方括号等
                import re as re_module
                for col in group_by_clause.split(','):
                    col = col.strip()
                    # 去除反引号、方括号
                    col = re_module.sub(r'[` \[\]]', '', col)
                    if col:
                        group_cols.append(col)

            # === 修复：将 GROUP BY 列添加到 SELECT ===
            if group_cols:
                # 获取 SELECT 子句
                select_match = re.search(r'SELECT\s+(.*?)\s+FROM', adjusted_sql, re.IGNORECASE | re.DOTALL)
                if select_match:
                    select_clause = select_match.group(1)
                    # 检查哪些列还没在 SELECT 中
                    cols_to_add = []
                    for col in group_cols:
                        if col.upper() not in select_clause.upper():
                            cols_to_add.append(col)

                    # 将缺失的列添加到 SELECT（插入到聚合函数之前）
                    if cols_to_add:
                        adjusted_sql = re.sub(
                            r'(SELECT\s+)(.*?)(\s+FROM)',
                            r'\1' + ', '.join(cols_to_add) + r', \2\3',
                            adjusted_sql,
                            flags=re.IGNORECASE | re.DOTALL
                        )

            # 添加 ORDER BY 和 LIMIT（正确的 SQL 语法：ORDER BY ... LIMIT n）
            if group_cols:
                adjusted_sql = re.sub(r'\s*$', '', adjusted_sql)  # 去掉末尾空白

                # 检查现有的 LIMIT 和 OFFSET
                has_limit = "LIMIT" in adjusted_sql.upper()
                has_offset = "OFFSET" in adjusted_sql.upper()
                has_order_by = "ORDER BY" in adjusted_sql.upper()

                if has_order_by and has_limit:
                    # ORDER BY 在 LIMIT 之后，需要重新排列
                    # 提取 ORDER BY 子句
                    order_match = re.search(r'ORDER\s+BY\s+[^\s]+\s+(ASC|DESC)?', adjusted_sql, re.IGNORECASE)
                    if order_match:
                        order_clause = order_match.group(0)
                        # 提取 LIMIT...OFFSET 子句
                        limit_match = re.search(r'LIMIT\s+\d+\s+OFFSET\s+\d+', adjusted_sql, re.IGNORECASE)
                        if limit_match:
                            limit_clause = limit_match.group(0)
                            # 重新排列：去掉原来的 ORDER BY 和 LIMIT，重新按正确顺序添加
                            adjusted_sql = re.sub(r'ORDER\s+BY\s+[^\s]+\s+(ASC|DESC)?', '', adjusted_sql, flags=re.IGNORECASE)
                            adjusted_sql = re.sub(r'LIMIT\s+\d+\s+OFFSET\s+\d+', '', adjusted_sql, flags=re.IGNORECASE)
                            adjusted_sql = adjusted_sql.rstrip()
                            adjusted_sql = f"{adjusted_sql} {order_clause} {limit_clause}"
                            logger.info(f"[_apply_dimensions_to_sql] 重新排列SQL语序: {adjusted_sql[:200]}")
                elif not has_order_by:
                    if has_limit and has_offset:
                        # LIMIT...OFFSET 存在，在它之前添加 ORDER BY
                        adjusted_sql = re.sub(
                            r'(LIMIT\s+\d+\s+OFFSET\s+\d+)',
                            f'ORDER BY {metric_col} DESC \\1',
                            adjusted_sql,
                            flags=re.IGNORECASE
                        )
                    else:
                        # 没有 ORDER BY也没有 LIMIT，正常添加
                        adjusted_sql += f" ORDER BY {metric_col} DESC LIMIT {top_n}"
                elif has_limit:
                    # 有 ORDER BY 但没有 LIMIT
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
        result = parser.parse(text)
        return result

    def _extract_top_n(self, text: str) -> Optional[int]:
        """从文本中提取 top N 排名信息（如"前三"、"前十"、"前13名"、"十三级"、"最高的10个"、"最高的"等）"""
        import re
        # 中文数字映射
        chinese_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '零': 0}
        # 匹配"前"+"数字/中文数字"+"名"或"级"等
        patterns = [
            r'前(\d+)名',                  # 前10名、前13名
            r'前(\d+)级',                  # 前10级
            r'前([一二三四五六七八九十零]+)名',  # 前三名、前十名
            r'前([一二三四五六七八九十]+)',     # 前三、前十
            r'最高的(\d+)个',               # 最高的10个
            r'最高的(\d+)名',               # 最高的10名
            r'top\s*(\d+)',                # top10、top 10
            r'第\s*(\d+)名',               # 第1名、第10名
            r'(\d+)\s*名',                 # 10名（数字+名）
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
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

        # 检查"最高的"不带数字的情况，默认返回10
        if re.search(r'最高的(?!\d)', text):  # 最高的后面不跟数字
            return 10

        return None

    def _extract_ranking_dimension(self, text: str, intent: str) -> Optional[str]:
        """
        从文本中提取排名分析的分组维度
        例如："最高的品类" -> "品类", "销售最好的品牌" -> "品牌"

        Returns:
            维度类型字符串（如"品类"、"品牌"、"渠道"），或者 None
        """
        import re
        text_lower = text.lower()

        # 如果不是排名类意图，直接返回
        ranking_intents = ["query_ranking", "query_value"]
        if intent not in ranking_intents:
            return None

        # 定义维度词及其可能的变体
        dimension_words = {
            "品类": ["品类", "类目", "商品类", "产品类", "category"],
            "品牌": ["品牌", "商标", "牌子", "brand"],
            "渠道": ["渠道", "通路", "channel"],
            "地区": ["地区", "区域", "地域", "省份", "城市", "region"],
            "平台": ["平台", "platform"],
            "国家": ["国家", "country", "国度"],
            "客户": ["客户", "顾客", "买家", "用户", "customer"],
            "商品": ["商品", "产品", "货品", "item", "product"],
            "SKU": ["sku", "SKU", "款号"],
            "ASIN": ["asin", "ASIN"],
            "部门": ["部门", "科室", "team", "department"],
            "设备": ["设备", "device"],
            "广告": ["广告", "ad", "广告计划"],
        }

        # 检测"最高的/最好的/最低的/最差的+维度词"模式
        ranking_patterns = [
            r'最高的\s*(\w+)',    # 最高的品类
            r'最好的\s*(\w+)',    # 最好的品牌
            r'最低的\s*(\w+)',    # 最低的地区
            r'最差的\s*(\w+)',    # 最差的渠道
            r'销量最高的\s*(\w+)', # 销量最高的品类
            r'销售最高的\s*(\w+)', # 销售最高的品牌
            r'卖得最好的\s*(\w+)', # 卖得最好的商品
            r'卖得最差的\s*(\w+)', # 卖得最差的商品
            r'最受欢迎的\s*(\w+)', # 最受欢迎的商品
            r'排名第一的\s*(\w+)', # 排名第一的品牌
        ]

        for pattern in ranking_patterns:
            match = re.search(pattern, text)
            if match:
                extracted_dim = match.group(1)

                # Step 1: 先检测 extracted_dim 本身是否是"二级品类"/"三级品类"等多级具体维度词
                # 匹配 "(一|二|三|四)级+品类" 等多级维度模式（优先级最高）
                multi_level_match = re.match(r'^(一|二|三|四)级(品类|品牌|类目)', extracted_dim)
                if multi_level_match:
                    logger.debug(f"[_extract_ranking_dimension] 检测到多级维度: {extracted_dim}")
                    return extracted_dim  # 直接返回具体维度词，如"二级品类"

                # Step 2: 精确匹配 extracted_dim 是否是已知维度类型变体
                # （按长度降序，确保"品类"不错误吞掉"二级品类"）
                all_variants = []
                for dim_type, dim_variants in dimension_words.items():
                    for variant in dim_variants:
                        all_variants.append((len(variant), variant, dim_type))
                all_variants.sort(key=lambda x: -x[0])  # 长度降序

                for _, variant, dim_type in all_variants:
                    if variant in extracted_dim or extracted_dim in variant:
                        logger.debug(f"[_extract_ranking_dimension] 检测到排名维度: {dim_type} (匹配变体: {variant})")
                        return dim_type

        # 备选：直接检测常见的维度词是否出现在"最高的"后面
        # 有些用户可能说"品类最高的"（维度词在"最高的"前面）
        for dim_type, dim_variants in dimension_words.items():
            for variant in dim_variants:
                # 检测"X最高的"或"最高的X"
                if re.search(rf'{variant}.*最高|最高.*{variant}', text):
                    logger.debug(f"[_extract_ranking_dimension] 检测到排名维度(变体): {dim_type}")
                    return dim_type

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
                    params=state.sql_params,
                    dept_id=getattr(state, 'dept_id', 0),
                    data_filter=getattr(state, 'data_filter', '')
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
        对比计算节点 - 处理同比环比计算（支持同时计算同比和环比）

        当意图为 query_comparison 时：
        1. 获取当前查询结果（当前周期值）
        2. 检测需要计算的对比类型（同比、环比）
        3. 对每种对比类型计算周期、查询对比值、计算涨跌幅
        4. 将所有对比结果存入 comparison_results 列表
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
        # 获取单位
        unit = state.entities.get("unit", "")
        logger.info(f"[comparison] unit={unit}")
        if current_value is None:
            logger.info("[comparison] 无法提取当前值，跳过")
            return {"skip_comparison": True}

        # 从用户消息中判断对比类型（支持同时计算同比和环比）
        last_message = state.messages[-1].content if state.messages else ""
        has_yoy = any(kw in last_message for kw in ["同比", "去年同期", "比去年同期"])
        has_mom = any(kw in last_message for kw in ["环比", "上月", "比上月"])
        comparison_types = []
        if has_yoy:
            comparison_types.append("同比")
        if has_mom:
            comparison_types.append("环比")
        if not comparison_types:
            # 默认使用同比
            comparison_types = ["同比"]
        logger.info(f"[comparison] 检测到对比类型: {comparison_types}")

        # 从 time_info 中提取时间范围
        time_info = state.entities.get("time_info", {})
        time_range = state.entities.get("time_range", {})

        # 优先用 time_info 的 start/end（time_info 是字典）
        start_date = None
        end_date = None
        if time_info and isinstance(time_info, dict):
            start_date = time_info.get("start")
            end_date = time_info.get("end")
        elif time_range and isinstance(time_range, dict):
            start_date = time_range.get("start")
            end_date = time_range.get("end")

        logger.info(f"[comparison] time_info={time_info}, start_date={start_date}, end_date={end_date}")

        if not start_date or not end_date:
            logger.warning("[comparison] 无法从 time_info 提取时间范围，跳过对比计算")
            result = {"skip_comparison": True, "reason": "无法提取时间范围"}
            logger.info(f"[comparison] 返回: {result}")
            return result

        # 解析日期
        import re
        from datetime import datetime
        try:
            start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
            end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
            # 判断原始时间范围是否是完整月份（结束日期是该月最后一天）
            is_full_month = end_dt.day == calendar.monthrange(end_dt.year, end_dt.month)[1]
            logger.info(f"[comparison] is_full_month={is_full_month} (end_dt.day={end_dt.day})")
        except Exception as e:
            logger.error(f"[comparison] 日期解析失败: {str(e)}")
            return {"skip_comparison": True}

        # 构建对比SQL（替换时间条件）- 为每种对比类型生成
        original_sql = state.generated_sql
        if not original_sql or original_sql == "METADATA_QUERY":
            logger.info("[comparison] original_sql无效，跳过")
            return {"skip_comparison": True}

        def build_comparison_sql(comparison_start: str, comparison_end: str) -> str:
            """构建对比SQL"""
            sql = re.sub(
                r"(\w+)\s*>=\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?",
                lambda m: f"{m.group(1)} >= '{comparison_start}'",
                original_sql,
                flags=re.IGNORECASE
            )
            sql = re.sub(
                r"(\w+)\s*<=\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?",
                lambda m: f"{m.group(1)} <= '{comparison_end}'",
                sql,
                flags=re.IGNORECASE
            )
            # 移除 LIMIT 和 OFFSET
            sql = re.sub(r'\s+LIMIT\s+\d+\s*(OFFSET\s+\d+)?', '', sql, flags=re.IGNORECASE)
            sql = re.sub(r'\s+OFFSET\s+\d+', '', sql, flags=re.IGNORECASE)
            return sql

        def calculate_comparison_period(comp_type: str, start_dt: datetime, end_dt: datetime, is_full_month: bool) -> tuple:
            """计算对比周期（开始日期，结束日期）"""
            if comp_type == "环比":
                # 环比：上月同日
                if start_dt.month == 1:
                    comp_start_year, comp_start_month = start_dt.year - 1, 12
                else:
                    comp_start_year, comp_start_month = start_dt.year, start_dt.month - 1

                if end_dt.month == 1:
                    comp_end_year, comp_end_month = end_dt.year - 1, 12
                else:
                    comp_end_year, comp_end_month = end_dt.year, end_dt.month - 1

                if is_full_month:
                    comparison_start = f"{comp_start_year}-{comp_start_month:02d}-{start_dt.day:02d}"
                    comp_end_day = calendar.monthrange(comp_end_year, comp_end_month)[1]
                    comparison_end = f"{comp_end_year}-{comp_end_month:02d}-{comp_end_day:02d}"
                else:
                    comparison_start = f"{comp_start_year}-{comp_start_month:02d}-{start_dt.day:02d}"
                    # 非完整月：结束日期为 end_dt.day - 1（昨天），不超过今天
                    from datetime import timedelta
                    yesterday = datetime.now() - timedelta(days=1)
                    comp_end_day = min(end_dt.day - 1, yesterday.day)
                    comparison_end = f"{comp_end_year}-{comp_end_month:02d}-{comp_end_day:02d}"
            else:
                # 同比：去年同期
                comp_start_year, comp_end_year = start_dt.year - 1, end_dt.year - 1
                if is_full_month:
                    comparison_start = f"{comp_start_year}-{start_dt.month:02d}-{start_dt.day:02d}"
                    comp_end_day = calendar.monthrange(comp_end_year, end_dt.month)[1]
                    comparison_end = f"{comp_end_year}-{end_dt.month:02d}-{comp_end_day:02d}"
                else:
                    comparison_start = f"{comp_start_year}-{start_dt.month:02d}-{start_dt.day:02d}"
                    # 非完整月：结束日期为 end_dt.day - 1（昨天），不超过今天
                    from datetime import timedelta
                    yesterday = datetime.now() - timedelta(days=1)
                    comp_end_day = min(end_dt.day - 1, yesterday.day)
                    comparison_end = f"{comp_end_year}-{end_dt.month:02d}-{comp_end_day:02d}"

            return comparison_start, comparison_end

        # 执行每种对比计算（并发优化）
        comparison_results = []
        thinking_parts = []

        # 提取当前查询的data_list（用于多行对比匹配）
        data_list = self._extract_data_list(state.sql_result)
        logger.info(f"[comparison] 当前查询数据列表长度: {len(data_list) if data_list else 0}")

        # 从原始SQL提取GROUP BY列（用于多行对比匹配）
        group_by_col = None
        group_by_match = re.search(r'GROUP BY\s+([^\s,]+)', state.generated_sql or '', re.IGNORECASE)
        if group_by_match:
            group_by_col = group_by_match.group(1).strip('`')
            logger.info(f"[comparison] 提取的GROUP BY列: {group_by_col}")

        # Step 1: 构建所有对比SQL
        comparison_tasks = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for comp_type in comparison_types:
            comparison_start, comparison_end = calculate_comparison_period(comp_type, start_dt, end_dt, is_full_month)
            # 检查对比周期的 end_date 是否大于今天
            try:
                comp_end_dt = datetime.strptime(comparison_end[:10], "%Y-%m-%d")
                if comp_end_dt > today:
                    logger.info(f"[comparison] {comp_type} 对比周期结束日期 {comparison_end} > 今天 {today.strftime('%Y-%m-%d')}，跳过该对比类型")
                    thinking_parts.append(f"{comp_type}：对比周期 {comparison_start} 至 {comparison_end} 超出今天，跳过")
                    continue
            except Exception as e:
                logger.warning(f"[comparison] 日期比较失败: {e}")
            comparison_sql = build_comparison_sql(comparison_start, comparison_end)
            comparison_tasks.append({
                "comp_type": comp_type,
                "comparison_start": comparison_start,
                "comparison_end": comparison_end,
                "comparison_sql": comparison_sql,
            })

        # Step 2: 并发执行所有对比SQL
        async def execute_single_comparison(task):
            comp_sql = task["comparison_sql"]
            comp_type = task["comp_type"]
            logger.info(f"[comparison] {comp_type} SQL: {comp_sql}")
            result = await self.sql_generator.execute(sql=comp_sql, params=state.sql_params)
            return task, result

        # 并发执行
        import asyncio
        results = await asyncio.gather(*[execute_single_comparison(t) for t in comparison_tasks], return_exceptions=True)

        # Step 3: 处理每个对比结果
        for result_item in results:
            if isinstance(result_item, Exception):
                logger.error(f"[comparison] 对比SQL执行失败: {str(result_item)}")
                continue

            task, comp_result = result_item
            comp_type = task["comp_type"]
            comparison_start = task["comparison_start"]
            comparison_end = task["comparison_end"]
            comparison_sql = task["comparison_sql"]

            try:
                logger.info(f"[comparison] {comp_type} 查询结果: {comp_result}")

                # 提取对比数据列表（用于多行匹配）
                comp_data_list = self._extract_data_list(comp_result)
                logger.info(f"[comparison] {comp_type} 对比数据列表长度: {len(comp_data_list) if comp_data_list else 0}")

                if comp_data_list:
                    # 构建group key -> row 的映射（用于多行匹配）
                    comp_data_map = {}
                    metric_col = None
                    # 优先使用 metric_name 从 state.entities 匹配列名（支持中文列名）
                    metric_name = state.entities.get("metric_name", "")
                    logger.info(f"[comparison] metric_name from entities: {metric_name}")

                    # 从 data_list（当前数据）检测 metric_col
                    if not metric_col and data_list:
                        first_row = data_list[0]
                        # 直接用 metric_name 匹配（最准确）
                        if metric_name and metric_name in first_row:
                            metric_col = metric_name
                            logger.info(f"[comparison] 使用 metric_name 作为 metric_col: {metric_col}")
                        else:
                            # 回退：从第一行取非 group_by 列
                            for k in first_row.keys():
                                if group_by_col and k.upper() == group_by_col.upper():
                                    continue
                                # 跳过已知的对比列名模式
                                if any(p in k for p in ['同比', '环比', '去年同期', '上月同期']):
                                    continue
                                metric_col = k
                                logger.info(f"[comparison] 从 data_list 检测到 metric_col: {metric_col}")
                                break

                    # 如果 data_list 没找到，从 comp_data_list 检测
                    if not metric_col:
                        for row in comp_data_list:
                            if group_by_col and group_by_col in row:
                                key = row.get(group_by_col)
                                comp_data_map[key] = row
                            # 提取指标列名（用于计算变化率）
                            if metric_col is None:
                                for k in row.keys():
                                    if k.upper() not in (group_by_col.upper(),) if group_by_col else True:
                                        # 跳过已知的对比列名模式
                                        if any(p in k for p in ['同比', '环比', '去年同期', '上月同期']):
                                            continue
                                        metric_col = k
                                        logger.info(f"[comparison] 从 comp_data_list 检测到 metric_col: {metric_col}")
                                        break
                    else:
                        # metric_col 已从 data_list 找到，同时构建 comp_data_map
                        for row in comp_data_list:
                            if group_by_col and group_by_col in row:
                                key = row.get(group_by_col)
                                comp_data_map[key] = row

                    # 计算每个group key的对比值和变化率
                    for row in data_list:
                        row_key = row.get(group_by_col) if group_by_col else None
                        comp_row = comp_data_map.get(row_key) if row_key else None

                        if comp_row and metric_col:
                            current_metric_val = self._extract_metric_value_from_row(row, metric_col)
                            comp_metric_val = self._extract_metric_value_from_row(comp_row, metric_col)

                            if current_metric_val is not None and comp_metric_val is not None and comp_metric_val != 0:
                                change_rate = (current_metric_val - comp_metric_val) / comp_metric_val * 100
                                # 添加对比列到当前行
                                if comp_type == "同比":
                                    row["去年同期"] = self._format_metric_value(comp_metric_val, unit)
                                    row["同比变化率"] = round(change_rate, 2)
                                else:
                                    row["上月同期"] = self._format_metric_value(comp_metric_val, unit)
                                    row["环比变化率"] = round(change_rate, 2)
                            else:
                                # 找不到对比数据或数据无效，也要加占位列保持每行列数一致
                                if comp_type == "同比":
                                    row["去年同期"] = None
                                    row["同比变化率"] = None
                                else:
                                    row["上月同期"] = None
                                    row["环比变化率"] = None
                        else:
                            # 找不到匹配的SKU，加占位列保持每行列数一致
                            if comp_type == "同比":
                                row["去年同期"] = None
                                row["同比变化率"] = None
                            else:
                                row["上月同期"] = None
                                row["环比变化率"] = None

                    # 计算总体对比（用于摘要）
                    total_comp = sum(self._extract_metric_value_from_row(row, metric_col) or 0 for row in comp_data_list)
                    total_current = sum(self._extract_metric_value_from_row(row, metric_col) or 0 for row in data_list)

                    comparison_results.append({
                        "current_value": total_current,
                        "comparison_value": total_comp,
                        "comparison_date": f"{comparison_start} 至 {comparison_end}",
                        "comparison_type": comp_type,
                        "change_rate": (total_current - total_comp) / total_comp * 100 if total_comp != 0 else 0,
                        "comparison_sql": comparison_sql,
                        "group_by_col": group_by_col,
                        "comp_data_map": {str(k): v for k, v in comp_data_map.items()}  # key转字符串
                    })
                    thinking_parts.append(f"{comp_type}={total_comp}（{(total_current - total_comp) / total_comp * 100:+.2f}%）" if total_comp != 0 else f"{comp_type}=0")
                    logger.info(f"[comparison] {comp_type} 计算成功: 总计={total_comp}, 涨跌幅={(total_current - total_comp) / total_comp * 100:+.2f}%")
                else:
                    logger.info(f"[comparison] {comp_type} 对比数据为空，跳过")

            except Exception as e:
                logger.error(f"[comparison] {comp_type} 计算失败: {str(e)}")
                continue

        if comparison_results:
            state.comparison_results = comparison_results
            self._add_thinking_step(state, "对比计算", "completed",
                f"当前值={current_value}，" + "，".join(thinking_parts))
            result = {"comparison_results": comparison_results}
            logger.info(f"[comparison] 成功返回 {len(comparison_results)} 个对比结果: {result}")
            return result
        else:
            self._add_thinking_step(state, "对比计算", "completed", "所有对比数据为空")
            logger.info("[comparison] 所有对比数据为空，跳过")
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

    def _extract_data_list(self, sql_result: Dict) -> Optional[List[Dict]]:
        """从SQL查询结果中提取数据列表（用于多行匹配）"""
        if not sql_result:
            return None
        data = sql_result.get("data")
        if not data:
            return None
        # 处理嵌套结构
        if isinstance(data, dict):
            if "data" in data:
                inner = data["data"]
                if isinstance(inner, list):
                    return inner
                elif isinstance(inner, dict):
                    return [inner]
            return [data]
        elif isinstance(data, list):
            return data
        return None

    def _extract_metric_value_from_row(self, row: Dict, metric_col: str) -> Optional[float]:
        """从单行数据中提取指标数值"""
        if not row or not metric_col:
            return None
        # 大小写不敏感匹配
        row_upper = {k.upper(): k for k in row.keys()}
        actual_col = row_upper.get(metric_col.upper())
        if not actual_col:
            return None
        val = row.get(actual_col)
        if val is None:
            return None
        try:
            if isinstance(val, str):
                return float(val.replace(",", "").strip())
            return float(val)
        except (ValueError, TypeError):
            return None

    def _format_metric_value(self, val: float, unit: str = "") -> str:
        """格式化指标数值显示"""
        if val is None:
            return "N/A"
        try:
            if unit == "%":
                return f"{val:.2f}%"
            elif unit in ("元", "万美元", "亿美元"):
                return f"¥{val:,.2f}"
            elif abs(val) >= 10000:
                return f"{val:,.2f}"
            else:
                return f"{val:,.2f}"
        except:
            return str(val)

    def response_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        生成回答节点
        - 元数据查询：展示业务口径、技术口径等
        - 数值查询：展示实际数据或"暂无数据"
        """
        # 需要追问的情况
        if state.needs_clarification:
            # 【修复】追问前保存上下文，确保 dimension 等信息被持久化
            self._update_context(state, state.entities)

            # metric_enum 类型：直接显示匹配指标列表
            clarification_type = getattr(state, 'clarification_type', None)
            if clarification_type == "metric_enum":
                return {
                    "answer": state.clarification_message,
                    "suggest_questions": getattr(state, 'suggest_questions', []) or self._generate_suggestions(state),
                    "needs_clarification": True,
                    "clarification_type": clarification_type,
                    "thinking_steps": [{k: v for k, v in (s.model_dump() if hasattr(s, 'model_dump') else s).items() if k != 'timestamp'} for s in state.thinking_steps],
                }
            # 其他追问类型：优先使用 state.error
            error_msg = getattr(state, 'error', None)
            if error_msg:
                return {
                    "answer": f"抱歉，{error_msg}",
                    "suggest_questions": getattr(state, 'suggest_questions', []) or self._generate_suggestions(state),
                    "needs_clarification": True,
                    "thinking_steps": [{k: v for k, v in (s.model_dump() if hasattr(s, 'model_dump') else s).items() if k != 'timestamp'} for s in state.thinking_steps],
                }
            # 使用 clarification_message 作为追问内容
            return {
                "answer": state.clarification_message or "抱歉，我需要更多信息来回答您的问题",
                "suggest_questions": getattr(state, 'suggest_questions', []) or self._generate_suggestions(state),
                "needs_clarification": True,
                "thinking_steps": [{k: v for k, v in (s.model_dump() if hasattr(s, 'model_dump') else s).items() if k != 'timestamp'} for s in state.thinking_steps],
            }

        # ========== 兜底处理：意图置信度低但不是明确指标查询 ==========
        # 如果意图是 query_value 但没有提取到任何指标，或者意图是 unknown，
        # 说明用户可能在闲聊或问了一个通用问题，直接走 LLM 回复
        if state.current_intent in ["query_value", "unknown"]:
            has_metric = bool(state.entities.get("metric_name") or state.entities.get("metric_code"))
            has_time = bool(state.entities.get("time_range"))
            # 既没有指标也没有时间，大概率是闲聊
            if not has_metric and not has_time:
                logger.info(f"[response_node] 兜底处理: intent={state.current_intent}, 无指标无时间，判定为闲聊")
                return {
                    "answer": "您好！我是智能问数助手，可以帮您查询指标数据。比如您可以问我：「昨天的销售额是多少」、「本周订单量趋势」等。请问有什么可以帮您？",
                    "suggest_questions": ["昨天的访客数是多少", "本周订单量如何", "查看销售额指标"],
                    "needs_clarification": False,
                    "thinking_steps": [{k: v for k, v in (s.model_dump() if hasattr(s, 'model_dump') else s).items() if k != 'timestamp'} for s in state.thinking_steps],
                }

        # 打招呼
        if state.current_intent == "greeting":
            return {
                "answer": "您好！我是智能问数助手，可以帮您查询指标信息。请问您想查询哪个指标？",
                "suggest_questions": ["昨天的访客数是多少", "本周订单量如何", "查看销售额指标"],
                "needs_clarification": False,
                "thinking_steps": [{k: v for k, v in (s.model_dump() if hasattr(s, 'model_dump') else s).items() if k != 'timestamp'} for s in state.thinking_steps],
            }

        # 感谢
        if state.current_intent == "thanks":
            return {
                "answer": "不客气！很高兴能帮到您。有什么其他问题随时问我～",
                "suggest_questions": ["昨天的访客数是多少", "本周订单量如何", "查看销售额指标"],
                "needs_clarification": False,
                "thinking_steps": [{k: v for k, v in (s.model_dump() if hasattr(s, 'model_dump') else s).items() if k != 'timestamp'} for s in state.thinking_steps],
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
        logger.info(f"[response_node] ENTRY sql_result type={type(sql_result)}, keys={sql_result.keys() if isinstance(sql_result, dict) else 'N/A'}, data_count={len(sql_result.get('data',[])) if isinstance(sql_result, dict) else 'N/A'}")

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
                    # 有数据，生成自然语言回答
                    metric_name = state.entities.get("metric_name", "该指标")
                    unit = state.entities.get("unit", "")
                    comparison_results = getattr(state, 'comparison_results', None)
                    logger.info(f"[response_node] metric_name={metric_name}, entities={state.entities}")

                    # 简单查询用模板生成回答，复杂查询才调用 LLM
                    # 防御性检查：确保 rows 是列表而不是 None
                    if isinstance(data, dict):
                        raw_data = data.get("data", [])
                        rows = raw_data if isinstance(raw_data, list) else []
                    else:
                        rows = data if isinstance(data, list) else []

                    # 防御性检查：确保 comparison_results 是列表
                    if comparison_results is not None and not isinstance(comparison_results, list):
                        comparison_results = None

                    is_simple = (
                        (comparison_results is None or len(comparison_results) == 0) and
                        len(rows) <= 3 and
                        state.current_intent not in ("query_trend", "query_ranking")
                    )

                    if is_simple:
                        # 简单模板生成（避免 LLM 调用耗时）
                        row = rows[0] if rows else {}

                        # ========== 多指标支持 ==========
                        multi_metrics = state.entities.get("metrics", [])
                        if multi_metrics and len(multi_metrics) >= 2:
                            # 多指标查询：为每个指标格式化结果
                            answer_parts = []

                            # 解析 starrocks_sql 提取别名映射（re 已从模块级别导入）
                            alias_to_metric = {}  # alias -> (metric_name, unit)
                            for m in multi_metrics:
                                m_name = m.get("metric_name", "该指标")
                                m_unit = m.get("unit", "")
                                m_sql = m.get("starrocks_sql", "")
                                # 提取 "as alias" 或 "AS alias" 模式
                                aliases = re.findall(r'(?:as|AS)\s+[`"]?(\w+)[`"]?', m_sql)
                                for alias in aliases:
                                    alias_to_metric[alias.upper()] = (m_name, m_unit)

                            for m in multi_metrics:
                                m_name = m.get("metric_name", "该指标")
                                m_unit = m.get("unit", "")
                                m_sql = m.get("starrocks_sql", "")
                                m_code = m.get("metric_code", "")

                                # 找到该指标对应的列名
                                m_col = None
                                # 1. 优先：从 starrocks_sql 提取 alias 精确匹配（忽略大小写）
                                aliases = re.findall(r'(?:as|AS)\s+[`"]?(\w+)[`"]?', m_sql)
                                row_keys_lower = {k.lower(): k for k in row.keys()}
                                for alias in aliases:
                                    if alias.lower() in row_keys_lower:
                                        m_col = row_keys_lower[alias.lower()]
                                        break
                                # 2. 尝试用 metric_code 匹配（如 ORDERED_PRODUCTSALES）
                                if not m_col and m_code:
                                    for k in row.keys():
                                        if m_code.upper() in k.upper():
                                            m_col = k
                                            break
                                # 3. 尝试用 metric_name 匹配（如 总销售额）
                                if not m_col:
                                    for k in row.keys():
                                        if m_name in k or k in m_name:
                                            if not any(p in k for p in ['同比', '环比', '去年同期', '上月同期', '月', '日', '年']):
                                                m_col = k
                                                break
                                # 4. 用别名映射表匹配
                                if not m_col:
                                    for k in row.keys():
                                        if k.upper() in alias_to_metric:
                                            m_col = k
                                            break
                                # 5. 找到所有非维度列（兜底）
                                if not m_col:
                                    group_by_cols = ['月', '日', '年', '月份', '日期', '年份']
                                    for k in row.keys():
                                        if not any(bc in k for bc in group_by_cols) and not any(p in k for p in ['同比', '环比', '去年同期', '上月同期']):
                                            if m_col is None:  # 只取第一个
                                                m_col = k

                                if m_col:
                                    m_val = row.get(m_col)
                                else:
                                    m_val = None

                                if m_val is not None and isinstance(m_val, (int, float)):
                                    if m_unit == "%":
                                        answer_parts.append(f"**{m_name}**为 {m_val:.2f}%")
                                    elif m_unit in ("元", "万美元", "亿美元"):
                                        answer_parts.append(f"**{m_name}**为 ¥{m_val:,.2f}")
                                    elif "次" in m_unit or "元" not in m_unit:
                                        answer_parts.append(f"**{m_name}**为 {m_val:,.2f}{m_unit}")
                                    else:
                                        answer_parts.append(f"**{m_name}**为 {m_val:,.2f}")
                                elif m_val is not None:
                                    answer_parts.append(f"**{m_name}**为 {m_val}")

                            answer = "，".join(answer_parts) if answer_parts else f"查询完成，共 {len(rows)} 条数据"
                        else:
                            # 单指标查询（原有逻辑，但修复了维度列问题）
                            # 尝试从 starrocks_sql 提取 alias
                            metric_col = None
                            starrocks_sql = state.entities.get("starrocks_sql", "")
                            if starrocks_sql:
                                aliases = re.findall(r'(?:as|AS)\s+[`"]?(\w+)[`"]?', starrocks_sql)
                                row_keys_lower = {k.lower(): k for k in row.keys()}
                                for alias in aliases:
                                    if alias.lower() in row_keys_lower:
                                        metric_col = row_keys_lower[alias.lower()]
                                        break
                            # 兜底：跳过维度列和对比列
                            if not metric_col:
                                dim_cols = list(self._get_all_dimension_keys())
                                dim_cols.extend(['月', '日', '年', '月份', '日期', '年份', '同比', '环比', '去年同期', '上月同期'])
                                for k in row.keys():
                                    if not any(p in k for p in dim_cols):
                                        metric_col = k
                                        break
                            metric_val = row.get(metric_col) if metric_col else None
                            if metric_val is not None:
                                if isinstance(metric_val, (int, float)):
                                    if unit == "%":
                                        answer = f"**{metric_name}**为 {metric_val:.2f}%"
                                    elif unit in ("元", "万美元", "亿美元"):
                                        answer = f"**{metric_name}**为 ¥{metric_val:,.2f}"
                                    else:
                                        answer = f"**{metric_name}**为 {metric_val:,.2f}"
                                else:
                                    answer = f"**{metric_name}**为 {metric_val}"
                            else:
                                answer = f"**{metric_name}**查询完成，共 {len(rows)} 条数据"
                    else:
                        # 复杂查询调用 LLM 生成自然语言
                        logger.info(f"[response_node] 复杂查询，调用 LLM generate_response，data={data}")
                        answer = self.llm_engine.generate_response(
                            question=state.messages[-1].content if state.messages else "",
                            sql=state.generated_sql or "",
                            result=data,
                            metric_name=metric_name,
                            unit=unit,
                        )
                        logger.info(f"[response_node] LLM generate_response 返回: {answer[:200] if answer else 'EMPTY'}")

                    # 如果有对比计算结果，添加到 result_data 每行
                    comparison_results = getattr(state, 'comparison_results', None)
                    if comparison_results:
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

                        # 处理 result_data 格式
                        rows_to_process = data
                        if isinstance(data, dict):
                            if "data" in data:
                                rows_to_process = data["data"]
                            else:
                                rows_to_process = [data]

                        # 添加对比列到每行（如果 comparison_node 已经处理过则跳过）
                        if isinstance(rows_to_process, list):
                            for row in rows_to_process:
                                if isinstance(row, dict):
                                    # 跳过已经处理过且值有效的行（comparison_node 已添加每行各自的对比值）
                                    if row.get("同比变化率") is not None or row.get("环比变化率") is not None:
                                        continue
                                    for comp in comparison_results:
                                        comp_type = comp.get("comparison_type", "对比")
                                        comp_value = comp.get("comparison_value", 0)
                                        change_rate = comp.get("change_rate", 0)
                                        comp_str = f"{int(comp_value):,}" if isinstance(comp_value, (int, float)) and comp_value == int(comp_value) else format_value(comp_value, unit)
                                        if comp_type == "同比":
                                            row["去年同期"] = comp_str
                                            row["同比变化率"] = round(change_rate, 2)
                                        else:
                                            row["上月同期"] = comp_str
                                            row["环比变化率"] = round(change_rate, 2)

                        # 更新 data
                        if isinstance(data, dict) and "data" in data:
                            data = rows_to_process
                        else:
                            data = rows_to_process

                        # 生成对比摘要
                        if comparison_results:
                            answer += f"\n\n📊 **对比结果**\n"
                            answer += f"| 指标 | 数值 |\n"
                            answer += f"|------|------|\n"

                            # 第一行：当期值
                            first_comp = comparison_results[0]
                            current_value = first_comp.get("current_value", 0)
                            unit_for_display = unit
                            current_str = format_value(current_value, unit_for_display)
                            answer += f"| {metric_name}（当期） | {current_str} |\n"

                            # 后续行：各种对比
                            for comp in comparison_results:
                                comp_type = comp.get("comparison_type", "对比")
                                comp_value = comp.get("comparison_value", 0)
                                comp_date = comp.get("comparison_date", "")
                                change_rate = comp.get("change_rate", 0)
                                comp_str = f"{int(comp_value):,}" if isinstance(comp_value, (int, float)) and comp_value == int(comp_value) else format_value(comp_value, unit_for_display)

                                if comp_type == "同比":
                                    comp_period = f"去年同期（{comp_date[:7]}）" if comp_date else "去年同期"
                                else:
                                    comp_period = f"上月同期（{comp_date[:7]}）" if comp_date else "上月同期"

                                change_emoji = "↑" if change_rate > 0 else ("↓" if change_rate < 0 else "→")
                                change_color = "上涨" if change_rate > 0 else ("下跌" if change_rate < 0 else "持平")

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

                    # 重排列顺序：维度列 → 指标值列 → 对比列 → 占比/毛利率
                    if isinstance(result_data, list) and result_data:
                        # 使用 ResultFormatter 统一处理列识别、rename、排序
                        generated_sql = getattr(state, 'generated_sql', '') or ''
                        metric_name = state.entities.get("metric_name", "")
                        result_data = self.result_formatter.normalize_result_columns(
                            result_data=result_data,
                            metric_name=metric_name,
                            generated_sql=generated_sql
                        )
                        logger.info(f"[response_node] AFTER normalize result_data[0]={result_data[0] if result_data else 'empty'}")
                        logger.info(f"[response_node] RETURNING: answer={answer[:100] if answer else 'EMPTY'}")

                    return {
                        "answer": answer,
                        "suggest_questions": self._generate_suggestions(state),
                        "needs_clarification": False,
                        "result_data": result_data,
                        "comparison_results": getattr(state, 'comparison_results', None),
                        "thinking_steps": [{k: v for k, v in (s.model_dump() if hasattr(s, 'model_dump') else s).items() if k != 'timestamp'} for s in state.thinking_steps],
                    }

        # 没有结果
        self._update_context(state, state.entities)
        return {
            "answer": "抱歉，未能获取到有效数据",
            "suggest_questions": self._generate_suggestions(state),
            "needs_clarification": False,
            "thinking_steps": [{k: v for k, v in (s.model_dump() if hasattr(s, 'model_dump') else s).items() if k != 'timestamp'} for s in state.thinking_steps],
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


# 全局节点实例
conversation_nodes = ConversationNodes()
