"""
LLM 引擎 - 调用腾讯云 DeepSeek
"""
import os
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
from ai.graph.state import IntentResult, SQLGenerationResult, ClarificationDecision

# 加载 .env
load_dotenv()


class LLMEngine:
    """LLM 引擎"""

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("TENCENT_API_KEY", ""),
            base_url=os.getenv("TENCENT_API_URL", ""),
        )
        self.model = "ms-nbgbkz24"

    def recognize_intent(self, text: str) -> IntentResult:
        """LLM 意图识别"""
        prompt = f"""你是一个指标查询助手。用户的问题是："{text}"
请识别用户的意图，可选意图包括：
- query_value: 查询某个指标的值
- query_trend: 查询指标趋势
- query_comparison: 对比分析
- unknown: 无法识别

只返回意图名称，不要解释。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50,
            )
            intent = response.choices[0].message.content.strip().lower()

            # 验证意图
            valid_intents = ["query_value", "query_trend", "query_comparison", "unknown"]
            if intent not in valid_intents:
                intent = "unknown"

            return IntentResult(
                intent=intent,
                confidence=0.8,
                entities={}
            )
        except Exception as e:
            print(f"LLM 调用失败: {e}")
            return IntentResult(
                intent="unknown",
                confidence=0.0,
                entities={}
            )

    def recognize_intent_enhanced(self, text: str, inherited_entities: dict = None) -> IntentResult:
        """增强的意图识别 - 支持多轮上下文"""
        inherited = ""
        if inherited_entities:
            metric = inherited_entities.get("inherited_metric")
            if metric:
                inherited = f"\n上下文信息：用户正在查询指标「{metric}」，可继承此指标"

        prompt = f"""你是一个业务指标查询助手。请分析用户问题并提取关键信息。

用户问题：「{text}」{inherited}

请识别：
1. 意图（query_value=查数值, query_trend=查趋势, query_comparison=对比, greeting=打招呼, thanks=感谢, bye=告别）
2. 指标名称（如：访客数、订单量、销售额）
3. 时间范围（昨天、今天、本周、本月、上月、去年等）
4. 其他参数

