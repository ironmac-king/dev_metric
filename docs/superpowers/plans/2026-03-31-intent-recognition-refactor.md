# 意图识别重构：阿里 Embedding + LangGraph

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 切换到阿里 text-embedding-v2，向量存 PostgreSQL pgvector，意图分类加置信度决策，支持反馈更新

**Architecture:**
- Embedding 改用阿里 dashscope Python SDK
- 向量从 Go API 加载改为直连 PostgreSQL pgvector 查询
- 意图分类新增置信度阈值决策（>0.85 直接确认，0.5-0.85 LLM 审核，<0.5 追问）
- 用户纠正意图后记录 feedback 表，管理员审核后可更新向量库

**Tech Stack:** 阿里 dashscope SDK, PostgreSQL pgvector, Python sklearn, Go Gin

---

## 阶段一：后端数据模型 + API

### Task 1: 添加 embedding_api_key 字段到 llm_configs

**Files:**
- Modify: `internal/model/metric.go:98-120` (LLMConfig 结构体)

- [ ] **Step 1: 查看现有 LLMConfig 结构体**

```go
// 查看 LLMConfig 结构体位置（大约在 metric.go 98-120 行）
type LLMConfig struct {
    ID        uint      `json:"id" gorm:"primaryKey"`
    Name      string    `json:"name" gorm:"size:64"`
    Provider  string    `json:"provider" gorm:"size:32"`   // openai/anthropic/tencent
    ApiURL    string    `json:"api_url" gorm:"size:512"`
    ApiKey    string    `json:"api_key" gorm:"size:256"`
    ModelName string    `json:"model_name" gorm:"size:128"`
    IsDefault int16     `json:"is_default" gorm:"default:0"`
    CreatedAt time.Time `json:"created_at"`
    UpdatedAt time.Time `json:"updated_at"`
}
```

- [ ] **Step 2: 添加 embedding_api_key 字段**

在 `ModelName` 字段后添加：
```go
EmbeddingApiKey string    `json:"embedding_api_key" gorm:"size:256"` // 阿里 dashscope 向量服务 API Key
```

- [ ] **Step 3: 验证编译**

```bash
go build ./cmd/server
```

- [ ] **Step 4: Commit**

```bash
git add internal/model/metric.go
git commit -m "feat(llm): add embedding_api_key field to LLMConfig"
```

---

### Task 2: 添加 IntentFeedback 模型

**Files:**
- Modify: `internal/model/metric.go` (新增 IntentFeedback 结构体)
- Modify: `internal/repository/postgres/db.go` (添加到 AutoMigrate)

- [ ] **Step 1: 在 IntentEmbedding 模型后添加 IntentFeedback**

```go
// IntentFeedback 意图反馈记录
type IntentFeedback struct {
    ID             uint      `json:"id" gorm:"primaryKey"`
    UserInput      string    `json:"user_input" gorm:"type:varchar(512)"`       // 用户原始输入
    PredictedIntent string   `json:"predicted_intent" gorm:"size:32"`           // 系统识别的意图
    CorrectIntent  string    `json:"correct_intent" gorm:"size:32"`            // 用户纠正的意图
    Status         int16     `json:"status" gorm:"default:0"`                 // 0=待审核 1=已采纳 2=已忽略
    SessionID      string    `json:"session_id" gorm:"size:64"`
    CreatedAt      time.Time `json:"created_at"`
    ReviewedAt     *time.Time `json:"reviewed_at"`
    ReviewedBy     string    `json:"reviewed_by" gorm:"size:64"`
}

func (IntentFeedback) TableName() string {
    return "intent_feedback"
}
```

- [ ] **Step 2: 添加到 AutoMigrate**

在 `internal/repository/postgres/db.go` 的 `autoMigrate()` 函数中添加 `&model.IntentFeedback{}`

- [ ] **Step 3: 重启 Go 后端验证 AutoMigrate**

```bash
go run ./cmd/server
# 观察日志确认 intent_feedback 表被创建
```

- [ ] **Step 4: Commit**

```bash
git add internal/model/metric.go internal/repository/postgres/db.go
git commit -m "feat(feedback): add IntentFeedback model for intent correction tracking"
```

