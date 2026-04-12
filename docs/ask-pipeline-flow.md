# 智能问数全流程详解

> 本文档详细描述智能问数系统的完整流程，用于开发参考和调试。
> **如有调整请同步更新本文档。**

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端 (Vue 3)                                   │
│  用户输入问题 → 选择引擎(LangGraph/LLM) → 展示结果 + 思考过程               │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTP POST /api/v1/ask
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Python AI 服务 (FastAPI)                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      AskRequest 处理                                 │  │
│  │  question, session_id, engine_type, page, page_size                │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                  get_engine(engine_type)                             │  │
│  │                                                                     │  │
│  │     engine_type 可选:                                               │  │
│  │       - "langgraph": LangGraph 多轮 + QueryBuilder SQL (默认)      │  │
│  │       - "llm": LLM 生成 QueryState (实验性)                         │  │
│  │                                                                     │  │
│  │  ┌─────────────────┬─────────────────┐                              │  │
│  │  │ LangGraphEngine │  LLMQueryEngine │                              │  │
│  │  └────────┬────────┴────────┬───────┘                              │  │
│  │           │                   │                                       │  │
│  │           ▼                   ▼                                       │  │
│  │  ┌───────────────────────────────────────────────┐                   │  │
│  │  │         LangGraph StateGraph 流程            │                   │  │
│  │  │                                               │                   │  │
│  │  │    ┌──────────┐    ┌──────────┐             │                   │  │
│  │  │    │ intent   │───▶│ entity   │             │                   │  │
│  │  │    │ 意图识别 │    │ 实体链接 │             │                   │  │
│  │  │    └──────────┘    └──────────┘             │                   │  │
│  │  │           │               │                   │                   │  │
│  │  │           └───────────────┴───────────────────│─────────────────▶ ┌──────────┐
│  │  │                                               │                 │ response  │
│  │  │                                               │                 │ 生成回答  │
│  │  │                                               │                 └──────────┘
│  │  │                                               │
│  │  │                                               ▼
│  │  │                               ┌───────────────────────────────┐
│  │  │                               │   条件边: needs_clarification │
│  │  │                               └───────────────────────────────┘
│  │  │                                        │              │
│  │  │                              True      │              │  False
│  │  │                               │        │              │
│  │  │                               ▼        │              ▼
│  │  │                        ┌──────────┐   │    ┌──────────────┐
│  │  │                        │ response  │   │    │ sql_build    │
│  │  │                        │ 追问等待  │   │    │ SQL生成      │
│  │  │                        └──────────┘   │    └──────┬───────┘
│  │  │                                     │            │
│  │  │                                     │            ▼
│  │  │                               ┌──────┴───────┐
│  │  │                               │  execute     │
│  │  │                               │ 执行查询     │
│  │  │                               └──────┬───────┘
│  │  │                                      │
│  │  │                                      ▼
│  │  │                               ┌──────────────┐
│  │  │                               │ comparison   │
│  │  │                               │ 对比计算     │
│  │  │                               └──────┬───────┘
│  │  │                                      │
│  │  │                                      ▼
│  │  │                               ┌──────────────┐
│  │  │                               │ response     │
│  │  │                               │ 生成回答     │
│  │  │                               └──────────────┘
│  │  └─────────────────────────────────────────────────────────────┘
│  └─────────────────────────────────────────────────────────────────────┘
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 二、节点详细流程

### ① intent_node (意图识别)

**位置**: `ai/graph/nodes.py`

**职责**: 识别用户意图和关键实体

