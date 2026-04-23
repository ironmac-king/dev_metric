<template>
  <transition name="slide-in">
    <div v-if="visible" class="logic-chain-panel">
      <div class="panel-header">
        <div class="panel-title">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="1.5"/>
            <path d="M9 5V9L11 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>分析过程</span>
        </div>
        <button class="close-btn" @click="$emit('update:modelValue', false)">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>

      <div class="panel-content">
        <!-- 空状态提示 -->
        <div v-if="steps.length === 0 && !stepsVersion" class="empty-hint">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="20" stroke="rgba(99, 102, 241, 0.2)" stroke-width="2" stroke-dasharray="4 4"/>
            <path d="M24 16V28M24 32V34" stroke="rgba(99, 102, 241, 0.4)" stroke-width="2.5" stroke-linecap="round"/>
          </svg>
          <span>开始提问后将展示分析过程</span>
        </div>

        <!-- Steps List -->
        <div class="steps-list" :key="stepsVersion">
          <div
            v-for="(step, index) in enrichedSteps"
            :key="index"
            class="step-item"
            :class="[step.status, { active: currentStepIndex === index && step.status === 'pending' }]"
          >
            <div class="step-indicator">
              <div class="step-number">
                <svg v-if="step.status === 'completed'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6L5 9L10 3" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <svg v-else-if="step.status === 'warning'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 4V7M6 8.5V9" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <svg v-else-if="step.status === 'failed' || step.status === 'error'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 3L9 9M9 3L3 9" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <svg v-else-if="step.status === 'requires_clarification'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 4V7M6 8.5V9" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span v-else class="step-index">{{ index + 1 }}</span>
              </div>
              <div class="step-line" v-if="index < steps.length - 1"></div>
            </div>
            <div class="step-content">
              <div class="step-header">
                <span class="step-name">{{ getStepName(step.step) }}</span>
                <!-- intent_router: 显示来源标签 (本地模型/LLM/托底) -->
                <span v-if="step.step === 'intent_router' && step.source" class="source-badge" :class="'source-' + step.source">
                  {{ sourceLabelMap[step.source] || step.source }}
                </span>
              </div>
              <!-- intent_router 步骤的实体标签（调试用，虚线样式） -->
              <div v-if="step.step === 'intent_router' && step.entities && step.entities.length > 0" class="entity-tags entity-tags-debug">
                <span
                  v-for="entity in step.entities"
                  :key="entity.text"
                  class="entity-tag"
                  :class="'entity-' + (entity.type || 'entity').toLowerCase()"
                >
                  <span class="entity-type">{{ entityTypeNameMap[entity.type] || entity.type }}</span>
                  <span class="entity-text">{{ entity.text }}</span>
                </span>
              </div>
              <!-- 实体标签展示（非 intent_router 步骤） -->
              <div v-if="step.step !== 'intent_router' && step.entities && step.entities.length > 0" class="entity-tags">
                <span
                  v-for="entity in step.entities"
                  :key="entity.text"
                  class="entity-tag"
                  :class="'entity-' + (entity.type || 'entity').toLowerCase()"
                >
                  <span class="entity-type">{{ entityTypeNameMap[entity.type] || entity.type }}</span>
                  <span class="entity-text">{{ entity.text }}</span>
                </span>
              </div>
              <!-- MQL 关键信息展示 -->
              <div v-if="step.step === 'mql_generator' && step.mqlInfo" class="mql-info">
                <div v-if="step.mqlInfo.metric" class="mql-item">
                  <span class="mql-label">指标</span>
                  <span class="mql-value">{{ step.mqlInfo.metric }}</span>
                </div>
                <div v-if="step.mqlInfo.time" class="mql-item">
                  <span class="mql-label">时间</span>
                  <span class="mql-value">{{ step.mqlInfo.time }}</span>
                </div>
                <div v-if="step.mqlInfo.filters && step.mqlInfo.filters.length > 0" class="mql-item">
                  <span class="mql-label">过滤</span>
                  <span class="mql-value">{{ step.mqlInfo.filters.join(', ') }}</span>
                </div>
                <div v-if="step.mqlInfo.dimensions && step.mqlInfo.dimensions.length > 0" class="mql-item">
                  <span class="mql-label">维度</span>
                  <span class="mql-value">{{ step.mqlInfo.dimensions.join(', ') }}</span>
                </div>
                <div v-if="step.mqlInfo.patterns && step.mqlInfo.patterns.length > 0" class="mql-item">
                  <span class="mql-label">模式</span>
                  <span class="mql-value">{{ step.mqlInfo.patterns.join(', ') }}</span>
                </div>
              </div>
              <!-- MQL JSON 展示 (mql_semantic_validator 步骤) -->
              <div v-if="step.step === 'mql_semantic_validator' && step.mql" class="mql-json-block">
                <div class="mql-json-header" @click="toggleMqlJson(step.step)">
                  <span class="mql-json-toggle-icon">{{ expandedMqlSteps.has(step.step) ? '▼' : '▶' }}</span>
                  <span class="mql-json-label">MQL JSON</span>
                </div>
                <pre v-if="expandedMqlSteps.has(step.step)" class="mql-json-content">{{ formatMqlJson(step.mql) }}</pre>
              </div>
              <!-- SQL WHERE 条件展示 (sql_generator) -->
              <div v-if="step.step === 'sql_generator' && step.sqlWhere" class="sql-where">
                <span class="sql-where-label">WHERE</span>
                <span class="sql-where-text">{{ step.sqlWhere }}</span>
              </div>
              <!-- 错误详情 (sql_executor 等失败状态) -->
              <div v-if="(step.status === 'failed' || step.status === 'error') && step.errorDetail" class="error-detail">
                <span class="error-icon">⚠️</span>
                <span class="error-text">{{ step.errorDetail }}</span>
              </div>
              <!-- 默认 content 描述 -->
              <div class="step-description" v-if="step.content && !step.errorDetail">{{ step.content }}</div>
              <div class="step-meta">
                <span v-if="step.llm_used" class="llm-badge">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path d="M2 5L5 2L8 5M5 2V8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  LLM
                </span>
                <span v-if="step.duration" class="step-duration">{{ step.duration }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- SQL 展开区域 -->
        <div v-if="sql" class="sql-toggle-section">
          <button class="sql-toggle-btn" @click="toggleSql">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="1" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.2"/>
              <path d="M4 5L1 7L4 9M10 5L13 7L10 9M7 4L7 10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
            <span>{{ sqlExpanded ? '收起' : '展开' }}查询SQL</span>
            <svg class="toggle-icon" :class="{ expanded: sqlExpanded }" width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M3 5L6 8L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <div v-if="sqlExpanded" class="sql-code-block">
            <pre v-html="highlightSql(sql)"></pre>
            <button class="sql-copy-btn" @click="copySql">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <rect x="4" y="4" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/>
                <path d="M2 8V2H8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              复制
            </button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  steps: {
    type: Array,
    default: () => []
  },
  sql: {
    type: String,
    default: ''
  },
  stepsVersion: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const currentStepIndex = computed(() => {
  return props.steps.findIndex(s => s.status === 'pending' || s.status === 'in_progress')
})

// SQL 展开状态
const sqlExpanded = ref(false)

// MQL JSON 展开状态
const expandedMqlSteps = ref(new Set())

// 切换 SQL 显示
function toggleSql() {
  sqlExpanded.value = !sqlExpanded.value
}

// 切换 MQL JSON 展开/收起
function toggleMqlJson(stepName) {
  if (expandedMqlSteps.value.has(stepName)) {
    expandedMqlSteps.value.delete(stepName)
  } else {
    expandedMqlSteps.value.add(stepName)
  }
  // 触发响应式更新
  expandedMqlSteps.value = new Set(expandedMqlSteps.value)
}

// 格式化 MQL JSON 用于展示（精简关键字段）
function formatMqlJson(mql) {
  if (!mql) return ''
  try {
    const精简 = {
      intent: mql.intent,
      metric: mql.metric ? {
        code: mql.metric.code,
        name: mql.metric.name,
        field: mql.metric.field,
        aggregation: mql.metric.aggregation,
        starrocks_sql: mql.metric.starrocks_sql ? '(已配置)' : null
      } : null,
      time: mql.time,
      dimensions: mql.dimensions,
      filters: mql.filters,
      comparison: mql.comparison,
      calculation_patterns: mql.calculation_patterns,
      order_by: mql.order_by,
      pagination: mql.pagination,
    }
    // 移除 null 值
    Object.keys(精简).forEach(k => {
      if (精简[k] === null || 精简[k] === undefined) delete 精简[k]
    })
    return JSON.stringify(精简, null, 2)
  } catch (e) {
    return JSON.stringify(mql, null, 2)
  }
}

// 复制 SQL
async function copySql() {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(props.sql)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = props.sql
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
  } catch (err) {
    console.error('复制失败:', err)
  }
}

