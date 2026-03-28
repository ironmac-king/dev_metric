<template>
  <div class="nlp-config">
    <header class="header">
      <div class="header-left">
        <h1 class="page-title">NLP 配置</h1>
        <p class="page-desc">管理意图识别和 SQL 模板</p>
      </div>
    </header>

    <el-card class="mb-3">
      <template #header>
        <span>向量管理</span>
      </template>
      <el-space>
        <el-button type="primary" @click="rebuildIntentEmbeddings">
          重新生成意图向量
        </el-button>
        <el-button type="primary" @click="rebuildMetricEmbeddings">
          重新生成指标向量
        </el-button>
      </el-space>
    </el-card>

    <el-tabs v-model="activeTab" class="config-tabs">
      <!-- 意图模板 -->
      <el-tab-pane label="意图模板" name="intents">
        <div class="section">
          <div class="section-header">
            <h2 class="section-title">意图模板管理</h2>
            <el-button type="primary" @click="showIntentDialog('create')">
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
                  <td>{{ tpl.name }}</td>
                  <td><span class="intent-badge">{{ tpl.intent }}</span></td>
                  <td class="patterns-cell">{{ tpl.patterns }}</td>
                  <td>{{ tpl.priority }}</td>
                  <td>
                    <el-switch
                      v-model="tpl.status"
                      :active-value="1"
                      :inactive-value="0"
                      @change="updateIntentStatus(tpl)"
                    />
                  </td>
                  <td>
                    <el-button link type="primary" @click="showIntentDialog('edit', tpl)">编辑</el-button>
                    <el-button link type="danger" @click="deleteIntent(tpl.id)">删除</el-button>
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
            <el-button type="primary" @click="showSQLDialog('create')">
              添加模板
            </el-button>
          </div>
          <div class="table-card">
            <table class="config-table">
              <thead>
                <tr>
                  <th>模板名称</th>
                  <th>指标编号</th>
                  <th>适用意图</th>
                  <th>SQL 模板</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tpl in sqlTemplates" :key="tpl.id">
                  <td>{{ tpl.name }}</td>
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
                    <el-button link type="primary" @click="showSQLDialog('edit', tpl)">编辑</el-button>
                    <el-button link type="danger" @click="deleteSQL(tpl.id)">删除</el-button>
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
            <el-button type="primary" @click="showTermDialog('create')">
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
                  <td>{{ term.term }}</td>
                  <td>{{ term.description }}</td>
                  <td>
                    <el-button link type="primary" @click="showTermDialog('edit', term)">编辑</el-button>
                    <el-button link type="danger" @click="deleteTerm(term.id)">删除</el-button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </el-tab-pane>

      <!-- 优化建议 -->
      <el-tab-pane label="优化建议" name="suggestions">
        <div class="section">
          <div class="section-header">
            <h2 class="section-title">基于负反馈的优化建议</h2>
            <el-button type="success" @click="triggerAnalysis" :loading="analyzing">
              手动触发分析
            </el-button>
          </div>
          <div class="info-box">
            <p>系统每天凌晨2点自动分析负反馈，生成优化建议。管理员审核后可以"应用"或"忽略"。</p>
          </div>
          <div class="table-card" v-if="optimizationSuggestions.length > 0">
            <table class="config-table">
              <thead>
                <tr>
                  <th>建议类型</th>
                  <th>目标表</th>
                  <th>建议内容</th>
                  <th>失败次数</th>
                  <th>置信度</th>
                  <th>原因</th>
                  <th>时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sug in optimizationSuggestions" :key="sug.id">
                  <td><span class="type-badge" :class="sug.suggestion_type">{{ getTypeLabel(sug.suggestion_type) }}</span></td>
                  <td><code class="metric-code">{{ sug.target_table }}</code></td>
                  <td class="value-cell">{{ sug.suggested_value }}</td>
                  <td><span class="fail-count">{{ sug.fail_count }}</span></td>
                  <td><span class="confidence">{{ (sug.confidence * 100).toFixed(0) }}%</span></td>
                  <td class="reason-cell">{{ sug.reason || '-' }}</td>
                  <td>{{ formatTime(sug.created_at) }}</td>
                  <td>
                    <el-button link type="success" @click="applySuggestion(sug.id)">应用</el-button>
                    <el-button link type="info" @click="ignoreSuggestion(sug.id)">忽略</el-button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <el-empty v-else description="暂无待审核的优化建议" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 意图模板弹窗 -->
    <el-dialog
      v-model="intentDialogVisible"
      :title="intentDialogTitle"
      width="600px"
    >
      <el-form :model="intentForm" label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="intentForm.name" placeholder="如：查询昨日数据" />
        </el-form-item>
        <el-form-item label="意图类型">
          <el-select v-model="intentForm.intent" placeholder="选择意图">
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
        <el-button @click="intentDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveIntent">保存</el-button>
      </template>
    </el-dialog>

    <!-- SQL 模板弹窗 -->
    <el-dialog
      v-model="sqlDialogVisible"
      :title="sqlDialogTitle"
      width="700px"
    >
      <el-form :model="sqlForm" label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="sqlForm.name" placeholder="如：访客数昨日查询" />
        </el-form-item>
        <el-form-item label="指标编号">
          <el-select v-model="sqlForm.metric_code" placeholder="选择指标" filterable>
            <el-option
              v-for="m in metricsList"
              :key="m.metric_code"
              :label="`${m.name} (${m.metric_code})`"
              :value="m.metric_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="适用意图">
          <el-select v-model="sqlForm.intent" placeholder="选择意图">
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
        <el-button @click="sqlDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSQL">保存</el-button>
      </template>
    </el-dialog>

    <!-- 业务术语弹窗 -->
    <el-dialog
      v-model="termDialogVisible"
      :title="termDialogTitle"
      width="500px"
    >
      <el-form :model="termForm" label-width="100px">
        <el-form-item label="术语">
          <el-input v-model="termForm.term" placeholder="如：访客数" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="termForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="termDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTerm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { metricAPI } from '../api'

