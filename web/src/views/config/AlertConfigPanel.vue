<template>
  <div class="alert-config-panel">
    <div class="panel-toolbar">
      <el-button type="primary" class="btn-primary" @click="showCreateDialog">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        新增规则
      </el-button>
    </div>

    <!-- Table -->
    <div class="table-card">
      <table class="config-table">
        <thead>
          <tr>
            <th>规则名称</th>
            <th>指标</th>
            <th>条件</th>
            <th>阈值</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rule in rules" :key="rule.id">
            <td class="name-cell">{{ rule.name }}</td>
            <td class="metric-cell">{{ rule.metric_name || rule.metric_code || '—' }}</td>
            <td class="condition-cell">{{ conditionLabel(rule.condition_type) }}</td>
            <td class="threshold-cell">{{ rule.threshold_value }}</td>
            <td>
              <el-switch :model-value="rule.notify_status === 1" @change="handleStatusChange(rule, $event)" />
            </td>
            <td>
              <div class="action-btns">
                <button class="btn-icon" @click="showEditDialog(rule)" title="编辑">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M11.5 2.5L13.5 4.5M2 14L3.5 10L12 1.5L14.5 4L5.5 13L2 14Z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
                  </svg>
                </button>
                <button class="btn-icon btn-danger" @click="handleDelete(rule)" title="删除">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M3 4H13M5.5 4V3C5.5 2.5 6 2 6.5 2H9.5C10 2 10.5 2.5 10.5 3V4M12 4V13C12 13.5 11.5 14 11 14H5C4.5 14 4 13.5 4 13V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="rules.length === 0">
            <td colspan="6" class="empty-cell">暂无告警规则</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px" class="alert-dialog">
      <el-form :model="form" label-width="100px" class="config-form">
        <el-form-item label="规则名称" required>
          <el-input v-model="form.name" placeholder="如: GMV下降告警" />
        </el-form-item>
        <el-form-item label="指标">
          <el-input v-model="form.metric_code" placeholder="指标编码，如: gmv" />
        </el-form-item>
        <el-form-item label="条件" required>
          <el-select v-model="form.condition_type" placeholder="选择条件" class="form-select">
            <el-option label="大于 (gt)" value="gt" />
            <el-option label="小于 (lt)" value="lt" />
            <el-option label="大于等于 (gte)" value="gte" />
            <el-option label="小于等于 (lte)" value="lte" />
            <el-option label="等于 (eq)" value="eq" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值">
          <el-input-number v-model="form.threshold_value" :step="0.01" />
        </el-form-item>
        <el-form-item label="Webhook">
          <el-input v-model="form.dingtalk_webhook" placeholder="钉钉 Webhook 地址" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.notify_status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { alertAPI } from '@/api'

const rules = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增告警规则')
const saving = ref(false)
const editingId = ref(null)

const form = reactive({
  name: '',
  metric_code: '',
  condition_type: 'lt',
  threshold_value: 0,
  dingtalk_webhook: '',
  notify_status: 1
})

const conditionLabel = (type) => {
  const map = { gt: '>', lt: '<', gte: '>=', lte: '<=', eq: '=' }
  return map[type] || type
}

const loadRules = async () => {
  try {
    const res = await alertAPI.list()
    rules.value = res.data || []
  } catch (e) {
    ElMessage.error('加载告警规则失败')
  }
}

const showCreateDialog = () => {
  editingId.value = null
  dialogTitle.value = '新增告警规则'
  Object.assign(form, { name: '', metric_code: '', condition_type: 'lt', threshold_value: 0, dingtalk_webhook: '', notify_status: 1 })
  dialogVisible.value = true
}

const showEditDialog = (rule) => {
  editingId.value = rule.id
  dialogTitle.value = '编辑告警规则'
  form.name = rule.name
  form.metric_code = rule.metric_code || ''
  form.condition_type = rule.condition_type
  form.threshold_value = rule.threshold_value
  form.dingtalk_webhook = rule.dingtalk_webhook || ''
  form.notify_status = rule.notify_status
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.name || !form.condition_type) {
    ElMessage.warning('请填写完整信息')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await alertAPI.update(editingId.value, form)
      ElMessage.success('更新成功')
    } else {
      await alertAPI.create(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadRules()
  } catch (e) {
    ElMessage.error(editingId.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (rule) => {
  try {
    await ElMessageBox.confirm(`确定删除告警规则 [${rule.name}] 吗？`, '删除确认', { type: 'warning' })
    await alertAPI.delete(rule.id)
    ElMessage.success('删除成功')
    loadRules()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleStatusChange = async (rule, val) => {
  try {
    await alertAPI.update(rule.id, { notify_status: val ? 1 : 0 })
    ElMessage.success(val ? '已启用' : '已禁用')
    loadRules()
  } catch (e) {
    ElMessage.error('更新状态失败')
  }
}

onMounted(loadRules)
</script>

<style scoped>
.alert-config-panel { padding: 0 4px; }

.panel-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #6366f1, #818cf8);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary:hover {
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  transform: translateY(-1px);
}

.table-card {
  background: #fafafa;
  border-radius: 12px;
  border: 1px solid #f0f0f0;
  overflow: hidden;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.config-table th {
  text-align: left;
  padding: 12px 16px;
  background: #f5f3ff;
  color: #6b7280;
  font-weight: 600;
  font-size: 13px;
  border-bottom: 1px solid #e5e7eb;
}

.config-table td {
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
  color: #374151;
}

.config-table tr:last-child td { border-bottom: none; }
.config-table tr:hover td { background: #f9f8ff; }

.name-cell { font-weight: 500; }

.metric-cell {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: #6366f1;
}

.condition-cell {
  font-size: 16px;
  font-weight: 700;
  color: #6366f1;
}

.threshold-cell {
  font-weight: 600;
  color: #374151;
}

.action-btns { display: flex; gap: 8px; }

.btn-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: white;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-icon:hover { border-color: #6366f1; color: #6366f1; }
.btn-icon.btn-danger:hover { border-color: #ef4444; color: #ef4444; }

.empty-cell {
  text-align: center;
  color: #9ca3af;
  padding: 40px 16px !important;
}

.alert-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 20px;
  margin-right: 0;
}

.alert-dialog :deep(.el-dialog__body) { padding: 24px 20px; }
.alert-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #e5e7eb;
  padding: 16px 20px;
}

.config-form .form-select { width: 100%; }
</style>
