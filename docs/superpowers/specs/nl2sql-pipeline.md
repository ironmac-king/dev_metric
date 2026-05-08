# 智能问数（NL2SQL）完整链路文档

> 以问题「最近15天销售额最高的二级品类是啥，还有同比，环比是多少」为例，贯穿整个前后端链路。

---

## 一、系统架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│  前端 (Vue 3, port 3001)                                            │
│  Ask.vue  ─── 用户输入问题 ─── 表格展示 + 图表展示                    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ HTTP POST /api/v1/ask
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Go 后端 (Gin, port 8080)                                            │
│  handler/ask.go::AskQuestion  ─── 会话管理 ─── 调用 Python AI 服务    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ HTTP POST localhost:8081/api/v1/ask
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Python AI 服务 (FastAPI, port 8081)                                  │
│                                                                     │
│  main.py::ask_question()                                             │
│       │                                                             │
│       ├── get_engine("langgraph")  →  LangGraphEngine                │
│       │                                                             │
│       └── response_node()  ←  列 rename + 拼自然语言回答             │
│                                  │                                    │
│                                  ▼                                    │
│                          FormatStage                                  │
│               (列 rename: GROUP_2 → 二级品类,                         │
│                列排序: 维度列 → 指标列 → 对比列)                        │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ SQL: SELECT GROUP_2, SUM(ORDERED_PRODUCTSALES) ...
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  StarRocks (port 9030)                                               │
│  dws.DWS_IMC_BUSINESSREPORT  ─── 返回原始数据                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、完整处理流程

问题：「最近15天销售额最高的二级品类是啥，还有同比，环比是多少」

---

### 步骤 1：前端发起请求

**文件：** `web/src/views/Ask.vue`

用户在输入框输入问题，点击发送。

```javascript
// Ask.vue
async function sendMessage() {
  const response = await request.post('/api/v1/ask', {
    question: "最近15天销售额最高的二级品类是啥，还有同比，环比是多少",
    session_id: sessionId,
    engine_type: "langgraph",
    page: 1,
    page_size: 10
  })
  // 收到响应后：
  // - answer: 自然语言回答
  // - result_data: 表格数据（用于 el-table 展示）
  // - comparison_results: 同比环比数据（用于图表）
  // - sql: 生成的 SQL（用于显示）
}
```

**前端请求体：**
```json
{
  "question": "最近15天销售额最高的二级品类是啥，还有同比，环比是多少",
  "session_id": "sess_20260406_001",
  "engine_type": "langgraph",
  "page": 1,
  "page_size": 10
}
```

---

### 步骤 2：Go 后端接收请求

**文件：** `cmd/server/internal/api/handler/ask.go`

```go
// AskQuestion 处理函数
func AskQuestion(c *gin.Context) {
    var req model.AskRequest
    json.NewDecoder(c.Body).Decode(&req)

    // 调用 Python AI 服务
    pythonURL := "http://localhost:8081/api/v1/ask"
    resp, _ := http.Post(pythonURL, "application/json", bytes.NewBuffer(buf))

    // 将 Python 响应转发回前端
    json.NewEncoder(c).Encode(pythonResp)
}
```

**Go 后端不处理任何业务逻辑**，只是透传请求到 Python AI 服务。

---

### 步骤 3：Python FastAPI 入口

**文件：** `ai/main.py` 第 264 行

```python
async def ask_question(req: AskRequest):
    engine = get_engine(engine_type)  # "langgraph" 或 "llm"
    result = await engine.process(
        question=req.question,
        session_id=session_id,
        page=req.page,
        page_size=req.page_size
    )
    # result 包含:
    # - answer: str
    # - result_data: list[dict]  (中文列名)
    # - comparison_results: list[dict]
    # - sql: str
    # - suggest: list[str]
    return result
```

---

### 步骤 4：LangGraph 引擎调度

**文件：** `ai/engine/langgraph_engine.py`

LangGraph 是一个状态机，按预设的边顺序执行各节点。

