<template>
  <div class="session-card" :class="{ active: isActive, starred: session.starred }" @click="$emit('click')">
    <div class="card-main">
      <div class="card-icon">
        <svg v-if="session.starred" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M8 1L10 6H15L11 9L12.5 14L8 11L3.5 14L5 9L1 6H6L8 1Z" fill="#F59E0B" stroke="#F59E0B" stroke-width="1"/>
        </svg>
        <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M8 2L10 6H14L11 9L12 14L8 11L4 14L5 9L2 6H6L8 2Z" stroke="currentColor" stroke-width="1" fill="none"/>
        </svg>
      </div>
      <div class="card-content">
        <div class="card-title">{{ session.title || '新对话' }}</div>
        <div class="card-meta">
          <span class="card-time">{{ formatTime(session.updated_at || session.created_at) }}</span>
          <span v-if="session.message_count" class="card-count">{{ session.message_count }}条消息</span>
        </div>
      </div>
    </div>
    <button class="star-btn" @click.stop="$emit('star')" :title="session.starred ? '取消星标' : '星标'">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path
          d="M7 1L8.5 5H13L9.5 7.5L11 12L7 9.5L3 12L4.5 7.5L1 5H5.5L7 1Z"
          :fill="session.starred ? '#F59E0B' : 'none'"
          :stroke="session.starred ? '#F59E0B' : 'currentColor'"
          stroke-width="1"
        />
      </svg>
    </button>
    <button class="delete-btn" @click.stop="$emit('delete')" title="删除会话">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M3 4H11M5 4V3C5 2.5 5.5 2 6 2H8C8.5 2 9 2.5 9 3V4M10 4V11C10 11.5 9.5 12 9 12H5C4.5 12 4 11.5 4 11V4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
defineProps({
  session: {
    type: Object,
    required: true
  },
  isActive: {
    type: Boolean,
    default: false
  }
})

defineEmits(['click', 'star', 'delete'])

function formatTime(timeStr) {
  if (!timeStr) return ''

  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date

  // 少于1分钟
  if (diff < 60 * 1000) {
    return '刚刚'
  }
  // 少于1小时
  if (diff < 60 * 60 * 1000) {
    return Math.floor(diff / 60000) + '分钟前'
  }
  // 少于24小时
  if (diff < 24 * 60 * 60 * 1000) {
    return Math.floor(diff / 3600000) + '小时前'
  }
  // 少于7天
  if (diff < 7 * 24 * 60 * 60 * 1000) {
    return Math.floor(diff / 86400000) + '天前'
  }

  // 超过7天显示日期
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.session-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  background: transparent;
  width: 100%;
  box-sizing: border-box;
}

.session-card:hover {
  background: var(--bg-hover);
}

.session-card.active {
  background: var(--bg-active);
}

.card-main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.card-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.session-card.starred .card-icon {
  color: #F59E0B;
}

.card-content {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.card-time {
}

.card-count {
}

.star-btn {
  flex-shrink: 0;
  padding: 4px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-tertiary);
  opacity: 0;
  transition: opacity 0.15s;
}

.session-card:hover .star-btn,
.session-card.starred .star-btn {
  opacity: 1;
}

.star-btn:hover {
  color: #F59E0B;
}

.delete-btn {
  flex-shrink: 0;
  padding: 4px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-tertiary);
  opacity: 0;
  transition: opacity 0.15s;
}

.session-card:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: var(--danger);
}
</style>
