<template>
  <div class="template-config">
    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-select v-model="filterType" placeholder="模板类型" clearable size="default" class="filter-select">
          <el-option label="summary" value="summary" />
          <el-option label="reason" value="reason" />
          <el-option label="action" value="action" />
          <el-option label="greeting" value="greeting" />
        </el-select>
        <el-button @click="loadTemplates" class="btn-refresh">
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
        添加模板
      </el-button>
    </div>

    <!-- Table -->
    <div class="table-card">
      <table class="config-table">
        <thead>
          <tr>
            <th>模板Key</th>
            <th>类型</th>
            <th>内容</th>
            <th>优先级</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tmpl in templates" :key="tmpl.id">
            <td class="key-cell">{{ tmpl.template_key }}</td>
            <td><span class="type-badge">{{ tmpl.template_type }}</span></td>
            <td class="content-cell">{{ tmpl.content_template }}</td>
            <td class="priority-cell">{{ tmpl.priority }}</td>
            <td>
              <el-switch :model-value="tmpl.enabled" @change="handleEnabledChange(tmpl, $event)" />
            </td>
            <td>
              <div class="action-btns">
                <button class="btn-icon" @click="showEditDialog(tmpl)" title="编辑">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M11.5 2.5L13.5 4.5M2 14L3.5 10L12 1.5L14.5 4L5.5 13L2 14Z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
                  </svg>
                </button>
                <button class="btn-icon btn-danger" @click="handleDelete(tmpl)" title="删除">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M3 4H13M5.5 4V3C5.5 2.5 6 2 6.5 2H9.5C10 2 10.5 2.5 10.5 3V4M12 4V13C12 13.5 11.5 14 11 14H5C4.5 14 4 13.5 4 13V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="templates.length === 0">
            <td colspan="6" class="empty-cell">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px" class="template-dialog">
      <el-form :model="form" label-width="100px" class="config-form">
        <el-form-item label="模板Key" required>
          <el-input v-model="form.template_key" placeholder="如: volatility_summary" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="模板类型" required>
          <el-select v-model="form.template_type" placeholder="选择类型" class="form-select">
            <el-option label="summary - 归因话术" value="summary" />
            <el-option label="reason - 原因分析" value="reason" />
            <el-option label="action - 建议话术" value="action" />
            <el-option label="greeting - 欢迎语" value="greeting" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板内容" required>
          <el-input v-model="form.content_template" type="textarea" :rows="4" placeholder='{{dimension}}{{emoji}}{{change}}，{{impact}}' />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="0" :max="100" :step="1" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <div class="placeholder-hint">
          <span>可用占位符: </span>
          <code>{{dimension}}</code>
          <code>{{emoji}}</code>
          <code>{{metric}}</code>
          <code>{{change}}</code>
          <code>{{impact}}</code>
          <code>{{reason}}</code>
          <code>{{action}}</code>
        </div>
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
import { outputTemplateAPI } from '@/api'

const templates = ref([])
const filterType = ref('')
const dialogVisible = ref(false)
const dialogTitle = ref('添加模板')
const saving = ref(false)
const editingId = ref(null)

const form = reactive({
  template_key: '',
  template_type: 'summary',
  content_template: '',
  priority: 0,
  enabled: true
})

const loadTemplates = async () => {
  try {
    const params = {}
    if (filterType.value) params.template_type = filterType.value
    const res = await outputTemplateAPI.list(params)
    templates.value = res.data || []
  } catch (e) {
    ElMessage.error('加载模板失败')
  }
}

const showCreateDialog = () => {
  editingId.value = null
  dialogTitle.value = '添加模板'
  Object.assign(form, {
    template_key: '',
    template_type: 'summary',
    content_template: '',
    priority: 0,
    enabled: true
  })
  dialogVisible.value = true
}

const showEditDialog = (tmpl) => {
  editingId.value = tmpl.id
  dialogTitle.value = '编辑模板'
  form.template_key = tmpl.template_key
  form.template_type = tmpl.template_type
  form.content_template = tmpl.content_template
  form.priority = tmpl.priority || 0
  form.enabled = tmpl.enabled !== false
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.template_key || !form.content_template) {
    ElMessage.warning('请填写完整信息')
    return
  }
  saving.value = true
  try {
    const payload = {
      template_key: form.template_key,
      template_type: form.template_type,
      content_template: form.content_template,
      priority: form.priority,
      enabled: form.enabled
    }
    if (editingId.value) {
      await outputTemplateAPI.update(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await outputTemplateAPI.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadTemplates()
  } catch (e) {
    ElMessage.error(editingId.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (tmpl) => {
  try {
    await ElMessageBox.confirm(`确定删除模板 [${tmpl.template_key}] 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await outputTemplateAPI.delete(tmpl.id)
    ElMessage.success('删除成功')
    loadTemplates()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleEnabledChange = async (tmpl, val) => {
  try {
    await outputTemplateAPI.update(tmpl.id, { enabled: val })
    ElMessage.success(val ? '已启用' : '已禁用')
    loadTemplates()
  } catch (e) {
    ElMessage.error('更新状态失败')
  }
}

onMounted(loadTemplates)
</script>

<style scoped>
.template-config {
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

.key-cell {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: #6366f1;
}

.type-badge {
  display: inline-block;
  padding: 3px 10px;
  background: #ede9fe;
  color: #6366f1;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.content-cell {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #9ca3af;
  font-size: 13px;
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

.template-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 20px;
  margin-right: 0;
}

.template-dialog :deep(.el-dialog__body) {
  padding: 24px 20px;
}

.template-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #e5e7eb;
  padding: 16px 20px;
}

.config-form .form-select {
  width: 100%;
}

.placeholder-hint {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding: 10px 12px;
  background: #f5f3ff;
  border-radius: 8px;
  font-size: 12px;
  color: #6b7280;
}

.placeholder-hint code {
  display: inline-block;
  padding: 2px 6px;
  background: white;
  border: 1px solid #ddd6fe;
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 11px;
  color: #6366f1;
}
</style>
