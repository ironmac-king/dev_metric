<template>
  <teleport to="body">
    <transition name="overlay">
      <div v-if="visible" class="report-overlay" @click.self="handleClose">
        <div class="report-container">
          <!-- Header -->
          <div class="report-header">
            <div class="header-left">
              <h1 class="report-title">{{ title }}</h1>
              <span class="report-meta">{{ generateTime }}</span>
            </div>
            <div class="header-actions">
              <button class="action-btn primary" @click="handleExportPdf">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M3 2H10L13 5V14H3V2Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
                  <path d="M10 2V5H13M6 8H10M6 11H10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
                导出PDF
              </button>
              <button class="action-btn" @click="handleCopy">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
                  <path d="M2 11V3H10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                {{ copied ? '已复制' : '复制内容' }}
              </button>
              <button class="action-btn" @click="handleSendEmail">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <rect x="1" y="3" width="14" height="10" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
                  <path d="M1 5L8 9L15 5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
                发送邮件
              </button>
              <button class="close-btn" @click="handleClose">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- Report Body -->
          <div class="report-body" ref="reportBodyRef">
            <!-- Summary Section -->
            <section v-if="summary" class="report-section">
              <h2 class="section-title">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.2"/>
                  <path d="M5 8H11M5 5H11M5 11H9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
                摘要
              </h2>
              <p class="summary-text">{{ summary }}</p>
            </section>

            <!-- Core Cards -->
            <section v-if="coreCards && coreCards.length > 0" class="report-section">
              <h2 class="section-title">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <rect x="1" y="4" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/>
                  <rect x="9" y="4" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/>
                  <rect x="5" y="9" width="6" height="5" rx="1" stroke="currentColor" stroke-width="1.2"/>
                </svg>
                核心指标
              </h2>
              <div class="core-cards-grid">
                <div
                  v-for="(card, idx) in coreCards"
                  :key="idx"
                  class="core-card"
                  :class="{ positive: card.trend >= 0, negative: card.trend < 0 }"
                >
                  <span class="card-label">{{ card.label }}</span>
                  <span class="card-value">{{ card.value }}</span>
                  <span class="card-trend">
                    <svg v-if="card.trend >= 0" width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M6 9V3M6 3L3 6M6 3L9 6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <svg v-else width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M6 3V9M6 9L3 6M6 9L9 6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    {{ card.trend >= 0 ? '+' : '' }}{{ card.trend }}%
                  </span>
                </div>
              </div>
            </section>

            <!-- Detail List -->
            <section v-if="detailList && detailList.length > 0" class="report-section">
              <h2 class="section-title">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M2 4H14M2 8H14M2 12H14" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
                详细列表
              </h2>
              <table class="detail-table">
                <thead>
                  <tr>
                    <th v-for="(header, idx) in detailHeaders" :key="idx">{{ header }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rowIdx) in detailList" :key="rowIdx">
                    <td v-for="(header, colIdx) in detailHeaders" :key="colIdx">
                      <span :class="{ positive: isPositive(row[header]), negative: isNegative(row[header]) }">
                        {{ row[header] }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>

            <!-- Expert Suggestions -->
            <section v-if="suggestions && suggestions.length > 0" class="report-section">
              <h2 class="section-title">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.2"/>
                  <path d="M8 5V9M8 11V11.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                专家建议
              </h2>
              <ul class="suggestions-list">
                <li v-for="(sug, idx) in suggestions" :key="idx">{{ sug }}</li>
              </ul>
            </section>
          </div>

          <!-- Footer -->
          <div class="report-footer">
            <span>由智能小Q自动生成</span>
            <span>{{ currentTime }}</span>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '数据分析报告'
  },
  summary: {
    type: String,
    default: ''
  },
  coreCards: {
    type: Array,
    default: () => []
  },
  detailList: {
    type: Array,
    default: () => []
  },
  detailHeaders: {
    type: Array,
    default: () => []
  },
  suggestions: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:visible', 'export', 'copy', 'email'])

const reportBodyRef = ref(null)
const copied = ref(false)

const generateTime = computed(() => {
  const now = new Date()
  return now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
})

const currentTime = computed(() => {
  return new Date().toLocaleString('zh-CN')
})

function handleClose() {
  emit('update:visible', false)
}

function handleExportPdf() {
  emit('export', reportBodyRef.value)
}

