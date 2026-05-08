<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <div class="page-icon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <rect x="2" y="2" width="8" height="8" rx="2" fill="currentColor" opacity="0.9"/>
            <rect x="12" y="2" width="8" height="8" rx="2" fill="currentColor" opacity="0.6"/>
            <rect x="2" y="12" width="8" height="8" rx="2" fill="currentColor" opacity="0.6"/>
            <rect x="12" y="12" width="8" height="8" rx="2" fill="currentColor" opacity="0.3"/>
          </svg>
        </div>
        <div class="header-text">
          <h1>Dashboard</h1>
          <p>实时监控业务指标</p>
        </div>
      </div>
    </header>

    <!-- Stats Row -->
    <div class="stats-row">
      <div v-for="stat in stats" :key="stat.label" class="stat-card">
        <div class="stat-label">{{ stat.label }}</div>
        <div class="stat-value">{{ stat.value }}</div>
        <div class="stat-change" :class="stat.changeType">
          <span class="change-icon">{{ stat.changeType === 'up' ? '↑' : '↓' }}</span>
          {{ stat.change }}
        </div>
      </div>
    </div>

    <!-- Metric Cards Section -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">告警监控</h2>
        <div class="refresh-btn" @click="loadMetricCards">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" :class="{ spinning: loadingCards }">
            <path d="M14 8A6 6 0 1 1 8 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M14 2v4h-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>刷新</span>
        </div>
      </div>
      <div class="metric-cards-scroll">
        <div class="metric-cards-row">
          <div
            v-for="card in metricCards"
            :key="card.rule_id"
            class="metric-card"
            :class="card.status"
            @click.stop="openEditDialog(card)"
          >
            <div class="card-header">
              <span v-if="card.status === 'critical'" class="card-status critical">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 1L13 12H1L7 1Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
                  <path d="M7 5v3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  <circle cx="7" cy="10" r="0.5" fill="currentColor"/>
                </svg>
                异常
              </span>
              <span v-else-if="card.status === 'warning'" class="card-status warning">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                  <path d="M7 4v3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  <circle cx="7" cy="9.5" r="0.5" fill="currentColor"/>
                </svg>
                告警
              </span>
              <span v-else class="card-status normal">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                  <path d="M4 7l2 2 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                正常
              </span>
              <button class="card-edit-btn" @click.stop="openEditDialog(card)" title="编辑">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M8.5 1.5L10.5 3.5L4 10H2V8L8.5 1.5Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
                </svg>
              </button>
            </div>
            <div class="card-body">
              <div class="card-metric-name">{{ card.metric_name }}</div>
              <div class="card-metric-code">{{ card.metric_code }}</div>
              <div class="card-value">
                <span class="value-number">{{ formatValue(card.current_value) }}</span>
                <span class="value-unit">{{ card.unit }}</span>
              </div>
              <div class="card-threshold">
                阈值: {{ card.condition_text }} {{ formatValue(card.threshold) }} {{ card.unit }}
              </div>
            </div>
            <div class="card-footer">
              <span class="last-check">检查: {{ card.last_check }}</span>
            </div>
          </div>

          <!-- Add Card -->
          <div class="metric-card add-card" @click="showAddDialog">
            <div class="add-icon">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                <circle cx="14" cy="14" r="13" stroke="currentColor" stroke-width="2" stroke-dasharray="4 4"/>
                <path d="M14 9V19M9 14H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
            <span class="add-text">添加监控</span>
          </div>

          <div v-if="!metricCards.length && !loadingCards" class="no-cards">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="18" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
              <path d="M20 12v10M20 26v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
            </svg>
            <p>暂无告警监控指标</p>
            <span>请在告警配置中添加监控规则</span>
          </div>
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
      </div>
      <div class="table-card">
        <table class="metrics-table">
          <thead>
            <tr>
              <th>指标名称</th>
              <th>所属域</th>
              <th>类型</th>
              <th>单位</th>
              <th>频度</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="metric in metricsList.slice(0, 10)" :key="metric.metric_code">
              <td class="metric-cell">
                <div class="metric-name">{{ metric.name }}</div>
                <div class="metric-code">{{ metric.metric_code }}</div>
              </td>
              <td>
                <span class="domain-badge">{{ metric.domain }}</span>
              </td>
              <td class="type-cell">{{ metric.category_1 || '-' }}</td>
              <td class="unit-cell">{{ metric.unit || '-' }}</td>
              <td class="freq-cell">{{ metric.frequency || '-' }}</td>
              <td>
                <span class="status-badge" :class="metric.status === '在用' ? 'active' : 'inactive'">
                  <span class="status-dot"></span>
                  {{ metric.status === '在用' ? '在用' : '停用' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="table-footer">
          <span class="results-count">共 {{ metricsList.length }} 条指标</span>
        </div>
      </div>
    </div>

    <!-- 添加监控对话框 -->
    <el-dialog
      v-model="addDialogVisible"
      :title="isEditMode ? '编辑告警监控' : '添加告警监控'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="addForm" label-width="100px" class="add-form">
        <el-form-item label="选择指标" required>
          <el-select
            v-model="addForm.metric_id"
            placeholder="请选择要监控的指标"
            filterable
            class="full-width"
            @change="onMetricChange"
          >
            <el-option
              v-for="m in availableMetrics"
              :key="m.id"
              :label="m.name"
              :value="m.id"
            >
              <div class="metric-option">
                <span class="metric-option-name">{{ m.name }}</span>
                <span class="metric-option-code">{{ m.metric_code }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- 显示指标 SQL 模板 -->
        <el-form-item v-if="selectedMetricSQL" label="SQL 模板">
          <div class="sql-template">
            <code>{{ selectedMetricSQL }}</code>
          </div>
        </el-form-item>

        <!-- WHERE 条件输入 -->
        <el-form-item label="WHERE 条件" required>
          <el-input
            v-model="addForm.where_condition"
            placeholder="如: date = CURRENT_DATE - INTERVAL '1 day'"
            type="textarea"
            :rows="2"
          />
          <div class="where-hint">填写 WHERE 条件，用于确定查询范围</div>
        </el-form-item>

        <el-form-item label="条件类型" required>
          <el-radio-group v-model="addForm.condition_type" class="condition-group">
            <el-radio label="gt">大于 (>)</el-radio>
            <el-radio label="lt">小于 (<)</el-radio>
            <el-radio label="gte">大于等于 (>=)</el-radio>
            <el-radio label="lte">小于等于 (<=)</el-radio>
            <el-radio label="eq">等于 (=)</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="阈值" required>
          <el-input-number
            v-model="addForm.threshold_value"
            :precision="2"
            :step="1"
            :min="0"
            class="threshold-input"
          />
          <span class="unit-label">{{ selectedMetricUnit }}</span>
        </el-form-item>

        <el-form-item label="规则名称">
          <el-input v-model="addForm.name" placeholder="如: 访客数告警" />
        </el-form-item>

        <el-form-item label="钉钉 Webhook">
          <el-input
            v-model="addForm.dingtalk_webhook"
            placeholder="选填，如已配置全局则无需填写"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="addDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleAddAlert" :loading="submitLoading">
            确定添加
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { dashboardAPI, metricAPI, alertAPI } from '../api'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const chartRef = ref(null)
const chartPeriod = ref('30d')

let chart = null
let resizeHandler = null

const stats = ref([
  { label: '指标总数', value: '155', change: '+12', changeType: 'up' },
  { label: '在用指标', value: '142', change: '+8', changeType: 'up' },
  { label: '告警规则', value: '23', change: '+3', changeType: 'up' },
  { label: '活跃告警', value: '3', change: '-2', changeType: 'down' },
])

const metricsList = ref([])
const metricCards = ref([])
const loadingCards = ref(false)

async function loadMetricCards() {
  loadingCards.value = true
  try {
    const res = await dashboardAPI.getMetricCards()
    // 只有返回非空数组时才更新，避免空数组清空卡片
    if (res.data?.cards && res.data.cards.length > 0) {
      metricCards.value = res.data.cards
    }
  } catch (e) {
    console.error('加载指标卡片失败:', e)
    // API 失败时保持旧数据，不清空
  } finally {
    loadingCards.value = false
  }
}

function formatValue(val) {
  if (val === null || val === undefined) return '-'
  if (val >= 10000) {
    return (val / 10000).toFixed(1) + '万'
  }
  if (Number.isInteger(val)) {
    return val.toLocaleString()
  }
  return val.toFixed(2)
}

// 添加监控对话框
const addDialogVisible = ref(false)
const isEditMode = ref(false)
const submitLoading = ref(false)
const availableMetrics = ref([])

const addForm = ref({
  metric_id: null,
  name: '',
  condition_type: 'gt',
  threshold_value: 0,
  where_condition: '',
  dingtalk_webhook: ''
})

const selectedMetricUnit = computed(() => {
  if (!addForm.value.metric_id) return ''
  const metric = availableMetrics.value.find(m => m.id === addForm.value.metric_id)
  return metric ? metric.unit || '' : ''
})

const selectedMetricSQL = computed(() => {
  if (!addForm.value.metric_id) return ''
  const metric = availableMetrics.value.find(m => m.id === addForm.value.metric_id)
  return metric ? metric.starrocks_sql || '（该指标未配置 SQL）' : ''
})

async function showAddDialog() {
  isEditMode.value = false
  addForm.value = {
    metric_id: null,
    name: '',
    condition_type: 'gt',
    threshold_value: 0,
    where_condition: '',
    dingtalk_webhook: ''
  }

  // 加载可选指标列表
  if (!availableMetrics.value.length) {
    try {
      const res = await metricAPI.list({ page: 1, page_size: 500 })
      if (res.data?.list) {
        // 过滤出"在用"状态的指标
        availableMetrics.value = res.data.list.filter(m => m.status === '在用')
      }
    } catch (e) {
      console.error('加载指标列表失败:', e)
    }
  }

  addDialogVisible.value = true
}

async function openEditDialog(card) {
  isEditMode.value = true
  // 加载可选指标列表（如果还没加载）
  if (!availableMetrics.value.length) {
    try {
      const res = await metricAPI.list({ page: 1, page_size: 500 })
      if (res.data?.list) {
        availableMetrics.value = res.data.list.filter(m => m.status === '在用')
      }
    } catch (e) {
      console.error('加载指标列表失败:', e)
    }
  }

  // 找到对应的指标信息
  const metric = availableMetrics.value.find(m => m.id === card.metric_id)

  addForm.value = {
    rule_id: card.rule_id,
    metric_id: card.metric_id,
    name: card.name || `${metric?.name || '指标'} 告警`,
    condition_type: card.condition_type || 'gt',
    threshold_value: card.threshold || 0,
    where_condition: card.where_condition || '',
    dingtalk_webhook: card.dingtalk_webhook || ''
  }

  addDialogVisible.value = true
}

function onMetricChange(metricId) {
  const metric = availableMetrics.value.find(m => m.id === metricId)
  if (metric) {
    addForm.value.name = `${metric.name} 告警`
  }
}

async function handleAddAlert() {
  if (!addForm.value.metric_id) {
    ElMessage.warning('请选择要监控的指标')
    return
  }
  if (!addForm.value.where_condition) {
    ElMessage.warning('请输入 WHERE 条件')
    return
  }
  if (!addForm.value.threshold_value && addForm.value.threshold_value !== 0) {
    ElMessage.warning('请输入阈值')
    return
  }

  submitLoading.value = true
  try {
    const metric = availableMetrics.value.find(m => m.id === addForm.value.metric_id)
    const data = {
      metric_id: addForm.value.metric_id,
      name: addForm.value.name || `${metric?.name || '指标'} 告警`,
      condition_type: addForm.value.condition_type,
      threshold_value: addForm.value.threshold_value,
      where_condition: addForm.value.where_condition,
      dingtalk_webhook: addForm.value.dingtalk_webhook,
      notify_status: 1
    }

    if (isEditMode.value && addForm.value.rule_id) {
      await alertAPI.update(addForm.value.rule_id, data)
      ElMessage.success('更新成功')
    } else {
      await alertAPI.create(data)
      ElMessage.success('添加成功')
    }
    addDialogVisible.value = false
    await loadMetricCards()
  } catch (e) {
    ElMessage.error((isEditMode.value ? '更新' : '添加') + '失败: ' + (e.message || '未知错误'))
  } finally {
    submitLoading.value = false
  }
}

let refreshInterval = null

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
    metricsList.value = []
  }

  // 加载指标卡片
  await loadMetricCards()

  // 每分钟自动刷新
  refreshInterval = setInterval(loadMetricCards, 60000)

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
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
})

