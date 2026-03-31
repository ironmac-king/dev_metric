<template>
  <div class="alerts-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="page-icon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M11 3C8.5 3 6.5 4.8 6.5 7V12L4.5 15V16H17.5V15L15.5 12V7C15.5 4.8 13.5 3 11 3Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M9.5 16V17C9.5 18.1 10.4 19 11.5 19C12.6 19 13.5 18.1 13.5 17V16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="header-text">
          <h1>告警配置</h1>
          <p>配置指标告警规则，及时发现数据异常</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" class="btn-primary" @click="handleCreate">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <path d="M7.5 3V12M3 7.5H12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          新增规则
        </el-button>
      </div>
    </div>

    <!-- Stats Row -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ alertRules.length }}</span>
        <span class="stat-label">告警规则</span>
      </div>
      <div class="stat-card">
        <span class="stat-value accent">{{ activeRules }}</span>
        <span class="stat-label">已启用</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ firingAlerts }}</span>
        <span class="stat-label">触发中</span>
      </div>
    </div>

    <!-- Table Card -->
    <div class="table-card">
      <el-table :data="alertRules" v-loading="loading" class="alerts-table" row-class-name="table-row">
        <el-table-column prop="name" label="规则名称" min-width="180">
          <template #default="{ row }">
            <div class="rule-name-cell">
              <span class="rule-name">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="metric_id" label="关联指标" width="150">
          <template #default="{ row }">
            <span class="metric-tag">{{ getMetricName(row.metric_id) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="condition_type" label="告警条件" width="150">
          <template #default="{ row }">
            <span class="condition-tag">
              {{ formatCondition(row.condition_type, row.threshold_value) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="持续时间" width="110" align="center">
          <template #default="{ row }">
            <span class="duration-tag">{{ row.duration }}分钟</span>
          </template>
        </el-table-column>
        <el-table-column prop="notify_status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.notify_status"
              :active-value="1"
              :inactive-value="0"
              @change="handleStatusChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <div class="action-group">
              <el-button link class="action-btn" @click="handleEdit(row)">编辑</el-button>
              <el-button link class="action-btn delete" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" class="alert-dialog">
      <el-form :model="form" label-width="100px" class="alert-form">
        <el-form-item label="规则名称" required>
          <el-input v-model="form.name" placeholder="如：广告转化率告警" />
        </el-form-item>
        <el-form-item label="关联指标" required>
          <el-select v-model="form.metric_id" placeholder="选择指标" style="width: 100%" filterable>
            <el-option
              v-for="m in metricsList"
              :key="m.id"
              :label="m.name"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="告警条件" required>
          <div class="condition-row">
            <el-select v-model="form.condition_type" style="width: 100px">
              <el-option label="大于" value="gt" />
              <el-option label="小于" value="lt" />
              <el-option label="大于等于" value="gte" />
              <el-option label="小于等于" value="lte" />
              <el-option label="等于" value="eq" />
            </el-select>
            <el-input-number v-model="form.threshold_value" :precision="4" style="width: 150px" />
          </div>
        </el-form-item>
        <el-form-item label="持续时间">
          <el-input-number v-model="form.duration" :min="1" :max="1440" style="width: 150px" /> 分钟
          <span class="form-tip">指标持续异常多少分钟后触发告警</span>
        </el-form-item>
        <el-form-item label="Webhook">
          <el-input v-model="form.dingtalk_webhook" placeholder="钉钉机器人 Webhook 地址" />
        </el-form-item>
        <el-form-item label="加签密钥">
          <el-input v-model="form.dingtalk_secret" placeholder="可选，钉钉机器人加签密钥" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.notify_status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="handleSave" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { alertAPI, metricAPI } from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const alertRules = ref([])
const metricsList = ref([])
const metricsMap = ref({})

const dialogVisible = ref(false)
const dialogTitle = ref('新增规则')
const form = ref({
  id: 0,
  name: '',
  metric_id: null,
  condition_type: 'gt',
  threshold_value: 0,
  duration: 5,
  dingtalk_webhook: '',
  dingtalk_secret: '',
  notify_status: 1
})

const activeRules = computed(() => alertRules.value.filter(r => r.notify_status === 1).length)
const firingAlerts = computed(() => 0)

onMounted(() => {
  loadAlerts()
  loadMetrics()
})

async function loadAlerts() {
  loading.value = true
  try {
    const res = await alertAPI.list()
    if (res.data) {
      alertRules.value = res.data.list || []
    }
  } catch (e) {
    alertRules.value = []
  } finally {
    loading.value = false
  }
}

async function loadMetrics() {
  try {
    const res = await metricAPI.list({ page: 1, page_size: 1000 })
    if (res.data && res.data.list) {
      metricsList.value = res.data.list
      res.data.list.forEach(m => {
        metricsMap.value[m.id] = m.name
      })
    }
  } catch (e) {
    metricsList.value = []
  }
}

function getMetricName(id) {
  return metricsMap.value[id] || `指标${id}`
}

function formatCondition(type, value) {
  const map = { gt: '>', lt: '<', gte: '>=', lte: '<=', eq: '=' }
  return `${map[type] || type} ${value}`
}

async function handleStatusChange(row) {
  try {
    await alertAPI.update(row.id, { notify_status: row.notify_status })
    ElMessage.success('更新成功')
  } catch (e) {
    ElMessage.error('更新失败')
    loadAlerts()
  }
}

function handleCreate() {
  dialogTitle.value = '新增规则'
  form.value = {
    id: 0,
    name: '',
    metric_id: null,
    condition_type: 'gt',
    threshold_value: 0,
    duration: 5,
    dingtalk_webhook: '',
    dingtalk_secret: '',
    notify_status: 1
  }
  dialogVisible.value = true
}

function handleEdit(row) {
  dialogTitle.value = '编辑规则'
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name) {
    ElMessage.warning('请输入规则名称')
    return
  }
  if (!form.value.metric_id) {
    ElMessage.warning('请选择关联指标')
    return
  }
  try {
    if (form.value.id) {
      await alertAPI.update(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await alertAPI.create(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadAlerts()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function handleDelete(row) {
  try {
    await alertAPI.delete(row.id)
    ElMessage.success('删除成功')
    loadAlerts()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.alerts-page {
  padding: 28px 32px;
  max-width: 1440px;
  margin: 0 auto;
  background: var(--bg-primary);
  min-height: 100vh;
}

/* Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-icon {
  width: 44px;
  height: 44px;
  background: #fef3c7;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b45309;
}

.header-text h1 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  letter-spacing: -0.3px;
}

.header-text p {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--primary);
  color: #ffffff;
  border: none;
  border-radius: var(--radius-lg);
  font-weight: 600;
  font-size: 14px;
  padding: 12px 24px;
  transition: all 0.25s ease;
  box-shadow: var(--shadow-card);
}

.btn-primary:hover {
  background: var(--primary-dark);
  transform: translateY(-2px) scale(1.01);
  box-shadow: var(--shadow-card-hover);
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 28px;
}

.stat-card {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  padding: 24px;
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.stat-value.accent {
  color: var(--primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

/* Table Card */
.table-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: var(--shadow-sm);
}

.alerts-table :deep(.el-table__header th) {
  background: var(--bg-primary) !important;
  font-weight: 600;
  font-size: 11px;
  color: var(--text-secondary);
  padding: 14px 12px;
  border-bottom: 1px solid var(--border);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.alerts-table :deep(.el-table__body td) {
  padding: 14px 12px;
  border-bottom: 1px solid #f4f4f5;
}

.alerts-table :deep(.el-table__row:hover > td) {
  background: var(--bg-primary) !important;
}

.rule-name-cell {
  display: flex;
  flex-direction: column;
}

.rule-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 13.5px;
}

.metric-tag {
  display: inline-block;
  padding: 3px 8px;
  background: var(--primary-glow);
  color: var(--primary);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.condition-tag {
  display: inline-block;
  padding: 3px 8px;
  background: #fef3c7;
  color: #b45309;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  font-family: 'SF Mono', Monaco, monospace;
}

.duration-tag {
  display: inline-block;
  padding: 3px 8px;
  background: #f5f3ff;
  color: #6d28d9;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.action-group {
  display: flex;
  gap: 2px;
  justify-content: center;
}

.action-btn {
  padding: 5px 10px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: 4px;
}

.action-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.action-btn.delete:hover {
  color: #ef4444;
  background: #fef2f2;
}

:deep(.el-switch.is-checked .el-switch__core) {
  background-color: var(--primary);
  border-color: var(--primary);
}

/* Dialog */
.alert-dialog :deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
}

.alert-dialog :deep(.el-dialog__title) {
  font-weight: 700;
  color: var(--text-primary);
}

.alert-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--text-primary);
}

.alert-form :deep(.el-input__wrapper),
.alert-form :deep(.el-textarea__inner) {
  border-radius: var(--radius-sm);
  box-shadow: none !important;
  border: 1px solid var(--border);
}

.alert-form :deep(.el-input__wrapper:hover),
.alert-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--primary);
}

.condition-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.form-tip {
  margin-left: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
