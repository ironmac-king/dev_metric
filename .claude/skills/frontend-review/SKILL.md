# 前端代码审查技能

## 触发条件
- 代码提交包含 `web/` 目录
- PR 包含前端变更
- 文件扩展名：`.vue`, `.js`, `.ts`, `.jsx`, `.tsx`

## 审查要点

### 1. Vue 3 最佳实践
- [ ] 使用 Composition API 而非 Options API
- [ ] 正确使用 `ref` 和 `reactive`
- [ ] 避免在模板中使用复杂表达式
- [ ] 使用 `defineProps` 和 `defineEmits`

### 2. 组件设计
- [ ] 组件职责单一
- [ ] Props 校验使用 TypeScript 或 PropTypes
- [ ] 避免不必要的组件嵌套
- [ ] 正确使用 `scoped` 样式

### 3. 状态管理
- [ ] Pinia store 结构清晰
- [ ] 避免在组件中直接修改 store
- [ ] 使用 getter 代替重复计算

### 4. API 调用
- [ ] 统一封装 API 调用
- [ ] 错误处理完整
- [ ] 加载状态管理
- [ ] 请求取消处理

### 5. 性能检查
- [ ] 避免不必要的重渲染
- [ ] 使用 `v-memo` 或 `v-once` 优化
- [ ] 图片懒加载
- [ ] 组件按需加载

## 常见问题

### ❌ 错误示例
```vue
<template>
  <!-- 复杂表达式 -->
  <div>{{ items.filter(x => x.id > 5).map(x => x.name).join(',') }}</div>

  <!-- 直接修改 props -->
  <script setup>
  props.title = 'new title'  // ❌ 错误
  </script>
</template>
```

### ✅ 正确示例
```vue
<template>
  <!-- 使用计算属性 -->
  <div>{{ displayedItems }}</div>
</template>

<script setup>
import { computed } from 'vue'

const displayedItems = computed(() => {
  return items.value
    .filter(x => x.id > 5)
    .map(x => x.name)
    .join(',')
})
</script>
```

## 自动化检查
```bash
# 运行 ESLint
cd web && npm run lint

# 运行类型检查
cd web && npm run type-check

# 运行测试
cd web && npm run test
```

## 输出格式
```markdown
## 前端代码审查报告

### 问题列表
| 严重程度 | 文件 | 问题 | 建议 |
|---------|------|------|------|
| 🔴 高 | MetricCard.vue | 复杂表达式 | 使用计算属性 |
| 🟡 中 | Dashboard.vue | 内存泄漏 | 添加 onUnmounted 清理 |
```
