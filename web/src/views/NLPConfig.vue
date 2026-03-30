<template>
  <div class="nlp-config-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="page-icon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M4 6L11 4L18 6V16L11 18L4 16V6Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
            <path d="M8 11L10 13L14 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="header-text">
          <h1>意图配置</h1>
          <p>管理意图识别和 SQL 模板</p>
        </div>
      </div>
    </div>

    <!-- Vector Management -->
    <div class="vector-bar">
      <div class="vector-info">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="1.5"/>
          <circle cx="9" cy="9" r="3" fill="currentColor"/>
        </svg>
        <span>向量管理</span>
      </div>
      <div class="vector-actions">
        <el-button @click="rebuildIntentEmbeddings">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 7C2 4.2 4.2 2 7 2C9.8 2 12 4.2 12 7M12 7C12 9.8 9.8 12 7 12C4.2 12 2 9.8 2 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            <path d="M10 5L12 7L10 9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          重新生成意图向量
        </el-button>
        <el-button @click="rebuildMetricEmbeddings">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 7C2 4.2 4.2 2 7 2C9.8 2 12 4.2 12 7M12 7C12 9.8 9.8 12 7 12C4.2 12 2 9.8 2 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            <path d="M10 5L12 7L10 9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          重新生成指标向量
        </el-button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="config-tabs-wrapper">
      <el-tabs v-model="activeTab" class="config-tabs">
        <!-- 意图模板 -->
        <el-tab-pane label="意图模板" name="intents">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">意图模板管理</h2>
              <el-button type="primary" class="btn-primary" @click="showIntentDialog('create')">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                添加模板
              </el-button>
            </div>
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
                  <tr v-for="tpl in intentTemplates" :key="tpl.id">
                    <td class="name-cell">{{ tpl.name }}</td>
                    <td><span class="intent-badge">{{ tpl.intent }}</span></td>
                    <td class="patterns-cell">{{ tpl.patterns }}</td>
                    <td class="priority-cell">{{ tpl.priority }}</td>
                    <td>
                      <el-switch
                        v-model="tpl.status"
                        :active-value="1"
                        :inactive-value="0"
                        @change="updateIntentStatus(tpl)"
                      />
                    </td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="showIntentDialog('edit', tpl)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deleteIntent(tpl.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </el-tab-pane>

        <!-- SQL 模板 -->
        <el-tab-pane label="SQL 模板" name="sql">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">SQL 模板管理</h2>
              <el-button type="primary" class="btn-primary" @click="showSQLDialog('create')">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                添加模板
              </el-button>
            </div>
            <div class="table-card">
              <table class="config-table">
                <thead>
                  <tr>
                    <th>模板名称</th>
                    <th>指标编号</th>
                    <th>适意图图</th>
                    <th>SQL 模板</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="tpl in sqlTemplates" :key="tpl.id">
                    <td class="name-cell">{{ tpl.name }}</td>
                    <td><code class="metric-code">{{ tpl.metric_code }}</code></td>
                    <td><span class="intent-badge">{{ tpl.intent }}</span></td>
                    <td class="sql-cell">{{ tpl.sql_template }}</td>
                    <td>
                      <el-switch
                        v-model="tpl.status"
                        :active-value="1"
                        :inactive-value="0"
                        @change="updateSQLStatus(tpl)"
                      />
                    </td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="showSQLDialog('edit', tpl)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deleteSQL(tpl.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </el-tab-pane>

        <!-- 业务术语 -->
        <el-tab-pane label="业务术语" name="terms">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">业务术语映射</h2>
              <el-button type="primary" class="btn-primary" @click="showTermDialog('create')">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                添加映射
              </el-button>
            </div>
            <div class="table-card">
              <table class="config-table">
                <thead>
                  <tr>
                    <th>术语</th>
                    <th>描述</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="term in businessTerms" :key="term.id">
                    <td class="name-cell">{{ term.term }}</td>
                    <td class="desc-cell">{{ term.description }}</td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="showTermDialog('edit', term)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deleteTerm(term.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </el-tab-pane>

        <!-- 意图反馈审核 -->
        <el-tab-pane label="意图反馈" name="feedback">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">意图反馈审核</h2>
              <el-button @click="loadFeedback" :loading="feedbackLoading" class="btn-refresh">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 7C2 4.2 4.2 2 7 2C9.8 2 12 4.2 12 7M12 7C12 9.8 9.8 12 7 12C4.2 12 2 9.8 2 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                  <path d="M10 5L12 7L10 9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                刷新
              </el-button>
            </div>
            <div class="table-card">
              <table class="config-table" v-if="intentFeedbacks.length > 0">
                <thead>
                  <tr>
                    <th>用户输入</th>
                    <th>预测意图</th>
                    <th>正确意图</th>
                    <th>会话ID</th>
                    <th>时间</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="fb in intentFeedbacks" :key="fb.id">
                    <td class="name-cell">{{ fb.user_input }}</td>
                    <td><span class="intent-badge error">{{ fb.predicted_intent }}</span></td>
                    <td><span class="intent-badge success">{{ fb.correct_intent }}</span></td>
                    <td class="mono-cell">{{ fb.session_id?.substring(0, 8) }}...</td>
                    <td class="time-cell">{{ formatTime(fb.created_at) }}</td>
                    <td>
                      <el-tag v-if="fb.status === 0" type="warning" size="small">待审核</el-tag>
                      <el-tag v-else-if="fb.status === 1" type="success" size="small">已通过</el-tag>
                      <el-tag v-else type="info" size="small">已拒绝</el-tag>
                    </td>
                    <td>
                      <div class="action-group" v-if="fb.status === 0">
                        <el-button link class="action-btn approve" @click="reviewFeedback(fb, 1)">通过</el-button>
                        <el-button link class="action-btn delete" @click="reviewFeedback(fb, 2)">拒绝</el-button>
                      </div>
                      <span v-else class="reviewed-label">已处理</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-else class="empty-state">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                  <circle cx="24" cy="24" r="20" stroke="currentColor" stroke-width="2"/>
                  <path d="M16 24L22 30L32 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <p>暂无待审核的意图反馈</p>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- Intent Dialog -->
    <el-dialog v-model="intentDialogVisible" :title="intentDialogTitle" width="550px" class="config-dialog">
      <el-form :model="intentForm" label-width="90px" class="config-form">
        <el-form-item label="模板名称">
          <el-input v-model="intentForm.name" placeholder="如：查询昨日数据" />
        </el-form-item>
        <el-form-item label="意图类型">
          <el-select v-model="intentForm.intent" placeholder="选择意图" style="width: 100%">
            <el-option label="查数值" value="query_value" />
            <el-option label="查趋势" value="query_trend" />
            <el-option label="对比分析" value="query_comparison" />
            <el-option label="查元数据" value="query_metadata" />
            <el-option label="打招呼" value="greeting" />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配模式">
          <el-input
            v-model="intentForm.patterns"
            type="textarea"
            :rows="2"
            placeholder="关键词用逗号分隔，如：昨天,昨日,昨天数据"
          />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="intentForm.priority" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="默认回复">
          <el-input v-model="intentForm.response" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="intentDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="saveIntent" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>

    <!-- SQL Dialog -->
    <el-dialog v-model="sqlDialogVisible" :title="sqlDialogTitle" width="650px" class="config-dialog">
      <el-form :model="sqlForm" label-width="90px" class="config-form">
        <el-form-item label="模板名称">
          <el-input v-model="sqlForm.name" placeholder="如：访客数昨日查询" />
        </el-form-item>
        <el-form-item label="指标编号">
          <el-select v-model="sqlForm.metric_code" placeholder="选择指标" filterable style="width: 100%">
            <el-option
              v-for="m in metricsList"
              :key="m.metric_code"
              :label="`${m.name} (${m.metric_code})`"
              :value="m.metric_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="适用意图">
          <el-select v-model="sqlForm.intent" placeholder="选择意图" style="width: 100%">
            <el-option label="查数值" value="query_value" />
            <el-option label="查趋势" value="query_trend" />
            <el-option label="对比分析" value="query_comparison" />
          </el-select>
        </el-form-item>
        <el-form-item label="SQL 模板">
          <el-input
            v-model="sqlForm.sql_template"
            type="textarea"
            :rows="4"
            placeholder="SELECT * FROM metric_data WHERE metric_id = '{metric_id}' AND date = CURRENT_DATE - INTERVAL '1 day'"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="sqlForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="sqlDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="saveSQL" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>

    <!-- Term Dialog -->
    <el-dialog v-model="termDialogVisible" :title="termDialogTitle" width="450px" class="config-dialog">
      <el-form :model="termForm" label-width="80px" class="config-form">
        <el-form-item label="术语">
          <el-input v-model="termForm.term" placeholder="如：访客数" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="termForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="termDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="saveTerm" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { metricAPI } from '../api'

