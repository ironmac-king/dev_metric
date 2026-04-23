<template>
  <div class="llm-ask-v2" :class="{ 'drawer-open': logicDrawerVisible }">
    <!-- 居中大容器 -->
    <div class="main-container" :class="{ 'fullscreen-result': hasResult }">
      <!-- 左侧对话区 -->
      <div class="chat-wrapper">
        <!-- 统一内容区 -->
        <div class="content-area">
          <!-- 初始化界面 -->
          <div v-if="messages.length === 0" class="init-view">
            <!-- 顶部问候区 -->
            <div class="greeting-section">
              <div class="avatar-wrapper" ref="avatarContainer"></div>
              <h1 class="welcome-text">{{ greetingText }}，匀点工作给我吧~</h1>
            </div>

            <!-- 快捷功能胶囊栏 -->
            <div class="mode-tabs">
              <button
                v-for="mode in modes"
                :key="mode.id"
                class="mode-tab"
                :class="{ active: activeMode === mode.id }"
                @click="activeMode = mode.id"
              >
                <component :is="mode.icon" />
                {{ mode.label }}
              </button>
            </div>

            <!-- 主输入框区域 -->
            <div class="init-input-section">
              <div class="chat-input-wrapper">
                <textarea
                  v-model="question"
                  class="chat-input"
                  placeholder="直接向我提问，输入/唤起快捷提示词"
                  rows="1"
                  @keydown.enter.exact.prevent="handleSend"
                ></textarea>
                <button class="send-btn" :disabled="!question.trim() || loading" @click="handleSend">
                  <svg v-if="!loading" width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M18 10L2 2L10 10M18 10L10 18M18 10L2 10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none" class="loading-spinner">
                    <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="50" stroke-dashoffset="12" stroke-linecap="round"/>
                  </svg>
                </button>
              </div>
              <div class="input-tools-bar">
                <span class="tool-icon">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M3 10H17M10 3L17 10L10 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
                <span class="tool-icon">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <rect x="2" y="4" width="16" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M6 8L10 12L14 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                </span>
                <span class="tool-hint">/ 唤起快捷词</span>
              </div>
            </div>

            <!-- 快捷提问卡片 -->
            <div class="suggestions-section">
              <div class="suggestions-title">快捷提问：</div>
              <div class="suggestions-grid">
                <div
                  v-for="suggestion in suggestions"
                  :key="suggestion.title"
                  class="suggestion-card"
                  @click="selectSuggestion(suggestion.text)"
                >
                  <div class="card-icon">
                    <component :is="suggestion.icon" />
                  </div>
                  <div class="card-content">
                    <h4><span class="slash-icon">/</span>{{ suggestion.title }}</h4>
                    <p>{{ suggestion.desc }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 聊天界面 -->
          <div v-else class="chat-view">
            <!-- 消息列表 -->
            <div class="messages-container" ref="messagesContainer">
              <div class="messages-list">
                <div
                  v-for="(msg, idx) in messages"
                  :key="idx"
                  class="message-item"
                  :class="{ 'user': msg.role === 'user', 'assistant': msg.role === 'assistant' }"
                >
                  <div v-if="msg.role === 'assistant'" class="message-avatar">
                    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                      <rect x="2" y="14" width="6" height="12" rx="1.5" fill="url(#msgLogoGrad2)"/>
                      <rect x="11" y="8" width="6" height="18" rx="1.5" fill="url(#msgLogoGrad2)" opacity="0.7"/>
                      <rect x="20" y="2" width="6" height="24" rx="1.5" fill="url(#msgLogoGrad2)" opacity="0.4"/>
                      <defs>
                        <linearGradient id="msgLogoGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" stop-color="#6366F1"/>
                          <stop offset="100%" stop-color="#8B5CF6"/>
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>
                  <div v-else class="message-avatar">
                    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                      <circle cx="14" cy="14" r="12" fill="url(#userAvatarGrad)"/>
                      <text x="14" y="18" text-anchor="middle" fill="#fff" font-size="12" font-weight="600">U</text>
                      <defs>
                        <linearGradient id="userAvatarGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" stop-color="#6366F1"/>
                          <stop offset="100%" stop-color="#8B5CF6"/>
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>
                  <div class="message-content" :class="{ loading: msg.loading }">
                    <div v-if="msg.loading" class="loading-dots">
                      <span></span><span></span><span></span>
                    </div>
                    <template v-else>
                      <div class="message-text" v-html="formatMessage(msg.content)"></div>
                      <div class="message-time">{{ msg.time }}</div>
                      <div v-if="msg.role === 'assistant'" class="message-actions">
                        <button class="action-btn" @click="copyMessage(msg)" title="复制">
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                            <rect x="4" y="4" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/>
                            <path d="M2 8V2H8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                          </svg>
                          复制
                        </button>
                        <button v-if="msg.interpretation" class="action-btn" @click="toggleInterpretation(idx)" :class="{ active: expandedInterpretation[idx] }" title="数据解读">
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                            <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.2"/>
                            <path d="M6 4V6M6 7.5V8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                          </svg>
                          解读
                        </button>
                        <button class="action-btn" @click="rateMessage(msg, 'up')" :class="{ active: msg.rating === 'up' }" title="好评">
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                            <path d="M6 2L7.5 5H10L6 8L2 5H4.5L6 2Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
                          </svg>
                        </button>
                        <button class="action-btn" @click="rateMessage(msg, 'down')" :class="{ active: msg.rating === 'down' }" title="差评">
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                            <path d="M6 10L4.5 7H2L6 4L10 7H7.5L6 10Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
                          </svg>
                        </button>
                      </div>
                    </template>

                    <!-- 异常标注 -->
                    <div v-if="msg.anomalies && msg.anomalies.length > 0" class="anomaly-list">
                      <div v-for="anomaly in msg.anomalies" :key="anomaly.type" class="anomaly-item">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path d="M7 1L13 12H1L7 1Z" stroke="#F59E0B" stroke-width="1.5" stroke-linejoin="round"/>
                          <path d="M7 5V8" stroke="#F59E0B" stroke-width="1.5" stroke-linecap="round"/>
                          <circle cx="7" cy="10.5" r="0.75" fill="#F59E0B"/>
                        </svg>
                        <span>{{ anomaly.message }}</span>
                      </div>
                    </div>

                    <!-- 意图澄清卡片 (action_type=clarify) -->
                    <ClarificationCard
                      v-if="msg.action_type === 'clarify' && msg.clarify_options"
                      :options="msg.clarify_options"
                      @select="handleClarificationSelect"
                      @confirm="handleClarificationConfirm"
                    />

                    <!-- 方案确认卡片 (action_type=confirm) -->
                    <PlanConfirmCard
                      v-if="msg.action_type === 'confirm' && msg.confirm_plan"
                      :plan="msg.confirm_plan"
                      @confirm="handlePlanConfirm"
                      @modify="handlePlanModify"
                    />

                    <!-- 泛指追问选项 -->
                    <div v-if="msg.needsClarification && msg.clarificationOptions" class="clarification-tags">
                      <span class="clarification-msg">{{ msg.clarificationMessage }}</span>
                      <button
                        v-for="option in msg.clarificationOptions"
                        :key="option.value"
                        class="clarification-tag"
                        @click="selectClarification(option, msg.originalQuestion)"
                      >
                        {{ option.label }}
                      </button>
                    </div>

                    <!-- 数据解读 -->
                    <div v-if="msg.interpretation && expandedInterpretation[idx]" class="message-interpretation">
                      {{ msg.interpretation }}
                    </div>

                    <!-- 图表展示 -->
                    <ChartCard
                      v-if="msg.resultData && msg.resultData.length > 0"
                      :data="msg.resultData"
                      :height="260"
                      :interpretation="msg.interpretation"
                      :truncation-length="12"
                      :metric-name="msg.metricName || ''"
                      :metric-names="msg.metricNames || []"
                      class="message-chart"
                    />

                    <!-- 思考过程 -->
                    <div v-if="msg.thinkingSteps && msg.thinkingSteps.length > 0" class="thinking-panel">
                      <button class="thinking-toggle" @click="toggleThinking(idx)">
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.2"/>
                          <path d="M6 3V6L8 7" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                        </svg>
                        <span>分析过程 ({{ msg.thinkingSteps.length }}步)</span>
                        <svg class="toggle-icon" :class="{ expanded: expandedThinking[idx] }" width="10" height="10" viewBox="0 0 10 10" fill="none">
                          <path d="M2 4L5 7L8 4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                      </button>
                      <div v-if="expandedThinking[idx]" class="thinking-steps">
                        <div
                          v-for="(step, sIdx) in msg.thinkingSteps"
                          :key="sIdx"
                          class="thinking-step"
                          :class="step.status"
                        >
                          <span class="step-name">{{ getStepName(step.step) }}</span>
                          <span class="step-status">
                            <span v-if="step.status === 'completed'" class="status-icon completed">✓</span>
                            <span v-else-if="step.status === 'failed'" class="status-icon failed">✗</span>
                            <span v-else class="status-icon pending">●</span>
                          </span>
                          <span v-if="step.duration" class="step-duration">{{ step.duration }}</span>
                          <span v-if="step.llm_used" class="llm-badge">LLM</span>
                        </div>
                      </div>
                    </div>

                    <!-- 建议问题 -->
                    <div v-if="msg.suggest && msg.suggest.length > 0" class="suggest-list">
                      <span class="suggest-label">建议：</span>
                      <button
                        v-for="s in msg.suggest"
                        :key="s"
                        class="suggest-btn"
                        @click="selectSuggestion(s)"
                      >
                        {{ s }}
                      </button>
                    </div>

                    <!-- 一键归因按钮 -->
                    <button
                      v-if="msg.resultData && msg.resultData.length > 0"
                      class="attribution-btn"
                      @click="openAttribution(msg)"
                    >
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M3 14L7 9L10 12L17 5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                      一键归因分析
                    </button>

                    <!-- 生成报告按钮 -->
                    <button
                      v-if="msg.resultData && msg.resultData.length > 0"
                      class="report-btn"
                      @click="generateReport(msg)"
                    >
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <rect x="2" y="1" width="10" height="12" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
                        <path d="M4 4H10M4 7H10M4 10H7" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                      </svg>
                      生成报告
                    </button>
                  </div>
                </div>
              </div>
            </div>

          <!-- 输入框区域 -->
          <div class="input-section">
            <div class="chat-input-wrapper">
              <textarea
                v-model="question"
                class="chat-input"
                placeholder="输入您的数据分析问题..."
                rows="2"
                @keydown.enter.exact.prevent="handleSend"
              ></textarea>
              <button class="send-btn" :disabled="!question.trim() || loading" @click="handleSend">
                <svg v-if="!loading" width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M18 10L2 2L10 10M18 10L10 18M18 10L2 10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none" class="loading-spinner">
                  <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="50" stroke-dashoffset="12" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
        </div>
      </div>

      <!-- 右侧分析过程 -->
      <LogicChainDrawer
        v-model="logicDrawerVisible"
        :steps="currentThinkingSteps"
        :sql="currentSql"
        :steps-version="stepsVersion"
      />
    </div>

    <!-- 归因分析面板 -->
    <AttributionPanel
      v-model="attributionVisible"
      :positive-factors="positiveFactors"
      :negative-factors="negativeFactors"
      :trend-data="trendData"
      @trace="handleTrace"
    />

    <!-- 报告预览 -->
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
  </div>
</template>

<script setup>
import { ref, h, nextTick, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { llmAskApi } from '../api/llmAsk'
import LogicChainDrawer from '../components/ask/LogicChainDrawer.vue'
import ClarificationCard from '../components/ask/ClarificationCard.vue'
import PlanConfirmCard from '../components/ask/PlanConfirmCard.vue'
import ChartCard from '../components/ask/ChartCard.vue'
import AttributionPanel from '../components/ask/AttributionPanel.vue'
import ReportPreview from '../components/ask/ReportPreview.vue'
import lottie from 'lottie-web'

const router = useRouter()
const question = ref('')
const activeMode = ref('query')
const messages = ref([])
const loading = ref(false)

// Session ID for multi-turn conversation
const sessionId = ref('')

// 消息持久化到 localStorage
const STORAGE_KEY = 'llm_ask_messages'
const loadMessages = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      messages.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('Failed to load messages:', e)
  }
}
const saveMessages = () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value))
  } catch (e) {
    console.error('Failed to save messages:', e)
  }
}
// 监听消息变化自动保存
watch(messages, saveMessages, { deep: true })

