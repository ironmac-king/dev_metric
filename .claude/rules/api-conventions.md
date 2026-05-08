# API 设计约定

## 通用规范

### URL 设计
```
# 资源命名
GET    /api/v1/metrics          # 指标列表
GET    /api/v1/metrics/:id      # 指标详情
POST   /api/v1/metrics          # 创建指标
PUT    /api/v1/metrics/:id      # 更新指标
DELETE /api/v1/metrics/:id      # 删除指标

# 动作命名
POST   /api/v1/metrics/import   # 导入（特殊动作用动词）
POST   /api/v1/ask              # 问数（特殊动作用动词）
```

### HTTP 方法
| 方法 | 用途 | 幂等性 |
|------|------|--------|
| GET | 查询资源 | ✅ |
| POST | 创建资源 | ❌ |
| PUT | 更新资源 | ✅ |
| DELETE | 删除资源 | ✅ |

### 状态码
| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| 200 | 成功 | 正常返回 |
| 201 | 已创建 | POST 成功创建 |
| 400 | 请求错误 | 参数错误 |
| 401 | 未认证 | 缺少登录 |
| 403 | 无权限 | 权限不足 |
| 404 | 不存在 | 资源不存在 |
| 500 | 服务器错误 | 内部错误 |

## 响应格式

### 成功响应
```json
{
  "code": 0,
  "message": "success",
  "data": {
    // 实际数据
  }
}
```

### 错误响应
```json
{
  "code": 40001,
  "message": "参数错误：metric_id 不能为空",
  "data": null
}
```

### 分页响应
```json
{
  "code": 0,
  "data": {
    "list": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5
    }
  }
}
```

## Go 后端 API

### Handler 规范
```go
// ✅ 正确：标准 Handler 签名
func GetMetric(c *gin.Context) {
    id, err := strconv.Atoi(c.Param("id"))
    if err != nil {
        response.Error(c, 400, "参数错误")
        return
    }

    metric, err := svc.GetMetricByID(id)
    if err != nil {
        if errors.Is(err, gorm.ErrRecordNotFound) {
            response.Error(c, 404, "指标不存在")
            return
        }
        response.Error(c, 500, "服务器错误")
        return
    }

    response.Success(c, metric)
}
```

### 路由注册
```go
func SetupRouter() *gin.Engine {
    r := gin.Default()

    v1 := r.Group("/api/v1")
    {
        metrics := v1.Group("/metrics")
        {
            metrics.GET("", handler.ListMetrics)
            metrics.GET("/:id", handler.GetMetric)
            metrics.POST("", handler.CreateMetric)
            metrics.PUT("/:id", handler.UpdateMetric)
            metrics.DELETE("/:id", handler.DeleteMetric)
            metrics.POST("/import", handler.ImportMetrics)
        }

        ask := v1.Group("/ask")
        {
            ask.POST("", handler.AskQuestion)
            ask.GET("/history", handler.GetHistory)
            ask.POST("/clear", handler.ClearSession)
        }
    }

    return r
}
```

## Python AI 服务 API

### 请求模型
```python
class AskRequest(BaseModel):
    question: str                    # 问题内容
    session_id: Optional[str] = None # 会话ID

class AskResponse(BaseModel):
    session_id: str                  # 会话ID
    answer: str                      # 回答内容
    suggest: List[str]              # 建议问题
    sql: Optional[str] = None       # 生成的SQL
```

### 响应模型
```python
# 成功响应
{
    "session_id": "xxx",
    "answer": "广告转化率是5%",
    "suggest": ["查看本周数据", "对比上周"],
    "sql": "SELECT ..."
}

# 错误响应
{
    "detail": "处理出错: xxx"
}
```

## 前端 API 封装

### API 模块化
```typescript
// api/metrics.ts
export const metricApi = {
  list: (params?: ListParams) =>
    request.get<Response>('/metrics', { params }),

  get: (id: number) =>
    request.get<Response>(`/metrics/${id}`),

  create: (data: MetricForm) =>
    request.post<Response>('/metrics', data),

  update: (id: number, data: MetricForm) =>
    request.put<Response>(`/metrics/${id}`, data),

  delete: (id: number) =>
    request.delete<Response>(`/metrics/${id}`),
}

// api/ask.ts
export const askApi = {
  ask: (question: string, sessionId?: string) =>
    request.post<AskResponse>('/ask', { question, session_id: sessionId }),

  getHistory: (sessionId: string) =>
    request.get<HistoryResponse>('/ask/history', { params: { session_id: sessionId } }),
}
```
