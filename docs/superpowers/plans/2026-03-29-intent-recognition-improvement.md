# 意图识别改进方案实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建混合架构意图识别系统：规则层 + 语义层(pgvector) + LLM层三层防御，支持多轮对话上下文继承

**Architecture:** 三层降级架构 - 规则层(毫秒级) → 语义层(Embedding+pgvector, 10-50ms) → LLM层(500ms+, 兜底)

**Tech Stack:** Go后端, Python AI服务(FastAPI), PostgreSQL(pgvector), 阿里云百炼text-embedding-v2

---

## 文件修改清单

### 数据库迁移
- Create: `dev_metric/migrations/007_enable_pgvector.sql`
- Create: `dev_metric/migrations/008_intent_embeddings.sql`
- Create: `dev_metric/migrations/009_metric_embeddings.sql`

### Go 后端
- Modify: `dev_metric/internal/model/metric.go` - 新增 IntentEmbedding, MetricEmbedding 模型
- Modify: `dev_metric/internal/repository/postgres/db.go` - 新增向量搜索方法
- Modify: `dev_metric/internal/api/handler/nlp.go` - 新增向量重建 API
- Modify: `dev_metric/internal/api/router.go` - 注册新路由

### Python AI 服务
- Create: `dev_metric/ai/engine/embedding_client.py` - 阿里云百炼 Embedding 调用
- Create: `dev_metric/ai/engine/semantic_search.py` - 语义搜索核心逻辑
- Modify: `dev_metric/ai/engine/rule_engine.py` - 新增语义搜索接口
- Modify: `dev_metric/ai/graph/state.py` - 新增 ConversationContext 类
- Modify: `dev_metric/ai/graph/nodes.py` - 重构 intent_node 增加语义层

### 前端
- Modify: `dev_metric/web/src/views/NLPConfig.vue` - 新增「重新生成向量」按钮

---

## Task 1: 数据库 - 启用 pgvector 扩展

**Files:**
- Create: `dev_metric/migrations/007_enable_pgvector.sql`

- [ ] **Step 1: 创建 pgvector 启用脚本**

```sql
-- 启用 pgvector 扩展（需要 superuser 权限）
CREATE EXTENSION IF NOT EXISTS vector;

-- 验证扩展是否启用
-- SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

---

## Task 2: 数据库 - 创建 intent_embeddings 表

**Files:**
- Create: `dev_metric/migrations/008_intent_embeddings.sql`

- [ ] **Step 1: 创建 intent_embeddings 表**

```sql
CREATE TABLE IF NOT EXISTS intent_embeddings (
    id SERIAL PRIMARY KEY,
    intent_id INTEGER NOT NULL REFERENCES intent_templates(id) ON DELETE CASCADE,
    intent_type VARCHAR(32) NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1536),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(intent_id)
);

-- 创建索引加速相似度搜索
CREATE INDEX IF NOT EXISTS idx_intent_embeddings_embedding ON intent_embeddings USING ivfflat (embedding vector_cosine_ops);

-- 创建意图类型的索引
CREATE INDEX IF NOT EXISTS idx_intent_embeddings_intent_type ON intent_embeddings(intent_type);
```

---

## Task 3: 数据库 - 创建 metric_embeddings 表

**Files:**
- Create: `dev_metric/migrations/009_metric_embeddings.sql`

- [ ] **Step 1: 创建 metric_embeddings 表**

```sql
CREATE TABLE IF NOT EXISTS metric_embeddings (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    metric_code VARCHAR(64) NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1536),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_id)
);

-- 创建索引加速相似度搜索
CREATE INDEX IF NOT EXISTS idx_metric_embeddings_embedding ON metric_embeddings USING ivfflat (embedding vector_cosine_ops);