// 是否有消息，用于全屏自适应
const hasResult = computed(() => messages.value.length > 0)
const expandedThinking = ref({})
const expandedInterpretation = ref({})
const messagesContainer = ref(null)
const avatarContainer = ref(null)
let avatarAnimation = null

// Drawer states
const logicDrawerVisible = ref(false)
const attributionVisible = ref(false)
const reportVisible = ref(false)

// Current thinking steps during processing
const currentThinkingSteps = ref([])
const stepsVersion = ref(0)  // 强制触发 Vue 重渲染
const currentSql = ref('')

// Attribution data
const positiveFactors = ref([])
const negativeFactors = ref([])
const trendData = ref([])

// Report data
const reportTitle = ref('')
const reportSummary = ref('')
const reportCoreCards = ref([])
const reportDetailList = ref([])
const reportDetailHeaders = ref([])
const reportSuggestions = ref([])

// Dynamic greeting based on time
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

// 知性美女挥手动画数据
const intelligentWomanData = {
  "v": "5.7.4",
  "fr": 30,
  "ip": 0,
  "op": 60,
  "w": 512,
  "h": 512,
  "nm": "Intelligent Business Woman",
  "ddd": 0,
  "assets": [],
  "layers": [
    { "ddd": 0, "ind": 1, "ty": 4, "nm": "Hair", "sr": 1, "ks": { "o": {"a": 0, "k": 100, "ix": 11}, "r": {"a": 0, "k": 0, "ix": 10}, "p": {"a": 0, "k": [256, 200, 0], "ix": 2}, "a": {"a": 0, "k": [0, 0, 0], "ix": 1}, "s": {"a": 0, "k": [100, 100, 100], "ix": 6} }, "ao": 0, "shapes": [{ "ty": "el", "s": {"a": 0, "k": [220, 200], "ix": 2}, "p": {"a": 0, "k": [0, 0], "ix": 3}, "nm": "Ellipse", "hd": false }, { "ty": "fl", "c": {"a": 0, "k": [0.25, 0.2, 0.15, 1], "ix": 4}, "o": {"a": 0, "k": 100, "ix": 5}, "nm": "Fill", "hd": false }, { "ty": "tr", "p": {"a": 0, "k": [0, 0], "ix": 1}, "a": {"a": 0, "k": [0, 0], "ix": 2}, "s": {"a": 0, "k": [100, 100], "ix": 3}, "r": {"a": 0, "k": 0, "ix": 6}, "o": {"a": 0, "k": 100, "ix": 7} }], "ip": 0, "op": 60, "st": 0, "bm": 0 },
    { "ddd": 0, "ind": 2, "ty": 4, "nm": "Face", "sr": 1, "ks": { "o": {"a": 0, "k": 100, "ix": 11}, "r": {"a": 0, "k": 0, "ix": 10}, "p": {"a": 0, "k": [256, 250, 0], "ix": 2}, "a": {"a": 0, "k": [0, 0, 0], "ix": 1}, "s": {"a": 0, "k": [100, 100, 100], "ix": 6} }, "ao": 0, "shapes": [{ "ty": "el", "s": {"a": 0, "k": [180, 200], "ix": 2}, "p": {"a": 0, "k": [0, 0], "ix": 3}, "nm": "Ellipse", "hd": false }, { "ty": "fl", "c": {"a": 0, "k": [0.98, 0.92, 0.88, 1], "ix": 4}, "o": {"a": 0, "k": 100, "ix": 5}, "nm": "Fill", "hd": false }, { "ty": "tr", "p": {"a": 0, "k": [0, 0], "ix": 1}, "a": {"a": 0, "k": [0, 0], "ix": 2}, "s": {"a": 0, "k": [100, 100], "ix": 3}, "r": {"a": 0, "k": 0, "ix": 6}, "o": {"a": 0, "k": 100, "ix": 7} }], "ip": 0, "op": 60, "st": 0, "bm": 0 },
    { "ddd": 0, "ind": 3, "ty": 4, "nm": "Left Eye", "sr": 1, "ks": { "o": {"a": 0, "k": 100, "ix": 11}, "r": {"a": 0, "k": 0, "ix": 10}, "p": {"a": 0, "k": [210, 230, 0], "ix": 2}, "a": {"a": 0, "k": [0, 0, 0], "ix": 1}, "s": {"a": 0, "k": [100, 100, 100], "ix": 6} }, "ao": 0, "shapes": [{ "ty": "el", "s": {"a": 0, "k": [16, 20], "ix": 2}, "p": {"a": 0, "k": [0, 0], "ix": 3}, "nm": "Ellipse", "hd": false }, { "ty": "fl", "c": {"a": 0, "k": [0.15, 0.15, 0.2, 1], "ix": 4}, "o": {"a": 0, "k": 100, "ix": 5}, "nm": "Fill", "hd": false }, { "ty": "tr", "p": {"a": 0, "k": [0, 0], "ix": 1}, "a": {"a": 0, "k": [0, 0], "ix": 2}, "s": {"a": 0, "k": [100, 100], "ix": 3}, "r": {"a": 0, "k": 0, "ix": 6}, "o": {"a": 0, "k": 100, "ix": 7} }], "ip": 0, "op": 60, "st": 0, "bm": 0 },
    { "ddd": 0, "ind": 4, "ty": 4, "nm": "Right Eye", "sr": 1, "ks": { "o": {"a": 0, "k": 100, "ix": 11}, "r": {"a": 0, "k": 0, "ix": 10}, "p": {"a": 0, "k": [302, 230, 0], "ix": 2}, "a": {"a": 0, "k": [0, 0, 0], "ix": 1}, "s": {"a": 0, "k": [100, 100, 100], "ix": 6} }, "ao": 0, "shapes": [{ "ty": "el", "s": {"a": 0, "k": [16, 20], "ix": 2}, "p": {"a": 0, "k": [0, 0], "ix": 3}, "nm": "Ellipse", "hd": false }, { "ty": "fl", "c": {"a": 0, "k": [0.15, 0.15, 0.2, 1], "ix": 4}, "o": {"a": 0, "k": 100, "ix": 5}, "nm": "Fill", "hd": false }, { "ty": "tr", "p": {"a": 0, "k": [0, 0], "ix": 1}, "a": {"a": 0, "k": [0, 0], "ix": 2}, "s": {"a": 0, "k": [100, 100], "ix": 3}, "r": {"a": 0, "k": 0, "ix": 6}, "o": {"a": 0, "k": 100, "ix": 7} }], "ip": 0, "op": 60, "st": 0, "bm": 0 },
    { "ddd": 0, "ind": 5, "ty": 4, "nm": "Smile", "sr": 1, "ks": { "o": {"a": 0, "k": 100, "ix": 11}, "r": {"a": 0, "k": 0, "ix": 10}, "p": {"a": 0, "k": [256, 290, 0], "ix": 2}, "a": {"a": 0, "k": [0, 0, 0], "ix": 1}, "s": {"a": 0, "k": [100, 100, 100], "ix": 6} }, "ao": 0, "shapes": [{ "ty": "rc", "d": 1, "s": {"a": 0, "k": [40, 8], "ix": 2}, "p": {"a": 0, "k": [0, 0], "ix": 3}, "r": {"a": 0, "k": 4, "ix": 4}, "nm": "Rectangle", "hd": false }, { "ty": "fl", "c": {"a": 0, "k": [0.8, 0.3, 0.3, 1], "ix": 4}, "o": {"a": 0, "k": 100, "ix": 5}, "nm": "Fill", "hd": false }, { "ty": "tr", "p": {"a": 0, "k": [0, 0], "ix": 1}, "a": {"a": 0, "k": [0, 0], "ix": 2}, "s": {"a": 0, "k": [100, 100], "ix": 3}, "r": {"a": 0, "k": 0, "ix": 6}, "o": {"a": 0, "k": 100, "ix": 7} }], "ip": 0, "op": 60, "st": 0, "bm": 0 },
    { "ddd": 0, "ind": 6, "ty": 4, "nm": "Blouse", "sr": 1, "ks": { "o": {"a": 0, "k": 100, "ix": 11}, "r": {"a": 0, "k": 0, "ix": 10}, "p": {"a": 0, "k": [256, 380, 0], "ix": 2}, "a": {"a": 0, "k": [0, 0, 0], "ix": 1}, "s": {"a": 0, "k": [100, 100, 100], "ix": 6} }, "ao": 0, "shapes": [{ "ty": "rc", "d": 1, "s": {"a": 0, "k": [200, 120], "ix": 2}, "p": {"a": 0, "k": [0, 0], "ix": 3}, "r": {"a": 0, "k": 20, "ix": 4}, "nm": "Rectangle", "hd": false }, { "ty": "fl", "c": {"a": 0, "k": [0.38, 0.4, 0.94, 1], "ix": 4}, "o": {"a": 0, "k": 100, "ix": 5}, "nm": "Fill", "hd": false }, { "ty": "tr", "p": {"a": 0, "k": [0, 0], "ix": 1}, "a": {"a": 0, "k": [0, 0], "ix": 2}, "s": {"a": 0, "k": [100, 100], "ix": 3}, "r": {"a": 0, "k": 0, "ix": 6}, "o": {"a": 0, "k": 100, "ix": 7} }], "ip": 0, "op": 60, "st": 0, "bm": 0 },
    { "ddd": 0, "ind": 7, "ty": 4, "nm": "Waving Arm", "sr": 1, "ks": { "o": {"a": 0, "k": 100, "ix": 11}, "r": { "a": 1, "k": [{"t": 0, "s": [0], "to": [0], "ti": [0]}, {"t": 10, "s": [-40], "to": [0], "ti": [0]}, {"t": 20, "s": [-10], "to": [0], "ti": [0]}, {"t": 30, "s": [-40], "to": [0], "ti": [0]}, {"t": 40, "s": [-10], "to": [0], "ti": [0]}, {"t": 50, "s": [-40], "to": [0], "ti": [0]}, {"t": 60, "s": [0], "to": [0], "ti": [0]}], "ix": 10 }, "p": {"a": 0, "k": [370, 350, 0], "ix": 2}, "a": {"a": 0, "k": [-60, 0, 0], "ix": 1}, "s": {"a": 0, "k": [100, 100, 100], "ix": 6} }, "ao": 0, "shapes": [{ "ty": "rc", "d": 1, "s": {"a": 0, "k": [120, 22], "ix": 2}, "p": {"a": 0, "k": [0, 0], "ix": 3}, "r": {"a": 0, "k": 11, "ix": 4}, "nm": "Rectangle", "hd": false }, { "ty": "fl", "c": {"a": 0, "k": [0.98, 0.92, 0.88, 1], "ix": 4}, "o": {"a": 0, "k": 100, "ix": 5}, "nm": "Fill", "hd": false }, { "ty": "tr", "p": {"a": 0, "k": [0, 0], "ix": 1}, "a": {"a": 0, "k": [0, 0], "ix": 2}, "s": {"a": 0, "k": [100, 100], "ix": 3}, "r": {"a": 0, "k": 0, "ix": 6}, "o": {"a": 0, "k": 100, "ix": 7} }], "ip": 0, "op": 60, "st": 0, "bm": 0 }
  ],
  "markers": []
}

