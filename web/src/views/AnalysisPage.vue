<template>
  <div class="analysis-page">
    <!-- 背景装饰 -->
    <div class="bg-gradient"></div>
    <div class="bg-grid"></div>

    <!-- 主内容区 -->
    <div class="analysis-container">
      <!-- 左侧对话面板 -->
      <div class="chat-panel">
        <!-- 面板头部 -->
        <div class="panel-header">
          <div class="panel-title">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 2L12.5 7.5H18L13.5 11L15.5 17L10 13.5L4.5 17L6.5 11L2 7.5H7.5L10 2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            </svg>
            <span>智能对话</span>
          </div>
          <button class="icon-btn" @click="clearChat" title="清空对话">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M3 5H15M6 5V3C6 2.44772 6.44772 2 7 2H11C11.5523 2 12 2.44772 12 3V5M7 8V13M11 8V13M4 5L5 15C5 15.5523 5.44772 16 6 16H12C12.5523 16 13 15.5523 13 15L14 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <!-- 流式/非流式切换 -->
          <div class="mode-toggle">
            <span :class="{ active: outputMode === 'non-stream' }" @click="outputMode = 'non-stream'">普通</span>
            <span :class="{ active: outputMode === 'stream' }" @click="outputMode = 'stream'">流式</span>
          </div>
        </div>

        <!-- 消息列表 -->
        <div class="messages-container" ref="messagesContainer">
          <!-- 骨架屏 -->
          <div v-if="historyLoading" class="skeleton-list">
            <div v-for="i in 3" :key="i" class="skeleton-card">
              <div class="skeleton-avatar"></div>
              <div class="skeleton-content">
                <div class="skeleton-line short"></div>
                <div class="skeleton-line long"></div>
                <div class="skeleton-line medium"></div>
              </div>
            </div>
          </div>
          <div v-else-if="!messages.length" class="empty-state">
            <div class="empty-icon">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                <circle cx="24" cy="24" r="20" stroke="currentColor" stroke-width="2"/>
                <path d="M16 20C16 19.4477 16.4477 19 17 19H31C31.5523 19 32 19.4477 32 20V30C32 30.5523 31.5523 31 31 31H17C16.4477 31 16 30.5523 16 30V20Z" stroke="currentColor" stroke-width="2"/>
                <path d="M20 25H28M20 28H24" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
            <p>开始对话，描述您的分析需求</p>
          </div>
          <div v-else class="message-list">
            <div
              v-for="(msg, idx) in messages"
              :key="idx"
              :class="['message', msg.role, { active: selectedIndex === idx && msg.role === 'assistant' }]"
              @click="msg.role === 'assistant' && msg.summary && selectReport(idx)"
            >
              <div class="message-avatar">
                <div v-if="msg.role === 'user'" class="avatar user-avatar">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="5" r="3" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M3 14C3 11.2386 5.23858 9 8 9C10.7614 9 13 11.2386 13 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                </div>
                <div v-else class="avatar ai-avatar">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M8 1L10 5H14L11 8L12 13L8 10L4 13L5 8L2 5H6L8 1Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
              <div class="message-content">
                <!-- 用户消息 -->
                <div v-if="msg.role === 'user'" class="message-bubble" v-html="formatMessage(msg.content)"></div>

                <!-- AI 消息：耗时步骤（流式） -->
                <div v-else-if="msg.role === 'assistant' && msg.thinkingSteps && msg.thinkingSteps.length > 0" class="message-bubble thinking-bubble">
                  <div class="thinking-steps-stream">
                    <div class="thinking-header">
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                        <path d="M7 4V7L9 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                      </svg>
                      <span>分析中...</span>
                      <span class="total-time" v-if="msg.totalTime">{{ msg.totalTime }}</span>
                    </div>
                    <div class="steps-list">
                      <div
                        v-for="(step, sIdx) in msg.thinkingSteps"
                        :key="sIdx"
                        :class="['step-item', step.status]"
                      >
                        <span class="step-icon">
                          <svg v-if="step.status === 'done'" width="10" height="10" viewBox="0 0 10 10" fill="none">
                            <circle cx="5" cy="5" r="4" fill="#16a34a"/>
                            <path d="M3 5L4.5 6.5L7 3.5" stroke="white" stroke-width="1.2" stroke-linecap="round"/>
                          </svg>
                          <svg v-else width="10" height="10" viewBox="0 0 10 10" fill="none">
                            <circle cx="5" cy="5" r="4" stroke="currentColor" stroke-width="1.5" stroke-dasharray="3 2"/>
                          </svg>
                        </span>
                        <span class="step-label">{{ step.label }}</span>
                        <span class="step-dur" v-if="step.duration">{{ step.duration }}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- AI 消息：摘要卡片（完成后） -->
                <div v-else-if="msg.role === 'assistant' && msg.summary" class="summary-card">
                  <div class="summary-bubble">
                    <div class="summary-header">
                      <span class="summary-badge">✅ 分析完成</span>
                      <span class="summary-time">{{ msg.totalTime }}</span>
                    </div>
                    <div class="summary-question" v-if="msg.question">Q: {{ msg.question }}</div>
                    <div class="summary-body" v-html="formatSummary(msg.summary)"></div>
                    <div class="summary-action">点击查看完整报告 →</div>
                  </div>
                </div>

                <!-- AI 消息：直接显示内容（当没有 summary 且没有 thinkingSteps 时） -->
                <div v-else-if="msg.role === 'assistant' && msg.content" class="message-bubble" v-html="formatMessage(msg.content)"></div>

                <div class="message-footer">
                  <div class="message-time">{{ formatTime(msg.created_at) }}</div>
                  <button
                    v-if="msg.role === 'assistant' && msg.summary"
                    class="delete-btn"
                    @click.stop="deleteMessage(idx)"
                    title="删除"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M3 4H11M5 4V3C5 2.44772 5.44772 2 6 2H8C8.55228 2 9 2.44772 9 3V4M6 6V10M8 6V10M4 4L4.5 11C4.5 11.5523 4.94772 12 5.5 12H8.5C9.05273 12 9.5 11.5523 9.5 11L10 4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-wrapper">
            <textarea
              v-model="inputText"
              :disabled="loading"
              placeholder="输入分析需求，如：分析近30天广告投放效果"
              rows="1"
              @keydown.enter.exact.prevent="handleSend"
            ></textarea>
            <button
              class="send-btn"
              :disabled="loading || !inputText.trim()"
              @click="handleSend"
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M3 9L15 9M15 9L10 4M15 9L10 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
          <div class="input-hint">按 Enter 发送，Shift + Enter 换行</div>
        </div>
      </div>

      <!-- 右侧分析面板 -->
      <div class="result-panel">
        <!-- 面板头部 -->
        <div class="panel-header">
          <div class="panel-title">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="2" y="4" width="16" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/>
              <path d="M6 9H14M6 12H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span>分析报告</span>
          </div>
          <div v-if="analysisLoading" class="progress-badge">
            <span class="spinner"></span>
            <span>分析中...</span>
          </div>
        </div>

        <!-- 分析结果内容 -->
        <div class="result-content">
          <div v-if="!analysisResult && !analysisLoading" class="result-empty">
            <div class="empty-illustration">
              <svg width="120" height="120" viewBox="0 0 120 120" fill="none">
                <rect x="20" y="30" width="80" height="60" rx="8" stroke="currentColor" stroke-width="2" stroke-dasharray="4 4"/>
                <path d="M40 50H80M40 60H70M40 70H60" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
                <circle cx="85" cy="75" r="20" fill="var(--primary)" opacity="0.1"/>
                <path d="M80 75L85 80L95 70" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <h4>准备就绪</h4>
            <p>在左侧输入分析需求，获取 AI 智能分析结果</p>
            <div class="quick-prompts">
              <span class="prompt-label">快速开始：</span>
              <button
                v-for="prompt in quickPrompts"
                :key="prompt"
                class="prompt-chip"
                @click="inputText = prompt"
              >
                {{ prompt }}
              </button>
            </div>
          </div>
          <div v-if="!analysisResult && !analysisLoading" class="result-empty">
            <div class="empty-illustration">
              <svg width="120" height="120" viewBox="0 0 120 120" fill="none">
                <rect x="20" y="30" width="80" height="60" rx="8" stroke="currentColor" stroke-width="2" stroke-dasharray="4 4"/>
                <path d="M40 50H80M40 60H70M40 70H60" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
                <circle cx="85" cy="75" r="20" fill="var(--primary)" opacity="0.1"/>
                <path d="M80 75L85 80L95 70" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <h4>准备就绪</h4>
            <p>在左侧输入分析需求，获取 AI 智能分析结果</p>
            <div class="quick-prompts">
              <span class="prompt-label">快速开始：</span>
              <button
                v-for="prompt in quickPrompts"
                :key="prompt"
                class="prompt-chip"
                @click="inputText = prompt"
              >
                {{ prompt }}
              </button>
            </div>
          </div>
          <div v-else-if="analysisLoading && !analysisResult" class="result-loading">
            <div class="loading-animation">
              <div class="pulse-ring"></div>
              <div class="pulse-ring delay-1"></div>
              <div class="pulse-ring delay-2"></div>
              <div class="pulse-center">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2L14 6H18L15 9L16 14L12 11L8 14L9 9L6 6H10L12 2Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
                </svg>
              </div>
            </div>
            <p>正在分析中，请稍候...</p>
          </div>
          <div v-else class="result-text" v-html="analysisResult"></div>

          <!-- 图表区域（仅当图表未嵌入markdown时显示） -->
          <div v-if="analysisCharts.length > 0 && !rawMarkdown.includes('[[CHART:')" class="charts-section">
            <div v-for="(chart, index) in analysisCharts" :key="index" class="chart-wrapper">
              <div class="chart-title">{{ chart.title }}</div>
              <div :ref="el => chartRefs[index] = el" class="chart-container"></div>
            </div>
          </div>
        </div>

        <!-- 底部操作 -->
        <div v-if="analysisResult" class="result-actions">
          <button class="action-btn" @click="copyResult">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="4" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.5"/>
              <path d="M4 4V2C4 1.44772 4.44772 1 5 1H12C12.5523 1 13 1.44772 13 2V9C13 9.55228 12.5523 10 12 10H11" stroke="currentColor" stroke-width="1.5"/>
            </svg>
            复制结果
          </button>
          <button class="action-btn" @click="exportResult">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 11V13C2 13.5523 2.44772 14 3 14H13C13.5523 14 14 13.5523 14 13V11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <path d="M8 2V10M8 10L5 7M8 10L11 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            导出报告
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, shallowRef, triggerRef } from 'vue'
import * as echarts from 'echarts'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 配置 marked
marked.setOptions({
  gfm: true,
  breaks: true
})

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const analysisResult = ref('')  // 用 ref 确保 v-html 响应式更新
const analysisLoading = ref(false)
const analysisCharts = ref([])
const chartRefs = ref([])
const messagesContainer = ref(null)
const sessionId = ref(localStorage.getItem('analysis_session_id') || '')
const selectedIndex = ref(-1)
const historyLoading = ref(false)
const reportCache = new Map()
const rawMarkdown = ref('')  // 用 ref 确保 v-html 响应式更新
const outputMode = ref('stream')  // 'stream' | 'non-stream' 默认流式输出
let initChartsTimer = null  // 防抖定时器

