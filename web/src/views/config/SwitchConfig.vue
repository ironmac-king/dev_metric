<template>
  <div class="switch-config">
    <!-- Global Switch -->
    <div class="global-switch-card">
      <div class="global-info">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="8" stroke="#6366f1" stroke-width="1.5"/>
          <circle cx="10" cy="10" r="4" fill="#6366f1"/>
        </svg>
        <div>
          <h3>全局分析开关</h3>
          <p>控制智能分析功能的整体启用状态</p>
        </div>
      </div>
      <div class="global-toggle">
        <span :class="['status-dot', globalEnabled ? 'active' : 'inactive']"></span>
        <span class="status-text">{{ globalEnabled ? '已启用' : '已禁用' }}</span>
      </div>
    </div>

    <!-- Trigger Switches -->
    <div class="switch-grid">
      <div v-for="sw in switches" :key="sw.trigger_type" class="switch-card" :class="sw.switch_status">
        <div class="switch-header">
          <span class="switch-type">{{ sw.trigger_type }}</span>
          <span :class="['status-badge', sw.switch_status]">{{ statusLabel(sw.switch_status) }}</span>
        </div>
        <div class="switch-body">
          <div v-if="sw.switch_status === 'gray'" class="gray-info">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.2"/>
              <path d="M7 4V7.5M7 10H7.01" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
            灰度比例: {{ sw.gray_ratio || 100 }}%
          </div>
          <div v-if="sw.switch_reason" class="switch-reason">{{ sw.switch_reason }}</div>
          <div v-if="sw.operator" class="switch-operator">操作人: {{ sw.operator }}</div>
        </div>
        <div class="switch-actions">
          <button v-if="sw.trigger_type !== 'all'" class="btn-action" @click="showSetDialog(sw)">
            {{ sw.switch_status === 'disabled' ? '启用' : '设置' }}
          </button>
          <button v-if="sw.trigger_type !== 'all' && sw.switch_status !== 'disabled'" class="btn-action btn-danger" @click="handleDisable(sw)">
            关闭
          </button>
        </div>
      </div>
    </div>

    <!-- Set Dialog -->
    <el-dialog v-model="dialogVisible" title="设置灰度" width="440px" class="switch-dialog">
      <div class="dialog-content">
        <div class="dialog-type">{{ currentSwitch?.trigger_type }}</div>
        <div class="dialog-field">
          <label>状态</label>
          <el-select v-model="dialogForm.switch_status" class="form-select">
            <el-option label="启用" value="enabled" />
            <el-option label="禁用" value="disabled" />
            <el-option label="灰度" value="gray" />
          </el-select>
        </div>
        <div v-if="dialogForm.switch_status === 'gray'" class="dialog-field">
          <label>灰度比例</label>
          <div class="slider-row">
            <el-slider v-model="dialogForm.gray_ratio" :min="1" :max="100" :step="1" :show-tooltip="true" />
            <span class="slider-value">{{ dialogForm.gray_ratio }}%</span>
          </div>
        </div>
        <div class="dialog-field">
          <label>原因</label>
          <el-input v-model="dialogForm.switch_reason" placeholder="可选" />
        </div>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSetSwitch" :loading="saving">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { triggerSwitchAPI } from '@/api'

const switches = ref([])
const dialogVisible = ref(false)
const currentSwitch = ref(null)
const saving = ref(false)

const dialogForm = reactive({
  switch_status: 'enabled',
  gray_ratio: 100,
  switch_reason: '',
  operator: ''
})

const globalEnabled = computed(() => {
  const allSwitch = switches.value.find(s => s.trigger_type === 'all')
  return allSwitch?.switch_status === 'enabled'
})

const statusLabel = (status) => {
  const map = { enabled: '已启用', disabled: '已禁用', gray: '灰度' }
  return map[status] || status
}

const loadSwitches = async () => {
  try {
    const res = await triggerSwitchAPI.list()
    switches.value = res.data || []
  } catch (e) {
    ElMessage.error('加载开关配置失败')
  }
}

const showSetDialog = (sw) => {
  currentSwitch.value = sw
  dialogForm.switch_status = sw.switch_status || 'enabled'
  dialogForm.gray_ratio = sw.gray_ratio || 100
  dialogForm.switch_reason = sw.switch_reason || ''
  dialogForm.operator = sw.operator || ''
  dialogVisible.value = true
}

const handleSetSwitch = async () => {
  if (!currentSwitch.value) return
  saving.value = true
  try {
    await triggerSwitchAPI.set(currentSwitch.value.trigger_type, {
      switch_status: dialogForm.switch_status,
      gray_ratio: dialogForm.switch_status === 'gray' ? dialogForm.gray_ratio : 100,
      switch_reason: dialogForm.switch_reason,
      operator: dialogForm.operator
    })
    ElMessage.success('设置成功')
    dialogVisible.value = false
    loadSwitches()
  } catch (e) {
    ElMessage.error('设置失败')
  } finally {
    saving.value = false
  }
}

const handleDisable = async (sw) => {
  try {
    await ElMessageBox.confirm(`确定关闭 [${sw.trigger_type}] 触发器吗？`, '关闭确认', {
      confirmButtonText: '关闭',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await triggerSwitchAPI.set(sw.trigger_type, {
      switch_status: 'disabled',
      gray_ratio: 0,
      switch_reason: '手动关闭',
      operator: 'admin'
    })
    ElMessage.success('已关闭')
    loadSwitches()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

onMounted(loadSwitches)
</script>

<style scoped>
.switch-config {
  padding: 0 4px;
}

.global-switch-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: linear-gradient(135deg, #f5f3ff, #ede9fe);
  border-radius: 14px;
  border: 1px solid #ddd6fe;
  margin-bottom: 20px;
}

.global-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.global-info h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1e1b4b;
}

.global-info p {
  margin: 4px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.global-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-dot.active {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
}

.status-dot.inactive {
  background: #ef4444;
}

.status-text {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.switch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.switch-card {
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 16px;
  transition: all 0.2s;
}

.switch-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.1);
}

.switch-card.disabled {
  opacity: 0.6;
}

.switch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.switch-type {
  font-size: 14px;
  font-weight: 600;
  color: #1e1b4b;
  font-family: 'Fira Code', monospace;
}

.status-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.enabled {
  background: #d1fae5;
  color: #059669;
}

.status-badge.disabled {
  background: #fee2e2;
  color: #dc2626;
}

.status-badge.gray {
  background: #fef3c7;
  color: #d97706;
}

.switch-body {
  margin-bottom: 12px;
  min-height: 40px;
}

.gray-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #d97706;
  margin-bottom: 6px;
}

.switch-reason {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.switch-operator {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}

.switch-actions {
  display: flex;
  gap: 8px;
}

.btn-action {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-action:hover {
  border-color: #6366f1;
  color: #6366f1;
}

.btn-action.btn-danger:hover {
  border-color: #ef4444;
  color: #ef4444;
}

.switch-dialog .dialog-content {
  padding: 8px 0;
}

.dialog-type {
  font-size: 18px;
  font-weight: 600;
  color: #1e1b4b;
  font-family: 'Fira Code', monospace;
  margin-bottom: 20px;
  text-align: center;
}

.dialog-field {
  margin-bottom: 16px;
}

.dialog-field label {
  display: block;
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 6px;
}

.form-select {
  width: 100%;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider-row .el-slider {
  flex: 1;
}

.slider-value {
  font-size: 14px;
  font-weight: 600;
  color: #6366f1;
  min-width: 48px;
  text-align: right;
}
</style>