// 步骤名称中英文映射 - 用户友好中文
const stepNameMap = {
  // V2 架构 11 步
  'intent_router': '理解意图',
  'context_enhancer': '增强上下文',
  'mql_generator': '生成查询逻辑',
  'mql_syntax_validator': '校验语法',
  'mql_semantic_validator': '校验语义',
  'sql_generator': '生成SQL',
  'sql_security_auditor': '安全审计',
  'sql_executor': '执行查询',
  'data_quality_checker': '质量检查',
  'result_analyzer': '分析结果',
  'state_manager': '整理输出',
  // 兼容旧名称
  'intent_node': '理解意图',
  'entity_router': '识别实体',
  'entity_node': '识别实体',
  'sql_gen': '生成SQL',
  'sql_gen_node': '生成SQL',
  'execute': '执行查询',
  'execute_node': '执行查询',
  'response': '生成回答',
  'response_node': '生成回答',
  'intent recognition': '理解意图',
  'entity extraction': '识别实体',
  'sql generation': '生成SQL',
  'execution': '执行查询',
  'response generation': '生成回答'
}

function getStepName(stepName) {
  return stepNameMap[stepName] || stepName
}

// 来源标签映射 (intent_router 步骤显示)
const sourceLabelMap = {
  'local_model': '本地模型',
  'llm': 'LLM',
  'fallback': '托底',
  'followup': '追问',
}

