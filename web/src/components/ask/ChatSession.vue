<template>
  <aside class="session-sidebar" :class="{ collapsed: collapsed }">
    <div class="sidebar-header">
      <h3 v-if="!collapsed">会话历史</h3>
      <button class="collapse-btn cursor-pointer" @click="$emit('toggle-collapse')">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path v-if="collapsed" d="M6 5L11 9L6 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          <path v-else d="M12 5L7 9L12 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
    </div>

    <div class="session-list" v-if="!collapsed">
      <!-- 分组会话历史 -->
      <div v-for="group in groupedSessions" :key="group.label" class="session-group">
        <div
          class="session-group-header cursor-pointer"
          @click="toggleGroup(group.label)"
        >
          <svg
            class="group-arrow"
            :class="{ collapsed: !expandedGroups[group.label] }"
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
          >
            <path d="M4 3L7 6L4 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="group-label">{{ group.label }}</span>
          <span class="group-count">{{ group.sessions.length }}</span>
        </div>

        <div v-show="expandedGroups[group.label]" class="session-group-content">
          <AskSessionCard
            v-for="session in group.sessions"
            :key="session.session_id || session.id"
            :session="session"
            :is-active="activeId === (session.session_id || session.id)"
            @click="$emit('select', session.session_id || session.id)"
            @star="$emit('star', session)"
            @delete="$emit('delete', session.session_id || session.id)"
          />
        </div>
      </div>

      <div v-if="!sessions.length" class="empty-sessions">
        暂无历史会话
      </div>
    </div>

    <div class="sidebar-footer" v-if="!collapsed">
      <button class="new-chat-btn cursor-pointer" @click="$emit('new-chat')">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        新建对话
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import AskSessionCard from '../../views/components/AskSessionCard.vue'

const props = defineProps<{
  sessions: Array<{
    id?: string | number
    session_id?: string | number
    created_at?: string
    [key: string]: any
  }>
  activeId: string | number
  collapsed: boolean
}>()

defineEmits<{
  select: [id: string | number]
  star: [session: any]
  delete: [id: string | number]
  'new-chat': []
  'toggle-collapse': []
}>()

// 分组展开状态（默认只有今天和昨天展开）
const expandedGroups = ref<Record<string, boolean>>({
  '今天': true,
  '昨天': true,
  '上周': false,
  '上月': false,
  '更早': false
})

// 切换分组展开/折叠
function toggleGroup(label: string) {
  expandedGroups.value[label] = !expandedGroups.value[label]
}

// 按时间分组会话
const groupedSessions = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)
  const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate())

  const groups: Record<string, typeof props.sessions> = {
    '今天': [],
    '昨天': [],
    '上周': [],
    '上月': [],
    '更早': []
  }

  for (const session of props.sessions) {
    const sessionDate = session.created_at ? new Date(session.created_at) : new Date(0)

    if (sessionDate >= today) {
      groups['今天'].push(session)
    } else if (sessionDate >= yesterday) {
      groups['昨天'].push(session)
    } else if (sessionDate >= lastWeek) {
      groups['上周'].push(session)
    } else if (sessionDate >= lastMonth) {
      groups['上月'].push(session)
    } else {
      groups['更早'].push(session)
    }
  }

  // 返回有数据的分组，按预设顺序
  const order = ['今天', '昨天', '上周', '上月', '更早']
  return order
    .filter(label => groups[label].length > 0)
    .map(label => ({
      label,
      sessions: groups[label]
    }))
})

// 如果当前选中的会话不在展开的分组中，自动展开
watch(() => props.activeId, (newId) => {
  for (const group of groupedSessions.value) {
    const hasActive = group.sessions.some(s => (s.session_id || s.id) === newId)
    if (hasActive && !expandedGroups.value[group.label]) {
      expandedGroups.value[group.label] = true
    }
  }
})
</script>

<style scoped>
.session-sidebar {
  width: 220px;
  min-width: 220px;
  background: var(--bg-card);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  position: relative;
  z-index: 10;
  border-right: 1px solid var(--border);
  overflow: hidden;
}

.session-sidebar.collapsed {
  width: 0;
  min-width: 0;
  overflow: hidden;
}

.sidebar-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-header h3 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.collapse-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 0.15s;
}

.collapse-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  overflow-x: hidden;
  width: 100%;
  box-sizing: border-box;
}

/* 分组会话历史 */
.session-group {
  margin-bottom: 4px;
}

.session-group-header {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background 0.15s;
  gap: 6px;
}

.session-group-header:hover {
  background: var(--bg-primary);
}

.group-arrow {
  color: var(--text-muted);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.group-arrow.collapsed {
  transform: rotate(-90deg);
}

.group-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  flex: 1;
}

.group-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-primary);
  padding: 1px 6px;
  border-radius: 10px;
}

.session-group-content {
  padding-left: 4px;
}

.empty-sessions {
  text-align: center;
  padding: 40px 16px;
  color: var(--text-muted);
  font-size: 13px;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border);
}

.new-chat-btn {
  width: 100%;
  padding: 10px;
  border: 1px dashed var(--border);
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.new-chat-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-glow);
}
</style>
