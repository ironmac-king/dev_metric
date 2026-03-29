# 项目记忆

## 项目概述
- **名称**: 业务指标管理平台 + 智能问数
- **技术栈**: Go后端 + Python AI服务 + Vue3前端 + PostgreSQL + StarRocks
- **端口**: Go(8080) / Python AI(8081) / 前端(3001)

## 核心架构
```
前端(Vue3) → Go API(8080) → PostgreSQL
                    ↓
              Python AI(8081) → 智能问数(LangGraph)
                    ↓
              StarRocks(数据查询)
```

## 关键文件
- `ai/graph/nodes.py` - 对话节点（intent/entity/sql_gen/execute/response）
- `ai/graph/state.py` - 对话状态定义
- `ai/engine/rule_engine.py` - 规则引擎
- `ai/sql_gen/generator.py` - SQL生成器
- `internal/api/handler/` - Go API处理器
- `internal/repository/postgres/db.go` - 数据库连接
- `internal/service/audit.go` - SQL审计服务
- `internal/api/middleware/audit.go` - 审计中间件

## 已完成功能
- ✅ 指标管理（CRUD + Excel导入）
- ✅ 告警规则配置
- ✅ 智能问数（LangGraph多轮对话）
- ✅ 意图模板管理
- ✅ SQL模板管理
- ✅ 业务口径/技术口径查询
- ✅ SQL审计日志（中间件+服务层）

## 待完成功能
- ❌ 钉钉告警推送
- ❌ JWT认证
- ❌ StarRocks实际数据对接
- ❌ 意图配置页面调试

## 已知问题
1. StarRocks无数据，查询返回空
2. 某些指标没有预置SQL模板
3. "用户数"等指标未在模板中配置

## 启动命令
```bash
# Go后端
go run ./cmd/server

# Python AI
python ai/main.py

# 前端
cd web && npm run dev
```

## 测试命令
```bash
# 单轮对话
curl -X POST http://localhost:8081/api/v1/ask \
  -d '{"question":"广告转化率是多少","session_id":"test"}'

# 多轮对话
# Q1: 广告转化率是多少
# Q2: 业务口径呢 (继承上轮指标)
# Q3: 技术口径呢 (继承上轮指标)
```

## 关键决策记录
1. **多轮对话实体继承**: 当用户问新指标时清空上轮实体，但保留last_valid_metric用于follow-up查询
2. **混合引擎策略**: 规则引擎优先匹配，LLM兜底
3. **意图识别**: query_metadata优先级高于query_value
