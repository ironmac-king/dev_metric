<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1 class="page-title">Dashboard</h1>
        <p class="page-desc">实时监控业务指标</p>
      </div>
      <div class="header-right">
        <el-button size="large">
          <el-icon><Download /></el-icon>
          Export
        </el-button>
      </div>
    </header>

    <!-- Stats Row -->
    <div class="stats-row">
      <div v-for="stat in stats" :key="stat.label" class="stat-card">
        <div class="stat-label">{{ stat.label }}</div>
        <div class="stat-value">{{ stat.value }}</div>
        <div class="stat-change" :class="stat.changeType">
          <span class="change-icon">{{ stat.changeType === 'up' ? '↑' : '↓' }}</span>
          {{ stat.change }} last month
        </div>
      </div>
    </div>

    <!-- Chart Section -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">指标趋势</h2>
        <div class="chart-controls">
          <el-radio-group v-model="chartPeriod" size="small">
            <el-radio-button label="7d">7 days</el-radio-button>
            <el-radio-button label="30d">30 days</el-radio-button>
            <el-radio-button label="90d">90 days</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <div class="chart-card">
        <div ref="chartRef" class="chart"></div>
      </div>
    </div>

    <!-- Metrics Table -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">指标列表</h2>
        <div class="table-controls">
          <el-input
            v-model="searchQuery"
            placeholder="Search metrics..."
            prefix-icon="Search"
            clearable
            size="large"
            :style="{ width: '280px' }"
          />
          <el-button size="large" type="primary">Add metric</el-button>
        </div>
      </div>
      <div class="table-card">
        <table class="metrics-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Domain</th>
              <th>Type</th>
              <th>Unit</th>
              <th>Frequency</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="metric in filteredMetrics" :key="metric.metric_code">
              <td class="metric-cell">
                <div class="metric-name">{{ metric.name }}</div>
                <div class="metric-code">{{ metric.metric_code }}</div>
              </td>
              <td>
                <span class="domain-badge">{{ metric.domain }}</span>
              </td>
              <td class="type-cell">{{ metric.category_1 }}</td>
              <td class="unit-cell">{{ metric.unit }}</td>
              <td class="freq-cell">{{ metric.frequency }}</td>
              <td>
                <span class="status-badge" :class="metric.status === '在用' ? 'active' : 'inactive'">
                  {{ metric.status === '在用' ? 'Active' : 'Inactive' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="table-footer">
          <span class="results-count">Showing {{ filteredMetrics.length }} of {{ metricsList.length }} results</span>
          <el-pagination
            size="small"
            layout="prev, pager, next"
            :total="metricsList.length"
            :page-size="10"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { dashboardAPI, metricAPI } from '../api'
import * as echarts from 'echarts'
import { Download, Search } from '@element-plus/icons-vue'

const chartRef = ref(null)
const chartPeriod = ref('30d')
const searchQuery = ref('')

let chart = null
let resizeHandler = null

const stats = ref([
  { label: 'Total Metrics', value: '155', change: '+12', changeType: 'up' },
  { label: 'Active Metrics', value: '142', change: '+8', changeType: 'up' },
  { label: 'Alert Rules', value: '23', change: '+3', changeType: 'up' },
  { label: 'Active Alerts', value: '3', change: '-2', changeType: 'down' },
])

const metricsList = ref([])

const filteredMetrics = computed(() => {
  if (!searchQuery.value) return metricsList.value.slice(0, 10)
  const q = searchQuery.value.toLowerCase()
  return metricsList.value
    .filter(m => m.name.toLowerCase().includes(q) || m.metric_code.toLowerCase().includes(q))
    .slice(0, 10)
})

onMounted(async () => {
  try {
    const summary = await dashboardAPI.getSummary()
    if (summary.data) {
      stats.value[0].value = summary.data.total_metrics || 155
      stats.value[1].value = summary.data.active_metrics || 142
      stats.value[2].value = summary.data.total_alerts || 23
      stats.value[3].value = summary.data.active_alerts || 3
    }
  } catch (e) {}

  try {
    const res = await metricAPI.list({ page: 1, page_size: 100 })
    if (res.data?.list) {
      metricsList.value = res.data.list
    }
  } catch (e) {
    metricsList.value = [
      { metric_code: 'MKI-01-0001', name: '日销售额', domain: '营销域', category_1: '国内营销', unit: '元', frequency: '日', status: '在用' },
      { metric_code: 'MKI-02-0001', name: '日访客数', domain: '营销域', category_1: '国内营销', unit: '人', frequency: '日', status: '在用' },
      { metric_code: 'MKI-03-0001', name: '日订单量', domain: '营销域', category_1: '国内营销', unit: '笔', frequency: '日', status: '在用' },
      { metric_code: 'MKI-04-0001', name: '库存周转率', domain: '供应链域', category_1: '库存管理', unit: '次', frequency: '月', status: '在用' },
      { metric_code: 'MKI-05-0001', name: '客户满意度', domain: '服务域', category_1: '客户服务', unit: '%', frequency: '季', status: '在用' },
    ]
  }

  await nextTick()
  initChart()
})

onUnmounted(() => {
  if (chart) {
    chart.dispose()
    chart = null
  }
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
})

function initChart() {
  if (!chartRef.value) return

  chart = echarts.init(chartRef.value)

  // 保存 resize handler 引用以便清理
  resizeHandler = () => chart?.resize()
  window.addEventListener('resize', resizeHandler)

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
    grid: { left: '0', right: '0', bottom: '0', top: '20px', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['Mar 1', 'Mar 5', 'Mar 10', 'Mar 15', 'Mar 20', 'Mar 25', 'Mar 30'],
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
    series: [{
      type: 'line',
      data: [820, 932, 1101, 1234, 1290, 1380, 1520],
      smooth: 0.4,
      symbol: 'circle',
      symbolSize: 0,
      lineStyle: { color: '#6366f1', width: 2.5 },
      itemStyle: { color: '#6366f1' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(99, 102, 241, 0.12)' },
            { offset: 1, color: 'rgba(99, 102, 241, 0)' }
          ]
        }
      }
    }]
  }

  chart.setOption(option)
}
</script>