---

### Task 3: 创建意图反馈 API

**Files:**
- Create: `internal/api/handler/intent_feedback.go` (新增 handler)
- Modify: `internal/api/router.go` (注册路由)

- [ ] **Step 1: 创建 intent_feedback.go handler**

```go
package handler

import (
    "dev_metric/internal/model"
    "dev_metric/internal/repository/postgres"
    "dev_metric/pkg/response"
    "strconv"

    "github.com/gin-gonic/gin"
)

// ListIntentFeedback 获取意图反馈列表（分页）
func ListIntentFeedback(c *gin.Context) {
    page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
    pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
    status := c.Query("status") // 可选：筛选状态

    var feedbacks []model.IntentFeedback
    query := postgres.Get().Model(&model.IntentFeedback{})

    if status != "" {
        query = query.Where("status = ?", status)
    }

    var total int64
    query.Count(&total)

    query.Order("id DESC").
        Offset((page - 1) * pageSize).
        Limit(pageSize).
        Find(&feedbacks)

    response.Success(c, gin.H{
        "list": feedbacks,
        "total": total,
        "page": page,
        "page_size": pageSize,
    })
}

// ReviewIntentFeedback 审核意图反馈
func ReviewIntentFeedback(c *gin.Context) {
    id, _ := strconv.Atoi(c.Param("id"))
    var feedback model.IntentFeedback
    if err := postgres.Get().First(&feedback, id).Error; err != nil {
        response.Error(c, response.CodeNotFound, "反馈记录不存在")
        return
    }

    var input struct {
        Status   int16  `json:"status"`   // 1=采纳 2=忽略
        ReviewedBy string `json:"reviewed_by"`
    }
    if err := c.ShouldBindJSON(&input); err != nil {
        response.Error(c, response.CodeBadRequest, "参数错误")
        return
    }

    feedback.Status = input.Status
    feedback.ReviewedBy = input.ReviewedBy
    now :=.now()
    feedback.ReviewedAt = &now

    postgres.Get().Save(&feedback)
    response.Success(c, feedback)
}

// RecordIntentFeedback 记录意图反馈（AI 服务调用）
func RecordIntentFeedback(c *gin.Context) {
    var input struct {
        UserInput       string `json:"user_input" binding:"required"`
        PredictedIntent string `json:"predicted_intent" binding:"required"`
        CorrectIntent   string `json:"correct_intent" binding:"required"`
        SessionID       string `json:"session_id"`
    }
    if err := c.ShouldBindJSON(&input); err != nil {
        response.Error(c, response.CodeBadRequest, "参数错误")
        return
    }

    feedback := model.IntentFeedback{
        UserInput:       input.UserInput,
        PredictedIntent: input.PredictedIntent,
        CorrectIntent:   input.CorrectIntent,
        SessionID:       input.SessionID,
        Status:          0, // 待审核
    }

    if err := postgres.Get().Create(&feedback).Error; err != nil {
        response.Error(c, response.CodeInternalError, "记录失败")
        return
    }
    response.Success(c, feedback)
}
```

- [ ] **Step 2: 在 router.go 添加路由**

在 `nlp` 路由组后添加：
```go
// 意图反馈
feedback := v1.Group("/feedback")
{
    feedback.GET("/intent", handler.ListIntentFeedback)
    feedback.POST("/intent", handler.RecordIntentFeedback)
    feedback.PUT("/intent/:id/review", handler.ReviewIntentFeedback)
}
```

- [ ] **Step 3: 测试 API**

```bash
# 测试创建反馈
curl -X POST http://localhost:8080/api/v1/feedback/intent \
  -H "Content-Type: application/json" \
  -d '{"user_input":"昨天页面访问量","predicted_intent":"query_value","correct_intent":"query_trend","session_id":"test"}'

# 测试列表
curl http://localhost:8080/api/v1/feedback/intent
```

- [ ] **Step 4: Commit**

```bash
git add internal/api/handler/intent_feedback.go internal/api/router.go
git commit -m "feat(feedback): add intent feedback API endpoints"
```

---

