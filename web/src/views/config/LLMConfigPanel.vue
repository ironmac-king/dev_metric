<template>
  <div class="llm-config-panel">
    <div class="panel-toolbar">
      <el-button type="primary" class="btn-primary" @click="showCreateDialog">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        新增配置
      </el-button>
    </div>

    <!-- Config Grid -->
    <div class="config-grid">
      <div v-for="config in configs" :key="config.id" class="config-card" :class="{ 'is-default': config.is_default === 1 }">
        <div class="card-header">
          <div class="provider-info">
            <span class="provider-icon">{{ getProviderIcon(config.provider) }}</span>
            <div class="card-title">
              <h4>{{ config.name }}</h4>
              <span class="status-tag" :class="config.status === 1 ? 'active' : 'inactive'">
                {{ config.status === 1 ? '启用' : '禁用' }}
              </span>
            </div>
          </div>
          <span v-if="config.is_default === 1" class="default-badge">默认</span>
        </div>
        <div class="card-body">
          <div class="info-item">
            <span class="info-label">Provider</span>
            <span class="info-value">{{ config.provider }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">模型</span>
            <span class="info-value mono">{{ config.model_name }}</span>
          </div>
          <div class="info-item full">
            <span class="info-label">API地址</span>
            <span class="info-value url">{{ config.api_url }}</span>
          </div>
        </div>
        <div class="card-footer">
          <el-button link class="action-btn" @click="showEditDialog(config)">编辑</el-button>
          <el-button link class="action-btn test" @click="handleTest(config)">测试</el-button>
          <el-button link class="action-btn" v-if="config.is_default !== 1" @click="handleSetDefault(config)">设为默认</el-button>
          <el-button link class="action-btn delete" @click="handleDelete(config)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px" class="llm-dialog">
      <el-form :model="form" label-width="90px" class="config-form">
        <el-form-item label="配置名称">
          <el-input v-model="form.name" placeholder="如：腾讯云 DeepSeek" />
        </el-form-item>
        <el-form-item label="Provider">
          <el-select v-model="form.provider" placeholder="选择提供商" style="width: 100%">
            <el-option label="腾讯云" value="tencent" />
            <el-option label="OpenAI" value="openai" />
            <el-option label="Anthropic" value="anthropic" />
          </el-select>
        </el-form-item>
        <el-form-item label="API地址">
          <el-input v-model="form.api_url" placeholder="https://api.example.com" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" placeholder="请输入 API Key" />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="form.model_name" placeholder="如: deepseek-chat" />
        </el-form-item>
        <el-form-item label="Temperature">
          <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
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
import { llmAPI } from '@/api'

const configs = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增配置')
const saving = ref(false)
const editingId = ref(null)

const form = reactive({
  name: '',
  provider: 'tencent',
  api_url: '',
  api_key: '',
  model_name: '',
  temperature: 0.7,
  status: 1
})

const getProviderIcon = (provider) => {
  const map = { tencent: '🔵', openai: '🟢', anthropic: '🟠' }
  return map[provider] || '⚪'
}

const loadConfigs = async () => {
  try {
    const res = await llmAPI.list()
    configs.value = res.data || []
  } catch (e) {
    ElMessage.error('加载LLM配置失败')
  }
}

const showCreateDialog = () => {
  editingId.value = null
  dialogTitle.value = '新增配置'
  Object.assign(form, { name: '', provider: 'tencent', api_url: '', api_key: '', model_name: '', temperature: 0.7, status: 1 })
  dialogVisible.value = true
}

const showEditDialog = (cfg) => {
  editingId.value = cfg.id
  dialogTitle.value = '编辑配置'
  form.name = cfg.name
  form.provider = cfg.provider
  form.api_url = cfg.api_url
  form.api_key = cfg.api_key || ''
  form.model_name = cfg.model_name
  form.temperature = cfg.temperature || 0.7
  form.status = cfg.status
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.name || !form.api_url || !form.model_name) {
    ElMessage.warning('请填写完整信息')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await llmAPI.update(editingId.value, form)
      ElMessage.success('更新成功')
    } else {
      await llmAPI.create(form)
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
    await ElMessageBox.confirm(`确定删除配置 [${cfg.name}] 吗？`, '删除确认', { type: 'warning' })
    await llmAPI.delete(cfg.id)
    ElMessage.success('删除成功')
    loadConfigs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleSetDefault = async (cfg) => {
  try {
    await llmAPI.setDefault(cfg.id)
    ElMessage.success('已设为默认')
    loadConfigs()
  } catch (e) {
    ElMessage.error('设置失败')
  }
}

const handleTest = async (cfg) => {
  try {
    await llmAPI.test({ api_url: cfg.api_url, api_key: cfg.api_key, model_name: cfg.model_name })
    ElMessage.success('连接测试成功')
  } catch (e) {
    ElMessage.error('连接测试失败')
  }
}

onMounted(loadConfigs)
</script>

<style scoped>
.llm-config-panel { padding: 0 4px; }

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

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.config-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.2s;
}

.config-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.08);
}

.config-card.is-default {
  border-color: #6366f1;
  background: #fafaff;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.provider-icon {
  font-size: 24px;
}

.card-title h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1e1b4b;
}

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  margin-top: 2px;
}

.status-tag.active {
  background: #d1fae5;
  color: #059669;
}

.status-tag.inactive {
  background: #fee2e2;
  color: #dc2626;
}

.default-badge {
  display: inline-block;
  padding: 2px 8px;
  background: #ede9fe;
  color: #6366f1;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.card-body {
  margin-bottom: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.info-item.full {
  flex-direction: column;
  gap: 2px;
}

.info-label {
  color: #9ca3af;
  font-size: 12px;
}

.info-value {
  color: #374151;
  font-weight: 500;
}

.info-value.mono {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}

.info-value.url {
  font-size: 11px;
  color: #6b7280;
  font-family: 'Fira Code', monospace;
  word-break: break-all;
}

.card-footer {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.action-btn {
  font-size: 12px;
  color: #6b7280;
  padding: 2px 6px;
}

.action-btn:hover {
  color: #6366f1;
}

.action-btn.test:hover {
  color: #10b981;
}

.action-btn.delete:hover {
  color: #ef4444;
}

.llm-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 20px;
  margin-right: 0;
}

.llm-dialog :deep(.el-dialog__body) { padding: 24px 20px; }
.llm-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #e5e7eb;
  padding: 16px 20px;
}
</style>