<style>
.dashboard {
  padding: 48px;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 48px;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  letter-spacing: -0.5px;
  margin-bottom: 4px;
}

.page-desc {
  font-size: 14px;
  color: #7177a4;
}

.header-right .el-button {
  background: #fff;
  border: 1px solid #e4e7ed;
  color: #1a1a1a;
  font-weight: 500;
  padding: 12px 20px;
  border-radius: 8px;
}

.header-right .el-button:hover {
  background: #f5f5f5;
  border-color: #c0c4cc;
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 48px;
}

.stat-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  padding: 24px;
  transition: all 0.2s ease;
}

.stat-card:hover {
  border-color: #c0c4cc;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}

.stat-label {
  font-size: 13px;
  font-weight: 500;
  color: #7177a4;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #1a1a1a;
  letter-spacing: -1px;
  margin-bottom: 8px;
}

.stat-change {
  font-size: 13px;
  font-weight: 500;
}

.stat-change.up { color: #10b981; }
.stat-change.down { color: #ef4444; }

.change-icon {
  margin-right: 4px;
}

/* Sections */
.section {
  margin-bottom: 48px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}

.chart-controls .el-radio-group {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 4px;
}

.chart-controls .el-radio-button__inner {
  background: transparent;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #7177a4;
  padding: 8px 14px;
}

.chart-controls .el-radio-button__original-radio:checked + .el-radio-button__inner {
  background: #1a1a1a;
  color: #fff;
  box-shadow: none;
}

/* Chart Card */
.chart-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  padding: 24px;
}

.chart {
  height: 300px;
  width: 100%;
}

/* Table Controls */
.table-controls {
  display: flex;
  gap: 12px;
}

.table-controls .el-input__wrapper {
  border-radius: 8px;
  box-shadow: none !important;
  border: 1px solid #e4e7ed;
}

.table-controls .el-input__wrapper:hover,
.table-controls .el-input__wrapper:focus {
  border-color: #6366f1;
}

.table-controls .el-button--primary {
  background: #6366f1;
  border-color: #6366f1;
  border-radius: 8px;
  font-weight: 500;
}

.table-controls .el-button--primary:hover {
  background: #5558e3;
  border-color: #5558e3;
}

/* Table Card */
.table-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
}

.metrics-table {
  width: 100%;
  border-collapse: collapse;
}

.metrics-table th {
  text-align: left;
  padding: 16px 20px;
  font-size: 12px;
  font-weight: 600;
  color: #7177a4;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}

.metrics-table td {
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f5;
  font-size: 14px;
  color: #1a1a1a;
}

.metrics-table tr:last-child td {
  border-bottom: none;
}

.metrics-table tr:hover td {
  background: #fafafa;
}

.metric-cell {
  padding-left: 20px !important;
}

.metric-name {
  font-weight: 500;
  color: #1a1a1a;
  margin-bottom: 2px;
}

.metric-code {
  font-size: 12px;
  color: #7177a4;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.domain-badge {
  display: inline-block;
  padding: 4px 10px;
  background: #f0f0ff;
  color: #6366f1;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.type-cell {
  color: #7177a4;
}

.unit-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: #7177a4;
  font-size: 13px;
}

.freq-cell {
  color: #7177a4;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-badge.active {
  background: #dcfce7;
  color: #166534;
}

.status-badge.active::before {
  background: #22c55e;
}

.status-badge.inactive {
  background: #f3f4f6;
  color: #6b7280;
}

.status-badge.inactive::before {
  background: #9ca3af;
}

/* Table Footer */
.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid #ebeef5;
  background: #fafafa;
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
  .dashboard {
    padding: 24px;
  }
  .stats-row {
    grid-template-columns: 1fr;
  }
  .header {
    flex-direction: column;
    gap: 20px;
  }
}
</style>
