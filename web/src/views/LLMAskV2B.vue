<template>
  <div class="llm-ask-v2b">
    <!-- 手机端侧边栏遮罩层 -->
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false"></div>

    <!-- 左侧边栏 -->
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <!-- 品牌区 -->
      <div class="brand-section">
        <div class="brand-logo">
          <img src="/lvdou-logo.png" alt="绿豆" class="brand-img" />
        </div>
        <span class="brand-name">智能问数</span>
      </div>

      <!-- 新对话按钮 -->
      <button class="new-chat-btn" @click="handleSidebarNewChat">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M2 7H12M7 2V12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span class="new-chat-text">新对话</span>
      </button>

      <!-- 历史对话 -->
      <div class="history-section">
        <div class="history-header">
          <span class="history-label">历史对话</span>
          <span class="history-count">{{ sessions.length }}</span>
        </div>
        <div class="history-list">
          <!-- ===== PC端：三个点菜单 ===== -->
          <template v-if="!isMobile">
            <div
              v-for="session in sessions"
              :key="session.session_id"
              class="history-item"
              :class="{ active: session.session_id === sessionId }"
              @click="handleSidebarSessionClick(session)"
            >
              <span class="history-dot"></span>
              <span class="history-text">{{ session.title || session.first_question || '新会话' }}</span>
              <svg v-if="session.starred" class="pin-icon" width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 1V5.5M3.5 3.5H8.5M4.5 5.5L3.5 11H8.5L7.5 5.5" stroke="#f59e0b" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <button class="action-trigger" @click.stop="toggleActionMenu(session.session_id, $event)">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="3" r="1.2" fill="currentColor"/>
                  <circle cx="7" cy="7" r="1.2" fill="currentColor"/>
                  <circle cx="7" cy="11" r="1.2" fill="currentColor"/>
                </svg>
              </button>
              <div v-if="activeActionMenu === session.session_id" class="action-menu" :style="menuPosition" @click.stop>
                <button class="action-menu-item" @click="handlePinSession(session)">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 1V6M4 4H10M5 6L4 13H10L9 6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <span>{{ session.starred ? '取消置顶' : '置顶' }}</span>
                </button>
                <button class="action-menu-item" @click="handleRenameSession(session)">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M10 2L12 4L5 11H3V9L10 2Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <span>重命名</span>
                </button>
                <button class="action-menu-item danger" @click="handleDeleteSession(session)">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M3 4H11M5 4V3H9V4M6 7V10M8 7V10M4 4L4.5 11H9.5L10 4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <span>删除</span>
                </button>
              </div>
            </div>
          </template>

          <!-- ===== 移动端：左滑删除 ===== -->
          <template v-else>
            <div
              v-for="session in sessions"
              :key="session.session_id"
              class="swipe-wrapper"
            >
              <div
                class="swipe-content"
                :style="swipeStyle(session.session_id)"
                @touchstart="onSwipeStart($event, session.session_id)"
                @touchmove="onSwipeMove($event, session.session_id)"
                @touchend="onSwipeEnd(session.session_id)"
              >
                <div
                  class="history-item"
                  :class="{ active: session.session_id === sessionId }"
                  @click="handleSidebarSessionClick(session)"
                >
                  <span class="history-dot"></span>
                  <span class="history-text">{{ session.title || session.first_question || '新会话' }}</span>
                  <svg v-if="session.starred" class="pin-icon" width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M6 1V5.5M3.5 3.5H8.5M4.5 5.5L3.5 11H8.5L7.5 5.5" stroke="#f59e0b" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
              <button class="swipe-delete" @click.stop="handleDeleteSession(session)">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
              </button>
            </div>
          </template>
        </div>
        <div v-if="sessions.length === 0 && !sessionsLoading" class="history-empty">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect x="4" y="8" width="24" height="18" rx="2" stroke="#c4c7cc" stroke-width="1.5"/>
            <path d="M4 12H28" stroke="#c4c7cc" stroke-width="1.5"/>
            <circle cx="8" cy="10" r="1.5" fill="#c4c7cc"/>
            <circle cx="12" cy="10" r="1.5" fill="#c4c7cc"/>
          </svg>
          <span>暂无历史对话</span>
        </div>
      </div>

      <!-- 用户信息 -->
      <div class="user-section">
        <div class="user-card">
          <div class="user-avatar">{{ userName.charAt(0).toUpperCase() }}</div>
          <div class="user-info">
            <span class="user-name">{{ userName }}</span>
            <span class="user-role">数据分析师</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧主内容区 -->
    <main class="main-content">
      <!-- 手机端顶部工具栏 -->
      <div class="mobile-header">
        <button class="mobile-menu-btn" @click="toggleSidebar">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M3 5H17M3 10H17M3 15H17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
        <span class="mobile-title">智能问数</span>
        <button class="mobile-new-btn" @click="handleSidebarNewChat">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 9H15M9 3V15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>

      <!-- 桌面端 header -->
      <header v-if="messages.length > 0" class="chat-header">
        <div class="header-left">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="1" y="1" width="16" height="16" rx="5" fill="#2468f2"/>
            <path d="M5 12V8M9 13V5M13 11V7" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          <span class="header-title">模型身份介绍</span>
        </div>
        <span class="header-hint">内容由AI生成，请仔细甄别</span>
      </header>

      <!-- 聊天内容区 -->
      <div class="chat-body" ref="messagesContainer">
        <div class="msg-container">
          <!-- 初始化界面 -->
          <div v-if="messages.length === 0" class="init-content">
            <div class="init-greeting">
              <img src="/lvdou-logo.png" alt="绿豆" class="init-logo" />
              <h1 class="init-title">{{ greetingText }}，想看什么数据跟我说。</h1>
            </div>
            <div class="init-suggestions">
              <div class="suggestions-label">你可以这样开场</div>
              <div class="suggestions-grid">
                <div
                  v-for="suggestion in suggestions"
                  :key="suggestion.title"
                  class="suggest-chip"
                  @click="selectSuggestion(suggestion.text)"
                >
                  <div class="chip-icon">
                    <component :is="suggestion.icon" />
                  </div>
                  <div class="chip-body">
                    <div class="chip-title">{{ suggestion.title }}</div>
                    <div class="chip-desc">{{ suggestion.desc }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 聊天消息 -->
          <div v-else class="messages-area">
            <template v-for="(msg, idx) in messages" :key="`msg-${idx}`">
              <LvDouMessage
                :msg="msg"
                :idx="idx"
                :expanded-interpretation="!!expandedInterpretation[idx]"
                @copy="copyMessage"
                @toggle-interpretation="toggleInterpretation"
                @rate="rateMessage"
                @open-process="openThinkingDrawer"
                @select-suggestion="selectSuggestion"
                @clarification-select="handleClarificationSelect"
                @clarification-confirm="handleClarificationConfirm"
                @plan-confirm="handlePlanConfirm"
                @plan-modify="handlePlanModify"
                @legacy-clarification="selectClarification"
                @drilldown="handleDrilldown"
              />
            </template>
          </div>
        </div>
      </div>

      <!-- 底部悬浮输入框 -->
      <div class="input-sticky">
        <div class="input-bar">
          <div class="input-top">
            <textarea
              ref="inputRef"
              v-model="question"
              class="chat-textarea"
              placeholder="发消息..."
              rows="1"
              @keydown.enter.exact.prevent="handleEnterKey"
              @input="autoResize"
            ></textarea>
            <button class="send-btn" :disabled="!question.trim() || loading" @click="handleSend">
              <svg v-if="!loading" width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M16 9L2 2L9 9M16 9L9 16M16 9L2 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <svg v-else width="18" height="18" viewBox="0 0 18 18" fill="none" class="loading-spinner">
                <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="2" stroke-dasharray="40" stroke-dashoffset="10" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <div class="input-tools">
            <span
              v-for="tool in inputTools"
              :key="tool"
              class="input-tool-tag"
            >{{ tool }}</span>
          </div>
        </div>
      </div>
    </main>

    <!-- 保留的业务组件 -->
    <LogicChainDrawer
      v-model="logicDrawerVisible"
      :steps="currentThinkingSteps"
      :sql="currentSql"
      :steps-version="stepsVersion"
    />

    <VolatilityPanel
      ref="volatilityPanelRef"
      v-model="attributionVisible"
      :metric-name="currentMetricName"
      :api-url="volatilityApiUrl"
    />

    <ReportPreview
      v-model="reportVisible"
      :title="reportTitle"
      :summary="reportSummary"
      :core-cards="reportCoreCards"
      :detail-list="reportDetailList"
      :detail-headers="reportDetailHeaders"
      :suggestions="reportSuggestions"
      @export="handleExportPdf"
      @email="handleSendEmail"
    />

    <!-- 删除确认弹窗 -->
    <Teleport to="body">
      <div v-if="deleteConfirm.visible" class="delete-confirm-overlay" @click.self="cancelDelete">
        <div class="delete-confirm-dialog">
          <div class="delete-confirm-title">删除对话</div>
          <div class="delete-confirm-msg">确定删除「{{ deleteConfirm.title }}」？删除后无法恢复。</div>
          <div class="delete-confirm-actions">
            <button class="dc-btn dc-cancel" @click="cancelDelete">取消</button>
            <button class="dc-btn dc-danger" @click="confirmDelete">删除</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, h, nextTick, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { llmAskApi, sessionApi } from '../api/llmAsk'
import { askAPI } from '../api'
import { runLlmAskStream } from '../composables/useLlmAskStream'
import { decodeStoredAskMessage } from '../utils/llmAskMessageCodec'
import { createLlmAskStreamAccumulator } from '../utils/llmAskStreamAccumulator'
import LogicChainDrawer from '../components/ask/LogicChainDrawer.vue'
import ClarificationCard from '../components/ask/ClarificationCard.vue'
import PlanConfirmCard from '../components/ask/PlanConfirmCard.vue'
import ChartCard from '../components/ask/ChartCard.vue'
import VolatilityPanel from '../components/ask/VolatilityPanel.vue'
import ReportPreview from '../components/ask/ReportPreview.vue'
import LvDouMessage from '../components/ask/LvDouMessage.vue'

const router = useRouter()
const $route = useRoute()
const question = ref('')

// 下钻类型 → 中文标签
const DRILLDOWN_LABELS = {
  sales: '销售经营分析',
  ad: '广告投放分析',
  inventory: '库存供应链分析',
  cost: '成本毛利分析',
}

const messages = ref([])
const loading = ref(false)
const sessionId = ref('')

// 侧边栏状态
const sidebarOpen = ref(false)
const sessions = ref([])
const sessionsLoading = ref(false)
const activeActionMenu = ref(null)
const menuPosition = ref({})

// 删除确认弹窗
const deleteConfirm = ref({ visible: false, session: null, title: '' })

// 移动端检测
const isMobile = ref(typeof window !== 'undefined' && window.innerWidth <= 768)
if (typeof window !== 'undefined') {
  window.addEventListener('resize', () => {
    isMobile.value = window.innerWidth <= 768
  })
}

// 左滑删除状态（仅移动端，iOS 风格）
const swipeOffset = ref({})
const swipeStartX = ref(0)
const swipeStartY = ref(0)
const swipeStartTime = ref(0)
const swipeActiveId = ref(null)
const SWIPE_THRESHOLD = 50
const DELETE_BTN_WIDTH = 72
const RUBBER_BAND = 0.35 // 超出边界的阻尼系数

function swipeStyle(sId) {
  const offset = swipeOffset.value[sId] || 0
  if (offset === 0) return {}
  return { transform: `translateX(${offset}px)` }
}

function onSwipeStart(e, sId) {
  swipeStartX.value = e.touches[0].clientX
  swipeStartY.value = e.touches[0].clientY
  swipeStartTime.value = Date.now()
  swipeActiveId.value = sId
  // 关闭其他已打开的项
  for (const key of Object.keys(swipeOffset.value)) {
    if (key !== sId && swipeOffset.value[key] !== 0) {
      swipeOffset.value[key] = 0
    }
  }
}

function onSwipeMove(e, sId) {
  const dx = e.touches[0].clientX - swipeStartX.value
  const dy = e.touches[0].clientY - swipeStartY.value
  // 垂直滑动时不拦截
  if (Math.abs(dy) > Math.abs(dx) && Math.abs(dx) < 10) return
  e.preventDefault()

  let target = dx
  // 超出左边界时加阻尼（iOS rubber-band）
  if (target < -DELETE_BTN_WIDTH) {
    const over = target + DELETE_BTN_WIDTH
    target = -DELETE_BTN_WIDTH + over * RUBBER_BAND
  }
  // 不允许右滑超过原位
  if (target > 0) target = target * RUBBER_BAND
  swipeOffset.value = { ...swipeOffset.value, [sId]: target }
}

function onSwipeEnd(sId) {
  const current = swipeOffset.value[sId] || 0
  const elapsed = Date.now() - swipeStartTime.value
  const velocity = Math.abs(current) / Math.max(elapsed, 1) * 1000
  // 快速滑动（速度 > 300px/s）或超过阈值 → 打开删除
  const shouldOpen = current < -SWIPE_THRESHOLD || velocity > 300
  const finalOffset = shouldOpen ? -DELETE_BTN_WIDTH : 0
  swipeOffset.value = { ...swipeOffset.value, [sId]: finalOffset }
  if (finalOffset === 0) swipeActiveId.value = null
  swipeStartTime.value = 0
}

// 工具按钮数组（可扩展）
const inputTools = ['快速查询']

// Expanded states
const expandedThinking = ref({})
const expandedInterpretation = ref({})

// SSE AbortController
let abortController = null

// 对话状态持久化到 localStorage
const STORAGE_KEY = 'llm_ask_state'

const resetState = () => {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  messages.value = []
  sessionId.value = ''
  expandedThinking.value = {}
  expandedInterpretation.value = {}
}

// 从 localStorage 获取用户名
const userName = computed(() => {
  try {
    const userInfo = localStorage.getItem('user_info')
    if (userInfo) {
      const user = JSON.parse(userInfo)
      return user?.username || user?.name || user?.id?.toString() || 'User'
    }
  } catch (e) {}
  return 'User'
})

// 加载历史会话列表
async function loadSessions() {
  try {
    sessionsLoading.value = true
    const res = await sessionApi.list()
    if (res.code === 0 && res.data) {
      const list = res.data || []
      // 置顶排前面，其余按时间倒序
      list.sort((a, b) => {
        if (a.starred && !b.starred) return -1
        if (!a.starred && b.starred) return 1
        return new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at)
      })
      sessions.value = list
    }
  } catch (e) {
    console.error('加载会话列表失败:', e)
  } finally {
    sessionsLoading.value = false
  }
}

