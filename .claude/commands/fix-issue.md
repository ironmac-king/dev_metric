# 问题修复命令

## 用途
自动化问题定位和修复流程。

## 执行方式
```
/project:fix-issue <问题描述>
```

## 工作流程

### Step 1: 问题定位
1. 查看错误日志
2. 追踪调用链路
3. 确认问题边界

### Step 2: 根因分析
- 定位到具体文件和代码行
- 分析失败原因
- 确认影响范围

### Step 3: 修复实施
1. 创建修复分支
2. 实施修复
3. 验证修复效果

### Step 4: 回归测试
- 单元测试
- 集成测试
- 手动验证

## 常用问题处理

### API问题
```bash
# 查看API日志
tail -f logs/api.log | grep ERROR

# 测试API端点
curl -X POST http://localhost:8080/api/v1/xxx
```

### 数据库问题
```bash
# 检查连接
psql -h localhost -U postgres -d dev_metric -c "SELECT 1"

# 查看慢查询
SELECT * FROM pg_stat_activity WHERE state = 'active';
```

### AI服务问题
```bash
# 检查Python服务状态
curl http://localhost:8081/health

# 查看AI日志
tail -f ai/logs/*.log
```

## 输出格式
```markdown
## 问题修复报告

### 问题描述
[问题描述]

### 根因分析
[根因分析]

### 修复方案
[修复方案]

### 验证结果
[验证结果]
```