```
intent_node(state)
    │
    ├─ 获取用户消息 (last_message = state.messages[-1].content)
    │
    ├─ LLM 意图识别
    │   └─ 调用 nl2structure prompt，返回 IntentResult
    │       intent: query_value / query_comparison / query_trend / query_metadata
    │       confidence: 0.0 ~ 1.0
    │       entities: {metric_name, metric_code, time_range, ...}
    │
    ├─ 时间解析 (_extract_time_info)
    │   ├─ TimeParser 解析时间表达式
    │   └─ 输出: time_info {type, start, end, original_expr}
    │
    ├─ 对比关键词检测 (has_comparison_kw)
    │   ├─ "同比", "环比", "对比", "比较"
    │   ├─ "去年同期", "上月同期", "比去年同期", "比上月"
    │   └─ 如检测到: intent → query_comparison (覆盖 LLM 返回的 intent)
    │
    ├─ 公式语法匹配 (_match_formula_syntax)
    │   ├─ 从 formula_syntax_configs 表匹配
    │   └─ 可覆盖 LLM 返回的 intent
    │
    ├─ 置信度检查
    │   ├─ confidence < 0.4 且无明确时间 → 追问
    │   └─ 对比关键词检测到但无时间 → 设置默认时间 "昨天"
    │
    ├─ top_n 提取 (_extract_top_n)
    │   └─ 识别 "前三"、"前十"、"前13" 等
    │
    ├─ 排名维度提取 (_extract_ranking_dimension)
    │   └─ 识别 "最高的品类" 等模式
    │
    └─ 输出: current_intent, entities {metric_name, metric_code, time_info, dimension, top_n, ...}
```

**关键代码逻辑**:
```python
# 对比关键词覆盖 intent (Bug Fix)
has_comparison_kw = any(kw in last_message for kw in ["同比", "环比", ...])
if has_comparison_kw and intent_result.intent not in ["query_comparison", "query_trend"]:
    intent_result.intent = "query_comparison"
    final_intent = "query_comparison"  # 注意: 必须同步修改 final_intent
```

---

### ② entity_node (实体链接)

**位置**: `ai/graph/nodes.py`

**职责**: 完善实体信息，建立指标链接

```
entity_node(state)
    │
    ├─ 获取 state.entities (来自 intent_node)
    │
    ├─ 指标链接 (metric_client)
    │   ├─ search_metrics(query, limit=8) - 语义搜索
    │   ├─ get_metric_by_code(code) - 精确匹配
    │   └─ get_metric(metric_id) - ID 查询
    │
    ├─ 指标枚举追问
    │   ├─ 当 metric_name 模糊且匹配到多个指标时触发
    │   └─ needs_clarification = True, clarification_type = "metric_enum"
    │
    ├─ 时间信息补充
    │   └─ 从 conversation_context 继承上轮时间 (如用户只回复 "呢")
    │
    ├─ 维度提取 (_extract_sql_dimensions)
    │   └─ 解析 entities 中的维度参数
    │
    ├─ 维度值候选 (_get_dimension_value_candidates)
    │   ├─ 当识别到维度但值不明确时触发
    │   └─ 输出: dimension_value_candidates
    │
    └─ 输出: entities (完整实体字典)
```

---

### ③ sql_build_node (SQL生成 - QueryBuilder)

**位置**: `ai/graph/nodes.py`

**职责**: 使用 QueryBuilder 将 QueryState 转换为确定性 SQL

```
sql_build_node(state)
    │
    ├─ 输入: state.entities, state.current_intent
    │
    ├─ 指标信息补充
    │   ├─ 如果 starrocks_sql 为空但有 metric_code
    │   └─ 调用 metric_client.get_metric_by_code() 获取
    │
    ├─ 维度映射 (_get_table_dimensions_cached)
    │   ├─ 从 dimension_configs 表获取
    │   └─ "品类" → "GROUP_3", "一级品类" → "GROUP_1", "三级品类" → "GROUP_3"
    │
    ├─ QueryState 构建
    │   │
    │   ├─ metric: {code, name, starrocks_table, starrocks_sql}
    │   ├─ time: TimeSpec {type, start, end, original_expr}
    │   ├─ dimensions: List[QueryDimension]
    │   │       QueryDimension.type = "三级品类"
    │   │       QueryDimension.field = "GROUP_3"  (映射后)
    │   │       QueryDimension.value = None  (用于 GROUP BY)
    │   ├─ pagination: PaginationSpec {page, page_size}
    │   └─ comparison: ComparisonSpec {enabled, types}
    │
    ├─ QueryBuilder.build_sql()
    │   │
    │   ├─ Step 1: _parse_starrocks_sql()
    │   │       └─ 解析 starrocks_sql，提取 select_fields, table, group_by_fields
    │   │
    │   ├─ Step 2: _render_starrocks_sql()
    │   │       ├─ 替换 {start_date}, {end_date} 占位符
    │   │       └─ 无占位符时，自动追加 FDATE 条件到 WHERE
    │   │
    │   ├─ Step 3: _build_base_sql()
    │   │       ├─ 组合 SELECT / FROM / WHERE / GROUP BY
    │   │       └─ dimensions → GROUP BY
    │   │
    │   ├─ Step 4: _apply_drill_down() (如有 drill_down spec)
    │   │       ├─ 在 SELECT 聚合函数前插入新维度列
    │   │       └─ 扩展 GROUP BY
    │   │
    │   ├─ Step 5: _apply_pagination()
    │   │       └─ 添加 LIMIT/OFFSET
    │   │
    │   └─ Step 6: _build_comparison_sqls() (如启用)
    │           ├─ 计算同比周期 (去年同月)
    │           ├─ 计算环比周期 (上月)
    │           └─ 生成对比 SQL 列表
    │
    ├─ 后处理
    │   └─ SKU 占位符移除 (AND sku = '{SKU}')
    │
    └─ 输出: generated_sql, thinking_steps
```