-- 创建指标编号的索引
CREATE INDEX IF NOT EXISTS idx_metric_embeddings_code ON metric_embeddings(metric_code);
```

---

## Task 4: Go 后端 - 新增 Embedding 模型

**Files:**
- Modify: `dev_metric/internal/model/metric.go` - 新增 IntentEmbedding, MetricEmbedding 模型

- [ ] **Step 1: 添加 IntentEmbedding 模型**

在 `metric.go` 文件末尾添加：

```go
// IntentEmbedding 意图向量表
type IntentEmbedding struct {
    ID         uint      `json:"id" gorm:"primaryKey"`
    IntentID   uint      `json:"intent_id" gorm:"index"`
    IntentType string    `json:"intent_type" gorm:"size:32"`
    Text       string    `json:"text" gorm:"type:text"`
    Embedding  string    `json:"embedding" gorm:"type:text"` // 存储为 JSON 字符串
    UpdatedAt  time.Time `json:"updated_at"`
}

func (IntentEmbedding) TableName() string {
    return "intent_embeddings"
}

// MetricEmbedding 指标向量表
type MetricEmbedding struct {
    ID         uint      `json:"id" gorm:"primaryKey"`
    MetricID   uint      `json:"metric_id" gorm:"index"`
    MetricCode string    `json:"metric_code" gorm:"size:64"`
    Text       string    `json:"text" gorm:"type:text"`
    Embedding  string    `json:"embedding" gorm:"type:text"` // 存储为 JSON 字符串
    UpdatedAt  time.Time `json:"updated_at"`
}

func (MetricEmbedding) TableName() string {
    return "metric_embeddings"
}
```

---

## Task 5: Go 后端 - 新增向量搜索方法

**Files:**
- Modify: `dev_metric/internal/repository/postgres/db.go` - 新增向量搜索方法

- [ ] **Step 1: 添加向量搜索相关方法**

在 `db.go` 添加以下方法：

```go
// SearchIntentEmbeddings 搜索相似意图向量（使用余弦距离）
func (db *DB) SearchIntentEmbeddings(queryEmbedding []float64, topK int) ([]IntentEmbedding, error) {
    var results []IntentEmbedding

    // 将 []float64 转换为 pgvector 格式
    embeddingStr := formatVectorForPostgres(queryEmbedding)

    sql := `
        SELECT id, intent_id, intent_type, text, embedding, updated_at,
               1 - (embedding <=> ?::vector) AS similarity
        FROM intent_embeddings
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> ?::vector
        LIMIT ?
    `

    rows, err := db.Raw(sql, embeddingStr, embeddingStr, topK).Rows()
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    for rows.Next() {
        var item IntentEmbedding
        var similarity float64
        if err := rows.Scan(&item.ID, &item.IntentID, &item.IntentType, &item.Text, &item.Embedding, &item.UpdatedAt, &similarity); err != nil {
            return nil, err
        }
        results = append(results, item)
    }

    return results, nil
}

// SearchMetricEmbeddings 搜索相似指标向量
func (db *DB) SearchMetricEmbeddings(queryEmbedding []float64, topK int) ([]MetricEmbedding, error) {
    var results []MetricEmbedding

    embeddingStr := formatVectorForPostgres(queryEmbedding)

    sql := `
        SELECT id, metric_id, metric_code, text, embedding, updated_at,
               1 - (embedding <=> ?::vector) AS similarity
        FROM metric_embeddings
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> ?::vector
        LIMIT ?
    `

    rows, err := db.Raw(sql, embeddingStr, embeddingStr, topK).Rows()
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    for rows.Next() {
        var item MetricEmbedding
        var similarity float64
        if err := rows.Scan(&item.ID, &item.MetricID, &item.MetricCode, &item.Text, &item.Embedding, &item.UpdatedAt, &similarity); err != nil {
            return nil, err
        }
        results = append(results, item)
    }

    return results, nil
}

