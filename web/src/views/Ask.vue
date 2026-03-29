<template>
  <div class="ask-page">
    <!-- 背景装饰 -->
    <div class="bg-gradient"></div>
    <div class="bg-blur"></div>

    <!-- 左侧会话历史 -->
    <aside class="session-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <h3 v-if="!sidebarCollapsed">会话历史</h3>
        <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path v-if="sidebarCollapsed" d="M7 5L12 10L7 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path v-else d="M13 5L8 10L13 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>

      <div class="session-list" v-if="!sidebarCollapsed">
        <div
          v-for="session in sessionHistory"
          :key="session.id"
          class="session-item"
          :class="{ active: sessionId === session.id }"
          @click="loadSession(session.id)"
        >
          <div class="session-info">
            <div class="session-title">{{ session.title || '新对话' }}</div>
            <div class="session-time">{{ formatTime(session.updated_at) }}</div>
          </div>
          <button class="delete-btn" @click.stop="deleteSession(session.id)">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3 3L11 11M3 11L11 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>

        <div v-if="!sessionHistory.length" class="empty-sessions">
          暂无历史会话
        </div>
      </div>

      <div class="sidebar-footer" v-if="!sidebarCollapsed">
        <button class="new-chat-btn" @click="createNewSession">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M9 3V15M3 9H15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          新建对话
        </button>
      </div>
    </aside>

    <!-- 主聊天区域 -->
    <div class="chat-main">
      <!-- 头部 -->
      <header class="chat-header">
        <div class="header-left">
          <div class="ai-avatar">
            <div class="ai-avatar-inner">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                <circle cx="14" cy="14" r="12" stroke="currentColor" stroke-width="1.5"/>
                <circle cx="14" cy="10" r="3" fill="currentColor"/>
                <circle cx="14" cy="18" r="2" fill="currentColor" opacity="0.5"/>
                <path d="M10 18C10 18 11.5 21 14 21C16.5 21 18 18 18 18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </div>
          </div>
          <div class="header-info">
            <h2>智能问数助手</h2>
            <div class="status-indicator">
              <span class="status-dot"></span>
              在线
            </div>
          </div>
        </div>
        <div class="header-actions">
          <el-dropdown trigger="click" @command="handleCommand">
            <button class="action-btn">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="5" r="1.5" fill="currentColor"/>
                <circle cx="10" cy="10" r="1.5" fill="currentColor"/>
                <circle cx="10" cy="15" r="1.5" fill="currentColor"/>
              </svg>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="clear">清空当前对话</el-dropdown-item>
                <el-dropdown-item command="export">导出对话记录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 消息区域 -->
      <div class="chat-messages" ref="messagesContainer">
        <!-- 欢迎界面 -->
        <div v-if="!messages.length" class="welcome-screen">
          <div class="welcome-icon">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
              <circle cx="32" cy="32" r="28" stroke="#409EFF" stroke-width="2" opacity="0.3"/>
              <circle cx="32" cy="32" r="20" stroke="#409EFF" stroke-width="2" opacity="0.5"/>
              <circle cx="32" cy="32" r="12" stroke="#409EFF" stroke-width="2"/>
              <circle cx="32" cy="24" r="4" fill="#409EFF"/>
              <circle cx="32" cy="38" r="3" fill="#409EFF" opacity="0.5"/>
              <path d="M26 38C26 38 28.5 44 32 44C35.5 44 38 38 38 38" stroke="#409EFF" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </div>
          <h1>有什么可以帮您的？</h1>
          <p>可以问我关于指标数据、业务口径、技术口径等问题</p>

          <div class="quick-queries">
            <div class="quick-query" v-for="q in quickQueries" :key="q.text" @click="handleSuggest(q.text)">
              <span class="query-icon">{{ q.icon }}</span>
              <span class="query-text">{{ q.text }}</span>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <transition-group name="message" tag="div" class="message-list">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            class="message"
            :class="msg.role"
          >
            <div class="message-avatar" :class="msg.role">
              <template v-if="msg.role === 'user'">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="8" r="4" fill="currentColor"/>
                  <path d="M4 20C4 16.6863 7.58172 14 12 14C16.4183 14 20 16.6863 20 20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </template>
              <template v-else>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/>
                  <circle cx="12" cy="9" r="2.5" fill="currentColor"/>
                  <circle cx="12" cy="15" r="1.5" fill="currentColor" opacity="0.5"/>
                  <path d="M9 15C9 15 10.2 18 12 18C13.8 18 15 15 15 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </template>
            </div>

            <div class="message-bubble">
              <!-- 思考过程 -->
              <div v-if="msg.thinking_steps && msg.thinking_steps.length > 0" class="thinking-process">
                <div class="thinking-header" @click="toggleThinking(msg)">
                  <div class="thinking-status">
                    <svg v-if="msg.thinking_expanded" width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M3 5L6 8L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    <svg v-else width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M5 3L8 6L5 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    <span>思考过程</span>
                  </div>
                  <div class="thinking-progress">
                    <span
                      v-for="(step, sIdx) in msg.thinking_steps"
                      :key="sIdx"
                      class="progress-dot"
                      :class="step.status"
                      :title="step.step + ': ' + step.status"
                    ></span>
                  </div>
                </div>
                <div v-if="msg.thinking_expanded" class="thinking-details">
                  <div
                    v-for="(step, sIdx) in msg.thinking_steps"
                    :key="sIdx"
                    class="thinking-step"
                    :class="step.status"
                  >
                    <div class="step-indicator">
                      <span class="step-icon">
                        <svg v-if="step.status === 'completed'" width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                          <path d="M4 7L6 9L10 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                        <svg v-else-if="step.status === 'error'" width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                          <path d="M5 5L9 9M9 5L5 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                        <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                        </svg>
                      </span>
                      <span class="step-name">{{ step.step }}</span>
                    </div>
                    <div v-if="step.content" class="step-content">{{ step.content }}</div>
                  </div>
                </div>
              </div>

              <div class="message-content" v-html="formatMessage(msg.content)"></div>
              <div v-if="msg.sql" class="message-sql">
                <div class="sql-header">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="1" y="1" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.2"/>
                    <path d="M4 5L7 7L4 9M8 9H10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                  </svg>
                  <span>SQL</span>
                </div>
                <pre><code>{{ msg.sql }}</code></pre>
              </div>
              <div class="message-time">{{ formatMessageTime(msg.created_at) }}</div>

              <!-- 反馈按钮（仅助手消息显示） -->
              <div v-if="msg.role === 'assistant'" class="message-feedback">
                <span class="feedback-label">回答满意吗？</span>
                <button
                  class="feedback-btn thumbs-up"
                  :class="{ active: msg.feedback === 1 }"
                  @click="handleFeedback(index, 1)"
                  title="满意"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M8 14C8 14 3 10.5 3 6.5C3 4.567 4.343 3 6 3C6.895 3 7.643 3.553 8 4C8.357 3.553 9.105 3 10 3C11.657 3 13 4.567 13 6.5C13 10.5 8 14 8 14Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
                <button
                  class="feedback-btn thumbs-down"
                  :class="{ active: msg.feedback === -1 }"
                  @click="handleFeedback(index, -1)"
                  title="不满意"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M8 2C8 2 13 5.5 13 9.5C13 11.433 11.657 13 10 13C9.105 13 8.357 12.447 8 12C7.643 12.447 6.895 13 6 13C4.343 13 3 11.433 3 9.5C3 5.5 8 2 8 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </transition-group>

        <!-- 加载动画 -->
        <div v-if="loading" class="message assistant">
          <div class="message-avatar assistant">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/>
              <circle cx="12" cy="9" r="2.5" fill="currentColor"/>
              <circle cx="12" cy="15" r="1.5" fill="currentColor" opacity="0.5"/>
              <path d="M9 15C9 15 10.2 18 12 18C13.8 18 15 15 15 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="message-bubble">
            <div class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="chat-input-area">
        <div class="input-wrapper">
          <el-input
            v-model="inputText"
            placeholder="输入您的问题..."
            @keyup.enter="handleSend"
            :disabled="loading"
            resize="none"
            rows="1"
            type="textarea"
            autosize
            class="chat-input"
          />
          <button class="send-btn" @click="handleSend" :disabled="loading || !inputText.trim()">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M3 10L17 10M17 10L12 5M17 10L12 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
        <div class="input-hint">
          按 Enter 发送，Shift + Enter 换行
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { askAPI } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const inputText = ref('')
const messages = ref([])
const loading = ref(false)
const sessionId = ref(localStorage.getItem('ask_session_id') || '')
const sessionHistory = ref([])
const sidebarCollapsed = ref(false)
const messagesContainer = ref(null)

