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
