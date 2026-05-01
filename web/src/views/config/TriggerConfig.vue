<template>
  <div class="trigger-config">
    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-select v-model="filterTriggerType" placeholder="触发类型" clearable size="default" class="filter-select">
          <el-option label="volatility" value="volatility" />
          <el-option label="generic_query" value="generic_query" />
          <el-option label="ad_effect" value="ad_effect" />
          <el-option label="inventory_risk" value="inventory_risk" />
          <el-option label="comparison" value="comparison" />
          <el-option label="context_followup" value="context_followup" />
        </el-select>
        <el-select v-model="filterEnabled" placeholder="状态" clearable size="default" class="filter-select">
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
        <el-button @click="loadConfigs" class="btn-refresh">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 7C2 4.2 4.2 2 7 2C9.8 2 12 4.2 12 7M12 7C12 9.8 9.8 12 7 12C4.2 12 2 9.8 2 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            <path d="M10 5L12 7L10 9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          刷新
        </el-button>
      </div>
      <el-button type="primary" class="btn-primary" @click="showCreateDialog">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        添加规则
      </el-button>
    </div>

    <!-- Table -->
    <div class="table-card">
      <table class="config-table">
        <thead>
          <tr>
            <th>触发类型</th>
            <th>指标编码</th>
            <th>条件配置</th>
            <th>优先级</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="cfg in configs" :key="cfg.id">
            <td><span class="type-badge">{{ cfg.trigger_type }}</span></td>
            <td class="metric-code">{{ cfg.metric_code || '全部' }}</td>
            <td class="condition-cell">
              <div v-if="cfg.condition" class="condition-tags">
                <span v-if="cfg.condition.mom" class="condition-tag">环比 {{ cfg.condition.mom }}%</span>
                <span v-if="cfg.condition.yoy" class="condition-tag">同比 {{ cfg.condition.yoy }}%</span>
                <span v-if="cfg.condition.days_warning" class="condition-tag">预警 {{ cfg.condition.days_warning }}天</span>
              </div>
              <span v-else>—</span>
            </td>
            <td class="priority-cell">{{ cfg.priority }}</td>
            <td>
              <el-switch :model-value="cfg.enabled" @change="handleEnabledChange(cfg, $event)" />
            </td>
            <td>
              <div class="action-btns">
                <button class="btn-icon" @click="showEditDialog(cfg)" title="编辑">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M11.5 2.5L13.5 4.5M2 14L3.5 10L12 1.5L14.5 4L5.5 13L2 14Z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
                  </svg>
                </button>
                <button class="btn-icon btn-danger" @click="handleDelete(cfg)" title="删除">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M3 4H13M5.5 4V3C5.5 2.5 6 2 6.5 2H9.5C10 2 10.5 2.5 10.5 3V4M12 4V13C12 13.5 11.5 14 11 14H5C4.5 14 4 13.5 4 13V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="configs.length === 0">
            <td colspan="6" class="empty-cell">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" class="config-dialog">
      <el-form :model="form" label-width="100px" class="config-form">
        <el-form-item label="触发类型" required>
          <el-select v-model="form.trigger_type" placeholder="选择触发类型" class="form-select">
            <el-option label="volatility - 波动触发" value="volatility" />
            <el-option label="generic_query - 泛问触发" value="generic_query" />
            <el-option label="ad_effect - 广告效果" value="ad_effect" />
            <el-option label="inventory_risk - 库存风险" value="inventory_risk" />
            <el-option label="comparison - 对比触发" value="comparison" />
            <el-option label="context_followup - 追问触发" value="context_followup" />
          </el-select>
        </el-form-item>
        <el-form-item label="指标名称">
          <el-select v-model="form.metric_code" placeholder="选择指标（留空则对所有指标生效）" clearable filterable class="form-select">
            <el-option v-for="m in metricList" :key="m.metric_code" :label="m.name" :value="m.name">
              <span style="float:left">{{ m.name }}</span>
              <span style="float:right;color:#9ca3af;font-size:12px">{{ m.metric_code }}</span>
            </el-option>
          </el-select>
          <div class="form-tip">留空表示对所有指标生效；也可选择具体指标</div>
        </el-form-item>
        <el-form-item label="环比阈值(%)">
          <el-input-number v-model="form.mom_threshold" :min="-100" :max="0" :step="1" />
        </el-form-item>
        <el-form-item label="同比阈值(%)">
          <el-input-number v-model="form.yoy_threshold" :min="-100" :max="0" :step="1" />
        </el-form-item>
        <el-form-item label="阈值类型">
          <el-select v-model="form.threshold_type" placeholder="阈值类型" class="form-select">
            <el-option label="normal - 普通" value="normal" />
            <el-option label="strict - 严格" value="strict" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="0" :max="100" :step="1" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.enabled" />
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
import { triggerConfigAPI } from '@/api'
import api from '@/api/index'

