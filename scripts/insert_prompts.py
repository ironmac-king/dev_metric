#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
插入 prompt 配置到数据库
"""
import psycopg2
import json

# 连接数据库
conn = psycopg2.connect(
    host='192.168.1.225',
    port=5432,
    database='dev_metric',
    user='postgres',
    password='admin123'
)
cur = conn.cursor()

# 需要插入的 prompt 配置
prompts = [
    {
        "name": "intent_validation",
        "description": "LLM 审核纠正意图 - 规则引擎结果审核",
        "category": "nl2structure",
        "prompt_text": """你是一个业务指标查询助手。规则引擎对用户问题进行了初步分析，请审核并纠正。

## 用户问题
「{text}」{inherited}

## 规则引擎初步结果
- 识别意图: {rule_intent}
- 识别指标: {rule_entities.get('metric_name', '无')}
- 时间范围: {rule_entities.get('time_range', '无')}

## 可用的指标库
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
  "is_valid": true/false,
  "intent": "最终确认的意图",
  "confidence": 0.0-1.0,
  "metric_name": "指标名称",
  "metric_code": "指标编号",
  "time_range": "时间范围",
  "dimension": "维度",
  "correction_reason": "纠正原因",
  "entities": {{}}
}}

请输出JSON：""",
        "variables": ["text", "rule_intent", "rule_entities", "metrics_str", "graph_context", "inherited"],
        "status": 1
    },
    {
        "name": "clarification_decision",
        "description": "追问决策 - 决定是否需要追问以及追问内容",
        "category": "nl2structure",
        "prompt_text": """你是一个 BI 查询助手 的对话策略专家。请严格按以下规则输出 JSON。

## 追问类型枚举（必须使用以下之一）
- metric_missing: 指标缺失
- time_range_missing: 时间范围缺失
- dimension_missing: 维度缺失
- filter_condition_missing: 过滤条件缺失
- action_intent_ambiguous: 操作意图模糊
- term_ambiguous: 术语歧义
- scope_too_broad: 范围太宽
- high_risk_operation: 高风险操作
- permission_required: 权限不足
- costly_query_warning: 高成本查询预警
- default_value_confirmation: 默认值确认
- implicit_need_discovery: 隐含需求挖掘

## 规则
1. 如果用户意图明确且所有必要信息已提供，返回 needs_clarification: false。
2. 如果缺少关键信息，返回 needs_clarification: true，并提出一个具体、简洁、一次只问一个问题的追问。
3. 追问时必须指定 clarification_type（使用上述枚举之一）。
4. 优先追问最重要的缺失字段。

## 当前状态
- 已识别指标: {metric_name}
- 已识别时间范围: {time_range}
- 已识别维度: {dimension}
- 缺少信息: {missing_fields_str}
- 已追问过的字段: {asked_fields_str}

## 对话历史
{history_summary}

## 已知默认值
- time_range 默认值: last_7_days（最近7天）
- dimension 默认值: all（不分维度）

## 输出格式（必须是合法 JSON，无其他内容）
{{"needs_clarification": true/false, "clarification_type": "追问类型枚举", "question": "追问内容", "reason": "原因", "missing_fields": [], "suggested_defaults": {{"字段名": "默认值"}}}}

请输出JSON：""",
        "variables": ["metric_name", "time_range", "dimension", "missing_fields_str", "asked_fields_str", "history_summary"],
        "status": 1
    },
    {
        "name": "followup_expansion",
        "description": "追问补齐 - 将短文本追问补齐为完整问题",
        "category": "nl2structure",
        "prompt_text": """你是一个业务指标查询助手。用户在进行多轮对话。

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

直接返回补齐后的问题：""",
        "variables": ["text", "inherited_metric", "inherited_time", "comparison_type"],
        "status": 1
    },
    {
        "name": "metric_extraction",
        "description": "指标提取 - 从短文本中提取可能的指标",
        "category": "nl2structure",
        "prompt_text": """你是一个业务指标匹配助手。用户输入了很短的内容，请判断他最可能想查询哪个指标。

## 用户输入
"{text}"

## 可用指标列表（部分）
{metrics_str}

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

请输出JSON：""",
        "variables": ["text", "metrics_str"],
        "status": 1
    },
    {
        "name": "empty_result_followup",
        "description": "空数据追问 - 查询结果为空时生成智能追问和建议",
        "category": "nl2structure",
        "prompt_text": """用户查询数据为空，请分析可能原因并生成智能追问。

## 用户问题
{question}

## 识别的指标
{metric_name}

## 时间范围
{time_range}

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

请返回 JSON，不要包含其他内容。""",
        "variables": ["question", "metric_name", "time_range", "sql", "metrics_str"],
        "status": 1
    },
    {
        "name": "sql_generation_fallback",
        "description": "SQL 生成（LLM fallback）- 根据指标和时间生成 StarRocks SQL",
        "category": "sql_generation",
        "prompt_text": """你是一个 SQL 生成助手。根据用户问题生成 StarRocks SQL。

用户问题：{question}
{metric_info}

要求：
1. 只生成 SELECT 查询语句
2. 使用 StarRocks SQL 语法
3. 不要包含 DROP、DELETE、UPDATE、INSERT 等危险操作
4. 假设有一个表叫 metric_data，包含 metric_id, date, value, dept_id 等字段

直接返回 SQL，不要解释。""",
        "variables": ["question", "metric_info"],
        "status": 1
    }
]

# 插入配置
for p in prompts:
    # 检查是否已存在
    cur.execute("SELECT id FROM prompt_configs WHERE name = %s", (p["name"],))
    exists = cur.fetchone()

    if exists:
        # 更新
        cur.execute("""
            UPDATE prompt_configs
            SET description = %s, category = %s, prompt_text = %s,
                variables = %s, status = %s, updated_at = NOW()
            WHERE name = %s
        """, (p["description"], p["category"], p["prompt_text"],
              json.dumps(p["variables"]), p["status"], p["name"]))
        print(f"Updated: {p['name']}")
    else:
        # 插入
        cur.execute("""
            INSERT INTO prompt_configs (name, description, category, prompt_text, variables, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (p["name"], p["description"], p["category"], p["prompt_text"],
              json.dumps(p["variables"]), p["status"]))
        print(f"Inserted: {p['name']}")

conn.commit()

# 验证
cur.execute("SELECT name, category, status, length(prompt_text) as prompt_len FROM prompt_configs ORDER BY name")
rows = cur.fetchall()
print("\n=== 验证 prompt_configs ===")
for r in rows:
    print(f"{r[0]:30s} | {r[1]:15s} | status={r[2]} | {r[3]} chars")

cur.close()
conn.close()
print("\nDone!")