const quickPrompts = [
  '分析近30天广告投放效果',
  '亚马逊流量分析',
  '亚马逊财务分析'
]

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({
    role: 'user',
    content: text,
    created_at: new Date().toISOString()
  })
  inputText.value = ''
  loading.value = true
  analysisLoading.value = true
  scrollToBottom()

  // 添加一条空的 AI 消息
  const aiMsgIndex = messages.value.length
  messages.value.push({
    role: 'assistant',
    id: null,
    question: text,
    content: '',
    summary: '',
    fullReport: '',
    thinkingSteps: [],
    totalTime: '',
    created_at: new Date().toISOString()
  })

  try {
    if (outputMode.value === 'stream') {
      // 流式模式
      await handleStreamMode(text, aiMsgIndex)
    } else {
      // 非流式模式
      await handleNonStreamMode(text, aiMsgIndex)
    }
    nextTick(() => initCharts())
  } catch (error) {
    console.error('[handleSend] 捕获到异常:', error)
    messages.value[aiMsgIndex].content = '分析失败: ' + error.message
    analysisResult.value = '<p>分析失败: ' + error.message + '</p>'
  } finally {
    loading.value = false
    analysisLoading.value = false
    scrollToBottom()
  }
}

async function handleNonStreamMode(text, aiMsgIndex) {
  const token = localStorage.getItem('access_token') || ''
  const response = await fetch('/api/v1/analysis/analyze', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ query: text, session_id: sessionId.value })
  })

  const data = await response.json()

  if (data.code !== 0) {
    throw new Error(data.message || '分析失败')
  }

  const { answer, charts } = data.data

  // 处理图表
  if (charts && charts.length > 0) {
    analysisCharts.value = charts
  }

  // 1. 先清理 markdown 格式问题（但不删除 [[CHART:N]] 标记，它们会在 embedChartsInHtml 中被替换）
  let cleanedMarkdown = answer
  cleanedMarkdown = cleanedMarkdown.replace(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)/g, '$1$2$3')
  cleanedMarkdown = cleanedMarkdown.replace(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/g, '$1$2$3')
  cleanedMarkdown = cleanedMarkdown.replace(/([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])/g, '$1$2')
  cleanedMarkdown = cleanedMarkdown.replace(/\*\*\s+(.+?)\s+\*\*/g, '**$1**')
  cleanedMarkdown = cleanedMarkdown.replace(/M\s*K\s*I-\d+\s*-\s*\d+/g, (m) => m.replace(/\s/g, ''))

  // 2. 转换为 HTML（此时 [[CHART:N]] 标记还在）
  const htmlBeforeCharts = marked.parse(cleanedMarkdown)

  // 3. 嵌入图表（替换 [[CHART:N]] 为实际的图表 HTML）
  const htmlWithCharts = embedChartsInHtml(htmlBeforeCharts)
  analysisResult.value = DOMPurify.sanitize(htmlWithCharts)
  rawMarkdown.value = answer

  // 更新消息
  if (aiMsgIndex < messages.value.length) {
    messages.value[aiMsgIndex].content = answer
    messages.value[aiMsgIndex].summary = extractSummary(answer)
    messages.value[aiMsgIndex].rawMarkdown = answer
    messages.value[aiMsgIndex].charts = charts || []
  }

  // 保存到后端
  try {
    const token = localStorage.getItem('access_token') || ''
    const saveRes = await fetch('/api/v1/ask-analysis/logs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        session_id: sessionId.value,
        question: text,
        answer: answer,
        thinking_steps: '',
        intent: 'decision_analysis',
        success: true
      })
    })
    const saveData = await saveRes.json()
    if (saveData.code === 0 && saveData.data?.id) {
      messages.value[aiMsgIndex].id = saveData.data.id
      reportCache.set(saveData.data.id, analysisResult.value)
    }
  } catch (e) {
    console.error('保存报告失败:', e)
  }
}

