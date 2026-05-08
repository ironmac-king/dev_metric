# 安全扫描技能

## 触发条件
- 代码提交包含敏感操作
- PR 合并前自动触发
- 手动调用 `/project:security-scan`

## 扫描范围

### 1. 凭证安全 🔴
- [ ] 硬编码密码/密钥检测
- [ ] API Key 泄露检查
- [ ] 配置文件中敏感信息
- [ ] 日志中的敏感数据

### 2. SQL 注入 🔴
- [ ] 字符串拼接 SQL 检测
- [ ] 参数化查询使用检查
- [ ] ORM 使用规范

### 3. XSS 漏洞 🟡
- [ ] 用户输入未转义
- [ ] innerHTML/outerHTML 使用
- [ ] DOM 注入

### 4. API 安全 🟡
- [ ] 认证机制检查
- [ ] CORS 配置
- [ ] 限流实现

### 5. 依赖安全 🟡
- [ ] 已知漏洞依赖检测
- [ ] 过期依赖检查

## 扫描工具

### Go 安全工具
```bash
# 漏洞扫描
govulncheck ./...

# 依赖检查
go list -m all | nancy

# SAST
staticcheck ./...
```

### Python 安全工具
```bash
# 依赖漏洞
pip-audit

# SAST
bandit -r ai/

# 安全扫描
safety check
```

### 前端安全工具
```bash
# npm 审计
cd web && npm audit

# 已知漏洞
npx snyk test
```

## 常见安全问题

### ❌ 硬编码凭证
```python
# ❌ 错误
API_KEY = "sk-xxxxxx-secret-key"

# ✅ 正确
API_KEY = os.environ.get("API_KEY")
```

### ❌ SQL 注入
```python
# ❌ 错误
query = f"SELECT * FROM users WHERE name = '{name}'"

# ✅ 正确
cursor.execute("SELECT * FROM users WHERE name = ?", (name,))
```

### ❌ XSS 风险
```javascript
// ❌ 错误
element.innerHTML = userInput

// ✅ 正确
element.textContent = userInput
```

## 输出格式
```markdown
## 安全扫描报告

### 🔴 高危漏洞 (必须修复)
| 严重程度 | 文件 | 漏洞类型 | 描述 |
|---------|------|---------|------|
| 🔴 | config.yaml | 硬编码凭证 | 发现明文密码 |

### 🟡 中危漏洞 (建议修复)
| 严重程度 | 文件 | 漏洞类型 | 描述 |
|---------|------|---------|------|
| 🟡 | ai/main.py | SQL注入风险 | 参数化查询缺失 |

### ✅ 通过项
- 依赖无已知漏洞 ✓
- API 认证机制正确 ✓
```

## 修复优先级
1. 🔴 高危：立即修复，阻止合并
2. 🟡 中危：尽快修复，可合并后修复
3. ⚪ 低危：建议修复，可忽略