**QueryBuilder 核心方法**:

| 方法 | 职责 |
|------|------|
| `_parse_starrocks_sql()` | 解析预置 SQL，提取字段映射 |
| `_render_starrocks_sql()` | 替换时间/维度占位符 |
| `_build_base_sql()` | 构建 SELECT/FROM/WHERE/GROUP BY |
| `_apply_drill_down()` | 扩展 GROUP BY (下钻) |
| `_apply_pagination()` | 添加分页 |
| `_build_comparison_sqls()` | 生成同比/环比 SQL |

---

### ④ execute_node (执行查询) [async]

**位置**: `ai/graph/nodes.py`

**职责**: 执行生成的 SQL，获取查询结果

```
execute_node(state) [async]
    │
    ├─ 跳过条件
    │   ├─ skip_execution = True
    │   ├─ generated_sql = "METADATA_QUERY"
    │   └─ generated_sql = "NONE"
    │
    ├─ SQLGenerator.execute()
    │   ├─ 调用 Go 后端 API
    │   │   POST http://localhost:8080/api/v1/query
    │   └─ 返回: {data: [...], count: N}
    │
    ├─ 元数据查询 (intent_is_metadata_query)
    │   ├─ 查 PostgreSQL 获取业务口径、技术口径
    │   └─ 返回 METADATA_QUERY 结果
    │
    ├─ last_valid_metric 更新
    │   └─ 保存当前有效的指标信息，用于 follow-up
    │
    └─ 输出: sql_result, last_valid_metric
```

---

### ⑤ comparison_node (对比计算)

**位置**: `ai/graph/nodes.py`

**职责**: 计算同比/环比涨跌幅

```
comparison_node(state)
    │
    ├─ 跳过条件
    │   ├─ intent != "query_comparison"
    │   └─ 无 sql_result
    │
    ├─ 对比类型检测 (从用户消息 last_message)
    │   ├─ has_yoy: "同比", "去年同期"
    │   └─ has_mom: "环比", "上月"
    │
    ├─ 周期计算 (T+1 数据逻辑)
    │   ├─ 当前数据实际是昨天
    │   ├─ 同比: 去年同月 (comp_year = current_year - 1)
    │   └─ 环比: 上月 (comp_month = current_month - 1)
    │
    ├─ 对比 SQL 执行
    │   ├─ 为每个维度值匹配对比数据
    │   └─ 使用 GROUP BY 列作为 key 建立索引
    │
    ├─ 涨跌幅计算
    │   └─ change_rate = (current - comparison) / comparison * 100
    │
    └─ 输出: comparison_results [{
        type: "同比" | "环比",
        current_value: float,
        comparison_value: float,
        change_rate: float,
        comparison_date: str,
        ...
    }]
```

---

### ⑥ response_node (生成回答)

**位置**: `ai/graph/nodes.py`