// 3D AI头像动画
onMounted(() => {
  // 每次进入都显示初始化页面，不加载历史记录
  // loadMessages()

  if (!avatarContainer.value) return

  try {
    avatarAnimation = lottie.loadAnimation({
      container: avatarContainer.value,
      renderer: 'svg',
      loop: true,
      autoplay: true,
      path: '/lottie/Assistant-Bot.json'
    })
  } catch (e) {
    console.error('Lottie init error:', e)
  }
})

onUnmounted(() => {
  if (avatarAnimation) {
    avatarAnimation.destroy()
  }
})

// Icon组件
const TrendIcon = () => h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
  h('path', { d: 'M3 14L8 9L11 12L17 5', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })
])

const QueryIcon = () => h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
  h('circle', { cx: 10, cy: 10, r: 7, stroke: 'currentColor', 'stroke-width': 1.5 }),
  h('path', { d: 'M14 14L18 18', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' })
])

const ChartIcon = () => h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
  h('path', { d: 'M3 17V11M8 17V7M13 17V13M18 17V3', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' })
])

const AlertIcon = () => h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
  h('path', { d: 'M10 2C7.24 2 5 4.24 5 7V9L3 12V13H17V12L15 9V7C15 4.24 12.76 2 10 2Z', stroke: 'currentColor', 'stroke-width': 1.5 }),
  h('path', { d: 'M8 13V14C8 15.1 8.9 16 10 16C11.1 16 12 15.1 12 14V13H8Z', stroke: 'currentColor', 'stroke-width': 1.5 })
])

