<template>
  <div class="alerts-page">
    <div class="page-header">
      <h2>告警配置</h2>
      <el-button type="primary" @click="handleCreate">新增规则</el-button>
    </div>

    <div class="table-card">
      <el-table :data="alertRules" v-loading="loading" stripe>
        <el-table-column prop="name" label="规则名称" min-width="150" />
        <el-table-column prop="metric_id" label="关联指标" width="120">
          <template #default="{ row }">
            {{ getMetricName(row.metric_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="condition_type" label="条件" width="100">
          <template #default="{ row }">
            {{ formatCondition(row.condition_type, row.threshold_value) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="持续时间" width="100">
          <template #default="{ row }">
            {{ row.duration }}分钟
          </template>
        </el-table-column>
        <el-table-column prop="notify_status" label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.notify_status"
              :active-value="1"
              :inactive-value="0"
              @change="handleStatusChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { alertAPI } from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const alertRules = ref([])
const metricsMap = ref({})

onMounted(() => {
  loadAlerts()
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
  ElMessage.info('创建规则功能开发中')
}

function handleEdit(row) {
  ElMessage.info('编辑规则功能开发中')
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
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.table-card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 24px;
}
</style>
