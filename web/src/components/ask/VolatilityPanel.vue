<template>
  <el-drawer
    v-model="visible"
    :direction="isMobile ? 'btt' : 'rtl'"
    :size="isMobile ? '100%' : '480'"
    :show-close="false"
    class="volatility-panel"
    :class="{ 'mobile-panel': isMobile }"
  >
    <template #header>
      <div class="drawer-header">
        <div class="drawer-title">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 14L7 9L10 12L17 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>{{ panelTitle }}</span>
        </div>
        <button class="close-btn" @click="handleClose">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </template>

    <div class="drawer-content">
      <!-- Mobile Tabs -->
      <div v-if="isMobile" class="mobile-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['tab-btn', { active: currentTab === tab.key }]"
          @click="currentTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Phase 1: Overview -->
      <div v-show="!isMobile || currentTab === 'overview'" class="section">
        <div class="section-header">
          <div class="section-label">
            <span :class="['status-dot', phaseStatus.overview]"></span>
            指标概况
          </div>
        </div>
        <div v-if="state.overview" class="overview-grid">
          <div class="kpi-card">
            <div class="kpi-label">当前值</div>
            <div class="kpi-value">{{ formatValue(state.overview.current_value) }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">环比</div>
            <div :class="['kpi-value', state.overview.mom_change >= 0 ? 'positive' : 'negative']">
              {{ state.overview.mom_change_pct }}
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">同比</div>
            <div :class="['kpi-value', state.overview.yoy_change >= 0 ? 'positive' : 'negative']">
              {{ state.overview.yoy_change_pct }}
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">波动率</div>
            <div :class="['kpi-value', getVolatilityClass(state.overview.volatility_rate)]">
              {{ state.overview.volatility_rate_pct }}
            </div>
          </div>
          <div class="kpi-card anomaly" :class="{ 'is-anomaly': state.overview.is_anomaly }">
            <div class="kpi-label">状态</div>
            <div class="kpi-value">
              <span v-if="state.overview.is_anomaly" class="anomaly-tag">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 1L11 10H1L6 1Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
                  <path d="M6 5V7M6 8.5V9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
                {{ state.overview.anomaly_level }}
              </span>
              <span v-else class="normal-tag">正常</span>
            </div>
          </div>
        </div>
        <div v-else class="skeleton-grid">
          <div v-for="i in 5" :key="i" class="skeleton-card"></div>
        </div>
      </div>

      <!-- Phase 2: Chart -->
      <div v-show="!isMobile || currentTab === 'volatility'" class="section">
        <div class="section-header">
          <div class="section-label">
            <span :class="['status-dot', phaseStatus.chart]"></span>
            波动幅度
          </div>
        </div>
        <div v-if="state.chartData && state.chartData.length > 0" class="chart-wrapper">
          <ChartCard
            :data="state.chartData"
            :height="180"
            :type="state.chartType || 'line'"
          />
        </div>
        <div v-else class="skeleton-chart"></div>
      </div>

      <!-- Phase 3: Drivers -->
      <div v-show="!isMobile || currentTab === 'drivers'" class="section">
        <div class="section-header">
          <div class="section-label">
            <span :class="['status-dot', phaseStatus.drivers]"></span>
            核心驱动
          </div>
        </div>
        <div v-if="state.positiveDims.length > 0 || state.negativeDims.length > 0">
          <!-- Positive -->
          <div v-if="state.positiveDims.length > 0" class="drivers-group">
            <div class="drivers-header positive">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 3V11M7 3L4 6M7 3L10 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span>正向驱动</span>
            </div>
            <div class="drivers-list">
              <div v-for="(dim, idx) in state.positiveDims" :key="'pos-' + idx" class="driver-item">
                <div class="driver-info">
                  <span class="driver-rank">{{ idx + 1 }}</span>
                  <span class="driver-name">{{ dim.name }}</span>
                  <span class="driver-contribution positive">+{{ dim.contribution.toFixed(1) }}%</span>
                </div>
                <div class="driver-bar">
                  <div class="driver-bar-fill positive" :style="{ width: getDriverBarWidth(dim.contribution) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>
          <!-- Negative -->
          <div v-if="state.negativeDims.length > 0" class="drivers-group">
            <div class="drivers-header negative">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 11V3M7 11L4 8M7 11L10 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span>负向拖累</span>
            </div>
            <div class="drivers-list">
              <div v-for="(dim, idx) in state.negativeDims" :key="'neg-' + idx" class="driver-item">
                <div class="driver-info">
                  <span class="driver-rank">{{ idx + 1 }}</span>
                  <span class="driver-name">{{ dim.name }}</span>
                  <span class="driver-contribution negative">{{ dim.contribution.toFixed(1) }}%</span>
                </div>
                <div class="driver-bar">
                  <div class="driver-bar-fill negative" :style="{ width: getDriverBarWidth(dim.contribution) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="skeleton-list">
          <div v-for="i in 3" :key="i" class="skeleton-item"></div>
        </div>
      </div>

      <!-- Phase 4: LLM Reasoning -->
      <div v-show="!isMobile || currentTab === 'reasoning'" class="section reasoning-section">
        <div class="section-header">
          <div class="section-label">
            <span :class="['status-dot', phaseStatus.reasoning]"></span>
            LLM 根因推理
          </div>
        </div>
        <div class="reasoning-content">
          <div v-if="state.llmThinking" class="thinking-stream">
            <div class="thinking-text">{{ state.llmThinking }}</div>
          </div>
          <div v-if="state.rootCause" class="root-cause-card">
            <div class="cause-label">根因归类</div>
            <div class="cause-value">{{ state.rootCause }}</div>
            <div class="confidence-bar">
              <div class="confidence-label">置信度</div>
              <div class="confidence-value">{{ (state.confidence * 100).toFixed(0) }}%</div>
              <div class="confidence-track">
                <div class="confidence-fill" :style="{ width: (state.confidence * 100) + '%' }"></div>
              </div>
            </div>
          </div>
          <div v-if="state.suggestion" class="suggestion-card">
            <div class="suggestion-label">分析建议</div>
            <div class="suggestion-text">{{ state.suggestion }}</div>
          </div>
          <div v-if="!state.rootCause && !state.llmThinking" class="reasoning-loading">
            <div class="loading-dots">
              <span></span><span></span><span></span>
            </div>
            <div class="loading-text">LLM 正在分析中...</div>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import ChartCard from './ChartCard.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  metricName: {
    type: String,
    default: ''
  },
  apiUrl: {
    type: String,
    default: '/api/v1/llm-ask/v2/volatility/stream'
  }
})

