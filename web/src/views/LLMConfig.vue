<template>
  <div class="llm-config-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="page-icon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <circle cx="5" cy="11" r="2.5" fill="currentColor"/>
            <circle cx="11" cy="5" r="2.5" fill="currentColor" opacity="0.7"/>
            <circle cx="11" cy="17" r="2.5" fill="currentColor" opacity="0.7"/>
            <circle cx="17" cy="11" r="2.5" fill="currentColor" opacity="0.5"/>
          </svg>
        </div>
        <div class="header-text">
          <h1>LLM 配置</h1>
          <p>管理大模型连接配置</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" class="btn-primary" @click="handleCreate">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <path d="M7.5 3V12M3 7.5H12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          新增配置
        </el-button>
      </div>
    </div>

    <!-- Config Grid -->
    <div class="config-grid">
      <div
        v-for="config in configs"
        :key="config.id"
        class="config-card"
        :class="{ 'is-default': config.is_default === 1 }"
      >
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
          <div class="info-item">
            <span class="info-label">Temperature</span>
            <span class="info-value">{{ config.temperature || 0.7 }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Embedding</span>
            <span class="info-value">{{ config.embedding_api_key ? '✅ 已配置' : '❌ 未配置' }}</span>
          </div>
        </div>

        <div class="card-footer">
          <el-button link class="action-btn" @click="handleEdit(config)">编辑</el-button>
          <el-button link class="action-btn test" @click="handleTest(config)">测试</el-button>
          <el-button link class="action-btn" v-if="config.is_default !== 1" @click="handleSetDefault(config)">设为默认</el-button>
          <el-button link class="action-btn delete" @click="handleDelete(config)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px" class="config-dialog">
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
          <el-input v-model="form.model_name" placeholder="如：deepseek-3.2" />
        </el-form-item>
        <el-form-item label="Embedding Key">
          <el-input v-model="form.embedding_api_key" type="password" placeholder="阿里 DashScope API Key（用于向量检索）" />
        </el-form-item>
        <el-form-item label="Temperature">
          <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" precision="1" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
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
import { ref, onMounted } from 'vue'
import { llmAPI } from '../api'
import { ElMessage } from 'element-plus'

const configs = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增配置')
const form = ref({
  name: '',
  provider: 'tencent',
  api_url: '',
  api_key: '',
  model_name: '',
  embedding_api_key: '',
  temperature: 0.7,
  status: 1
})

onMounted(() => {
  loadConfigs()
})

async function loadConfigs() {
  try {
    const res = await llmAPI.list()
    if (res.data) {
      configs.value = res.data
    }
  } catch (e) {
    configs.value = [
      {
        id: 1,
        name: '腾讯云 DeepSeek',
        provider: 'tencent',
        api_url: 'https://api.tencent.com',
        model_name: 'deepseek-3.2',
        is_default: 1,
        status: 1
      }
    ]
  }
}

function getProviderIcon(provider) {
  const icons = { tencent: '🔶', openai: '🟢', anthropic: '🟠' }
  return icons[provider] || '🔵'
}

function handleCreate() {
  dialogTitle.value = '新增配置'
  form.value = {
    name: '',
    provider: 'tencent',
    api_url: '',
    api_key: '',
    model_name: '',
    embedding_api_key: '',
    temperature: 0.7,
    status: 1
  }
  dialogVisible.value = true
}

function handleEdit(config) {
  dialogTitle.value = '编辑配置'
  form.value = { ...config }
  dialogVisible.value = true
}

async function handleSave() {
  try {
    if (form.value.id) {
      await llmAPI.update(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await llmAPI.create(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadConfigs()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function handleTest(config) {
  try {
    await llmAPI.test({
      api_url: config.api_url,
      api_key: config.api_key,
      model_name: config.model_name
    })
    ElMessage.success('连接测试成功')
  } catch (e) {
    ElMessage.error('连接测试失败')
  }
}

async function handleSetDefault(config) {
  try {
    await llmAPI.setDefault(config.id)
    ElMessage.success('设置成功')
    loadConfigs()
  } catch (e) {
    ElMessage.error('设置失败')
  }
}

async function handleDelete(config) {
  try {
    await llmAPI.delete(config.id)
    ElMessage.success('删除成功')
    loadConfigs()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.llm-config-page {
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
  background: var(--primary-glow);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
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

/* Config Grid */
.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.config-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.config-card:hover {
  box-shadow: var(--shadow-md);
}

.config-card.is-default {
  border-color: var(--primary);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.provider-icon {
  font-size: 28px;
}

.card-title h4 {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.status-tag.active {
  background: #dcfce7;
  color: #15803d;
}

.status-tag.inactive {
  background: #f4f4f5;
  color: var(--text-secondary);
}

.default-badge {
  display: inline-block;
  padding: 3px 8px;
  background: var(--primary-glow);
  color: var(--primary);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.card-body {
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.info-item.full {
  margin-bottom: 0;
}

.info-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.info-value.mono {
  font-family: 'SF Mono', Monaco, monospace;
}

.info-value.url {
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-all;
}

.card-footer {
  display: flex;
  gap: 4px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.action-btn {
  padding: 6px 10px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: 4px;
}

.action-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.action-btn.test:hover {
  color: var(--primary);
}

.action-btn.delete:hover {
  color: #ef4444;
  background: #fef2f2;
}

/* Dialog */
.config-dialog :deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
}

.config-dialog :deep(.el-dialog__title) {
  font-weight: 700;
  color: var(--text-primary);
}

.config-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--text-primary);
}

.config-form :deep(.el-input__wrapper),
.config-form :deep(.el-textarea__inner) {
  border-radius: var(--radius-sm);
  box-shadow: none !important;
  border: 1px solid var(--border);
}

.config-form :deep(.el-input__wrapper:hover),
.config-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--primary);
}
</style>