// 修补不完整的 Markdown，流式过程中调用
function patchMarkdown(text) {
  if (!text) return text

  // 1. 补全未闭合的代码块（```）
  const codeBlockCount = (text.match(/```/g) || []).length
  if (codeBlockCount % 2 !== 0) {
    text += '\n```'
  }

  // 2. 处理不完整的表格 - 核心问题
  // 表格格式: | 列1 | 列2 | 后面跟 |---|---|
  // 如果只有 | 开头但没有表格分隔符 |---|，说明表格不完整
  const tableStartIdx = text.indexOf('| ')
  if (tableStartIdx !== -1) {
    // 检查是否有表格分隔行 (包含 |---| 的行)
    const hasTableSeparator = /\|[-:\s|]+\|/.test(text)
    // 检查是否在表格分隔行之后（说明表格已完整）
    const lastTableSepIdx = text.lastIndexOf('|---')
    const lastPipeIdx = text.lastIndexOf('|')

    // 如果有表格开始但没有分隔符，或者分隔符在最后一个 | 之后
    if (!hasTableSeparator || (lastPipeIdx > lastTableSepIdx && lastTableSepIdx !== -1)) {
      // 表格不完整：把最后一个不完整的表格行转为纯文本（行首加 > 变成引用）
      const lines = text.split('\n')
      for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i]
        // 如果这行是表格行（以 | 开头或包含 | 但不是分隔符）且不在完整表格后
        if (line.trim().startsWith('|') && !/^\|[-:\s|]+\|$/.test(line.trim())) {
          // 检查这行后面是否有完整的表格（有空行或到末尾）
          const afterThisLine = lines.slice(i + 1).join('\n')
          if (!afterThisLine.trim() || !hasTableSeparator) {
            // 把这行标记为纯文本（前面加 > 引用符号）
            lines[i] = '> ' + line
            break
          }
        }
      }
      text = lines.join('\n')
    }
  }

  // 3. 补全未闭合的加粗 **
  const boldCount = (text.match(/\*\*/g) || []).length
  if (boldCount % 2 !== 0) {
    text += '**'
  }

  return text
}

