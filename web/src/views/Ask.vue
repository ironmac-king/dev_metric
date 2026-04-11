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
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/>
                  <circle cx="12" cy="9" r="2.5" fill="currentColor"/>
                  <circle cx="12" cy="15" r="1.5" fill="currentColor" opacity="0.5"/>
                  <path d="M9 15C9 15 10.2 18 12 18C13.8 18 15 15 15 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
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
              <el-upload
                class="ai-avatar-uploader"
                :show-file-list="false"
                :before-upload="handleAiUpload"
                accept="image/*"
              >
                <el-button size="small" class="ai-upload-btn">上传自定义头像</el-button>
              </el-upload>
            </div>
          </el-popover>
          <div class="header-info">
            <h2>智能问数助手</h2>
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
        placeholder="输入您的问题..."
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
import { ref, computed, onMounted, nextTick, inject } from 'vue'
import { useRoute } from 'vue-router'
import { askAPI } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import AskPreferencesPanel from './components/AskPreferencesPanel.vue'
import ChatSession from '@/components/ask/ChatSession.vue'
import ChatMessage from '@/components/ask/ChatMessage.vue'
import QuickActions from '@/components/ask/QuickActions.vue'
import ChatInput from '@/components/ask/ChatInput.vue'

const route = useRoute()

// 从 Layout 注入侧边栏控制
const layoutSidebar = inject('layoutSidebar', null)
const { hideSidebar, showSidebar } = layoutSidebar || {}

// 核心状态
const question = ref('')
const messages = ref([])
const loading = ref(false)
const sessionId = ref(localStorage.getItem('ask_session_id') || '')
const sessionHistory = ref([])
const sidebarCollapsed = ref(false)
const chatMessageRef = ref<InstanceType<typeof ChatMessage> | null>(null)
const showPreferencesPanel = ref(false)
const selectedCandidateIdx = ref(null)
const selectedDimValueIdx = ref(null)

// 偏好设置状态
const preferences = ref({
  theme: 'light',
  message_style: 'bubbles',
  font_size: 'medium',
  show_thinking: true,
  compact_mode: false
})

// 编辑消息
const editingMessageIndex = ref(-1)
const editingContent = ref('')

// 下钻相关
const selectedDims = ref({})

// Type-ahead
const suggestions = ref<Array<{dimension_field: string, dimension_value: string}>>([])
const selectedIndex = ref(-1)
const showSuggestions = ref(false)
const singleMatchSuggestion = ref<{dimension_field: string, dimension_value: string} | null>(null)
let debounceTimer
const currentMetricCode = ref('')
const currentSQL = ref('')
const currentGroupBy = ref('')
const engineType = ref(localStorage.getItem('engine_type') || 'langgraph')
const drillHistory = ref([])

// 推荐问题和最近提问
const recommendQuestions = ref<string[]>([])
const recentQuestions = ref<string[]>([])

// Avatar 配置
const aiPresets = [
  { bg: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #722ED1 0%, #4A1080 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #00A870 0%, #007B50 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #F5222D 0%, #C41230 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #FA8C16 0%, #D46B08 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #13C2C2 0%, #08979C 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #EC4899 0%, #BE185D 100%)', letter: 'AI' },
]

const aiAvatarPreset = ref('')
const aiAvatarCustom = ref('')

const userAvatarStyle = computed(() => {
  const custom = localStorage.getItem('user_avatar_custom')
  const preset = localStorage.getItem('user_avatar_preset')
  if (custom) return { background: `url(${custom}) center/cover` }
  if (preset) return { background: preset }
  return { background: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)' }
})

const hasUserAvatar = computed(() => {
  return !!(localStorage.getItem('user_avatar_custom') || localStorage.getItem('user_avatar_preset'))
})

const hasAiAvatar = computed(() => {
  return !!(localStorage.getItem('ai_avatar_custom') || localStorage.getItem('ai_avatar_preset'))
})

const aiAvatarStyle = computed(() => {
  if (aiAvatarCustom.value) return { background: `url(${aiAvatarCustom.value}) center/cover`, color: 'transparent' }
  if (aiAvatarPreset.value) return { background: aiAvatarPreset.value }
  return { background: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)' }
})

const aiAvatarPreviewLetter = computed(() => {
  if (aiAvatarCustom.value) return ''
  if (aiAvatarPreset.value) {
    const preset = aiPresets.find(p => p.bg === aiAvatarPreset.value)
    return preset ? preset.letter : 'AI'
  }
  return 'AI'
})

// 头像选择
function selectAiPreset(preset) {
  aiAvatarPreset.value = preset.bg
  aiAvatarCustom.value = ''
  localStorage.setItem('ai_avatar_preset', preset.bg)
  localStorage.setItem('ai_avatar_custom', '')
}

function handleAiUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    aiAvatarCustom.value = e.target.result
    aiAvatarPreset.value = ''
    localStorage.setItem('ai_avatar_custom', e.target.result)
    localStorage.setItem('ai_avatar_preset', '')
  }
  reader.readAsDataURL(file)
  return false
}