const activeTab = ref('intents')
const intentTemplates = ref([])
const sqlTemplates = ref([])
const businessTerms = ref([])
const metricsList = ref([])
const intentFeedbacks = ref([])
const feedbackLoading = ref(false)

// Intent Dialog
const intentDialogVisible = ref(false)
const intentDialogTitle = ref('添加意图模板')
const intentForm = ref({
  name: '',
  intent: 'query_value',
  patterns: '',
  priority: 0,
  response: '',
  status: 1
})
const editingIntentId = ref(null)

// SQL Dialog
const sqlDialogVisible = ref(false)
const sqlDialogTitle = ref('添加 SQL 模板')
const sqlForm = ref({
  name: '',
  metric_code: '',
  intent: 'query_value',
  sql_template: '',
  description: '',
  status: 1
})
const editingSQLId = ref(null)

// Term Dialog
const termDialogVisible = ref(false)
const termDialogTitle = ref('添加术语映射')
const termForm = ref({
  term: '',
  description: ''
})
const editingTermId = ref(null)

async function loadData() {
  try {
    const [intentsRes, sqlRes, termsRes, metricsRes] = await Promise.all([
      fetch('/api/v1/nlp/intents').then(r => r.json()),
      fetch('/api/v1/nlp/sql-templates').then(r => r.json()),
      fetch('/api/v1/metadata/terms').then(r => r.json()),
      metricAPI.list({ page: 1, page_size: 500 })
    ])

    intentTemplates.value = intentsRes.data || []
    sqlTemplates.value = sqlRes.data || []
    businessTerms.value = termsRes.data || []
    metricsList.value = metricsRes.data?.list || []
  } catch (e) {
    console.error('加载数据失败:', e)
  }
}