// 侧边栏会话点击
async function handleSidebarSessionClick(session) {
  console.log('[sidebar] clicked session:', session)
  sidebarOpen.value = false
  await handleSelectSession(session)
}

// 侧边栏新对话
function handleSidebarNewChat() {
  sidebarOpen.value = false
  resetState()
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}

function toggleActionMenu(sId, event) {
  event?.stopPropagation()
  if (activeActionMenu.value === sId) {
    activeActionMenu.value = null
    menuPosition.value = {}
  } else {
    activeActionMenu.value = sId
    const btn = event?.currentTarget || event?.target?.closest('.action-trigger')
    if (btn) {
      const rect = btn.getBoundingClientRect()
      menuPosition.value = {
        position: 'fixed',
        top: `${Math.min(rect.bottom + 4, window.innerHeight - 160)}px`,
        left: `${Math.max(0, rect.left - 100)}px`,
      }
    }
  }
}

async function handlePinSession(session) {
  activeActionMenu.value = null
  menuPosition.value = {}
  try {
    await sessionApi.save({
      session_id: session.session_id,
      title: session.title || session.first_question,
      starred: !session.starred,
    })
    await loadSessions()
  } catch (e) {
    console.error('置顶失败:', e)
  }
}

async function handleRenameSession(session) {
  activeActionMenu.value = null
  menuPosition.value = {}
  const newTitle = prompt('重命名对话', session.title || session.first_question || '')
  if (newTitle && newTitle.trim()) {
    try {
      await sessionApi.save({
        session_id: session.session_id,
        title: newTitle.trim(),
      })
      await loadSessions()
    } catch (e) {
      console.error('重命名失败:', e)
    }
  }
}