const emit = defineEmits(['update:modelValue', 'close'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// Mobile detection
const isMobile = ref(window.innerWidth < 768)
const currentTab = ref('overview')
const tabs = [
  { key: 'overview', label: '概况' },
  { key: 'volatility', label: '波动' },
  { key: 'drivers', label: '驱动' },
  { key: 'reasoning', label: '推理' }
]

const panelTitle = computed(() => {
  if (!props.metricName) return '分析报告'
  // 分类数据（品类分析）vs 时间序列（波动分析）
  const isCategory = state.value.overview?.data_type === 'category'
  const suffix = isCategory ? '品类分析' : '波动分析'
  return `${props.metricName} ${suffix}`
})

// State management
const state = ref({
  overview: null,
  chartData: [],
  chartType: 'line',  // 'line' or 'bar'
  positiveDims: [],
  negativeDims: [],
  rootCause: '',
  suggestion: '',
  llmThinking: '',
  llmStage: '',
  confidence: 0
})

const phaseStatus = computed(() => ({
  overview: state.value.overview ? 'done' : 'loading',
  chart: state.value.chartData.length > 0 ? 'done' : (state.value.overview ? 'loading' : 'pending'),
  drivers: (state.value.positiveDims.length > 0 || state.value.negativeDims.length > 0) ? 'done' : (state.value.chartData.length > 0 ? 'loading' : 'pending'),
  reasoning: state.value.rootCause ? 'done' : (state.value.llmThinking ? 'loading' : 'pending')
}))

const eventSource = ref(null)

// Methods
function formatValue(val) {
  if (typeof val !== 'number') return val
  if (Math.abs(val) >= 10000) {
    return (val / 10000).toFixed(2) + '万'
  }
  return val.toFixed(2)
}

function getVolatilityClass(rate) {
  if (rate > 0.25) return 'anomaly'
  if (rate > 0.15) return 'warning'
  return 'normal'
}

function getDriverBarWidth(contribution) {
  return Math.min(Math.abs(contribution) * 2, 100) // Scale for visibility
}

function handleClose() {
  stopStream()
  visible.value = false
  emit('close')
}

function stopStream() {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
}

function startStream(data) {
  stopStream()
  // Reset state
  state.value = {
    overview: null,
    chartData: [],
    chartType: 'line',  // default to line, updated by SSE
    positiveDims: [],
    negativeDims: [],
    rootCause: '',
    suggestion: '',
    llmThinking: '',
    llmStage: '',
    confidence: 0
  }

  // DEBUG: log raw data
  const rawData = Array.isArray(data.data) ? data.data : []
  const transformedData = transformToVolatilityFormat(rawData, data.dimension_key || 'dimension')

  const requestData = {
    metric_name: data.metric_name || props.metricName,
    data: transformedData,
    dimension_key: data.dimension_key || 'dimension',
    // 传递SQL层计算好的mom/yoy
    mom_change: data.mom_change ?? null,
    yoy_change: data.yoy_change ?? null
  }

  fetchVolatilityData(requestData)
}

/**
 * Transform chat result data to volatility analysis format
 * Backend expects: [{date, value, dimension}]
 */
function transformToVolatilityFormat(rawData, dimensionKey) {
  if (!rawData || rawData.length === 0) return []

  const result = []
  const firstRow = rawData[0]
  const keys = Object.keys(firstRow)

  // 1. Detect date column - EXACT match for FDATE first, then other patterns
  const dateKey = keys.find(k => /^FDATE$/i.test(k)) ||
    keys.find(k => /date|time|日期|时间|day|year|周期/i.test(k) && !/month/i.test(k))

  // 2. Detect value column - look for actual numeric values, excluding date columns
  // Priority: numeric column > string number column (not a date)
  let valueKey = keys.find(k =>
    typeof firstRow[k] === 'number' &&
    k !== dateKey
  )

  if (!valueKey) {
    // Find all columns with numeric string values, then pick the one with largest value
    // (assumes larger values = main metric, smaller values = dimension/grouping)
    const numericCols = keys.filter(k => {
      if (k === dateKey) return false
      const val = firstRow[k]
      if (typeof val === 'string') {
        const numericPattern = /^-?\d+(\.\d+)?$/
        const cleaned = val.replace(/,/g, '').trim()
        if (!numericPattern.test(cleaned)) return false
        const parsed = parseFloat(cleaned)
        return !isNaN(parsed) && isFinite(parsed) && parsed > 0
      }
      return false
    })

    if (numericCols.length > 0) {
      // Pick the column with the largest value (main metric)
      valueKey = numericCols.reduce((best, k) => {
        const val = parseFloat(firstRow[k].replace(/,/g, ''))
        const bestVal = parseFloat(firstRow[best].replace(/,/g, ''))
        return val > bestVal ? k : best
      })
    }
  }

  // 3. Detect dimension column
  const dimKey = keys.find(k =>
    /^GROUP_\d$/i.test(k) ||
    /dimension|channel|site|品类|品牌|平台|category|分类/i.test(k)
  )

  for (const row of rawData) {
    const entry = {}

    // Date - use FDATE or similar
    if (dateKey) {
      entry.date = row[dateKey]
    } else {
      entry.date = ''
    }

    // Value - extract numeric value
    if (valueKey) {
      const rawVal = row[valueKey]
      if (typeof rawVal === 'number') {
        entry.value = rawVal
      } else if (typeof rawVal === 'string') {
        const parsed = parseFloat(rawVal.replace(/,/g, ''))
        entry.value = isNaN(parsed) ? 0 : parsed
      } else {
        entry.value = 0
      }
    } else {
      entry.value = 0
    }

    // Dimension
    if (dimKey) {
      entry[dimensionKey] = String(row[dimKey] || '')
    } else {
      entry[dimensionKey] = ''
    }

    result.push(entry)
  }

  return result
}

async function fetchVolatilityData(data) {
  try {
    const response = await fetch(props.apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let eventType = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.replace('event: ', '').trim()
          continue
        }
        if (line.startsWith('data: ')) {
          const jsonStr = line.replace('data: ', '').trim()
          if (!jsonStr) continue
          try {
            const eventData = JSON.parse(jsonStr)
            handleSSEEvent(eventData, eventType)
          } catch (e) {
            console.error('[VolatilityPanel] JSON parse error:', e)
          }
        }
      }
    }
  } catch (e) {
    console.error('[VolatilityPanel] Fetch error:', e)
  }
}