function initChart() {
  if (!chartRef.value) return

  chart = echarts.init(chartRef.value)

  resizeHandler = () => chart?.resize()
  window.addEventListener('resize', resizeHandler)

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#E5E7EB',
      borderWidth: 1,
      textStyle: { color: '#1E1B4B', fontSize: 13 },
      axisPointer: { type: 'line', lineStyle: { color: '#E5E7EB' } }
    },
    grid: { left: '0', right: '0', bottom: '0', top: '20px', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['Mar 1', 'Mar 5', 'Mar 10', 'Mar 15', 'Mar 20', 'Mar 25', 'Mar 30'],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#6B7280', fontSize: 12 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#F3F4F6', type: 'dashed' } },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#6B7280', fontSize: 12 }
    },
    series: [{
      type: 'line',
      data: [820, 932, 1101, 1234, 1290, 1380, 1520],
      smooth: 0.4,
      symbol: 'circle',
      symbolSize: 0,
      lineStyle: { color: '#1677FF', width: 2.5 },
      itemStyle: { color: '#1677FF' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(22, 119, 255, 0.12)' },
            { offset: 1, color: 'rgba(22, 119, 255, 0)' }
          ]
        }
      }
    }]
  }

  chart.setOption(option)
}
</script>

<style scoped>
.dashboard {
  padding: 32px 36px;
  max-width: 1440px;
  margin: 0 auto;
  background: var(--bg-primary);
  min-height: 100vh;
}