function loadAiAvatarConfig() {
  aiAvatarPreset.value = localStorage.getItem('ai_avatar_preset') || ''
  aiAvatarCustom.value = localStorage.getItem('ai_avatar_custom') || ''
}

// 生命周期
onMounted(async () => {
  loadAiAvatarConfig()
  loadSessionHistory()
  loadRecommendQuestions()

  // 加载偏好设置
  try {
    const res = await askAPI.getPreferences()
    if (res.data) {
      preferences.value = { ...preferences.value, ...res.data }
    }
  } catch (e) {
    console.error('加载偏好设置失败:', e)
  }

  // 等待 DOM 渲染完成后再应用样式
  await nextTick()
  applyAllPreferences()

  const questionParam = route.query.q
  const sessionParam = route.query.session_id

  if (questionParam && typeof questionParam === 'string') {
    question.value = questionParam
    setTimeout(() => handleSend(), 100)
  } else if (sessionParam && typeof sessionParam === 'string') {
    loadSession(sessionParam)
  } else if (sessionId.value) {
    loadSession(sessionId.value)
  }
})

// 应用所有偏好设置
function applyAllPreferences() {
  // 应用主题
  document.documentElement.setAttribute('data-theme', preferences.value.theme)
  localStorage.setItem('ask_theme', preferences.value.theme)
  // 消息样式通过 Vue props 传递给 ChatMessage 组件，自动响应式更新
}

// 处理偏好设置变更事件
function onPreferencesChanged({ key, value }) {
  // 更新本地状态 - Vue 会自动把新的 preferences 传递给 ChatMessage
  preferences.value[key] = value

  // 如果是主题，需要额外处理
  if (key === 'theme') {
    document.documentElement.setAttribute('data-theme', value)
    localStorage.setItem('ask_theme', value)
  }
  // 其他样式通过 Vue props 传递，ChatMessage 会自动响应更新
}

// 会话管理
async function loadSessionHistory() {
  try {
    const res = await askAPI.getSessions()
    if (res.data) sessionHistory.value = [...res.data]
  } catch (e) {
    console.error('加载会话历史失败:', e)
  }
}

async function toggleStarSession(session) {
  try {
    const sessionIdToUse = session.id || session.session_id
    await askAPI.starSession(sessionIdToUse)
    session.starred = !session.starred
  } catch (e) {
    ElMessage.error('星标失败')
  }
}

async function loadSession(id) {
  try {
    const res = await askAPI.getMessages(id)
    if (res.data?.messages && res.data.messages.length > 0) {
      sessionId.value = id
      localStorage.setItem('ask_session_id', id)
      messages.value = res.data.messages.map(m => ({
        role: m.role,
        content: m.content,
        sql: m.sql,
        created_at: m.created_at,
        result_data: m.result_data || null,
        comparison_results: m.comparison_result || m.comparison_results || null,
        comparison_result: m.comparison_result || m.comparison_results || null,
        drill_down_dims: m.drill_down_dims || null,
        breadcrumbs: m.breadcrumbs || null,
        metric_code: m.metric_code || null,
        thinking_expanded: true,
        thinking_steps: []
      }))
      await scrollToBottom()
    } else {
      sessionId.value = id
      localStorage.setItem('ask_session_id', id)
      messages.value = []
    }
  } catch (e) {
    ElMessage.error('加载会话失败')
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
    const idx = sessionHistory.value.findIndex(s => (s.session_id || s.id) === id)
    if (idx !== -1) sessionHistory.value.splice(idx, 1)
    if ((sessionId.value || '').toString() === id.toString()) {
      await createNewSession()
    }
    ElMessage.success('删除成功')
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除会话失败:', e)
      ElMessage.error('删除失败，请重试')
    }
  }
}