### Task 4: 修改向量重建 API 使用阿里 Embedding

**Files:**
- Modify: `internal/api/handler/nlp.go` (RebuildIntentEmbeddings, RebuildMetricEmbeddings)

- [ ] **Step 1: 查看现有 RebuildIntentEmbeddings 实现**

搜索 `RebuildIntentEmbeddings` 函数

- [ ] **Step 2: 修改为调用 Python 服务生成向量**

Python 服务需要新增一个内部接口 `/internal/generate-embeddings` 接受文本列表，返回阿里 embedding 向量。Go API 拿到向量后存入 PostgreSQL。

```go
// RebuildIntentEmbeddings 重建意图向量
func RebuildIntentEmbeddings(c *gin.Context) {
    // 1. 获取所有意图模板
    var intents []model.IntentTemplate
    postgres.Get().Find(&intents)

    // 2. 提取所有 pattern_text
    texts := []string{}
    for _, intent := range intents {
        patterns := strings.Split(intent.Patterns, ",")
        for _, p := range patterns {
            p = strings.TrimSpace(p)
            if p != "" {
                texts = append(texts, p)
            }
        }
    }

    // 3. 调用 Python 服务生成向量
    payload := map[string]interface{}{"texts": texts}
    payloadBytes, _ := json.Marshal(payload)
    resp, err := http.Post("http://localhost:8081/internal/generate-embeddings",
        "application/json",
        bytes.NewReader(payloadBytes))
    if err != nil {
        response.Error(c, response.CodeInternalError, "调用向量生成服务失败")
        return
    }
    defer resp.Body.Close()

    var result struct {
        Code int `json:"code"`
        Data []struct {
            Text   string    `json:"text"`
            Vector []float64 `json:"embedding"`
        } `json:"data"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        response.Error(c, response.CodeInternalError, "解析向量响应失败")
        return
    }

    // 4. 存入 intent_embeddings 表
    for _, item := range result.Data {
        embeddingJSON, _ := json.Marshal(item.Vector)
        record := model.IntentEmbedding{
            IntentType: getIntentTypeByPattern(item.Text), // 需要辅助函数
            Text:       item.Text,
            Embedding:  string(embeddingJSON),
        }
        postgres.Get().Save(&record)
    }

    response.Success(c, gin.H{"count": len(result.Data)})
}
```

**注意：** `getIntentTypeByPattern` 需要根据 pattern_text 查找对应的 intent_type（查 intent_templates 表）

- [ ] **Step 3: Commit**

---

### Task 5: 添加 Python 向量生成内部接口

**Files:**
- Modify: `ai/main.py` (新增内部接口)

- [ ] **Step 1: 在 ai/main.py 添加内部接口**

在现有路由后添加：

```python
@app.post("/internal/generate-embeddings")
def generate_embeddings():
    """内部接口：接收文本列表，返回阿里 embedding 向量"""
    from ai.engine.alibaba_embedding import alibaba_embedding

    body = request.json
    texts = body.get("texts", [])

    if not texts:
        return {"code": 0, "data": []}

    try:
        vectors = alibaba_embedding.embed(texts)
        data = [{"text": text, "embedding": vec} for text, vec in zip(texts, vectors)]
        return {"code": 0, "data": data}
    except Exception as e:
        return {"code": 500, "message": str(e)}, 500
```

- [ ] **Step 2: Commit**

---

## 阶段二：AI 服务 Embedding 切换

### Task 6: 创建阿里 Embedding 客户端

**Files:**
- Create: `ai/engine/alibaba_embedding.py` (新文件)

- [ ] **Step 1: 安装阿里 dashscope SDK**

```bash
pip install dashscope
```

- [ ] **Step 2: 创建 alibaba_embedding.py**

```python
"""
阿里 text-embedding-v2 接入
使用 dashscope SDK
"""
from typing import List, Optional
from dashscope import TextEmbedding