// formatVectorForPostgres 将 []float64 转换为 pgvector 格式字符串 "[0.1,0.2,0.3]"
func formatVectorForPostgres(v []float64) string {
    if len(v) == 0 {
        return "[]"
    }
    parts := make([]string, len(v))
    for i, f := range v {
        parts[i] = strconv.FormatFloat(f, 'f', 6, 64)
    }
    return "[" + strings.Join(parts, ",") + "]"
}
```

**注意：** 需要在 db.go 文件顶部添加 `strings` 和 `strconv` 包的导入。

---

## Task 6: Go 后端 - 新增向量重建 API

**Files:**
- Modify: `dev_metric/internal/api/handler/nlp.go` - 新增向量重建 Handler

- [ ] **Step 1: 添加向量重建相关 Handler**

在 `nlp.go` 文件末尾添加：

```go
import (
    "encoding/json"
    "strings"
)

// RebuildIntentEmbeddings 重新生成所有意图向量
func RebuildIntentEmbeddings(c *gin.Context) {
    // 获取所有启用的意图模板
    var templates []model.IntentTemplate
    postgres.Get().Where("status = ?", 1).Find(&templates)

    count := 0
    for _, tpl := range templates {
        // 构建待向量化的文本：pattern + intent
        texts := strings.Split(tpl.Patterns, ",")
        for _, text := range texts {
            text = strings.TrimSpace(text)
            if text == "" {
                continue
            }
            // 调用 AI 服务生成向量
            embedding, err := generateEmbedding(text)
            if err != nil {
                continue
            }

            // 存储向量
            embeddingJSON, _ := json.Marshal(embedding)
            emb := model.IntentEmbedding{
                IntentID:   tpl.ID,
                IntentType: tpl.Intent,
                Text:       text,
                Embedding:  string(embeddingJSON),
            }

            // 使用 upsert
            postgres.Get().Where("intent_id = ? AND text = ?", tpl.ID, text).
                Assign(emb).
                FirstOrCreate(&model.IntentEmbedding{})
            count++
        }
    }

    response.Success(c, gin.H{"success": true, "count": count})
}

// RebuildMetricEmbeddings 重新生成所有指标向量
func RebuildMetricEmbeddings(c *gin.Context) {
    // 获取所有指标
    var metrics []model.Metric
    postgres.Get().Find(&metrics)

    count := 0
    for _, m := range metrics {
        // 构建待向量化的文本：名称 + 英文名 + 业务定义
        texts := []string{m.Name}
        if m.NameEn != "" {
            texts = append(texts, m.NameEn)
        }
        if m.BusinessDefinition != "" {
            texts = append(texts, m.BusinessDefinition)
        }
        combinedText := strings.Join(texts, " ")

        // 调用 AI 服务生成向量
        embedding, err := generateEmbedding(combinedText)
        if err != nil {
            continue
        }

        // 存储向量
        embeddingJSON, _ := json.Marshal(embedding)
        emb := model.MetricEmbedding{
            MetricID:   m.ID,
            MetricCode: m.MetricCode,
            Text:       combinedText,
            Embedding:  string(embeddingJSON),
        }

        // 使用 upsert
        postgres.Get().Where("metric_id = ?", m.ID).
            Assign(emb).
            FirstOrCreate(&model.MetricEmbedding{})
        count++
    }

    response.Success(c, gin.H{"success": true, "count": count})
}