// 消息发送
async function handleSend() {
  if (!question.value.trim() || loading.value) return

  drillHistory.value = []
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
    const res = await askAPI.ask({
      question: questionText,
      session_id: sessionId.value || undefined,
      engine_type: engineType.value
    })

    if (res) {
      if (!sessionId.value && res.session_id) {
        sessionId.value = res.session_id
        localStorage.setItem('ask_session_id', sessionId.value)
        await loadSessionHistory()
      }

      const metricCode = extractMetricCode(res)
      const sql = res.sql || ''
      if (metricCode) currentMetricCode.value = metricCode
      if (sql) currentSQL.value = sql

      let resultData = res.result_data
      if (typeof resultData === 'string') {
        try { resultData = JSON.parse(resultData) } catch { resultData = null }
      }

      messages.value.push({
        role: 'assistant',
        content: res.answer,
        sql: res.sql,
        result_data: resultData || null,
        comparison_result: res.comparison_result || res.comparison_results?.[0] || null,
        comparison_results: res.comparison_results || null,
        drill_down_dims: res.drill_down_dims || [],
        breadcrumbs: res.breadcrumbs || [],
        created_at: new Date().toISOString(),
        thinking_expanded: false,
        thinking_steps: res.thinking_steps || [],
        needs_clarification: res.needs_clarification || false,
        clarification_message: res.clarification_message || null,
        clarification_type: res.clarification_type || null,
        matched_metrics: res.matched_metrics || [],
        dimension_value_candidates: res.dimension_value_candidates || [],
        dimension_value_matched_text: res.dimension_value_matched_text || ''
      })
    }
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，服务暂时不可用，请稍后再试。',
      created_at: new Date().toISOString(),
      thinking_expanded: false,
      thinking_steps: []
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  chatMessageRef.value?.scrollToBottom()
}

// 编辑消息
function startEdit(index) {
  editingMessageIndex.value = index
  editingContent.value = messages.value[index].content
}

function cancelEdit() {
  editingMessageIndex.value = -1
  editingContent.value = ''
}

async function resendMessage() {
  const index = editingMessageIndex.value
  if (index === -1) return
  const newContent = editingContent.value.trim()
  if (!newContent) return

  messages.value[index].content = newContent
  editingMessageIndex.value = -1
  editingContent.value = ''
  messages.value = messages.value.slice(0, index + 1)

  await scrollToBottom()
  loading.value = true

  try {
    const res = await askAPI.ask({
      question: newContent,
      session_id: sessionId.value || undefined,
      engine_type: engineType.value
    })

    if (res) {
      if (!sessionId.value && res.session_id) {
        sessionId.value = res.session_id
        localStorage.setItem('ask_session_id', sessionId.value)
        await loadSessionHistory()
      }

      const metricCode = extractMetricCode(res)
      const sql = res.sql || ''
      if (metricCode) currentMetricCode.value = metricCode
      if (sql) currentSQL.value = sql

      let resultData = res.result_data
      if (typeof resultData === 'string') {
        try { resultData = JSON.parse(resultData) } catch { resultData = null }
      }

      messages.value.push({
        role: 'assistant',
        content: res.answer,
        sql: res.sql,
        result_data: resultData || null,
        comparison_result: res.comparison_result || res.comparison_results?.[0] || null,
        comparison_results: res.comparison_results || null,
        drill_down_dims: res.drill_down_dims || [],
        breadcrumbs: res.breadcrumbs || [],
        created_at: new Date().toISOString(),
        thinking_expanded: false,
        thinking_steps: res.thinking_steps || [],
        needs_clarification: res.needs_clarification || false,
        clarification_message: res.clarification_message || null,
        clarification_type: res.clarification_type || null,
        matched_metrics: res.matched_metrics || [],
        dimension_value_candidates: res.dimension_value_candidates || [],
        dimension_value_matched_text: res.dimension_value_matched_text || ''
      })
    }
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，服务暂时不可用，请稍后再试。',
      created_at: new Date().toISOString(),
      thinking_expanded: false,
      thinking_steps: []
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

// 指标/维度选择
function selectMetricCandidate(idx, metric) {
  selectedCandidateIdx.value = idx
  const metricQuestion = `${metric.name || metric.metric_name}（${metric.metric_code}）`
  question.value = metricQuestion
  handleSend()
}

function selectDimensionValueCandidate(idx, dimValue) {
  selectedDimValueIdx.value = idx

  let lastAiMsgWithCandidates = null
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role === 'assistant' && msg.dimension_value_candidates && msg.dimension_value_candidates.length > 0) {
      lastAiMsgWithCandidates = msg
      break
    }
  }

  let newQuestion = ''
  if (lastAiMsgWithCandidates) {
    const aiIndex = messages.value.indexOf(lastAiMsgWithCandidates)
    const userMsgIndex = aiIndex - 1

    if (userMsgIndex >= 0 && messages.value[userMsgIndex].role === 'user') {
      const userMsg = messages.value[userMsgIndex]
      const matchedText = lastAiMsgWithCandidates.dimension_value_matched_text || ''

      const isStandaloneNumber = /^\d+$/.test(matchedText)
      let canReplace = matchedText && userMsg.content.includes(matchedText)

      if (canReplace && isStandaloneNumber) {
        const pattern = new RegExp(`(?<![0-9])${matchedText}(?![0-9])`)
        canReplace = pattern.test(userMsg.content)
      }

      if (canReplace) {
        newQuestion = userMsg.content.replace(matchedText, dimValue.dimension_value)
      } else {
        newQuestion = dimValue.dimension_value
      }

      lastAiMsgWithCandidates.dimension_value_candidates = null
    }
  }

  if (!newQuestion) newQuestion = dimValue.dimension_value
  question.value = newQuestion
  handleSend()
}