async function handleStreamMode(text, aiMsgIndex) {
  const t0 = performance.now()
  // 使用 fetch + ReadableStream 解析 SSE
  const token = localStorage.getItem('access_token') || ''
  const t1 = performance.now()
  const response = await fetch('/api/v1/analysis/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ query: text, session_id: sessionId.value })
  })
  console.log('[耗时] fetch请求:', Math.round(performance.now() - t1), 'ms')

  if (!response.ok) {
    throw new Error('请求失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let fullContent = ''
  let chunkCount = 0
  let chartCount = 0

  // 解析 SSE 事件 - 支持多行 data: 内容，处理空行
  // SSE 格式: "data: 内容" 表示一行内容，空 "data:" 或 "data: " 表示换行
  const parseSSE = (data) => {
    const lines = data.split('\n')
    const dataLines = []
    for (const line of lines) {
      if (!line) continue  // 跳过空行（来自 split 产生的空字符串）

      // 优先匹配 "data: xxx" 格式（有空格）
      if (line.startsWith('data: ')) {
        const content = line.slice(6)
        // 如果是空内容（data: 后面只有空格），表示换行
        if (content.trim() === '') {
          dataLines.push('\n')
        } else {
          dataLines.push(content)
        }
      }
      // 处理 "data:xxx" 或 "data:" 格式（无空格或空内容）
      else if (line.startsWith('data:')) {
        const afterData = line.slice(5)  // 去掉 "data:"
        if (afterData.trim() === '') {
          // 空 data: 行表示换行
          dataLines.push('\n')
        } else {
          // data:xxx 格式（无空格）
          dataLines.push(afterData)
        }
      }
    }
    return dataLines.join('')
  }

  // 清理 markdown 的函数
  const cleanMarkdown = (md) => {
    let cleaned = md
    // 删除报告中的 logo 图片，避免重复请求外部 CDN
    cleaned = cleaned.replace(/<img[^>]*ugnas\.com[^>]*>/gi, '')
    cleaned = cleaned.replace(/\[\[[\s\S]*?CHART_BLOCK[\s\S]*?\]\]/gi, '')
    cleaned = cleaned.replace(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)/g, '$1$2$3')
    cleaned = cleaned.replace(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/g, '$1$2$3')
    cleaned = cleaned.replace(/([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])/g, '$1$2')
    cleaned = cleaned.replace(/\*\*\s+(.+?)\s+\*\*/g, '**$1**')
    cleaned = cleaned.replace(/M\s*K\s*I-\d+\s*-\s*\d+/g, (m) => m.replace(/\s/g, ''))
    return cleaned
  }

  let lastEventType = ''
  let streamDone = false  // 标记流式是否已完成

  while (!streamDone) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // 处理 buffer 中的所有完整行
    const lines = buffer.split('\n')
    buffer = lines.pop() || '' // 保留最后一行（可能不完整）

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        lastEventType = line.slice(7)
        continue
      }

      const eventData = parseSSE(line)
      // done 和 close 事件即使 eventData 为空也要处理
      if (!eventData && lastEventType !== 'done' && lastEventType !== 'close') continue

      if (lastEventType === 'chunk') {
        chunkCount++
        // 收到文本 chunk，追加
        fullContent += eventData
        // 删除 logo 图片避免重复请求 CDN
        const cleaned = fullContent.replace(/<img[^>]*ugnas\.com[^>]*>/gi, '')
        const html = '<pre style="white-space:pre-wrap;word-break:break-all;font-family:inherit;margin:0;padding:0;background:transparent;border:none;color:var(--text-primary)">' + DOMPurify.sanitize(cleaned) + '</pre>'
        analysisResult.value = html
        rawMarkdown.value = fullContent
        // 同时更新 messages 中的 content（让左边消息列表也能显示实时内容）
        if (aiMsgIndex < messages.value.length) {
          messages.value[aiMsgIndex].content = fullContent
        }
        // Vue ref 自动追踪依赖，无需手动 triggerRef
      } else if (lastEventType === 'chart') {
        const tChart = performance.now()
        // 收到图表数据，处理 markdown 中的图表标记
        try {
          chartCount++
          const chartPayload = JSON.parse(eventData)
          // 如果有 markdown 字段（处理后的完整 markdown），用它替换 fullContent
          if (chartPayload.markdown) {
            fullContent = chartPayload.markdown
          }
          // 更新图表数据
          if (chartPayload.charts && chartPayload.charts.length > 0) {
            analysisCharts.value = chartPayload.charts
          }
          // 渲染 markdown（嵌入图表）
          const finalMarkdown = cleanMarkdown(fullContent)
          const parsedHtml = marked.parse(finalMarkdown)
          console.log('[DEBUG] chart事件 parsedHtml 前50字符:', parsedHtml?.substring(0, 50))
          console.log('[DEBUG] chart事件 [[CHART 数量:', (parsedHtml?.match(/\[\[CHART:/g) || []).length)
          const htmlWithCharts = embedChartsInHtml(parsedHtml)
          console.log('[DEBUG] chart事件 htmlWithCharts chart-embed数量:', (htmlWithCharts?.match(/chart-embed/g) || []).length)
          analysisResult.value = DOMPurify.sanitize(htmlWithCharts)
          rawMarkdown.value = fullContent
          // 防抖：清除之前的 initCharts 定时器，只设置一个新的
          if (initChartsTimer) {
            clearTimeout(initChartsTimer)
          }
          initChartsTimer = setTimeout(() => {
            initCharts()
            initChartsTimer = null
          }, 100)
          console.log('[耗时] chart事件处理:', Math.round(performance.now() - tChart), 'ms, chartCount:', chartCount)
        } catch (e) {
          console.error('解析图表数据失败:', e, 'raw data:', eventData?.substring(0, 200))
        }
      } else if (lastEventType === 'thinking') {
        // 收到思考步骤，更新 thinkingSteps
        const { steps, totalTime } = parseThinkingStep(eventData)
        if (steps.length > 0) {
          messages.value[aiMsgIndex].thinkingSteps.push(...steps)
          triggerRef(messages.value)
        }
        if (totalTime) {
          messages.value[aiMsgIndex].totalTime = totalTime
        }
      } else if (lastEventType === 'done' || lastEventType === 'close') {
        // 完成：清除防抖定时器，立即初始化图表
        if (initChartsTimer) {
          clearTimeout(initChartsTimer)
          initChartsTimer = null
        }
        rawMarkdown.value = fullContent
        // 清空思考步骤，显示完成状态
        if (aiMsgIndex < messages.value.length) {
          messages.value[aiMsgIndex].thinkingSteps = []
        }
        // 标记流式完成，退出 while 循环
        streamDone = true
        break
      }
    }
  }

  // 处理剩余 buffer
  if (buffer) {
    const eventData = parseSSE(buffer)
    if (eventData && lastEventType === 'chunk') {
      fullContent += eventData
      // 如果之前没有 chart 事件，需要更新文本显示
      if (!analysisCharts.value.length) {
        const cleaned = fullContent.replace(/<img[^>]*ugnas\.com[^>]*>/gi, '')
        analysisResult.value = DOMPurify.sanitize('<pre>' + DOMPurify.sanitize(cleaned) + '</pre>')
      }
    }
  }

  const tAfterLoop = performance.now()
  console.log('[耗时] while循环结束, chunkCount:', chunkCount, 'chartCount:', chartCount, '耗时:', Math.round(tAfterLoop - t0), 'ms')

  // 如果有图表，直接初始化；否则解析 markdown
  if (analysisCharts.value.length > 0) {
    // 图表已在 chart 事件中渲染并设置了 setTimeout，这里直接初始化
    await nextTick()
    initCharts()
    console.log('[耗时] initCharts完成, 图表数:', analysisCharts.value.length, '耗时:', Math.round(performance.now() - tAfterLoop), 'ms')
  } else {
    // 无图表时解析 markdown
    const finalCleaned = cleanMarkdown(fullContent)
    try {
      analysisResult.value = DOMPurify.sanitize(marked.parse(finalCleaned))
    } catch (e) {
      console.error('[流式] marked.parse 失败:', e)
      analysisResult.value = DOMPurify.sanitize('<pre>' + finalCleaned + '</pre>')
    }
  }

  if (aiMsgIndex < messages.value.length) {
    messages.value[aiMsgIndex].content = fullContent
    messages.value[aiMsgIndex].summary = extractSummary(fullContent)
    messages.value[aiMsgIndex].rawMarkdown = fullContent
    messages.value[aiMsgIndex].charts = analysisCharts.value
  }

  console.log('[耗时] handleStreamMode总耗时:', Math.round(performance.now() - t0), 'ms')

  // 保存到后端
  try {
    const token = localStorage.getItem('access_token') || ''
    const sid = sessionId.value

    const tSave = performance.now()
    const saveRes = await fetch('/api/v1/ask-analysis/logs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        session_id: sid,
        question: text,
        answer: fullContent,
        thinking_steps: '',
        intent: 'decision_analysis',
        success: true
      })
    })
    console.log('[耗时] 保存到后端:', Math.round(performance.now() - tSave), 'ms')

    if (!saveRes.ok) {
      console.error('[保存] 请求失败, 状态:', saveRes.status)
      return
    }

    const saveData = await saveRes.json()

    if (saveData.code === 0 && saveData.data?.id) {
      messages.value[aiMsgIndex].id = saveData.data.id
      // 保存渲染后的 HTML 到缓存，避免 selectReport 拿到原始 markdown
      reportCache.set(saveData.data.id, analysisResult.value)
    }
    console.log('[耗时] 全流程总耗时:', Math.round(performance.now() - t0), 'ms')
  } catch (e) {
    console.error('保存报告失败:', e)
  }
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function parseThinkingStep(text) {
  // text 格式: "[耗时] 步骤1: xxx: YYYms (累计: ZZZms)"
  const steps = []
  let totalTime = ''
  let stepNum = 0

  // 尝试解析带耗时的步骤
  // 格式: [耗时] 步骤X: 名称: NNNms (累计: MMMms)
  const match = text.match(/\[耗时\]\s*步骤(\d+):\s*(.+?):\s*(\d+)ms\s*\(累计:\s*(\d+)ms\)/)
  if (match) {
    stepNum = parseInt(match[1])
    const label = `步骤${stepNum}: ${match[2].trim()}`  // 还原完整标签 "步骤1: xxx"
    const duration = parseInt(match[3])
    totalTime = formatDuration(parseInt(match[4]))
    steps.push({
      stepNum,
      label,
      duration: formatDuration(duration),
      status: 'active'
    })
  } else {
    // 纯文本 thinking 事件 - 直接显示
    steps.push({
      stepNum: 0,
      label: text,
      duration: '',
      status: 'active'
    })
  }

  return { steps, totalTime }
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`
  const s = (ms / 1000).toFixed(1)
  return `${s}s`
}

function formatMessage(text) {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

// 提取摘要内容
function extractSummary(text) {
  if (!text) return ''
  // 提取前几行的关键数据
  const lines = text.split('\n').filter(l => l.trim())
  const summaryLines = lines.slice(0, 5).join('\n')
  return summaryLines
}

// 格式化摘要显示
function formatSummary(text) {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

// 删除消息
async function deleteMessage(idx) {
  const msg = messages.value[idx]
  if (!msg) return

  const msgId = msg.id

  // 如果有后端 ID，调用后端删除
  if (msgId) {
    try {
      const token = localStorage.getItem('access_token') || ''
      const res = await fetch(`/api/v1/ask-analysis/logs/${msgId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      if (data.code !== 0) {
        console.error('删除失败:', data.message)
        // 后端删除失败但仍删除本地（避免用户困惑）
      }
    } catch (e) {
      console.error('删除失败:', e)
      // 网络错误但仍删除本地
    }
  }

  // 从本地列表移除
  messages.value.splice(idx, 1)

  // 如果删除的是当前选中项，清空右边报告
  if (selectedIndex.value === idx) {
    selectedIndex.value = -1
    analysisResult.value = ''
    analysisCharts.value = []
  } else if (selectedIndex.value > idx) {
    selectedIndex.value--
  }
}