class AlibabaEmbedding:
    """阿里 text-embedding-v2 客户端"""

    def __init__(self, api_key: str = None):
        if api_key:
            TextEmbedding.api_key = api_key
        self.model = 'text-embedding-v2'

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        调用阿里 text-embedding-v2 获取文本向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not texts:
            return []

        response = TextEmbedding.call(
            model=self.model,
            input=texts
        )

        if response.status_code == 200:
            return [item['embedding'] for item in response.output['embeddings']]
        else:
            raise Exception(f"Embedding API error: {response.code}")

    def embed_single(self, text: str) -> Optional[List[float]]:
        """单个文本向量化"""
        results = self.embed([text])
        return results[0] if results else None


# 全局实例（需要外部设置 api_key）
alibaba_embedding = AlibabaEmbedding()
```

- [ ] **Step 3: Commit**

```bash
git add ai/engine/alibaba_embedding.py
git commit -m "feat(embedding): add Alibaba text-embedding-v2 client"
```

---

### Task 6: 修改 embedding_client 支持阿里

**Files:**
- Modify: `ai/engine/embedding_client.py`

- [ ] **Step 1: 添加阿里配置选项**

```python
class EmbeddingClient:
    """统一的 Embedding 客户端，支持 DeepSeek 和阿里"""

    def __init__(self, provider: str = "deepseek"):
        self.provider = provider
        if provider == "alibaba":
            from ai.engine.alibaba_embedding import alibaba_embedding
            self._client = alibaba_embedding
        else:
            self._client = None  # 现有 DeepSeek 逻辑
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.api_url = "https://api.deepseek.com/embeddings"
        self.model = "deepseek-embedding"

    def embed(self, texts: List[str]) -> List[List[float]]:
        if self.provider == "alibaba":
            return self._client.embed(texts)
        # 现有 DeepSeek 逻辑...
```

- [ ] **Step 2: Commit**

---

### Task 7: 修改 SemanticSearch 直连 PostgreSQL pgvector

**Files:**
- Modify: `ai/engine/semantic_search.py`

- [ ] **Step 1: 添加 PostgreSQL 连接和向量加载**

```python
import psycopg2
import os

class SemanticSearch:
    # ... 现有 __init__ 保持不变 ...

    def _load_vectors_from_pgvector(self):
        """从 PostgreSQL pgvector 加载向量"""
        DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin123@192.168.1.225:5432/dev_metric")

        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 加载意图向量
            cur.execute("SELECT text, intent_type, embedding FROM intent_embeddings")
            for row in cur.fetchall():
                text, intent_type, embedding_str = row
                import json
                embedding = json.loads(embedding_str)
                self._intent_vectors[text] = np.array(embedding)
                self._intent_types[text] = intent_type

            # 加载指标向量
            cur.execute("SELECT metric_code, text, embedding FROM metric_embeddings")
            for row in cur.fetchall():
                metric_code, text, embedding_str = row
                embedding = json.loads(embedding_str)
                self._metric_vectors[metric_code] = np.array(embedding)
                self._metric_info[metric_code] = {"text": text}

            cur.close()
            conn.close()
            self._initialized = True
            print(f"[SemanticSearch] 从 PG 加载了 {len(self._intent_vectors)} 意图向量, {len(self._metric_vectors)} 指标向量")

        except Exception as e:
            print(f"[SemanticSearch] 从PG加载向量失败: {e}")
            # 降级到 API 加载
            self._load_vectors_from_api()
```

- [ ] **Step 2: 修改 ensure_loaded 使用 pgvector**

将 `ensure_loaded` 中的 `_load_vectors_from_api()` 改为先尝试 `_load_vectors_from_pgvector()`

- [ ] **Step 3: Commit**

---

## 阶段三：LangGraph 节点重构

### Task 8: 重构 intent_classify_node 添加置信度决策

**Files:**
- Modify: `ai/graph/nodes.py` (intent_node 方法)

- [ ] **Step 1: 查看现有 intent_node 实现**

位置：大约第 44-129 行

- [ ] **Step 2: 添加置信度阈值常量**

```python
# 在 nodes.py 顶部常量区
INTENT_HIGH_THRESHOLD = 0.85   # >0.85 直接确认
INTENT_MEDIUM_THRESHOLD = 0.5  # 0.5-0.85 LLM审核
```

- [ ] **Step 3: 重构 intent_node 添加置信度决策**

修改 `intent_node` 方法中的向量搜索结果处理逻辑：

```python
# 向量搜索结果处理（新增）
semantic_intent, similarity = self.semantic_search.match_intent(last_message)