function handleSSEEvent(data, eventType) {
  // Handle events by data.type (the actual event type sent by backend)
  // This is more reliable than SSE event line when events are multiplexed
  if (data.type) {
    switch (data.type) {
      case 'volatility_overview':
        state.value.overview = {
          current_value: data.current_value,
          mom_change: data.mom_change,
          mom_change_pct: data.mom_change_pct,
          yoy_change: data.yoy_change,
          yoy_change_pct: data.yoy_change_pct,
          volatility_rate: data.volatility_rate,
          volatility_rate_pct: data.volatility_rate_pct,
          anomaly_level: data.anomaly_level,
          is_anomaly: data.is_anomaly
        }
        break
      case 'volatility_chart':
        state.value.chartData = data.chart_data || []
        // Use backend-specified chart type, or default to 'line'
        if (data.chart_type) {
          state.value.chartType = data.chart_type
        }
        break
      case 'volatility_dims':
        state.value.positiveDims = data.positive_dims || []
        state.value.negativeDims = data.negative_dims || []
        break
      case 'volatility_llm_reasoning':
        // LLM reasoning content
        if (data.content) {
          state.value.llmThinking = data.content
          state.value.llmStage = data.stage || ''
        }
        break
      case 'volatility_root':
        state.value.rootCause = data.root_cause
        state.value.confidence = data.confidence || 0
        state.value.suggestion = data.suggestion || ''
        state.value.llmThinking = ''
        break
      case 'volatility_done':
        // Done event - no action needed
        break
    }
  }
}