// 选择报告
async function selectReport(idx) {
  selectedIndex.value = idx
  const msg = messages.value[idx]
  if (!msg) return

  // 从缓存或后端获取完整报告
  if (msg.fullReport) {
    analysisResult.value = msg.fullReport
  } else if (reportCache.has(msg.id)) {
    analysisResult.value = reportCache.get(msg.id)
  } else if (msg.id) {
    try {
      const token = localStorage.getItem('access_token') || ''
      const res = await fetch(`/api/v1/ask-analysis/logs/${msg.id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      if (data.code === 0 && data.data?.answer) {
        // 清理并渲染 markdown
        let cleaned = data.data.answer
        cleaned = cleaned.replace(/\[\[[\s\S]*?CHART[\s\S]*?\]\]/gi, '')
        cleaned = cleaned.replace(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)/g, '$1$2$3')
        cleaned = cleaned.replace(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/g, '$1$2$3')
        cleaned = cleaned.replace(/([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])/g, '$1$2')
        cleaned = cleaned.replace(/\*\*\s+(.+?)\s+\*\*/g, '**$1**')
        cleaned = cleaned.replace(/M\s*K\s*I-\d+\s*-\s*\d+/g, (m) => m.replace(/\s/g, ''))
        const rendered = DOMPurify.sanitize(marked.parse(cleaned))
        reportCache.set(msg.id, rendered)
        msg.fullReport = rendered
        analysisResult.value = rendered
        // 保存 rawMarkdown 用于后续解析图表
        msg.rawMarkdown = data.data.answer
      }
    } catch (e) {
      console.error('加载报告失败:', e)
      return
    }
  } else {
    return
  }

  // 使用消息中保存的数据设置图表
  if (msg.charts && msg.charts.length > 0) {
    analysisCharts.value = msg.charts
    // 同时设置 rawMarkdown（如果是从后端获取的新消息）
    if (msg.rawMarkdown) {
      rawMarkdown.value = msg.rawMarkdown
    }
  } else if (msg.rawMarkdown) {
    // 没有预解析的 charts，但从 rawMarkdown 解析
    rawMarkdown.value = msg.rawMarkdown
    const { charts } = parseChartDataFromText(msg.rawMarkdown)
    analysisCharts.value = charts
  }

  nextTick(() => initCharts())
}

// 加载历史记录
async function loadHistory() {
  if (!sessionId.value) {
    sessionId.value = generateSessionId()
    localStorage.setItem('analysis_session_id', sessionId.value)
  }

  historyLoading.value = true
  try {
    const token = localStorage.getItem('access_token') || ''
    const res = await fetch(`/api/v1/ask-analysis/logs?session_id=${sessionId.value}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await res.json()
    if (data.code === 0 && data.data?.list) {
      // 预渲染所有报告的 HTML
      const renderMarkdown = (text, charts = []) => {
        if (!text) return ''
        let cleaned = text
        // 移除旧的 [[CHART_BLOCK]] 格式，但保留 [[CHART:N]] 格式
        cleaned = cleaned.replace(/\[\[[\s\S]*?CHART_BLOCK[\s\S]*?\]\]/gi, '')
        cleaned = cleaned.replace(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)/g, '$1$2$3')
        cleaned = cleaned.replace(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/g, '$1$2$3')
        cleaned = cleaned.replace(/([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])/g, '$1$2')
        cleaned = cleaned.replace(/\*\*\s+(.+?)\s+\*\*/g, '**$1**')
        cleaned = cleaned.replace(/M\s*K\s*I-\d+\s*-\s*\d+/g, (m) => m.replace(/\s/g, ''))
        // 嵌入图表
        if (charts.length > 0) {
          // 临时设置 analysisCharts 以便 embedChartsInHtml 使用
          const origCharts = analysisCharts.value
          analysisCharts.value = charts
          const html = embedChartsInHtml(marked.parse(cleaned))
          analysisCharts.value = origCharts
          return DOMPurify.sanitize(html)
        }
        return DOMPurify.sanitize(marked.parse(cleaned))
      }

      messages.value = data.data.list.map(log => {
        // 预解析图表数据
        const { charts } = parseChartDataFromText(log.answer)
        return {
          id: log.id,
          session_id: log.session_id,
          role: 'assistant',
          question: log.question,
          content: '',
          summary: extractSummary(log.answer),
          fullReport: renderMarkdown(log.answer, charts),  // 存渲染后的 HTML
          rawMarkdown: log.answer,  // 保存原始 markdown（包含图表数据）
          charts: charts,  // 保存预解析的图表数据
          thinkingSteps: [],
          totalTime: '',
          created_at: log.created_at
        }
      })
      // 缓存所有报告（渲染后的 HTML）
      data.data.list.forEach(log => {
        reportCache.set(log.id, renderMarkdown(log.answer))
      })
    }
  } catch (e) {
    console.error('加载历史失败:', e)
  } finally {
    historyLoading.value = false
  }
}

function generateSessionId() {
  return 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9)
}