async function handleCopy() {
  try {
    const text = extractReportText()
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('复制失败:', err)
  }
}

function handleSendEmail() {
  emit('email', extractReportText())
}

function extractReportText() {
  let text = `${props.title}\n${'='.repeat(40)}\n\n`
  if (props.summary) {
    text += `【摘要】\n${props.summary}\n\n`
  }
  if (props.coreCards && props.coreCards.length > 0) {
    text += `【核心指标】\n`
    props.coreCards.forEach(card => {
      text += `· ${card.label}：${card.value} (${card.trend >= 0 ? '+' : ''}${card.trend}%)\n`
    })
    text += '\n'
  }
  if (props.detailList && props.detailList.length > 0) {
    text += `【详细列表】\n`
    text += props.detailHeaders.join('\t') + '\n'
    props.detailList.forEach(row => {
      text += props.detailHeaders.map(h => row[h]).join('\t') + '\n'
    })
    text += '\n'
  }
  if (props.suggestions && props.suggestions.length > 0) {
    text += `【专家建议】\n`
    props.suggestions.forEach((sug, idx) => {
      text += `${idx + 1}. ${sug}\n`
    })
  }
  return text
}

function isPositive(val) {
  if (typeof val === 'string') {
    return val.startsWith('+') || val.startsWith('正')
  }
  if (typeof val === 'number') {
    return val >= 0
  }
  return false
}

function isNegative(val) {
  if (typeof val === 'string') {
    return val.startsWith('-') || val.startsWith('负')
  }
  if (typeof val === 'number') {
    return val < 0
  }
  return false
}
</script>

<style scoped>
.report-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 40px;
  overflow-y: auto;
}

.report-container {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 900px;
  min-height: 600px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

/* Header */
.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 28px;
  border-bottom: 1px solid #e5e7eb;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.report-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f1f1f;
  margin: 0;
}

.report-meta {
  font-size: 12px;
  color: #9ca3af;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #f9fafb;
  border-color: #d1d5db;
}

.action-btn.primary {
  background: #6366F1;
  border-color: #6366F1;
  color: #fff;
}

.action-btn.primary:hover {
  background: #5558E3;
}

.close-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
  margin-left: 8px;
}

.close-btn:hover {
  background: #f3f4f6;
  color: #1f1f1f;
}

/* Body */
.report-body {
  flex: 1;
  padding: 28px;
  overflow-y: auto;
}

.report-section {
  margin-bottom: 32px;
}

.report-section:last-child {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
  margin: 0 0 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid #6366F1;
}

.section-title svg {
  color: #6366F1;
}

.summary-text {
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
  margin: 0;
}

/* Core Cards */
.core-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.core-card {
  background: #f9fafb;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 1px solid #e5e7eb;
}

.core-card.positive {
  border-color: rgba(16, 185, 129, 0.3);
  background: rgba(16, 185, 129, 0.04);
}

.core-card.negative {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.04);
}

.card-label {
  font-size: 12px;
  color: #6b7280;
}

.card-value {
  font-size: 24px;
  font-weight: 700;
  color: #1f1f1f;
}

.card-trend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
}

.core-card.positive .card-trend {
  color: #10B981;
}

.core-card.negative .card-trend {
  color: #EF4444;
}

/* Detail Table */
.detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.detail-table th {
  text-align: left;
  padding: 10px 12px;
  background: #f3f4f6;
  color: #6b7280;
  font-weight: 600;
  border-bottom: 1px solid #e5e7eb;
}

.detail-table td {
  padding: 12px;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
}

.detail-table tr:last-child td {
  border-bottom: none;
}

.detail-table .positive {
  color: #10B981;
  font-weight: 500;
}

.detail-table .negative {
  color: #EF4444;
  font-weight: 500;
}

/* Suggestions */
.suggestions-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.suggestions-list li {
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
}

/* Footer */
.report-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 28px;
  background: #f9fafb;
  border-top: 1px solid #e5e7eb;
  border-radius: 0 0 16px 16px;
  font-size: 11px;
  color: #9ca3af;
}

/* Transitions */
.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.3s;
}

.overlay-enter-active .report-container,
.overlay-leave-active .report-container {
  transition: transform 0.3s, opacity 0.3s;
}

.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}

.overlay-enter-from .report-container,
.overlay-leave-to .report-container {
  transform: scale(0.95);
  opacity: 0;
}
</style>