// Watch for visibility changes
watch(visible, (val) => {
  if (!val) {
    stopStream()
  }
})

// Handle resize
onMounted(() => {
  window.addEventListener('resize', () => {
    isMobile.value = window.innerWidth < 768
  })
})

onUnmounted(() => {
  stopStream()
})

// Expose startStream for parent component
defineExpose({
  startStream
})
</script>

<style scoped>
.volatility-panel {
  --el-drawer-bg-color: #fff;
}

/* Mobile responsive */
.mobile-panel {
  border-radius: 12px 12px 0 0;
  height: 70vh !important;
  min-height: 100dvh;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}

.drawer-title svg {
  color: #1E40AF;
}

.close-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(30, 64, 175, 0.08);
  color: #1E40AF;
}

.drawer-content {
  padding: 16px 0;
}

/* Mobile Tabs */
.mobile-tabs {
  display: flex;
  gap: 4px;
  padding: 0 16px 12px;
  overflow-x: auto;
}

.tab-btn {
  padding: 8px 16px;
  border: none;
  background: #f3f4f6;
  border-radius: 6px;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}

.tab-btn.active {
  background: #1E40AF;
  color: #fff;
}

/* Section */
.section {
  padding: 0 16px 24px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e5e7eb;
}

.status-dot.done {
  background: #10B981;
}

