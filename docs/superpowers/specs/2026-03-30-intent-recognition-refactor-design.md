# 意图识别重构：阿里 Embedding + LangGraph

## Context

当前意图识别存在以下问题：
1. Embedding API 用的是 DeepSeek，但用户已购买阿里 text-embedding-v2，需要切换
2. Embedding 向量存内存不存库，每次语义搜索都实时调 API（贵且慢）
3. 规则层硬编码在代码里，新增意图要改代码
4. 三层串联没有反馈回溯机制

需要重构为：向量存库 + LangGraph 节点化 + 半自动反馈更新

## 设计

### 1. 整体架构

```
用户输入
  ↓
intent_classify 节点（LangGraph）
  ├─ 规则层快速匹配（已有 builtin_patterns）
  └─ 向量搜索（查 PostgreSQL pgvector）
  ↓
置信度决策
  ├─ > 0.85 → 确认意图 → entity_node
  ├─ 0.5-0.85 → LLM 审核（DeepSeek）→ confirm/correct
  └─ < 0.5 → 追问补全
  ↓
entity_node（实体识别：指标、时间、维度）
  ↓
sql_gen_node（SQL 生成）
  ↓
intent_feedback 节点（用户反馈，半自动更新向量）
```

### 2. 数据模型

**新增表：**

```sql
-- 意图模板向量（pgvector）
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE intent_embeddings (
    id SERIAL PRIMARY KEY,
    intent_type VARCHAR(32) NOT NULL,      -- query_value, query_trend, etc.
    pattern_text VARCHAR(256) NOT NULL,    -- 原始匹配文本，如"昨天"
    embedding_vector vector(1536),          -- 阿里 text-embedding-v2 向量维度
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(intent_type, pattern_text)
);

-- 指标向量
CREATE TABLE metric_embeddings (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER REFERENCES metrics(id),
    metric_code VARCHAR(64),
    pattern_text VARCHAR(256),              -- 用于生成向量的文本，如"页面访问量"
    embedding_vector vector(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(metric_id)
);

-- 用户反馈记录
CREATE TABLE intent_feedback (
    id SERIAL PRIMARY KEY,
    user_input VARCHAR(512) NOT NULL,       -- 用户原始输入
    predicted_intent VARCHAR(32),           -- 系统识别的意图
    correct_intent VARCHAR(32),              -- 用户纠正的意图
    status SMALLINT DEFAULT 0,             -- 0=待审核 1=已采纳 2=已忽略
    session_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    reviewed_by VARCHAR(64)
);

-- 意图模板（已有表 intent_templates，新增字段）
ALTER TABLE intent_templates ADD COLUMN IF NOT EXISTS embedding_vector vector(1536);
```

### 3. LLM 配置表改动

**修改 `llm_configs` 表，新增字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| embedding_api_key | VARCHAR(256) | 阿里 dashscope 向量服务 API Key |

API Key 在 LLM 配置页面统一管理，不写在代码里。

### 4. API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/nlp/intents/rebuild-embeddings | 重建所有意图向量（Python 调用阿里 SDK 生成，Go 存库） |
| POST | /api/v1/nlp/metrics/rebuild-embeddings | 重建所有指标向量 |
| GET | /api/v1/feedback/intent | 分页获取意图反馈记录 |
| PUT | /api/v1/feedback/intent/:id/review | 审核反馈（采纳/忽略） |

**说明：**
- AI 服务直连 PostgreSQL 查询 pgvector，不走 Go API
- 向量生成在 Python 侧（调用 dashscope SDK），存储在 Go 侧（通过 API 回调）

### 5. Embedding 接入（阿里 text-embedding-v2）



**修改文件：`ai/engine/embedding_client.py`**

使用阿里官方 Python SDK `dashscope`，不走 HTTP：

```python
from dashscope import TextEmbedding

class EmbeddingClient:
    def __init__(self):
        from ai.engine.llm import LLMEngine
        llm = LLMEngine()
        cfg = llm.get_default_config()
        dashscope.api_key = cfg.get("embedding_api_key", "")

    def embed(self, texts: List[str]) -> List[List[float]]:
        response = TextEmbedding.call(
            model='text-embedding-v2',
            input=texts
        )
        if response.status_code == 200:
            return [item['embedding'] for item in response.output['embeddings']]
        else:
            raise Exception(f"Embedding API error: {response.code}")
```

**向量生成流程（重建向量时）：**
1. Go API 收到 `POST /api/v1/nlp/intents/rebuild-embeddings`
2. Go 调用 Python 服务 `/internal/generate-embeddings`（Flask/内部接口）
3. Python 调用 dashscope SDK 生成向量
4. Python 返回向量列表给 Go
5. Go 写入 PostgreSQL pgvector

**API Key 来源：**
- 从 Go 后端 `GET /api/v1/llm/configs` 获取默认 LLM 配置
- `embedding_api_key` 字段存 PostgreSQL `llm_configs` 表

### 6. LangGraph 节点设计

**修改文件：`ai/graph/nodes.py`**

**5.1 intent_classify 节点（重构）**

