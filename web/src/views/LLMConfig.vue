<template>
  <div class="llm-config-page">
    <div class="page-header">
      <h2>大模型配置</h2>
      <el-button type="primary" @click="handleCreate">新增配置</el-button>
    </div>

    <div class="config-grid">
      <div
        v-for="config in configs"
        :key="config.id"
        class="config-card"
        :class="{ 'is-default': config.is_default === 1 }"
      >
        <div class="card-header">
          <span class="provider-icon">{{ getProviderIcon(config.provider) }}</span>
          <div class="card-title">
            <h4>{{ config.name }}</h4>
            <el-tag size="small" :type="config.status === 1 ? 'success' : 'info'">
              {{ config.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </div>
          <el-tag v-if="config.is_default === 1" type="warning" size="small">
            默认
          </el-tag>
        </div>

        <div class="card-body">
          <div class="info-item">
            <span class="label">Provider:</span>
            <span class="value">{{ config.provider }}</span>
          </div>
          <div class="info-item">
            <span class="label">模型:</span>
            <span class="value">{{ config.model_name }}</span>
          </div>
          <div class="info-item">
            <span class="label">API地址:</span>
            <span class="value url">{{ config.api_url }}</span>
          </div>
        </div>

        <div class="card-footer">
          <el-button link type="primary" @click="handleEdit(config)">编辑</el-button>
          <el-button link type="success" @click="handleTest(config)">测试</el-button>
          <el-button
            link
            type="warning"
            v-if="config.is_default !== 1"
            @click="handleSetDefault(config)"
          >
            设为默认
          </el-button>
          <el-button link type="danger" @click="handleDelete(config)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="配置名称">
          <el-input v-model="form.name" placeholder="如：腾讯云 DeepSeek" />
        </el-form-item>
        <el-form-item label="Provider">
          <el-select v-model="form.provider" placeholder="选择提供商">
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
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
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
    // 示例数据
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

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
}

.config-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 20px;
  transition: all 0.3s ease;
}

.config-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
}

.config-card.is-default {
  border: 2px solid #409EFF;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.provider-icon {
  font-size: 32px;
}

.card-title {
  flex: 1;
}

.card-title h4 {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.card-body {
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  margin-bottom: 8px;
  font-size: 13px;
}

.info-item .label {
  color: #909399;
  width: 60px;
  flex-shrink: 0;
}

.info-item .value {
  color: #606266;
  word-break: break-all;
}

.info-item .value.url {
  font-size: 12px;
  color: #909399;
}

.card-footer {
  display: flex;
  gap: 12px;
  border-top: 1px solid #f0f0f0;
  padding-top: 16px;
}
</style>