const modes = [
  { id: 'query', label: '数据查询', icon: QueryIcon },
  { id: 'analyze', label: '趋势分析', icon: TrendIcon },
  { id: 'compare', label: '对比分析', icon: ChartIcon },
  { id: 'alert', label: '异常告警', icon: AlertIcon }
]

const suggestions = [
  { title: '本月各品类销售额', desc: '查看各品类的销售数据排名，了解哪些品类表现最好', icon: QueryIcon, text: '本月各品类销售额是多少？' },
  { title: '近30天用户趋势', desc: '分析用户数的变化趋势，发现增长或下降的规律', icon: TrendIcon, text: '近30天用户数变化趋势' },
  { title: '指标异常检测', desc: '自动发现数据中的异常波动，及时预警问题', icon: AlertIcon, text: '最近有哪些指标出现异常？' },
  { title: '环比数据对比', desc: '对比不同周期的数据差异，评估业务变化', icon: ChartIcon, text: '对比本月与上月数据差异' }
]

async function handleSend() {
  if (!question.value.trim() || loading.value) return

  const userQuestion = question.value.trim()
  question.value = ''

  messages.value.push({
    role: 'user',
    content: userQuestion,
    time: getCurrentTime()
  })

  scrollToBottom()
  loading.value = true

  // Open logic drawer when AI starts processing
  logicDrawerVisible.value = true
  currentThinkingSteps.value = []
  currentSql.value = ''

  // 流式响应数据
  let finalAnswer = ''
  let finalSql = ''
  let finalResultData = []
  let finalMetricName = ''
  let finalMetricNames = []
  let finalSuggest = []
  let finalClarificationOptions = []
  let finalClarificationMessage = ''
  let finalNeedsClarification = false
  let finalThinkingClarificationMessage = ''
  let finalThinkingClarificationOptions = []
  let finalThinkingOriginalQuestion = ''
  let thinkingStepsMap = new Map()

  try {
    const token = localStorage.getItem('token') || ''

    const response = await fetch('/api/v1/llm-ask/v2/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({
        question: userQuestion,
        user_id: 'default',
        session_id: sessionId.value || undefined,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
          continue
        }
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim()
          if (!dataStr) continue

          try {
            const data = JSON.parse(dataStr)

            if (currentEvent === 'step_start') {
              const stepName = data.step
              thinkingStepsMap.set(stepName, {
                step: stepName,
                status: 'in_progress',
                content: '',
                duration: ''
              })
              // 同步更新 + 触发 Vue 重渲染
              currentThinkingSteps.value = Array.from(thinkingStepsMap.values())
              stepsVersion.value++
            } else if (currentEvent === 'step_complete') {
              const stepName = data.step
              const existing = thinkingStepsMap.get(stepName) || { step: stepName }
              thinkingStepsMap.set(stepName, {
                ...existing,
                status: 'completed',
                duration: data.duration_ms ? `${data.duration_ms}ms` : ''
              })
              currentThinkingSteps.value = Array.from(thinkingStepsMap.values())
              stepsVersion.value++
            } else if (currentEvent === 'thinking') {
              const stepName = data.step
              const existing = thinkingStepsMap.get(stepName) || { step: stepName }
              thinkingStepsMap.set(stepName, {
                ...existing,
                content: data.content,
                entities: data.entities || [],
                llm_used: data.llm_used || false,
                source: data.source || null,
                mql: data.mql || null,
                needsClarification: data.needs_clarification || false,
                clarificationMessage: data.clarification_message || '',
                clarificationOptions: data.clarification_options || [],
                originalQuestion: data.original_question || ''
              })
              // 追问信息优先从 thinking 事件获取（泛指维度时流程在 intent_router 就中断了）
              if (data.needs_clarification) {
                finalNeedsClarification = true
                finalThinkingClarificationMessage = data.clarification_message || ''
                finalThinkingClarificationOptions = data.clarification_options || []
                finalThinkingOriginalQuestion = data.original_question || ''
              }
              currentThinkingSteps.value = Array.from(thinkingStepsMap.values())
              stepsVersion.value++
            } else if (currentEvent === 'sql_ready') {
              finalSql = data.sql
              currentSql.value = data.sql
            } else if (currentEvent === 'result_ready') {
              finalResultData = data.result_data || []
              finalMetricName = data.metric_name || ''
              finalMetricNames = data.metric_names || []
            } else if (currentEvent === 'answer_ready') {
              finalAnswer = data.answer
              finalSuggest = data.suggestions || []
              finalClarificationOptions = data.clarification_options || []
              finalClarificationMessage = data.clarification_message || ''
            } else if (currentEvent === 'connected') {
              // 保存 session_id 用于多轮对话
              if (data.session_id) {
                sessionId.value = data.session_id
              }
            } else if (currentEvent === 'done') {
              // 完成
            } else if (currentEvent === 'error') {
              console.error('SSE Error:', data.error)
            }
          } catch (e) {
            // 忽略解析错误
          }
          currentEvent = ''
        }
      }
    }

    const finalSteps = Array.from(thinkingStepsMap.values()).map(s => ({
      step: s.step,
      status: s.status,
      content: s.content,
      duration: s.duration,
      entities: s.entities || [],
      llm_used: s.llm_used || false,
      source: s.source || null,
      mql: s.mql || null
    }))

    // 当有结果数据但没有文字回答时，生成默认回答
    let displayAnswer = finalAnswer
    if (!displayAnswer && finalResultData && finalResultData.length > 0) {
      const firstRow = finalResultData[0]
      const keys = Object.keys(firstRow)
      if (keys.length === 1) {
        const val = firstRow[keys[0]]
        if (!isNaN(parseFloat(val))) {
          const num = parseFloat(val)
          let formatted = num.toLocaleString()
          if (num >= 100000000) formatted = (num / 100000000).toFixed(2) + '亿'
          else if (num >= 10000) formatted = (num / 10000).toFixed(2) + '万'
          displayAnswer = `查询结果：${formatted}`
        }
      }
    }
    // 如果有图表数据，不显示文字回答（只通过图表卡片展示）
    // 追问时优先显示追问消息
    let finalContent = ''
    if (finalNeedsClarification && finalThinkingClarificationMessage) {
      finalContent = finalThinkingClarificationMessage
    } else if (finalResultData && finalResultData.length > 0) {
      finalContent = ''
    } else {
      finalContent = displayAnswer || '抱歉，我没有找到相关数据。'
    }

    // 追问选项优先从 thinking 事件获取（泛指维度时流程在 intent_router 就中断了）
    const effectiveClarificationOptions = finalNeedsClarification && finalThinkingClarificationOptions.length > 0
      ? finalThinkingClarificationOptions
      : finalClarificationOptions
    const effectiveClarificationMessage = finalNeedsClarification && finalThinkingClarificationMessage
      ? finalThinkingClarificationMessage
      : finalClarificationMessage

    messages.value.push({
      role: 'assistant',
      content: finalContent,
      sql: finalSql,
      thinkingSteps: finalSteps,
      resultData: finalResultData,
      metricName: finalMetricName,
      metricNames: finalMetricNames,
      suggest: finalSuggest,
      needsClarification: finalNeedsClarification || effectiveClarificationOptions.length > 0,
      clarificationOptions: effectiveClarificationOptions,
      clarificationMessage: effectiveClarificationMessage,
      originalQuestion: finalThinkingOriginalQuestion,
      time: getCurrentTime()
    })

    expandedThinking.value[messages.value.length - 1] = false

    currentThinkingSteps.value = finalSteps
    stepsVersion.value++
    currentSql.value = finalSql

  } catch (e) {
    console.error('流式请求失败:', e)
    messages.value.push({
      role: 'assistant',
      content: '抱歉，服务出现问题，请稍后再试。',
      time: getCurrentTime()
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function updateThinkingSteps() {
  const newSteps = Array.from(thinkingStepsMap.values()).map(s => ({
    step: s.step,
    status: s.status,
    content: s.content,
    duration: s.duration,
    entities: s.entities || [],
    llm_used: s.llm_used || false
  }))
  currentThinkingSteps.value = newSteps
  await nextTick()
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
  prepareAttributionData({ result_data: msg.resultData })
  attributionVisible.value = true
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

function rateMessage(msg, rating) {
  if (msg.rating === rating) {
    msg.rating = null
  } else {
    msg.rating = rating
  }
}

function selectClarification(option, originalQuestion) {
  // 使用 original_question + replace_key 改写问题
  // 例如：originalQuestion="本月各品类销售额是多少？", option.replace_key="品类", option.value="一级品类"
  // 改写为："本月各一级品类销售额是多少？"
  if (option.replace_key && originalQuestion) {
    const rewritten = originalQuestion.replace(option.replace_key, option.value)
    question.value = rewritten
  } else {
    question.value = option.label
  }
  handleSend()
}

// ClarificationCard 选项处理
function handleClarificationSelect(option) {
  // 选中高亮，前端状态管理
  console.log('Clarification selected:', option)
}

// ClarificationCard 确认处理
function handleClarificationConfirm(option) {
  // 用户确认后，发送选中的选项
  question.value = option.label
  handleSend()
}

// PlanConfirmCard 确认处理
function handlePlanConfirm(plan) {
  // 用户确认方案，开始分析
  loading.value = true
  // 发送确认请求
  llmAskApi.confirmPlan(plan).then(res => {
    // 处理返回结果
    console.log('Plan confirmed:', res)
  }).finally(() => {
    loading.value = false
  })
}

// PlanConfirmCard 修改处理
function handlePlanModify(modifiedPlan) {
  // 用户修改了方案，用新方案重新查询
  loading.value = true
  llmAskApi.modifyPlan(modifiedPlan).then(res => {
    console.log('Plan modified:', res)
  }).finally(() => {
    loading.value = false
  })
}

function selectSuggestion(s) {
  question.value = s
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

function formatMessage(text) {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

function getCurrentTime() {
  const now = new Date()
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

async function copyMessage(msg) {
  try {
    await navigator.clipboard.writeText(msg.content)
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
</script>

<style scoped>
.llm-ask-v2 {
  height: 100vh;
  width: 100%;
  background: linear-gradient(135deg, #F5F3FF 0%, #FBFBFF 50%, #F0F0FF 100%);
  display: flex;
  overflow: hidden;
  position: relative;
  transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 居中大容器 - max-width: 1200px */
.main-container {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  justify-content: center;
  gap: 24px;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  height: calc(100vh - 40px);
  box-sizing: border-box;
  transition: max-width 0.3s ease;
}

/* 结果全屏模式 - 自适应全屏 */
.main-container.fullscreen-result {
  max-width: 100%;
  padding: 16px 24px;
}

/* 统一内容区 */
.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-height: 0;
  overflow: hidden;
}

.llm-ask-v2::after {
  content: '';
  position: fixed;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.08) 0%, transparent 70%);
  bottom: -100px;
  left: -100px;
  pointer-events: none;
  z-index: 0;
}

.chat-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: transparent;
  border-radius: 16px;
  box-shadow: none;
  border: none;
  overflow: hidden;
}

/* 初始化界面 */
.init-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 140px 52px 32px;
  min-height: 100%;
  width: 100%;
  max-width: 2100px;
  margin: 0 auto;
}

/* 聊天界面 */
.chat-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  overflow: hidden;
  max-width: 2470px;
  margin: 0 auto;
}

/* 顶部问候区 */
.greeting-section {
  display: flex;
  flex-direction: row;
  align-items: center;
  margin-bottom: 42px;
  gap: 21px;
  width: 100%;
  max-width: 1400px;
}

.avatar-wrapper {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: #FBFBFF;
  box-shadow: 0 0 26px rgba(99, 102, 241, 0.25), 0 0 52px rgba(99, 102, 241, 0.1);
  animation: avatarFloat 3s ease-in-out infinite;
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
}

.avatar-wrapper svg {
  width: 84px;
  height: 84px;
}

@keyframes avatarFloat {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-6px) scale(1.02); }
}

.welcome-text {
  font-size: 26px;
  font-weight: 600;
  background: linear-gradient(90deg, #5959FF, #8D7BFF);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-align: center;
  margin: 0;
}

/* 快捷功能胶囊栏 */
.mode-tabs {
  display: flex;
  gap: 16px;
  justify-content: flex-start;
  margin-bottom: 32px;
  width: 100%;
  max-width: 1400px;
}

.mode-tab {
  height: 42px;
  padding: 0 21px;
  background: transparent;
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 21px;
  font-size: 18px;
  color: #333333;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.08);
  transition: all 0.2s ease;
}

.mode-tab:hover {
  border-color: #5959FF;
  color: #5959FF;
}

.mode-tab.active {
  background: linear-gradient(135deg, #5959FF 0%, #8D7BFF 100%);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(89, 89, 255, 0.3);
}

.mode-tab svg {
  width: 16px;
  height: 16px;
}

/* 主输入框区域 - 初始化界面 */
.init-input-section {
  width: 100%;
  max-width: 1400px;
  margin-bottom: 32px;
}

.init-input-section .chat-input-wrapper {
  display: flex;
  align-items: flex-end;
  background: #FFFFFF;
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 21px;
  padding: 18px 24px;
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.08);
  transition: all 0.2s ease;
  min-height: 104px;
}

.init-input-section .chat-input-wrapper:focus-within {
  border-color: #5959FF;
  box-shadow: 0 4px 24px rgba(89, 89, 255, 0.2);
}

.init-input-section .chat-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 21px;
  line-height: 1.5;
  resize: none;
  background: transparent;
  color: #1f1f1f;
  min-height: 78px;
}

.init-input-section .chat-input::placeholder {
  color: #BFBFBF;
}

.init-input-section .send-btn {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #5959FF 0%, #8D7BFF 100%);
  border: none;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-left: 16px;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(89, 89, 255, 0.3);
}

.init-input-section .send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 6px 16px rgba(89, 89, 255, 0.4);
}

.init-input-section .send-btn:disabled {
  background: #F0F0F0;
  cursor: not-allowed;
  box-shadow: none;
}

.init-input-section .send-btn svg {
  width: 18px;
  height: 18px;
}

/* 底部工具栏 */
.input-tools-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 32px;
  padding: 4px 0;
}

.tool-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: #8C8C8C;
  cursor: pointer;
}