// 引擎切换
function setEngineType(type) {
  engineType.value = type
  localStorage.setItem('engine_type', type)
  ElMessage.success(`已切换到 ${type === 'langgraph' ? 'LangGraph' : 'LLM'} 引擎`)
}

// 下拉菜单
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

// 思考过程
function toggleThinking(msg) {
  msg.thinking_expanded = !msg.thinking_expanded
}

// 提取 metric_code
function extractMetricCode(data) {
  if (data.metric_code) return data.metric_code
  if (data.thinking_steps) {
    for (const step of data.thinking_steps) {
      if (step.content && step.content.includes('指标：')) {
        const match = step.content.match(/指标[：:]\s*([^\s|]+)/)
        if (match) return match[1]
      }
    }
  }
  return ''
}

// 反馈
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

// 下钻
function isDimSelected(dimName, msg) {
  const index = messages.value.indexOf(msg)
  return selectedDims.value[index]?.includes(dimName) || false
}

function hasSelectedDims(msg) {
  const index = messages.value.indexOf(msg)
  return selectedDims.value[index]?.length > 0
}

function toggleDimSelection(dimName, msg) {
  const index = messages.value.indexOf(msg)
  if (!selectedDims.value[index]) selectedDims.value[index] = []
  const idx = selectedDims.value[index].indexOf(dimName)
  if (idx >= 0) {
    selectedDims.value[index].splice(idx, 1)
  } else {
    selectedDims.value[index].push(dimName)
  }
}

function clearDimSelection(msg) {
  const index = messages.value.indexOf(msg)
  selectedDims.value[index] = []
}

