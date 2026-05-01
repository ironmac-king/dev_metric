<template>
  <div class="label-config">
    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-select v-model="filterType" placeholder="维度类型" clearable size="default" class="filter-select">
          <el-option label="country" value="country" />
          <el-option label="platform" value="platform" />
          <el-option label="ad_channel" value="ad_channel" />
          <el-option label="sku" value="sku" />
          <el-option label="currency" value="currency" />
        </el-select>
        <el-button @click="loadLabels" class="btn-refresh">
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
        添加标签
      </el-button>
    </div>

    <!-- Table -->
    <div class="table-card">
      <table class="config-table">
        <thead>
          <tr>
            <th>维度类型</th>
            <th>原始值</th>
            <th>显示名称</th>
            <th>图标</th>
            <th>优先级</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="label in labels" :key="label.id">
            <td><span class="type-badge">{{ label.dimension_type }}</span></td>
            <td class="raw-value">{{ label.raw_value }}</td>
            <td class="display-name">
              <span v-if="label.emoji" class="emoji">{{ label.emoji }}</span>
              {{ label.display_name }}
            </td>
            <td class="emoji-cell">{{ label.emoji || '—' }}</td>
            <td class="priority-tag">{{ label.priority_tag || '—' }}</td>
            <td>
              <div class="action-btns">
                <button class="btn-icon" @click="showEditDialog(label)" title="编辑">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M11.5 2.5L13.5 4.5M2 14L3.5 10L12 1.5L14.5 4L5.5 13L2 14Z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
                  </svg>
                </button>
                <button class="btn-icon btn-danger" @click="handleDelete(label)" title="删除">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M3 4H13M5.5 4V3C5.5 2.5 6 2 6.5 2H9.5C10 2 10.5 2.5 10.5 3V4M12 4V13C12 13.5 11.5 14 11 14H5C4.5 14 4 13.5 4 13V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="labels.length === 0">
            <td colspan="6" class="empty-cell">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px" class="label-dialog">
      <el-form :model="form" label-width="100px" class="config-form">
        <el-form-item label="维度类型" required>
          <el-select v-model="form.dimension_type" placeholder="选择维度类型" class="form-select">
            <el-option label="country - 国家/站点" value="country" />
            <el-option label="platform - 平台" value="platform" />
            <el-option label="ad_channel - 广告渠道" value="ad_channel" />
            <el-option label="sku - 商品" value="sku" />
            <el-option label="currency - 币种" value="currency" />
          </el-select>
        </el-form-item>
        <el-form-item label="原始值" required>
          <el-input v-model="form.raw_value" placeholder="如: US, AMAZON" />
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="form.display_name" placeholder="如: 美国站, Amazon" />
        </el-form-item>
        <el-form-item label="Emoji图标">
          <el-input v-model="form.emoji" placeholder="如: 🏪" style="width: 80px" maxlength="4" />
        </el-form-item>
        <el-form-item label="优先级标签">
          <el-select v-model="form.priority_tag" placeholder="选择优先级" clearable class="form-select">
            <el-option label="P0" value="P0" />
            <el-option label="P1" value="P1" />
            <el-option label="P2" value="P2" />
          </el-select>
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
import { dimensionLabelAPI } from '@/api'

const labels = ref([])
const filterType = ref('')
const dialogVisible = ref(false)
const dialogTitle = ref('添加标签')
const saving = ref(false)
const editingId = ref(null)

const form = reactive({
  dimension_type: 'country',
  raw_value: '',
  display_name: '',
  emoji: '',
  priority_tag: ''
})

const loadLabels = async () => {
  try {
    const params = {}
    if (filterType.value) params.dimension_type = filterType.value
    const res = await dimensionLabelAPI.list(params)
    labels.value = res.data || []
  } catch (e) {
    ElMessage.error('加载标签失败')
  }
}

const showCreateDialog = () => {
  editingId.value = null
  dialogTitle.value = '添加标签'
  Object.assign(form, {
    dimension_type: 'country',
    raw_value: '',
    display_name: '',
    emoji: '',
    priority_tag: ''
  })
  dialogVisible.value = true
}

const showEditDialog = (label) => {
  editingId.value = label.id
  dialogTitle.value = '编辑标签'
  form.dimension_type = label.dimension_type
  form.raw_value = label.raw_value
  form.display_name = label.display_name
  form.emoji = label.emoji || ''
  form.priority_tag = label.priority_tag || ''
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.dimension_type || !form.raw_value || !form.display_name) {
    ElMessage.warning('请填写完整信息')
    return
  }
  saving.value = true
  try {
    const payload = { ...form }
    if (editingId.value) {
      await dimensionLabelAPI.update(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await dimensionLabelAPI.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadLabels()
  } catch (e) {
    ElMessage.error(editingId.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (label) => {
  try {
    await ElMessageBox.confirm(`确定删除标签 [${label.display_name}] 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await dimensionLabelAPI.delete(label.id)
    ElMessage.success('删除成功')
    loadLabels()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(loadLabels)
</script>

<style scoped>
.label-config {
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
  padding: 10px 16px;
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

.raw-value {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: #6366f1;
}

.display-name {
  font-weight: 500;
}

.emoji {
  margin-right: 4px;
}

.emoji-cell {
  font-size: 16px;
}

.priority-tag {
  font-size: 12px;
  font-weight: 600;
  color: #d97706;
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

.label-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 20px;
  margin-right: 0;
}

.label-dialog :deep(.el-dialog__body) {
  padding: 24px 20px;
}

.label-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #e5e7eb;
  padding: 16px 20px;
}

.config-form .form-select {
  width: 100%;
}
</style>