function handleDeleteSession(session) {
  activeActionMenu.value = null
  menuPosition.value = {}
  deleteConfirm.value = {
    visible: true,
    session,
    title: session.title || session.first_question || '新会话',
  }
}

function cancelDelete() {
  deleteConfirm.value = { visible: false, session: null, title: '' }
}

async function confirmDelete() {
  const session = deleteConfirm.value.session
  deleteConfirm.value = { visible: false, session: null, title: '' }
  if (!session) return
  try {
    await sessionApi.delete(session.session_id)
    if (session.session_id === sessionId.value) {
      resetState()
    }
    await loadSessions()
  } catch (e) {
    console.error('删除失败:', e)
  }
}

// 从会话历史选择会话
async function handleSelectSession(session) {
  try {
    const res = await llmAskApi.getHistory(session.session_id)
    const rawMessages = res.messages || res.data?.messages || []
    if (rawMessages.length > 0) {
      const transformedMessages = rawMessages.map(decodeStoredAskMessage)
      messages.value = transformedMessages
      sessionId.value = session.session_id
      expandedThinking.value = {}
      expandedInterpretation.value = {}
    }
  } catch (e) {
    console.error('加载会话失败:', e)
  }
}

const loadState = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const state = JSON.parse(saved)
      messages.value = state.messages || []
      sessionId.value = state.sessionId || ''
      expandedThinking.value = state.expandedThinking || {}
      expandedInterpretation.value = state.expandedInterpretation || {}
    }
  } catch (e) {
    console.error('Failed to load state:', e)
  }
}

