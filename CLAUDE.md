# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## 项目概述

业务指标管理平台 + 智能问数（NL2SQL）。技术栈：Go 后端 + Python AI 服务 + Vue 3 前端 + PostgreSQL + StarRocks。

## 常用命令

```bash
# Redis (port 6379) - Go 后端缓存依赖
redis-server

# Go 后端 (port 8080)
cd C:/Users/4014/Desktop/DEV2_METRIC/dev_metric
go run ./cmd/server

# Python AI 服务 (port 8081) - ai/main.py 是 async FastAPI 应用
cd C:/Users/4014/Desktop/DEV2_METRIC/dev_metric
python -m uvicorn ai.main:app --port 8081

# 前端 (port 3001)
cd C:/Users/4014/Desktop/DEV2_METRIC/dev_metric/web
npm run dev

# 数据库迁移
go run ./cmd/migrate/main.go

# Excel 导入 (CLI)
go run ./cmd/importer/main.go --file 指标中心指标字典.xlsx

# 构建
go build -o bin/server ./cmd/server

# Go 依赖
go mod tidy
```

## 系统架构

```
┌─────────────────────────┬────────────────────────────────────────────────┐
│  Vue 3 前端 (port 3001) │  Python AI 服务 (port 8081)                   │
│  Element Plus            │  FastAPI + async 对话引擎 │ LLM │ 规则引擎    │
└────────────┬────────────┴──────────────────────┬─────────────────────────┘
             │ HTTP REST API                      │
             ▼                                    ▼
┌─────────────────────────┬──────────────────────┬─────────────────────────┐
│  Go 后端 Gin (port 8080)│                      │  指标元数据 API          │
│  指标管理 │ 告警 │ Dashboard│◄─────────────────│  (语义知识库)            │
└───────────┬─────────────┴──────────────────────┴─────────────────────────┘
            │                                        │
            ▼                                        ▼
     ┌─────────────┐                        ┌─────────────┐
     │ PostgreSQL  │                        │  StarRocks  │
     │ (配置存储)   │                        │  (数据查询)  │
     └─────────────┘                        └─────────────┘
```

## 代码组织

### Go 后端 (`internal/`)

- `api/handler/` — HTTP Handler，按资源命名（metric.go, alert.go, ask.go...）
- `api/router.go` — 路由注册
- `api/middleware/` — 中间件（审计、安全）
- `model/` — GORM 数据模型（所有表结构）
- `repository/postgres/` — PostgreSQL 连接（db.go）
- `repository/starrocks/` — StarRocks 客户端
- `service/` — 业务服务层
- `task/` — 定时任务（如告警检查）

### Python AI 服务 (`ai/`)

- `main.py` — FastAPI 入口，`ask_question` 是 `async def`
- `graph/state.py` — V1 对话状态（已废弃，仅保留类型定义）
- `engine/llm_v2/` — **LLM.V2 活跃引擎**（`graph.py` 是 LangGraph 入口）
- `engine/llm.py` — V1 LLM 引擎（已废弃）
- `engine/rule_engine.py` — V1 规则引擎（已废弃）
- `engine/semantic_search.py` — 语义搜索（pgvector 存储 + 阿里 text-embedding-v2）
- `engine/alibaba_embedding.py` — 阿里 Embedding 客户端（text-embedding-v2，1536维）
- `engine/time_parser.py` — 时间表达式解析（支持"近7日"、"近30天"等）
- `sql_gen/generator.py` — SQLGenerator，`execute()` 是 **async** 方法
- `client/metric_client.py` — Go API 客户端（获取指标配置）
- `feedback/` — 意图反馈收集、自动失败检测、优化建议

### 前端 (`web/src/`)

- `views/` — Vue 页面（Dashboard、Metrics、Alerts、Ask、NLPConfig、LLMConfig...）
- `api/` — 前端 API 封装（axios）
- `router/` — Vue Router 配置
- Vite 配置了 `@` 路径别名指向 `src/`

## AI 服务关键实现细节

### LLM.V2 LangGraph 架构（智能问数核心）

`ai/engine/llm_v2/` 是当前活跃的智能问数引擎（V1 已废弃）。

**13 步 LangGraph 闭环**：

```
intent_router → context_enhancer → mql_generator → mql_syntax_validator
    → mql_semantic_validator → sql_generator → sql_security_auditor
    → sql_executor → data_quality_checker → trigger_analyzer
    → result_analyzer → state_manager
```