.status-dot.loading {
  background: #F59E0B;
  animation: pulse 1s ease-in-out infinite;
}

.status-dot.pending {
  background: #e5e7eb;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Overview Grid */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.kpi-card {
  padding: 12px;
  background: #f9fafb;
  border-radius: 10px;
}

.kpi-card.anomaly {
  grid-column: span 2;
}

.kpi-card.is-anomaly {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.kpi-label {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
}

.kpi-value {
  font-size: 18px;
  font-weight: 600;
  color: #1f1f1f;
  font-family: 'Fira Code', monospace;
}

.kpi-value.positive {
  color: #10B981;
}

.kpi-value.negative {
  color: #EF4444;
}

.kpi-value.warning {
  color: #F59E0B;
}

.kpi-value.anomaly {
  color: #EF4444;
}

.anomaly-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: rgba(245, 158, 11, 0.1);
  color: #D97706;
  border-radius: 4px;
  font-size: 13px;
}

.normal-tag {
  color: #10B981;
  font-size: 13px;
}

/* Skeleton */
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.skeleton-card {
  height: 60px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 10px;
}

.skeleton-chart {
  height: 180px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 10px;
}

.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-item {
  height: 50px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 10px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Chart */
.chart-wrapper {
  border-radius: 10px;
  overflow: hidden;
}

/* Drivers */
.drivers-group {
  margin-bottom: 16px;
}

.drivers-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 10px;
  padding: 6px 10px;
  border-radius: 6px;
}

.drivers-header.positive {
  color: #10B981;
  background: rgba(16, 185, 129, 0.08);
}

.drivers-header.negative {
  color: #EF4444;
  background: rgba(239, 68, 68, 0.08);
}

.drivers-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.driver-item {
  padding: 10px 12px;
  background: #f9fafb;
  border-radius: 8px;
}

.driver-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.driver-rank {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.driver-name {
  flex: 1;
  font-size: 13px;
  color: #374151;
}

.driver-contribution {
  font-size: 13px;
  font-weight: 600;
}

.driver-contribution.positive {
  color: #10B981;
}

.driver-contribution.negative {
  color: #EF4444;
}

.driver-bar {
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
}

.driver-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.driver-bar-fill.positive {
  background: linear-gradient(90deg, #10B981 0%, #34D399 100%);
}

.driver-bar-fill.negative {
  background: linear-gradient(90deg, #EF4444 0%, #F87171 100%);
}

/* Reasoning */
.reasoning-section {
  min-height: 200px;
}

.reasoning-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.thinking-stream {
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
  border-left: 3px solid #3B82F6;
}

.thinking-text {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
}

.root-cause-card {
  padding: 16px;
  background: linear-gradient(135deg, rgba(30, 64, 175, 0.05) 0%, rgba(59, 130, 246, 0.05) 100%);
  border: 1px solid rgba(30, 64, 175, 0.1);
  border-radius: 10px;
}

.cause-label {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
}

.cause-value {
  font-size: 15px;
  font-weight: 600;
  color: #1E40AF;
  margin-bottom: 12px;
}

.confidence-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-label {
  font-size: 11px;
  color: #6b7280;
}

.confidence-value {
  font-size: 12px;
  font-weight: 600;
  color: #1E40AF;
  min-width: 36px;
}

.confidence-track {
  flex: 1;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  background: linear-gradient(90deg, #1E40AF 0%, #3B82F6 100%);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.suggestion-card {
  padding: 16px;
  background: rgba(16, 185, 129, 0.05);
  border: 1px solid rgba(16, 185, 129, 0.1);
  border-radius: 10px;
}

.suggestion-label {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
}

.suggestion-text {
  font-size: 14px;
  color: #374151;
  line-height: 1.5;
}

.reasoning-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 12px;
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3B82F6;
  animation: bounce 1.4s ease-in-out infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.loading-text {
  font-size: 13px;
  color: #6b7280;
}

/* Desktop responsive */
@media (min-width: 768px) {
  .volatility-panel {
    border-radius: 12px 0 0 12px;
  }
}
</style>