**职责**: 生成用户友好的回答文本

```
response_node(state)
    │
    ├─ 结果为空
    │   └─ answer = "抱歉，暂无数据"
    │
    ├─ 多轮对话上下文更新 (_update_context)
    │   ├─ 保存 current_metric_code
    │   ├─ 保存 current_time_expr
    │   └─ 保存 current_dimensions
    │
    ├─ 生成回答文本
    │   ├─ 单条数据: "{指标名}为{值}"
    │   ├─ 多条数据: "{指标名}查询完成，共N条"
    │   └─ 对比数据: "同比增长/下降X%"
    │
    ├─ 建议问题 (suggest_questions)
    │   ├─ 基于当前指标推荐
    │   └─ 基于当前维度推荐
    │
    └─ 输出: answer, suggest_questions, result_data, comparison_results
```

---

## 三、下钻流程 (drill_down)

**位置**: `ai/main.py` - `drill_down_question()`

**触发**: 前端点击下钻按钮

```
POST /api/v1/ask/drill_down
DrillDownRequest:
    session_id, dimension_names[], metric_code,
    current_sql, current_group_by,
    comparison_types[], page, page_size
```

**处理流程**:

```
drill_down_question(req)
    │
    ├─ 1. 获取指标配置
    │   └─ metric_client.get_metric_by_code(metric_code)
    │
    ├─ 2. 获取维度配置
    │   └─ metric_client.get_dimension_configs(table_name)
    │
    ├─ 3. 提取时间范围
    │   └─ 从 current_sql 解析 FDATE 条件
    │
    ├─ 4. QueryBuilder._parse_starrocks_sql()
    │   └─ 解析 starrocks_sql，提取 field_mapping
    │
    ├─ 5. 构建 DrillDownSpec
    │   ├─ add_dimensions: 新增的维度列
    │   └─ original_group_by: 原始 GROUP BY 列
    │
    ├─ 6. QueryBuilder._apply_drill_down()
    │   ├─ 移除原有 GROUP BY
    │   ├─ 在 SELECT 聚合函数前插入新维度列
    │   └─ 添加新的 GROUP BY
    │
    ├─ 7. 执行查询
    │   └─ sql_generator.execute(new_sql)
    │
    ├─ 8. 对比计算 (可选)
    │   ├─ 环比: 上月同期
    │   └─ 同比: 去年同月
    │
    ├─ 9. 列名替换
    │   ├─ 维度列名 → 中文维度名 (col_to_dim_name)
    │   └─ 指标列名 → 中文指标名 (metric_name_map)
    │
    └─ 10. 构建响应
        └─ answer, sql, drill_down_dims, breadcrumbs, result_data, comparison_results
```

---

## 四、数据模型

### ConversationState

**位置**: `ai/graph/state.py`

```python
class ConversationState(BaseModel):
    session_id: str
    messages: List[ConversationMessage]
    current_intent: str

    # 实体信息
    entities: Dict[str, Any]  # metric_name, metric_code, time_info, dimension, ...

    # SQL 相关
    generated_sql: str
    sql_result: Any
    intent_is_metadata_query: bool

    # 追问相关
    needs_clarification: bool
    clarification_message: str
    clarification_type: str

    # 多轮上下文
    conversation_context: ConversationContext
    last_valid_metric: Dict[str, Any]

    # 对比计算
    comparison_results: List[Dict[str, Any]]

    # 思考过程
    thinking_steps: List[ThinkingStep]
```

### QueryState

**位置**: `ai/sql_gen/query_builder.py`

```python
class QueryState(BaseModel):
    version: str = "1.0"
    intent: str
    confidence: float

    metric: Dict[str, Any]  # code, name, starrocks_table, starrocks_sql

    time: TimeSpec  # type, start, end, original_expr
    dimensions: List[QueryDimension]
    pagination: PaginationSpec  # page, page_size
    comparison: ComparisonSpec  # enabled, types

    drill_down: Optional[DrillDownSpec]  # add_dimensions, original_group_by
```

### ClarificationType

**位置**: `ai/graph/state.py`

