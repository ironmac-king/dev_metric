<template>
  <div class="prompt-config-page">
    <div class="page-header">
      <h1 class="page-title">Prompt 配置</h1>
      <p class="page-desc">配置智能问数的 Prompt 模板，支持版本管理和 AI 辅助写作</p>
    </div>

    <el-row :gutter="20">
      <!-- 左侧：Prompt 列表 -->
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <span>Prompt 列表</span>
          </template>
          <el-scrollbar height="calc(100vh - 280px)">
            <el-menu :default-active="selectedConfigId" @select="handleSelectConfig">
              <el-menu-item v-for="cfg in configs" :key="cfg.id" :index="String(cfg.id)">
                <span>{{ cfg.name }}</span>
                <el-tag size="small" type="info" style="margin-left:8px">v{{ cfg.version }}</el-tag>
              </el-menu-item>
            </el-menu>
          </el-scrollbar>
        </el-card>
      </el-col>

      <!-- 右侧：Prompt 编辑 -->
      <el-col :span="18">
        <el-card shadow="hover">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>{{ currentConfig?.name || '请选择 Prompt' }}</span>
              <div>
                <el-button type="primary" @click="handleAIWrite" :loading="aiWriting" v-if="currentConfig">
                  <el-icon style="margin-right:4px"><MagicStick /></el-icon>
                  AI 代写
                </el-button>
                <el-button type="info" plain @click="openHistoryDialog" v-if="currentConfig">
                  <el-icon style="margin-right:4px"><Clock /></el-icon>
                  版本历史
                </el-button>
                <el-button type="success" @click="handleSave" v-if="currentConfig">
                  保存
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="currentConfig">
            <el-form :model="editForm" label-width="100px">
              <el-form-item label="名称">
                <el-input v-model="editForm.name" disabled />
              </el-form-item>
              <el-form-item label="说明">
                <el-input v-model="editForm.description" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="变量定义">
                <el-input v-model="editForm.variables" placeholder='JSON数组，如 ["intent", "metric_name"]' />
              </el-form-item>
              <el-form-item label="状态">
                <el-switch v-model="editForm.status" :active-value="1" :inactive-value="0" />
              </el-form-item>
              <el-form-item label="Prompt 内容">
                <el-input v-model="editForm.prompt_text" type="textarea" :rows="15" :autosize="{ minRows: 15, maxRows: 50 }" font-family="monospace" />
              </el-form-item>
            </el-form>
          </div>

          <el-empty v-else description="请从左侧选择一个 Prompt" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 版本历史弹窗 -->
    <el-dialog v-model="historyDialogVisible" title="版本历史" width="800px">
      <el-table :data="versions" stripe>
        <el-table-column prop="version" label="版本号" width="100" />
        <el-table-column prop="prompt_text" label="Prompt 内容" min-width="400">
          <template #default="{ row }">
            <el-input type="textarea" :rows="3" v-model="row.prompt_text" disabled />
          </template>
        </el-table-column>
        <el-table-column prop="change_reason" label="变更原因" width="150" />
        <el-table-column prop="created_by" label="操作人" width="100" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleRollback(row)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- AI 代写结果弹窗 -->
    <el-dialog v-model="aiDialogVisible" title="AI 代写结果" width="700px">
      <el-input type="textarea" :rows="15" v-model="aiSuggestedPrompt" font-family="monospace" />
      <template #footer>
        <el-button @click="aiDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleApplyAIPrompt">应用到编辑器</el-button>
      </template>
    </el-dialog>

    <!-- AI 代写模式选择弹窗 -->
    <el-dialog v-model="aiModeDialogVisible" title="AI 代写" width="500px">
      <el-form label-width="120px">
        <el-form-item label="生成模式">
          <el-radio-group v-model="aiWriteMode">
            <el-radio label="regenerate">重新生成</el-radio>
            <el-radio label="improve">基于现有优化</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="当前模板" v-if="aiWriteMode === 'improve'">
          <el-select v-model="aiTargetConfig" placeholder="选择要优化的模板" style="width:100%">
            <el-option v-for="cfg in configs" :key="cfg.id" :label="cfg.name" :value="cfg.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiModeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="executeAIWrite">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { promptConfigAPI } from '@/api'