以 JSON 格式返回：
{{"intent": "意图", "confidence": 0.9, "metric_name": "指标名", "time_range": "时间范围", "entities": {{}}}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()

            # 尝试解析 JSON
            import json
            try:
                # 提取 JSON 部分
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                result = json.loads(content)
                return IntentResult(
                    intent=result.get("intent", "unknown"),
                    confidence=result.get("confidence", 0.7),
                    entities={
                        "metric_name": result.get("metric_name"),
                        "time_range": result.get("time_range"),
                        **result.get("entities", {})
                    }
                )
            except json.JSONDecodeError:
                # JSON 解析失败，用简单方式提取
                return self._parse_intent_fallback(text, inherited_entities)

        except Exception as e:
            print(f"LLM 增强意图识别失败: {e}")
            return IntentResult(
                intent="query_value",
                confidence=0.5,
                entities={}
            )

    def _parse_intent_fallback(self, text: str, inherited_entities: dict = None) -> IntentResult:
        """意图识别回退 - 简单规则匹配"""
        text_lower = text.lower()

        # 意图识别
        intent = "query_value"
        if any(kw in text_lower for kw in ["趋势", "走势", "变化"]):
            intent = "query_trend"
        elif any(kw in text_lower for kw in ["对比", "比较", "同比", "环比"]):
            intent = "query_comparison"
        elif any(kw in text_lower for kw in ["你好", "hi", "hello", "在吗"]):
            intent = "greeting"
        # 元数据查询意图
        elif any(kw in text_lower for kw in ["业务口径", "技术口径", "定义", "指标说明", "是什么意思", "口径呢"]):
            intent = "query_metadata"
        # 数值查询意图
        elif any(kw in text_lower for kw in ["数据", "数值", "多少", "多少笔", "多少钱"]):
            intent = "query_value"

        # 时间范围
        time_range = None
        if any(kw in text_lower for kw in ["昨天", "昨日"]):
            time_range = "yesterday"
        elif any(kw in text_lower for kw in ["今天", "今日"]):
            time_range = "today"
        elif any(kw in text_lower for kw in ["本周", "这周"]):
            time_range = "this_week"
        elif any(kw in text_lower for kw in ["本月", "这月"]):
            time_range = "this_month"

        # 指标名称 - 从上下文继承
        metric_name = None
        if inherited_entities:
            metric_name = inherited_entities.get("inherited_metric")

        return IntentResult(
            intent=intent,
            confidence=0.6,
            entities={
                "metric_name": metric_name,
                "time_range": time_range,
            }
        )

    def generate_sql(
        self,
        question: str,
        entities: Dict[str, Any]
    ) -> Optional[SQLGenerationResult]:
        """LLM 生成 SQL"""
        # 从 entities 获取指标信息构建 prompt
        metric_info = ""
        if "metric_code" in entities:
            metric_info = f"指标编号: {entities['metric_code']}"
        if "metric_name" in entities:
            metric_info += f", 指标名称: {entities['metric_name']}"

        prompt = f"""你是一个 SQL 生成助手。根据用户问题生成 StarRocks SQL。

用户问题：{question}
{metric_info}

要求：
1. 只生成 SELECT 查询语句
2. 使用 StarRocks SQL 语法
3. 不要包含 DROP、DELETE、UPDATE、INSERT 等危险操作
4. 假设有一个表叫 metric_data，包含 metric_id, date, value, dept_id 等字段

直接返回 SQL，不要解释。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            sql = response.choices[0].message.content.strip()

            # 简单校验
            if any(kw in sql.lower() for kw in ["drop", "delete", "update", "insert"]):
                return None

            return SQLGenerationResult(
                sql=sql,
                params=entities,
                is_safe=True
            )
        except Exception as e:
            print(f"LLM SQL 生成失败: {e}")
            return None

    def generate_response(
        self,
        question: str,
        sql: str,
        result: Any,
        metric_name: str
    ) -> str:
        """生成自然语言回答"""
        prompt = f"""用户问：{question}
执行的 SQL：{sql}
查询结果：{result}
指标名称：{metric_name}

请用自然语言回答用户问题，简明扼要。如果结果为空或查询失败，请说明。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM 响应生成失败: {e}")
            return f"根据您的问题，{metric_name}的查询结果为：{result}"

    def extract_metric_from_text(self, text: str, available_metrics: list = None) -> Optional[Dict[str, Any]]:
        """
        从用户输入中提取可能的指标 - 用于短输入或模糊输入
        比如用户说"sku"，LLM 应该能识别出可能是指"缺货SKU数"等包含SKU的指标

        Args:
            text: 用户输入
            available_metrics: 可用的指标列表（如果为None，从规则引擎获取）

        Returns:
            可能的指标信息，包含 metric_name, confidence, reason
        """
        import json

        # 如果没有可用指标列表，从规则引擎获取
        if available_metrics is None:
            available_metrics = list(self._get_available_metrics())

        metrics_str = ", ".join(available_metrics[:50]) if available_metrics else "无"

        prompt = f"""你是一个业务指标匹配助手。用户输入了很短的内容，请判断他最可能想查询哪个指标。

## 用户输入
"{text}"

## 可用指标列表（部分）
{metrics_str}
{"...(还有更多指标)" if len(available_metrics) > 50 else ""}

## 任务
1. 分析用户输入，判断最可能匹配的指标
2. 如果能匹配到，返回匹配的指标名和置信度
3. 如果完全无法匹配，返回空

## 匹配规则
- "sku"、"SKU" → 可能匹配包含"SKU"的指标如"缺货SKU数"
- "访客"、"visitors" → 可能匹配"访客数"
- "订单"、"orders" → 可能匹配"订单量"、"订单数"
- 完全无法匹配任何指标 → 返回空

## 输出格式（必须是合法 JSON）
{{"matched": true/false, "metric_name": "可能的指标名", "confidence": 0.0-1.0, "reason": "匹配原因"}}

请输出JSON："""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()

            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content)

            if result.get("matched"):
                return {
                    "metric_name": result.get("metric_name"),
                    "confidence": result.get("confidence", 0.5),
                    "reason": result.get("reason", ""),
                }
            return None

        except json.JSONDecodeError as e:
            print(f"LLM 指标提取 JSON 解析失败: {e}")
            return None
        except Exception as e:
            print(f"LLM 指标提取失败: {e}")
            return None

    def _get_available_metrics(self) -> list:
        """获取可用的指标列表"""
        try:
            from ai.engine.rule_engine import RuleEngine
            rule_engine = RuleEngine()
            return list(rule_engine.metric_templates.keys())
        except:
            return []

    def decide_clarification(
        self,
        state: "ConversationState",
        missing_fields: list,
    ) -> ClarificationDecision:
        """
        LLM 决定是否需要追问 - 智能澄清模块（完整版）

        Args:
            state: 当前对话状态
            missing_fields: 缺少的字段列表

        Returns:
            ClarificationDecision: 包含是否追问、追问类型、追问内容等
        """
        import json
        from ai.graph.state import ClarificationType

        # 构建对话历史摘要
        history_summary = self._build_history_summary(state.messages)

        # 当前状态
        metric_name = state.entities.get("metric_name", "未知")
        time_range = state.entities.get("time_range", "未指定")
        dimension = state.entities.get("dimension", "未指定")
        asked_fields = state.asked_fields

        prompt = f"""你是一个 BI 查询助手 的对话策略专家。请严格按以下规则输出 JSON。

## 追问类型枚举（必须使用以下之一）
- metric_missing: 指标缺失（用户没说具体指标）
- time_range_missing: 时间范围缺失（没说昨天/本周/本月等）
- dimension_missing: 维度缺失（没说按地区/部门/产品分组）
- filter_condition_missing: 过滤条件缺失（没说只看某类订单/某个产品）
- action_intent_ambiguous: 操作意图模糊（不确定要查、改、还是导出）
- term_ambiguous: 术语歧义（同一个词有多个含义）
- scope_too_broad: 范围太宽（问题太泛化）
- high_risk_operation: 高风险操作（涉及删除、覆盖等）
- permission_required: 权限不足
- costly_query_warning: 高成本查询预警
- default_value_confirmation: 默认值确认（系统假设了默认值需用户确认）
- implicit_need_discovery: 隐含需求挖掘（用户可能需要但没说）

## 规则
1. 如果用户意图明确且所有必要信息已提供，返回 needs_clarification: false。
2. 如果缺少关键信息，返回 needs_clarification: true，并提出一个**具体、简洁、一次只问一个问题**的追问。
3. 追问时必须指定 clarification_type（使用上述枚举之一）。
4. 优先追问最重要的缺失字段。

## 当前状态
- 已识别指标: {metric_name}
- 已识别时间范围: {time_range}
- 已识别维度: {dimension}
- 缺少信息: {', '.join(missing_fields) if missing_fields else '无'}
- 已追问过的字段: {', '.join(asked_fields) if asked_fields else '无'}

## 对话历史
{history_summary}

## 已知默认值
- time_range 默认值: last_7_days（最近7天）
- dimension 默认值: all（不分维度）

## 输出格式（必须是合法 JSON，无其他内容）
{{"needs_clarification": true/false, "clarification_type": "追问类型枚举", "question": "追问内容（如果需要）", "reason": "原因", "missing_fields": [], "suggested_defaults": {{"字段名": "默认值"}}}}

## 示例
示例1 - 用户只说"销售额"：
输入: missing_fields=["time_range"], metric_name="销售额"
输出: {{"needs_clarification": true, "clarification_type": "time_range_missing", "question": "请问您想查询哪个时间段的销售额？昨天、本周还是本月？", "reason": "缺少时间范围", "missing_fields": ["time_range"], "suggested_defaults": {{"time_range": "last_7_days"}}}}

示例2 - 用户说"昨天访客数"：
输入: missing_fields=[], metric_name="访客数"
输出: {{"needs_clarification": false, "reason": "信息完整，无需追问", "missing_fields": []}}

示例3 - 用户说"销售数据"，无指标无时间：
输入: missing_fields=["metric_name", "time_range"], metric_name="未知"
输出: {{"needs_clarification": true, "clarification_type": "metric_missing", "question": "请问您想查询哪个业务指标？例如销售额、访客数或订单量？", "reason": "缺少指标名称", "missing_fields": ["metric_name"], "suggested_defaults": {{"time_range": "last_7_days"}}}}

请输出JSON："""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400,
            )
            content = response.choices[0].message.content.strip()

            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content)

            # 验证 clarification_type 是否合法
            clarification_type = result.get("clarification_type")
            if clarification_type not in ClarificationType.all_types():
                # 如果类型不合法，使用通用类型
                if "metric" in str(clarification_type).lower():
                    clarification_type = ClarificationType.METRIC_MISSING
                elif "time" in str(clarification_type).lower():
                    clarification_type = ClarificationType.TIME_RANGE_MISSING
                else:
                    clarification_type = ClarificationType.SCOPE_TOO_BROAD

            return ClarificationDecision(
                needs_clarification=result.get("needs_clarification", False),
                clarification_type=clarification_type,
                question=result.get("question"),
                reason=result.get("reason"),
                missing_fields=result.get("missing_fields", []),
                suggested_defaults=result.get("suggested_defaults", {}),
            )

        except json.JSONDecodeError as e:
            print(f"LLM 追问决策 JSON 解析失败: {e}, content: {content}")
            # 降级：使用规则判断
            return self._fallback_clarification(missing_fields, metric_name)
        except Exception as e:
            print(f"LLM 追问决策失败: {e}")
            # 降级：使用规则判断
            return self._fallback_clarification(missing_fields, metric_name)

    def _build_history_summary(self, messages: list) -> str:
        """构建对话历史摘要（最近5轮）"""
        if not messages:
            return "（无历史记录）"

        # 只取最近5条消息
        recent = messages[-5:] if len(messages) > 5 else messages
        lines = []
        for msg in recent:
            role = "用户" if msg.role == "user" else "助手"
            lines.append(f"- {role}: {msg.content[:50]}{'...' if len(msg.content) > 50 else ''}")
        return "\n".join(lines)

    def _fallback_clarification(self, missing_fields: list, metric_name: str) -> ClarificationDecision:
        """规则降级追问策略"""
        from ai.graph.state import ClarificationType

        if not missing_fields:
            return ClarificationDecision(
                needs_clarification=False,
                reason="信息完整",
            )

        # 简单规则：只问第一个缺失字段
        field = missing_fields[0]
        if field == "time_range":
            return ClarificationDecision(
                needs_clarification=True,
                clarification_type=ClarificationType.TIME_RANGE_MISSING,
                question=f"请问您想查询「{metric_name}」哪个时间段的数据？",
                reason=f"缺少时间范围，使用默认值: last_7_days",
                missing_fields=[field],
                suggested_defaults={"time_range": "last_7_days"},
            )
        elif field == "metric_name":
            return ClarificationDecision(
                needs_clarification=True,
                clarification_type=ClarificationType.METRIC_MISSING,
                question=f"请问您想查询哪个业务指标？例如销售额、访客数或订单量？",
                reason=f"缺少指标名称",
                missing_fields=[field],
            )
        elif field == "dimension":
            return ClarificationDecision(
                needs_clarification=True,
                clarification_type=ClarificationType.DIMENSION_MISSING,
                question=f"需要按什么维度查看？例如地区、部门或产品线？",
                reason=f"缺少维度信息",
                missing_fields=[field],
                suggested_defaults={"dimension": "all"},
            )

        return ClarificationDecision(
            needs_clarification=True,
            clarification_type=ClarificationType.SCOPE_TOO_BROAD,
            question=f"请提供您的{field}？",
            reason=f"缺少{field}",
            missing_fields=[field],
        )


class CircuitBreaker:
    """熔断器"""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    def call(self, func, *args, **kwargs):
        """带熔断的调用"""
        if self.state == "open":
            raise Exception("LLM 服务暂时不可用，请稍后再试")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e

    def on_success(self):
        """成功回调"""
        self.failures = 0
        self.state = "closed"

    def on_failure(self):
        """失败回调"""
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = "open"
