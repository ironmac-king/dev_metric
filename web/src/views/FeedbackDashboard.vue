<template>
  <div class="feedback-dashboard">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1 class="page-title">反馈看板</h1>
        <p class="page-desc">智能问数效果分析</p>
      </div>
      <div class="header-right">
        <el-radio-group v-model="period" size="default" @change="handlePeriodChange">
          <el-radio-button label="day">日</el-radio-button>
          <el-radio-button label="week">周</el-radio-button>
          <el-radio-button label="month">月</el-radio-button>
        </el-radio-group>
      </div>
    </header>

    <!-- Stats Row -->
    <div class="stats-row">
      <div class="stat-card" :class="{ 'animate-in': mounted }" style="animation-delay: 0ms">
        <div class="stat-icon total">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-label">总反馈数</div>
          <div class="stat-value">{{ stats.total_feedback || 0 }}</div>
          <div class="stat-rate">占比 100%</div>
        </div>
      </div>

      <div class="stat-card" :class="{ 'animate-in': mounted }" style="animation-delay: 100ms">
        <div class="stat-icon positive">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-label">👍 点赞</div>
          <div class="stat-value positive-value">{{ stats.positive?.count || 0 }}</div>
          <div class="stat-rate">占比 {{ (stats.positive?.rate || 0).toFixed(1) }}%</div>
        </div>
      </div>

      <div class="stat-card" :class="{ 'animate-in': mounted }" style="animation-delay: 200ms">
        <div class="stat-icon negative">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-label">👎 点踩</div>
          <div class="stat-value negative-value">{{ stats.negative?.count || 0 }}</div>
          <div class="stat-rate">占比 {{ (stats.negative?.rate || 0).toFixed(1) }}%</div>
        </div>
      </div>

      <div class="stat-card" :class="{ 'animate-in': mounted }" style="animation-delay: 300ms">
        <div class="stat-icon silent">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 1l22 22M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/>
            <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-label">🔇 沉默用户</div>
          <div class="stat-value silent-value">{{ stats.silent?.count || 0 }}</div>
          <div class="stat-rate">占比 {{ (stats.silent?.rate || 0).toFixed(1) }}%</div>
        </div>
      </div>
    </div>

    <!-- Trend Chart Section -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">反馈趋势</h2>
      </div>
      <div class="chart-card">
        <div ref="trendChartRef" class="chart"></div>
      </div>
    </div>

    <!-- Success Rate by Type -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">追问类型成功率排行</h2>
      </div>
      <div class="rate-card">
        <div class="rate-list">
          <div v-for="(item, index) in typeStats" :key="item.clarification_type" class="rate-item">
            <div class="rate-rank">{{ index + 1 }}</div>
            <div class="rate-info">
              <div class="rate-type">{{ getTypeName(item.clarification_type) }}</div>
              <div class="rate-bar-container">
                <div class="rate-bar" :style="{ width: item.success_rate + '%', background: getRateColor(item.success_rate) }"></div>
              </div>
            </div>
            <div class="rate-value" :style="{ color: getRateColor(item.success_rate) }">{{ item.success_rate.toFixed(1) }}%</div>
          </div>
          <div v-if="typeStats.length === 0" class="empty-tip">暂无数据</div>
        </div>
      </div>
    </div>

    <!-- Feedback List -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">问题明细</h2>
        <div class="filter-controls">
          <el-select v-model="filters.feedback_type" placeholder="反馈类型" clearable size="default" :style="{ width: '140px' }" @change="handleFeedbackTypeChange">
            <el-option label="全部" value="" />
            <el-option label="👍 点赞" value="positive" />
            <el-option label="👎 点踩" value="negative" />
            <el-option label="🔇 沉默" value="silent" />
          </el-select>
          <el-select v-model="filters.clarification_type" placeholder="追问类型" clearable size="default" :style="{ width: '160px' }" @change="handleClarTypeChange">
            <el-option label="全部" value="" />
            <el-option v-for="t in clarificationTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            size="default"
            value-format="YYYY-MM-DD"
            @change="handleDateChange"
          />
        </div>
      </div>
      <div class="table-card">
        <table class="feedback-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>会话ID</th>
              <th>问题摘要</th>
              <th>追问类型</th>
              <th>失败原因</th>
              <th>反馈</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in feedbackList" :key="item.id">
              <td class="time-cell">{{ formatTime(item.created_at) }}</td>
              <td class="session-cell">{{ item.session_id }}</td>
              <td class="question-cell" :title="item.question_preview">{{ item.question_preview || '--' }}</td>
              <td>
                <span class="type-badge">{{ getTypeName(item.clarification_type) }}</span>
              </td>
              <td class="fail-reason-cell">{{ item.fail_reason || '--' }}</td>
              <td>
                <span class="feedback-badge" :class="getFeedbackClass(item.feedback_display)">
                  {{ item.feedback_display || '--' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="table-footer">
          <span class="results-count">
            共 {{ pagination.total }} 条结果
          </span>
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.page_size"
            :page-sizes="[10, 20, 50]"
            :total="pagination.total"
            layout="sizes, prev, pager, next"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { feedbackAPI } from '../api'
import * as echarts from 'echarts'

const mounted = ref(false)
const period = ref('day')
const trendChartRef = ref(null)
const dateRange = ref([])

let trendChart = null

const stats = ref({})
const typeStats = ref([])
const feedbackList = ref([])

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const filters = reactive({
  feedback_type: '',
  clarification_type: '',
  start_date: '',
  end_date: ''
})

const clarificationTypes = [
  { value: 'time_range', label: '时间范围缺失' },
  { value: 'dimension', label: '维度缺失' },
  { value: 'metric_missing', label: '指标不存在' },
  { value: 'no_data', label: '数据为空' },
  { value: 'ambiguous', label: '表述模糊' },
  { value: 'permission', label: '权限不足' },
  { value: 'scope_too_broad', label: '表述太宽泛' },
  { value: 'metric_enum', label: '指标枚举' }
]

const getTypeName = (type) => {
  const found = clarificationTypes.find(t => t.value === type)
  return found ? found.label : type || '--'
}

const getRateColor = (rate) => {
  if (rate >= 70) return '#67C23A'
  if (rate >= 40) return '#E6A23C'
  return '#F56C6C'
}

const getFeedbackClass = (display) => {
  if (display === '👍') return 'positive'
  if (display === '👎') return 'negative'
  if (display === '🔇') return 'silent'
  return ''
}

const formatTime = (time) => {
  if (!time) return '--'
  const d = new Date(time)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

const fetchStats = async () => {
  try {
    const res = await feedbackAPI.getStats()
    if (res.data) {
      stats.value = res.data
    }
  } catch (e) {
    console.error('Failed to fetch stats:', e)
  }
}

const fetchTrend = async () => {
  try {
    const res = await feedbackAPI.getTrend(period.value)
    if (res.data?.trends) {
      renderTrendChart(res.data.trends)
    }
  } catch (e) {
    console.error('Failed to fetch trend:', e)
  }
}

const fetchTypeStats = async () => {
  try {
    const res = await feedbackAPI.getByType()
    if (res.data?.stats) {
      typeStats.value = res.data.stats
    }
  } catch (e) {
    console.error('Failed to fetch type stats:', e)
  }
}

const fetchFeedbackList = async () => {
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size,
      ...filters
    }
    const res = await feedbackAPI.getList(params)
    if (res.data) {
      feedbackList.value = res.data.list || []
      pagination.total = res.data.pagination?.total || 0
    }
  } catch (e) {
    console.error('Failed to fetch feedback list:', e)
  }
}

const renderTrendChart = (trends) => {
  if (!trendChartRef.value) return

  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }

  const dates = trends.map(t => t.date)
  const positiveData = trends.map(t => t.positive)
  const negativeData = trends.map(t => t.negative)
  const silentData = trends.map(t => t.silent)

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e4e7ed',
      borderWidth: 1,
      textStyle: { color: '#1a1a1a', fontSize: 13 },
      axisPointer: { type: 'line', lineStyle: { color: '#e4e7ed' } }
    },
    legend: {
      data: ['👍 点赞', '👎 点踩', '🔇 沉默'],
      bottom: 0,
      textStyle: { color: '#7177a4', fontSize: 12 },
      itemGap: 24
    },
    grid: { left: '0', right: '0', bottom: '50px', top: '20px', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#7177a4', fontSize: 12 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f0f5', type: 'dashed' } },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#7177a4', fontSize: 12 }
    },
    series: [
      {
        name: '👍 点赞',
        type: 'line',
        data: positiveData,
        smooth: 0.4,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#67C23A', width: 2 },
        itemStyle: { color: '#67C23A' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(103, 194, 58, 0.15)' },
              { offset: 1, color: 'rgba(103, 194, 58, 0)' }
            ]
          }
        }
      },
      {
        name: '👎 点踩',
        type: 'line',
        data: negativeData,
        smooth: 0.4,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#F56C6C', width: 2 },
        itemStyle: { color: '#F56C6C' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(245, 108, 108, 0.15)' },
              { offset: 1, color: 'rgba(245, 108, 108, 0)' }
            ]
          }
        }
      },
      {
        name: '🔇 沉默',
        type: 'line',
        data: silentData,
        smooth: 0.4,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#909399', width: 2 },
        itemStyle: { color: '#909399' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(144, 147, 153, 0.15)' },
              { offset: 1, color: 'rgba(144, 147, 153, 0)' }
            ]
          }
        }
      }
    ]
  }

  trendChart.setOption(option)
}

