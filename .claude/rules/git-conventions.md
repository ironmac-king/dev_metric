# Git 提交规范

## 分支命名

### 格式
```
<类型>/<描述>
```

### 类型
| 类型 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能 | feature/user-auth |
| `fix/` | Bug修复 | fix/metric-query-error |
| `refactor/` | 重构 | refactor/ask-service |
| `docs/` | 文档更新 | docs/api-doc |
| `chore/` | 其他修改 | chore/update-deps |

### 示例
```bash
# 正确
git checkout -b feature/add-alert-system
git checkout -b fix/session-timeout
git checkout -b fix/multi-turn-conversation

# 错误
git checkout -b fix-bug-1
git checkout -b wip
git checkout -b temp
```

## Commit 规范

### 格式
```
<类型>(<范围>): <描述>

[可选的正文]

[可选的尾部]
```

### 类型
| 类型 | 描述 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 重构（不是新功能也不是修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具变更 |

### 示例
```bash
# 正确
git commit -m "feat(ask): 添加多轮对话上下文继承"
git commit -m "fix(entity): 修复实体链接错误继承上轮指标"
git commit -m "docs(readme): 更新部署说明"
git commit -m "refactor(sql): 重构SQL生成逻辑"

# 错误
git commit -m "fix bug"
git commit -m "update"
git commit -m "wip"
```

### Commit 消息正文
```bash
git commit -m "fix(ask): 修复多轮对话实体继承问题

问题：用户问'用户数呢'后，再问'业务口径呢'会错误继承
解决方案：
- 添加last_valid_metric字段保存最后有效的指标
- 在entity_node中正确判断是否为follow-up查询
- 清除上一轮的错误状态

影响范围：智能问数多轮对话功能
"

# 多行提交
git commit -m "feat(graph): 添加对话状态管理

- 实现last_valid_metric跟踪最后有效指标
- 修复entity_node在失败后错误继承的问题
- 优化错误消息显示逻辑

Closes #123
```

## PR 规范

### PR 标题
```
[类型] 简短描述

示例：
[Feature] 添加多轮对话支持
[Bugfix] 修复实体继承错误
[Refactor] 重构SQL生成逻辑
```

### PR 描述模板
```markdown
## 变更内容
[描述本次变更的内容]

## 影响范围
[描述影响的功能/模块]

## 测试验证
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动验证通过

## 截图（如果有UI变更）
[截图]
```

## 合并流程
```bash
# 1. 保持分支最新
git checkout main
git pull origin main
git checkout feature/xxx
git rebase main

# 2. 推送分支
git push origin feature/xxx

# 3. 创建 PR
gh pr create --title "[Feature] xxx" --body "$(cat PR_TEMPLATE.md)"

# 4. Code Review 后合并
gh pr merge --squash
```

## 保护分支
- `main` 分支禁止直接推送
- 所有变更必须通过 PR
- 必须有 Code Review 才能合并
- CI 测试必须通过