/* ==========================================
   Bento Grid Dashboard - Apple Style
   ========================================== */

/* Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-icon {
  width: 52px;
  height: 52px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  box-shadow: var(--shadow-card);
  transition: all 0.3s ease;
}

.page-icon:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card-hover);
}

.header-text h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 6px 0;
  letter-spacing: -0.5px;
}

.header-text p {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

/* ==========================================
   Bento Grid Stats Cards
   ========================================== */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 28px;
}

.stat-card {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  padding: 24px;
  box-shadow: var(--shadow-card);
  transition: all var(--transition-bounce);
  cursor: pointer;
  border: 1px solid rgba(22, 119, 255, 0.08);
}

.stat-card:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: var(--shadow-card-hover);
}

.stat-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--primary);
  letter-spacing: -1px;
  margin-bottom: 8px;
  line-height: 1;
}

.stat-change {
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 20px;
}

.stat-change.up {
  color: var(--cta);
  background: rgba(34, 197, 94, 0.1);
}

.stat-change.down {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.change-icon {
  margin-right: 2px;
}

/* ==========================================
   Bento Section
   ========================================== */
.section {
  margin-bottom: 28px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

/* Chart Controls */
.chart-controls .el-radio-group {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 4px;
  box-shadow: var(--shadow-sm);
}

.chart-controls .el-radio-button__inner {
  background: transparent;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 8px 16px;
  transition: all 0.2s ease;
}

.chart-controls .el-radio-button__original-radio:checked + .el-radio-button__inner {
  background: var(--primary);
  color: #fff;
  box-shadow: none;
}

/* ==========================================
   ByteDance Chart Card
   ========================================== */
.chart-card {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  padding: 24px;
  box-shadow: var(--shadow-card);
  border: 1px solid rgba(22, 119, 255, 0.08);
  transition: all var(--transition-bounce);
}

.chart-card:hover {
  box-shadow: var(--shadow-card-hover);
}

.chart {
  height: 320px;
  width: 100%;
}

/* ==========================================
   Bento Table Card
   ========================================== */
.table-card {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-card);
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.metrics-table {
  width: 100%;
  border-collapse: collapse;
}

.metrics-table th {
  text-align: left;
  padding: 16px 20px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
}

.metrics-table td {
  padding: 18px 20px;
  border-bottom: 1px solid var(--border-light);
  font-size: 14px;
  color: var(--text-primary);
}

.metrics-table tr:last-child td {
  border-bottom: none;
}

.metrics-table tr {
  transition: background 0.15s ease;
}

.metrics-table tr:hover td {
  background: rgba(22, 119, 255, 0.04);
}

.metric-cell {
  padding-left: 20px !important;
}

.metric-name {
  font-weight: 600;
  margin-bottom: 4px;
  font-size: 14px;
}

.metric-code {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'JetBrains Mono', Monaco, monospace;
}

.domain-badge {
  display: inline-block;
  padding: 5px 12px;
  background: var(--primary-glow);
  color: var(--primary);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.type-cell {
  color: var(--text-secondary);
  font-size: 13px;
}

.unit-cell {
  font-family: 'SF Mono', 'JetBrains Mono', Monaco, monospace;
  color: var(--text-secondary);
  font-size: 13px;
}

.freq-cell {
  color: var(--text-secondary);
  font-size: 13px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-badge.active {
  background: rgba(34, 197, 94, 0.1);
  color: var(--cta);
}

.status-badge.active::before {
  background: var(--cta);
  animation: pulse 2s infinite;
}

.status-badge.inactive {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-secondary);
}

.status-badge.inactive::before {
  background: #94A3B8;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  background: var(--bg-primary);
}

.results-count {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

/* ==========================================
   Metric Cards - 告警监控卡片
   ========================================== */
.metric-cards-scroll {
  overflow-x: auto;
  padding-bottom: 8px;
  margin: 0 -4px;
}

.metric-cards-scroll::-webkit-scrollbar {
  height: 6px;
}

.metric-cards-scroll::-webkit-scrollbar-track {
  background: var(--bg-primary);
  border-radius: 3px;
}

.metric-cards-scroll::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}

.metric-cards-scroll::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.metric-cards-row {
  display: flex;
  gap: 16px;
  padding: 4px;
}

/* Metric Card */
.metric-card {
  flex-shrink: 0;
  width: 220px;
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  padding: 18px;
  box-shadow: var(--shadow-card);
  border: 1px solid var(--border);
  transition: all var(--transition-bounce);
  cursor: pointer;
  border-left: 4px solid transparent;
}

.metric-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-card-hover);
}

/* Card States */
.metric-card.critical {
  background: #FEF2F2;
  border-left-color: #EF4444;
  border-color: rgba(239, 68, 68, 0.2);
}

.metric-card.critical .card-value .value-number {
  color: #DC2626;
}

.metric-card.warning {
  background: #FFFBEB;
  border-left-color: #F59E0B;
  border-color: rgba(245, 158, 11, 0.2);
}

.metric-card.warning .card-value .value-number {
  color: #D97706;
}

.metric-card.normal {
  background: var(--bg-card);
  border-left-color: var(--cta);
}

/* Card Header */
.card-header {
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.card-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
}

.card-status.critical {
  background: rgba(239, 68, 68, 0.1);
  color: #DC2626;
}

.card-status.critical svg {
  animation: ring 1s infinite;
}

.card-status.warning {
  background: rgba(245, 158, 11, 0.1);
  color: #D97706;
}

.card-status.normal {
  background: rgba(34, 197, 94, 0.1);
  color: var(--cta);
}

.card-edit-btn {
  opacity: 0;
  padding: 4px 6px;
  border: none;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.metric-card:hover .card-edit-btn {
  opacity: 1;
}

.card-edit-btn:hover {
  background: rgba(22, 119, 255, 0.15);
  color: var(--primary);
}

@keyframes ring {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(15deg); }
  50% { transform: rotate(-15deg); }
  75% { transform: rotate(10deg); }
}

/* Card Body */
.card-body {
  margin-bottom: 14px;
}

.card-metric-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-metric-code {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', 'SF Mono', Monaco, monospace;
  margin-bottom: 12px;
}

.card-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 8px;
}