// 实体类型中文映射
const entityTypeNameMap = {
  'METRIC': '指标',
  'TIME': '时间',
  'FILTER': '过滤',
  'DIMENSION': '维度',
  'OPERATOR': '操作',
  'COMPARISON': '对比',
  'ENTITY': '实体',
  'VALUE': '值',
}

// 实体类型颜色
const entityTypeColorMap = {
  'METRIC': '#6366F1',
  'TIME': '#059669',
  'FILTER': '#D97706',
  'DIMENSION': '#7C3AED',
  'OPERATOR': '#0891B2',
  'COMPARISON': '#DC2626',
  'ENTITY': '#6B7280',
  'VALUE': '#374151',
}

// 计算 enrichedSteps - 为每个 step 添加额外展示信息
const enrichedSteps = computed(() => {
  return props.steps.map(step => {
    const enriched = { ...step }

    // intent_router: 提取实体信息（已经在 entities 里，前端直接用）
    // mql_generator: 尝试从 content 解析 MQL 信息
    if (step.step === 'mql_generator' && step.content) {
      const mqlInfo = parseMqlInfo(step)
      enriched.mqlInfo = mqlInfo
    }

    // sql_generator: 提取 WHERE 条件
    if (step.step === 'sql_generator' && step.content) {
      const sqlMatch = step.content.match(/SQL 生成成功[:：]?\s*(.+)/i)
      if (sqlMatch) {
        const sql = sqlMatch[1].trim()
        // 提取 WHERE 之后的部分
        const whereIdx = sql.toUpperCase().indexOf('WHERE')
        if (whereIdx !== -1) {
          enriched.sqlWhere = sql.substring(whereIdx + 5).trim()
        } else {
          enriched.sqlWhere = sql
        }
      }
    }

    // 失败步骤: 提取错误详情
    if ((step.status === 'failed' || step.status === 'error') && step.content) {
      enriched.errorDetail = step.content
    }

    return enriched
  })
})