const quickQueries = [
  { icon: '📊', text: '昨天的访客数是多少' },
  { icon: '📈', text: '本周订单量如何' },
  { icon: '📉', text: '本月销售额趋势' },
  { icon: '📝', text: '广告转化率的业务口径是什么' },
]

onMounted(() => {
  loadSessionHistory()
  if (sessionId.value) {
    loadSession(sessionId.value)
  }
})

async function loadSessionHistory() {
  try {
    const res = await askAPI.getHistory(sessionId.value)
    if (res.data?.sessions) {
      sessionHistory.value = res.data.sessions
    }
  } catch (e) {
    console.error('加载会话历史失败:', e)
  }
}

async function loadSession(id) {
  try {
    const res = await askAPI.getHistory(id)
    if (res.data?.messages) {
      sessionId.value = id
      localStorage.setItem('ask_session_id', id)
      messages.value = res.data.messages.map(m => ({
        role: m.role,
        content: m.content,
        sql: m.sql,
        created_at: m.created_at,
        thinking_expanded: true,
        thinking_steps: []
      }))
      await scrollToBottom()
    }
  } catch (e) {
    console.error('加载会话失败:', e)
  }
}

async function createNewSession() {
  sessionId.value = ''
  localStorage.removeItem('ask_session_id')
  messages.value = []
  await loadSessionHistory()
}