// generateEmbedding 调用 AI 服务生成向量
func generateEmbedding(text string) ([]float64, error) {
    import (
        "bytes"
        "net/http"
    )

    apiURL := "https://dashscope.aliyuncs.com/compatible-mode/text-embedding/text-embedding-v2"
    apiKey := os.Getenv("DASHSCOPE_API_KEY") // 需要在环境变量中配置阿里云百炼 API Key

    reqBody := map[string]interface{}{
        "model": "text-embedding-v2",
        "input": text,
    }
    bodyBytes, _ := json.Marshal(reqBody)

    req, _ := http.NewRequest("POST", apiURL, bytes.NewReader(bodyBytes))
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Authorization", "Bearer "+apiKey)

    client := &http.Client{Timeout: 30 * time.Second}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)

    if resp.StatusCode != 200 {
        return nil, fmt.Errorf("embedding API error: %d", resp.StatusCode)
    }

    output := result["output"].(map[string]interface{})
    embedding := output["embedding"].([]interface{})
    resultVec := make([]float64, len(embedding))
    for i, v := range embedding {
        resultVec[i] = v.(float64)
    }

    return resultVec, nil
}
```

---

## Task 7: Go 后端 - 注册新路由

**Files:**
- Modify: `dev_metric/internal/api/router.go` - 注册向量重建路由

- [ ] **Step 1: 添加向量重建路由**

在 router.go 中找到 NLP 路由配置部分，添加：

```go
// NLP 路由组
nlp := v1.Group("/nlp")
{
    // 现有路由...
    nlp.GET("/templates", handler.GetAllNLPTemplates)
    nlp.GET("/intents", handler.ListIntentTemplates)
    nlp.POST("/intents", handler.CreateIntentTemplate)
    nlp.PUT("/intents/:id", handler.UpdateIntentTemplate)
    nlp.DELETE("/intents/:id", handler.DeleteIntentTemplate)
    nlp.GET("/sql-templates", handler.ListSQLTemplates)
    nlp.POST("/sql-templates", handler.CreateSQLTemplate)
    nlp.PUT("/sql-templates/:id", handler.UpdateSQLTemplate)
    nlp.DELETE("/sql-templates/:id", handler.DeleteSQLTemplate)

    // 新增：向量重建 API
    nlp.POST("/intents/rebuild-embeddings", handler.RebuildIntentEmbeddings)
    nlp.POST("/metrics/rebuild-embeddings", handler.RebuildMetricEmbeddings)
}
```

---

## Task 8: Python AI 服务 - 创建 Embedding 客户端

**Files:**
- Create: `dev_metric/ai/engine/embedding_client.py`

- [ ] **Step 1: 创建 embedding_client.py**

```python
"""
阿里云百炼 Embedding 调用客户端
"""
import os
import httpx
from typing import List, Optional


class EmbeddingClient:
    """阿里云百炼 Embedding 客户端"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.api_url = "https://dashscope.aliyuncs.com/compatible-mode/text-embedding/text-embedding-v2"
        self.model = "text-embedding-v2"

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        调用百炼 API 获取文本向量

        Args:
            texts: 文本列表（最多 25 条）

        Returns:
            向量列表，每个向量 1536 维
        """
        if not texts:
            return []

        if not self.api_key:
            print("[EmbeddingClient] 警告：DASHSCOPE_API_KEY 未设置")
            return []

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "input": texts,
        }

        try:
            response = httpx.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            output = result.get("output", {})
            embeddings = output.get("embeddings", [])

            return [e.get("embedding", []) for e in embeddings]

        except httpx.HTTPStatusError as e:
            print(f"[EmbeddingClient] HTTP 错误: {e.response.status_code}")
            return [[] for _ in texts]
        except Exception as e:
            print(f"[EmbeddingClient] 调用失败: {e}")
            return [[] for _ in texts]

    def embed_single(self, text: str) -> Optional[List[float]]:
        """单个文本向量化"""
        results = self.embed([text])
        return results[0] if results else None


# 全局实例
embedding_client = EmbeddingClient()
```

---

## Task 9: Python AI 服务 - 创建语义搜索模块

**Files:**
- Create: `dev_metric/ai/engine/semantic_search.py`

- [ ] **Step 1: 创建 semantic_search.py**

```python
"""
语义搜索模块 - 基于 pgvector 的向量相似度搜索
"""
import httpx
from typing import List, Dict, Any, Optional, Tuple
from ai.engine.embedding_client import embedding_client