// 解析 MQL 信息
function parseMqlInfo(step) {
  const info = {}
  const content = step.content || ''
  const entities = step.entities || []

  // 从 entities 提取指标
  const metricEntity = entities.find(e => e.type === 'METRIC')
  if (metricEntity) {
    info.metric = metricEntity.text
  }

  // 从 entities 提取时间
  const timeEntity = entities.find(e => e.type === 'TIME')
  if (timeEntity) {
    info.time = timeEntity.text
  }

  // 从 entities 提取过滤
  const filterEntities = entities.filter(e => e.type === 'FILTER')
  if (filterEntities.length > 0) {
    info.filters = filterEntities.map(e => e.text)
  }

  // 从 entities 提取维度
  const dimEntities = entities.filter(e => e.type === 'DIMENSION')
  if (dimEntities.length > 0) {
    info.dimensions = dimEntities.map(e => e.text)
  }

  // 从 content 解析模式（环比、同比等）
  if (content.includes('环比') || content.includes('mom') || content.includes('MoM')) {
    info.patterns = info.patterns || []
    info.patterns.push('环比(MoM)')
  }
  if (content.includes('同比') || content.includes('yoy') || content.includes('YoY')) {
    info.patterns = info.patterns || []
    info.patterns.push('同比(YoY)')
  }

  return info
}

// SQL Syntax Highlighting
function highlightSql(sql) {
  if (!sql) return ''

  // HTML 转义映射
  const htmlEscapes = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }

  // 先转义 HTML
  let result = sql.replace(/[&<>"']/g, char => htmlEscapes[char])

  // Keywords
  const keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'GROUP', 'BY', 'ORDER', 'ASC', 'DESC', 'LIMIT', 'OFFSET', 'HAVING', 'AS', 'IN', 'NOT', 'NULL', 'IS', 'LIKE', 'BETWEEN', 'EXISTS', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'UNION', 'ALL', 'DISTINCT', 'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP', 'ALTER', 'INDEX', 'VIEW']
  const functions = ['SUM', 'AVG', 'COUNT', 'MAX', 'MIN', 'COALESCE', 'IFNULL', 'NVL', 'CAST', 'CONVERT', 'DATE', 'YEAR', 'MONTH', 'DAY', 'NOW', 'DATEADD', 'DATEDIFF', 'CONCAT', 'SUBSTRING', 'TRIM', 'UPPER', 'LOWER', 'LENGTH', 'ROUND', 'FLOOR', 'CEIL', 'ABS']

  // 关键词高亮（不会影响已转义的 HTML 实体）
  keywords.forEach(kw => {
    const regex = new RegExp(`\\b(${kw})\\b`, 'gi')
    result = result.replace(regex, '<span class="sql-keyword">$1</span>')
  })

  // 函数高亮
  functions.forEach(fn => {
    const regex = new RegExp(`\\b(${fn})\\b`, 'gi')
    result = result.replace(regex, '<span class="sql-function">$1</span>')
  })

  // 字符串高亮
  result = result.replace(/&#39;([^&#]*)&#39;/g, '<span class="sql-string">&#39;$1&#39;</span>')
  result = result.replace(/&quot;([^&]*)&quot;/g, '<span class="sql-string">&quot;$1&quot;</span>')

  // 数字高亮
  result = result.replace(/\b(\d+\.?\d*)\b/g, '<span class="sql-number">$1</span>')

  return result
}
</script>

<style scoped>
.logic-chain-panel {
  position: sticky;
  top: 40px;
  width: 500px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 40px rgba(99, 102, 241, 0.08), 0 4px 16px rgba(99, 102, 241, 0.05), 0 0 120px rgba(99, 102, 241, 0.04), 0 0 200px rgba(139, 92, 246, 0.03);
  z-index: 100;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(99, 102, 241, 0.08);
  max-height: calc(100vh - 80px);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(99, 102, 241, 0.08);
  flex-shrink: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}

.panel-title svg {
  color: #6366F1;
}

.close-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(99, 102, 241, 0.08);
  color: #6366F1;
}

/* 空状态提示 */
.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: rgba(99, 102, 241, 0.5);
  font-size: 13px;
  text-align: center;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* Steps List */