function formatResult(text) {
  if (!text) return ''

  // 清理前后空白字符，确保 ^ 锚点能正确匹配 heading
  text = text.trim()

  // 0. 移除图表数据标记 {CHART_DATA:...} 和 [[CHART_BLOCK]] 占位符
  // 支持多种格式：{CHART_DATA:{...}}, {CHART_DATA:[...]}, {CHART_DATA :...} 等
  // 以及带空格的变化如 {CHART_ BLOCK} 或 [[ CHART_BLOCK ]]
  text = text.replace(/\{ ?CHART[_\s]?DATA[\s\S]*?\}/gi, '')
  // 移除 [[CHART_BLOCK]] 和类似变体，但保留 [[CHART:N]] 格式
  text = text.replace(/\[\[[\s\S]*?CHART_BLOCK[\s\S]*?\]\]/gi, '')
  // 处理单括号的 {CHART_BLOCK} 格式
  text = text.replace(/\{ ?CHART[\s\S]*?\}/gi, '')

  // 1. 预处理：修复 LLM 生成的格式问题
  // 1a. 修复加粗标记周围的空格（如 ** text ** -> **text**）
  text = text.replace(/\*\*\s+(.+?)\s+\*\*/g, '**$1**')
  // 1b. 处理加粗标签
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // 1c. 修复被断开的 markdown 标题（同一行有多个 # 开头，如 "# 标题 ## 二级标题"）
  // 问题：原 regex (?=\s+#{1,6}\s) 要求第二个 heading 后正好一个空格，但实际可能有多个
  // 解决：使用 \s{2,} 匹配两个以上空格，然后插入换行
  text = text.replace(/^(#{1,6}\s+[^\n]+?)\s{2,}(#{1,6}\s+)/gm, '$1\n$2')

  // 1e. 修复 heading 和 table 在同一行的情况（如 "##  数据概览  |  指标 |"）
  // 在 heading 后的 | 前插入换行（| 本身保留在第二行）
  text = text.replace(/^(#{1,6}\s+[^\n]+?)\s+\|/gm, '$1\n|')
  // 1d. 修复标题后的表格行（去掉行首的空格，让表格能被正确识别）
  text = text.replace(/^(#{1,6}\s+.+?)(\s+)(\|)/gm, '$1\n$3')
  // 1f. 修复 table header 和 separator 在同一行的情况（如 "| 指标 | |------|----|"）
  // 匹配: header 的结尾 | + 空白 + separator 的开头 |
  // 替换为: | + 换行 + |
  text = text.replace(/(\|)\s+(\|)/g, '$1\n$2')
  // 1g. 修复 table content 后跟 heading 的情况（如 "| 页面访问量 |  ##  销售趋势分析"）
  // 在 | 后的多个空格 + ## 前插入换行
  text = text.replace(/(\|)\s{2,}(#{1,6}\s)/g, '$1\n$2')
  // 1h. 修复 heading 和 content 在同一行的情况（如 "##  销售趋势分析近30天..."）
  // 使用中文 pattern：heading 以常见词结尾，content 以常见 pattern 开头
  // 在 heading 结束后插入换行
  text = text.replace(/^(#{1,6}\s+[^\n]+?(?:分析|概述|总结|报告))([根从由因当近环比同每按根据])/gm, '$1\n$2')
  // 1i. 修复行中间的 heading（如 "content ...  ##  关键发现"）
  // 在行中间的 ## 前插入换行
  text = text.replace(/([^\n])(\s{2,}#{1,6}\s)/gm, '$1\n$2')
  // 1j. 修复 heading 后紧跟 inline list items 的情况（如 "## 指标数据  - MKI-02-0009:..."）
  // 在 heading 和第一个 list item 之间插入换行
  text = text.replace(/^(#{1,6}\s+[^\n]+?)\s{2,}- /gm, '$1\n\n- ')
  // 1k. 修复 inline list items 连在一起的情况（如 "- item1  - item2  - item3"）
  // 在 "  - " (space-dash-space) 前插入换行
  text = text.replace(/([^\n])(\s+)- (\S)/gm, '$1\n- $3')

  // 2. 规范化行结束符
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n')

  // 3. 分割内容为行
  const lines = text.split('\n')
  const result = []
  let inTable = false
  let inList = false
  let listType = null // 'ul' or 'ol'
  let tableHeaderIndex = -1 // 记录表头行索引

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i]
    const trimmed = line.trim()

    // 空行处理
    if (!trimmed) {
      if (inTable) {
        result.push('</tbody></table>')
        inTable = false
        tableHeaderIndex = -1
      }
      if (inList) {
        result.push(`</${listType}>`)
        inList = false
        listType = null
      }
      continue
    }

    // 表头分隔线检测：只包含 |、空格、-、: 且包含 --- 或类似模式
    const separatorPattern = /^[\|\s\-:]+$/
    const hasDashSequence = /[\-:\s]{3,}/.test(trimmed) || trimmed.includes('---')
    const isTableSeparator = separatorPattern.test(trimmed) && hasDashSequence
    if (isTableSeparator) {
      continue
    }

    // 表格行检测（| 开头和结尾）
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (inList) {
        result.push(`</${listType}>`)
        inList = false
        listType = null
      }
      if (!inTable) {
        result.push('<table class="result-table"><tbody>')
        inTable = true
        tableHeaderIndex = i
      }
      // 解析表格单元格：先移除首尾的 |
      const cellContent = trimmed.slice(1, -1)
      const cells = cellContent.split('|').map(c => c.trim()).filter(c => c && c !== '---')
      if (cells.length > 0) {
        // 判断是否是表头行
        const isHeader = tableHeaderIndex === i
        const tag = isHeader ? 'th' : 'td'
        // 清理单元格内容
        const cleanCells = cells.map(c => c.replace(/\s+/g, ' '))
        result.push('<tr>' + cleanCells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>')
      }
      continue
    }

    // 关闭表格
    if (inTable) {
      result.push('</tbody></table>')
      inTable = false
      tableHeaderIndex = -1
    }

    // 标题处理（支持行首的 # 标记）
    if (trimmed.startsWith('### ')) {
      if (inList) { result.push(`</${listType}>`); inList = false; listType = null }
      result.push(`<h3>${trimmed.slice(4)}</h3>`)
      continue
    }
    if (trimmed.startsWith('## ')) {
      if (inList) { result.push(`</${listType}>`); inList = false; listType = null }
      result.push(`<h2>${trimmed.slice(3)}</h2>`)
      continue
    }
    if (trimmed.startsWith('# ')) {
      if (inList) { result.push(`</${listType}>`); inList = false; listType = null }
      result.push(`<h1>${trimmed.slice(2)}</h1>`)
      continue
    }

    // 列表项处理（- 或 * 开头）
    if (trimmed.match(/^[\-\*] /)) {
      if (!inList || listType !== 'ul') {
        if (inList) result.push(`</${listType}>`)
        result.push('<ul class="result-list">')
        inList = true
        listType = 'ul'
      }
      const content = trimmed.slice(2)
      result.push(`<li>${content}</li>`)
      continue
    }

    // 序号列表（如 1. 或 1) 开头）
    if (trimmed.match(/^\d+[.\)]\s/)) {
      if (!inList || listType !== 'ol') {
        if (inList) result.push(`</${listType}>`)
        result.push('<ol class="result-list">')
        inList = true
        listType = 'ol'
      }
      const content = trimmed.replace(/^\d+[.\)]\s/, '')
      result.push(`<li>${content}</li>`)
      continue
    }

    // 关闭列表
    if (inList) {
      result.push(`</${listType}>`)
      inList = false
      listType = null
    }

    // 普通段落
    result.push(`<p>${trimmed}</p>`)
  }

  // 关闭未关闭的标签
  if (inTable) result.push('</tbody></table>')
  if (inList) result.push(`</${listType}>`)

  return result.join('')
}

function parseChartData() {
  // 使用全局 rawMarkdown
  return parseChartDataFromText(rawMarkdown.value, (cleanedText) => {
    analysisResult.value = cleanedText
  })
}

// 从文本解析图表数据
function parseChartDataFromText(text, onCleaned) {
  const charts = []
  const prefix = '{CHART_DATA:'

  if (!text) {
    return { charts: [], cleanedText: text }
  }

  if (!text) {
    return { charts: [], cleanedText: text }
  }

  // 第一遍：找到所有 CHART_DATA 的起止位置
  const ranges = []
  let searchStart = 0

  while (searchStart < text.length) {
    const chartStart = text.indexOf(prefix, searchStart)
    if (chartStart === -1) break

    // 从 CHART_DATA: 后开始找对应的结束括号
    const jsonStart = chartStart + prefix.length
    let braceCount = 0
    let jsonEnd = -1

    for (let i = jsonStart; i < text.length; i++) {
      if (text[i] === '{') {
        braceCount++
      } else if (text[i] === '}') {
        braceCount--
        if (braceCount === 0) {
          jsonEnd = i
          break
        }
      }
    }

    if (jsonEnd !== -1) {
      ranges.push({ start: chartStart, end: jsonEnd + 1 })
      searchStart = jsonEnd + 1
    } else {
      break
    }
  }

  // 提取每个 CHART_DATA 的 JSON
  for (const range of ranges) {
    const jsonStr = text.substring(range.start + prefix.length, range.end)
    try {
      const chartData = JSON.parse(jsonStr)
      charts.push(chartData)
    } catch (e) {
      console.error('Chart JSON parse error:', e)
    }
  }

  // 从文本中移除所有 CHART_DATA 块（从后往前移除，避免索引偏移）
  let cleanedText = text
  if (ranges.length > 0) {
    ranges.sort((a, b) => b.start - a.start)
    for (const range of ranges) {
      cleanedText = cleanedText.substring(0, range.start) + cleanedText.substring(range.end)
    }
  }

  // 如果提供了回调，调用它来处理清理后的文本
  if (onCleaned) {
    onCleaned(cleanedText)
  }

  return { charts, cleanedText }
}

function buildEChartsOption(chartData) {
  // chartData 现在是单个图表对象，不是包含 charts 数组的对象
  if (!chartData || !chartData.title) return null

  const firstChart = chartData
  const baseSeries = firstChart.series || []

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: firstChart.title,
      left: 'left',
      textStyle: { fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#E5E7EB',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)' }
    },
    legend: {
      bottom: 0,
      data: baseSeries.map(s => s.name)
    },
    grid: {
      left: 50,
      right: 20,
      top: 40,
      bottom: 40
    },
    xAxis: {
      type: 'category',
      data: firstChart.xData,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'var(--text-muted)' }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#E5E7EB' } },
      axisLabel: { color: 'var(--text-muted)' }
    },
    series: []
  }

  if (firstChart.type === 'pie') {
    option.series = [{
      name: baseSeries[0]?.name || firstChart.title,
      type: 'pie',
      radius: '60%',
      data: baseSeries[0]?.data || [],
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      },
      label: { color: 'var(--text-secondary)' }
    }]
  } else {
    option.series = baseSeries.map((s, idx) => {
      const isLine = firstChart.type === 'line'
      return {
        name: s.name,
        type: firstChart.type || 'line',
        data: s.data,
        smooth: isLine ? 0.4 : false,
        ...(isLine ? {
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(22, 119, 255, 0.12)' },
                { offset: 1, color: 'rgba(22, 119, 255, 0)' }
              ]
            }
          },
          lineStyle: { color: '#1677FF', width: 2 },
          itemStyle: { color: '#1677FF' }
        } : {
          barWidth: '50%',
          itemStyle: { color: '#1677FF', borderRadius: firstChart.type === 'bar' ? [4, 4, 0, 0] : 0 }
        })
      }
    })
  }

  return option
}

// 把 [[CHART:N]] 标记替换成图表 HTML
function embedChartsInHtml(html) {
  if (!html || !analysisCharts.value.length) return html

  const result = html.replace(/\[\[CHART:(\d+)\]\]/g, (match, index) => {
    const chartIndex = parseInt(index, 10)
    const chartData = analysisCharts.value[chartIndex]
    if (!chartData) return ''
    const title = chartData.title || `图表 ${chartIndex + 1}`
    return `<div class="chart-embed" data-chart-index="${chartIndex}">
      <div class="chart-embed-title">${title}</div>
      <div class="chart-embed-container"></div>
    </div>`
  })
  return result
}

function initCharts() {
  const t0 = performance.now()
  // 先查找所有嵌入式图表容器
  const containers = document.querySelectorAll('.chart-embed-container[data-chart-index]')
  console.log('[耗时] initCharts查找容器:', Math.round(performance.now() - t0), 'ms, 数量:', containers.length)
  containers.forEach(container => {
    const index = parseInt(container.getAttribute('data-chart-index'), 10)
    const chartData = analysisCharts.value[index]
    if (!chartData) return

    let chart = echarts.getInstanceByDom(container)
    if (!chart) {
      chart = echarts.init(container)
    }

    const option = buildEChartsOption(chartData)
    if (option) {
      chart.setOption(option)
    }
  })
  console.log('[耗时] initCharts完成, 总耗时:', Math.round(performance.now() - t0), 'ms')

  // 旧的 chartRefs 方式仍然保留，作为备用
  analysisCharts.value.forEach((chartData, index) => {
    const container = chartRefs.value[index]
    if (!container) return

    let chart = echarts.getInstanceByDom(container)
    if (!chart) {
      chart = echarts.init(container)
    }

    const option = buildEChartsOption(chartData)
    if (option) {
      chart.setOption(option)
    }
  })
}

function handleResize() {
  chartRefs.value.forEach(chart => {
    if (chart) {
      chart.resize()
    }
  })
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  // 避免重复加载
  if (messages.value.length === 0) {
    loadHistory()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartRefs.value.forEach(chart => {
    if (chart) {
      chart.dispose()
    }
  })
})

async function clearChat() {
  const sid = sessionId.value
  // 调用后端清除会话
  try {
    const token = localStorage.getItem('access_token') || ''
    // 1. 清除 Python AI 服务会话（使用内部接口，不需要认证）
    await fetch(`/api/v1/internal/ask/clear?session_id=${sid}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    // 2. 清除 Go 后端的日志记录
    await fetch(`/api/v1/ask-analysis/logs?session_id=${sid}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })
  } catch (e) {
    console.error('清除会话失败:', e)
  }
  // 清除本地状态
  messages.value = []
  analysisResult.value = ''
  analysisCharts.value = []
  selectedIndex.value = -1
  reportCache.clear()
  // Dispose charts
  chartRefs.value.forEach(chart => {
    if (chart) chart.dispose()
  })
  chartRefs.value = []
  // 生成新的 sessionId
  sessionId.value = generateSessionId()
  localStorage.setItem('analysis_session_id', sessionId.value)
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function copyResult() {
  navigator.clipboard.writeText(analysisResult.value)
}

function exportResult() {
  const blob = new Blob([analysisResult.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `分析报告_${new Date().toISOString().slice(0, 10)}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
/* === 页面基础 === */
.analysis-page {
  min-height: 100vh;
  background: var(--bg-primary);
  position: relative;
  overflow: hidden;
}

.bg-gradient {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 300px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 50%, transparent 100%);
  opacity: 0.05;
  pointer-events: none;
}

.bg-grid {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image:
    linear-gradient(rgba(30, 64, 175, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(30, 64, 175, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
}

/* === 主容器 === */
.analysis-container {
  display: flex;
  gap: 20px;
  padding: 20px 24px;
  height: calc(100vh - 60px);
  max-width: 1600px;
  margin: 0 auto;
}

/* === 面板通用样式 === */
.chat-panel,
.result-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.chat-panel {
  width: 440px;
  flex-shrink: 0;
}

.result-panel {
  flex: 1;
  min-width: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(135deg, rgba(30, 64, 175, 0.03) 0%, transparent 100%);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-title svg {
  color: var(--primary);
}

.icon-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-muted);
  transition: all 0.2s ease;
}

.icon-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.mode-toggle {
  display: flex;
  background: var(--bg-primary);
  border-radius: 8px;
  padding: 2px;
  gap: 2px;
}

.mode-toggle span {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.mode-toggle span.active {
  background: var(--primary);
  color: white;
}

/* === 消息区域 === */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 16px;
}

.empty-icon {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border-radius: 20px;
  color: var(--primary);
  opacity: 0.6;
}

.empty-state p {
  font-size: 14px;
  margin: 0;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-avatar {
  background: linear-gradient(135deg, #3B82F6 0%, #1E40AF 100%);
  color: white;
}

.ai-avatar {
  background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
  color: white;
}

.message.user .avatar {
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
}

.message-content {
  max-width: 80%;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
}

.message.user .message-bubble {
  background: var(--bg-primary);
  border-bottom-right-radius: 4px;
}

.message.assistant .message-bubble {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  color: white;
  border-bottom-left-radius: 4px;
}

.message-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
  padding: 0 4px;
}

.message.user .message-time {
  text-align: right;
}

.message-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
  padding: 0 4px;
}

.delete-btn {
  opacity: 0.5;
  background: none;
  border: none;
  padding: 4px;
  cursor: pointer;
  color: var(--text-muted);
  border-radius: 4px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 16px 20px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--text-muted);
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-8px); opacity: 1; }
}

/* === 输入区域 === */
.input-area {
  padding: 16px 20px 20px;
  border-top: 1px solid var(--border);
  background: var(--bg-card);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 12px 12px 16px;
  transition: all 0.2s ease;
}

.input-wrapper:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
}

.input-wrapper textarea {
  flex: 1;
  border: none;
  background: transparent;
  resize: none;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
  outline: none;
}

.input-wrapper textarea::placeholder {
  color: var(--text-muted);
}

.send-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  border-radius: 10px;
  cursor: pointer;
  color: white;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(30, 64, 175, 0.3);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.input-hint {
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
  margin-top: 8px;
}

/* === 结果区域 === */
.result-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.result-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--text-muted);
}

.empty-illustration {
  margin-bottom: 24px;
  opacity: 0.4;
}

.result-empty h4 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.result-empty p {
  font-size: 14px;
  margin: 0 0 24px;
}

.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 400px;
}

.prompt-label {
  font-size: 12px;
  color: var(--text-muted);
  width: 100%;
  margin-bottom: 4px;
}

.prompt-chip {
  padding: 8px 16px;
  border: 1px solid var(--border);
  background: var(--bg-primary);
  border-radius: 20px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.prompt-chip:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: rgba(30, 64, 175, 0.05);
}

/* 加载动画 */
.result-loading {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
}

.loading-animation {
  position: relative;
  width: 100px;
  height: 100px;
}

.pulse-ring {
  position: absolute;
  inset: 0;
  border: 2px solid var(--primary);
  border-radius: 50%;
  opacity: 0;
  animation: pulse-out 2s infinite;
}

.pulse-ring.delay-1 { animation-delay: 0.5s; }
.pulse-ring.delay-2 { animation-delay: 1s; }

@keyframes pulse-out {
  0% { transform: scale(0.5); opacity: 0.8; }
  100% { transform: scale(1.5); opacity: 0; }
}

.pulse-center {
  position: absolute;
  inset: 25px;
  background: var(--primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.result-loading p {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
}

/* 结果文本 */
.result-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
}

/* 限制报告中的图片大小 */
.result-text img {
  max-width: 120px;
  height: auto;
  float: right;
}

/* 报告 logo 图片，禁用重复加载 */
.report-logo-img {
  pointer-events: none;
}

/* 打字机效果文字 */
.typewriter-text {
  font-family: 'Courier New', monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 表格样式 */
.result-text table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  table-layout: fixed;
}

.result-text td, .result-text th {
  padding: 8px 12px;
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  border: 1px solid var(--border);
}

.result-text th {
  background: var(--bg-primary);
  font-weight: 600;
}

.result-text td {
  font-weight: normal;
}

.result-text h1, .result-text h2, .result-text h3 {
  color: var(--text-primary);
  margin: 24px 0 16px;
}

.result-text h1:first-child,
.result-text h2:first-child,
.result-text h3:first-child {
  margin-top: 0;
}

.result-text ul, .result-text ol {
  padding-left: 24px;
  margin: 16px 0;
}

.result-text li {
  margin: 8px 0;
}

.result-text strong {
  color: var(--primary);
  font-weight: 600;
}

.result-text code {
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
}

/* 嵌入式图表样式 */
.chart-embed {
  margin: 24px 0;
  padding: 16px;
  background: var(--bg-primary);
  border-radius: 12px;
}

.chart-embed-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  text-align: left;
}

.chart-embed-container {
  width: 100%;
  height: 320px;
}

/* 图表区域 */
.charts-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
}

.chart-wrapper {
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 16px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  text-align: left;
}

.chart-container {
  width: 100%;
  height: 320px;
}

/* 底部操作 */
.result-actions {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  background: var(--bg-primary);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

/* 进度徽章 */
.progress-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(30, 64, 175, 0.1);
  border-radius: 20px;
  font-size: 12px;
  color: var(--primary);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(30, 64, 175, 0.2);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 耗时步骤面板 */
.thinking-steps-panel {
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--border);
}

.thinking-steps-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.thinking-steps-header svg {
  color: var(--primary);
}

.total-time {
  margin-left: auto;
  font-size: 12px;
  color: var(--primary);
  background: rgba(30, 64, 175, 0.08);
  padding: 2px 8px;
  border-radius: 10px;
}

.thinking-steps-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.thinking-step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-card);
  border-radius: 8px;
  transition: all 0.2s ease;
}

.thinking-step-item.active {
  background: rgba(30, 64, 175, 0.06);
  border: 1px solid rgba(30, 64, 175, 0.2);
}

.thinking-step-item.done {
  opacity: 0.7;
}

.step-indicator {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-dot {
  width: 8px;
  height: 8px;
  background: var(--text-muted);
  border-radius: 50%;
}

.spin-path {
  animation: spin 1s linear infinite;
  transform-origin: center;
}

.step-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
  min-width: 0;
}

.step-name {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-time {
  font-size: 12px;
  font-family: 'Fira Code', monospace;
  color: var(--primary);
  flex-shrink: 0;
  margin-left: 12px;
  background: rgba(30, 64, 175, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
}

/* 流式耗时气泡样式 */
.thinking-bubble {
  background: linear-gradient(135deg, rgba(30, 64, 175, 0.08) 0%, rgba(30, 64, 175, 0.03) 100%) !important;
  border: 1px solid rgba(30, 64, 175, 0.15) !important;
  color: var(--text-primary) !important;
  padding: 14px 16px !important;
}

.thinking-steps-stream {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  padding-bottom: 8px;
  border-bottom: 1px dashed rgba(30, 64, 175, 0.2);
}

.thinking-header svg {
  animation: spin 2s linear infinite;
}

.thinking-header .total-time {
  margin-left: auto;
  font-size: 11px;
  background: rgba(30, 64, 175, 0.1);
  padding: 2px 8px;
  border-radius: 10px;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
}

.step-item.active {
  color: var(--primary);
  font-weight: 500;
}

.step-item .step-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.step-item .step-icon svg {
  animation: spin 1.5s linear infinite;
}

.step-item .step-label {
  flex: 1;
}

.step-item .step-dur {
  font-size: 11px;
  font-family: 'Fira Code', monospace;
  color: var(--primary);
  opacity: 0.8;
}

/* 骨架屏动画 */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.skeleton-card {
  display: flex;
  gap: 12px;
  animation: pulse 1.5s ease-in-out infinite;
}

.skeleton-avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: var(--bg-primary);
  flex-shrink: 0;
}

.skeleton-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background: var(--bg-primary);
}

.skeleton-line.short { width: 40%; }
.skeleton-line.medium { width: 70%; }
.skeleton-line.long { width: 100%; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 摘要卡片 */
.summary-card {
  cursor: pointer;
  transition: all 0.2s ease;
}

.summary-card:hover .summary-bubble {
  border-color: rgba(30, 64, 175, 0.4);
  box-shadow: 0 4px 16px rgba(30, 64, 175, 0.15);
  transform: translateY(-2px);
}

.summary-card.active .summary-bubble {
  border-color: var(--primary);
  border-left: 3px solid var(--primary);
}

.summary-bubble {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  transition: all 0.2s ease;
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.summary-badge {
  background: rgba(22, 163, 74, 0.1);
  color: #16a34a;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.summary-time {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'Fira Code', monospace;
}

.summary-question {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border);
}

.summary-body {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}

.summary-action {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  font-size: 12px;
  color: var(--primary);
  font-weight: 500;
}

/* 消息选中高亮 */
.message.assistant.active {
  background: rgba(30, 64, 175, 0.03);
  border-radius: 12px;
}
</style>