```python
async def process(question, session_id, ...):
    # 1. 获取或初始化状态
    state = await aget_state(session_id)
    state.messages.append(UserMessage(content=question))

    # 2. 执行状态机（自动按边顺序执行）
    result = await self.app.ainvoke(state, config)

    # 3. 二次调用 response_node 生成最终回答
    response_state = build_response_state(result)
    final = conversation_nodes.response_node(response_state)

    return final
```

**LangGraph StateGraph 执行顺序：**
```
intent → entity → sql_gen → execute → comparison → response
              ↓
        [条件边]
      needs_clarification?
         ↙     ↘
       True    False
         |       |
      response  execute
```

---

### 步骤 5：Stage 1 — 意图识别

**文件：** `ai/graph/nodes.py` `intent_node()`

**输入：** `messages[-1].content`

**处理流程：**

```
1. Step 0: 处理追问
   - 检测到是完整问题（非短词），跳过追问恢复逻辑

2. Step 1: 上下文继承
   - session 为新会话，无上轮 context，跳过

3. Step 2: LLM 意图识别
   - 调用 llm_engine.recognize_intent_enhanced()
   - 返回:
     {
       "current_intent": "query_comparison",
       "entities": {
         "metric_name": "销售额",
         "time_range": "最近15天",
         "dimension": "二级品类",
         "top_n": 10,
         "comparison_type": ["同比", "环比"]
       }
     }

4. 对比关键词覆盖
   - 检测到"同比"/"环比"，强制设置 intent = "query_comparison"
```

**输出：**
```python
{
    "current_intent": "query_comparison",
    "entities": {
        "metric_name": "销售额",
        "time_range": "最近15天",
        "dimension": "二级品类",
        "top_n": 10,
        "comparison_type": ["同比", "环比"]
    }
}
```

---

### 步骤 6：Stage 2 — 实体链接

**文件：** `ai/graph/nodes.py` `entity_node()`

**输入：** `state.entities` from intent_node

**处理流程：**

```
1. 上下文继承
   - 新会话，无继承数据

2. 业务术语链接
   - "销售额" → metric_code: "MKI-02-0001"
   - 获取 starrocks_sql:
     SELECT GROUP_2, SUM(ORDERED_PRODUCTSALES) AS ORDERED_PRODUCTSALES
     FROM dws.DWS_IMC_BUSINESSREPORT
     WHERE FDATE >= '{start}' AND FDATE <= '{end}'
     GROUP BY GROUP_2

3. 时间解析
   - "最近15天" → TimeParser 解析
   - end_date = 今天 - 1 = 2026-04-05
   - start_date = 2026-03-22

4. 维度提取
   - "二级品类" → dimension: "二级品类"
   - 去 dim_configs 里查: "二级品类" → column_name: "GROUP_2"
```

**输出：**
```python
{
    "entities": {
        "metric_name": "销售额",
        "metric_code": "MKI-02-0001",
        "starrocks_sql": "SELECT GROUP_2, SUM(ORDERED_PRODUCTSALES) AS ORDERED_PRODUCTSALES ...",
        "time_range": "最近15天",
        "time_info": {
            "type": "date_range",
            "start_date": "2026-03-22",
            "end_date": "2026-04-05"
        },
        "dimension": "二级品类",
        "top_n": 10
    }
}
```

---

### 步骤 7：Stage 3 — SQL 生成

**文件：** `ai/graph/nodes.py` `sql_build_node()`

**输入：** `state.entities` with `starrocks_sql` + `time_info`

**处理流程：**

```
1. 构建 QueryState
   - metric.starrocks_sql: 预置 SQL 模板
   - time: {start: 2026-03-22, end: 2026-04-05}

2. SQLBuilder.build_sql() 处理:
   a. 渲染 starrocks_sql 中的 {start_date} / {end_date} 占位符
   b. 替换 {dimension} 占位符为 "GROUP_2"
   c. 添加 WHERE 条件: FDATE >= '2026-03-22' AND FDATE <= '2026-04-05'
   d. 添加 GROUP BY GROUP_2
   e. 添加 ORDER BY SUM(ORDERED_PRODUCTSALES) DESC LIMIT 10
```