.tool-icon:hover {
  color: #5959FF;
}

.tool-hint {
  font-size: 14px;
  color: #8C8C8C;
  margin-left: auto;
}

/* 消息区域 */
.messages-container {
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow-y: auto;
  padding: 26px 21px;
  scroll-behavior: smooth;
  display: flex;
  flex-direction: column;
}

/* 初始化容器 - 已废弃，使用 .init-view */
.init-container {
  display: none;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-bottom: 20px;
}

.message-item {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  animation: messageSlideIn 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  padding-top: 0;
}

.message-item.user {
  flex-direction: row-reverse;
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  position: absolute;
  top: -31px;
  left: 0;
  width: 62px;
  height: 62px;
  border-radius: 21px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid rgba(99, 102, 241, 0.1);
  z-index: 1;
}

.message-item.user .message-avatar {
  left: auto;
  right: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0.1) 100%);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.message-content {
  max-width: 75%;
  min-width: 234px;
  background: #fff;
  border-radius: 40px;
  padding: 20px 28px;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.06), 0 1px 4px rgba(99, 102, 241, 0.03);
  border: 1px solid rgba(99, 102, 241, 0.06);
  position: relative;
  transition: all 0.2s ease;
}

.message-content:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.08), 0 2px 4px rgba(99, 102, 241, 0.04);
}

