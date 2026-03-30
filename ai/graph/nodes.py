"""
LangGraph 对话节点 - 优化版
"""
import re
import os
from typing import Dict, Any, Optional, List
from ai.graph.state import ConversationState, IntentResult, SQLGenerationResult, ClarificationDecision, ThinkingStep, ConversationContext
from ai.engine.rule_engine import RuleEngine
from ai.engine.llm import LLMEngine
from ai.sql_gen.generator import SQLGenerator
from ai.client.metric_client import MetricClient


# 延迟导入 Neo4j 相关模块，避免启动时必须连接
def _get_graph_query():
    """延迟加载 GraphQuery，避免 Neo4j 未启动时影响整体功能"""
    try:
        from ai.knowledge_graph.query import GraphQuery
        return GraphQuery()
    except Exception as e:
        if os.getenv("DEBUG"):
            print(f"[GraphQuery] Failed to load: {e}")
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
        意图识别节点 - 三层架构
        1. 规则层：关键词精准匹配（打招呼、感谢、告别）
        2. 语义层：Embedding + pgvector 相似度匹配
        3. LLM层：规则和语义都匹配不到时兜底
        """
        last_message = state.messages[-1].content if state.messages else ""

        # ========== Step 0: 复用上下文 ==========
        inherited_context = getattr(state, 'conversation_context', None) or ConversationContext()
        inherited_entities = {}
        if inherited_context.current_metric_name:
            inherited_entities = {
                "inherited_metric": inherited_context.current_metric_name,
                "inherited_metric_id": inherited_context.current_metric_id,
                "inherited_metric_name": inherited_context.current_metric_name,
            }

        print(f"[DEBUG intent_node] 输入: {last_message}")

        # ========== Step 1: 规则层匹配 ==========
        rule_result = self.rule_engine.recognize_intent(last_message)
        print(f"[DEBUG intent_node] 规则层结果: intent={rule_result.intent}, confidence={rule_result.confidence}")

        # 如果规则层匹配到确定性意图（打招呼、感谢、告别等），直接返回
        if rule_result.confidence >= 0.9 and rule_result.intent in ["greeting", "thanks", "bye"]:
            self._update_context(state, rule_result.entities)
            return {
                "current_intent": rule_result.intent,
                "entities": rule_result.entities,
            }

        # ========== Step 2: 语义层匹配（置信度决策）==========
        # 使用原始相似度分数进行置信度决策
        # 阈值：>0.85 直接确认，0.5-0.85 LLM审核，<0.5 追问
        INTENT_HIGH_THRESHOLD = 0.85
        INTENT_MEDIUM_THRESHOLD = 0.5

        semantic_intent_raw, similarity = self.rule_engine.semantic_search_intent(last_message)
        print(f"[DEBUG intent_node] 语义层结果: intent={semantic_intent_raw}, similarity={similarity:.3f}")

        # 语义层高置信度匹配（>0.85），直接使用
        if semantic_intent_raw and similarity > INTENT_HIGH_THRESHOLD:
            self._update_context(state, rule_result.entities)
            self._add_thinking_step(state, "意图理解", "completed",
                f"直接确认「{semantic_intent_raw}」，相似度 {similarity:.2f}")
            return {
                "current_intent": semantic_intent_raw,
                "entities": rule_result.entities,
            }

        # 语义层中等置信度（0.5-0.85），LLM 审核
        if semantic_intent_raw and similarity > INTENT_MEDIUM_THRESHOLD:
            print(f"[DEBUG intent_node] 进入 LLM 审核（相似度 {similarity:.2f}）...")
            intent_result = self._llm_review_intent(state, semantic_intent_raw, similarity)
        # 语义层低置信度（<0.5），追问用户
        elif semantic_intent_raw and similarity <= INTENT_MEDIUM_THRESHOLD:
            print(f"[DEBUG intent_node] 相似度太低（{similarity:.2f}），追问用户")
            state.needs_clarification = True
            state.clarification_type = "intent"
            state.clarification_message = "抱歉，我没理解您的意思。您是想查询指标值、趋势、还是对比数据呢？"
            self._add_thinking_step(state, "意图理解", "requires_clarification",
                f"相似度 {similarity:.2f} < {INTENT_MEDIUM_THRESHOLD}，需要追问")
            return {"current_intent": None, "entities": {}}
        # 无语义匹配，使用规则层结果
        else:
            intent_result = rule_result

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
            f"识别为「{intent_desc}」，置信度 {intent_result.confidence:.2f}（{match_level}匹配）")

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
        if entities.get("metric_id"):
            ctx.current_metric_id = entities.get("metric_id")
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

    def entity_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        实体链接节点 - 增强版
        支持多轮上下文继承
        """
        entities = state.entities.copy()

        # ========== 获取对话上下文 ==========
        ctx = getattr(state, 'conversation_context', None)

        # ========== 继承上轮的指标信息 ==========
        if ctx and not entities.get("metric_id") and not entities.get("metric_name"):
            if ctx.current_metric_name or ctx.current_metric_code:
                entities.setdefault("metric_name", ctx.current_metric_name)
                entities.setdefault("metric_code", ctx.current_metric_code)
                entities.setdefault("metric_id", ctx.current_metric_id)
                print(f"[DEBUG entity_node] 继承上轮指标: {ctx.current_metric_name}")

        # ========== 继承上轮的时间表达式 ==========
        if ctx and not entities.get("time_range") and ctx.current_time_expr:
            # 检查用户是否明确指定了新的时间
            last_message = state.messages[-1].content if state.messages else ""
            has_explicit_time = any(kw in last_message for kw in ["昨天", "今日", "本周", "本月", "去年"])
            if not has_explicit_time:
                entities.setdefault("time_range", ctx.current_time_expr)
                print(f"[DEBUG entity_node] 继承上轮时间: {ctx.current_time_expr}")

        # ========== 继承上轮的维度 ==========
        if ctx:
            for dim_key, dim_value in ctx.current_dimensions.items():
                if dim_key not in entities and dim_value:
                    entities[dim_key] = dim_value
                    print(f"[DEBUG entity_node] 继承上轮维度: {dim_key}={dim_value}")

        last_message = state.messages[-1].content if state.messages else ""

        # 检查是否是回应上轮的 metric_enum 追问（用户选择指标）
        user_just_selected_metric = False  # 标记用户是否刚选择了指标
        print(f"[DEBUG entity_node] 检查 metric_enum: clarification_type={getattr(state, 'clarification_type', None)}, matched_metrics存在={getattr(state, 'matched_metrics', None) is not None}")
        if getattr(state, 'clarification_type', None) == 'metric_enum' and getattr(state, 'matched_metrics', None) is not None:
            # 用户在选择指标
            print(f"[DEBUG entity_node] matched_metrics内容: {state.matched_metrics[:2] if state.matched_metrics else None}")
            chosen_metric = self._parse_metric_choice(last_message, state.matched_metrics)
            print(f"[DEBUG entity_node] _parse_metric_choice结果: {chosen_metric}")
            if chosen_metric:
                entities.update(chosen_metric)
                print(f"[DEBUG entity_node] 用户选择了指标: {chosen_metric.get('metric_name')}")
                state.matched_metrics = None  # 清除选择状态
                state.needs_clarification = False  # 清除追问状态
                state.clarification_type = None  # 清除追问类型
                state.clarification_message = None  # 清除追问消息
                user_just_selected_metric = True  # 标记用户刚选择了指标

        # 链接业务术语到指标
        term_links = self.rule_engine.link_business_terms_enhanced(
            last_message,
            entities
        )

        # 如果实体链接返回空，检查是否是新的指标查询
        # 新指标查询的特征：包含指标相关的词（如"数"、"量"、"用户"等）
        # 如果是新的指标查询，即使 metric_id 已设置，也要清除（因为这是不同的指标）
        if not term_links:
            follow_up_only_indicators = ["定义", "口径", "规则", "怎么", "如何"]
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
            confirmation_words = ["是的", "好", "可以", "对的", "没错", "确定", "行", "ok", "yeah", "yes"]
            is_confirmation = last_message.strip() in confirmation_words or last_message.strip().lower() in ["ok", "yes", "yeah", "y"]
            if not is_pure_followup and inherited_metric and not user_just_selected_metric and not is_confirmation:
                if contains_metric_reference or (is_short_input and not is_time_word):
                    # 用户说了指标相关词但没匹配到，或者输入很短且不是时间词，清除继承
                    entities["metric_name"] = None
                    entities["metric_code"] = None
                    entities["metric_id"] = None
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
                        print(f"[DEBUG entity_node] LLM 识别到指标: {matched_metric}, confidence: {llm_result.get('confidence')}")

        entities.update(term_links)

        # 如果没有匹配到指标但有时间范围，也要提取
        if not term_links and not entities.get("time_range"):
            time_range = self._extract_time_range(last_message)
            if time_range:
                entities["time_range"] = time_range
                print(f"[DEBUG entity_node] 提取到时间范围: {time_range}")

        # 提取完整时间信息（用于追问和SQL组装）
        time_info = self._extract_time_info(last_message)
        if time_info:
            entities["time_info"] = time_info
            print(f"[DEBUG entity_node] 提取到完整时间信息: {time_info}")

        # 检查是否是业务术语查询（ASIN、SKU等）
        business_term_info = self.rule_engine.recognize_business_term(last_message)
        if business_term_info:
            # 设置业务术语标记，让后续节点知道这是业务术语查询
            entities["is_business_term"] = True
            entities["business_term_name"] = business_term_info.get("term")
            entities["business_term_description"] = business_term_info.get("description")
            entities["business_term_intent"] = business_term_info.get("intent")
            print(f"[DEBUG entity_node] 识别到业务术语查询: {business_term_info.get('term')}")

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
                                print(f"[GraphQuery] Found context for {metric_code}: "
                                      f"upstream={len(context.get('upstream', []))}, "
                                      f"downstream={len(context.get('downstream', []))}, "
                                      f"correlated={len(context.get('correlated', []))}")
                    except Exception as e:
                        if os.getenv("DEBUG"):
                            print(f"[GraphQuery] Query failed: {e}")
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
        if entities.get("time_range"):
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
            print(f"[DEBUG clarification] 应用默认值: {applied_defaults}")

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
        print(f"[DEBUG sql_gen] intent={state.current_intent}, entities={state.entities}")

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
                    print(f"[DEBUG sql_gen] 继承上轮实体: {state.entities}")
                else:
                    # 尝试从 last_valid_metric 获取（用于follow-up但中间有失败的查询）
                    last_metric = getattr(state, 'last_valid_metric', {})
                    if last_metric and (last_metric.get("metric_name") or last_metric.get("metric_code")):
                        state.entities["metric_name"] = last_metric.get("metric_name")
                        state.entities["metric_code"] = last_metric.get("metric_code")
                        state.entities["metric_id"] = last_metric.get("metric_id")
                        state.entities["unit"] = last_metric.get("unit")
                        state.entities["starrocks_sql"] = last_metric.get("starrocks_sql")
                        print(f"[DEBUG sql_gen] 继承last_valid_metric: {state.entities}")

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

        # 提取维度参数
        dimensions = self._extract_sql_dimensions(state.entities)
        print(f"[DEBUG _build_value_sql] 提取的维度参数: {dimensions}")

        # Step 1: 优先使用预置 SQL
        if starrocks_sql:
            # 如果有预置 SQL，应用维度参数调整
            adjusted_sql = self._apply_dimensions_to_sql(starrocks_sql, dimensions, state.entities, time_info)
            print(f"[DEBUG _build_value_sql] 维度调整后的SQL: {adjusted_sql}")

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
                print(f"[DEBUG sql_gen] contains_time_word=True, metric_code={metric_code}, metric_name={metric_name}, metric_id={metric_id}")
                actual_starrocks_sql = None
                if metric_id:
                    try:
                        metric_info = self.metric_client.get_metric(metric_id)
                        print(f"[DEBUG sql_gen] get_metric({metric_id}) returned: starrocks_sql={repr(metric_info.get('starrocks_sql', 'NOT_FOUND')[:100] if metric_info.get('starrocks_sql') else 'EMPTY')}")
                        if metric_info and metric_info.get("starrocks_sql"):
                            actual_starrocks_sql = metric_info.get("starrocks_sql")
                    except Exception as e:
                        print(f"[DEBUG sql_gen] 获取指标详情失败: {e}")

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
                    print(f"[DEBUG sql_gen] metric_code={metric_code}, metric_id={metric_id}, metric_name={metric_name}")
                    # 如果有 metric_code，优先用 metric_code 查询指标详情
                    if metric_code and metric_id:
                        try:
                            metric_info = self.metric_client.get_metric(metric_id)
                            print(f"[DEBUG sql_gen] get_metric result: {metric_info.get('name') if metric_info else 'None'}")
                            if metric_info:
                                # 用 metric_code 找到了指标，但 starrocks_sql 为空，说明这个指标没有查询SQL
                                # 搜索相关指标给用户选择
                                matched_metrics = self.metric_client.search_metrics(metric_name or last_message, limit=8)
                                print(f"[DEBUG sql_gen] matched_metrics count={len(matched_metrics)}")
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
                            print(f"[DEBUG sql_gen] get_metric失败: {e}")

                    # 降级：用 metric_name 或用户输入搜索
                    search_query = metric_name if metric_name else last_message
                    matched_metrics = self.metric_client.search_metrics(search_query, limit=8)
                    print(f"[DEBUG sql_gen] fallback search_query={search_query}, matched_metrics count={len(matched_metrics)}")
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
            print(f"[DEBUG] 获取维度配置失败: {e}")
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

        return dimensions

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

        # 从 SQL 提取表名
        table_name = self._extract_table_name(sql)

        # === 1. 处理时间范围（占位符替换 + 自动注入）===
        if time_info:
            start_date = time_info.get("start")
            end_date = time_info.get("end")
            # 先替换占位符
            if start_date:
                adjusted_sql = adjusted_sql.replace("{start_date}", f"'{start_date}'")
            if end_date:
                adjusted_sql = adjusted_sql.replace("{end_date}", f"'{end_date}'")
            # 如果没有占位符，自动追加到 WHERE
            if table_name and ("{start_date}" not in adjusted_sql and "{end_date}" not in adjusted_sql):
                if start_date:
                    time_conditions = [
                        f"fdate = '{start_date}'",
                        f"report_month = '{start_date[:7]}'" if len(start_date) >= 7 else None,
                        f"the_year = '{start_date[:4]}'" if len(start_date) >= 4 else None,
                    ]
                    for cond in [c for c in time_conditions if c]:
                        if "WHERE" in adjusted_sql.upper():
                            adjusted_sql += f" AND {cond}"
                        else:
                            adjusted_sql += f" WHERE {cond}"

        # === 2. 处理动态维度 (GROUP BY) ===
        dimension = entities.get("dimension")  # 如 "department"
        if dimension:
            # 有维度，保留 GROUP BY，从配置查列名
            if table_name:
                dim_configs = self._get_table_dimensions_cached(table_name)
                if dimension in dim_configs:
                    column = dim_configs[dimension].get("column_name", dimension)
                else:
                    column = dimension
            else:
                column = dimension
            adjusted_sql = adjusted_sql.replace("{dimension}", column)
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


    def _extract_time_range(self, text: str) -> Optional[str]:
        """从文本中提取时间范围（内部格式）"""
        return self._extract_time_from_text(text)

    def _build_sql_from_template(self, starrocks_sql: str, state: ConversationState) -> str:
        """从预置 SQL 模板构建查询"""
        # 如果预置 SQL 已经是完整查询，直接返回
        if "metric_id" in starrocks_sql.lower() or "metric_code" in starrocks_sql.lower():
            return starrocks_sql
        return starrocks_sql

    def execute_node(self, state: ConversationState) -> Dict[str, Any]:
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
                result = self.sql_generator.execute(
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
                    metric_name = state.entities.get("metric_name", "该指标")
                    return {
                        "answer": f"目前没有查到 {metric_name} 的数据。\n\n您可以：\n1. 查看该指标的业务口径：「业务口径呢」\n2. 查看技术口径：「技术口径呢」\n3. 换一个指标查询",
                        "suggest_questions": [f"{metric_name}的业务口径", "帮我查其他指标"],
                        "needs_clarification": False,
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
                    return {
                        "answer": answer,
                        "suggest_questions": self._generate_suggestions(state),
                        "needs_clarification": False,
                    }

        # 没有结果
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

        print(f"[DEBUG intent_feedback] 检测到用户纠正: {last_message}")

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
            print(f"[DEBUG intent_feedback] 记录反馈: predicted={state.current_intent}, correct={correct_intent}")

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
            print(f"[DEBUG intent_feedback] 记录反馈失败: {e}")


# 全局节点实例
conversation_nodes = ConversationNodes()