const configs = ref([])
const metricList = ref([])
const filterTriggerType = ref('')
const filterEnabled = ref('')
const dialogVisible = ref(false)
const dialogTitle = ref('添加触发规则')
const saving = ref(false)
const editingId = ref(null)

const form = reactive({
  trigger_type: '',
  metric_code: '',
  mom_threshold: -10,
  yoy_threshold: -15,
  threshold_type: 'normal',
  priority: 0,
  enabled: true
})

const loadConfigs = async () => {
  try {
    const params = {}
    if (filterTriggerType.value) params.trigger_type = filterTriggerType.value
    if (filterEnabled.value !== '') params.enabled = filterEnabled.value
    const res = await triggerConfigAPI.list(params)
    configs.value = res.data || []
  } catch (e) {
    ElMessage.error('加载触发规则失败')
  }
}

const loadMetrics = async () => {
  try {
    const res = await api.get('/metadata/metrics')
    metricList.value = res.data || []
  } catch (e) {
    console.warn('加载指标列表失败', e)
  }
}

const showCreateDialog = () => {
  editingId.value = null
  dialogTitle.value = '添加触发规则'
  Object.assign(form, {
    trigger_type: 'volatility',
    metric_code: '',
    mom_threshold: -10,
    yoy_threshold: -15,
    threshold_type: 'normal',
    priority: 0,
    enabled: true
  })
  dialogVisible.value = true
}

const showEditDialog = (cfg) => {
  editingId.value = cfg.id
  dialogTitle.value = '编辑触发规则'
  form.trigger_type = cfg.trigger_type
  form.metric_code = cfg.metric_code || ''
  form.mom_threshold = cfg.condition?.mom || -10
  form.yoy_threshold = cfg.condition?.yoy || -15
  form.threshold_type = cfg.condition?.threshold_type || 'normal'
  form.priority = cfg.priority || 0
  form.enabled = cfg.enabled !== false
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.trigger_type) {
    ElMessage.warning('请选择触发类型')
    return
  }
  saving.value = true
  try {
    const condition = {}
    if (form.trigger_type === 'volatility' || form.trigger_type === 'generic_query') {
      condition.mom = form.mom_threshold
      condition.yoy = form.yoy_threshold
      condition.threshold_type = form.threshold_type
    } else if (form.trigger_type === 'inventory_risk') {
      condition.days_warning = Math.abs(form.mom_threshold)
    }

    const payload = {
      trigger_type: form.trigger_type,
      metric_code: form.metric_code || null,
      condition,
      priority: form.priority,
      enabled: form.enabled
    }

    if (editingId.value) {
      await triggerConfigAPI.update(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await triggerConfigAPI.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadConfigs()
  } catch (e) {
    ElMessage.error(editingId.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (cfg) => {
  try {
    await ElMessageBox.confirm(`确定删除触发规则 [${cfg.trigger_type}] 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await triggerConfigAPI.delete(cfg.id)
    ElMessage.success('删除成功')
    loadConfigs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleEnabledChange = async (cfg, val) => {
  try {
    await triggerConfigAPI.update(cfg.id, { enabled: val })
    ElMessage.success(val ? '已启用' : '已禁用')
    loadConfigs()
  } catch (e) {
    ElMessage.error('更新状态失败')
  }
}

onMounted(() => {
  loadConfigs()
  loadMetrics()
})
</script>

<style scoped>
.trigger-config {
  padding: 0 4px;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.filter-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-select {
  width: 160px;
}

.btn-refresh {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: white;
  color: #6b7280;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-refresh:hover {
  border-color: #6366f1;
  color: #6366f1;
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
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  color: #374151;
}

.config-table tr:last-child td {
  border-bottom: none;
}

.config-table tr:hover td {
  background: #f9f8ff;
}

.type-badge {
  display: inline-block;
  padding: 3px 10px;
  background: #ede9fe;
  color: #6366f1;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  font-family: 'Fira Code', monospace;
}

.metric-code {
  font-family: 'Fira Code', monospace;
  color: #9ca3af;
  font-size: 13px;
}

.condition-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.condition-tag {
  display: inline-block;
  padding: 2px 8px;
  background: #fef3c7;
  color: #d97706;
  border-radius: 4px;
  font-size: 12px;
}

.priority-cell {
  font-weight: 600;
  color: #6366f1;
}

.action-btns {
  display: flex;
  gap: 8px;
}

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

.btn-icon:hover {
  border-color: #6366f1;
  color: #6366f1;
}

.btn-icon.btn-danger:hover {
  border-color: #ef4444;
  color: #ef4444;
}

.empty-cell {
  text-align: center;
  color: #9ca3af;
  padding: 40px 16px !important;
}

.config-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 20px;
  margin-right: 0;
}

.config-dialog :deep(.el-dialog__body) {
  padding: 24px 20px;
}

.config-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #e5e7eb;
  padding: 16px 20px;
}

.config-form .form-select {
  width: 100%;
}

.form-tip {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}
</style>
