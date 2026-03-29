# 后端代码审查技能

## 触发条件
- 代码提交包含 `internal/` 或 `cmd/` 目录
- PR 包含 Go 后端变更
- 文件扩展名：`.go`

## 审查要点

### 1. 安全性检查 🔴
- [ ] **SQL注入**：是否使用参数化查询？
- [ ] **敏感信息**：是否硬编码密码/密钥？
- [ ] **权限控制**：是否有未授权访问风险？
- [ ] **输入验证**：是否校验用户输入？

### 2. 错误处理
- [ ] 错误是否被正确处理？
- [ ] 错误消息是否泄露敏感信息？
- [ ] 是否使用统一的错误响应格式？

### 3. 并发安全
- [ ] 是否有竞态条件？
- [ ] 是否正确使用 mutex？
- [ ] 是否有死锁风险？

### 4. 资源管理
- [ ] 数据库连接是否正确关闭？
- [ ] 是否有资源泄漏？
- [ ] 是否正确处理超时？

### 5. 日志规范
- [ ] 是否记录关键操作？
- [ ] 是否包含 trace_id？
- [ ] 是否避免日志注入？

## 常见漏洞模式

### ❌ SQL 注入风险
```go
// ❌ 错误：字符串拼接
query := "SELECT * FROM users WHERE name = '" + name + "'"

// ✅ 正确：参数化查询
db.Where("name = ?", name).Find(&users)
```

### ❌ 敏感信息泄露
```go
// ❌ 错误：日志中打印密码
log.Printf("password: %s", password)

// ✅ 正确：脱敏处理
log.Printf("user login attempt: %s", maskString(password))
```

### ❌ 权限绕过
```go
// ❌ 错误：未检查用户权限
func DeleteMetric(c *gin.Context) {
    id := c.Param("id")
    db.Delete(&Metric{}, id)  // 任何人都能删除
}

// ✅ 正确：权限检查
func DeleteMetric(c *gin.Context) {
    if !IsAdmin(c) {
        response.Error(c, 403, "无权限")
        return
    }
    // ...
}
```

## Go 特别检查
```bash
# 运行 go vet
go vet ./...

# 检查竞态条件
go race detect ./...

# 安全检查
go run golang.org/x/vuln/cmd/govulncheck ./...
```

## 输出格式
```markdown
## Go 后端代码审查报告

### 🔴 高危问题
| 文件 | 行号 | 问题 | 风险 |
|------|------|------|------|
| metric.go | 45 | SQL拼接 | SQL注入 |

### 🟡 中危问题
| 文件 | 行号 | 问题 | 建议 |
|------|------|------|------|
| handler.go | 78 | 错误未记录 | 添加日志 |

### ✅ 通过项
- 参数化查询 ✓
- 错误处理 ✓
- 权限检查 ✓
```