**最终生成的 SQL：**
```sql
SELECT
    `GROUP_2` AS `二级品类`,
    SUM(ORDERED_PRODUCTSALES) AS `总销售额`
FROM dws.DWS_IMC_BUSINESSREPORT
WHERE FDATE >= '2026-03-22'
  AND FDATE <= '2026-04-05'
GROUP BY `GROUP_2`
ORDER BY SUM(ORDERED_PRODUCTSALES) DESC
LIMIT 10 OFFSET 0
```

**输出：**
```python
{
    "generated_sql": "SELECT `GROUP_2` ... GROUP BY `GROUP_2` ORDER BY ... LIMIT 10 OFFSET 0",
    "sql_params": {}
}
```

---

### 步骤 8：Stage 4 — SQL 执行

**文件：** `ai/graph/nodes.py` `execute_node()`

**输入：** `state.generated_sql`

**处理流程：**

```
1. 判断 intent != "greeting/thanks/bye"，继续执行

2. 调用 SQLGenerator.execute()
   → HTTP POST http://localhost:8080/api/v1/query/execute
   → Go 后端查 StarRocks

3. StarRocks 返回:
   {
     "data": [
       {"GROUP_2": "存储类", "ORDERED_PRODUCTSALES": 5411376.33},
       {"GROUP_2": "数据类", "ORDERED_PRODUCTSALES": 41711029.62},
       {"GROUP_2": "电源类", "ORDERED_PRODUCTSALES": 28211226.92},
       ...
     ],
     "count": 10
   }
```

**输出：**
```python
{
    "sql_result": {
        "data": [
            {"GROUP_2": "存储类", "ORDERED_PRODUCTSALES": 5411376.33},
            {"GROUP_2": "数据类", "ORDERED_PRODUCTSALES": 41711029.62},
            {"GROUP_2": "电源类", "ORDERED_PRODUCTSALES": 28211226.92},
            ...
        ],
        "count": 10
    }
}
```

---

### 步骤 9：Stage 5 — 对比计算（同比环比）

**文件：** `ai/graph/nodes.py` `comparison_node()`

**输入：** `state.sql_result` + `state.generated_sql` + `state.entities.time_info`

**处理流程：**

```
1. 检测对比类型
   - 用户问了"同比"+"环比" → 需要计算两种

2. 计算对比周期:
   同比: 2025-03-22 ~ 2025-04-05  (去年同期)
   环比: 2026-03-01 ~ 2026-03-22  (上月同期)

3. 构建同比 SQL (替换时间条件):
   SELECT GROUP_2, SUM(ORDERED_PRODUCTSALES)
   FROM dws.DWS_IMC_BUSINESSREPORT
   WHERE FDATE >= '2025-03-22' AND FDATE <= '2025-04-05'
   GROUP BY GROUP_2

4. 执行同比查询，得到各品类去年同期值

5. 计算涨跌幅:
   change_rate = (current - comparison) / comparison * 100

6. 环比同理
```

**输出：**
```python
{
    "comparison_results": [
        {
            "comparison_type": "同比",
            "current_value": 130233044.50,
            "comparison_value": 449409223.13,
            "change_rate": -71.02,
            "date_range": "2025-03-22 至 2025-04-05",
            "group_by_col": "GROUP_2",
            "comp_data_map": {
                "存储类": {"comparison_value": 14865172.67},
                "数据类": {"comparison_value": 65506253.14},
                ...
            }
        },
        {
            "comparison_type": "环比",
            "current_value": 130233044.50,
            "comparison_value": 163210892.30,
            "change_rate": -20.20,
            "date_range": "2026-03-01 至 2026-03-22",
            ...
        }
    ]
}
```

---

### 步骤 10：Stage 6 — 响应格式化

**文件：** `ai/graph/nodes.py` `response_node()`

**输入：** `state.sql_result` + `state.comparison_results` + `state.entities`

**处理流程：**

```
1. 判断有数据，调用 LLM 生成自然语言回答

2. 列 rename + 排序 (FormatStage):
   输入列名: ["GROUP_2", "ORDERED_PRODUCTSALES"]
   列类型判断:
     - GROUP_2: 维度列 (GROUP BY 列)
     - ORDERED_PRODUCTSALES: 指标列

   rename 映射 (查 dim_configs):
     GROUP_2 → 二级品类
     ORDERED_PRODUCTSALES → 总销售额

   排序: 维度列 → 指标列 → 对比列 → 占比列

3. 对比结果写入每行:
   原: {二级品类: "存储类", 总销售额: 5411376.33}
   加: {去年同期: "14,865,172.67", 同比变化率: -63.6, 上月同期: "8,502,551.41", 环比变化率: -36.36}
```

