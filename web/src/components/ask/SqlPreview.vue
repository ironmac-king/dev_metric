<template>
  <div class="sql-preview" :class="{ expanded: isExpanded }">
    <button class="sql-header" @click="toggle">
      <div class="sql-header-left">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="1" y="1" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.2"/>
          <path d="M4 5L1 7L4 9M10 5L13 7L10 9M7 4L7 10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
        <span class="sql-title">{{ title }}</span>
        <span v-if="!isExpanded" class="sql-hint">点击展开</span>
      </div>
      <svg class="toggle-icon" :class="{ rotated: isExpanded }" width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M3 5L6 8L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
    <transition name="expand">
      <div v-if="isExpanded" class="sql-body">
        <pre class="sql-content"><code v-html="highlightedSql"></code></pre>
        <button v-if="copyable" class="copy-btn" @click="copySql">
          <svg v-if="!copied" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="4" y="4" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
            <path d="M2 10V2H10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5" fill="#10B981"/>
            <path d="M4 7L6 9L10 5" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          {{ copied ? '已复制' : '复制' }}
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  sql: {
    type: String,
    required: true
  },
  title: {
    type: String,
    default: '查询SQL'
  },
  copyable: {
    type: Boolean,
    default: true
  }
})

const isExpanded = ref(false)
const copied = ref(false)

const highlightedSql = computed(() => {
  if (!props.sql) return ''
  // Simple SQL syntax highlighting
  let sql = props.sql
    // Keywords
    .replace(/\b(SELECT|FROM|WHERE|AND|OR|ORDER BY|GROUP BY|HAVING|LIMIT|OFFSET|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|IN|BETWEEN|LIKE|IS|NULL|NOT|UNION|ALL|DISTINCT|INSERT|UPDATE|DELETE|SET|VALUES|CREATE|DROP|ALTER|TABLE|INDEX|VIEW|INTO|ASC|DESC)\b/gi, '<span class="keyword">$1</span>')
    // Functions
    .replace(/\b(SUM|AVG|COUNT|MAX|MIN|COALESCE|IFNULL|CASE|WHEN|THEN|ELSE|END|CAST|CONVERT|VARCHAR|INT|INTEGER|FLOAT|DOUBLE|DECIMAL|DATE|DATETIME|TIMESTAMP|YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)\b/gi, '<span class="function">$1</span>')
    // Numbers
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="number">$1</span>')
    // Strings
    .replace(/'([^']*)'/g, '<span class="string">\'$1\'</span>')
    // Comments
    .replace(/--([^\n]*)/g, '<span class="comment">--$1</span>')
  return sql
})

function toggle() {
  isExpanded.value = !isExpanded.value
}

async function copySql() {
  try {
    // 尝试新版 Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(props.sql)
    } else {
      // fallback: 创建临时 textarea
      const textarea = document.createElement('textarea')
      textarea.value = props.sql
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('复制失败:', err)
  }
}
</script>

<style scoped>
.sql-preview {
  margin-top: 12px;
  background: #F8FAFC;
  border: 1px solid rgba(99, 102, 241, 0.12);
  border-radius: 8px;
  overflow: hidden;
}

.sql-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(99, 102, 241, 0.04);
  border: none;
  cursor: pointer;
  transition: background 0.2s;
}

.sql-header:hover {
  background: rgba(99, 102, 241, 0.08);
}

.sql-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6366F1;
}

.sql-title {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
}

.sql-hint {
  font-size: 11px;
  color: #9ca3af;
  margin-left: 8px;
}

.toggle-icon {
  color: #9ca3af;
  transition: transform 0.2s;
}

.toggle-icon.rotated {
  transform: rotate(180deg);
}

.sql-body {
  padding: 12px;
  position: relative;
  background: #fff;
}

.sql-content {
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  line-height: 1.6;
}

.copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: rgba(99, 102, 241, 0.08);
  border: none;
  border-radius: 4px;
  color: #6366F1;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
  z-index: 10;
}

.copy-btn:hover {
  background: rgba(99, 102, 241, 0.15);
}

/* Expand transition */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>

<style>
/* Global styles for syntax highlighting */
.sql-preview .keyword {
  color: #6366F1;
  font-weight: 600;
}

.sql-preview .function {
  color: #059669;
}

.sql-preview .number {
  color: #7C3AED;
}

.sql-preview .string {
  color: #D97706;
}

.sql-preview .comment {
  color: #9CA3AF;
  font-style: italic;
}
</style>