| # | 节点 | 驱动 | 说明 |
|---|------|------|------|
| 1 | intent_router | LLM | 识别意图（query_value/trend/comparison 等） |
| 2 | context_enhancer | RAG | 检索相似案例 |
| 3 | mql_generator | LLM | 自然语言 → MQL Schema |
| 4 | mql_syntax_validator | 规则 | JSON Schema 语法验证 |
| 5 | mql_semantic_validator | LLM+规则 | 指标名→starrocks_sql 映射验证 |
| 6 | sql_generator | **确定性规则** | MQL → SQL（不走 LLM） |
| 7 | sql_security_auditor | 规则 | SQL 安全检查 |
| 8 | sql_executor | async IO | 异步查 StarRocks |
| 9 | data_quality_checker | 规则 | 空数据/异常值检查 |
| 10 | trigger_analyzer | 规则 | 决策分析触发检测（波动/库存/广告效果等） |
| 11 | result_analyzer | LLM | 生成自然语言回答 |
| 12 | state_manager | 规则 | 更新会话状态 |

**trigger_analyzer** 是决策分析引擎（`/api/v1/analysis`），也可在问数链路中被触发，支持 6 类触发器：VolatilityTrigger、ComparisonTrigger、AdEffectTrigger、InventoryRiskTrigger、GenericQueryTrigger、ContextTrigger。

**决策分析**有独立入口 `/api/v1/analysis/analyze`，不经过问数链路。

### 对话流程（同步节点调用链）

```
main.py ask_question (async)
  → intent_node(state)        # 同步
  → entity_node(state)        # 同步
  → sql_gen_node(state)       # 同步
  → execute_node(state)       # async！必须 await
  → response_node(state)      # 同步
```

**重要**：`execute_node` 是 `async def`，内部调用 `await self.sql_generator.execute()`（也是 async）。如果忘记 await，sql_result 会是 coroutine 对象而不是实际结果，导致 `'coroutine' object has no attribute 'get'` 错误。

### 语义搜索架构

- **Embedding**：阿里 text-embedding-v2（1536维），通过 `DASHSCOPE_API_KEY` 环境变量认证
- **存储**：PostgreSQL pgvector，`intent_embeddings` / `metric_embeddings` 表存储向量
- **查询**：Python 调用 `/internal/generate-embeddings` 端点生成向量，再做余弦相似度搜索
- **置信度阈值**：>0.85 直接确认，0.25-0.85 LLM 审核，<0.25 追问

### 时间维度（日、月、年）

- `TimeParser` 解析时间表达式（`近7日`、`近30天`、`近7天` 等）
- 维度配置存在 `dimension_configs` 表（PostgreSQL），包含 StarRocks 表的维度列映射
- `_apply_dimensions_to_sql` 会将时间维度自动注入为 `GROUP BY`（无需 SQL 模板有占位符）
- 实体识别通过 `按([日月年天周])查看` 正则识别时间粒度维度

### 多轮对话上下文机制

**上下文保存**：每个 `response_node` 返回前都会调用 `_update_context(state, entities)` 将当前 `metric_name/metric_code/time_range` 保存到 `conversation_context`，确保下一轮可以恢复。

**Step 0 意图确认恢复**：当用户回复"指标值"、"趋势"等短词时，`intent_node` 入口检测到 `_prev_clarification_type` 或 `conversation_context` 存在，会直接从 context 恢复指标/时间，跳过规则/语义匹配。同时通过 `_intent_confirmed_from_context` 标记保护恢复的实体不被 `entity_node` 清除。

**ConversationContext 字段**（`graph/state.py`）：
```
current_metric_code, current_metric_name, current_time_expr, current_dimensions
```
注意：上下文追踪只用 `metric_code`，不用 `metric_id`（后者仅用于 SQL 执行层）。

### 空数据智能追问

当 SQL 查询返回空数据时，`response_node` 调用 `llm_engine.generate_empty_result_followup()` 分析原因并给出具体建议，而不是返回固定模板。

## 关键约定

代码风格、API 规范、Git 规范已记录在 `.claude/rules/` 目录下，修改代码前应先参考：

- `.claude/rules/code-style.md` — Go/Python/Vue 代码风格
- `.claude/rules/api-conventions.md` — REST API 设计规范
- `.claude/rules/git-conventions.md` — 分支和 Commit 规范

### API 响应格式

```json
{ "code": 0, "message": "success", "data": {} }
```

错误响应 `code` 非 0，`message` 描述错误原因。

### Excel 导入/导出

列头与 `cmd/importer/main.go` 中的 `headerMapping` 完全对齐，24 个字段。导入使用两步流程：预览（`POST /import-preview`）→ 确认提交（`POST /import-commit`）。

## 端口配置

| 服务 | 端口 | 入口 |
|------|------|------|
| Go 后端 | 18080 | `go run ./cmd/server` |
| Python AI | 18081 | `python -m uvicorn ai.main:app --port 18081` |
| Vue 前端 | 3002 | `cd web && npm run dev` |

## 数据库

- **PostgreSQL** (5432): 配置存储、指标元数据、用户、告警规则、pgvector 向量
- **StarRocks** (9030): 实际业务数据查询

配置在 `config.yaml`，数据库连接用 `192.168.1.225`（不是 localhost）。

## 回复

默认用中文回复，回答前先叫一声大哥。
