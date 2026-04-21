<template>
  <div class="ask-page">
    <!-- 背景装饰 -->
    <div class="bg-gradient"></div>

    <!-- 左侧会话历史 -->
    <ChatSession
      :sessions="sessionHistory"
      :active-id="sessionId"
      :collapsed="sidebarCollapsed"
      @select="loadSession"
      @star="toggleStarSession"
      @delete="deleteSession"
      @new-chat="createNewSession"
      @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
    />

    <!-- 主聊天区域 -->
    <div class="chat-main">
      <!-- 头部 -->
      <header class="chat-header">
        <div class="header-left">
          <el-popover placement="bottom" :width="280" trigger="click">
            <template #reference>
              <div class="ai-avatar cursor-pointer" :style="aiAvatarStyle">
                <div ref="lottieContainer" class="lottie-avatar"></div>
              </div>
            </template>
            <div class="ai-avatar-settings">
              <div class="ai-avatar-preview" :style="aiAvatarStyle">{{ aiAvatarPreviewLetter }}</div>
              <div class="ai-avatar-presets">
                <div
                  v-for="(preset, index) in aiPresets"
                  :key="index"
                  class="ai-preset-item cursor-pointer"
                  :class="{ active: aiAvatarPreset === preset.bg }"
                  :style="{ background: preset.bg }"
                  @click="selectAiPreset(preset)"
                >
                  <span class="ai-preset-letter">{{ preset.letter }}</span>
                </div>
              </div>
            </div>
          </el-popover>
          <div class="header-info">
            <h2>LLM.V1 智能问数</h2>
            <div class="status-indicator">
              <span class="status-dot"></span>
              在线
            </div>
          </div>
        </div>
        <div class="header-actions">
          <button v-if="sidebarCollapsed" class="action-btn cursor-pointer" @click="sidebarCollapsed = false" title="显示会话历史">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <rect x="2" y="3" width="14" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/>
              <path d="M6 7H12M6 10H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <button class="action-btn cursor-pointer" @click="showPreferencesPanel = true" title="偏好设置">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <circle cx="9" cy="9" r="2" stroke="currentColor" stroke-width="1.5"/>
              <path d="M9 1V3M9 15V17M1 9H3M15 9H17M3.3 3.3L4.7 4.7M13.3 13.3L14.7 14.7M3.3 14.7L4.7 13.3M13.3 4.7L14.7 3.3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <el-dropdown trigger="click" @command="handleCommand">
            <button class="action-btn cursor-pointer">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <circle cx="9" cy="4" r="1.5" fill="currentColor"/>
                <circle cx="9" cy="9" r="1.5" fill="currentColor"/>
                <circle cx="9" cy="14" r="1.5" fill="currentColor"/>
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
      <ChatMessage
        ref="chatMessageRef"
        :messages="messages"
        :loading="loading"
        :ai-avatar-style="aiAvatarStyle"
        :user-avatar-style="userAvatarStyle"
        :has-ai-avatar="hasAiAvatar"
        :has-user-avatar="hasUserAvatar"
        :editing-message-index="editingMessageIndex"
        :editing-content="editingContent"
        :selected-candidate-idx="selectedCandidateIdx"
        :selected-dim-value-idx="selectedDimValueIdx"
        :selected-dims="selectedDims"
        :message-style="preferences.message_style"
        :font-size="preferences.font_size"
        :compact-mode="preferences.compact_mode"
        :show-thinking="preferences.show_thinking"
        @toggle-thinking="toggleThinking"
        @select-metric="selectMetricCandidate"
        @select-dim-value="selectDimensionValueCandidate"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @drill-down="handleDrillDown"
        @breadcrumb-click="handleBreadcrumbClick"
        @back="handleBack"
        @feedback="handleFeedback"
        @start-edit="startEdit"
        @resend="resendMessage"
        @cancel-edit="cancelEdit"
        @toggle-dim="toggleDimSelection"
        @clear-dims="clearDimSelection"
        @select-suggestion="handleSelectSuggestion"
      />

      <!-- 操作栏 -->
      <QuickActions
        :recommend-questions="recommendQuestions"
        :recent-questions="recentQuestions"
        @my-favorites="handleMyFavorites"
        @select-recommend="handleSelectRecommend"
        @select-recent="handleSelectRecent"
        @clear-context="handleClearContext"
        @open-recommend="loadRecommendQuestions"
        @open-recent="refreshRecentQuestions"
      />

      <!-- 输入区域 -->
      <ChatInput
        v-model="question"
        :disabled="loading"
        :suggestions="suggestions"
        :show-suggestions="showSuggestions"
        :selected-index="selectedIndex"
        :single-match="singleMatchSuggestion"
        placeholder="输入您的问题，如：本月销售额是多少？"
        @send="handleSend"
        @input="onInput"
        @navigate-up="navigateUp"
        @navigate-down="navigateDown"
        @select-current="selectCurrent"
        @close-suggestions="closeSuggestions"
        @select-suggestion="selectSuggestion"
      />
    </div>

    <!-- 偏好设置面板 -->
    <AskPreferencesPanel v-model="showPreferencesPanel" @preferences-changed="onPreferencesChanged" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, inject, watch, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { llmAskApi } from '@/api/llmAsk'
