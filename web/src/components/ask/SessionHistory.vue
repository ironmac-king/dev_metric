<template>
  <!-- 悬浮按钮 -->
  <div class="session-history-trigger" :class="{ expanded: isExpanded }">
    <button class="trigger-btn" @click="togglePanel" :title="isExpanded ? '收起会话历史' : '查看会话历史'">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <rect x="2" y="3" width="14" height="2" rx="1" fill="currentColor"/>
        <rect x="2" y="8" width="10" height="2" rx="1" fill="currentColor"/>
        <rect x="2" y="13" width="12" height="2" rx="1" fill="currentColor"/>
      </svg>
      <span v-if="!isExpanded && sessionCount > 0" class="badge">{{ sessionCount > 99 ? '99+' : sessionCount }}</span>
    </button>

    <!-- 侧边面板 -->
    <transition name="slide">
      <div v-if="isExpanded" class="history-panel">
        <!-- 面板头部 -->
        <div class="panel-header">
          <span class="panel-title">会话记录</span>
          <button class="close-btn" @click="togglePanel" title="收起">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>

        <!-- 新建会话按钮 -->
        <button class="new-session-btn" @click="handleNewSession">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>新建会话</span>
        </button>

        <!-- 会话列表 -->
        <div class="session-list" v-loading="loading">
          <div v-if="sessions.length === 0 && !loading" class="empty-state">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="12" stroke="#D1D5DB" stroke-width="1.5"/>
              <path d="M12 16H20M16 12V20" stroke="#D1D5DB" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <p>暂无会话记录</p>
          </div>

          <div
            v-for="session in sessions"
            :key="session.session_id"
            class="session-item"
            :class="{ active: session.session_id === currentSessionId }"
            @click="handleSelectSession(session)"
          >
            <div class="session-content">
              <div class="session-title">{{ session.title || '新会话' }}</div>
              <div class="session-preview">{{ session.first_question || '...' }}</div>
            </div>
            <button
              class="delete-btn"
              @click.stop="handleDeleteSession(session)"
              title="删除"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 3.5H12M5 3.5V2.5C5 2.22386 5.22386 2 5.5 2H8.5C8.77614 2 9 2.22386 9 2.5V3.5M11 3.5V11.5C11 11.7761 10.7761 12 10.5 12H3.5C3.22386 12 3 11.7761 3 11.5V3.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { sessionApi } from '@/api/llmAsk'
import { ElMessage, ElMessageBox } from 'element-plus'

const emit = defineEmits(['select-session', 'new-session'])

const isExpanded = ref(false)
const loading = ref(false)
const sessions = ref([])

const currentSessionId = computed(() => {
  try {
    const state = JSON.parse(localStorage.getItem('llm_ask_state') || '{}')
    return state.sessionId || ''
  } catch {
    return ''
  }
})

const sessionCount = computed(() => sessions.value.length)

function togglePanel() {
  isExpanded.value = !isExpanded.value
  if (isExpanded.value) {
    loadSessions()
  }
}

async function loadSessions() {
  loading.value = true
  try {
    const res = await sessionApi.list()
    if (res.code === 0) {
      sessions.value = res.data || []
    }
  } catch (e) {
    console.error('加载会话列表失败:', e)
  } finally {
    loading.value = false
  }
}

function handleSelectSession(session) {
  emit('select-session', session)
}

function handleNewSession() {
  emit('new-session')
  isExpanded.value = false
}

async function handleDeleteSession(session) {
  try {
    await ElMessageBox.confirm(
      `确定删除该会话？`,
      '提示',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await sessionApi.delete(session.session_id)
    ElMessage.success('已删除')
    sessions.value = sessions.value.filter(s => s.session_id !== session.session_id)
    if (session.session_id === currentSessionId.value) {
      emit('new-session')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date

  if (diff < 86400000) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  if (diff < 604800000) {
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return weekdays[date.getDay()]
  }
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

defineExpose({
  refreshSessions: loadSessions
})

onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.session-history-trigger {
  position: fixed;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 100;
  display: flex;
  align-items: flex-start;
}

.trigger-btn {
  width: 36px;
  height: 36px;
  border-radius: 0 8px 8px 0;
  background: #FFFFFF;
  color: #1F2937;
  border: 1px solid #E5E7EB;
  border-left: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: all 0.2s ease;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
}

.trigger-btn:hover {
  background: #F9FAFB;
  color: #3B82F6;
}

.trigger-btn .badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: #3B82F6;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.history-panel {
  width: 240px;
  height: calc(100vh - 120px);
  background: #FFFFFF;
  border-right: 1px solid #E5E7EB;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #F3F4F6;
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
  color: #1F2937;
}

.close-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: #9CA3AF;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.close-btn:hover {
  background: #F3F4F6;
  color: #6B7280;
}

.new-session-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: calc(100% - 24px);
  margin: 12px;
  padding: 8px 12px;
  background: transparent;
  color: #6B7280;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s ease;
}

.new-session-btn:hover {
  background: #F9FAFB;
  color: #1F2937;
  border-color: #D1D5DB;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #9CA3AF;
  text-align: center;
}

.empty-state p {
  margin-top: 8px;
  font-size: 13px;
}

.session-item {
  display: flex;
  align-items: flex-start;
  padding: 10px 8px;
  margin-bottom: 2px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

.session-item:hover {
  background: #F9FAFB;
}

.session-item.active {
  background: #F0F7FF;
}

.session-content {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: #1F2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.session-preview {
  font-size: 12px;
  color: #9CA3AF;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.delete-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: #D1D5DB;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: #FEE2E2;
  color: #EF4444;
}

/* 过渡动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}
</style>
