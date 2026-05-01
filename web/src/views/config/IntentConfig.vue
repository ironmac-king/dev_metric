<template>
  <div class="intent-config">
    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-input v-model="searchKeyword" placeholder="搜索模板名称" clearable size="default" class="search-input" @clear="loadIntents" @keyup.enter="loadIntents">
          <template #prefix>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="margin-top:2px">
              <circle cx="6" cy="6" r="4.5" stroke="#9ca3af" stroke-width="1.2"/>
              <path d="M9.5 9.5L13 13" stroke="#9ca3af" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
          </template>
        </el-input>
        <el-button @click="loadIntents" class="btn-refresh">
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
            <th>模板名称</th>
            <th>意图类型</th>
            <th>匹配模式</th>
            <th>优先级</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tpl in intents" :key="tpl.id">
            <td class="name-cell">{{ tpl.name }}</td>
            <td><span class="intent-badge">{{ tpl.intent }}</span></td>
            <td class="patterns-cell">{{ tpl.patterns || '—' }}</td>
            <td class="priority-cell">{{ tpl.priority }}</td>
            <td>
              <el-switch :model-value="tpl.enabled" @change="handleEnabledChange(tpl, $event)" />
            </td>
            <td>
              <div class="action-btns">
                <button class="btn-icon" @click="showEditDialog(tpl)" title="编辑">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M11.5 2.5L13.5 4.5M2 14L3.5 10L12 1.5L14.5 4L5.5 13L2 14Z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
                  </svg>
                </button>
                <button class="btn-icon btn-danger" @click="handleDelete(tpl)" title="删除">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M3 4H13M5.5 4V3C5.5 2.5 6 2 6.5 2H9.5C10 2 10.5 2.5 10.5 3V4M12 4V13C12 13.5 11.5 14 11 14H5C4.5 14 4 13.5 4 13V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="intents.length === 0">
            <td colspan="6" class="empty-cell">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px" class="intent-dialog">
      <el-form :model="form" label-width="100px" class="config-form">
        <el-form-item label="模板名称" required>
          <el-input v-model="form.name" placeholder="如: 销售额查询" />
        </el-form-item>
        <el-form-item label="意图类型" required>
          <el-select v-model="form.intent" placeholder="选择意图" class="form-select">
            <el-option label="query_value - 指标查询" value="query_value" />
            <el-option label="trend - 趋势分析" value="trend" />
            <el-option label="comparison - 对比分析" value="comparison" />
            <el-option label="ranking - 排名分析" value="ranking" />
            <el-option label="ratio - 占比分析" value="ratio" />
            <el-option label="forecast - 预测分析" value="forecast" />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配模式">
          <el-input v-model="form.patterns" type="textarea" :rows="2" placeholder="多个模式用逗号分隔，如: 销售额是多少,查询销售额" />
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
import api from '@/api'

const intents = ref([])
const searchKeyword = ref('')
const dialogVisible = ref(false)
const dialogTitle = ref('添加意图模板')
const saving = ref(false)
const editingId = ref(null)

const form = reactive({
  name: '',
  intent: 'query_value',
  patterns: '',
  priority: 0,
  enabled: true
})

const loadIntents = async () => {
  try {
    const res = await api.get('/nlp/intents')
    let data = res.data || []
    if (searchKeyword.value) {
      const kw = searchKeyword.value.toLowerCase()
      data = data.filter(i => i.name.toLowerCase().includes(kw) || (i.patterns && i.patterns.toLowerCase().includes(kw)))
    }
    intents.value = data
  } catch (e) {
    ElMessage.error('加载意图模板失败')
  }
}

const showCreateDialog = () => {
  editingId.value = null
  dialogTitle.value = '添加意图模板'
  Object.assign(form, { name: '', intent: 'query_value', patterns: '', priority: 0, enabled: true })
  dialogVisible.value = true
}

const showEditDialog = (tpl) => {
  editingId.value = tpl.id
  dialogTitle.value = '编辑意图模板'
  form.name = tpl.name
  form.intent = tpl.intent
  form.patterns = tpl.patterns || ''
  form.priority = tpl.priority || 0
  form.enabled = tpl.enabled !== false
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.name || !form.intent) {
    ElMessage.warning('请填写完整信息')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/nlp/intents/${editingId.value}`, form)
      ElMessage.success('更新成功')
    } else {
      await api.post('/nlp/intents', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadIntents()
  } catch (e) {
    ElMessage.error(editingId.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (tpl) => {
  try {
    await ElMessageBox.confirm(`确定删除意图模板 [${tpl.name}] 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.delete(`/nlp/intents/${tpl.id}`)
    ElMessage.success('删除成功')
    loadIntents()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleEnabledChange = async (tpl, val) => {
  try {
    await api.put(`/nlp/intents/${tpl.id}`, { enabled: val })
    ElMessage.success(val ? '已启用' : '已禁用')
    loadIntents()
  } catch (e) {
    ElMessage.error('更新状态失败')
  }
}

onMounted(loadIntents)
</script>

<style scoped>
.intent-config { padding: 0 4px; }

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

.search-input {
  width: 240px;
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

.btn-refresh:hover { border-color: #6366f1; color: #6366f1; }

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

.intent-badge {
  display: inline-block;
  padding: 3px 10px;
  background: #ede9fe;
  color: #6366f1;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.patterns-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #9ca3af;
  font-size: 13px;
}

.priority-cell { font-weight: 600; color: #6366f1; }

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

.intent-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 20px;
  margin-right: 0;
}

.intent-dialog :deep(.el-dialog__body) { padding: 24px 20px; }
.intent-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #e5e7eb;
  padding: 16px 20px;
}

.config-form .form-select { width: 100%; }
</style>