import AskPreferencesPanel from './components/AskPreferencesPanel.vue'
import ChatSession from '@/components/ask/ChatSession.vue'
import ChatMessage from '@/components/ask/ChatMessage.vue'
import QuickActions from '@/components/ask/QuickActions.vue'
import ChatInput from '@/components/ask/ChatInput.vue'
import lottie from 'lottie-web'

// 核心状态
const question = ref('')
const messages = ref<any[]>([])
const loading = ref(false)
const sessionId = ref(localStorage.getItem('llm_v1_session_id') || '')
const sessionHistory = ref<any[]>([])
const sidebarCollapsed = ref(false)
const chatMessageRef = ref<InstanceType<typeof ChatMessage> | null>(null)
const lottieContainer = ref<HTMLElement | null>(null)
let lottieAnim: any = null

// 消息编辑状态
const editingMessageIndex = ref(-1)
const editingContent = ref('')

// 指标候选选择
const selectedCandidateIdx = ref(-1)
const selectedDimValueIdx = ref(-1)
const selectedDims = ref<string[]>([])

// 建议
const suggestions = ref<any[]>([])
const showSuggestions = ref(false)
const selectedIndex = ref(-1)
const singleMatchSuggestion = ref(false)

// 偏好设置
const showPreferencesPanel = ref(false)
const preferences = ref({
  message_style: 'card',
  font_size: 14,
  compact_mode: false,
  show_thinking: true,
  show_sql: true,
  animation_enabled: true
})