.steps-list {
  display: flex;
  flex-direction: column;
}

.step-item {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.step-item.active {
  background: rgba(99, 102, 241, 0.04);
  border-radius: 8px;
  margin: 0 -8px;
  padding: 12px 8px;
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.step-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

.step-item.completed .step-number {
  background: #6366F1;
  color: #fff;
}

.step-item.warning .step-number {
  background: #F59E0B;
  color: #fff;
}

.step-item.failed .step-number,
.step-item.error .step-number {
  background: #EF4444;
  color: #fff;
}

.step-item.requires_clarification .step-number {
  background: #6366F1;
  color: #fff;
}

.step-item.pending .step-number,
.step-item.in_progress .step-number {
  background: #6366F1;
  color: #fff;
}

.step-index {
  font-size: 11px;
}

.step-line {
  width: 2px;
  flex: 1;
  min-height: 16px;
  background: #e5e7eb;
  margin: 4px 0;
  border-radius: 1px;
}

.step-item.completed .step-line {
  background: linear-gradient(180deg, #6366F1 0%, #e5e7eb 100%);
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.step-name {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.step-item.failed .step-name,
.step-item.error .step-name {
  color: #EF4444;
}

/* 来源标签 (本地模型/LLM) */
.source-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.source-local_model {
  background: rgba(5, 150, 105, 0.1);
  color: #059669;
}

.source-llm {
  background: rgba(99, 102, 241, 0.1);
  color: #6366F1;
}

.source-fallback {
  background: rgba(245, 158, 11, 0.1);
  color: #D97706;
}

.source-followup {
  background: rgba(124, 58, 237, 0.1);
  color: #7C3AED;
}

.step-description {
  font-size: 11px;
  color: #6b7280;
  margin-top: 4px;
  line-height: 1.5;
  word-break: break-all;
}

/* 实体标签 */
.entity-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.entity-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.entity-tag .entity-type {
  opacity: 0.7;
  font-size: 9px;
}

.entity-tag .entity-text {
  font-weight: 600;
}

.entity-metric {
  background: rgba(99, 102, 241, 0.1);
  color: #6366F1;
}

.entity-time {
  background: rgba(5, 150, 105, 0.1);
  color: #059669;
}

.entity-filter {
  background: rgba(217, 119, 6, 0.1);
  color: #D97706;
}

.entity-dimension {
  background: rgba(124, 58, 237, 0.1);
  color: #7C3AED;
}

.entity-operator {
  background: rgba(8, 145, 178, 0.1);
  color: #0891B2;
}

.entity-comparison {
  background: rgba(220, 38, 38, 0.1);
  color: #DC2626;
}

/* intent_router 步骤的实体标签（调试用，虚线边框） */
.entity-tags-debug {
  border: 1px dashed rgba(99, 102, 241, 0.3);
  border-radius: 6px;
  padding: 6px 8px;
  margin-top: 4px;
  background: rgba(99, 102, 241, 0.02);
}

/* MQL 信息展示 */
.mql-info {
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(99, 102, 241, 0.04);
  border-radius: 6px;
  border: 1px solid rgba(99, 102, 241, 0.08);
}

.mql-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 11px;
  line-height: 1.6;
}

.mql-item + .mql-item {
  margin-top: 4px;
}

.mql-label {
  color: #6b7280;
  flex-shrink: 0;
  min-width: 28px;
}

.mql-value {
  color: #374151;
  font-weight: 500;
  word-break: break-all;
}

/* SQL WHERE 条件 */
.sql-where {
  margin-top: 8px;
  padding: 6px 10px;
  background: #F8FAFC;
  border-radius: 6px;
  font-size: 11px;
  font-family: 'Monaco', 'Menlo', monospace;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.sql-where-label {
  color: #6366F1;
  font-weight: 600;
  flex-shrink: 0;
}

.sql-where-text {
  color: #374151;
  word-break: break-all;
  line-height: 1.5;
}

/* 错误详情 */
.error-detail {
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(239, 68, 68, 0.06);
  border-radius: 6px;
  border: 1px solid rgba(239, 68, 68, 0.15);
  font-size: 11px;
  display: flex;
  gap: 6px;
  align-items: flex-start;
}

.error-icon {
  flex-shrink: 0;
}

.error-text {
  color: #DC2626;
  line-height: 1.5;
  word-break: break-all;
}

/* MQL JSON 块 */
.mql-json-block {
  margin-top: 8px;
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 6px;
  overflow: hidden;
}

.mql-json-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(99, 102, 241, 0.06);
  cursor: pointer;
  user-select: none;
  font-size: 11px;
  font-weight: 500;
  color: #6366F1;
}

.mql-json-header:hover {
  background: rgba(99, 102, 241, 0.1);
}

.mql-json-toggle-icon {
  font-size: 9px;
  color: #6366F1;
}

.mql-json-label {
  color: #6366F1;
}

.mql-json-content {
  margin: 0;
  padding: 10px;
  background: #F8FAFC;
  font-size: 10px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: #374151;
  line-height: 1.6;
  overflow-x: auto;
  max-height: 300px;
  white-space: pre-wrap;
  word-break: break-all;
}

.step-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.llm-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  background: rgba(99, 102, 241, 0.1);
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  color: #6366F1;
}

.step-duration {
  font-size: 11px;
  color: #9ca3af;
}

/* SQL Preview */
.sql-preview-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(99, 102, 241, 0.12);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #6366F1;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-header svg {
  color: #6366F1;
}

.sql-code-block {
  background: #F8FAFC;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(99, 102, 241, 0.12);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.06);
}

.sql-code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(99, 102, 241, 0.04);
  border-bottom: 1px solid rgba(99, 102, 241, 0.08);
}

.sql-dots {
  display: flex;
  gap: 6px;
}

.sql-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.sql-dot:nth-child(1) { background: #FF5F56; }
.sql-dot:nth-child(2) { background: #FFBD2E; }
.sql-dot:nth-child(3) { background: #27CA40; }

.sql-copy-btn {
  padding: 4px 10px;
  background: rgba(99, 102, 241, 0.15);
  border: none;
  border-radius: 6px;
  color: #8B5CF6;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 4px;
}

.sql-copy-btn:hover {
  background: rgba(99, 102, 241, 0.25);
  color: #A78BFA;
}

.sql-code-block pre {
  padding: 12px;
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
}

/* SQL Toggle Section */
.sql-toggle-section {
  padding: 12px 16px;
  border-top: 1px solid rgba(99, 102, 241, 0.08);
  flex-shrink: 0;
}

.sql-toggle-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: rgba(99, 102, 241, 0.04);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 8px;
  color: #6366F1;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.sql-toggle-btn:hover {
  background: rgba(99, 102, 241, 0.08);
}

.sql-toggle-btn .toggle-icon {
  margin-left: auto;
  transition: transform 0.2s;
}

.sql-toggle-btn .toggle-icon.expanded {
  transform: rotate(180deg);
}

.sql-toggle-section .sql-code-block {
  margin-top: 8px;
  position: relative;
  background: #F8FAFC;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(99, 102, 241, 0.12);
}

.sql-toggle-section .sql-code-block pre {
  max-height: 200px;
}

.sql-toggle-section .sql-copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 10px;
  background: rgba(99, 102, 241, 0.1);
  border: none;
  border-radius: 4px;
  color: #6366F1;
  font-size: 11px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
  z-index: 10;
}

.sql-toggle-section .sql-copy-btn:hover {
  background: rgba(99, 102, 241, 0.2);
}

/* SQL Syntax Highlighting */
pre :deep(.sql-keyword) { color: #6366F1; font-weight: 600; }
pre :deep(.sql-function) { color: #059669; }
pre :deep(.sql-string) { color: #D97706; }
pre :deep(.sql-number) { color: #7C3AED; }
pre :deep(.sql-operator) { color: #6366F1; }
pre :deep(.sql-comment) { color: #9CA3AF; font-style: italic; }
pre :deep(.sql-table) { color: #0891B2; }
pre :deep(.sql-column) { color: #374151; }

/* Slide transition */
.slide-in-enter-active,
.slide-in-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-in-enter-from,
.slide-in-leave-to {
  transform: translateX(100%);
}
</style>