const activeTab = ref('intents')
const intentTemplates = ref([])
const sqlTemplates = ref([])
const businessTerms = ref([])
const metricsList = ref([])

// 意图模板弹窗
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

// SQL 模板弹窗
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

// 业务术语弹窗
const termDialogVisible = ref(false)
const termDialogTitle = ref('添加术语映射')
const termForm = ref({
  term: '',
  description: ''
})
const editingTermId = ref(null)

// 优化建议
const optimizationSuggestions = ref([])
const analyzing = ref(false)

async function loadData() {
  try {
    const [intentsRes, sqlRes, termsRes, metricsRes, suggestionsRes] = await Promise.all([
      fetch('/api/v1/nlp/intents').then(r => r.json()),
      fetch('/api/v1/nlp/sql-templates').then(r => r.json()),
      fetch('/api/v1/metadata/terms').then(r => r.json()),
      metricAPI.list({ page: 1, page_size: 500 }),
      fetch('http://localhost:8081/api/v1/feedback/suggestions').then(r => r.json()).catch(() => ({ data: [] }))
    ])

    intentTemplates.value = intentsRes.data || []
    sqlTemplates.value = sqlRes.data || []
    businessTerms.value = termsRes.data || []
    metricsList.value = metricsRes.data?.list || []
    optimizationSuggestions.value = suggestionsRes.data || []
  } catch (e) {
    console.error('加载数据失败:', e)
  }
}

// 意图模板
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

// SQL 模板
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

// 业务术语
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
  try {
    await ElMessageBox.confirm('确定删除这个映射吗？', '提示', { type: 'warning' })
    await fetch(`/api/v1/metadata/terms/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 优化建议
async function loadSuggestions() {
  try {
    const res = await fetch('http://localhost:8081/api/v1/feedback/suggestions')
    const data = await res.json()
    optimizationSuggestions.value = data.data || []
  } catch (e) {
    console.error('加载优化建议失败:', e)
  }
}

async function triggerAnalysis() {
  analyzing.value = true
  try {
    await fetch('http://localhost:8081/api/v1/feedback/analyze', { method: 'POST' })
    ElMessage.success('分析已触发，请稍后刷新查看结果')
    // 延迟刷新
    setTimeout(() => loadSuggestions(), 2000)
  } catch (e) {
    ElMessage.error('触发分析失败')
  } finally {
    analyzing.value = false
  }
}

async function applySuggestion(id) {
  try {
    const res = await fetch(`http://localhost:8081/api/v1/feedback/suggestions/${id}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ applied_by: 'admin' })
    })
    const data = await res.json()
    if (data.success) {
      ElMessage.success('建议已应用')
      loadSuggestions()
    } else {
      ElMessage.error(data.message || '应用失败')
    }
  } catch (e) {
    ElMessage.error('应用失败')
  }
}

async function ignoreSuggestion(id) {
  try {
    const res = await fetch(`http://localhost:8081/api/v1/feedback/suggestions/${id}/ignore`, {
      method: 'POST'
    })
    const data = await res.json()
    if (data.success) {
      ElMessage.success('已忽略')
      loadSuggestions()
    } else {
      ElMessage.error(data.message || '操作失败')
    }
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

function getTypeLabel(type) {
  const labels = {
    'add_intent_pattern': '新增模式',
    'modify_pattern': '修改模式',
    'add_synonym': '添加同义词'
  }
  return labels[type] || type
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

// 重新生成意图向量
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

// 重新生成指标向量
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
</script>

<style scoped>
.nlp-config {
  padding: 48px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  letter-spacing: -0.5px;
  margin-bottom: 4px;
}

.page-desc {
  font-size: 14px;
  color: #7177a4;
}

.config-tabs {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
}

.section {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}

.table-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
}

.config-table th {
  text-align: left;
  padding: 14px 20px;
  font-size: 12px;
  font-weight: 600;
  color: #7177a4;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}

.config-table td {
  padding: 14px 20px;
  border-bottom: 1px solid #f0f0f5;
  font-size: 14px;
  color: #1a1a1a;
}

.config-table tr:last-child td {
  border-bottom: none;
}

.config-table tr:hover td {
  background: #fafafa;
}

.intent-badge {
  display: inline-block;
  padding: 4px 10px;
  background: #f0f0ff;
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
}

.sql-cell {
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
  color: #7177a4;
}

.metric-code {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
}

:deep(.el-tabs__item) {
  font-weight: 500;
}

:deep(.el-tabs__item.is-active) {
  color: #6366f1;
}

:deep(.el-tabs__active-bar) {
  background-color: #6366f1;
}

:deep(.el-select) {
  width: 100%;
}

.info-box {
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 20px;
  font-size: 13px;
  color: #67c23a;
}

.info-box p {
  margin: 0;
}

.type-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.type-badge.add_intent_pattern {
  background: #ecf5ff;
  color: #409eff;
}

.type-badge.modify_pattern {
  background: #fef0f0;
  color: #f56c6c;
}

.type-badge.add_synonym {
  background: #f0f9eb;
  color: #67c23a;
}

.value-cell {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fail-count {
  display: inline-block;
  padding: 2px 8px;
  background: #fef0f0;
  color: #f56c6c;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.confidence {
  color: #67c23a;
  font-weight: 500;
}

.reason-cell {
  max-width: 200px;
  font-size: 12px;
  color: #7177a4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
