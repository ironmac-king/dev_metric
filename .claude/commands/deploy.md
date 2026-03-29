# 部署命令

## 用途
标准化部署流程，确保各环境一致性。

## 执行方式
```
/project:deploy <环境>
```

## 环境说明
| 环境 | 用途 | 端口 |
|------|------|------|
| `dev` | 开发环境 | 本地 |
| `test` | 测试环境 | 待配置 |
| `prod` | 生产环境 | 待配置 |

## 部署流程

### 1. 部署前检查
```bash
# 检查依赖完整性
go mod verify
pip freeze > requirements.txt

# 运行测试
go test ./...
pytest

# 安全检查
/project:review
```

### 2. 编译构建
```bash
# Go后端
go build -o bin/server ./cmd/server

# Python AI服务
cd ai && pip install -r requirements.txt

# 前端
cd web && npm run build
```

### 3. 服务启动
```bash
# 启动顺序
# 1. PostgreSQL
# 2. StarRocks
# 3. Go后端 (port 8080)
# 4. Python AI服务 (port 8081)
# 5. 前端 (port 3001)

# Go后端
go run ./cmd/server

# Python AI
python ai/main.py

# 前端
cd web && npm run dev
```

### 4. 健康检查
```bash
# 后端
curl http://localhost:8080/health

# AI服务
curl http://localhost:8081/health

# 前端
curl http://localhost:3001
```

## 回滚流程
```bash
# 1. 停止当前服务
pkill -f "go run" || taskkill /F /IM go.exe

# 2. 切换到上一个版本
git checkout <previous-tag>

# 3. 重新部署
/project:deploy dev
```