// Intent
function showIntentDialog(mode, tpl = null) {
  if (mode === 'create') {
    intentDialogTitle.value = '添加意图模板'
    intentForm.value = { name: '', intent: 'query_value', patterns: '', priority: 0, response: '', status: 1 }
    editingIntentId.value = null
  } else {
    intentDialogTitle.value = '编辑意图模板'
    intentForm.value = { ...tpl }
    editingIntentId.value = tpl.id
  }
  intentDialogVisible.value = true
}

async function saveIntent() {
  try {
    if (editingIntentId.value) {
      await fetch(`/api/v1/nlp/intents/${editingIntentId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intentForm.value)
      })
      ElMessage.success('更新成功')
    } else {
      await fetch('/api/v1/nlp/intents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intentForm.value)
      })
      ElMessage.success('创建成功')
    }
    intentDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function updateIntentStatus(tpl) {
  try {
    await fetch(`/api/v1/nlp/intents/${tpl.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: tpl.status })
    })
    ElMessage.success('状态更新成功')
  } catch (e) {
    ElMessage.error('更新失败')
    loadData()
  }
}

async function deleteIntent(id) {
  await ElMessageBox.confirm('确定删除这个模板吗？', '提示', { type: 'warning' })
  try {
    await fetch(`/api/v1/nlp/intents/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// SQL
function showSQLDialog(mode, tpl = null) {
  if (mode === 'create') {
    sqlDialogTitle.value = '添加 SQL 模板'
    sqlForm.value = { name: '', metric_code: '', intent: 'query_value', sql_template: '', description: '', status: 1 }
    editingSQLId.value = null
  } else {
    sqlDialogTitle.value = '编辑 SQL 模板'
    sqlForm.value = { ...tpl }
    editingSQLId.value = tpl.id
  }
  sqlDialogVisible.value = true
}

async function saveSQL() {
  try {
    if (editingSQLId.value) {
      await fetch(`/api/v1/nlp/sql-templates/${editingSQLId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sqlForm.value)
      })
      ElMessage.success('更新成功')
    } else {
      await fetch('/api/v1/nlp/sql-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sqlForm.value)
      })
      ElMessage.success('创建成功')
    }
    sqlDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function updateSQLStatus(tpl) {
  try {
    await fetch(`/api/v1/nlp/sql-templates/${tpl.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: tpl.status })
    })
    ElMessage.success('状态更新成功')
  } catch (e) {
    ElMessage.error('更新失败')
    loadData()
  }
}

async function deleteSQL(id) {
  await ElMessageBox.confirm('确定删除这个模板吗？', '提示', { type: 'warning' })
  try {
    await fetch(`/api/v1/nlp/sql-templates/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// Term
function showTermDialog(mode, term = null) {
  if (mode === 'create') {
    termDialogTitle.value = '添加术语映射'
    termForm.value = { term: '', description: '' }
    editingTermId.value = null
  } else {
    termDialogTitle.value = '编辑术语映射'
    termForm.value = { term: term.term, description: term.description }
    editingTermId.value = term.id
  }
  termDialogVisible.value = true
}

async function saveTerm() {
  try {
    if (editingTermId.value) {
      await fetch(`/api/v1/metadata/terms/${editingTermId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(termForm.value)
      })
      ElMessage.success('更新成功')
    } else {
      await fetch('/api/v1/metadata/terms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(termForm.value)
      })
      ElMessage.success('创建成功')
    }
    termDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function deleteTerm(id) {
  await ElMessageBox.confirm('确定删除这个映射吗？', '提示', { type: 'warning' })
  try {
    await fetch(`/api/v1/metadata/terms/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// Intent Feedback
async function loadFeedback() {
  feedbackLoading.value = true
  try {
    const res = await fetch('/api/v1/feedback/intent')
    const data = await res.json()
    intentFeedbacks.value = data.data || []
  } catch (e) {
    console.error('加载反馈失败:', e)
  } finally {
    feedbackLoading.value = false
  }
}

async function reviewFeedback(feedback, status) {
  try {
    await fetch(`/api/v1/feedback/intent/${feedback.id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    })
    ElMessage.success(status === 1 ? '已通过' : '已拒绝')
    loadFeedback()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
}

// Vector
async function rebuildIntentEmbeddings() {
  try {
    const response = await fetch('/api/v1/nlp/intents/rebuild-embeddings', { method: 'POST' })
    const data = await response.json()
    if (data.code === 0) {
      ElMessage.success(`成功重建 ${data.data.count} 条意图向量`)
    }
  } catch (error) {
    ElMessage.error('重建失败')
  }
}

async function rebuildMetricEmbeddings() {
  try {
    const response = await fetch('/api/v1/nlp/metrics/rebuild-embeddings', { method: 'POST' })
    const data = await response.json()
    if (data.code === 0) {
      ElMessage.success(`成功重建 ${data.data.count} 条指标向量`)
    }
  } catch (error) {
    ElMessage.error('重建失败')
  }
}

onMounted(() => {
  loadData()
})

// 切换到反馈标签时懒加载数据
watch(activeTab, (tab) => {
  if (tab === 'feedback' && intentFeedbacks.value.length === 0) {
    loadFeedback()
  }
})
</script>

<style scoped>
.nlp-config-page {
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

/* Vector Bar */
.vector-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 14px 20px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm);
}

.vector-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.vector-actions {
  display: flex;
  gap: 10px;
}

.vector-actions .el-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

/* Tabs Wrapper */
.config-tabs-wrapper {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
}

/* Tabs */
.config-tabs :deep(.el-tabs__header) {
  margin: 0 0 20px 0;
  padding: 0;
}

.config-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.config-tabs :deep(.el-tabs__item) {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 14px;
}

.config-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary);
}

.config-tabs :deep(.el-tabs__active-bar) {
  height: 2px;
  background: var(--primary);
}

/* Section */
.section {
  margin-bottom: 24px;
}

.section:last-child {
  margin-bottom: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
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

/* Table */
.table-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
}

.config-table th {
  text-align: left;
  padding: 12px 14px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
}

.config-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #f4f4f5;
  font-size: 13px;
  color: var(--text-primary);
}

.config-table tr:last-child td {
  border-bottom: none;
}

.config-table tr:hover td {
  background: var(--bg-primary);
}

.name-cell {
  font-weight: 600;
}

.intent-badge {
  display: inline-block;
  padding: 3px 8px;
  background: var(--primary-glow);
  color: var(--primary);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.patterns-cell {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.priority-cell {
  font-family: 'SF Mono', Monaco, monospace;
  color: var(--text-secondary);
}

.metric-code {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
}

.sql-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.desc-cell {
  color: var(--text-secondary);
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-group {
  display: flex;
  gap: 2px;
}

.action-btn {
  padding: 4px 8px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: 4px;
}

.action-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.action-btn.delete:hover {
  color: #ef4444;
  background: #fef2f2;
}

.action-btn.approve:hover {
  color: #22c55e;
  background: #f0fdf4;
}

.intent-badge.error {
  background: #fef2f2;
  color: #ef4444;
}

.intent-badge.success {
  background: #f0fdf4;
  color: #22c55e;
}

.mono-cell {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 11px;
  color: var(--text-secondary);
}

.time-cell {
  font-size: 12px;
  color: var(--text-secondary);
}

.reviewed-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.empty-state {
  padding: 48px;
  text-align: center;
  color: var(--text-secondary);
}

.empty-state svg {
  margin-bottom: 12px;
  opacity: 0.4;
}

.empty-state p {
  margin: 0;
  font-size: 13px;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

:deep(.el-switch.is-checked .el-switch__core) {
  background-color: var(--primary);
  border-color: var(--primary);
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
