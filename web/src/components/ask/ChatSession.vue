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
      <AskSessionCard
        v-for="session in sessions"
        :key="session.session_id || session.id"
        :session="session"
        :is-active="activeId === (session.session_id || session.id)"
        @click="$emit('select', session.session_id || session.id)"
        @star="$emit('star', session)"
        @delete="$emit('delete', session.session_id || session.id)"
      />

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
import AskSessionCard from '../../views/components/AskSessionCard.vue'

defineProps<{
  sessions: Array<{
    id?: string | number
    session_id?: string | number
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