```python
class ClarificationType:
    METRIC_MISSING = "metric_missing"           # 指标缺失
    TIME_RANGE_MISSING = "time_range_missing"  # 时间范围缺失
    DIMENSION_MISSING = "dimension_missing"    # 维度缺失
    DIMENSION_VALUE_MISSING = "dimension_value_missing"  # 维度值缺失
    ACTION_INTENT_AMBIGUOUS = "action_intent_ambiguous"  # 操作意图模糊
    METRIC_ENUM = "metric_enum"  # 指标枚举选择
    # ... (共12种)
```

---

## 五、意图类型

| intent | 说明 | 典型问题 |
|--------|------|----------|
| `query_value` | 查询指标值 | "总销售额是多少" |
| `query_trend` | 查询趋势 | "销售额趋势" |
| `query_comparison` | 对比分析 | "销售额同比是多少" |
| `query_metadata` | 查询元数据 | "业务口径是什么" |
| `greeting` | 问候 | "你好" |
| `thanks` | 感谢 | "谢谢" |
| `bye` | 告别 | "再见" |
| `unknown` | 未知 | - |

---

## 六、引擎类型

| engine_type | 类 | 说明 |
|-------------|-----|------|
| `langgraph` | LangGraphEngine | **默认** LangGraph 多轮 + QueryBuilder SQL |
| `llm` | LLMQueryEngine | 实验性，LLM 生成 QueryState |

---

## 七、T+1 数据逻辑

- StarRocks 数据是 T+1，即今天查到的数据是昨天及之前的数据
- 对比计算时，当前日期需要 -1 天

```python
# 当前数据实际是昨天
current_date = datetime.now() - timedelta(days=1)

# 同比: 去年同月
comp_year = current_date.year - 1
comp_month = current_date.month

# 环比: 上月
if current_date.month == 1:
    comp_year = current_date.year - 1
    comp_month = 12
else:
    comp_month = current_date.month - 1
```

---

## 八、调试日志关键词

| 关键词 | 位置 | 说明 |
|--------|------|------|
| `[intent_node]` | 意图识别 | 打印意图识别结果 |
| `[entity_node]` | 实体链接 | 打印实体信息 |
| `[sql_build_node]` | SQL生成 | 打印 QueryBuilder 调用 |
| `[sql_gen]` | SQL生成 | _build_value_sql 调用 |
| `[comparison]` | 对比计算 | 打印对比计算结果 |
| `[_apply_drill_down]` | 下钻 | 打印下钻 SQL 生成 |

---

## 九、维度识别流程

### 9.1 维度来源

**dimensions 表**：存储维度类型和值映射

| 字段 | 说明 |
|------|------|
| code | 维度编码（site/platform/region/category/device） |
| name | 中文名称 |
| description | 描述 |
| values | JSON 映射，如 `{"亚马逊": "amazon", "天猫": "tmall"}` |

### 9.2 维度加载逻辑

**位置**: `ai/engine/rule_engine.py` - `_load_dimensions()`

```
_load_dimensions()
    │
    ├─ 优先从 Go API 加载
    │   GET /api/v1/metadata/dimensions
    │   返回: [{"code": "site", "values": {...}}, ...]
    │
    ├─ 解析 dimensions 数据
    │   └─ 存入 self._dimension_cache = {dimension_type: {name: code}}
    │
    └─ API 失败时使用 fallback 默认值
```

### 9.3 Fallback 默认维度

**位置**: `ai/engine/rule_engine.py` - `_init_fallback_dimensions()`

```python
self._dimension_cache = {
    "platform": {"ebay": "ebay", "沃尔玛": "walmart"},
    "region": {"华东": "east_china", "华南": "south_china", ...},
    "site": {"亚马逊": "amazon", "天猫": "tmall", ...},
}
```

### 9.4 维度识别顺序

**位置**: `ai/engine/rule_engine.py` - `_extract_dimensions()`

```
_extract_dimensions(text)
    │
    ├─ 分词：按标点和空格分词
    │
    ├─ 1. platform (平台) - 优先检查
    │
    ├─ 2. region (地区) - 支持"华东区"变体
    │
    ├─ 3. department (部门) - 已移除避免误匹配
    │
    ├─ 4. site (站点)
    │
    ├─ 5. category (品类)
    │
    └─ 6. device (设备)
```