```python
def intent_classify_node(state: ConversationState) -> ConversationState:
    """
    LangGraph 意图分类节点
    1. 规则层快速匹配
    2. 向量搜索（查 PostgreSQL，无则调 API）
    3. 置信度决策
    """
    last_message = state.messages[-1].content if state.messages else ""

    # Step 1: 规则层快速匹配
    rule_result = rule_engine.recognize_intent(last_message)
    if rule_result and rule_result.confidence >= 0.9:
        state.entities["intent"] = rule_result.intent
        state.entities["intent_confidence"] = rule_result.confidence
        state.entities["intent_source"] = "rule"
        return state

    # Step 2: 向量搜索
    semantic_intent, similarity = semantic_search.match_intent(last_message)

    # Step 3: 置信度决策
    if semantic_intent and similarity > 0.85:
        state.entities["intent"] = semantic_intent
        state.entities["intent_confidence"] = similarity
        state.entities["intent_source"] = "vector"
    elif semantic_intent and similarity > 0.5:
        # Step 4: LLM 审核
        state.entities["intent"] = semantic_intent
        state.entities["intent_confidence"] = similarity
        state.entities["intent_source"] = "vector_needs_review"
        state = _llm_review_intent(state)
    else:
        # 追问
        state.needs_clarification = True
        state.clarification_type = "intent"
        state.clarification_message = "抱歉，我没理解您的意思。您是想查询指标值、趋势、还是对比数据呢？"

    return state

def _llm_review_intent(state: ConversationState) -> ConversationState:
    """LLM 审核意图（DeepSeek）"""
    prompt = f"""用户输入：{last_message}
系统识别意图：{state.entities.get('intent')}
置信度：{state.entities.get('intent_confidence')}

请判断这个意图识别是否正确。如果错误，请给出正确的意图类型。
返回格式：{{"correct": true/false, "intent": "query_value"}}"""
    # 调用 LLM 审核...
```

**5.2 intent_feedback 节点（新增）**

```python
def intent_feedback_node(state: ConversationState) -> ConversationState:
    """
    用户反馈处理节点
    用户纠正意图后，记录到 feedback 表
    管理员审核后更新向量库
    """
    if not state.entities.get("user_corrected_intent"):
        return state

    # 记录反馈
    record = {
        "user_input": state.messages[-1].content,
        "predicted_intent": state.entities.get("predicted_intent"),
        "correct_intent": state.entities.get("user_corrected_intent"),
        "session_id": state.session_id
    }
    api.post("/api/v1/feedback/intent", record)
    return state
```

**5.3 LangGraph 状态定义**

```python
class ConversationState(TypedDict):
    # 意图相关（新增字段）
    intent_confidence: float
    intent_source: str  # "rule" | "vector" | "llm_review"
    predicted_intent: str  # 系统识别的意图
    user_corrected_intent: str  # 用户纠正的意图

    # 反馈相关（新增）
    needs_feedback_record: bool
    feedback_status: str  # "pending" | "reviewed" | "ignored"
```

### 7. 向量相似度搜索

**AI 服务直连 PostgreSQL 查询 pgvector**

AI 服务启动时从 PostgreSQL 加载所有向量到内存（`semantic_search.py` 已有此逻辑），查询时：

```python
# semantic_search.py 启动时加载
def load_intent_vectors(self):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.execute("SELECT intent_type, pattern_text, embedding_vector FROM intent_embeddings")
    for row in cur:
        self._intent_vectors[row[1]] = np.array(row[2])  # pattern_text -> vector
        self._intent_types[row[1]] = row[0]  # pattern_text -> intent_type

# 查询时：生成向量后，在内存中用 sklearn 计算余弦相似度
query_embedding = embedding_client.embed_single(query)
similarity = cosine_similarity(query_vec, stored_vecs)
```

**向量相似度阈值：**
- `> 0.85`：直接确认意图
- `0.5 - 0.85`：LLM 审核
- `< 0.5`：追问

### 8. 反馈更新流程

```
用户说"不是这个意思，应该是查趋势"
  ↓
intent_feedback_node 记录反馈到 intent_feedback 表
  ↓
管理员在 NLPConfig 页面审核
  ├─ 采纳 → 管理员点击"更新向量"
  │    → 用 correct_intent + 用户输入文本 重新生成向量
  │    → 更新 intent_embeddings 表
  └─ 忽略 → 标记为已忽略
```

### 9. 文件清单

**后端：**
| 文件 | 改动 |
|------|------|
| `internal/model/metric.go` | 新增 `IntentEmbedding`, `MetricEmbedding`, `IntentFeedback` 模型 |
| `internal/api/handler/nlp.go` | 添加 `/feedback/intent` 相关 API，向量重建改用阿里 embedding |
| `internal/api/handler/feedback.go` | 新增（如果需要独立文件） |
| `internal/api/router.go` | 注册新路由 |

**AI 服务：**
| 文件 | 改动 |
|------|------|
| `ai/engine/embedding_client.py` | 改用阿里 dashscope Python SDK |
| `ai/engine/semantic_search.py` | 直连 PostgreSQL 加载向量（pgvector），内存计算余弦相似度 |
| `ai/graph/nodes.py` | `intent_classify_node` 重构 + `intent_feedback_node` 新增 |
| `ai/graph/state.py` | 新增 `intent_confidence`, `intent_source` 等字段 |

**前端：**
| 文件 | 改动 |
|------|------|
| `web/src/views/NLPConfig.vue` | 添加意图反馈审核区域 |
| `web/src/api/index.js` | 添加反馈相关 API |

---

## 验证

1. **Embedding 接入**：调用阿里 embedding API 生成向量，确认维度正确（1536）
2. **向量搜索**：存入 pgvector 后，用 `SELECT ... <=>` 做相似度查询，确认能返回正确结果
3. **意图分类流程**：
   - 问"昨天页面访问量" → 规则层匹配到 query_yesterday → 置信度高直接确认
   - 问"广告转化率和昨天比怎么样" → 向量搜索 + LLM 审核
   - 问"你们这个系统能干啥" → 置信度低触发追问
4. **反馈流程**：故意纠正意图 → 确认记录入库 → 管理员审核采纳 → 确认向量更新
5. **整体对话**：完整问数流程走通，确认 LangGraph 状态流转正确