const handlePeriodChange = () => {
  fetchTrend()
}

const handleFeedbackTypeChange = () => {
  pagination.page = 1
  fetchFeedbackList()
}

const handleClarTypeChange = () => {
  pagination.page = 1
  fetchFeedbackList()
}

const handleDateChange = (val) => {
  if (val && val.length === 2) {
    filters.start_date = val[0]
    filters.end_date = val[1]
  } else {
    filters.start_date = ''
    filters.end_date = ''
  }
  pagination.page = 1
  fetchFeedbackList()
}

const handleSizeChange = () => {
  pagination.page = 1
  fetchFeedbackList()
}

const handlePageChange = (page) => {
  pagination.page = page
  fetchFeedbackList()
}

onMounted(async () => {
  mounted.value = true

  await Promise.all([
    fetchStats(),
    fetchTrend(),
    fetchTypeStats(),
    fetchFeedbackList()
  ])

  await nextTick()
  window.addEventListener('resize', () => trendChart?.resize())
})

onUnmounted(() => {
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
  window.removeEventListener('resize', () => trendChart?.resize())
})
</script>

<style scoped>
.feedback-dashboard {
  padding: 32px 40px;
  min-height: 100vh;
  background: linear-gradient(160deg, #F5F7FA 0%, #E8ECF3 100%);
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
}

.page-title {
  font-size: 26px;
  font-weight: 600;
  color: #1a1a1a;
  letter-spacing: -0.5px;
  margin-bottom: 4px;
}

.page-desc {
  font-size: 14px;
  color: #7177a4;
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  padding: 24px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.stat-card.animate-in {
  opacity: 1;
  transform: translateY(0);
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon svg {
  width: 24px;
  height: 24px;
}

.stat-icon.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.stat-icon.positive {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  color: #fff;
}

.stat-icon.negative {
  background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
  color: #fff;
}

.stat-icon.silent {
  background: linear-gradient(135deg, #485563 0%, #29323c 100%);
  color: #fff;
}

.stat-content {
  flex: 1;
}

.stat-label {
  font-size: 13px;
  font-weight: 500;
  color: #7177a4;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a1a;
  letter-spacing: -1px;
  margin-bottom: 4px;
}

.stat-value.positive-value { color: #67C23A; }
.stat-value.negative-value { color: #F56C6C; }
.stat-value.silent-value { color: #909399; }

.stat-rate {
  font-size: 12px;
  color: #a2a6b3;
}

/* Sections */
.section {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
}

/* Chart Card */
.chart-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  padding: 24px;
}

.chart {
  height: 280px;
  width: 100%;
}

/* Rate Card */
.rate-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  padding: 24px;
}

.rate-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rate-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.rate-rank {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f0f0f5;
  color: #7177a4;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.rate-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rate-type {
  font-size: 14px;
  color: #1a1a1a;
  font-weight: 500;
}

.rate-bar-container {
  height: 8px;
  background: #f0f0f5;
  border-radius: 4px;
  overflow: hidden;
}

.rate-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.rate-value {
  font-size: 16px;
  font-weight: 700;
  min-width: 60px;
  text-align: right;
}

.empty-tip {
  text-align: center;
  color: #a2a6b3;
  padding: 32px;
}

/* Filter Controls */
.filter-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.filter-controls .el-select :deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: none !important;
  border: 1px solid #e4e7ed;
  background: rgba(255, 255, 255, 0.8);
}

.filter-controls .el-date-editor {
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  background: rgba(255, 255, 255, 0.8);
}

/* Table Card */
.table-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  overflow: hidden;
}

.feedback-table {
  width: 100%;
  border-collapse: collapse;
}

.feedback-table th {
  text-align: left;
  padding: 14px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #7177a4;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: rgba(249, 250, 251, 0.8);
  border-bottom: 1px solid #ebeef5;
}

.feedback-table td {
  padding: 14px 16px;
  border-bottom: 1px solid #f0f0f5;
  font-size: 13px;
  color: #1a1a1a;
}

.feedback-table tr:last-child td {
  border-bottom: none;
}

.feedback-table tr:hover td {
  background: rgba(249, 250, 251, 0.5);
}

.time-cell {
  color: #7177a4;
  font-size: 12px;
  white-space: nowrap;
}

.session-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  color: #7177a4;
}

.question-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.type-badge {
  display: inline-block;
  padding: 4px 10px;
  background: #f0f0ff;
  color: #6366f1;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.fail-reason-cell {
  color: #F56C6C;
  font-size: 12px;
}

.feedback-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  font-size: 16px;
}

.feedback-badge.positive {
  background: #dcfce7;
}

.feedback-badge.negative {
  background: #fee2e2;
}

.feedback-badge.silent {
  background: #f3f4f6;
}

/* Table Footer */
.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-top: 1px solid #ebeef5;
  background: rgba(249, 250, 251, 0.8);
}

.results-count {
  font-size: 13px;
  color: #7177a4;
}

.table-footer .el-pagination {
  background: transparent;
}

.table-footer .el-pager li {
  border-radius: 6px;
  font-weight: 500;
}

.table-footer .el-pager li.is-active {
  background: #6366f1;
  color: #fff;
}

/* Responsive */
@media (max-width: 1200px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .feedback-dashboard {
    padding: 20px;
  }
  .stats-row {
    grid-template-columns: 1fr;
  }
  .header {
    flex-direction: column;
    gap: 16px;
  }
  .filter-controls {
    flex-wrap: wrap;
  }
}
</style>