// AI 头像
const aiAvatarStyle = ref({ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' })
const hasAiAvatar = ref(true)
const hasUserAvatar = ref(true)
const aiAvatarPreset = ref('')
const aiAvatarPreviewLetter = computed(() => 'V1')
const aiPresets = [
  { letter: 'V1', bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' },
  { letter: 'V2', bg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
  { letter: 'V3', bg: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' },
  { letter: 'V4', bg: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' },
  { letter: 'V5', bg: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' },
  { letter: 'V6', bg: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)' },
  { letter: 'V7', bg: 'linear-gradient(135deg, #d299c2 0%, #fef9d7 100%)' },
  { letter: 'V8', bg: 'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)' },
]

const userAvatarStyle = computed(() => {
  return { background: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)' }
})

// 推荐问题
const recommendQuestions = ref<string[]>([])
const recentQuestions = ref<string[]>([])

// 生命周期
onMounted(async () => {
  loadSessionHistory()
  loadPreferences()
  loadRecommendQuestions()

  const savedSessionId = localStorage.getItem('llm_v1_session_id')
  if (savedSessionId) {
    sessionId.value = savedSessionId
    await loadSession(savedSessionId)
  }

  // 初始化 Lottie 动画
  nextTick(() => {
    if (lottieContainer.value) {
      lottieAnim = lottie.loadAnimation({
        container: lottieContainer.value,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        path: '/lottie/Assistant-Bot.json'
      })
    }
  })
})

onUnmounted(() => {
  if (lottieAnim) {
    lottieAnim.destroy()
    lottieAnim = null
  }
})

// 会话管理
async function loadSessionHistory() {
  try {
    const saved = localStorage.getItem('llm_v1_sessions')
    if (saved) {
      sessionHistory.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('加载会话历史失败:', e)
  }
}

async function loadSession(id: string) {
  if (!id) return
  sessionId.value = id
  localStorage.setItem('llm_v1_session_id', id)

  try {
    const res = await llmAskApi.getHistory(id)
    if (res.data?.messages && res.data.messages.length > 0) {
      messages.value = res.data.messages.map((m: any) => ({
        role: m.role || 'assistant',
        content: m.content || m.answer || '',
        sql: m.sql || '',
        created_at: m.created_at || new Date().toISOString(),
        result_data: m.chart_config?.data || m.result_data || null,
        thinking_expanded: false,
        thinking_steps: m.thinking_steps || [],
        chart_config: m.chart_config || {},
        suggest: m.suggestions || []
      }))
    } else {
      messages.value = []
    }
  } catch (e) {
    console.error('加载会话历史失败:', e)
    try {
      const savedMessages = localStorage.getItem(`llm_v1_messages_${id}`)
      if (savedMessages) {
        messages.value = JSON.parse(savedMessages)
      } else {
        messages.value = []
      }
    } catch (e2) {
      console.error('加载本地会话消息失败:', e2)
      messages.value = []
    }
  }
}

function createNewSession() {
  sessionId.value = 'llm_' + Date.now()
  localStorage.setItem('llm_v1_session_id', sessionId.value)
  messages.value = []
  saveSessions()
}

async function deleteSession(id: string) {
  try {
    await llmAskApi.clearSession(id)
    sessionHistory.value = sessionHistory.value.filter(s => s.id !== id)
    localStorage.removeItem(`llm_v1_messages_${id}`)
    if (sessionId.value === id) {
      createNewSession()
    }
    ElMessage.success('会话已删除')
  } catch (e) {
    console.error('删除会话失败:', e)
  }
}

function toggleStarSession(sessionId: string) {
  const session = sessionHistory.value.find(s => s.id === sessionId)
  if (session) {
    session.starred = !session.starred
    saveSessions()
  }
}

function saveSessions() {
  const now = new Date().toISOString()
  const currentSession = {
    id: sessionId.value,
    title: messages.value.length > 0
      ? (messages.value[0]?.content?.substring(0, 30) || '新对话')
      : '新对话',
    created_at: now,
    updated_at: now,
    starred: false
  }

  const existingIds = sessionHistory.value.map(s => s.id)
  if (existingIds.includes(sessionId.value)) {
    sessionHistory.value = sessionHistory.value.map(s =>
      s.id === sessionId.value ? { ...s, updated_at: now } : s
    )
  } else {
    sessionHistory.value = [currentSession, ...sessionHistory.value].slice(0, 20)
  }
  localStorage.setItem('llm_v1_sessions', JSON.stringify(sessionHistory.value))
}

function saveMessages() {
  if (sessionId.value) {
    localStorage.setItem(`llm_v1_messages_${sessionId.value}`, JSON.stringify(messages.value))
  }
}

// 消息发送
async function handleSend() {
  if (!question.value.trim() || loading.value) return

  const questionText = question.value.trim()
  question.value = ''

  messages.value.push({
    role: 'user',
    content: questionText,
    created_at: new Date().toISOString(),
    thinking_expanded: true,
    thinking_steps: []
  })

  await scrollToBottom()
  loading.value = true

  try {
    if (!sessionId.value) {
      sessionId.value = 'llm_' + Date.now()
      localStorage.setItem('llm_v1_session_id', sessionId.value)
    }

    const res = await llmAskApi.ask({
      question: questionText,
      session_id: sessionId.value
    })

    messages.value.push({
      role: 'assistant',
      content: res.answer || '',
      sql: res.sql || '',
      result_data: res.result_data || [],
      chart_config: res.chart_config || {},
      suggest: res.suggestions || [],
      anomaly_warnings: res.anomaly_warnings || [],
      needs_clarification: res.needs_clarification || false,
      clarification_type: res.clarification_type,
      clarification_message: res.clarification_message,
      clarification_options: res.clarification_options || [],
      thinking_steps: res.thinking_steps || [],
      thinking_expanded: false,
      created_at: new Date().toISOString()
    })

    saveSessions()
    saveMessages()

    await scrollToBottom()
  } catch (e: any) {
    console.error('LLM.V1 请求失败:', e)
    messages.value.push({
      role: 'assistant',
      content: `抱歉，处理您的问题时出现错误：${e.message || '未知错误'}`,
      sql: '',
      chart_config: {},
      suggest: [],
      anomaly_warnings: [],
      thinking_steps: [],
      created_at: new Date().toISOString()
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

async function handleStop() {
  loading.value = false
}

async function resendMessage() {
  const lastUserIdx = messages.value.findLastIndex(m => m.role === 'user')
  if (lastUserIdx === -1) return

  const lastUserMsg = messages.value[lastUserIdx]
  messages.value = messages.value.slice(0, lastUserIdx)

  question.value = lastUserMsg.content
  await handleSend()
}

async function handleSelectSuggestion(suggestion: string) {
  question.value = suggestion.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}]/gu, '').trim()
  await handleSend()
}

function onQuickAction(questionText: string) {
  question.value = questionText
  handleSend()
}

async function scrollToBottom() {
  await nextTick()
  chatMessageRef.value?.scrollToBottom()
}

// 输入建议
function onInput() {
  showSuggestions.value = false
  selectedIndex.value = -1
}

function navigateUp() {
  if (!showSuggestions.value || suggestions.value.length === 0) return
  if (selectedIndex.value > 0) {
    selectedIndex.value--
  }
}

function navigateDown() {
  if (!showSuggestions.value || suggestions.value.length === 0) return
  if (selectedIndex.value < suggestions.value.length - 1) {
    selectedIndex.value++
  }
}

function selectCurrent() {
  if (selectedIndex.value >= 0 && suggestions.value[selectedIndex.value]) {
    selectSuggestion(suggestions.value[selectedIndex.value])
  }
}

function closeSuggestions() {
  showSuggestions.value = false
  selectedIndex.value = -1
}

function selectSuggestion(suggestion: any) {
  if (typeof suggestion === 'string') {
    question.value = suggestion
  } else {
    question.value = suggestion.text || suggestion
  }
  closeSuggestions()
  handleSend()
}

// 反馈
function handleFeedback(index: number, value: number) {
  messages.value[index].feedback = value
  ElMessage.success(value === 1 ? '感谢反馈' : '已记录您的反馈')
}

// 命令处理
function handleCommand(command: string) {
  if (command === 'clear') {
    ElMessageBox.confirm('确定要清空当前对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      messages.value = []
      saveMessages()
    }).catch(() => {})
  } else if (command === 'export') {
    exportConversation()
  }
}

// 导出对话
function exportConversation() {
  const data = JSON.stringify(messages.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `llm-v1-conversation-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// 偏好设置
function loadPreferences() {
  try {
    const saved = localStorage.getItem('llm_v1_preferences')
    if (saved) {
      preferences.value = { ...preferences.value, ...JSON.parse(saved) }
    }
  } catch (e) {
    console.error('加载偏好设置失败:', e)
  }
}

function onPreferencesChanged(newPrefs: any) {
  preferences.value = { ...preferences.value, ...newPrefs }
  localStorage.setItem('llm_v1_preferences', JSON.stringify(preferences.value))
}

// 推荐问题
function loadRecommendQuestions() {
  recommendQuestions.value = [
    '本月销售额是多少？',
    '分平台看订单量',
    '近7天各店铺销售额趋势',
    '本月销售额前10的店铺'
  ]
}

function refreshRecentQuestions() {
  // 从本地存储加载最近问题
  try {
    const saved = localStorage.getItem('llm_v1_recent_questions')
    if (saved) {
      recentQuestions.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('加载最近问题失败:', e)
  }
}

function handleSelectRecommend(text: string) {
  question.value = text
  handleSend()
}

function handleSelectRecent(text: string) {
  question.value = text
  handleSend()
}

function handleClearContext() {
  createNewSession()
  ElMessage.success('上下文已清除')
}

function handleMyFavorites() {
  ElMessage.info('我的收藏功能开发中')
}

// 编辑消息
function startEdit(index: number) {
  editingMessageIndex.value = index
  editingContent.value = messages.value[index].content
}

function cancelEdit() {
  editingMessageIndex.value = -1
  editingContent.value = ''
}

function toggleThinking(msg: any) {
  const index = messages.value.indexOf(msg)
  if (index >= 0) {
    messages.value[index].thinking_expanded = !messages.value[index].thinking_expanded
  }
}

// 指标候选选择
function selectMetricCandidate(index: number) {
  selectedCandidateIdx.value = index
}

function selectDimensionValueCandidate(index: number) {
  selectedDimValueIdx.value = index
}

function handlePageChange(page: number) {
  console.log('page change:', page)
}

function handlePageSizeChange(size: number) {
  console.log('page size change:', size)
}

function handleDrillDown(params: any) {
  console.log('drill down:', params)
}

function handleBreadcrumbClick(index: number) {
  console.log('breadcrumb click:', index)
}

function handleBack() {
  console.log('back')
}

function toggleDimSelection(dim: string) {
  const idx = selectedDims.value.indexOf(dim)
  if (idx >= 0) {
    selectedDims.value.splice(idx, 1)
  } else {
    selectedDims.value.push(dim)
  }
}

function clearDimSelection() {
  selectedDims.value = []
}

// AI 头像选择
function selectAiPreset(preset: any) {
  aiAvatarPreset.value = preset.bg
  aiAvatarStyle.value = { background: preset.bg }
  localStorage.setItem('llm_v1_ai_avatar', preset.bg)
}

// 监听器
watch(() => question.value, (val) => {
  if (val.trim()) {
    showSuggestions.value = true
  }
})
</script>

<style scoped>
.ask-page {
  height: 100vh;
  display: flex;
  position: relative;
  overflow: hidden;
  background: var(--bg-primary);
}

.bg-gradient {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-primary);
  pointer-events: none;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 5;
}

.chat-header {
  padding: 16px 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ai-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  overflow: hidden;
}

.lottie-avatar {
  width: 36px;
  height: 36px;
}

.header-info h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #16a34a;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #16a34a;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.action-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

/* AI Avatar Settings */
.ai-avatar-settings {
  padding: 8px 0;
}

.ai-avatar-preview {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
  margin: 0 auto 16px;
  box-shadow: 0 4px 12px rgba(22, 119, 255, 0.35);
}

.ai-avatar-presets {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 0 4px;
  margin-bottom: 14px;
}

.ai-preset-item {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.ai-preset-item:hover {
  transform: scale(1.08);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.ai-preset-item.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-glow);
}

.ai-preset-letter {
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
}

.ai-avatar-uploader {
  display: flex;
  justify-content: center;
}

.ai-upload-btn {
  width: 100%;
  border: 1px dashed var(--border);
  color: var(--text-secondary);
  font-size: 12px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.ai-upload-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-glow);
}
</style>
