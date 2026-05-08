<template>
  <div class="ask-analysis-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="page-icon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M11 2L2 7V15L11 20L20 15V7L11 2Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M11 12L11 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <circle cx="11" cy="14" r="1" fill="currentColor"/>
          </svg>
        </div>
        <div class="header-text">
          <h1>问数分析</h1>
          <p>分析智能问数的对话记录与失败原因</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button class="btn-secondary" @click="handleExport">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <path d="M7.5 10V3M7.5 10L4 6.5M7.5 10L11 6.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M3 12H12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          导出
        </el-button>
      </div>
    </div>

    <!-- KPI Cards -->
    <div class="kpi-cards">
      <div class="kpi-card">
        <div class="kpi-value">{{ stats.total }}</div>
        <div class="kpi-label">总对话数</div>
      </div>
      <div class="kpi-card success">
        <div class="kpi-value">{{ stats.success }}</div>
        <div class="kpi-label">成功</div>
      </div>
      <div class="kpi-card danger">
        <div class="kpi-value">{{ stats.fail }}</div>
        <div class="kpi-label">失败</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value">{{ stats.successRate }}%</div>
        <div class="kpi-label">成功率</div>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="filter-tabs">
        <button
          class="filter-tab"
          :class="{ active: filterStatus === 'all' }"
          @click="filterStatus = 'all'; fetchLogs()"
        >
          全部
        </button>
        <button
          class="filter-tab"
          :class="{ active: filterStatus === 'true' }"
          @click="filterStatus = 'true'; fetchLogs()"
        >
          <span class="status-dot success"></span>
          成功
        </button>
        <button
          class="filter-tab"
          :class="{ active: filterStatus === 'false' }"
          @click="filterStatus = 'false'; fetchLogs()"
        >
          <span class="status-dot danger"></span>
          失败
        </button>
      </div>
      <div class="filter-time">
        <el-select v-model="timeRange" placeholder="时间范围" @change="fetchLogs">
          <el-option label="近7天" value="7" />
          <el-option label="近30天" value="30" />
          <el-option label="近90天" value="90" />
        </el-select>
      </div>
    </div>

    <!-- Data Table -->
    <div class="table-card">
      <el-table
        :data="logs"
        v-loading="loading"
        class="analysis-table"
        row-class-name="table-row"
        row-key="id"
        @row-click="handleRowClick"
        highlight-current-row
        :expand-row-keys="expandedRows"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-panel" v-if="expandedRows.includes(row.id)">
              <div class="expand-section">
                <div class="expand-label">用户问题</div>
                <div class="expand-value">{{ row.question }}</div>
              </div>
              <div class="expand-section" v-if="!row.success">
                <div class="expand-label">失败阶段</div>
                <div class="expand-value">
                  <span class="fail-stage-badge" :class="row.fail_stage">
                    {{ getFailStageText(row.fail_stage) }}
                  </span>
                </div>
              </div>
              <div class="expand-section" v-if="!row.success && row.fail_reason">
                <div class="expand-label">失败原因</div>
                <div class="expand-value warning-text">{{ row.fail_reason }}</div>
              </div>
              <div class="expand-section" v-if="!row.success && row.suggestion">
                <div class="expand-label">建议解决方案</div>
                <div class="expand-value suggestion-text">{{ row.suggestion }}</div>
              </div>
              <div class="expand-section" v-if="row.intent">
                <div class="expand-label">识别的意图</div>
                <div class="expand-value">{{ row.intent }}</div>
              </div>
              <div class="expand-section thinking-section" v-if="row.thinking_steps">
                <div class="expand-label">分析过程</div>
                <div class="thinking-steps">
                  <div
                    v-for="(step, idx) in parseThinkingSteps(row.thinking_steps)"
                    :key="idx"
                    class="thinking-step"
                    :class="step.status"
                  >
                    <span class="step-icon">
                      <svg v-if="step.status === 'completed'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.5"/>
                        <path d="M3.5 6L5 7.5L8.5 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                      </svg>
                      <svg v-else-if="step.status === 'error' || step.status === 'requires_clarification'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.5"/>
                        <path d="M4 4L8 8M8 4L4 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                      </svg>
                      <svg v-else width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.5"/>
                      </svg>
                    </span>
                    <span class="step-name">{{ step.step }}</span>
                    <span class="step-content" v-if="step.content">{{ step.content }}</span>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="session_id" label="会话ID" width="200">
          <template #default="{ row }">
            <span class="session-id">{{ row.session_id.substring(0, 8) }}...</span>
          </template>
        </el-table-column>
        <el-table-column prop="question" label="问题摘要" min-width="280">
          <template #default="{ row }">
            <span class="question-text">{{ row.question.substring(0, 50) }}{{ row.question.length > 50 ? '...' : '' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="intent" label="意图" width="120">
          <template #default="{ row }">
            <span class="intent-tag">{{ row.intent || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="success" label="状态" width="100">
          <template #default="{ row }">
            <span class="status-badge" :class="row.success ? 'success' : 'danger'">
              {{ row.success ? '成功' : '失败' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="160">
          <template #default="{ row }">
            <span class="time-text">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <button class="expand-btn" @click.stop="toggleExpand(row)">
              {{ expandedRows.includes(row.id) ? '收起' : '查看' }}
            </button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { askAnalysisAPI } from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const logs = ref([])
const expandedRows = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filterStatus = ref('all')
const timeRange = ref('7')

// Stats computed from logs
const stats = computed(() => {
  const successCount = logs.value.filter(l => l.success).length
  const failCount = logs.value.filter(l => !l.success).length
  const totalCount = logs.value.length
  return {
    total: total.value,
    success: successCount,
    fail: failCount,
    successRate: totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 0
  }
})

async function fetchLogs() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterStatus.value !== 'all') {
      params.success = filterStatus.value
    }
    // 添加日期范围筛选
    if (timeRange.value) {
      const days = parseInt(timeRange.value)
      const end = new Date()
      const start = new Date()
      start.setDate(end.getDate() - days)
      params.start_date = start.toISOString().split('T')[0]
      params.end_date = end.toISOString().split('T')[0]
    }
    // 添加当前用户ID筛选
    const userInfo = localStorage.getItem('user_info')
    if (userInfo) {
      try {
        const user = JSON.parse(userInfo)
        if (user && user.id) {
          params.user_id = String(user.id)
        }
      } catch (e) {
        console.error('解析用户信息失败:', e)
      }
    }

    const res = await askAnalysisAPI.getLogs(params)
    if (res.code === 0) {
      logs.value = res.data.list || []
      total.value = res.data.pagination?.total || 0
    } else {
      ElMessage.error(res.message || '获取日志失败')
    }
  } catch (err) {
    console.error('获取日志失败:', err)
    ElMessage.error('获取日志失败')
  } finally {
    loading.value = false
  }
}

function handleRowClick(row) {
  toggleExpand(row)
}

function toggleExpand(row) {
  const idx = expandedRows.value.indexOf(row.id)
  if (idx >= 0) {
    expandedRows.value.splice(idx, 1)
  } else {
    expandedRows.value.push(row.id)
  }
}

function handleExpandChange(row, expanded) {
  if (expanded) {
    if (!expandedRows.value.includes(row.id)) {
      expandedRows.value.push(row.id)
    }
  } else {
    const idx = expandedRows.value.indexOf(row.id)
    if (idx >= 0) {
      expandedRows.value.splice(idx, 1)
    }
  }
}

function handleSizeChange(val) {
  pageSize.value = val
  fetchLogs()
}

function handlePageChange(val) {
  currentPage.value = val
  fetchLogs()
}

function handleExport() {
  ElMessage.info('导出功能开发中')
}

function getFailStageText(stage) {
  const map = {
    'intent': '意图识别',
    'entity': '实体提取',
    'sql': 'SQL生成',
    'execute': '数据查询',
    'unknown': '未知'
  }
  return map[stage] || stage || '未知'
}

function formatTime(time) {
  if (!time) return '-'
  const d = new Date(time)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function parseThinkingSteps(stepsJson) {
  if (!stepsJson) return []
  try {
    const steps = typeof stepsJson === 'string' ? JSON.parse(stepsJson) : stepsJson
    return Array.isArray(steps) ? steps : []
  } catch {
    return []
  }
}

onMounted(() => {
  fetchLogs()
})
</script>

<style scoped>
.ask-analysis-page {
  padding: 24px;
  background: #f8fafc;
  min-height: 100vh;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.page-icon {
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.header-text h1 {
  font-size: 22px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 4px 0;
}

.header-text p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
}

/* KPI Cards */
.kpi-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.kpi-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  border: 1px solid #e2e8f0;
}

.kpi-card.success .kpi-value {
  color: #16a34a;
}

.kpi-card.danger .kpi-value {
  color: #dc2626;
}

.kpi-value {
  font-size: 32px;
  font-weight: 700;
  color: #0f172a;
  font-family: 'Fira Code', monospace;
}

.kpi-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 4px;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 16px;
  border: 1px solid #e2e8f0;
}

.filter-tabs {
  display: flex;
  gap: 4px;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-tab:hover {
  background: #f1f5f9;
  color: #475569;
}

.filter-tab.active {
  background: #eff6ff;
  color: #1e40af;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.success {
  background: #16a34a;
}

.status-dot.danger {
  background: #dc2626;
}

.filter-time :deep(.el-select) {
  width: 120px;
}

.filter-time :deep(.el-input__wrapper) {
  border-radius: 8px;
}

/* Table Card */
.table-card {
  background: white;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.analysis-table {
  font-size: 13px;
}

.analysis-table :deep(.el-table__header th) {
  background: #f8fafc !important;
  color: #475569;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.analysis-table :deep(.el-table__row) {
  cursor: pointer;
  transition: background 0.15s;
}

.analysis-table :deep(.el-table__row:hover) {
  background: #f8fafc;
}

.session-id {
  font-family: 'Fira Code', monospace;
  color: #64748b;
  font-size: 12px;
}

.question-text {
  color: #1e293b;
}

.intent-tag {
  display: inline-block;
  padding: 2px 8px;
  background: #f1f5f9;
  border-radius: 4px;
  color: #475569;
  font-size: 12px;
}

.status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.success {
  background: #dcfce7;
  color: #16a34a;
}

.status-badge.danger {
  background: #fee2e2;
  color: #dc2626;
}

.time-text {
  color: #64748b;
  font-size: 12px;
}

.expand-btn {
  padding: 4px 12px;
  background: #f1f5f9;
  border: none;
  border-radius: 6px;
  color: #475569;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.expand-btn:hover {
  background: #e2e8f0;
  color: #1e293b;
}

/* Expand Panel */
.expand-panel {
  padding: 16px 20px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.expand-section {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 12px;
  margin-bottom: 12px;
  align-items: start;
}

.expand-section:last-child {
  margin-bottom: 0;
}

.expand-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding-top: 2px;
}

.expand-value {
  font-size: 13px;
  color: #1e293b;
}

.warning-text {
  color: #d97706;
  padding: 6px 10px;
  background: #fef3c7;
  border-radius: 6px;
}

.suggestion-text {
  color: #059669;
  padding: 6px 10px;
  background: #d1fae5;
  border-radius: 6px;
}

.fail-stage-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.fail-stage-badge.intent {
  background: #dbeafe;
  color: #1d4ed8;
}

.fail-stage-badge.entity {
  background: #fef3c7;
  color: #d97706;
}

.fail-stage-badge.sql {
  background: #ede9fe;
  color: #7c3aed;
}

.fail-stage-badge.execute {
  background: #fee2e2;
  color: #dc2626;
}

/* Thinking Steps in expand panel */
.thinking-section {
  display: block;
}

.thinking-section .expand-label {
  margin-bottom: 8px;
}

.thinking-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.thinking-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.thinking-step.requires_clarification,
.thinking-step.error {
  background: #fffbeb;
  border-color: #fcd34d;
}

.step-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

.thinking-step.completed .step-icon {
  color: #16a34a;
}

.thinking-step.requires_clarification .step-icon,
.thinking-step.error .step-icon {
  color: #f59e0b;
}

.step-name {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}

.step-content {
  font-size: 12px;
  color: #64748b;
  margin-left: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-width: 600px;
}

/* Pagination */
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 16px;
  border-top: 1px solid #f1f5f9;
}

.pagination-bar :deep(.el-pagination) {
  font-size: 13px;
}
</style>