.value-number {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
  line-height: 1;
}

.value-unit {
  font-size: 13px;
  color: var(--text-secondary);
}

.card-threshold {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 6px 10px;
  background: var(--bg-primary);
  border-radius: 8px;
}

/* Card Footer */
.card-footer {
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.metric-card.critical .card-footer {
  border-top-color: rgba(239, 68, 68, 0.2);
}

.metric-card.warning .card-footer {
  border-top-color: rgba(245, 158, 11, 0.2);
}

.last-check {
  font-size: 11px;
  color: var(--text-muted);
}

/* Refresh Button */
.refresh-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid var(--border);
  background: var(--bg-card);
}

.refresh-btn:hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-glow);
}

.refresh-btn svg {
  transition: transform 0.3s ease;
}

.refresh-btn svg.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* No Cards */
.no-cards {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted);
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  border: 1px dashed var(--border);
  min-width: 280px;
}

.no-cards p {
  font-size: 14px;
  font-weight: 500;
  margin-top: 12px;
  color: var(--text-secondary);
}

.no-cards span {
  font-size: 12px;
  margin-top: 4px;
}

/* Add Card */
.add-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border: 2px dashed var(--border);
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 180px;
}

.add-card:hover {
  border-color: var(--primary);
  background: var(--primary-glow);
}

