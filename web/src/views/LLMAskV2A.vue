<template>
  <div class="llm-ask-v2" :class="{ 'drawer-open': logicDrawerVisible }">
    <!-- 会话历史悬浮面板 -->
    <SessionHistory
      ref="sessionHistoryRef"
      @select-session="handleSelectSession"
      @new-session="handleNewSessionFromHistory"
    />

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
              <div class="avatar-wrapper">
                <svg width="68" height="68" viewBox="0 0 68 68" fill="none" aria-hidden="true">
                  <rect x="8" y="8" width="52" height="52" rx="18" fill="#0F172A"/>
                  <path d="M22 42V30M34 46V22M46 38V26" stroke="#F8FAFC" stroke-width="5" stroke-linecap="round"/>
                </svg>
              </div>
              <h1 class="welcome-text">{{ greetingText }}，把问题直接抛给我，我先给你结论，再补证据和下一步。</h1>
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
                  ref="inputRef"
                  v-model="question"
                  class="chat-input"
                  placeholder="直接向我提问，输入/唤起快捷提示词"
                  rows="1"
                  @keydown.enter.exact.prevent="handleEnterKey"
                  @keydown.up.prevent="navigateCommand(-1)"
                  @keydown.down.prevent="navigateCommand(1)"
                  @keydown.esc="closeCommandPanel"
                ></textarea>
                <button class="send-btn" :disabled="!question.trim() || loading" @click="handleSend">
                  <svg v-if="!loading" width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M18 10L2 2L10 10M18 10L10 18M18 10L2 10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none" class="loading-spinner">
                    <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="50" stroke-dashoffset="12" stroke-linecap="round"/>
                  </svg>
                </button>

                <!-- / 快捷命令面板 -->
                <div v-if="showCommandPanel && suggestions.length" class="command-panel">
                  <div class="command-header">
                    <span>快捷命令</span>
                    <span class="command-hint">↑↓ 导航 Enter 选择 Esc 关闭</span>
                  </div>
                  <div
                    v-for="(cmd, idx) in suggestions"
                    :key="cmd.title"
                    :class="['command-item', { selected: idx === commandSelectedIndex }]"
                    @click="selectCommand(cmd)"
                  >
                    <span class="command-icon">
                      <component :is="cmd.icon" />
                    </span>
                    <div class="command-content">
                      <span class="command-title"><span class="slash">/</span>{{ cmd.title }}</span>
                      <span class="command-desc">{{ cmd.desc }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="input-tools-bar">
                <span class="tool-label">支持直接提问，也可以用下面的起手问题。</span>
                <span class="tool-icon" aria-hidden="true">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M3 10H17M10 3L17 10L10 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
                <span class="tool-icon" aria-hidden="true">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <rect x="2" y="4" width="16" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M6 8L10 12L14 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                </span>
                <span class="tool-hint">输入 / 打开快捷词</span>
              </div>
            </div>

            <!-- 快捷提问卡片 -->
            <div class="suggestions-section">
              <div class="suggestions-title">你可以这样开场</div>
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
                <ModernAskMessage
                  v-for="(msg, idx) in messages"
                  :key="`modern-${msg.role}-${idx}-${msg.time || msg.created_at || ''}`"
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
                <div
                  v-if="false"
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
                    <div v-if="msg.mql?.time?.start" class="message-date-range">
                      {{ formatDateRange(msg.mql.time.start, msg.mql.time.end) }}
                    </div>
                    <div v-if="msg.loading" class="loading-dots">
                      <span></span><span></span><span></span>
                    </div>
                    <template v-else>
                      <div class="message-text" v-html="formatMessage(msg.content)"></div>
                      <div class="message-time">{{ formatTime(msg.time) }}</div>
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
                    <div v-if="msg.needsClarification && msg.clarificationOptions && !isSlotMissingOptions(msg.clarificationOptions)" class="clarification-tags">
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
                      :columns="msg.columns || []"
                      :height="260"
                      :interpretation="msg.interpretation"
                      :truncation-length="12"
                      :metric-name="msg.metricName || ''"
                      :metric-names="msg.metricNames || []"
                      :time-start="msg.mql?.time?.start"
                      :time-end="msg.mql?.time?.end"
                      class="message-chart"
                    />

                    <!-- 多指标分析报告 - 紧凑卡片样式 -->
                    <div v-if="msg.analysis" class="chat-report-card" :class="'theme-' + msg.category">
                      <div class="report-header">
                        <div class="header-main">
                          <el-icon class="header-icon"><DataLine /></el-icon>
                          <span class="summary-text">{{ msg.analysis.summary }}</span>
                        </div>
                        <div class="health-badge" :class="getHealthClass(msg.analysis.health_score)">
                          {{ msg.analysis.health_score }}分
                        </div>
                      </div>

                      <div v-if="msg.analysis.top_urgent_action" class="urgent-banner">
                        <el-icon><WarningFilled /></el-icon>
                        <span>{{ msg.analysis.top_urgent_action }}</span>
                      </div>

                      <div class="report-body">
                        <div v-if="msg.analysis.issues?.length" class="section issues-section">
                          <div class="section-title text-red">需关注异常</div>
                          <div v-for="(issue, idx) in msg.analysis.issues" :key="idx" class="data-item">
                            <div class="item-header">
                              <span class="tag" :class="issue.priority">{{ issue.priority }}</span>
                              <span class="metric">{{ issue.metric }}</span>
                              <span class="value text-red">{{ issue.conclusion }}</span>
                            </div>
                            <div class="item-reason">{{ issue.reason }}</div>
                          </div>
                        </div>

                        <div v-if="msg.analysis.highlights?.length" class="section highlights-section">
                          <div class="section-title text-green">业务亮点</div>
                          <div v-for="(hl, idx) in msg.analysis.highlights" :key="idx" class="data-item">
                            <div class="item-header">
                              <span class="metric">{{ hl.metric }}</span>
                              <span class="value text-green">{{ hl.conclusion }}</span>
                            </div>
                            <div class="item-reason">{{ hl.reason }}</div>
                          </div>
                        </div>
                      </div>

                      <div v-if="msg.analysis.action_items?.length" class="action-section">
                        <div class="action-title">行动建议</div>
                        <ul class="action-list">
                          <li v-for="(action, idx) in msg.analysis.action_items" :key="idx">
                            <span class="bullet" :class="{ 'is-urgent': action.type === 'urgent' }"></span>
                            {{ action.text }}
                          </li>
                        </ul>
                      </div>
                    </div>

                    <!-- 思考过程（默认隐藏） -->
                    <div v-if="false && msg.thinkingSteps && msg.thinkingSteps.length > 0" class="thinking-panel">
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
                          <span v-if="step.content" class="step-content">{{ step.content }}</span>
                        </div>
                      </div>
                    </div>

                    <!-- 建议问题 -->
                    <div v-if="msg.suggest && msg.suggest.length > 0" class="suggest-row">
                      <span class="suggest-label">为你推荐</span>
                      <div class="suggest-items">
                        <button
                          v-for="s in msg.suggest"
                          :key="s"
                          class="suggest-item"
                          @click="selectSuggestion(s)"
                        >
                          {{ s }}
                        </button>
                      </div>
                    </div>

                    <!-- 决策分析 - 仅当有有效 category 时显示（由 trigger_analyzer 设置） -->
                    <div v-if="msg.role === 'assistant' && msg.resultData && msg.resultData.length > 0 && msg.category" class="analysis-drilldown">
                      <div class="drilldown-title">决策分析</div>
                      <div class="drilldown-list">
                        <button class="drilldown-btn" @click="handleDrilldown({ check: 'sales' })">📊 看销售</button>
                        <button class="drilldown-btn" @click="handleDrilldown({ check: 'ad' })">📢 看广告</button>
                        <button class="drilldown-btn" @click="handleDrilldown({ check: 'inventory' })">📦 看库存</button>
                        <button class="drilldown-btn" @click="handleDrilldown({ check: 'profit' })">💰 看利润</button>
                      </div>
                    </div>

                    <!-- 波动分析按钮（默认隐藏，对比问题自动触发） -->
                    <button
                      v-if="false && msg.resultData && msg.resultData.length > 0 && canDoVolatilityAnalysis(msg.resultData)"
                      class="attribution-btn"
                      @click="openAttribution(msg)"
                    >
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M3 14L7 9L10 12L17 5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                      波动分析
                    </button>

                    <!-- 生成报告按钮 -->
                    <button
                      v-if="false"
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
                placeholder="直接向我提问，输入/唤起快捷提示词"
                rows="2"
                @keydown.enter.exact.prevent="handleEnterKey"
                @keydown.up.prevent="navigateCommand(-1)"
                @keydown.down.prevent="navigateCommand(1)"
                @keydown.esc="closeCommandPanel"
              ></textarea>
              <button class="send-btn" :disabled="!question.trim() || loading" @click="handleSend">
                <svg v-if="!loading" width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M18 10L2 2L10 10M18 10L10 18M18 10L2 10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none" class="loading-spinner">
                  <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="50" stroke-dashoffset="12" stroke-linecap="round"/>
                </svg>
              </button>

              <!-- / 快捷命令面板 -->
              <div v-if="showCommandPanel && suggestions.length" class="command-panel">
                <div class="command-header">
                  <span>快捷命令</span>
                  <span class="command-hint">↑↓ 导航 Enter 选择 Esc 关闭</span>
                </div>
                <div
                  v-for="(cmd, idx) in suggestions"
                  :key="cmd.title"
                  :class="['command-item', { selected: idx === commandSelectedIndex }]"
                  @click="selectCommand(cmd)"
                >
                  <span class="command-icon">
                    <component :is="cmd.icon" />
                  </span>
                  <div class="command-content">
                    <span class="command-title"><span class="slash">/</span>{{ cmd.title }}</span>
                    <span class="command-desc">{{ cmd.desc }}</span>
                  </div>
                </div>
              </div>
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

    <!-- 波动分析面板 -->
    <VolatilityPanel
      ref="volatilityPanelRef"
      v-model="attributionVisible"
      :metric-name="currentMetricName"
      :api-url="volatilityApiUrl"
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
import SessionHistory from '../components/ask/SessionHistory.vue'
import ModernAskMessage from '../components/ask/ModernAskMessage.vue'

const router = useRouter()
const $route = useRoute()
const question = ref('')

// 下钻类型 → 中文标签（用于用户消息显示）
const DRILLDOWN_LABELS = {
  sales: '销售经营分析',
  ad: '广告投放分析',
  inventory: '库存供应链分析',
  cost: '成本毛利分析',
}
const activeMode = ref('query')
const messages = ref([])
const loading = ref(false)

// Session ID for multi-turn conversation
const sessionId = ref('')

// Expanded states
const expandedThinking = ref({})
const expandedInterpretation = ref({})

// / 命令面板
const showCommandPanel = ref(false)
const commandSelectedIndex = ref(0)

// SSE AbortController，用于取消正在进行的请求
let abortController = null

// 对话状态持久化到 localStorage
const STORAGE_KEY = 'llm_ask_state'
const resetState = () => {
  // 取消正在进行的 SSE 请求
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  // 点击导航时重置状态，显示初始化页面
  messages.value = []
  sessionId.value = ''
  expandedThinking.value = {}
  expandedInterpretation.value = {}
}

// 从会话历史选择会话
async function handleSelectSession(session) {
  try {
    // 加载该会话的消息
    const res = await llmAskApi.getHistory(session.session_id)
    console.log('[handleSelectSession] res:', res)
    console.log('[handleSelectSession] res.code:', res.code)
    console.log('[handleSelectSession] res.data:', res.data)
    if (res.code === 0 && res.data) {
      const transformedMessages = (res.data.messages || []).map(decodeStoredAskMessage)
      messages.value = transformedMessages
      sessionId.value = session.session_id
      expandedThinking.value = {}
      expandedInterpretation.value = {}
      // Debug: 查看恢复的消息数据
      const assistantMsg = transformedMessages.find(m => m.role === 'assistant')
      if (assistantMsg) {
        console.log('[handleSelectSession] 恢复的消息:', JSON.stringify({
          role: assistantMsg.role,
          resultData: assistantMsg.resultData,
          metricName: assistantMsg.metricName,
          columns: assistantMsg.columns,
        }).slice(0, 500))
      }
    }
  } catch (e) {
    console.error('加载会话失败:', e)
  }
}

// 从会话历史新建会话
function handleNewSessionFromHistory() {
  resetState()
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
// 监听所有状态变化自动保存
watch(messages, saveState, { deep: true })
watch(sessionId, saveState)
watch(expandedThinking, saveState, { deep: true })
watch(expandedInterpretation, saveState, { deep: true })

// 检测 / 触发命令面板
watch(question, (val) => {
  if (val === '/') {
    showCommandPanel.value = true
    commandSelectedIndex.value = 0
  } else if (!val.startsWith('/')) {
    showCommandPanel.value = false
  }
})

// 路由变化时重置状态（从其他页面切换回来时）
watch(() => $route.path, (path) => {
  if (path === '/llm-ask-v2') {
    resetState()
  }
})

// 是否有消息，用于全屏自适应
const hasResult = computed(() => messages.value.length > 0)
const messagesContainer = ref(null)
const sessionHistoryRef = ref(null)

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

// Volatility analysis
const volatilityPanelRef = ref(null)
const currentMetricName = ref('')
const volatilityApiUrl = '/api/v1/llm-ask/v2/volatility/stream'
let pendingAutoVolatilityQuestion = ''  // 暂存当前问题，判断是否自动触发波动分析

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
onMounted(async () => {
  // 获取初始快捷提问
  await fetchInitialSuggestions()

  // 每次进入页面都显示初始化界面
  // 新建会话或从历史会话选择时由相应函数处理
  resetState()

  // 如果有 sessionId，清除它（回到初始化）
  sessionId.value = ''
  console.log('[LLMAskV2A] after mount, messages count:', messages.value.length, 'sessionId:', sessionId.value)

  // 滚动到底部展示最新消息
  scrollToBottom()
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
  { id: 'query', label: '销售分析', icon: QueryIcon },
  // { id: 'analyze', label: '趋势分析', icon: TrendIcon },
  // { id: 'compare', label: '对比分析', icon: ChartIcon },
  // { id: 'alert', label: '异常告警', icon: AlertIcon }
]

const suggestions = ref([])

// Icon 映射
const iconMap = {
  QueryIcon,
  TrendIcon,
  ChartIcon,
  AlertIcon
}

// 获取初始快捷提问
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
    // 使用默认值
    suggestions.value = [
      { title: '看品类对比', desc: '先看本月各品类规模，再决定要不要继续下钻。', icon: QueryIcon, text: '本月各品类销售额对比一下' },
      { title: '看近期变化', desc: '用趋势先判断最近 30 天有没有明显拐点。', icon: TrendIcon, text: '近30天用户数变化趋势怎么样' },
      { title: '找异常波动', desc: '先把异常指标挑出来，再解释为什么变动。', icon: AlertIcon, text: '最近有哪些指标出现异常' },
      { title: '做环比对比', desc: '先给我本月和上月的关键差异，再看细分。', icon: ChartIcon, text: '对比本月与上月数据差异' }
    ]
  }
}

// 处理回车键
function handleEnterKey() {
  // 如果命令面板打开，选择当前命令
  if (showCommandPanel.value && suggestions.value.length > 0) {
    const cmd = suggestions.value[commandSelectedIndex.value]
    if (cmd) {
      selectCommand(cmd)
    }
    return
  }
  // 否则发送消息
  handleSend()
}

async function handleSend() {
  if (!question.value.trim() || loading.value) return

  const userQuestion = question.value.trim()
  question.value = ''
  pendingAutoVolatilityQuestion = userQuestion  // 暂存，支持自动触发波动分析

  // 将 __DRILLDOWN__:xxx__ 格式映射为中文显示（API 请求体仍用原始格式）
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

  // 分析过程默认折叠，先在主消息流里给轻量处理中反馈
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
        sessionHistoryRef.value?.refreshSessions?.()
      }
    },
    onError: (error) => {
      console.error('SSE Error:', error)
    },
  })

  try {
    // 取消之前的请求
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

    // 自动触发波动分析：追问"为什么"类问题且数据适合做波动分析时
    // answer_ready 之后 mom/yoy 才有正确值，所以延迟到 nextTick 再判断
    await nextTick()
    const latestMsg = messages.value[messages.value.length - 1]
    const latestResultData = streamAccumulator.getFinalResultData()
    if (latestMsg && latestResultData && latestResultData.length > 0) {
      const q = pendingAutoVolatilityQuestion || ''
      const isComparisonQuestion = /为什么|为啥|为什么.比|为啥.比|哪个.高|哪个.低|对比|比较|差异/.test(q)
      if (isComparisonQuestion && canDoVolatilityAnalysis(latestResultData)) {
        // 如果 mom/yoy 为空，尝试从 analysis.kpi 取值
        if (!latestMsg.momChange && latestMsg.analysis?.kpi?.mom != null) {
          latestMsg.momChange = latestMsg.analysis.kpi.mom / 100  // trigger_analyzer 返回的是百分比值如 -100.0，需转小数
        }
        if (!latestMsg.yoyChange && latestMsg.analysis?.kpi?.yoy != null) {
          latestMsg.yoyChange = latestMsg.analysis.kpi.yoy / 100
        }
        // 如果 timeRange 为空，从最终的 thinking steps 里取最新的 MQL time
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

/**
 * 判断数据是否适合做波动分析
 * 适合：多行数据（时间序列或多品类）或包含维度列
 * 不适合：单行汇总数据（如"本月销售额"只有一行）
 */
function canDoVolatilityAnalysis(resultData) {
  if (!resultData || resultData.length === 0) return false

  const firstRow = resultData[0]
  if (!firstRow) return false

  const keys = Object.keys(firstRow)

  // 单行比较数据（有"当前值"和"环比值"）适合做波动分析
  const isComparisonRow = keys.includes('当前值') && keys.includes('环比值')
  if (isComparisonRow) return true

  // 单行数据不适合
  if (resultData.length === 1) return false

  // 检查是否有维度列（GROUP_X 或其他维度列）
  const hasDimensionColumn = keys.some(k =>
    /^GROUP_\d$/i.test(k) ||
    /^(dimension|channel|site|品类|品牌|平台|category)$/i.test(k)
  )

  // 多行数据或有维度列的数据适合做波动分析
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
  // Deep copy to avoid reactive proxy issues
  let resultDataCopy = JSON.parse(JSON.stringify(msg.resultData || []))
  let timeRange = msg.timeRange ? { start: msg.timeRange.start, end: msg.timeRange.end } : null

  // 如果是比较结果（单行含"当前值"和"环比值"），转换成两行时间序列格式
  if (resultDataCopy.length === 1) {
    const row = resultDataCopy[0]
    const hasCurrent = '当前值' in row
    const hasPrev = '环比值' in row
    if (hasCurrent && hasPrev) {
      const currentVal = parseFloat(row['当前值']) || 0
      const prevVal = parseFloat(row['环比值']) || 0
      // 从 timeRange 解析出当期和上期月份
      let currentDate = ''
      let prevDate = ''
      if (timeRange && timeRange.start) {
        currentDate = timeRange.start // 如 2026-03-01
        // 上期往前推一个月
        const d = new Date(timeRange.start)
        d.setMonth(d.getMonth() - 1)
        prevDate = d.toISOString().slice(0, 10) // 如 2026-02-01
      }
      resultDataCopy = [
        { date: currentDate, value: currentVal },
        { date: prevDate, value: prevVal }
      ]
      // 用比较值计算 mom（不再让 volatility 重新算）
      const momFromMsg = msg.momChange ?? (prevVal !== 0 ? (currentVal - prevVal) / prevVal : null)
      const yoyFromMsg = msg.yoyChange ?? null
      // 更新 timeRange 为包含两个月的范围（回写到 msg，保证 volatility 收到正确的时间范围）
      if (prevDate && currentDate) {
        timeRange = { start: prevDate, end: currentDate }
        msg.timeRange = timeRange
      }
      msg.momChange = momFromMsg
      msg.yoyChange = yoyFromMsg
    }
  }

  // 设置当前指标名称
  currentMetricName.value = msg.metricName || '指标'
  // 准备数据并打开面板
  prepareAttributionData({ result_data: resultDataCopy })
  attributionVisible.value = true
  // 启动波动分析流
  if (volatilityPanelRef.value && resultDataCopy.length > 0) {
    volatilityPanelRef.value.startStream({
      metric_name: msg.metricName || '指标',
      data: resultDataCopy,
      dimension_key: 'dimension',
      mom_change: msg.momChange ?? null,
      yoy_change: msg.yoyChange ?? null,
      starrocks_sql: msg.starrocksSql ?? null,
      // 只传 column 和 value，过滤掉 level 等 MQL 内部字段
      dimension_filters: (msg.dimensionFilters || []).map(d => ({
        column: d.column || d.type || '',
        value: d.value || ''
      })),
      // 传 MQL time range（start/end）用于计算正确的 MoM/YoY
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
  // 切换本地状态
  if (msg.rating === rating) {
    msg.rating = null
  } else {
    msg.rating = rating
  }
  // 调用后端 API 保存反馈
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

// 快速下钻处理
function handleDrilldown(option) {
  if (!option || !option.check) return
  // 构建下钻问题
  let q = ''
  if (option.check === 'sales') {
    q = '__DRILLDOWN__:sales__'
  } else if (option.check === 'ad') {
    q = '__DRILLDOWN__:ad__'
  } else if (option.check === 'inventory' || option.check === 'supply') {
    q = '__DRILLDOWN__:inventory__'
  } else if (option.check === 'profit' || option.check === 'cost') {
    q = '__DRILLDOWN__:cost__'
  }
  if (q) {
    question.value = q
    handleSend()
  }
}

// / 命令面板导航
function navigateCommand(dir) {
  if (!showCommandPanel.value || !suggestions.value.length) return
  const len = suggestions.value.length
  commandSelectedIndex.value = (commandSelectedIndex.value + dir + len) % len
}

// 选择命令
function selectCommand(cmd) {
  question.value = cmd.text
  showCommandPanel.value = false
  handleSend()
}

// 关闭命令面板
function closeCommandPanel() {
  showCommandPanel.value = false
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

// 判断是否是槽位缺失选项（不是品类级别选项）
function isSlotMissingOptions(options) {
  if (!options || !Array.isArray(options) || options.length === 0) return false
  // 品类级别选项有一二三级等关键词，不属于槽位缺失
  const categoryKeywords = ['一级', '二级', '三级', '四级', '品类', '类目']
  const isCategoryLevel = options.every(opt => {
    const label = opt.label || opt.value || String(opt)
    return categoryKeywords.some(kw => String(label).includes(kw))
  })
  if (isCategoryLevel) return false
  // 槽位选项通常是简单字符串或对象，选项较少
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
  if (s && e && s !== e) {
    return `${s} ~ ${e}`
  }
  return s
}

function getCurrentTime() {
  const now = new Date()
  return now.toISOString()
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
    // 优先复制图表数据（resultData）
    if (msg.resultData && msg.resultData.length > 0) {
      const keys = Object.keys(msg.resultData[0])
      // 转为 CSV 格式
      const header = keys.join('\t')
      const rows = msg.resultData.map(row =>
        keys.map(k => row[k] ?? '').join('\t')
      )
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

    // 其次复制 SQL
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

    // 最后复制纯文本
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
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid rgba(99, 102, 241, 0.1);
  align-self: flex-start;
  margin-top: 4px;
}

.message-item.user .message-avatar {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0.1) 100%);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.message-content {
  max-width: 75%;
  min-width: 200px;
  background: #fff;
  border-radius: 40px;
  padding: 20px 28px;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.06), 0 1px 4px rgba(99, 102, 241, 0.03);
  border: 1px solid rgba(99, 102, 241, 0.06);
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
  display: none;
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
  display: none;
}

.message-text {
  font-size: 14px;
  line-height: 1.7;
  color: #2d3748;
}

.message-item.user .message-text {
  color: #fff;
}

.message-date-range {
  font-size: 11px;
  color: #909399;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px dashed #ebeef5;
}

.message-item.user .message-date-range {
  color: rgba(255, 255, 255, 0.7);
  border-bottom-color: rgba(255, 255, 255, 0.2);
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
  padding: 8px 16px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  color: #6366F1;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.clarification-tag:hover {
  background: #6366F1;
  color: #fff;
  border-color: #6366F1;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
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

.step-content {
  color: #374151;
  font-size: 11px;
  margin-left: 8px;
  flex: 1;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}

/* 建议问题 - 轻量文字标签 */
.suggest-row {
  margin-top: 10px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.suggest-label {
  font-size: 13px;
  color: #9ca3af;
  white-space: nowrap;
  line-height: 28px;
}

.suggest-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.suggest-item {
  padding: 4px 12px;
  background: transparent;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  font-size: 13px;
  color: #6366F1;
  cursor: pointer;
  transition: all 0.15s ease;
  line-height: 1.4;
}

.suggest-item:hover {
  background: rgba(99, 102, 241, 0.06);
  border-color: rgba(99, 102, 241, 0.3);
}

/* 快速下钻 */
.analysis-drilldown {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 12px 16px;
  background: rgba(99, 102, 241, 0.04);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 12px;
}

.drilldown-title {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  white-space: nowrap;
}

.drilldown-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.drilldown-btn {
  padding: 8px 16px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  color: #6366F1;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.drilldown-btn:hover {
  background: #6366F1;
  color: white;
  border-color: #6366F1;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

/* 多指标分析报告 - 紧凑卡片样式 */
.chat-report-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;
  color: #374151;
  width: 100%;
  max-width: 600px;
  margin-top: 12px;
}

/* 主题色：销售 - 蓝色 */
.chat-report-card.theme-sales {
  border-color: #3b82f6;
}
.chat-report-card.theme-sales .report-header {
  background-color: #eff6ff;
  border-bottom-color: #dbeafe;
}
.chat-report-card.theme-sales .header-icon {
  color: #3b82f6;
}

/* 主题色：广告 - 紫色 */
.chat-report-card.theme-ad {
  border-color: #8b5cf6;
}
.chat-report-card.theme-ad .report-header {
  background-color: #f5f3ff;
  border-bottom-color: #e9d5ff;
}
.chat-report-card.theme-ad .header-icon {
  color: #8b5cf6;
}

/* 主题色：供应链 - 橙色 */
.chat-report-card.theme-inventory {
  border-color: #f97316;
}
.chat-report-card.theme-inventory .report-header {
  background-color: #fff7ed;
  border-bottom-color: #fed7aa;
}
.chat-report-card.theme-inventory .header-icon {
  color: #f97316;
}

/* 主题色：成本 - 金色 */
.chat-report-card.theme-cost {
  border-color: #0d9488;
}
.chat-report-card.theme-cost .report-header {
  background-color: #f0fdfa;
  border-bottom-color: #ccfbf1;
}
.chat-report-card.theme-cost .header-icon {
  color: #0d9488;
}

/* site_health 卡片由 trigger_analyzer 生成，大哥不需要看 */
.chat-report-card.theme-site_health {
  display: none;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 12px 16px;
  background-color: #f9fafb;
  border-bottom: 1px solid #f3f4f6;
}

.report-header .header-main {
  display: flex;
  gap: 8px;
  font-weight: 600;
  line-height: 1.4;
  flex: 1;
}

.header-icon {
  color: #3b82f6;
  font-size: 16px;
  margin-top: 2px;
}

.report-header .summary-text {
  flex: 1;
}

.health-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: bold;
  font-size: 12px;
  white-space: nowrap;
}

.health-excellent { background: #dcfce7; color: #166534; }
.health-good { background: #fef08a; color: #854d0e; }
.health-warning { background: #fee2e2; color: #991b1b; }

.urgent-banner {
  background-color: #fff1f2;
  color: #e11d48;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  border-bottom: 1px solid #ffe4e6;
}

.report-body {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 8px;
}

.text-red { color: #ef4444; }
.text-green { color: #10b981; }

.data-item {
  background: #f9fafb;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 8px;
}

.data-item:last-child { margin-bottom: 0; }

.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.item-header .metric {
  font-weight: 600;
  color: #111827;
}

.item-header .value {
  margin-left: auto;
  font-weight: 600;
}

.item-reason {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
}

.tag {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  font-weight: bold;
}

.tag.P0 { background: #fee2e2; color: #ef4444; }
.tag.P1 { background: #ffedd5; color: #f97316; }
.tag.P2 { background: #f3f4f6; color: #6b7280; }

.action-section {
  padding: 12px 16px;
  background-color: #f8fafc;
  border-top: 1px dashed #e2e8f0;
}

.action-title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}

.action-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.action-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
  color: #334155;
  line-height: 1.4;
}

.bullet {
  width: 6px;
  height: 6px;
  background: #94a3b8;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

.bullet.is-urgent { background: #ef4444; }

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

/* / 快捷命令面板 */
.command-panel {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 12px rgba(0, 0, 0, 0.08);
  z-index: 1000;
  overflow: hidden;
  max-height: 280px;
  overflow-y: auto;
  animation: dropdownFadeIn 0.15s ease-out;
}

@keyframes dropdownFadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.command-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #F9FAFB;
  border-bottom: 1px solid #F3F4F6;
  font-size: 12px;
  color: #6B7280;
}

.command-hint {
  font-size: 11px;
  color: #9CA3AF;
}

.command-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.1s ease;
  border-bottom: 1px solid #F9FAFB;
}

.command-item:last-child {
  border-bottom: none;
}

.command-item:hover {
  background: #F9FAFB;
}

.command-item.selected {
  background: #EFF6FF;
}

.command-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #F3F4F6;
  border-radius: 8px;
  color: #3B82F6;
}

.command-item.selected .command-icon {
  background: #DBEAFE;
}

.command-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.command-title {
  font-size: 14px;
  font-weight: 500;
  color: #1F2937;
}

.command-title .slash {
  color: #3B82F6;
  margin-right: 2px;
}

.command-desc {
  font-size: 12px;
  color: #6B7280;
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

/* ========================================
   Responsive Design - Mobile Adaptation
   ======================================== */

@media (max-width: 768px) {
  .llm-ask-v2 {
    height: 100vh;
    height: 100dvh;
  }

  .main-container {
    padding: 80px 16px 24px;
    gap: 16px;
    height: calc(100vh - 60px);
    height: calc(100dvh - 60px);
    max-width: 100%;
  }

  .init-view {
    padding: 60px 16px 24px;
    max-width: 100%;
    justify-content: flex-start;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }

  .greeting-section {
    flex-direction: column;
    align-items: center;
    text-align: center;
    margin-bottom: 16px;
    max-width: 100%;
  }

  .avatar-wrapper {
    width: 48px;
    height: 48px;
  }

  .avatar-wrapper svg {
    width: 48px;
    height: 48px;
  }

  .welcome-text {
    font-size: 16px;
    line-height: 1.4;
  }

  .mode-tabs {
    display: none;
  }

  .init-input-section {
    width: 100%;
    max-width: 100%;
    margin-bottom: 12px;
  }

  .init-input-section .chat-input-wrapper {
    padding: 12px 16px;
    min-height: 56px;
    border-radius: 14px;
  }

  .init-input-section .chat-input {
    font-size: 15px;
    min-height: 32px;
  }

  .init-input-section .send-btn {
    width: 40px;
    height: 40px;
    margin-left: 10px;
    flex-shrink: 0;
  }

  .suggestions-section {
    width: 100%;
    max-width: 100%;
    flex: 1;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }

  .suggestions-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .suggestion-card .card-content p {
    display: none;
  }

  .suggestion-card {
    padding: 10px 12px;
    min-height: auto;
    flex-direction: row;
    align-items: center;
  }

  .card-content h4 {
    font-size: 14px;
  }

  .card-icon {
    width: 40px;
    height: 40px;
    margin-bottom: 8px;
  }

  .suggestions-title {
    font-size: 14px;
    margin-bottom: 10px;
  }

  .input-tools-bar {
    display: none;
  }

  /* Chat view responsive */
  .chat-view {
    padding: 0;
  }

  .messages-container {
    padding: 12px 8px;
  }

  .message-item {
    gap: 10px;
    margin-bottom: 12px;
  }

  .message-avatar {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
  }

  .message-avatar img,
  .message-avatar svg {
    width: 32px;
    height: 32px;
  }

  .message-content {
    max-width: 80%;
    min-width: unset;
    padding: 10px 14px;
  }

  .message-item.assistant .message-content {
    border-radius: 14px 14px 14px 4px;
  }

  .message-item.user .message-content {
    border-radius: 14px 14px 4px 14px;
  }

  .input-section {
    padding: 12px 16px 16px;
  }

  .chat-input-wrapper {
    padding: 12px 16px;
    border-radius: 20px;
    min-height: 80px;
  }

  .chat-input {
    font-size: 16px;
    min-height: 44px;
  }

  .send-btn {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    margin-left: 12px;
  }

  .send-btn svg {
    width: 18px;
    height: 18px;
  }

  /* ========== UI 增强 ========== */

  /* 输入框毛玻璃效果 */
  .input-section {
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-top: 1px solid rgba(255, 255, 255, 0.3);
  }

  /* 按钮触控热区 */
  .send-btn,
  .action-btn,
  .clarification-tag {
    min-height: 44px;
    min-width: 44px;
  }

  /* 用户气泡优化 */
  .message-item.user .message-content {
    background: linear-gradient(135deg, #6366F1 0%, #7C3AED 100%);
    color: #fff;
    border: none;
    padding: 10px 14px;
    border-radius: 18px 18px 4px 18px;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
  }

  .message-item.user .message-text {
    color: #fff;
    font-size: 14px;
    line-height: 1.5;
  }

  .message-item.user .message-time {
    color: rgba(255, 255, 255, 0.7);
  }

  /* placeholder 可读性 */
  .chat-input::placeholder {
    color: #666;
  }

  /* 快速下钻移动端适配 */
  .analysis-drilldown {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 12px;
  }

  .drilldown-list {
    gap: 6px;
  }

  .drilldown-btn {
    padding: 6px 12px;
    font-size: 12px;
  }
}

@media (max-width: 480px) {
  .main-container {
    padding: 70px 12px 16px;
    max-width: 100%;
  }

  .init-view {
    padding: 50px 12px 16px;
    max-width: 100%;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }

  .greeting-section {
    max-width: 100%;
    margin-bottom: 12px;
  }

  .welcome-text {
    font-size: 15px;
  }

  .avatar-wrapper {
    width: 44px;
    height: 44px;
  }

  .avatar-wrapper svg {
    width: 44px;
    height: 44px;
  }

  .mode-tabs {
    display: none;
  }

  .init-input-section {
    margin-bottom: 10px;
  }

  .init-input-section .chat-input-wrapper {
    padding: 10px 14px;
    min-height: 48px;
  }

  .init-input-section .chat-input {
    font-size: 14px;
    min-height: 28px;
  }

  .init-input-section .send-btn {
    width: 36px;
    height: 36px;
  }

  .input-tools-bar {
    display: none;
  }

  .suggestions-section {
    max-width: 100%;
    flex: 1;
    overflow-y: auto;
  }

  .suggestions-title {
    font-size: 13px;
    margin-bottom: 8px;
  }

  .suggestions-grid {
    gap: 8px;
  }

  .suggestion-card .card-content p {
    display: none;
  }

  .suggestion-card {
    flex-direction: row;
    align-items: center;
    padding: 8px 10px;
  }

  .card-content h4 {
    font-size: 13px;
  }

  .card-icon {
    width: 36px;
    height: 36px;
    margin-bottom: 0;
    margin-right: 10px;
  }

  .message-content {
    max-width: 90%;
    padding: 10px 12px;
  }

  .chat-view {
    padding: 0;
  }

  .messages-container {
    padding: 10px 6px;
  }

  .message-item {
    gap: 8px;
    margin-bottom: 10px;
  }

  .message-avatar {
    width: 28px;
    height: 28px;
    flex-shrink: 0;
  }

  .message-avatar img,
  .message-avatar svg {
    width: 28px;
    height: 28px;
  }

  .message-item.assistant .message-content {
    border-radius: 12px 12px 12px 4px;
  }

  .message-item.user .message-content {
    border-radius: 12px 12px 4px 12px;
  }

  .input-section {
    padding: 10px 12px 12px;
  }

  .chat-input-wrapper {
    padding: 10px 14px;
    border-radius: 18px;
    min-height: 60px;
  }

  .chat-input {
    font-size: 15px;
    min-height: 36px;
  }

  .send-btn {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    margin-left: 10px;
  }

  /* 快速下钻移动端适配 */
  .analysis-drilldown {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 10px;
  }

  .drilldown-list {
    gap: 6px;
  }

  .drilldown-btn {
    padding: 6px 10px;
    font-size: 12px;
  }
}

/* ========================================
   2026 Refresh Overrides
   ======================================== */

.llm-ask-v2 {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.08), transparent 32%),
    radial-gradient(circle at bottom right, rgba(15, 23, 42, 0.05), transparent 26%),
    linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
}

.main-container {
  max-width: 1480px;
  padding: 20px 24px 20px 96px;
  gap: 0;
  height: 100vh;
}

.content-area {
  background: transparent;
}

.chat-wrapper {
  background: transparent;
}

.init-view {
  max-width: 960px;
  padding: 110px 32px 24px;
  justify-content: center;
}

.greeting-section {
  justify-content: center;
  text-align: center;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 28px;
}

.avatar-wrapper {
  width: 68px;
  height: 68px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.welcome-text {
  font-size: 34px;
  line-height: 1.35;
  font-weight: 700;
  max-width: 760px;
  background: none;
  -webkit-text-fill-color: #0f172a;
  color: #0f172a;
}

.mode-tabs {
  justify-content: center;
  gap: 8px;
  margin-bottom: 18px;
}

.mode-tab {
  height: 34px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(226, 232, 240, 0.82);
  color: #64748b;
  padding: 0 14px;
  font-size: 12px;
  font-weight: 600;
}

.mode-tab.active {
  background: #0f172a;
  color: #f8fafc;
  border-color: #0f172a;
}

.init-input-section,
.suggestions-section {
  max-width: 860px;
}

.init-input-section .chat-input-wrapper,
.input-section .chat-input-wrapper {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(16px);
}

.init-input-section .chat-input-wrapper {
  min-height: 84px;
  border-radius: 28px;
  padding: 16px 18px 16px 22px;
}

.chat-input {
  font-size: 17px;
  color: #0f172a;
}

.chat-input::placeholder {
  color: #94a3b8;
}

.send-btn {
  background: #0f172a;
  border-radius: 18px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.18);
}

.send-btn:hover:not(:disabled) {
  background: #111827;
  box-shadow: 0 20px 44px rgba(15, 23, 42, 0.22);
}

.suggestions-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.suggestion-card {
  background: rgba(255, 255, 255, 0.66);
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 20px;
  min-height: 96px;
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.04);
}

.suggestion-card:hover {
  border-color: #bfdbfe;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.07);
}

.card-icon {
  border-radius: 16px;
  background: #eff6ff;
  color: #2563eb;
}

.card-content h4 {
  color: #0f172a;
}

.card-content p,
.suggestions-title,
.tool-hint {
  color: #64748b;
}

.suggestions-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  margin-bottom: 10px;
}

.input-tools-bar {
  justify-content: flex-end;
  gap: 10px;
}

.tool-label {
  margin-right: auto;
  font-size: 13px;
  color: #64748b;
}

.tool-icon {
  opacity: 0.5;
}

.tool-hint {
  font-size: 12px;
}

.chat-view {
  max-width: 980px;
  width: 100%;
  margin: 0 auto;
}

.messages-container {
  padding: 36px 24px 20px;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-bottom: 24px;
}

.input-section {
  padding: 12px 24px 28px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0) 0%, rgba(248, 250, 252, 0.88) 32%, rgba(248, 250, 252, 0.98) 100%);
}

.input-section .chat-input-wrapper {
  min-height: 76px;
  border-radius: 26px;
  padding: 14px 16px 14px 20px;
}

.command-panel {
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.14);
}

@media (max-width: 1100px) {
  .main-container {
    padding: 76px 16px 16px;
  }

  .chat-view,
  .init-view,
  .init-input-section,
  .suggestions-section {
    max-width: 100%;
  }

  .welcome-text {
    font-size: 24px;
  }

  .messages-container {
    padding: 20px 6px 14px;
  }

  .input-section {
    padding: 10px 8px 16px;
  }

  .suggestions-grid {
    grid-template-columns: 1fr;
  }

  .tool-label {
    display: none;
  }
}
</style>
