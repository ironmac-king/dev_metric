# 代码风格规范

## Go 代码规范

### 命名规范
```go
// 变量命名
var userCount int        // 驼峰式
var user_name string     // ❌ 禁止使用下划线

// 常量命名
const MaxRetryCount = 3 // 全大写下划线分隔

// 函数命名
func GetUserByID() {}   // 驼峰式，公开函数大写开头
func getUserByID() {}    // 私有函数小写开头

// 接口命名
type Reader interface {} // 接口名+er后缀
```

### 错误处理
```go
// ✅ 正确：检查错误并返回
func doSomething() error {
    if err := doThing(); err != nil {
        return fmt.Errorf("doSomething failed: %w", err)
    }
    return nil
}

// ❌ 错误：忽略错误
doSomething()
```

### 包管理
```go
// ✅ 正确：使用完整导入路径
import (
    "fmt"
    "net/http"
    "github.com/xxx/project/internal/model"
)

// ❌ 错误：相对路径
import "../model"
```

### 注释规范
```go
// GetUserByID 根据用户ID获取用户信息
// 参数：
//   - id: 用户ID
// 返回：用户信息，错误信息
func GetUserByID(id int) (*User, error) {
    // ...
}
```

## Python 代码规范

### 命名规范
```python
# 变量命名
user_count = 0        # 下划线式
userName = ""         # ❌ 禁止使用驼峰

# 类命名
class UserService:     # 驼峰式，首字母大写
class _BaseHandler:   # 私有类前导下划线

# 常量命名
MAX_RETRY_COUNT = 3   # 全大写下划线分隔
```

### 类型注解
```python
# ✅ 推荐：使用类型注解
def get_user_by_id(user_id: int) -> Optional[User]:
    pass

# ❌ 避免：无类型信息
def get_user_by_id(user_id):
    pass
```

### 异步代码
```python
# ✅ 正确：异步函数使用async/await
async def fetch_data(url: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ❌ 错误：混用同步异步
def fetch_data(url):
    response = requests.get(url)  # 同步调用在async函数中
```

## 前端代码规范 (Vue 3)

### 组件命名
```vue
<!-- ✅ 正确：PascalCase -->
<template>
  <UserProfile />
  <MetricCard />
</template>

<!-- ❌ 错误： kebab-case 在模板中 -->
<user-profile />
```

### 样式规范
```vue
<style scoped>
/* ✅ 使用 scoped 防止样式泄漏 */
.card {
  padding: 16px;
}

/* ✅ 使用 CSS 变量 */
color: var(--color-primary);
</style>
```

### API 调用
```typescript
// ✅ 正确：封装 API 调用
import { metricApi } from '@/api/metrics'

async function fetchMetrics() {
  const { data } = await metricApi.list()
  return data
}
```

## 架构设计规范

### 核心原则：调整逻辑或新增功能必须考虑架构冲突

在修改现有代码时，**必须先分析对现有架构的影响**，尤其是多层或有状态流（如 LangGraph）的场景。

### 常见架构冲突模式

#### 1. 多层状态流冲突
**问题**：在一个节点设置的字段，被后续节点依赖或覆盖，导致状态不一致。

**示例**：在 `intent_node` 中设置 `needs_clarification=True` 跳过 `entity_node`，但 `entity_node` 负责识别具体实体值，导致实体永远不会被识别。

**排查方法**：
- 检查是否有节点提前返回（跳过后续节点）
- 检查后续节点是否依赖前置节点设置的状态

#### 2. 职责边界冲突
**问题**：新逻辑与现有逻辑职责重叠，产生重复处理或死锁。

**示例**：
- 旧：`detect_intent_override` 检测到"品类"就触发 `category_level` 追问
- 新：`SlotClarificationEngine` 统一处理槽位追问
- 冲突：两套追问逻辑并存，新逻辑无法生效

**排查方法**：
- 新增功能前先梳理现有代码的数据流
- 检查是否有两处以上设置同一个状态字段

#### 3. 时序冲突
**问题**：在某节点检查的状态，依赖后续节点才能填充。

**示例**：在 `intent_node` 末尾检查 `entity` 槽位是否有值，但 `entity_node` 还没运行。

**排查方法**：
- 绘制数据流图，确认节点顺序
- 检查依赖状态在检查点之前是否已填充

### 冲突解决原则

| 原则 | 说明 |
|------|------|
| **单一职责** | 一个状态字段只由一个来源设置 |
| **后置检查** | 状态检查应在状态填充之后 |
| **渐进迁移** | 废弃旧逻辑时，确保新逻辑完全接管 |
| **完整验证** | 修改后必须端到端测试数据流 |

### 验证检查清单

新增/修改代码时，必须确认：

- [ ] 是否影响了其他节点的执行路径？
- [ ] 是否有状态字段被多处设置？
- [ ] 依赖的状态在检查点是否已填充？
- [ ] 是否有新旧两套逻辑并存的风险？
- [ ] 是否需要废弃旧逻辑或添加迁移注释？