/* AI消息气泡宽度撑满 */
.message-item.assistant .message-content {
  max-width: 100%;
  width: 100%;
  flex: 1;
}

/* AI消息气泡小三角 */
.message-item.assistant .message-content::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 16px;
  width: 0;
  height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-right: 10px solid #fff;
  filter: drop-shadow(-2px 0 2px rgba(99, 102, 241, 0.04));
}

.message-item.user .message-content {
  background: linear-gradient(135deg, #6366F1 0%, #7C3AED 100%);
  color: #fff;
  border: none;
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.3), 0 2px 4px rgba(99, 102, 241, 0.15);
  padding: 10px 16px;
}

/* 用户消息气泡小三角 */
.message-item.user .message-content::before {
  content: '';
  position: absolute;
  right: -8px;
  top: 16px;
  width: 0;
  height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-left: 10px solid #6366F1;
}

.message-text {
  font-size: 14px;
  line-height: 1.7;
  color: #2d3748;
}

.message-item.user .message-text {
  color: #fff;
}

.message-time {
  font-size: 10px;
  color: #c0c4cc;
  margin-top: 6px;
  text-align: right;
}

.message-item.user .message-time {
  color: rgba(255, 255, 255, 0.6);
}

/* 发送状态 */
.message-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
  justify-content: flex-end;
}