if semantic_intent and similarity > INTENT_HIGH_THRESHOLD:
    # 直接确认
    entities["intent"] = semantic_intent
    entities["intent_confidence"] = similarity
    entities["intent_source"] = "vector"
elif semantic_intent and similarity > INTENT_MEDIUM_THRESHOLD:
    # LLM 审核
    entities["intent"] = semantic_intent
    entities["intent_confidence"] = similarity
    entities["intent_source"] = "vector_needs_review"
    state = self._llm_review_intent(state)
else:
    # 追问
    state.needs_clarification = True
    state.clarification_type = "intent"
    state.clarification_message = "抱歉，我没理解您的意思。您是想查询指标值、趋势、还是对比数据呢？"
```

- [ ] **Step 4: 添加 _llm_review_intent 辅助方法**

```python
def _llm_review_intent(self, state: ConversationState) -> ConversationState:
    """LLM 审核意图（DeepSeek）"""
    last_message = state.messages[-1].content if state.messages else ""
    prompt = f"""用户输入：{last_message}
系统识别意图：{state.entities.get('intent')}
置信度：{state.entities.get('intent_confidence')}

请判断这个意图识别是否正确。如果错误，请给出正确的意图类型。
返回格式：{{"correct": true/false, "intent": "query_value"}}"""

    try:
        result = self.llm_engine.call(prompt)
        import json
        result_json = json.loads(result)
        if not result_json.get("correct", True):
            state.entities["intent"] = result_json.get("intent")
            state.entities["intent_source"] = "llm_corrected"
    except Exception as e:
        print(f"[DEBUG] LLM审核失败: {e}")

    return state
```

- [ ] **Step 5: Commit**

---

### Task 9: 添加 intent_feedback_node

**Files:**
- Modify: `ai/graph/nodes.py` (ConversationGraph 类)

- [ ] **Step 1: 在 ConversationGraph 中添加 feedback_node 方法**

在 `response_node` 方法后添加：

```python
def feedback_node(self, state: ConversationState) -> ConversationState:
    """
    用户反馈处理节点
    用户纠正意图后，记录到 feedback 表
    """
    user_corrected = state.entities.get("user_corrected_intent")
    if not user_corrected:
        return state

    predicted = state.entities.get("predicted_intent", state.current_intent)
    record = {
        "user_input": state.messages[-1].content if state.messages else "",
        "predicted_intent": predicted,
        "correct_intent": user_corrected,
        "session_id": state.session_id
    }

    try:
        import requests
        requests.post("http://localhost:8080/api/v1/feedback/intent", json=record, timeout=5)
    except Exception as e:
        print(f"[DEBUG] 记录意图反馈失败: {e}")

    return state
```

- [ ] **Step 2: Commit**

---

## 阶段四：前端反馈审核 UI

### Task 10: 添加意图反馈审核区域到 NLPConfig

**Files:**
- Modify: `web/src/views/NLPConfig.vue`
- Modify: `web/src/api/index.js`

- [ ] **Step 1: 在 api/index.js 添加反馈 API**

```javascript
const feedbackAPI = {
  list: (params) => request.get('/feedback/intent', { params }),
  review: (id, data) => request.put(`/feedback/intent/${id}/review`, data),
}
```

- [ ] **Step 2: 在 NLPConfig.vue 添加反馈审核 Tab**

在现有 Tab 布局中添加"意图反馈"Tab，显示待审核列表，支持采纳/忽略操作

- [ ] **Step 3: Commit**

---

## 验证清单

1. **Embedding 切换**：调用阿里 API 生成向量，确认返回 1536 维
2. **向量加载**：重启 Python 服务，确认从 pgvector 加载向量
3. **意图分类**：
   - 问"昨天页面访问量" → 规则层匹配，置信度高直接确认
   - 问模糊问题 → 触发 LLM 审核或追问
4. **反馈流程**：故意纠正意图 → 确认记录入库 → 管理员审核 → 向量更新