**重要**：检查顺序决定了当一个词匹配多个维度时的优先级

### 9.5 维度值识别（entity_node 中）

**位置**: `ai/graph/nodes.py` - `_get_dimension_value_candidates()`

```
识别到维度但值不明确时：
    │
    ├─ 并发搜索所有候选维度值
    │   ThreadPoolExecutor(max_workers=10)
    │
    ├─ 精确匹配 → 直接使用
    │
    ├─ 唯一匹配 → 直接使用
    │
    └─ 多个候选 → 追问用户确认
```

---

## 十、已知问题修复记录

### Bug 1: 对比关键词覆盖 intent 不完整
- **问题**: 对比关键词检测到后，`final_intent` 没有被同步修改
- **修复**: 在 `intent_node` 添加 `final_intent = "query_comparison"`
- **日期**: 2026-04-07

### Bug 2: 品类维度未映射到 GROUP_3
- **问题**: "三级品类" 没有映射到数据库列名 GROUP_3
- **修复**: 在 `sql_build_node` 中添加维度映射逻辑
- **日期**: 2026-04-07

### Bug 3: entity_node 重复调用 TimeParser
- **问题**: `intent_node` 和 `entity_node` 都调用了 TimeParser，浪费性能
- **状态**: **待修复**
- **位置**: `ai/graph/nodes.py` 第 276 行（intent_node）和第 743 行（entity_node）

### Bug 4: clarification 只检查 time_range
- **问题**: 追问逻辑只检查 time_range，忽略 metric 检查
- **修复**: 同时检查 metric 和 time_range
- **日期**: 2026-04-07

### Bug 5: 维度识别错误（亚马逊 → platform）
- **问题**: "亚马逊" 被识别为 platform 而非 site
- **修复**: 在 fallback 中添加 site 映射，并从 platform 移除"亚马逊"
- **日期**: 2026-04-11

---

## 十一、关键文件索引

| 功能 | 文件路径 |
|------|----------|
| Go API Handler | `internal/api/handler/ask.go` |
| Python FastAPI 入口 | `ai/main.py` |
| LangGraph 引擎 | `ai/engine/langgraph_engine.py` |
| 对话节点 | `ai/graph/nodes.py` |
| 规则引擎 | `ai/engine/rule_engine.py` |
| QueryBuilder | `ai/sql_gen/query_builder.py` |
| SQL 执行器 | `ai/sql_gen/generator.py` |
| 指标客户端 | `ai/client/metric_client.py` |
| 对话状态 | `ai/graph/state.py` |
| 时间解析器 | `ai/engine/time_parser.py` |
| LLM 调用 | `ai/engine/llm.py` |

---

## 十二、调试日志关键词

| 关键词 | 位置 | 说明 |
|--------|------|------|
| `[RuleEngine]` | 规则引擎 | 维度加载和识别日志 |
| `[intent_node]` | 意图识别 | 打印意图识别结果 |
| `[entity_node]` | 实体链接 | 打印实体信息 |
| `[sql_build_node]` | SQL生成 | 打印 QueryBuilder 调用 |
| `[comparison]` | 对比计算 | 打印对比计算结果 |
| `[_apply_drill_down]` | 下钻 | 打印下钻 SQL 生成 |
| `comparison_types` | 对比类型 | 打印检测到的对比类型 |

---

## 十、测试用例

```python
# 简单查询
"最近15天总销售额是多少"

# 带维度
"最近15天按三级品类汇总销售额"

# 带同比环比
"最近15天销售额同比环比是多少"

# 带排名的复杂查询
"最近15天销售额最高的三级品类是啥，还有同比，环比是多少"

# 下钻
POST /api/v1/ask/drill_down
{
    "dimension_names": ["三级品类"],
    "metric_code": "MKI-02-0009",
    "current_sql": "SELECT SUM(...) FROM ... WHERE FDATE >= '2026-03-21'",
    "comparison_types": ["同比", "环比"]
}
```