.message-status.sending {
  color: rgba(255, 255, 255, 0.5);
}

.message-status.error {
  color: #F87171;
}

/* 加载中的消息气泡 */
.message-content.loading {
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6366F1;
  animation: dotBounce 1.4s ease-in-out infinite;
}

.loading-dots span:nth-child(1) { animation-delay: 0s; }
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotBounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 消息操作按钮 */
.message-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-content:hover .message-actions {
  opacity: 1;
}

.action-btn {
  padding: 4px 10px;
  font-size: 11px;
  color: #9ca3af;
  background: rgba(99, 102, 241, 0.06);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-btn:hover {
  background: rgba(99, 102, 241, 0.12);
  color: #6366F1;
}

.message-item.user .action-btn {
  background: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.8);
}

.message-item.user .action-btn:hover {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.action-btn.active {
  background: rgba(99, 102, 241, 0.15);
  color: #6366F1;
}

/* 异常标注 */
.anomaly-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.anomaly-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #FEF3C7;
  border-radius: 8px;
  font-size: 12px;
  color: #92400E;
}

/* 泛指追问 */
.clarification-tags {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.clarification-msg {
  font-size: 12px;
  color: #6b7280;
}

.clarification-tag {
  padding: 6px 14px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 20px;
  font-size: 12px;
  color: #6366F1;
  cursor: pointer;
  transition: all 0.2s;
}

.clarification-tag:hover {
  background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
  color: #fff;
  border-color: transparent;
}

/* 消息数据解读 */
.message-interpretation {
  margin-top: 10px;
  padding: 10px 14px;
  background: #F8FAFF;
  border: 1px solid #E0E7FF;
  border-radius: 8px;
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}

/* SQL块 */
.sql-block {
  margin-top: 10px;
  background: #1f1f1f;
  border-radius: 10px;
  overflow: hidden;
}

.sql-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #2d2d2d;
  font-size: 11px;
  color: #9ca3af;
}