**输出（返回给 main.py）：**
```python
{
    "answer": "最近15天销售额最高的二级品类是**数据类**，总销售额约 4,171 万元，同比 -36.33%，环比 -34.36%。",
    "result_data": [
        {
            "二级品类": "数据类",
            "总销售额": "41711029.6200000",
            "去年同期": "65,506,253.14",
            "同比变化率": -36.33,
            "上月同期": "63,543,582.80",
            "环比变化率": -34.36
        },
        {
            "二级品类": "电源类",
            "总销售额": "28211226.9200000",
            "去年同期": "1,237,551.10",
            "同比变化率": 215.43,
            "上月同期": "2,109,717.26",
            "环比变化率": -45.08
        },
        ... 共 10 条
    ],
    "comparison_results": [...],
    "sql": "SELECT `GROUP_2` ...",
    "suggest_questions": ["查看数据类的近30天趋势", "对比其他品类"]
}
```

---

### 步骤 11：返回前端展示

**文件：** `web/src/views/Ask.vue`

```javascript
// 收到响应后
const response = await askApi.ask(question, sessionId)

// result_data → 表格展示
<el-table :data="response.result_data">
  <el-table-column prop="二级品类" label="二级品类" />
  <el-table-column prop="总销售额" label="总销售额" />
  <el-table-column prop="去年同期" label="去年同期" />
  <el-table-column prop="同比变化率" label="同比变化率">
    <template #default="{row}">
      <span :style="{color: row.同比变化率 >= 0 ? 'green' : 'red'}">
        {{ row.同比变化率 >= 0 ? '↑' : '↓' }}{{ Math.abs(row.同比变化率).toFixed(2) }}%
      </span>
    </template>
  </el-table-column>
  ...
</el-table>

// answer → 文字回答展示
<div class="answer">{{ response.answer }}</div>

// sql → 可折叠 SQL 展示
<pre>{{ response.sql }}</pre>
```

---

## 三、关键数据结构

### AskRequest (前端 → Go → Python)

```python
class AskRequest(BaseModel):
    question: str                    # "最近15天销售额最高的二级品类是啥，还有同比，环比是多少"
    session_id: Optional[str]       # 会话 ID
    engine_type: Optional[str]       # "langgraph" | "llm"
    page: Optional[int]             # 分页
    page_size: Optional[int]         # 每页条数
```

### AskResponse (Python → Go → 前端)

```python
class AskResponse(BaseModel):
    session_id: str
    answer: str                      # 自然语言回答
    result_data: List[Dict]          # 表格数据（中文列名）
    comparison_results: List[Dict]    # 同比环比数据
    sql: str                         # 生成的 SQL
    suggest_questions: List[str]     # 建议问题
    needs_clarification: bool
    drill_down_dims: List[Dict]      # 下钻维度候选
    breadcrumbs: List[Dict]           # 面包屑路径
    total: int                       # 总记录数
    page: int
    page_size: int
```

### result_data 格式（表格展示用）

```python
[
    {
        "二级品类": "数据类",
        "总销售额": "41711029.6200000",
        "去年同期": "65,506,253.14",
        "同比变化率": -36.33,
        "上月同期": "63,543,582.80",
        "环比变化率": -34.36
    },
    ...
]
```

### comparison_results 格式（图表展示用）

```python
[
    {
        "comparison_type": "同比",
        "current_value": 130233044.50,
        "comparison_value": 449409223.13,
        "change_rate": -71.02,
        "date_range": "2025-03-22 至 2025-04-05",
        "group_by_col": "GROUP_2",
        "comp_data_map": {
            "数据类": {"comparison_value": 65506253.14},
            "电源类": {"comparison_value": 1237551.10},
            ...
        }
    },
    {
        "comparison_type": "环比",
        "current_value": 130233044.50,
        "comparison_value": 163210892.30,
        "change_rate": -20.20,
        ...
    }
]
```