async function deleteSession(id) {
  try {
    await ElMessageBox.confirm('确定要删除这个会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await askAPI.clearSession(id)
    if (sessionId.value === id) {
      await createNewSession()
    }
    await loadSessionHistory()
    ElMessage.success('删除成功')
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除会话失败:', e)
    }
  }
}

async function handleSend() {
  if (!inputText.value.trim() || loading.value) return

  const question = inputText.value.trim()
  inputText.value = ''

  messages.value.push({
    role: 'user',
    content: question,
    created_at: new Date().toISOString(),
    thinking_expanded: true,
    thinking_steps: []
  })

  await scrollToBottom()
  loading.value = true

  try {
    const res = await askAPI.ask({
      question,
      session_id: sessionId.value || undefined
    })

    if (res.data) {
      if (!sessionId.value && res.data.session_id) {
        sessionId.value = res.data.session_id
        localStorage.setItem('ask_session_id', sessionId.value)
        await loadSessionHistory()
      }

      // Debug: 检查 thinking_steps
      console.log('API response res:', res)
      console.log('thinking_steps:', res.data?.thinking_steps)

      messages.value.push({
        role: 'assistant',
        content: res.data.answer,
        sql: res.data.sql,
        created_at: new Date().toISOString(),
        thinking_expanded: true,
        thinking_steps: res.data.thinking_steps || []
      })
    }
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，服务暂时不可用，请稍后再试。',
      created_at: new Date().toISOString(),
      thinking_expanded: true,
      thinking_steps: []
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

function handleSuggest(text) {
  inputText.value = text
  handleSend()
}

async function handleCommand(command) {
  if (command === 'clear') {
    messages.value = []
    ElMessage.success('对话已清空')
  } else if (command === 'export') {
    const content = messages.value.map(m =>
      `${m.role === 'user' ? '我' : '助手'}：${m.content}`
    ).join('\n\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `对话记录_${new Date().toLocaleDateString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function toggleThinking(msg) {
  msg.thinking_expanded = !msg.thinking_expanded
}

function formatTime(time) {
  if (!time) return ''
  const d = new Date(time)
  const now = new Date()
  const diff = now - d

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatMessageTime(time) {
  if (!time) return ''
  return new Date(time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatMessage(content) {
  // 简单的格式化：换行和粗体
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

async function handleFeedback(index, feedback) {
  const msg = messages.value[index]
  if (msg.feedback) {
    ElMessage.info('您已经反馈过了')
    return
  }

  msg.feedback = feedback

  try {
    await askAPI.sendFeedback({
      session_id: sessionId.value,
      turn_index: index,
      feedback: feedback,
      metric_id: msg.metric_id || null,
      clarification_type: msg.clarification_type || null,
      clarification_question: msg.clarification_question || null
    })
    ElMessage.success(feedback === 1 ? '感谢您的肯定！' : '感谢您的反馈，我们会继续优化')
  } catch (e) {
    msg.feedback = null
    ElMessage.error('反馈失败，请重试')
  }
}
</script>

<style scoped>
.ask-page {
  height: 100vh;
  display: flex;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #F5F7FA 0%, #E8ECF3 100%);
}

/* 背景装饰 */
.bg-gradient {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background:
    radial-gradient(circle at 20% 20%, rgba(64, 158, 255, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(103, 194, 58, 0.06) 0%, transparent 50%);
  pointer-events: none;
}

.bg-blur {
  position: fixed;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
  opacity: 0.03;
  pointer-events: none;
}

/* 侧边栏 */
.session-sidebar {
  width: 280px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  position: relative;
  z-index: 10;
}

.session-sidebar.collapsed {
  width: 60px;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
}

.collapse-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #7177a4;
  transition: all 0.15s;
}

.collapse-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #1a1a1a;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 4px;
}

.session-item:hover {
  background: rgba(64, 158, 255, 0.08);
}

.session-item.active {
  background: rgba(64, 158, 255, 0.12);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  color: #1a1a1a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.delete-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  opacity: 0;
  transition: all 0.15s;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(245, 108, 108, 0.1);
  color: #F56C6C;
}

.empty-sessions {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
  font-size: 14px;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.new-chat-btn {
  width: 100%;
  padding: 12px;
  border: 1px dashed rgba(64, 158, 255, 0.4);
  background: transparent;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #409EFF;
  transition: all 0.15s;
}

.new-chat-btn:hover {
  background: rgba(64, 158, 255, 0.08);
  border-color: #409EFF;
}

/* 主聊天区域 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 5;
}

/* 头部 */
.chat-header {
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ai-avatar {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, #409EFF 0%, #66B1FF 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.header-info h2 {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 4px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #67C23A;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #67C23A;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.action-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #7177a4;
  transition: all 0.15s;
}

.action-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #1a1a1a;
}

/* 消息区域 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.welcome-screen {
  text-align: center;
  padding: 60px 20px;
  animation: fadeIn 0.5s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.welcome-icon {
  margin-bottom: 24px;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.welcome-screen h1 {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 12px;
}

.welcome-screen p {
  font-size: 14px;
  color: #7177a4;
  margin-bottom: 32px;
}

.quick-queries {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  max-width: 500px;
  margin: 0 auto;
}

.quick-query {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.quick-query:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  border-color: #409EFF;
}

.query-icon {
  font-size: 20px;
}

.query-text {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

/* 消息列表 */
.message-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message {
  display: flex;
  gap: 14px;
  animation: messageIn 0.3s ease;
}

@keyframes messageIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-avatar.user {
  background: linear-gradient(135deg, #909399 0%, #B1B3B8 100%);
  color: white;
}

.message-avatar.assistant {
  background: linear-gradient(135deg, #409EFF 0%, #66B1FF 100%);
  color: white;
}

.message-bubble {
  max-width: 70%;
  min-width: 100px;
}

.message-content {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: 14px 18px;
  border-radius: 16px;
  border-top-left-radius: 4px;
  font-size: 14px;
  line-height: 1.7;
  color: #303133;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.message.user .message-content {
  background: linear-gradient(135deg, #409EFF 0%, #66B1FF 100%);
  color: white;
  border-top-left-radius: 16px;
  border-top-right-radius: 4px;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.3);
}

.message-sql {
  margin-top: 10px;
  background: #f5f7fa;
  border-radius: 10px;
  overflow: hidden;
}

.sql-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #ebeef5;
  font-size: 12px;
  font-weight: 500;
  color: #606266;
}

.message-sql pre {
  padding: 12px;
  margin: 0;
  overflow-x: auto;
}

.message-sql code {
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: #303133;
}

/* 思考过程 */
.thinking-process {
  margin-bottom: 12px;
  background: linear-gradient(135deg, #f8f9fb 0%, #f0f2f5 100%);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(64, 158, 255, 0.15);
}

.thinking-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.15s;
}

.thinking-header:hover {
  background: rgba(64, 158, 255, 0.05);
}

.thinking-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #409EFF;
}

.thinking-progress {
  display: flex;
  align-items: center;
  gap: 4px;
}

.progress-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #dcdfe6;
  transition: all 0.2s;
}

.progress-dot.completed {
  background: #67C23A;
  box-shadow: 0 0 4px rgba(103, 194, 58, 0.4);
}

.progress-dot.error {
  background: #F56C6C;
  box-shadow: 0 0 4px rgba(245, 108, 108, 0.4);
}

.progress-dot.pending {
  background: #dcdfe6;
  animation: pulse-dot 1.5s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.thinking-details {
  padding: 0 14px 14px;
  animation: slideDown 0.2s ease;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.thinking-step {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.thinking-step:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.step-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}

.thinking-step.completed .step-icon {
  color: #67C23A;
}

.thinking-step.error .step-icon {
  color: #F56C6C;
}

.thinking-step.pending .step-icon {
  color: #909399;
}

.step-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.step-content {
  font-size: 12px;
  color: #7177a4;
  line-height: 1.6;
  padding-left: 28px;
  word-break: break-all;
}

.message-time {
  font-size: 11px;
  color: #909399;
  margin-top: 6px;
  text-align: right;
}

.message.user .message-time {
  text-align: left;
}

/* 反馈按钮 */
.message-feedback {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.feedback-label {
  font-size: 12px;
  color: #909399;
}

.feedback-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
  transition: all 0.15s;
}

.feedback-btn:hover {
  background: rgba(0, 0, 0, 0.05);
}

.feedback-btn.thumbs-up:hover,
.feedback-btn.thumbs-up.active {
  color: #67C23A;
  background: rgba(103, 194, 58, 0.1);
}

.feedback-btn.thumbs-down:hover,
.feedback-btn.thumbs-down.active {
  color: #F56C6C;
  background: rgba(245, 108, 108, 0.1);
}

.feedback-btn.active {
  transform: scale(1.1);
}

/* 加载动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #909399;
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* 输入区域 */
.chat-input-area {
  padding: 16px 24px 24px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(20px);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: white;
  border-radius: 16px;
  padding: 8px 8px 8px 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(0, 0, 0, 0.06);
  transition: all 0.2s;
}

.input-wrapper:focus-within {
  border-color: #409EFF;
  box-shadow: 0 4px 20px rgba(64, 158, 255, 0.15);
}

.chat-input {
  flex: 1;
}

.chat-input :deep(.el-textarea__inner) {
  border: none;
  padding: 8px 0;
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  box-shadow: none !important;
}

.chat-input :deep(.el-textarea__inner:focus) {
  box-shadow: none !important;
}

.send-btn {
  width: 44px;
  height: 44px;
  border: none;
  background: linear-gradient(135deg, #409EFF 0%, #66B1FF 100%);
  border-radius: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-hint {
  font-size: 12px;
  color: #909399;
  text-align: center;
  margin-top: 10px;
}

/* 消息过渡动画 */
.message-enter-active {
  transition: all 0.3s ease;
}
.message-leave-active {
  transition: all 0.2s ease;
}
.message-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.message-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