const saveState = () => {
  try {
    const state = {
      messages: messages.value,
      sessionId: sessionId.value,
      expandedThinking: expandedThinking.value,
      expandedInterpretation: expandedInterpretation.value,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (e) {
    console.error('Failed to save state:', e)
  }
}

watch(messages, saveState, { deep: true })
watch(sessionId, saveState)
watch(expandedThinking, saveState, { deep: true })
watch(expandedInterpretation, saveState, { deep: true })

// 路由变化时重置状态
watch(() => $route.path, (path) => {
  if (path === '/llm-ask-v2b') {
    resetState()
  }
})

const messagesContainer = ref(null)

// Drawer states
const logicDrawerVisible = ref(false)
const attributionVisible = ref(false)
const reportVisible = ref(false)

const currentThinkingSteps = ref([])
const stepsVersion = ref(0)
const currentSql = ref('')

const positiveFactors = ref([])
const negativeFactors = ref([])
const trendData = ref([])

const volatilityPanelRef = ref(null)
const currentMetricName = ref('')
const volatilityApiUrl = '/api/v1/llm-ask/v2/volatility/stream'
let pendingAutoVolatilityQuestion = ''

const reportTitle = ref('')
const reportSummary = ref('')
const reportCoreCards = ref([])
const reportDetailList = ref([])
const reportDetailHeaders = ref([])
const reportSuggestions = ref([])

const greetingText = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 9) return '早晨好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  if (hour < 21) return '傍晚好'
  return '晚上好'
})

onMounted(async () => {
  await fetchInitialSuggestions()
  resetState()
  sessionId.value = ''
  loadSessions()
  scrollToBottom()
})

// 点击外部关闭操作菜单
if (typeof document !== 'undefined') {
  document.addEventListener('click', () => {
    if (activeActionMenu.value) {
      activeActionMenu.value = null
      menuPosition.value = {}
    }
  })
}

// Icon 组件
const QueryIcon = () => h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
  h('circle', { cx: 10, cy: 10, r: 7, stroke: 'currentColor', 'stroke-width': 1.5 }),
  h('path', { d: 'M14 14L18 18', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' })
])
const TrendIcon = () => h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
  h('path', { d: 'M3 14L8 9L11 12L17 5', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })
])
const ChartIcon = () => h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
  h('path', { d: 'M3 17V11M8 17V7M13 17V13M18 17V3', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' })
])
const AlertIcon = () => h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
  h('path', { d: 'M10 2C7.24 2 5 4.24 5 7V9L3 12V13H17V12L15 9V7C15 4.24 12.76 2 10 2Z', stroke: 'currentColor', 'stroke-width': 1.5 }),
  h('path', { d: 'M8 13V14C8 15.1 8.9 16 10 16C11.1 16 12 15.1 12 14V13H8Z', stroke: 'currentColor', 'stroke-width': 1.5 })
])

const iconMap = { QueryIcon, TrendIcon, ChartIcon, AlertIcon }

const suggestions = ref([])

async function fetchInitialSuggestions() {
  try {
    const res = await fetch('/api/v1/internal/ask/suggest-v2')
    const data = await res.json()
    if (data.code === 0 && data.data) {
      suggestions.value = data.data.map(s => ({
        ...s,
        icon: iconMap[s.icon] || QueryIcon
      }))
    }
  } catch (e) {
    console.error('获取快捷提问失败:', e)
    suggestions.value = [
      { title: '看品类对比', desc: '先看本月各品类规模，再决定要不要继续下钻。', icon: QueryIcon, text: '本月各品类销售额对比一下' },
      { title: '看近期变化', desc: '用趋势先判断最近 30 天有没有明显拐点。', icon: TrendIcon, text: '近30天用户数变化趋势怎么样' },
      { title: '找异常波动', desc: '先把异常指标挑出来，再解释为什么变动。', icon: AlertIcon, text: '最近有哪些指标出现异常' },
      { title: '做环比对比', desc: '先给我本月和上月的关键差异，再看细分。', icon: ChartIcon, text: '对比本月与上月数据差异' }
    ]
  }
}

function handleEnterKey() {
  handleSend()
}

function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