class SemanticSearch:
    """语义搜索 - 意图/指标向量搜索"""

    # 相似度阈值
    HIGH_THRESHOLD = 0.85   # >0.85 直接确认
    MEDIUM_THRESHOLD = 0.70  # 0.70-0.85 LLM确认
    LOW_THRESHOLD = 0.0     # <0.70 LLM兜底

    def __init__(self, api_base: str = "http://localhost:8080"):
        self.api_base = api_base

    def search_intent(self, query: str, top_k: int = 5) -> Tuple[Optional[str], float]:
        """
        搜索相似意图

        Returns:
            (意图类型, 相似度) 如果找到返回意图类型，否则返回 None
        """
        # 1. 生成查询向量
        query_embedding = embedding_client.embed_single(query)
        if not query_embedding:
            return None, 0.0

        # 2. 调用 Go API 搜索
        try:
            response = httpx.post(
                f"{self.api_base}/api/v1/nlp/semantic-search/intent",
                json={"embedding": query_embedding, "top_k": top_k},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    results = data.get("data", [])
                    if results:
                        best = results[0]
                        return best.get("intent_type"), best.get("similarity", 0.0)
        except Exception as e:
            print(f"[SemanticSearch] 搜索意图失败: {e}")

        return None, 0.0

    def search_metric(self, query: str, top_k: int = 5) -> Tuple[Optional[Dict], float]:
        """
        搜索相似指标

        Returns:
            (指标信息 dict, 相似度) 如果找到返回指标信息，否则返回 None
        """
        # 1. 生成查询向量
        query_embedding = embedding_client.embed_single(query)
        if not query_embedding:
            return None, 0.0

        # 2. 调用 Go API 搜索
        try:
            response = httpx.post(
                f"{self.api_base}/api/v1/nlp/semantic-search/metric",
                json={"embedding": query_embedding, "top_k": top_k},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    results = data.get("data", [])
                    if results:
                        best = results[0]
                        return {
                            "metric_id": best.get("metric_id"),
                            "metric_code": best.get("metric_code"),
                            "metric_name": best.get("text", "").split()[0] if best.get("text") else "",
                        }, best.get("similarity", 0.0)
        except Exception as e:
            print(f"[SemanticSearch] 搜索指标失败: {e}")

        return None, 0.0

    def match_intent(self, query: str) -> Tuple[Optional[str], str]:
        """
        匹配意图 - 三层降级

        Returns:
            (意图类型, 匹配级别) 匹配级别: "high", "medium", "low", "none"
        """
        intent_type, similarity = self.search_intent(query)

        if similarity > self.HIGH_THRESHOLD:
            return intent_type, "high"
        elif similarity > self.MEDIUM_THRESHOLD:
            return intent_type, "medium"
        elif similarity > self.LOW_THRESHOLD:
            return intent_type, "low"
        else:
            return None, "none"

    def match_metric(self, query: str) -> Tuple[Optional[Dict], str]:
        """
        匹配指标 - 三层降级

        Returns:
            (指标信息, 匹配级别)
        """
        metric_info, similarity = self.search_metric(query)

        if similarity > self.HIGH_THRESHOLD:
            return metric_info, "high"
        elif similarity > self.MEDIUM_THRESHOLD:
            return metric_info, "medium"
        elif similarity > self.LOW_THRESHOLD:
            return metric_info, "low"
        else:
            return None, "none"


# 全局实例
semantic_search = SemanticSearch()
```

---

## Task 10: Python AI 服务 - 修改规则引擎

**Files:**
- Modify: `dev_metric/ai/engine/rule_engine.py` - 新增语义搜索接口

- [ ] **Step 1: 在 RuleEngine 类中添加语义搜索方法**

在 `rule_engine.py` 的 `RuleEngine` 类中添加以下方法：

```python
def semantic_search_intent(self, query: str) -> Tuple[Optional[str], float]:
    """语义搜索意图（委托给 SemanticSearch）"""
    from ai.engine.semantic_search import semantic_search
    return semantic_search.match_intent(query)

def semantic_search_metric(self, query: str) -> Tuple[Optional[Dict], float]:
    """语义搜索指标（委托给 SemanticSearch）"""
    from ai.engine.semantic_search import semantic_search
    return semantic_search.match_metric(query)
```

在文件顶部添加导入：

```python
from typing import Tuple
```

---

## Task 11: Python AI 服务 - 新增 ConversationContext

**Files:**
- Modify: `dev_metric/ai/graph/state.py` - 新增 ConversationContext 类

- [ ] **Step 1: 在 state.py 中添加 ConversationContext 类**

在 `state.py` 文件的 `IntentResult` 类后面添加：

```python
class ConversationContext(BaseModel):
    """多轮对话上下文 - 用于继承上轮对话的关键信息"""
    current_metric_id: Optional[int] = None
    current_metric_code: Optional[str] = None
    current_metric_name: Optional[str] = None
    current_time_expr: Optional[str] = None
    current_dimensions: Dict[str, str] = {}
    time_inherited: bool = False
    dimensions_inherited: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_metric_id": self.current_metric_id,
            "current_metric_code": self.current_metric_code,
            "current_metric_name": self.current_metric_name,
            "current_time_expr": self.current_time_expr,
            "current_dimensions": self.current_dimensions,
            "time_inherited": self.time_inherited,
            "dimensions_inherited": self.dimensions_inherited,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        return cls(**data) if data else cls()
```

同时在 `ConversationState` 类中添加上下文字段：

```python
class ConversationState(BaseModel):
    """LangGraph 对话状态"""
    # ... 现有字段 ...

    # ========== 多轮对话上下文继承 ==========
    conversation_context: Optional[ConversationContext] = None  # 对话上下文
```

---

## Task 12: Python AI 服务 - 重构 intent_node

**Files:**
- Modify: `dev_metric/ai/graph/nodes.py` - 重构 intent_node 增加语义层

- [ ] **Step 1: 重构 intent_node 方法**

在 `nodes.py` 中找到 `intent_node` 方法，修改为三层架构：

```python
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

    # ========== Step 2: 语义层匹配 ==========
    semantic_intent, match_level = self.rule_engine.semantic_search_intent(last_message)
    print(f"[DEBUG intent_node] 语义层结果: intent={semantic_intent}, level={match_level}")

    # 语义层高置信度匹配，直接使用
    if match_level == "high" and semantic_intent:
        self._update_context(state, rule_result.entities)
        return {
            "current_intent": semantic_intent,
            "entities": rule_result.entities,
        }

    # ========== Step 3: LLM 层兜底 ==========
    # 语义层中低置信度或规则层不确信时，调用 LLM
    if match_level in ["medium", "low"] or rule_result.confidence < 0.9:
        print(f"[DEBUG intent_node] 进入 LLM 层...")
        available_metrics_info = self.rule_engine.metric_templates if hasattr(self.rule_engine, 'metric_templates') else {}

        # 构建候选意图
        candidate_intent = semantic_intent or rule_result.intent

        intent_result = self.llm_engine.validate_and_correct_intent(
            text=last_message,
            rule_intent=candidate_intent,
            rule_entities=rule_result.entities or {},
            available_metrics_info=available_metrics_info,
            inherited_entities=inherited_entities,
            metric_context=None
        )
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
```

在文件顶部添加必要的导入：

```python
from ai.graph.state import ConversationState, IntentResult, SQLGenerationResult, ClarificationDecision, ThinkingStep, ConversationContext
```

---

## Task 13: Python AI 服务 - 实现上下文继承

**Files:**
- Modify: `dev_metric/ai/graph/nodes.py` - entity_node 中实现上下文继承

- [ ] **Step 1: 修改 entity_node 方法支持上下文继承**

在 `entity_node` 方法中添加上下文继承逻辑：

```python
def entity_node(self, state: ConversationState) -> Dict[str, Any]:
    """实体链接节点 - 支持多轮上下文继承"""
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
        has_explicit_time = any(kw in last_message for kw in ["昨天", "今天", "本周", "本月", "去年"])
        if not has_explicit_time:
            entities.setdefault("time_range", ctx.current_time_expr)
            print(f"[DEBUG entity_node] 继承上轮时间: {ctx.current_time_expr}")

    # ========== 继承上轮的维度 ==========
    if ctx:
        for dim_key, dim_value in ctx.current_dimensions.items():
            if dim_key not in entities and dim_value:
                entities[dim_key] = dim_value
                print(f"[DEBUG entity_node] 继承上轮维度: {dim_key}={dim_value}")

    # ... 其余现有逻辑保持不变 ...
```

---

## Task 14: 前端 - 新增向量重建按钮

**Files:**
- Modify: `dev_metric/web/src/views/NLPConfig.vue` - 新增向量重建功能

- [ ] **Step 1: 在 NLPConfig.vue 中添加向量重建按钮和方法**

在 Vue 组件的 methods 中添加：

```javascript
methods: {
  // ... 现有方法 ...

  // 重新生成意图向量
  async rebuildIntentEmbeddings() {
    try {
      const response = await this.$http.post('/nlp/intents/rebuild-embeddings')
      if (response.data.code === 0) {
        this.$message.success(`成功重建 ${response.data.data.count} 条意图向量`)
      }
    } catch (error) {
      this.$message.error('重建失败')
    }
  },

  // 重新生成指标向量
  async rebuildMetricEmbeddings() {
    try {
      const response = await this.$http.post('/nlp/metrics/rebuild-embeddings')
      if (response.data.code === 0) {
        this.$message.success(`成功重建 ${response.data.data.count} 条指标向量`)
      }
    } catch (error) {
      this.$message.error('重建失败')
    }
  },
}
```

在模板中添加按钮（在页面某个合适位置）：

```html
<el-card class="mb-3">
  <template #header>
    <span>向量管理</span>
  </template>
  <el-space>
    <el-button type="primary" @click="rebuildIntentEmbeddings">
      重新生成意图向量
    </el-button>
    <el-button type="primary" @click="rebuildMetricEmbeddings">
      重新生成指标向量
    </el-button>
  </el-space>
</el-card>
```

---

## Task 15: 验证计划

**Files:**
- 无文件变更

- [ ] **Step 1: 启动服务并验证**

```bash
# 1. 启动 Go 后端
cd dev_metric && go run ./cmd/server

# 2. 启动 Python AI 服务
cd dev_metric && python ai/main.py

# 3. 启动前端
cd dev_metric/web && npm run dev
```

- [ ] **Step 2: 验证数据库扩展**

```sql
-- 在 PostgreSQL 中执行
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extname FROM pg_extension WHERE extname = 'vector';
-- 应该返回 'vector'
```

- [ ] **Step 3: 测试向量重建 API**

```bash
# 重建意图向量
curl -X POST http://localhost:8080/api/v1/nlp/intents/rebuild-embeddings

# 重建指标向量
curl -X POST http://localhost:8080/api/v1/nlp/metrics/rebuild-embeddings
```

- [ ] **Step 4: 测试语义搜索**

```bash
# 测试口语化表达识别
curl -X POST http://localhost:8080/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "转化率咋样"}'
```

预期结果：应该能识别为 query_value 意图

- [ ] **Step 5: 测试多轮对话**

```
用户: "广告转化率是多少"
系统: 返回转化率数据
用户: "同比呢"
系统: 应该继承"广告转化率"这个指标
```

---

## 实施顺序

1. **数据库迁移** (Task 1-3) - 需要在测试前完成
2. **Go 后端模型和 API** (Task 4-7) - Python 服务依赖这些 API
3. **Python AI 服务** (Task 8-13) - 核心语义层逻辑
4. **前端** (Task 14) - 可选，后置
5. **验证** (Task 15) - 全部完成后验证

---

## 注意事项

1. **阿里云百炼 API Key**: 需要在环境变量中配置 `DASHSCOPE_API_KEY`
2. **pgvector 权限**: 需要 PostgreSQL superuser 权限来创建扩展
3. **批量处理**: 向量重建是批量操作，需要注意超时处理
4. **向量维度**: 百炼 text-embedding-v2 是 1536 维
