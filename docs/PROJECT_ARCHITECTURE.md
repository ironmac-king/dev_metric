# 业务指标管理平台 + 智能问数 - 项目架构文档

> 本文档详细描述 dev_metric 项目的架构、功能和业务流程。

---

## 1. 系统概述

**项目名称**：业务指标管理平台 + 智能问数（NL2SQL）

**项目目标**：
- 业务指标管理平台（导入 155 条指标）
- 智能问数（NL2SQL）- 通过自然语言查询业务数据

**Git 仓库**：https://github.com/ironmac-king/dev_metric.git

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                    前端层 (Vue 3 + Element Plus)                     │
│                        Dashboard | 指标管理 | 告警配置 | 智能问数 | LLM配置 | 意图配置 │
│                                      Port 3001                                     │
└──────────────────────────────────────────────┬──────────────────────────────────┘
                                               │ HTTP REST / WebSocket
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              Go 后端 (Gin Framework)  Port 8080                    │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │   指标管理 API   │  │    告警管理 API   │  │         智能问数 API              │ │
│  │  CRUD / 导入    │  │  规则配置 / 记录   │  │    /api/v1/ask → Python AI     │ │
│  │  (metric.go)   │  │   (alert.go)     │  │         (ask.go)                │ │
│  └────────┬────────┘  └────────┬─────────┘  └───────────────┬──────────────┘ │
│           │                     │                               │                  │
│           └────────────────────┼───────────────────────────────┘                  │
│                                ▼                                                 │
│                    ┌────────────────────────┐                                     │
│                    │   Prompt 配置加载      │  ← prompt_configs 表                │
│                    └───────────┬────────────┘                                     │
└────────────────────────────────┼─────────────────────────────────────────────────┘
                                 │ 仅当 AI 服务需要指标语义知识时调用
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            Python AI 服务 (FastAPI)  Port 8081                    │
│                                                                                   │
│   ┌────────────────────────────────────────────────────────────────────────────┐ │
│   │                     LangGraph 对话引擎                                       │ │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────────┐      │ │
│   │  │intent_   │→ │ entity_  │→ │ sql_gen_ │→ │ execute_           │      │ │
│   │  │node()    │  │node()    │  │ node()   │  │ node() / response_ │      │ │
│   │  │意图识别   │  │实体链接  │  │ SQL生成  │  │node()             │      │ │
│   │  └──────────┘  └──────────┘  └──────────┘  └─────────────────────┘      │ │
│   └────────────────────────────────────────────────────────────────────────────┘ │
│                                │                                                 │
│   ┌────────────────────────────┼────────────────────────────────────────────┐  │
│   │   规则引擎 + SQL 模板       │   LLM 调用（意图识别）                      │  │
│   │   rule_engine.py           │   llm.py (腾讯云 DeepSeek)                 │  │
│   └────────────────────────────┴────────────────────────────────────────────┘  │
└─────────────────────────────────┼────────────────────────────────────────────────┘
                                  │ Go 后端元数据 API (/api/v1/metadata/*)
                                  ▼
┌──────────────────────────────┐   ┌──────────────────────────────────────────────────┐
│         PostgreSQL            │   │                   StarRocks                      │
│  ┌────────────────────────┐  │   │  ┌────────────────────────────────────────────┐  │
│  │ metrics               │  │   │  │          业务数据查询                     │  │
│  │ alert_rules           │  │   │  │  SELECT {starrocks_sql} WHERE ...         │  │
│  │ alert_records         │  │◄─┼──│  └────────────────────────────────────────────┘  │
│  │ llm_configs           │  │   │  └──────────────────────────────────────────────────┘
│  │ dimensions            │  │   │
│  │ business_terms        │  │   │
│  │ intent_templates      │  │   │
│  │ sql_templates         │  │   │
│  │ prompt_configs        │  │   │
│  │ dimensions_configs     │  │   │
│  └────────────────────────┘  │   │
└──────────────────────────────┘   │
                                  │
                                  ▼
                        ┌──────────────────┐
                        │   钉钉 Webhook    │ ← 告警推送（待完成）
                        └──────────────────┘
```

**图例**：
- ─── 实线箭头：数据流向
- ─ ─ ─ 虚线：待完成功能 / 规划中

---

## 3. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Element Plus | Port 3001，用户操作界面 |
| 后端 | Go + Gin Framework | Port 8080，统一入口，路由分发 |
| AI 服务 | Python + FastAPI | Port 8081，LangGraph 驱动，异步对话引擎 |
| 数据库 | PostgreSQL | Port 5432，配置存储、元数据 |
| 数据仓库 | StarRocks | Port 9030，业务数据查询 |
| 缓存 | Redis | Port 6379，Go 后端缓存依赖 |
| LLM | 腾讯云 DeepSeek | 意图识别 |

---

## 4. 数据库表结构

### 4.1 核心业务表

#### metrics - 指标定义表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| metric_code | VARCHAR(64) | 指标编号（如 MKI-02-0001） |
| domain | VARCHAR(64) | 所属域（如 营销域） |
| category_1 | VARCHAR(64) | 一级分类 |
| category_2 | VARCHAR(64) | 二级分类 |
| category_3 | VARCHAR(64) | 三级分类 |
| name | VARCHAR(128) | 指标名称 |
| name_en | VARCHAR(128) | 英文名称 |
| metric_type | VARCHAR(32) | 指标类型 |
| business_definition | TEXT | 业务定义 |
| business_rule | TEXT | 业务口径 |
| technical_rule | TEXT | 技术口径 |
| starrocks_sql | TEXT | 查询 SQL |
| unit | VARCHAR(32) | 度量单位 |
| frequency | VARCHAR(32) | 统计频度 |
| status | VARCHAR(32) | 指标状态（在用/停用） |

#### alert_rules - 告警规则表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| metric_id | INTEGER | 关联指标 ID |
| name | VARCHAR(128) | 规则名称 |
| condition_type | VARCHAR(32) | gt/lt/gte/lte/eq |
| threshold_value | DECIMAL | 阈值 |
| dingtalk_webhook | VARCHAR(512) | 钉钉 Webhook |
| notify_status | SMALLINT | 0=禁用 1=启用 |

#### alert_records - 告警记录表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| rule_id | INTEGER | 规则 ID |
| metric_value | DECIMAL | 触发时指标值 |
| trigger_time | TIMESTAMP | 触发时间 |
| notify_status | SMALLINT | 推送状态 |

#### llm_configs - LLM 配置表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(64) | 配置名称 |
| provider | VARCHAR(32) | tencent/openai/anthropic |
| api_url | VARCHAR(512) | API 地址 |
| api_key | VARCHAR(256) | API Key |
| model_name | VARCHAR(128) | 模型名称 |
| is_default | SMALLINT | 是否默认 |

### 4.2 维度与术语表

#### dimensions - 维度表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(64) | 维度名称 |
| code | VARCHAR(32) | 维度编码 |
| type | VARCHAR(32) | 维度类型 |

#### business_terms - 业务术语表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| term | VARCHAR(128) | 术语 |
| metric_id | INTEGER | 关联指标 |
| synonym | VARCHAR(256) | 同义词 |

#### metric_dimensions - 指标-维度关联表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| metric_id | INTEGER | 指标 ID |
| dimension_id | INTEGER | 维度 ID |

#### dimension_configs - StarRocks 表维度配置
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| table_name | VARCHAR(128) | 表名 |
| dimension_name | VARCHAR(64) | 维度名称 |
| column_name | VARCHAR(64) | 列名 |
| dimension_values | TEXT | 维度值列表（JSON） |
| status | SMALLINT | 状态 |

### 4.3 智能问数相关表

#### intent_templates - 意图模板表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(64) | 模板名称 |
| intent | VARCHAR(32) | 意图类型 |
| patterns | TEXT | 匹配模式（逗号分隔） |
| priority | INT | 优先级 |
| response | TEXT | 默认回复 |
| status | SMALLINT | 状态 |

#### sql_templates - SQL 模板表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(128) | 模板名称 |
| metric_code | VARCHAR(64) | 指标编号 |
| intent | VARCHAR(32) | 适用意图类型 |
| sql_template | TEXT | SQL 模板 |
| description | TEXT | 说明 |
| status | SMALLINT | 状态 |

#### prompt_configs - Prompt 配置表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(64) | 配置名称 |
| prompt_type | VARCHAR(32) | prompt 类型 |
| prompt_text | TEXT | prompt 内容 |
| model_name | VARCHAR(64) | 适用模型 |
| version | INT | 版本号 |
| status | SMALLINT | 状态 |

### 4.4 用户与权限表

#### users - 用户表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| username | VARCHAR(64) | 用户名 |
| password_hash | VARCHAR(256) | 密码哈希 |
| email | VARCHAR(128) | 邮箱 |
| role_id | INTEGER | 角色 ID |
| status | SMALLINT | 状态 |

#### roles - 角色表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(64) | 角色名称 |
| description | VARCHAR(256) | 描述 |

#### role_menus - 角色菜单表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| role_id | INTEGER | 角色 ID |
| menu_id | INTEGER | 菜单 ID |

### 4.5 智能问数会话表

#### ask_session - 问数会话表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| session_id | VARCHAR(64) | 会话 ID |
| user_id | INTEGER | 用户 ID |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### ask_message - 会话消息表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| session_id | VARCHAR(64) | 会话 ID |
| role | VARCHAR(16) | user/assistant |
| content | TEXT | 消息内容 |
| created_at | TIMESTAMP | 创建时间 |

#### ask_analysis_log - 问数分析日志表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| session_id | VARCHAR(64) | 会话 ID |
| question | TEXT | 用户问题 |
| intent | VARCHAR(32) | 识别意图 |
| entities | TEXT | 实体识别结果（JSON） |
| generated_sql | TEXT | 生成的 SQL |
| result | TEXT | 查询结果 |
| latency_ms | INTEGER | 耗时毫秒 |
| created_at | TIMESTAMP | 创建时间 |

### 4.6 其他配置表

#### starrocks_configs - StarRocks 连接配置
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(64) | 配置名称 |
| host | VARCHAR(128) | 主机地址 |
| port | INT | 端口 |
| database | VARCHAR(64) | 数据库 |
| username | VARCHAR(64) | 用户名 |
| password | VARCHAR(256) | 密码 |
| is_default | SMALLINT | 是否默认 |

#### formula_syntax_configs - 公式语法配置
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| intent | VARCHAR(32) | 意图类型 |
| pattern | VARCHAR(256) | 匹配模式 |
| formula_sql | TEXT | 公式 SQL |
| description | TEXT | 说明 |
| status | SMALLINT | 状态 |

#### sql_audit_logs - SQL 审计日志
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| sql_text | TEXT | SQL 语句 |
| user_id | INTEGER | 用户 ID |
| ip_address | VARCHAR(64) | IP 地址 |
| execute_time | TIMESTAMP | 执行时间 |

---

## 5. API 接口

### 5.1 指标管理 API (metric.go)

| 方法 | 路径 | 描述 | 请求体/参数 |
|------|------|------|------------|
| GET | /api/v1/metrics | 指标列表 | ?page=1&page_size=10&keyword= |
| GET | /api/v1/metrics/:id | 指标详情 | - |
| POST | /api/v1/metrics | 创建指标 | MetricForm |
| PUT | /api/v1/metrics/:id | 更新指标 | MetricForm |
| DELETE | /api/v1/metrics/:id | 删除指标 | - |
| POST | /api/v1/metrics/import | 导入 Excel | multipart/form-data |
| POST | /api/v1/metrics/import-preview | 预览导入 | multipart/form-data |
| POST | /api/v1/metrics/import-commit | 确认导入 | ImportCommitForm |
| GET | /api/v1/metrics/export | 导出 Excel | ?ids=1,2,3 |
| GET | /api/v1/metrics/statistics | 指标统计 | - |

### 5.2 仪表盘 API (dashboard.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/dashboard/summary | 汇总数据 |
| GET | /api/v1/dashboard/charts | 图表数据 |
| GET | /api/v1/dashboard/cards | 指标卡片数据 |

### 5.3 智能问数 API (ask.go)

| 方法 | 路径 | 描述 | 请求体 |
|------|------|------|--------|
| POST | /api/v1/ask | 发送问题 | {"question": "...", "session_id": "..."} |
| GET | /api/v1/ask/history | 对话历史 | ?session_id=xxx |
| POST | /api/v1/ask/clear | 清除会话 | {"session_id": "..."} |
| GET | /api/v1/ask/suggest | 问题建议 | ?session_id=xxx |
| POST | /api/v1/ask/drill_down | 下钻查询 | {"session_id": "...", "dimension": "...", "value": "..."} |

### 5.4 指标元数据 API (metadata.go) - 供 Python AI 服务调用

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/metadata/metrics | 所有指标 |
| GET | /api/v1/metadata/metrics/:id | 指标详情 |
| GET | /api/v1/metadata/dimensions | 所有维度 |
| GET | /api/v1/metadata/terms | 业务术语 |
| GET | /api/v1/metadata/dimension-values/search | 搜索维度值 | ?query=xxx&dimension_field=xxx |

### 5.5 NLP 模板管理 API (nlp.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/nlp/templates | 所有模板 |
| GET | /api/v1/nlp/intents | 意图模板列表 |
| POST | /api/v1/nlp/intents | 创建意图模板 |
| PUT | /api/v1/nlp/intents/:id | 更新意图模板 |
| DELETE | /api/v1/nlp/intents/:id | 删除意图模板 |
| GET | /api/v1/nlp/sql-templates | SQL 模板列表 |
| POST | /api/v1/nlp/sql-templates | 创建 SQL 模板 |
| PUT | /api/v1/nlp/sql-templates/:id | 更新 SQL 模板 |
| DELETE | /api/v1/nlp/sql-templates/:id | 删除 SQL 模板 |

### 5.6 LLM 配置 API (llm.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/llm/configs | 配置列表 |
| GET | /api/v1/llm/configs/:id | 配置详情 |
| POST | /api/v1/llm/configs | 创建配置 |
| PUT | /api/v1/llm/configs/:id | 更新配置 |
| DELETE | /api/v1/llm/configs/:id | 删除配置 |
| POST | /api/v1/llm/configs/test | 测试连接 |

### 5.7 告警管理 API (alert.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/alerts/rules | 告警规则列表 |
| POST | /api/v1/alerts/rules | 创建告警规则 |
| PUT | /api/v1/alerts/rules/:id | 更新告警规则 |
| DELETE | /api/v1/alerts/rules/:id | 删除告警规则 |
| GET | /api/v1/alerts/records | 告警记录列表 |
| POST | /api/v1/alerts/records/:id/notify | 触发通知 |

### 5.8 维度配置 API (dimension.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/dimensions | 维度列表 |
| POST | /api/v1/dimensions | 创建维度 |
| PUT | /api/v1/dimensions/:id | 更新维度 |
| DELETE | /api/v1/dimensions/:id | 删除维度 |
| GET | /api/v1/dimension-configs | 表维度配置列表 |
| POST | /api/v1/dimension-configs | 创建表维度配置 |
| PUT | /api/v1/dimension-configs/:id | 更新表维度配置 |
| DELETE | /api/v1/dimension-configs/:id | 删除表维度配置 |

### 5.9 认证 API (auth.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/auth/login | 登录 |
| POST | /api/v1/auth/logout | 登出 |
| POST | /api/v1/auth/refresh | 刷新 Token |

### 5.10 用户管理 API (user.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/users | 用户列表 |
| POST | /api/v1/users | 创建用户 |
| PUT | /api/v1/users/:id | 更新用户 |
| DELETE | /api/v1/users/:id | 删除用户 |

### 5.11 Prompt 配置 API (prompt_config.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/prompt-configs | Prompt 配置列表 |
| POST | /api/v1/prompt-configs | 创建 Prompt 配置 |
| PUT | /api/v1/prompt-configs/:id | 更新 Prompt 配置 |
| DELETE | /api/v1/prompt-configs/:id | 删除 Prompt 配置 |
| GET | /api/v1/prompt-configs/:id/versions | 版本历史 |
| POST | /api/v1/prompt-configs/:id/rollback | 回滚版本 |

### 5.12 StarRocks 配置 API (starrocks.go)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/starrocks/configs | 配置列表 |
| POST | /api/v1/starrocks/configs | 创建配置 |
| PUT | /api/v1/starrocks/configs/:id | 更新配置 |
| DELETE | /api/v1/starrocks/configs/:id | 删除配置 |
| POST | /api/v1/starrocks/query | 执行查询 |

---

## 6. Python AI 服务 API

### 6.1 智能问数接口 (main.py)

| 方法 | 路径 | 描述 | 请求体 |
|------|------|------|--------|
| POST | /api/v1/ask | 发送问题 | AskRequest |
| POST | /api/v1/ask/drill_down | 下钻查询 | DrillDownRequest |
| GET | /api/v1/ask/history | 对话历史 | - |
| POST | /api/v1/ask/feedback | 提交反馈 | FeedbackRequest |

**AskRequest**:
```json
{
    "question": "本月销售额是多少",
    "session_id": "xxx",
    "comparison_types": ["环比", "同比"]
}
```

**AskResponse**:
```json
{
    "session_id": "xxx",
    "answer": "本月销售额为 ¥1,000,000",
    "suggest": ["查看本周数据", "对比上周"],
    "sql": "SELECT ...",
    "thinking_steps": [...]
}
```

### 6.2 内部接口 (供 Go 后端调用)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/metadata/metrics | 获取所有指标 |
| GET | /api/v1/metadata/metrics/:id | 获取指标详情 |
| GET | /api/v1/dimension-values/search | 搜索维度值 |

---

## 7. 核心业务流程

### 7.1 智能问数完整流程（LangGraph 多轮对话）

```
用户问题
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  intent_node()  ←── LLM 意图识别（腾讯云 DeepSeek）    │
│  识别用户意图：query_value / query_trend / query_comparison / query_metadata │
└──────────────────────────┬───────────────────────────┘
                           │ intent: query_value / query_trend / query_comparison / query_metadata
                           ▼
┌──────────────────────────────────────────────────────┐
│  entity_node()  ←── 规则引擎 + LLM 辅助实体链接        │
│  实体与时间解析                                        │
│  - 提取 metric_name / metric_code                     │
│  - 提取 time_range / time_info                       │
│  - 提取 dimension（GROUP BY 维度）                    │
│  - 提取 dimension_values（WHERE 条件）                │
└──────────────────────────┬───────────────────────────┘
                           │ entities: {metric_code, dimensions, time_range, ...}
                           ▼
┌──────────────────────────────────────────────────────┐
│  sql_build_node()  ←── QueryBuilder 确定性 SQL 构建   │
│  生成查询 SQL                                         │
│  - 从 starrocks_sql 模板渲染                           │
│  - 应用时间维度 WHERE 条件                            │
│  - 应用 GROUP BY 维度                                 │
│  - 应用具体维度值 WHERE 条件                         │
└──────────────────────────┬───────────────────────────┘
                           │ sql: SELECT ... GROUP BY ...
                           ▼
┌──────────────────────────────────────────────────────┐
│  execute_node()  ←── 异步执行查询                     │
│  执行查询                                             │
│  - 查 PostgreSQL（元数据）                            │
│  - 查 StarRocks（业务数据）                           │
│  - 返回数值或"暂无数据"                               │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  comparison_node()  ←── 同比/环比计算（可选）          │
│  对比计算                                             │
│  - 环比：上月同期数据                                  │
│  - 同比：去年同期数据                                  │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  response_node()  ←── 生成自然语言回答                │
│  返回最终回复                                         │
│  - 简单查询：用模板格式化                              │
│  - 复杂查询：LLM 生成                                 │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
                      返回结果给用户
```

### 7.2 意图类型说明

| 意图类型 | 说明 | 数据来源 |
|----------|------|----------|
| `query_value` | 查指标当前值 | StarRocks |
| `query_trend` | 查趋势/变化 | StarRocks |
| `query_comparison` | 对比分析 | StarRocks |
| `query_metadata` | 查业务/技术口径 | PostgreSQL |

### 7.3 多轮对话示例

**第一轮：用户问值**
```
用户: 「广告转化率是多少」
  → intent_node(): query_value
  → entity_node(): "广告转化率" → MKI-02-0011, time_range=null
  → sql_gen_node(): 查 MKI-02-0011 的 starrocks_sql
  → execute_node(): 查 StarRocks → 返回 "暂无数据"
  → response_node(): "当前暂无广告转化率数据"
```

**第二轮：用户问口径（多轮上下文复用）**
```
用户: 「业务口径呢」
  → intent_node(): query_metadata
  → entity_node(): 复用上轮实体 "广告转化率"
  → execute_node(): 查 PostgreSQL metrics 表的 business_rule 字段
  → response_node(): "广告转化率的业务口径是..."
```

### 7.4 指标 CRUD 流程

```
前端操作
    │
    ▼
┌─────────────────────────────────────────────┐
│  Go API: metric.go                          │
│  POST /api/v1/metrics                      │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  GORM: Create(metric)                      │
│  写入 PostgreSQL metrics 表                  │
└─────────────────────────────────────────────┘
```

### 7.5 Excel 导入流程

```
上传 Excel
    │
    ▼
┌─────────────────────────────────────────────┐
│  POST /api/v1/metrics/import-preview        │
│  解析 Excel，校验数据                         │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  返回预览数据，确认无误后                      │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  POST /api/v1/metrics/import-commit         │
│  批量写入 metrics 表                          │
└─────────────────────────────────────────────┘
```

### 7.6 告警触发流程（待完成）

```
定时任务（每分钟检查）
    │
    ▼
┌─────────────────────────────────────────────┐
│  查询 StarRocks 指标数据                      │
│  比较阈值                                     │
└──────────────────────┬──────────────────────┘
                       │ 超过阈值
                       ▼
┌─────────────────────────────────────────────┐
│  写入 alert_records 表                       │
│  调用钉钉 Webhook 推送                       │
└─────────────────────────────────────────────┘
```

---

## 8. 前端页面清单

| 页面路径 | 文件 | 功能描述 |
|---------|------|----------|
| / | views/Layout.vue | 整体布局，侧边栏导航 |
| /login | views/Login.vue | 登录页面 |
| /dashboard | views/Dashboard.vue | Dashboard 首页 |
| /metrics | views/Metrics.vue | 指标管理（CRUD + 导入导出） |
| /alerts | views/Alerts.vue | 告警配置 |
| /ask | views/Ask.vue | 智能问数 |
| /ask-analysis | views/AskAnalysis.vue | 问数分析 |
| /ask-dashboard | views/AskDashboard.vue | 问数 Dashboard |
| /analysis | views/AnalysisPage.vue | 决策分析 |
| /nlp-config | views/NLPConfig.vue | 意图/SQL 模板配置 |
| /prompt-config | views/PromptConfig.vue | Prompt 配置 |
| /llm-config | views/LLMConfig.vue | LLM 配置 |
| /dimension-config | views/DimensionConfig.vue | 维度配置 |
| /starrocks-config | views/StarRocksConfig.vue | StarRocks 配置 |
| /feedback | views/FeedbackDashboard.vue | 反馈 Dashboard |
| /users | views/UserManagement.vue | 用户管理 |
| /roles | views/RolePermission.vue | 角色权限 |

---

## 9. 项目文件结构

```
dev_metric/
├── cmd/
│   ├── server/                      # Go 后端服务入口 (port 8080)
│   │   └── main.go
│   ├── importer/                    # Excel 导入工具
│   │   └── main.go
│   ├── migrate/                     # 数据库迁移
│   │   └── main.go
│   └── reset_admin/                 # 重置管理员密码
│       └── main.go
│
├── internal/
│   ├── api/
│   │   ├── handler/                # HTTP Handler
│   │   │   ├── metric.go           # 指标管理
│   │   │   ├── alert.go             # 告警管理
│   │   │   ├── dashboard.go         # Dashboard
│   │   │   ├── ask.go               # 智能问数
│   │   │   ├── metadata.go          # 指标元数据
│   │   │   ├── llm.go              # LLM 配置
│   │   │   ├── nlp.go              # NLP 模板
│   │   │   ├── dimension.go         # 维度配置
│   │   │   ├── auth.go             # 认证
│   │   │   ├── user.go             # 用户管理
│   │   │   └── ...
│   │   ├── middleware/              # 中间件
│   │   │   └── security.go
│   │   └── router.go               # 路由注册
│   │
│   ├── model/                     # 数据模型
│   │   ├── metric.go              # metrics, alert_rules, llm_configs 等
│   │   ├── prompt_config.go        # prompt_configs
│   │   ├── role.go                 # roles, role_menus
│   │   └── dimension_config.go      # dimension_configs
│   │
│   ├── repository/
│   │   └── postgres/
│   │       └── db.go               # PostgreSQL 连接
│   │
│   └── service/                    # 业务服务层
│
├── ai/                             # Python AI 服务 (port 8081)
│   ├── main.py                    # FastAPI 入口
│   │
│   ├── engine/                    # 核心引擎
│   │   ├── langgraph_engine.py   # LangGraph 对话引擎
│   │   ├── rule_engine.py         # 规则引擎
│   │   ├── llm.py                 # LLM 调用
│   │   ├── prompt_manager.py       # Prompt 管理
│   │   └── time_parser.py         # 时间解析
│   │
│   ├── graph/                     # 对话图节点
│   │   ├── nodes.py               # 节点实现
│   │   ├── state.py               # 对话状态
│   │   ├── _dimension_resolver.py # 维度解析
│   │   ├── _sql_builder.py        # SQL 构建
│   │   └── _result_formatter.py    # 结果格式化
│   │
│   ├── sql_gen/                   # SQL 生成
│   │   ├── generator.py           # SQL 生成器
│   │   ├── query_builder.py       # QueryBuilder
│   │   └── cache.py              # SQL 缓存
│   │
│   ├── client/                    # 客户端
│   │   ├── metric_client.py       # Go API 客户端
│   │   └── dim_value_client.py    # 维度值客户端
│   │
│   ├── analysis/                  # 分析模块
│   │   ├── agent.py
│   │   ├── template_matcher.py
│   │   └── insights/              # 洞察分析
│   │       ├── trend.py
│   │       ├── anomaly.py
│   │       └── forecast.py
│   │
│   ├── feedback/                  # 反馈模块
│   │   ├── collector.py
│   │   ├── analyzer.py
│   │   └── auto_detector.py
│   │
│   └── ml/                       # ML 模块
│       ├── intent_classifier.py
│       └── entity_extractor.py
│
├── web/                           # Vue 3 前端 (port 3001)
│   └── src/
│       ├── views/                # 页面
│       │   ├── Dashboard.vue
│       │   ├── Metrics.vue
│       │   ├── Alerts.vue
│       │   ├── Ask.vue
│       │   ├── NLPConfig.vue
│       │   └── ...
│       │
│       ├── components/            # 组件
│       ├── api/                  # API 封装
│       ├── router/               # 路由配置
│       └── store/                # 状态管理
│
├── pkg/
│   └── response/                  # 响应封装
│
├── config.yaml                    # 配置文件
└── go.mod                        # Go 依赖
```

---

## 10. 启动命令

```bash
# Redis (port 6379) - Go 后端缓存依赖
redis-server

# Go 后端 (port 8080)
cd C:/Users/4014/Desktop/dev_metric/dev_metric
go run ./cmd/server

# Python AI 服务 (port 8081)
cd C:/Users/4014/Desktop/dev_metric/dev_metric
python -m uvicorn ai.main:app --port 8081

# 前端 (port 3001)
cd C:/Users/4014/Desktop/dev_metric/dev_metric/web
npm run dev

# 数据库迁移
go run ./cmd/migrate/main.go

# Excel 导入 (CLI)
go run ./cmd/importer/main.go --file 指标中心指标字典.xlsx
```

---

## 11. 待完成功能

1. **钉钉告警推送** - 定时任务 + 钉钉 Webhook
2. **认证系统完善** - JWT 登录、权限控制
3. **StarRocks 对接** - 需要实际数据
4. **意图配置页面调试** - 需调试保存功能
5. **Excel 导入 starrocks_sql** - 需配置 Excel 列映射
6. **SQL 生成层升级 LLM** - prompt_manager.get_sql_generation_prompt() 是空壳

---

## 12. 当前已知问题

1. StarRocks 无实际数据，查询返回空
2. 意图/SQL 模板需要配置后才能匹配
3. Python 服务重启后才会加载新配置
4. GROUP BY 维度列有时不会同步到 SELECT（已修复待验证）

---

*文档生成时间：2026-04-10*
*最后更新：架构文档整理*