async function handleDrillDown(msg, comparisonTypes = null) {
  const index = messages.value.indexOf(msg)
  const selected = selectedDims.value[index] || []
  if (selected.length === 0) {
    ElMessage.warning('请选择至少一个维度')
    return
  }

  if (!comparisonTypes) {
    const msgContent = msg.content || ''
    const hasYoy = msgContent.includes('同比') || msgContent.includes('去年同期')
    const hasMom = msgContent.includes('环比') || msgContent.includes('上月')

    if (hasYoy && hasMom) {
      comparisonTypes = ['同比', '环比']
    } else if (hasYoy) {
      comparisonTypes = ['同比']
    } else if (hasMom) {
      comparisonTypes = ['环比']
    } else if (msg.comparison_results && msg.comparison_results.length > 0) {
      comparisonTypes = msg.comparison_results.map(c => c.comparison_type)
    } else {
      comparisonTypes = []
    }
  }

  drillHistory.value.push({
    sql: currentSQL.value || msg.sql,
    groupBy: currentGroupBy.value,
    breadcrumbs: JSON.parse(JSON.stringify(msg.breadcrumbs || [])),
    result_data: msg.result_data,
    drill_down_dims: msg.drill_down_dims,
    content: msg.content,
    comparison_results: msg.comparison_results
  })

  loading.value = true
  try {
    const res = await askAPI.drillDown({
      session_id: sessionId.value,
      dimension_names: selected,
      metric_code: msg.metric_code || currentMetricCode.value || '',
      current_sql: msg.sql || currentSQL.value || '',
      current_group_by: currentGroupBy.value,
      comparison_types: comparisonTypes
    })

    if (res) {
      currentSQL.value = res.sql
      currentGroupBy.value = res.breadcrumbs?.map(b => b.value).join(',') || ''

      msg.content = res.answer
      msg.sql = res.sql
      msg.result_data = res.result_data || null
      msg.drill_down_dims = res.drill_down_dims || []
      msg.breadcrumbs = res.breadcrumbs || []
      msg.comparison_results = res.comparison_results || null
      msg.thinking_expanded = false
      await scrollToBottom()
    }
  } catch (e) {
    ElMessage.error('下钻失败，请重试')
  } finally {
    loading.value = false
    clearDimSelection(msg)
    await scrollToBottom()
  }
}

async function handlePageChange(page, msg) {
  const index = messages.value.indexOf(msg)
  loading.value = true
  try {
    const res = await askAPI.ask({
      question: msg.content || '当前数据',
      session_id: sessionId.value,
      page: page,
      page_size: msg.page_size || 10,
      engine_type: engineType.value
    })

    if (res) {
      msg.result_data = res.result_data || null
      msg.page = res.page
      msg.page_size = res.page_size
      msg.total = res.total
      msg.sql = res.sql
      await scrollToBottom()
    }
  } catch (e) {
    ElMessage.error('分页查询失败')
  } finally {
    loading.value = false
  }
}

async function handlePageSizeChange(size, msg) {
  // 改变每页条数时重置到第一页
  msg.page = 1
  msg.page_size = size
  await handlePageChange(1, msg)
}

async function handleBreadcrumbClick(crumb, cIdx, msg) {
  if (drillHistory.value.length === 0) {
    ElMessage.warning('没有可返回的历史')
    return
  }

  const previousState = drillHistory.value[drillHistory.value.length - 1]
  drillHistory.value.pop()

  currentSQL.value = previousState.sql
  currentGroupBy.value = previousState.groupBy
  msg.content = previousState.content
  msg.sql = previousState.sql
  msg.result_data = previousState.result_data
  msg.drill_down_dims = previousState.drill_down_dims
  msg.breadcrumbs = previousState.breadcrumbs

  ElMessage.success(`已返回到: ${crumb.name}`)
  await scrollToBottom()
}

async function handleBack(msg) {
  if (msg.breadcrumbs && msg.breadcrumbs.length > 1) {
    const parentCrumb = msg.breadcrumbs[msg.breadcrumbs.length - 2]
    await handleBreadcrumbClick(parentCrumb, msg.breadcrumbs.length - 2, msg)
  } else if (drillHistory.value.length > 0) {
    const previousState = drillHistory.value[drillHistory.value.length - 1]
    drillHistory.value.pop()
    currentSQL.value = previousState.sql
    currentGroupBy.value = previousState.groupBy
    msg.content = previousState.content
    msg.sql = previousState.sql
    msg.result_data = previousState.result_data
    msg.drill_down_dims = previousState.drill_down_dims
    msg.breadcrumbs = previousState.breadcrumbs
    ElMessage.success('已返回上一级')
    await scrollToBottom()
  } else {
    ElMessage.warning('没有可返回的历史')
  }
}

// 操作栏
function handleMyFavorites() {
  ElMessage.info('我的收藏功能开发中')
}

async function handleSelectRecommend(q: string) {
  question.value = q
  await handleSend()
}

async function handleSelectRecent(q: string) {
  question.value = q
  await handleSend()
}