import { MagicStick, Clock } from '@element-plus/icons-vue'

const configs = ref([])
const selectedConfigId = ref('')
const currentConfig = ref(null)
const historyDialogVisible = ref(false)
const aiDialogVisible = ref(false)
const aiModeDialogVisible = ref(false)
const aiWriting = ref(false)
const aiSuggestedPrompt = ref('')
const aiWriteMode = ref('improve')
const aiTargetConfig = ref('')
const versions = ref([])
const editForm = ref({
  name: '',
  description: '',
  prompt_text: '',
  variables: '[]',
  status: 1
})

async function loadConfigs() {
  try {
    const res = await promptConfigAPI.list()
    configs.value = res.data || []
    if (configs.value.length > 0 && !selectedConfigId.value) {
      handleSelectConfig(String(configs.value[0].id))
    }
  } catch (e) {
    ElMessage.error('加载 Prompt 配置失败')
  }
}

function handleSelectConfig(id) {
  selectedConfigId.value = id
  const cfg = configs.value.find(c => String(c.id) === id)
  if (cfg) {
    currentConfig.value = cfg
    editForm.value = {
      name: cfg.name,
      description: cfg.description || '',
      prompt_text: cfg.prompt_text || '',
      variables: Array.isArray(cfg.variables) ? JSON.stringify(cfg.variables) : (cfg.variables || '[]'),
      status: cfg.status
    }
  }
}

async function handleSave() {
  try {
    const id = selectedConfigId.value
    await promptConfigAPI.update(id, {
      description: editForm.value.description,
      prompt_text: editForm.value.prompt_text,
      variables: editForm.value.variables,
      status: editForm.value.status
    })
    ElMessage.success('保存成功')
    await loadConfigs()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function openHistoryDialog() {
  try {
    const res = await promptConfigAPI.getVersions(selectedConfigId.value)
    versions.value = res.data || []
    historyDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载版本历史失败')
  }
}

async function handleRollback(version) {
  try {
    await ElMessageBox.confirm(
      `确定要回滚到版本 ${version.version} 吗？`,
      '确认回滚',
      { type: 'warning' }
    )
    await promptConfigAPI.rollback(selectedConfigId.value, { version: version.version })
    ElMessage.success('回滚成功')
    historyDialogVisible.value = false
    await loadConfigs()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('回滚失败')
    }
  }
}

async function handleAIWrite() {
  // 每次打开都重置选项
  aiWriteMode.value = 'improve'
  aiTargetConfig.value = currentConfig.value?.id || ''
  aiModeDialogVisible.value = true
}

async function executeAIWrite() {
  aiModeDialogVisible.value = false
  aiWriting.value = true
  aiSuggestedPrompt.value = ''

  try {
    let promptContent = ''
    if (aiWriteMode.value === 'improve') {
      const targetId = aiTargetConfig.value || currentConfig.value?.id
      const targetCfg = configs.value.find(c => c.id === targetId)
      if (targetCfg) {
        promptContent = targetCfg.prompt_text || ''
      }
    }

    // 调用后端 API 生成 Prompt
    const res = await promptConfigAPI.generate({
      current_prompt: promptContent,
      task_name: editForm.value.name,
      description: editForm.value.description || editForm.value.name,
      mode: aiWriteMode.value
    })

    if (res.data?.prompt) {
      aiSuggestedPrompt.value = res.data.prompt
      aiDialogVisible.value = true
    } else {
      ElMessage.error('AI 代写失败：未获取到有效内容')
    }
  } catch (e) {
    console.error('AI 代写失败:', e)
    ElMessage.error('AI 代写失败：' + (e.message || '未知错误'))
  } finally {
    aiWriting.value = false
  }
}

function handleApplyAIPrompt() {
  editForm.value.prompt_text = aiSuggestedPrompt.value
  aiDialogVisible.value = false
  ElMessage.success('已应用到编辑器，请检查后保存')
}

function formatTime(time) {
  if (!time) return ''
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.prompt-config-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.page-desc {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.el-menu-item {
  display: flex;
  align-items: center;
}
</style>