.add-card:hover .add-icon {
  color: var(--primary);
}

.add-card:hover .add-text {
  color: var(--primary);
}

.add-icon {
  color: var(--text-muted);
  margin-bottom: 12px;
  transition: all 0.2s ease;
}

.add-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

/* Add Form */
.add-form .el-select.full-width {
  width: 100%;
}

.add-form .threshold-input {
  width: 180px;
}

.unit-label {
  margin-left: 12px;
  font-size: 14px;
  color: var(--text-secondary);
}

.metric-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.metric-option-name {
  font-weight: 500;
}

.metric-option-code {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', 'SF Mono', Monaco, monospace;
}

.condition-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.condition-group .el-radio {
  margin-right: 0;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
}

.condition-group .el-radio:hover {
  border-color: var(--primary);
}

.condition-group .el-radio.is-checked {
  border-color: var(--primary);
  background: var(--primary-glow);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* SQL Template Display */
.sql-template {
  background: #1E1E2E;
  border-radius: var(--radius-md);
  padding: 12px 16px;
  max-height: 120px;
  overflow-y: auto;
}

.sql-template code {
  font-family: 'JetBrains Mono', 'SF Mono', Monaco, monospace;
  font-size: 12px;
  color: #CDD6F4;
  white-space: pre-wrap;
  word-break: break-all;
}

.where-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
  line-height: 1.4;
}
</style>