// 每次打开下拉时刷新最近提问
function refreshRecentQuestions() {
  // 使用 Set 去重，保持顺序（最新的在前面）
  const seen = new Set()
  recentQuestions.value = messages.value
    .filter(m => m.role === 'user')
    .map(m => m.content)
    .reverse()
    .filter(q => {
      if (seen.has(q)) return false
      seen.add(q)
      return true
    })
    .slice(0, 10)
}

// 加载推荐问题
async function loadRecommendQuestions() {
  try {
    const res = await askAPI.getSuggest()
    if (res.data) {
      recommendQuestions.value = res.data
    }
  } catch (e) {
    console.error('获取推荐问题失败', e)
  }
}

async function handleClearContext() {
  try {
    await ElMessageBox.confirm('确定要清空当前会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const sid = sessionId.value
    await askAPI.clearSession(sid)
    if (sid) askAPI.deleteMessages(sid)
    messages.value = []
    currentMetricCode.value = ''
    currentSQL.value = ''
    currentGroupBy.value = ''
    selectedDims.value = {}
    sessionHistory.value = sessionHistory.value.filter(s => (s.id || s.session_id) !== sid)
    sessionId.value = ''
    localStorage.removeItem('ask_session_id')
    ElMessage.success('上下文已清空')
  } catch (e) {}
}

// Type-ahead
function onInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fetchSuggestions, 300)
}

async function fetchSuggestions() {
  const text = question.value
  const chineseMatch = text.match(/[\u4e00-\u9fa5]{2,}/g) || []
  const codeMatch = text.match(/[A-Za-z0-9\-_]{3,}/g) || []
  const allMatches = [...chineseMatch, ...codeMatch]

  if (allMatches.length === 0) {
    closeSuggestions()
    return
  }

  const queryText = allMatches[allMatches.length - 1]
  if (queryText.length < 2) {
    closeSuggestions()
    return
  }

  try {
    const res = await fetch(`/api/v1/dimension-values/search?query=${encodeURIComponent(queryText)}&limit=10`)
    const data = await res.json()
    if (data.code === 0 && data.data) {
      suggestions.value = data.data
      showSuggestions.value = suggestions.value.length > 0

      // 检测单一精确匹配
      const exactMatches = suggestions.value.filter(s => s.match_type === 'exact')
      singleMatchSuggestion.value = exactMatches.length === 1 ? exactMatches[0] : null
    }
  } catch (e) {
    console.error('获取维度候选失败', e)
    closeSuggestions()
  }
}

function navigateUp() {
  if (selectedIndex.value > 0) {
    selectedIndex.value--
    scrollToSelected()
  }
}

function navigateDown() {
  if (selectedIndex.value < suggestions.value.length - 1) {
    selectedIndex.value++
    scrollToSelected()
  }
}

function scrollToSelected() {
  nextTick(() => {
    const container = document.querySelector('.dim-suggestions-dropdown')
    const items = container?.querySelectorAll('.dim-suggestion-item')
    const selected = items?.[selectedIndex.value]
    selected?.scrollIntoView({ block: 'nearest' })
  })
}

function selectCurrent() {
  if (selectedIndex.value >= 0 && suggestions.value[selectedIndex.value]) {
    selectSuggestion(suggestions.value[selectedIndex.value])
  }
}

function selectSuggestion(item) {
  const text = question.value
  // 提取最后一个单词（可能部分输入的词）
  const words = text.split(/\s+/)
  const lastWord = words[words.length - 1]

  if (lastWord && item.dimension_value.startsWith(lastWord)) {
    // 替换最后一个词
    words[words.length - 1] = item.dimension_value
    question.value = words.join(' ') + ' '
  } else if (text && !text.endsWith(' ') && !text.endsWith('\n')) {
    // 没有部分匹配的词，追加
    question.value = text + ' ' + item.dimension_value
  } else {
    question.value = text + item.dimension_value
  }
  closeSuggestions()
}

function closeSuggestions() {
  showSuggestions.value = false
  selectedIndex.value = -1
  singleMatchSuggestion.value = null
}
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

/* Tab 切换样式 */
.mode-tabs {
  position: relative;
  z-index: 10;
  padding: 0 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}

.mode-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.mode-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.mode-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 0 20px;
  height: 44px;
  line-height: 44px;
}

.mode-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary);
  font-weight: 600;
}

.mode-tabs :deep(.el-tabs__active-bar) {
  height: 2px;
  background: var(--primary);
}
</style>
