# 测试命令

## 用途
运行各类测试验证代码正确性。

## 执行方式
```
/project:test [类型]
```

## 测试类型

### `[unit]` - 单元测试
```bash
# Go单元测试
go test ./internal/... -v -count=1

# Python单元测试
cd ai && pytest tests/ -v
```

### `[integration]` - 集成测试
```bash
# 启动依赖服务
docker-compose up -d postgres starrocks

# 运行集成测试
go test ./... -tags=integration -v
```

### `[api]` - API测试
```bash
# 启动服务
go run ./cmd/server &
python ai/main.py &

# 测试指标API
curl -X GET http://localhost:8080/api/v1/metrics

# 测试AI问数
curl -X POST http://localhost:8081/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"广告转化率是多少"}'
```

### `[all]` - 全部测试
```bash
# 完整测试流程
/project:test unit
/project:test integration
/project:test api
```

## 测试覆盖要求
| 模块 | 覆盖率目标 |
|------|----------|
| Go后端 | ≥70% |
| Python AI | ≥60% |
| 前端 | ≥50% |

## 持续集成
- 每次PR必须通过全部测试
- 测试失败阻止合并
- 覆盖率下降警告

## 常用测试场景

### 智能问数测试
```bash
# 单轮对话
curl -X POST http://localhost:8081/api/v1/ask \
  -d '{"question":"广告转化率是多少","session_id":"test"}'

# 多轮对话
curl -X POST http://localhost:8081/api/v1/ask \
  -d '{"question":"广告转化率是多少","session_id":"multi"}'
curl -X POST http://localhost:8081/api/v1/ask \
  -d '{"question":"业务口径呢","session_id":"multi"}'
```