.sql-content {
  padding: 12px;
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: #a5d6ff;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

/* 思考过程 */
.thinking-panel {
  margin-top: 10px;
  background: rgba(99, 102, 241, 0.04);
  border-radius: 10px;
  overflow: hidden;
}

.thinking-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: transparent;
  border: none;
  font-size: 12px;
  color: #6366F1;
  cursor: pointer;
  transition: all 0.2s;
}

.thinking-toggle:hover {
  background: rgba(99, 102, 241, 0.08);
}

.toggle-icon {
  margin-left: auto;
  transition: transform 0.2s;
}

.toggle-icon.expanded {
  transform: rotate(180deg);
}

.thinking-steps {
  padding: 8px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.thinking-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.step-name {
  color: #6b7280;
  font-family: 'Monaco', 'Menlo', monospace;
}

.step-status {
  font-size: 10px;
}

.status-icon.completed { color: #6366F1; }
.status-icon.failed { color: #EF4444; }
.status-icon.pending { color: #F59E0B; }

.step-duration {
  color: #9ca3af;
  margin-left: auto;
}

.llm-badge {
  padding: 2px 6px;
  background: rgba(99, 102, 241, 0.1);
  border-radius: 4px;
  font-size: 9px;
  color: #6366F1;
  font-weight: 600;
}

/* 建议问题 */
.suggest-list {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.suggest-label {
  font-size: 12px;
  color: #9ca3af;
}

.suggest-btn {
  padding: 6px 14px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(139, 92, 246, 0.08) 100%);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 20px;
  font-size: 12px;
  color: #6366F1;
  cursor: pointer;
  transition: all 0.2s;
}

.suggest-btn:hover {
  background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
  color: #fff;
  border-color: transparent;
}

/* 图表卡片 */
.message-chart {
  margin-top: 12px;
  width: 100%;
  flex: 1;
}

/* 一键归因按钮 */
.attribution-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  margin-right: 8px;
  padding: 8px 14px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #6366F1;
  cursor: pointer;
  transition: all 0.2s;
}

.attribution-btn:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(99, 102, 241, 0.08) 100%);
  border-color: rgba(99, 102, 241, 0.25);
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(99, 102, 241, 0.1);
}

/* 生成报告按钮 */
.report-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 14px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(99, 102, 241, 0.05) 100%);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #6366F1;
  cursor: pointer;
  transition: all 0.2s;
}

.report-btn:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(99, 102, 241, 0.08) 100%);
  border-color: rgba(99, 102, 241, 0.25);
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(99, 102, 241, 0.08);
}

/* 输入框区域 */
.input-section {
  width: 100%;
  padding: 16px 21px 21px;
  background: transparent;
  flex-shrink: 0;
}

.chat-input-wrapper {
  display: flex;
  align-items: flex-end;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  border-radius: 31px;
  padding: 18px 24px;
  box-shadow: 0 8px 32px rgba(99, 102, 241, 0.1), 0 4px 16px rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.5);
  transition: all 0.2s ease;
  min-height: 104px;
}

.chat-input-wrapper:focus-within {
  box-shadow: 0 12px 40px rgba(99, 102, 241, 0.1), 0 6px 20px rgba(99, 102, 241, 0.05), 0 0 0 1.5px rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.1);
}

.input-tools {
  display: flex;
  gap: 14px;
  margin-right: 16px;
  padding-bottom: 8px;
}

.tool-icon {
  color: #9ca3af;
  cursor: pointer;
  transition: color 0.2s;
}

.tool-icon:hover {
  color: #6366F1;
}

.chat-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 21px;
  line-height: 1.6;
  resize: none;
  background: transparent;
  color: #1f1f1f;
  min-height: 52px;
}

.chat-input::placeholder {
  color: #9ca3af;
}

.send-btn {
  width: 57px;
  height: 57px;
  border-radius: 18px;
  background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
  border: none;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-left: 18px;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.4);
}

.send-btn svg {
  width: 22px;
  height: 22px;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.loading-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 快捷提问标题 */
.suggestions-title {
  font-size: 20px;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 16px;
  text-align: left;
}

/* 快捷提问卡片 */
.suggestions-section {
  width: 100%;
  max-width: 1400px;
}

.suggestions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 21px;
  width: 100%;
}

.suggestion-card {
  background: transparent;
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 16px;
  padding: 18px;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 94px;
}

.suggestion-card:hover {
  background: transparent;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  border-color: #5959FF;
}

.card-icon {
  width: 52px;
  height: 52px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(89, 89, 255, 0.1) 0%, rgba(141, 123, 255, 0.1) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5959FF;
  flex-shrink: 0;
}

.card-icon svg {
  width: 26px;
  height: 26px;
}

.card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-content h4 {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-content h4 .slash-icon {
  color: #5959FF;
  font-weight: 700;
}

.card-content p {
  font-size: 14px;
  color: #8C8C8C;
  margin: 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