async function handleSend() {
  if (!question.value.trim() || loading.value) return

  const userQuestion = question.value.trim()
  question.value = ''
  pendingAutoVolatilityQuestion = userQuestion

  let displayQuestion = userQuestion
  if (userQuestion.startsWith('__DRILLDOWN__:')) {
    const match = userQuestion.match(/^__DRILLDOWN__:(.+?)__$/)
    if (match) {
      const type = match[1]
      const label = DRILLDOWN_LABELS[type] || type
      displayQuestion = `请做${label}`
    }
  }

  messages.value.push({
    role: 'user',
    content: displayQuestion,
    time: getCurrentTime()
  })

  const pendingMessage = {
    id: `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    role: 'assistant',
    content: '',
    time: getCurrentTime(),
    loading: true,
    processingLabel: '正在分析你的问题…',
    thinkingSteps: [],
  }
  messages.value.push(pendingMessage)

  scrollToBottom()
  loading.value = true
  logicDrawerVisible.value = false
  currentThinkingSteps.value = []
  currentSql.value = ''

  const streamAccumulator = createLlmAskStreamAccumulator({
    onThinkingStepsChange: (steps) => {
      currentThinkingSteps.value = steps
      stepsVersion.value++
      pendingMessage.thinkingSteps = steps
      const lastStep = [...steps].reverse().find(step => step.content || step.status === 'in_progress')
      pendingMessage.processingLabel = lastStep?.content || `正在${getStepName(lastStep?.step || 'intent_router')}…`
    },
    onSqlChange: (sql) => {
      currentSql.value = sql
    },
    onSessionConnected: (incomingSessionId) => {
      sessionId.value = incomingSessionId
    },
    onDone: () => {
      if (sessionId.value) {
        loadSessions()
      }
    },
    onError: (error) => {
      console.error('SSE Error:', error)
    },
  })

  try {
    if (abortController) {
      abortController.abort()
    }
    abortController = new AbortController()
    const token = localStorage.getItem('token') || ''
    const resolvedUserId = (() => {
      try {
        const userInfo = localStorage.getItem('user_info')
        if (userInfo) {
          const user = JSON.parse(userInfo)
          return user && user.id ? String(user.id) : 'default'
        }
      } catch (e) {}
      return 'default'
    })()

    await runLlmAskStream({
      question: userQuestion,
      sessionId: sessionId.value,
      token,
      userId: resolvedUserId,
      signal: abortController.signal,
      onEvent: (currentEvent, data) => streamAccumulator.handleEvent(currentEvent, data),
    })

    const finalSteps = streamAccumulator.getFinalSteps()
    const finalMessage = streamAccumulator.buildMessage(getCurrentTime())
    const pendingIndex = messages.value.findIndex(item => item.id === pendingMessage.id)
    if (pendingIndex >= 0) {
      messages.value.splice(pendingIndex, 1, finalMessage)
      expandedThinking.value[pendingIndex] = false
    } else {
      messages.value.push(finalMessage)
      expandedThinking.value[messages.value.length - 1] = false
    }

    currentThinkingSteps.value = finalSteps
    stepsVersion.value++

    await nextTick()
    const latestMsg = messages.value[messages.value.length - 1]
    const latestResultData = streamAccumulator.getFinalResultData()
    if (latestMsg && latestResultData && latestResultData.length > 0) {
      const q = pendingAutoVolatilityQuestion || ''
      const isComparisonQuestion = /为什么|为啥|为什么.比|为啥.比|哪个.高|哪个.低|对比|比较|差异/.test(q)
      if (isComparisonQuestion && canDoVolatilityAnalysis(latestResultData)) {
        if (!latestMsg.momChange && latestMsg.analysis?.kpi?.mom != null) {
          latestMsg.momChange = latestMsg.analysis.kpi.mom / 100
        }
        if (!latestMsg.yoyChange && latestMsg.analysis?.kpi?.yoy != null) {
          latestMsg.yoyChange = latestMsg.analysis.kpi.yoy / 100
        }
        if (!latestMsg.timeRange || !latestMsg.timeRange.start) {
          for (let i = finalSteps.length - 1; i >= 0; i--) {
            const step = finalSteps[i]
            if (step?.mql?.time?.start) {
              latestMsg.timeRange = step.mql.time
              break
            }
          }
        }
        openAttribution(latestMsg)
      }
    }

  } catch (e) {
    console.error('流式请求失败:', e)
    const fallbackMessage = {
      role: 'assistant',
      content: '抱歉，服务出现问题，请稍后再试。',
      time: getCurrentTime()
    }
    const pendingIndex = messages.value.findIndex(item => item.id === pendingMessage.id)
    if (pendingIndex >= 0) {
      messages.value.splice(pendingIndex, 1, fallbackMessage)
    } else {
      messages.value.push(fallbackMessage)
    }
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function canDoVolatilityAnalysis(resultData) {
  if (!resultData || resultData.length === 0) return false
  const firstRow = resultData[0]
  if (!firstRow) return false
  const keys = Object.keys(firstRow)
  const isComparisonRow = keys.includes('当前值') && keys.includes('环比值')
  if (isComparisonRow) return true
  if (resultData.length === 1) return false
  const hasDimensionColumn = keys.some(k =>
    /^GROUP_\d$/i.test(k) ||
    /^(dimension|channel|site|品类|品牌|平台|category)$/i.test(k)
  )
  return resultData.length > 1 || hasDimensionColumn
}

function prepareAttributionData(data) {
  const resultData = data?.result_data || []
  if (resultData.length === 0) return
  const keys = Object.keys(resultData[0])
  const numericKeys = keys.filter(k => typeof resultData[0][k] === 'number')
  positiveFactors.value = []
  negativeFactors.value = []
  trendData.value = resultData
  if (numericKeys.length > 0) {
    const sampleKey = numericKeys[0]
    const values = resultData.map(r => r[sampleKey]).filter(v => typeof v === 'number')
    values.forEach((val, idx) => {
      if (val >= 0) {
        positiveFactors.value.push({ name: resultData[idx][keys[0]], value: val })
      } else {
        negativeFactors.value.push({ name: resultData[idx][keys[0]], value: val })
      }
    })
  }
}

function openAttribution(msg) {
  let resultDataCopy = JSON.parse(JSON.stringify(msg.resultData || []))
  let timeRange = msg.timeRange ? { start: msg.timeRange.start, end: msg.timeRange.end } : null
  if (resultDataCopy.length === 1) {
    const row = resultDataCopy[0]
    const hasCurrent = '当前值' in row
    const hasPrev = '环比值' in row
    if (hasCurrent && hasPrev) {
      const currentVal = parseFloat(row['当前值']) || 0
      const prevVal = parseFloat(row['环比值']) || 0
      let currentDate = ''
      let prevDate = ''
      if (timeRange && timeRange.start) {
        currentDate = timeRange.start
        const d = new Date(timeRange.start)
        d.setMonth(d.getMonth() - 1)
        prevDate = d.toISOString().slice(0, 10)
      }
      resultDataCopy = [
        { date: currentDate, value: currentVal },
        { date: prevDate, value: prevVal }
      ]
      const momFromMsg = msg.momChange ?? (prevVal !== 0 ? (currentVal - prevVal) / prevVal : null)
      const yoyFromMsg = msg.yoyChange ?? null
      if (prevDate && currentDate) {
        timeRange = { start: prevDate, end: currentDate }
        msg.timeRange = timeRange
      }
      msg.momChange = momFromMsg
      msg.yoyChange = yoyFromMsg
    }
  }
  currentMetricName.value = msg.metricName || '指标'
  prepareAttributionData({ result_data: resultDataCopy })
  attributionVisible.value = true
  if (volatilityPanelRef.value && resultDataCopy.length > 0) {
    volatilityPanelRef.value.startStream({
      metric_name: msg.metricName || '指标',
      data: resultDataCopy,
      dimension_key: 'dimension',
      mom_change: msg.momChange ?? null,
      yoy_change: msg.yoyChange ?? null,
      starrocks_sql: msg.starrocksSql ?? null,
      dimension_filters: (msg.dimensionFilters || []).map(d => ({
        column: d.column || d.type || '',
        value: d.value || ''
      })),
      time_range: timeRange
    })
  }
}

function generateReport(msg) {
  const resultData = msg.resultData || []
  if (resultData.length === 0) return
  const keys = Object.keys(resultData[0])
  const numericKeys = keys.filter(k => typeof resultData[0][k] === 'number')
  reportTitle.value = '数据分析报告'
  reportSummary.value = msg.content || '根据查询结果生成的分析报告'
  if (numericKeys.length > 0) {
    const key = numericKeys[0]
    const values = resultData.map(r => r[key]).filter(v => typeof v === 'number')
    const sum = values.reduce((a, b) => a + b, 0)
    const avg = sum / values.length
    reportCoreCards.value = [
      { label: keys[0], value: sum.toFixed(2), trend: Math.random() * 20 - 10 },
      { label: '记录数', value: resultData.length, trend: 0 },
      { label: '平均值', value: avg.toFixed(2), trend: Math.random() * 10 - 5 }
    ]
  }
  reportDetailList.value = resultData.slice(0, 10)
  reportDetailHeaders.value = keys
  reportSuggestions.value = msg.suggest || ['建议进一步分析数据趋势', '关注异常波动指标']
  reportVisible.value = true
}

function handleTrace(factor) {
  console.log('Tracing factor:', factor)
}

function handleExportPdf(element) {
  console.log('Export PDF:', element)
}

function handleSendEmail(text) {
  console.log('Send email:', text)
}

function toggleThinking(idx) {
  expandedThinking.value[idx] = !expandedThinking.value[idx]
}

function toggleInterpretation(idx) {
  expandedInterpretation.value[idx] = !expandedInterpretation.value[idx]
}

function openThinkingDrawer(msg) {
  currentThinkingSteps.value = Array.isArray(msg.thinkingSteps) ? msg.thinkingSteps : []
  currentSql.value = msg.sql || msg.starrocksSql || ''
  logicDrawerVisible.value = true
}

async function rateMessage(msg, rating) {
  if (msg.rating === rating) {
    msg.rating = null
  } else {
    msg.rating = rating
  }
  try {
    await askAPI.sendFeedback({
      session_id: sessionId.value,
      feedback: rating
    })
  } catch (err) {
    console.error('反馈提交失败:', err)
  }
}

function selectClarification(option, originalQuestion) {
  if (option.replace_key && originalQuestion) {
    const rewritten = originalQuestion.replace(option.replace_key, option.value)
    question.value = rewritten
  } else {
    question.value = option.label
  }
  handleSend()
}

function handleClarificationSelect(option) {
  console.log('Clarification selected:', option)
}

function handleClarificationConfirm(option) {
  question.value = option.label
  handleSend()
}

function handlePlanConfirm(plan) {
  loading.value = true
  llmAskApi.confirmPlan(plan).then(res => {
    console.log('Plan confirmed:', res)
  }).finally(() => {
    loading.value = false
  })
}

function handlePlanModify(modifiedPlan) {
  loading.value = true
  llmAskApi.modifyPlan(modifiedPlan).then(res => {
    console.log('Plan modified:', res)
  }).finally(() => {
    loading.value = false
  })
}

function handleDrilldown(option) {
  if (!option) return
  // SSE drilldown_options 格式: { label, action, params: { question } }
  if (option.params?.question) {
    question.value = option.params.question
    handleSend()
    return
  }
  // 旧格式: { check: 'sales' }
  if (option.check) {
    let q = ''
    if (option.check === 'sales') q = '__DRILLDOWN__:sales__'
    else if (option.check === 'ad') q = '__DRILLDOWN__:ad__'
    else if (option.check === 'inventory' || option.check === 'supply') q = '__DRILLDOWN__:inventory__'
    else if (option.check === 'profit' || option.check === 'cost') q = '__DRILLDOWN__:cost__'
    if (q) {
      question.value = q
      handleSend()
    }
  }
}

function selectSuggestion(s, contextMsg = null) {
  let fullQuestion = s
  if (contextMsg) {
    const timeRange = contextMsg.timeRange || contextMsg.mql?.time
    let dimensionFilters = contextMsg.dimensionFilters || contextMsg.dimensions || []
    if (Array.isArray(dimensionFilters)) {
      dimensionFilters = dimensionFilters.map(dim => {
        if (typeof dim === 'object' && dim !== null) {
          if (dim.value !== undefined && dim.value !== null) return String(dim.value)
          const entries = Object.entries(dim)
          return entries.length > 0 ? String(entries[0][1]) : ''
        }
        return String(dim)
      }).filter(v => v && v !== 'null')
    } else if (typeof dimensionFilters === 'object' && dimensionFilters !== null) {
      dimensionFilters = Object.entries(dimensionFilters).map(([k, v]) => String(v))
    }
    if (timeRange?.start && timeRange?.end) {
      const hasTimeExpr = /近\d+[天日月年]|今天|昨天|本周|本月|本年|上月|去年/.test(s)
      if (!hasTimeExpr) fullQuestion = `${timeRange.start} ~ ${timeRange.end}的${s}`
    } else if (timeRange?.start) {
      const hasTimeExpr = /近\d+[天日月年]|今天|昨天|本周|本月|本年|上月|去年/.test(s)
      if (!hasTimeExpr) fullQuestion = `${timeRange.start}以来的${s}`
    }
    if (dimensionFilters && dimensionFilters.length > 0) {
      const dimStr = dimensionFilters.join('、')
      const hasDimExpr = dimensionFilters.some(dim => s.includes(dim))
      if (!hasDimExpr) fullQuestion = `${dimStr}的${fullQuestion}`
    }
  }
  question.value = fullQuestion
  handleSend()
}

const stepNameMap = {
  'intent_router': '理解意图',
  'context_enhancer': '增强上下文',
  'mql_generator': '生成查询逻辑',
  'mql_syntax_validator': '校验语法',
  'mql_semantic_validator': '校验语义',
  'sql_generator': '生成SQL',
  'sql_security_auditor': '安全审计',
  'sql_executor': '执行查询',
  'data_quality_checker': '质量检查',
  'result_analyzer': '分析结果',
  'state_manager': '整理输出',
  'intent_node': '理解意图',
  'entity_router': '识别实体',
  'entity_node': '识别实体',
  'sql_gen': '生成SQL',
  'sql_gen_node': '生成SQL',
  'execute': '执行查询',
  'execute_node': '执行查询',
  'response': '生成回答',
  'response_node': '生成回答',
  'intent recognition': '理解意图',
  'entity extraction': '识别实体',
  'sql generation': '生成SQL',
  'execution': '执行查询',
  'response generation': '生成回答'
}

function getStepName(stepName) {
  return stepNameMap[stepName] || stepName
}

function isSlotMissingOptions(options) {
  if (!options || !Array.isArray(options) || options.length === 0) return false
  const categoryKeywords = ['一级', '二级', '三级', '四级', '品类', '类目']
  const isCategoryLevel = options.every(opt => {
    const label = opt.label || opt.value || String(opt)
    return categoryKeywords.some(kw => String(label).includes(kw))
  })
  if (isCategoryLevel) return false
  return options.length <= 3 && options.every(opt => typeof opt === 'string' || (opt.label && typeof opt.label === 'string'))
}

function formatMessage(text) {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

function formatDateRange(start, end) {
  if (!start) return ''
  const s = start ? start.slice(0, 10) : ''
  const e = end ? end.slice(0, 10) : ''
  if (s && e && s !== e) return `${s} ~ ${e}`
  return s
}

function getCurrentTime() {
  return new Date().toISOString()
}

function formatTime(isoString) {
  if (!isoString) return ''
  const d = new Date(isoString)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function getHealthClass(score) {
  if (score >= 90) return 'health-excellent'
  if (score >= 70) return 'health-good'
  return 'health-warning'
}

async function copyMessage(msg) {
  try {
    if (msg.resultData && msg.resultData.length > 0) {
      const keys = Object.keys(msg.resultData[0])
      const header = keys.join('\t')
      const rows = msg.resultData.map(row => keys.map(k => row[k] ?? '').join('\t'))
      const csvText = [header, ...rows].join('\n')
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(csvText)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = csvText
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      return
    }
    if (msg.sql) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(msg.sql)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = msg.sql
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      return
    }
    if (msg.content) {
      const plainText = msg.content.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '')
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(plainText)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = plainText
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      return
    }
  } catch (err) {
    console.error('复制失败:', err)
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// Ctrl+K 快捷键新建对话
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      handleSidebarNewChat()
    }
  })
}
</script>

<style scoped>
/* ===== CSS 变量 ===== */
.llm-ask-v2b {
  --sidebar-bg: #f8f9fa;
  --sidebar-w: 280px;
  --main-bg: #ffffff;
  --active-blue: #2468f2;
  --active-blue-light: #e8f0fe;
  --hover-grey: #edeff2;
  --text-main: #1f2329;
  --text-sub: #646a73;
  --text-muted: #8f959e;
  --border-color: #dee0e3;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.12);
}

/* ===== 整体布局 ===== */
.llm-ask-v2b {
  height: 100vh;
  width: 100%;
  display: flex;
  overflow-x: visible;
  overflow-y: hidden;
  background: var(--main-bg);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ===== 侧边栏遮罩（手机端） ===== */
.sidebar-overlay {
  display: none;
}

/* ===== 左侧边栏 ===== */
.sidebar {
  width: var(--sidebar-w);
  height: 100vh;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  flex-shrink: 0;
  border-right: 1px solid #eee;
  overflow-x: visible;
  overflow-y: hidden;
  user-select: none;
  text-align: left;
}

.brand-section {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px 14px;
  justify-content: flex-start;
}

.brand-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.brand-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.brand-name {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: -0.3px;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 0 16px 20px;
  padding: 10px 0;
  background: var(--active-blue);
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.new-chat-btn:hover {
  background: #1b5ae0;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(36, 104, 242, 0.3);
}

.new-chat-btn:active {
  transform: translateY(0);
}

.new-chat-btn svg {
  opacity: 0.9;
}

.history-section {
  flex: 1;
  overflow-x: visible;
  overflow-y: hidden;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px 8px;
}

.history-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.history-count {
  font-size: 11px;
  color: var(--text-muted);
  background: #f2f3f5;
  padding: 1px 7px;
  border-radius: 8px;
  font-weight: 500;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.history-list::-webkit-scrollbar {
  width: 4px;
}

.history-list::-webkit-scrollbar-thumb {
  background: #e0e0e0;
  border-radius: 4px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  margin-bottom: 1px;
  position: relative;
}

.history-item:hover {
  background: #f5f6f7;
}

.history-item.active {
  background: #e8f0fe;
}

.history-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #c4c7cc;
  flex-shrink: 0;
  transition: background 0.15s ease;
}

.history-item:hover .history-dot {
  background: var(--text-muted);
}

.history-item.active .history-dot {
  background: var(--active-blue);
}

.history-text {
  font-size: 13px;
  color: var(--text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
  transition: color 0.15s ease;
  max-width: 180px;
  flex: 1;
  min-width: 0;
}

.history-actions {
  /* 已移除 */
}

.action-trigger {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
  opacity: 0;
  margin-left: auto;
}

.history-item:hover .action-trigger {
  opacity: 1;
}

.action-trigger:hover {
  background: #e8e8e8;
  color: var(--text-main);
}

.action-menu {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.15);
  z-index: 2000;
  min-width: 130px;
  padding: 4px;
  animation: menuFadeIn 0.12s ease;
}

@keyframes menuFadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.action-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-main);
  cursor: pointer;
  transition: background 0.1s ease;
}

.action-menu-item:hover {
  background: #f5f6f7;
}

.action-menu-item.danger {
  color: #ef4444;
}

.action-menu-item.danger:hover {
  background: #fef2f2;
}

.history-item:hover .history-text {
  color: var(--text-main);
}

.history-item.active .history-text {
  color: var(--text-main);
  font-weight: 500;
}

.pin-icon {
  flex-shrink: 0;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  font-size: 13px;
  color: #c4c7cc;
}

.user-section {
  padding: 12px 16px 16px;
  border-top: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  transition: background 0.15s ease;
}

.user-card:hover {
  background: #f5f6f7;
}

.user-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 11px;
  color: var(--text-muted);
}

/* ===== 右侧主内容区 ===== */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  background: var(--main-bg);
}

/* 手机端顶部工具栏（默认隐藏） */
.mobile-header {
  display: none;
}

/* 桌面端 header */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-main);
}

.header-hint {
  font-size: 12px;
  color: var(--text-muted);
}

/* ===== 聊天内容区 ===== */
.chat-body {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.msg-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 24px 160px;
  width: 100%;
  box-sizing: border-box;
}

/* ===== 初始化界面 ===== */
.init-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 80px;
}

.init-greeting {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 48px;
}

.init-logo {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  object-fit: contain;
  flex-shrink: 0;
}

.init-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-main);
  margin: 0;
  line-height: 1.4;
}

.init-suggestions {
  width: 100%;
  max-width: 640px;
}

.suggestions-label {
  font-size: 14px;
  color: var(--text-sub);
  margin-bottom: 16px;
}

.suggestions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.suggest-chip {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  background: #f7f8fa;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.suggest-chip:hover {
  background: var(--active-blue-light);
  border-color: var(--active-blue);
}

.chip-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--active-blue);
}

.chip-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-main);
  margin-bottom: 4px;
}

.chip-desc {
  font-size: 12px;
  color: var(--text-sub);
  line-height: 1.4;
}

.chip-body {
  min-width: 0;
}

/* ===== 消息区域 ===== */
.messages-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ===== 底部悬浮输入框 ===== */
.input-sticky {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 800px;
  padding: 0 24px;
  box-sizing: border-box;
  z-index: 10;
}

.input-bar {
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.input-top {
  display: flex;
  align-items: flex-end;
  padding: 12px 12px 8px 20px;
  gap: 8px;
}

.chat-textarea {
  flex: 1;
  border: none;
  outline: none;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  background: transparent;
  color: var(--text-main);
  min-height: 24px;
  max-height: 120px;
  font-family: inherit;
}

.chat-textarea::placeholder {
  color: var(--text-muted);
}

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--active-blue);
  border: none;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: #1b5ae0;
  transform: scale(1.05);
}

.send-btn:disabled {
  background: #d0d5dd;
  cursor: not-allowed;
}

.send-btn svg {
  display: block;
}

.loading-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.input-tools {
  display: flex;
  gap: 8px;
  padding: 4px 20px 10px;
}

.input-tool-tag {
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-sub);
  background: #f2f3f5;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.input-tool-tag:hover {
  background: var(--active-blue-light);
  color: var(--active-blue);
}

/* ===== 手机端响应式 ===== */
@media (max-width: 768px) {
  /* 左滑删除（iOS 风格） */
  .swipe-wrapper {
    position: relative;
    overflow: hidden;
    margin-bottom: 1px;
  }

  .swipe-content {
    position: relative;
    z-index: 2;
    background: #fff;
    transition: transform 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    will-change: transform;
  }
  /* 滑动过程中取消过渡，跟手指实时走 */
  .swipe-content:active {
    transition: none;
  }

  .swipe-delete {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    width: 72px;
    background: #f5f5f7;
    color: #8e8e93;
    border: none;
    font-size: 13px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    cursor: pointer;
    z-index: 1;
    -webkit-tap-highlight-color: transparent;
  }
  .swipe-delete:active {
    color: #ff3b30;
  }

  /* 手机端隐藏三个点菜单 */
  .action-trigger { display: none; }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 999;
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 1000;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    box-shadow: none;
  }

  .sidebar.open {
    transform: translateX(0);
    box-shadow: var(--shadow-lg);
  }

  .mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
    background: var(--main-bg);
  }

  .mobile-menu-btn,
  .mobile-new-btn {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-main);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .mobile-menu-btn:hover,
  .mobile-new-btn:hover {
    background: var(--hover-grey);
  }

  .mobile-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-main);
  }

  .chat-header {
    display: none;
  }

  .msg-container {
    padding: 16px 16px 140px;
  }

  .init-content {
    padding-top: 40px;
  }

  .init-greeting {
    flex-direction: column;
    text-align: center;
    margin-bottom: 32px;
  }

  .init-title {
    font-size: 18px;
  }

  .suggestions-grid {
    grid-template-columns: 1fr;
  }

  .input-sticky {
    left: 0;
    transform: none;
    max-width: 100%;
    padding: 0 12px;
    bottom: 12px;
  }

  .input-bar {
    border-radius: 16px;
  }
}

@media (min-width: 769px) and (max-width: 1024px) {
  .sidebar {
    width: 220px;
  }
  .msg-container {
    max-width: 680px;
  }
}
</style>

<style>
/* 删除确认弹窗（Teleport to body，需非 scoped） */
.delete-confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.15s ease;
}

.delete-confirm-dialog {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  min-width: 320px;
  max-width: 400px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.2s ease;
}

.delete-confirm-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2329;
  margin-bottom: 12px;
}

.delete-confirm-msg {
  font-size: 14px;
  color: #4e5969;
  line-height: 1.6;
  margin-bottom: 20px;
}

.delete-confirm-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.dc-btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
}

.dc-cancel {
  background: #f2f3f5;
  color: #4e5969;
}

.dc-cancel:hover {
  background: #e5e6eb;
}

.dc-danger {
  background: #ef4444;
  color: #fff;
}

.dc-danger:hover {
  background: #dc2626;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