---

## 四、dim_configs 维度配置

**来源：** PostgreSQL `dimensions` 表，通过 `metric_client.get_dimension_configs(table_name)` 获取

两张表通过 `table_name` 关联：
- `metrics.starrocks_sql` 中的 `FROM` 子句 → 表名
- `dimensions.table_name` → 关联到维度配置

```python
{
    "二级品类": {"column_name": "GROUP_2", "values": []},
    "一级品类": {"column_name": "GROUP_1", "values": []},
    "三级品类": {"column_name": "GROUP_3", "values": []},
    "品牌": {"column_name": "BRAND", "values": []},
    "平台": {"column_name": "PLATFORM", "values": []},
    "渠道": {"column_name": "CHANNEL", "values": []},
    ...
}
```

**用途：**
1. `resolve_dimension()`: 将"二级品类"解析为 column_name: "GROUP_2"
2. `FormatStage`: 将 GROUP_2 rename 回"二级品类"

---

## 五、多轮对话上下文

**问题：** 用户先问"最近15天销售额最高的二级品类"，然后问"环比呢"

**处理流程：**

```
第一轮:
  intent_node → entity_node → sql_gen_node → execute_node → response_node
  → response_node 最后调用 _update_context(state, entities)
  → conversation_context = {
      current_metric_code: "MKI-02-0001",
      current_metric_name: "销售额",
      current_time_expr: "最近15天",
      current_dimensions: ["二级品类"]
    }

第二轮 (用户说"环比呢"):
  intent_node 检测到:
    - 短文本 (< 4字符)
    - 有 conversation_context
  → 不做 LLM 识别，直接从 context 恢复 metric_name + time_range
  → LLM expand_followup_question("环比呢") → "最近15天销售额的环比是多少"
  → 继续正常流程
```

---

## 六、State 对象各阶段流转

```
ConversationState {
    session_id: str
    messages: List[ConversationMessage]
    current_intent: str                    # intent_node 输出
    entities: Dict                         # intent_node → entity_node → ... 逐步充实
    generated_sql: str                    # sql_build_node 输出
    sql_params: Dict                      # sql_build_node 输出
    sql_result: Dict                      # execute_node 输出 {data: [], count: N}
    comparison_results: List[Dict]        # comparison_node 输出
    conversation_context: Dict            # 多轮上下文
    last_valid_metric: Dict               # 最后有效的指标
    thinking_steps: List[Dict]            # 思考步骤
}
```

**流转过程：**
```
intent_node
    ↓ (current_intent + entities)
entity_node
    ↓ (entities 充实)
sql_build_node
    ↓ (generated_sql)
execute_node
    ↓ (sql_result)
comparison_node
    ↓ (comparison_results)
response_node
    ↓ (answer + result_data)
返回给前端
```

---

## 七、文件索引

| 文件 | 职责 |
|------|------|
| `web/src/views/Ask.vue` | 前端问数页面 |
| `cmd/server/internal/api/handler/ask.go` | Go 问数接口 |
| `ai/main.py` | FastAPI 入口，调用 engine |
| `ai/engine/langgraph_engine.py` | LangGraph 状态机引擎 |
| `ai/engine/base.py` | 引擎工厂 get_engine() |
| `ai/graph/nodes.py` | 6 个 Stage 业务逻辑（intent/entity/sql_gen/execute/comparison/response） |
| `ai/graph/state.py` | ConversationState 定义 |
| `ai/graph/_dimension_resolver.py` | 维度识别与解析 |
| `ai/graph/_sql_builder.py` | SQL 构建 |
| `ai/graph/_result_formatter.py` | 列 rename + 排序 |
| `ai/sql_gen/generator.py` | SQL 执行器（调用 Go 后端） |
| `ai/sql_gen/query_builder.py` | SQL 模板构建 |
| `ai/engine/time_parser.py` | 时间表达式解析 |
| `ai/engine/rule_engine.py` | 规则引擎（业务术语、意图模板） |
| `ai/engine/llm.py` | LLM 调用（腾讯云 DeepSeek） |
| `ai/client/metric_client.py` | Go API 客户端（获取指标配置） |
