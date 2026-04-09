"""
LLM 引擎 - 调用腾讯云 DeepSeek
"""
import os
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv
from ai.graph.state import IntentResult, SQLGenerationResult, ClarificationDecision
from ai.config.logging_config import get_logger
from ai.engine.prompt_manager import get_prompt_manager

# 全局单例
_llm_engine = None


def get_llm_engine() -> "LLMEngine":
    """获取 LLM 引擎单例"""
    global _llm_engine
    if _llm_engine is None:
        _llm_engine = LLMEngine()
    return _llm_engine

logger = get_logger("ai.llm")

# 加载 .env
load_dotenv()


class LLMEngine:
    """LLM 引擎"""

    # Function Calling Schema - 用于意图识别和实体提取
    INTENT_RECOGNITION_FUNCTION = {
        "name": "recognize_intent",
        "description": "从用户问题中识别意图和提取实体，用于业务指标查询场景",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "意图类型",
                    "enum": ["query_value", "query_trend", "query_comparison", "query_metadata",
                             "query_ranking", "query_ratio", "query_retention", "greeting", "thanks", "bye", "unknown"]
                },
                "confidence": {
                    "type": "number",
                    "description": "置信度 0-1",
                    "minimum": 0,
                    "maximum": 1
                },
                "metric_name": {
                    "type": "string",
                    "description": "识别的指标名称，如'销售额'、'广告转化率'、'访客数'"
                },
                "time_range": {
                    "type": "string",
                    "description": "时间范围，如'近30天'、'本月'、'上周'"
                },
                "dimension": {
                    "type": "string",
                    "description": "维度粒度，如'日'、'月'、'品类'、'品牌'（用于 GROUP BY 分组）"
                },
                "dimension_values": {
                    "type": "string",
                    "description": "具体维度值，如'GROUP_3=有线网卡'、'region=华东'"
                },
                "top_n": {
                    "type": "integer",
                    "description": "Top N 排名数量，如 10 表示前 10 名"
                }
            },
            "required": ["intent", "confidence"]
        }
    }

    def __init__(self):
        self._config = None
        self._load_llm_config()

    def _load_llm_config(self):
        """从数据库加载 LLM 配置"""
        try:
            import httpx
            response = httpx.get(
                f"http://localhost:8080/api/v1/llm/configs",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                configs = data.get("data", [])

                # 找默认配置
                default_config = None
                for cfg in configs:
                    if cfg.get("is_default") == 1 or cfg.get("is_default") == True:
                        default_config = cfg
                        break

                # 如果没有默认的，用第一个
                if not default_config and configs:
                    default_config = configs[0]

                if default_config:
                    self._config = default_config
                    # OpenAI SDK expects base_url without /chat/completions
                    api_url = default_config.get("api_url", "")
                    if api_url.endswith("/chat/completions"):
                        api_url = api_url.rsplit("/chat/completions", 1)[0]
                    self.client = OpenAI(
                        api_key=default_config.get("api_key", ""),
                        base_url=api_url,
                    )
                    self.model = default_config.get("model_name", "deepseek-3.2")
                    logger.info(f"[LLMEngine] 已加载 LLM 配置: {default_config.get('name')}")
                    return

            # 配置加载失败，使用环境变量作为回退
            logger.info("[LLMEngine] 使用环境变量配置（LLM 配置未找到）")
            self._use_env_config()
        except Exception as e:
            logger.info(f"[LLMEngine] 加载 LLM 配置失败: {e}，使用环境变量")
            self._use_env_config()

    def _use_env_config(self):
        """使用环境变量配置"""
        self.client = OpenAI(
            api_key=os.getenv("TENCENT_API_KEY", ""),
            base_url=os.getenv("TENCENT_API_URL", ""),
        )
        self.model = os.getenv("LLM_MODEL", "ms-nbgbkz24")

    def reload_config(self):
        """重新加载配置（用于配置变更后刷新）"""
        self._config = None
        self._load_llm_config()

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
            logger.error(f"LLM 调用失败: {e}")
            return IntentResult(
                intent="unknown",
                confidence=0.0,
                entities={}
            )

    def recognize_intent_enhanced(self, text: str, inherited_entities: dict = None) -> IntentResult:
        """
        增强的意图识别 - 使用 Function Calling 替代 Prompt 解析

        通过 tools 参数直接获取结构化输出，避免 JSON 解析错误
        """
        # 构建继承上下文的提示
        inherited_context = ""
        if inherited_entities:
            metric = inherited_entities.get("inherited_metric")
            if metric:
                inherited_context = f"\n（上下文：用户正在查询指标「{metric}」，可继承此指标）"

        # 系统提示
        system_prompt = """你是一个专业的业务指标查询助手，擅长从用户的自然语言中准确提取结构化信息。

【指标知识】
- 常见指标：销售额、订单量、访客数、广告转化率、页面访问量、加购率、客单价
- 指标编号格式：MKI-02-0001（格式：MKI-领域-序号）
- 指标域：营销域、服务域、用户域
- 维度类型：日、月、年（时间维度）、品类、品牌、渠道、地区、平台（业务维度）

【意图类型】
- query_value: 查询指标数值（如"销售额是多少"、"近30天访客数"）
- query_trend: 查询指标趋势（如"销售额趋势"、"走势怎么样"）
- query_comparison: 对比分析（如"环比"、"同比"、"对比"）
- query_metadata: 查询元数据（如"业务口径"、"技术口径"、"定义"）
- query_ranking: 排名分析（如"最高的品类"、"前10名品牌"）
- query_ratio: 占比分析（如"占比"、"比例"）
- greeting: 打招呼
- thanks: 感谢
- bye: 告别

【重要】
- 如果用户提到"各平台"、"各地区"、"各品类"等多维度分组需求，在 dimension 字段填入对应的维度类型
- 如果用户提到"第一名"、"前10"、"最高的"等排名需求，设置 top_n 参数
- 时间表达优先使用标准描述如"近30天"、"本月"、"上周"

【区分维度类型和维度值】
- 维度类型是分类名，如"品类"、"平台"、"渠道"，出现在 dimension 字段
- 维度值是具体名称，如"智能云存储"、"天猫"、"京东"，出现在 dimension_values 字段

【Few-shot 示例】
用户问题：「今年智能云存储销售额是多少」
返回：{"intent": "query_value", "metric_name": "销售额", "time_range": "今年", "dimension": "品类", "dimension_values": "智能云存储"}

用户问题：「天猫平台的订单量」
返回：{"intent": "query_value", "metric_name": "订单量", "dimension": "平台", "dimension_values": "天猫"}

用户问题：「各品类销售额是多少」
返回：{"intent": "query_value", "metric_name": "销售额", "dimension": "品类", "dimension_values": null}

用户问题：「今年京东渠道的转化率」
返回：{"intent": "query_value", "metric_name": "转化率", "time_range": "今年", "dimension": "渠道", "dimension_values": "京东"}
"""

        try:
            # 使用纯文本 Prompt + JSON 解析（腾讯云 DeepSeek 不支持 Function Calling）
            user_content = f"""用户问题：「{text}」{inherited_context}

请以 JSON 格式返回识别结果，格式如下：
{{"intent": "意图", "confidence": 0.0-1.0, "metric_name": "指标名称", "time_range": "时间范围", "dimension": "维度", "dimension_values": "维度值", "top_n": 数字}}

只返回 JSON，不要其他内容。"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,
                max_tokens=300,
            )

            content = response.choices[0].message.content.strip()
            logger.debug(f"[recognize_intent_enhanced] LLM 返回: {content}")

            # 解析 JSON
            import json
            # 提取 JSON 部分（可能包含在 ```json ``` 中）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content)

            # 构建 entities
            entities = {}
            if result.get("metric_name"):
                entities["metric_name"] = result["metric_name"]
            if result.get("time_range"):
                entities["time_range"] = result["time_range"]
            if result.get("dimension"):
                entities["dimension"] = result["dimension"]
            if result.get("dimension_values"):
                entities["dimension_values"] = result["dimension_values"]
            if result.get("top_n"):
                entities["top_n"] = result["top_n"]

            return IntentResult(
                intent=result.get("intent", "unknown"),
                confidence=result.get("confidence", 0.7),
                entities=entities
            )

        except json.JSONDecodeError as e:
            logger.warning(f"[recognize_intent_enhanced] JSON 解析失败: {e}，降级处理")
            return self._parse_intent_fallback(text, inherited_entities)
        except Exception as e:
            logger.error(f"[recognize_intent_enhanced] LLM 调用失败: {e}")
            return self._parse_intent_fallback(text, inherited_entities)

    def expand_followup_question(self, text: str, inherited_metric: str, inherited_time: str = None, comparison_type: str = None) -> str:
        """
        将短文本追问补齐为完整问题

        Args:
            text: 用户输入的短文本（如"环比呢"）
            inherited_metric: 上轮对话中的指标名（如"页面访问量"）
            inherited_time: 上轮对话中的时间表达（如"上月"、"本月"等）
            comparison_type: 对比类型（"环比"或"同比"），如果为None则从text推断

        Returns:
            补齐后的完整问题
        """
        # 从text推断对比类型
        if comparison_type is None:
            if "环比" in text:
                comparison_type = "环比"
            elif "同比" in text:
                comparison_type = "同比"
            else:
                comparison_type = "环比"  # 默认

        time_hint = f"上轮时间是「{inherited_time}」" if inherited_time else "上轮时间是「上月」"

        prompt = f"""你是一个业务指标查询助手。用户在进行多轮对话。

当前轮用户说：「{text}」
上轮查询的指标是：「{inherited_metric}」
{time_hint}

请将用户的短文本追问补齐为完整的问题描述。

规则：
1. 直接返回补齐后的问题，不要解释
2. 保持原有的对比类型（环比/同比）
3. 时间必须继承上轮的时间，不能自己推断新时间
4. 补齐后的问题应该像用户直接说出来的一样自然

示例：
- 上轮"上月销量同比是多少"，本轮"环比呢" → "上月销量环比是多少"
- 上轮"本月广告花费"，本轮"同比呢" → "本月广告花费同比是多少"
- 上轮"上周转化率"，本轮"趋势呢" → "上周转化率趋势是什么"

直接返回补齐后的问题："""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100,
            )
            expanded = response.choices[0].message.content.strip()
            logger.info(f"[expand_followup] '{text}' + '{inherited_metric}' → '{expanded}'")
            return expanded
        except Exception as e:
            logger.error(f"[expand_followup] 补齐失败: {e}")
            # 降级处理：直接拼接
            if comparison_type == "环比":
                return f"上月{inherited_metric}环比是多少"
            else:
                return f"上月{inherited_metric}同比是多少"

    def validate_and_correct_intent(
        self,
        text: str,
        rule_intent: str,
        rule_entities: dict,
        available_metrics_info: dict = None,
        inherited_entities: dict = None,
        metric_context: dict = None
    ) -> IntentResult:
        """
        LLM 审核并纠正规则引擎的结果

        Args:
            text: 用户输入
            rule_intent: 规则引擎识别的意图
            rule_entities: 规则引擎识别的实体
            available_metrics_info: 可用的指标完整信息（dict，key为指标名）
            inherited_entities: 继承的上下文
            metric_context: 指标知识图谱上下文（包含上游、下游、相关指标）

        Returns:
            IntentResult: LLM 审核后的最终结果
        """
        import json

        # 获取指标列表和完整信息
        if available_metrics_info is None:
            available_metrics_info = {}

        # 构建指标列表字符串（格式化输出）
        metrics_lines = []
        for name, info in available_metrics_info.items():
            if isinstance(info, dict):
                code = info.get("metric_code", "")
                unit = info.get("unit", "")
                metrics_lines.append(f"- {name} ({code}) - 单位: {unit}" if unit else f"- {name} ({code})")
        metrics_str = "\n".join(metrics_lines[:50])  # 最多50个
        if len(metrics_lines) > 50:
            metrics_str += f"\n...（还有 {len(metrics_lines) - 50} 个指标）"

        inherited = ""
        if inherited_entities:
            metric = inherited_entities.get("inherited_metric")
            if metric:
                inherited = f"\n继承的上下文：用户上一轮正在查询指标「{metric}」"

        # 构建知识图谱上下文
        graph_context = ""
        if metric_context:
            upstream = metric_context.get("upstream", [])
            downstream = metric_context.get("downstream", [])
            correlated = metric_context.get("correlated", [])

            if upstream:
                upstream_str = ", ".join([f"「{m['name']}」" for m in upstream[:5]])
                graph_context += f"\n上游指标（影响当前指标）：{upstream_str}"
            if downstream:
                downstream_str = ", ".join([f"「{m['name']}」" for m in downstream[:5]])
                graph_context += f"\n下游指标（被当前指标影响）：{downstream_str}"
            if correlated:
                correlated_str = ", ".join([f"「{m['name']}」" for m in correlated[:5]])
                graph_context += f"\n相关指标：{correlated_str}"

        prompt = f"""你是一个业务指标查询助手。规则引擎对用户问题进行了初步分析，请审核并纠正。

## 用户问题
「{text}」{inherited}

## 规则引擎初步结果
- 识别意图: {rule_intent}
- 识别指标: {rule_entities.get('metric_name', '无')}
- 时间范围: {rule_entities.get('time_range', '无')}

## 可用的指标库（{len(metrics_lines)} 个指标）
{metrics_str if metrics_str else '无'}

## 指标知识图谱上下文
{graph_context if graph_context else '（暂无图谱数据）'}

## 你的任务
1. 判断规则引擎的结果是否正确
2. 如果正确，保持原结果
3. 如果错误或不完整，纠正它
4. **重要**：如果用户问的是指标，必须从上面的指标库中选择，不要瞎编指标名
5. 从指标库选择时，注意中英文名称的对应（如"访客数"和"visitors"是同一个指标）
6. **关键**：如果用户问题中包含泛指词如"各平台"、"各地区"、"各维度"等，说明用户想要多维度分组查询。但指标库中一般没有"各平台X指标"这种指标，只有具体平台的具体指标。此时应该：
   - 识别用户实际想查询的基础指标（如"销售额"）
   - 在entities中设置dimension字段为用户提到的维度
   - 保持is_valid=True，让后续流程处理维度追问

## 意图类型说明
- query_value: 查询指标数值
- query_trend: 查询指标趋势（上升/下降）
- query_comparison: 对比分析（对比两个时间/维度）
- query_metadata: 查询指标元数据（业务口径、技术口径、定义等）
- greeting: 打招呼
- thanks: 感谢
- bye: 告别

## 输出格式（必须是合法 JSON）
{{
  "is_valid": true/false,  // 规则引擎结果是否正确
  "intent": "最终确认的意图",
  "confidence": 0.0-1.0,  // 置信度
  "metric_name": "指标名称（必须从指标库中选择）",
  "metric_code": "指标编号",
  "time_range": "时间范围",
  "dimension": "维度（如平台、地区等，如果用户提到的话）",
  "correction_reason": "纠正原因（如果纠正了的话）",
  "entities": {{}}
}}

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

            is_valid = result.get("is_valid", True)
            correction_reason = result.get("correction_reason", "")

            # 如果纠正了，打印原因
            if not is_valid and correction_reason:
                logger.info(f"[LLM] 纠正意图: {correction_reason}")

            # 如果 LLM 返回了指标名，尝试从指标库中获取更多信息
            metric_name = result.get("metric_name")
            metric_code = result.get("metric_code")
            if metric_name and available_metrics_info:
                if metric_name in available_metrics_info:
                    info = available_metrics_info[metric_name]
                    if isinstance(info, dict) and not metric_code:
                        metric_code = info.get("metric_code", "")
                # 尝试用 metric_code 查找
                if not metric_code:
                    for name, info in available_metrics_info.items():
                        if isinstance(info, dict) and info.get("metric_code") == metric_code:
                            metric_name = name
                            break

            # 提取维度信息（LLM 返回在顶层）
            dimension = result.get("dimension")

            # 构建 entities
            entities = {
                "metric_name": metric_name,
                "metric_code": metric_code,
                "time_range": result.get("time_range"),
                **result.get("entities", {})
            }
            # 添加维度（如果 LLM 识别到了）
            if dimension:
                entities["dimension"] = dimension

            return IntentResult(
                intent=result.get("intent", rule_intent),
                confidence=result.get("confidence", 0.7),
                entities=entities
            )

        except json.JSONDecodeError as e:
            logger.info(f"[LLM] 意图审核 JSON 解析失败: {e}")
            # 解析失败，使用规则引擎结果
            return IntentResult(
                intent=rule_intent,
                confidence=0.5,
                entities=rule_entities
            )
        except Exception as e:
            logger.info(f"[LLM] 意图审核失败: {e}")
            return IntentResult(
                intent=rule_intent,
                confidence=0.5,
                entities=rule_entities
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
            logger.error(f"LLM SQL 生成失败: {e}")
            return None

    def generate_response(
        self,
        question: str,
        sql: str,
        result: Any,
        metric_name: str,
        unit: str = ""
    ) -> str:
        """生成自然语言回答"""
        unit_hint = f"单位：{unit}" if unit else ""
        prompt = f"""用户问：{question}
执行的 SQL：{sql}
查询结果：{result}
指标名称：{metric_name}
{unit_hint}

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
            logger.error(f"LLM 响应生成失败: {e}")
            return f"根据您的问题，{metric_name}的查询结果为：{result}"

    def generate_empty_result_followup(
        self,
        question: str,
        metric_name: str,
        time_range: str,
        sql: str,
        available_metrics: list = None,
    ) -> Dict[str, Any]:
        """
        当查询结果为空时，调用 LLM 生成智能追问和建议。
        分析可能原因并给出具体建议。
        """
        import json

        if available_metrics is None:
            available_metrics = list(self._get_available_metrics())

        # available_metrics 可能是字符串列表，也可能是字典列表
        metric_names = []
        for m in available_metrics[:30]:
            if isinstance(m, str):
                metric_names.append(m)
            elif isinstance(m, dict):
                metric_names.append(m.get("metric_name", "") or m.get("metric_code", "") or "")
        metrics_str = ", ".join([n for n in metric_names if n])

        prompt = f"""用户查询数据为空，请分析可能原因并生成智能追问。

## 用户问题
{question}

## 识别的指标
{metric_name or "未知"}

## 时间范围
{time_range or "未指定"}

## 执行的 SQL
{sql}

## 系统中的可用指标（部分）
{metrics_str}

请分析并返回 JSON 格式的建议，包含以下字段：
- analysis: 分析数据为空的可能原因（1-2句话）
- suggestions: 建议用户采取的行动数组，每个建议包含:
  - type: "time_range" | "metric_alternative" | "check_definition" | "retry"
  - text: 具体的建议问题（用户可以直接问的自然语言）
  - reason: 为什么要这样建议

请返回 JSON，不要包含其他内容。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个智能数据分析助手。当用户查询的数据为空时，你要分析可能的原因并给出具体、可操作的建议。建议要具体到用户可以直接复制粘贴提问的程度。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=800,
            )
            content = response.choices[0].message.content.strip()

            # 尝试解析 JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            return {
                "analysis": result.get("analysis", "暂无数据"),
                "suggestions": result.get("suggestions", []),
                "needs_clarification": True,
            }
        except Exception as e:
            logger.error(f"LLM 追问生成失败: {e}")
            # 降级：返回通用建议
            return {
                "analysis": "未能查到数据，可能该指标在指定时间段内没有记录。",
                "suggestions": [
                    {"type": "time_range", "text": f"{metric_name}最近有数据吗", "reason": "检查指标是否有近期数据"},
                    {"type": "check_definition", "text": f"{metric_name}的业务口径是什么", "reason": "确认指标口径是否正确"},
                ],
                "needs_clarification": False,
            }

    def _get_available_metrics(self) -> list:
        """获取可用指标列表"""
        try:
            import httpx
            response = httpx.get(
                f"http://localhost:8080/api/v1/metadata/metrics",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("metrics", [])
        except Exception:
            pass
        return []

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
            logger.error(f"LLM 指标提取 JSON 解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM 指标提取失败: {e}")
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
            logger.error(f"LLM 追问决策 JSON 解析失败: {e}, content: {content}")
            # 降级：使用规则判断
            return self._fallback_clarification(missing_fields, metric_name)
        except Exception as e:
            logger.error(f"LLM 追问决策失败: {e}")
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

    def call(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """
        通用 LLM 调用接口

        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            LLM 返回的文本内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.info(f"[LLMEngine] LLM 调用失败: {e}")
            return ""

    def generate_query_state(self, question: str, session_id: str = "", context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        LLM 生成 QueryState JSON

        Args:
            question: 用户问题
            session_id: 会话 ID
            context: 上下文信息（如上轮 QueryState）

        Returns:
            QueryState 字典
        """
        import json
        from ai.engine.prompt_manager import get_prompt_manager

        prompt_manager = get_prompt_manager()
        base_prompt = prompt_manager.get_nl2querystate_prompt()

        # 如果有上下文，添加到 prompt
        context_info = ""
        if context:
            context_info = f"\n\n【上轮上下文】\n上轮 QueryState: {json.dumps(context, ensure_ascii=False, indent=2)}"
            # 追问场景：用户可能只说了"环比呢"、"同比呢"
            short_question_keywords = ["呢", "呢？", "？", "啊", "哦", "嗯", "再", "还"]
            is_followup = len(question) < 10 or any(kw in question for kw in short_question_keywords)
            if is_followup and context.get("metric"):
                context_info += "\n注意：这是追问，上轮已有指标信息，请继承上轮的 metric 和 time"

        prompt = f"""{base_prompt}{context_info}

【用户问题】
{question}

请输出 JSON："""

        logger.info(f"[LLMEngine] 生成 QueryState, question={question[:50]}")

        response = self.call(prompt, temperature=0.3, max_tokens=3000)

        if not response:
            logger.warning("[LLMEngine] QueryState 生成失败，返回空")
            return {}

        # 解析 JSON
        try:
            # 尝试提取 JSON（可能包含在 ```json ``` 中）
            json_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response

            query_state = json.loads(json_str)
            logger.info(f"[LLMEngine] QueryState 生成成功: intent={query_state.get('intent')}")
            return query_state
        except json.JSONDecodeError as e:
            logger.error(f"[LLMEngine] QueryState JSON 解析失败: {e}, response={response[:200]}")
            return {}

    def generate_prompt_improvement(
        self,
        current_prompt: str = "",
        task_name: str = "自然语言转结构化实体",
        task_description: str = "意图识别、实体提取、时间解析",
        mode: str = "improve"  # "improve" or "regenerate"
    ) -> str:
        """
        生成或优化 Prompt

        Args:
            current_prompt: 当前 Prompt（优化模式需要）
            task_name: 任务名称
            task_description: 任务描述
            mode: "improve" 基于现有优化, "regenerate" 重新生成

        Returns:
            生成的 Prompt 内容
        """
        if mode == "improve" and current_prompt:
            system_prompt = """你是一个专业的 Prompt 工程师，擅长优化 NL2Structure Prompt。

请分析当前 Prompt 的不足，从以下角度优化：
1. 意图识别准确性 - 是否覆盖所有常见场景
2. 时间表达覆盖度 - 是否支持各种时间表达
3. 业务场景完整性 - 跨境电商、供应链、人力资源
4. 示例质量 - 示例是否足够多且有代表性
5. 约束条件 - 是否清晰无歧义

请直接输出优化后的完整 Prompt，不要任何解释。"""
            user_prompt = f"""=== 当前 Prompt ===
{current_prompt}

=== 任务信息 ===
任务名称：{task_name}
任务描述：{task_description}

请输出优化后的完整 Prompt。"""
        else:
            system_prompt = """你是一个专业的 Prompt 工程师，擅长为业务指标查询系统生成 NL2Structure Prompt。

NL2Structure Prompt 用于将用户自然语言转换为结构化数据，输出格式为 JSON。

输出格式要求：
- intent: 查询意图 (query_value/query_trend/query_comparison/query_metadata/greeting/thanks/bye/unknown)
- metric_name: 指标名称
- time_range: 时间范围 {type, start, end, original}
- dimension: 维度
- comparison_period: 对比周期

请生成一个完整的 Prompt，覆盖所有常见场景。"""
            user_prompt = f"""任务名称：{task_name}
任务描述：{task_description}

请直接输出完整的 Prompt 内容，不要任何解释。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.info(f"[LLMEngine] Prompt 生成失败: {e}")
            return ""


    def suggest_dimension_correction(self, query: str, candidates: List[str]) -> str:
        """
        LLM 生成维度值纠错建议

        Args:
            query: 用户输入的维度值
            candidates: 候选维度值列表

        Returns:
            纠错建议，如"您是指'有线网卡'吗？"
        """
        if not candidates:
            return ""

        candidates_str = ", ".join([f"'{c}'" for c in candidates])
        prompt = f"""用户输入的维度值 '{query}' 没有精确匹配。
最相似的候选值：{candidates_str}

请生成一句友好的纠错建议，例如：
"您是指'有线网卡'吗？"

只输出建议语句，不要其他内容。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.info(f"[LLMEngine] 维度纠错建议生成失败: {e}")
            return ""

    async def stream(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2000):
        """
        流式 LLM 调用（用于 SSE 输出）

        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Yields:
            str: LLM 返回的文本片段
        """
        try:
            # OpenAI SDK 的流式调用
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            try:
                logger.info(f"[LLMEngine] 流式 LLM 调用失败: {e}")
            except Exception:
                pass  # 忽略日志编码错误
            try:
                error_str = str(e)
                yield f"LLM 调用出错: {error_str}"
            except Exception:
                yield "LLM 调用出错: (编码错误无法显示)"

    async def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4000) -> str:
        """
        非流式 LLM 调用（一次性返回完整结果）

        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            str: LLM 返回的完整文本
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            try:
                logger.info(f"[LLMEngine] LLM 调用失败: {e}")
            except Exception:
                pass
            raise e


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
