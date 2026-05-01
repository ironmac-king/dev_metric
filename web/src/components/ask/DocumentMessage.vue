<template>
  <div class="document-message">

    <!-- 骨架屏（按类型定制） -->
    <template v-if="loading">
      <div v-if="queryType === 'A' || queryType === 'A_SIMPLE'" class="skeleton-a">
        <el-skeleton :rows="3" animated />
      </div>
      <div v-else-if="queryType === 'B'" class="skeleton-b">
        <el-skeleton :rows="2" animated />
        <div class="supplement-card">
          <el-skeleton :rows="3" animated />
        </div>
      </div>
      <div v-else class="skeleton-c">
        <el-skeleton :rows="4" animated />
      </div>
    </template>

    <!-- 实际内容 -->
    <template v-else>

      <!-- 类型 A / A_SIMPLE：完整文档结构 -->
      <template v-if="queryType === 'A' || queryType === 'A_SIMPLE'">
        <!-- 头部 -->
        <div class="doc-header">
          <h1># {{ queryTitle }}</h1>
          <div class="doc-meta">
            <span>**查询时间**：{{ timeRange }}</span>
            <span>**数据来源**：指标系统</span>
            <span>**数据状态**：{{ dataStatus }}</span>
          </div>
        </div>

        <!-- 核心结论（仅类型A有） -->
        <div v-if="queryType === 'A'" class="doc-section">
          <h2>## 一、核心结论</h2>
          <p class="lead-conclusion">{{ coreConclusion }}</p>
          <ul v-if="highlights.length || issues.length" class="highlights">
            <li v-for="h in highlights" class="highlight-positive">🥇 {{ h }}</li>
            <li v-for="i in issues" class="highlight-problem">⚠️ {{ i }}</li>
          </ul>
        </div>

        <!-- 核心数据表格 -->
        <div class="doc-section" v-if="resultData.length">
          <h2>## 二、核心数据表格</h2>
          <div class="table-toolbar">
            <el-button size="small" @click="handleCopy">
              <el-dropdown trigger="click" @command="handleCopyFormat">
                <span>复制<i class="el-icon-arrow-down el-icon--right"></i></span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="excel">Excel 格式</el-dropdown-item>
                    <el-dropdown-item command="markdown">Markdown 格式</el-dropdown-item>
                    <el-dropdown-item command="csv">CSV 格式</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </el-button>
          </div>
          <el-table
            :data="resultData"
            border
            stripe
            @row-click="handleRowClick"
            @header-click="handleHeaderClick"
            class="doc-table"
          >
            <el-table-column
              v-for="col in columns"
              :key="col.prop"
              :prop="col.prop"
              :label="col.label"
              :formatter="col.formatter"
              :sortable="col.sortable"
              :fixed="col.fixed"
            >
              <template #default="{ row }">
                <span :class="{ 'trend-up': isPositiveTrend(row[col.prop]), 'trend-down': isNegativeTrend(row[col.prop]) }">
                  {{ col.formatter ? col.formatter(row[col.prop]) : row[col.prop] }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 分析摘要（仅类型A有） -->
        <div class="doc-section" v-if="queryType === 'A' && hasAnalysis">
          <h2>## 三、分析摘要</h2>
          <div v-if="urgentIssues.length" class="alert alert-danger">
            <strong>🔴 紧急问题</strong>
            <ul><li v-for="i in urgentIssues">{{ i }}</li></ul>
          </div>
          <div v-if="warnings.length" class="alert alert-warning">
            <strong>🟡 预警提示</strong>
            <ul><li v-for="w in warnings">{{ w }}</li></ul>
          </div>
          <div v-if="positiveItems.length" class="alert alert-success">
            <strong>🟢 积极亮点</strong>
            <ul><li v-for="p in positiveItems">{{ p }}</li></ul>
          </div>
        </div>

        <!-- 你可能还会问 -->
        <div class="doc-section" v-if="suggestions.length">
          <h2>## 四、你可能还会问</h2>
          <div class="suggest-tags">
            <span
              v-for="s in suggestions"
              :key="s"
              class="suggest-tag"
              @click="$emit('select-suggestion', s)"
            >
              {{ s }}
            </span>
          </div>
        </div>
      </template>

      <!-- 类型 B：极简一句话 + 补充信息卡片 -->
      <template v-else-if="queryType === 'B'">
        <div class="type-b-answer">
          <p v-html="formattedAnswer"></p>
        </div>

        <!-- 补充信息卡片 -->
        <div class="supplement-card" v-if="supplementaryInfo.length">
          <div class="supplement-title">📌 补充信息</div>
          <div class="supplement-list">
            <div v-for="item in supplementaryInfo" :key="item.label" class="supplement-item">
              <span class="label">{{ item.label }}</span>
              <span class="value">
                {{ item.value }}
                <span
                  v-if="item.trend"
                  :class="item.trend.startsWith('+') ? 'trend-up' : 'trend-down'"
                >
                  {{ item.trend }}
                </span>
              </span>
            </div>
          </div>
        </div>

        <!-- 建议问题 -->
        <div class="suggest-tags" v-if="suggestions.length" style="margin-top: 12px;">
          <span
            v-for="s in suggestions"
            :key="s"
            class="suggest-tag"
            @click="$emit('select-suggestion', s)"
          >
            {{ s }}
          </span>
        </div>
      </template>

      <!-- 类型 C：分析型 → 文档结论 + 自然语言分析 -->
      <template v-else-if="queryType === 'C'">
        <div class="doc-header">
          <h1># {{ queryTitle }}</h1>
          <div class="doc-meta">
            <span>**分析时间**：{{ timeRange }}</span>
          </div>
        </div>

        <div class="doc-section">
          <h2>## 核心结论</h2>
          <p class="lead-conclusion">{{ coreConclusion }}</p>
        </div>

        <div class="doc-section" v-if="analysisContent">
          <h2>## 详细分析</h2>
          <div class="analysis-block" v-html="analysisContent"></div>
        </div>

        <div class="doc-section" v-if="suggestions.length">
          <h2>## 建议措施</h2>
          <div class="suggest-tags">
            <span
              v-for="s in suggestions"
              :key="s"
              class="suggest-tag"
              @click="$emit('select-suggestion', s)"
            >
              {{ s }}
            </span>
          </div>
        </div>
      </template>

      <!-- 底部操作栏 -->
      <div class="doc-actions">
        <button @click="$emit('export')">[导出Excel]</button>
        <button @click="$emit('share')">[分享]</button>
        <button @click="handleCopy">[复制]</button>
        <button @click="$emit('toggle-thinking')">[查看分析过程]</button>
        <button @click="$emit('feedback', 1)" :class="{ active: userFeedback === 1 }">[👍]</button>
        <button @click="$emit('feedback', -1)" :class="{ active: userFeedback === -1 }">[👎]</button>
      </div>

    </template>

    <!-- 空状态 -->
    <div v-if="!loading && !hasContent" class="empty-state">
      <p>暂无数据</p>
      <div class="empty-reasons">
        <p>📌 可能原因：</p>
        <ul>
          <li>所选时间范围内没有销售记录</li>
          <li>数据尚未同步完成（通常延迟15分钟）</li>
        </ul>
      </div>
      <div class="empty-actions">
        <el-button size="small" @click="$emit('retry')">[刷新重试]</el-button>
        <el-button size="small" @click="$emit('view-alternative')">[查看昨天的数据]</el-button>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-if="error" class="error-state">
      <p>查询失败，请稍后重试</p>
      <p class="error-detail">错误信息：{{ error }}</p>
      <div class="empty-actions">
        <el-button size="small" @click="$emit('retry')">[重试]</el-button>
        <el-button size="small" @click="$emit('contact-support')">[联系技术支持]</el-button>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  msg: {
    content?: string
    result_data?: any[]
    analysis?: any
    suggest?: string[]
    supplementary_info?: any[]
    intent?: string
    thread_id?: string
    force_query_type?: string
    drilldown_options?: string[]
    is_follow_up?: boolean
    append_to_message_id?: string
    [key: string]: any
  }
  loading?: boolean
  error?: string
  userFeedback?: number
}>()

const emit = defineEmits<{
  'select-suggestion': [item: string]
  'export': []
  'share': []
  'copy': []
  'toggle-thinking': []
  'feedback': [value: number]
  'drilldown': [dimValue: string]
  'retry': []
  'view-alternative': []
  'contact-support': []
}>()

// ========== 查询类型判断 ==========
const analysisKeywords = [
  '为什么', '原因', '分析', '趋势', '预测',
  '怎么回事', '下滑', '增长', '波动'
]

function classifyQuery(msg: any): 'A' | 'B' | 'C' | 'A_SIMPLE' {
  // 最高优先级：后端强制指定
  if (msg.force_query_type) return msg.force_query_type

  const { intent, result_data, content } = msg
  const row = result_data?.[0]
  const colCount = row ? Object.keys(row).length : 0

  // 类型A：排名/对比意图，或（行数>3 且 列数>3）
  if (
    intent === 'query_ranking' ||
    intent === 'query_comparison' ||
    (result_data?.length > 3 && colCount > 3)
  ) {
    return 'A'
  }

  // 类型C：分析意图 或 包含分析关键词
  const isAnalysisIntent =
    intent === 'query_anomaly' ||
    analysisKeywords.some((k: string) => content?.includes(k))

  if (isAnalysisIntent) {
    return 'C'
  }

  // 简化版类型A：行数>3 但列数<=3（如 "日期，销售额" 趋势数据）
  if (result_data?.length > 3 && colCount <= 3) {
    return 'A_SIMPLE'
  }

  // 类型B：默认简单事实型
  return 'B'
}

const queryType = computed(() => classifyQuery(props.msg))

// ========== 数据解析 ==========
const queryTitle = computed(() => {
  // 从用户问题提取前30字符作为标题
  const content = props.msg.content || ''
  if (content.length > 30) {
    return content.substring(0, 30) + '...'
  }
  return content || '数据查询结果'
})

const timeRange = computed(() => {
  const time = props.msg.mql?.time
  if (time?.start && time?.end) {
    return `${time.start} ~ ${time.end}`
  }
  return '本月'
})

const dataStatus = computed(() => {
  const data = props.msg.result_data
  if (!data || data.length === 0) {
    return '❌ 数据为空'
  }
  return `✅ 数据完整 | 包含${data.length}条记录`
})

const resultData = computed(() => {
  return props.msg.result_data || []
})

const coreConclusion = computed(() => {
  // 优先从 analysis 获取
  if (props.msg.analysis?.summary) {
    return props.msg.analysis.summary
  }
  // 从 answer 提取第一句
  const content = props.msg.content || ''
  const sentences = content.split(/[。.!?]/).filter(Boolean)
  return sentences[0] || content
})

const highlights = computed(() => {
  if (props.msg.analysis?.highlights) {
    return props.msg.analysis.highlights
  }
  // 从 answer 中提取包含增长/上升等词的句子
  const content = props.msg.content || ''
  const sentences = content.split(/[。.!?]/).filter(Boolean)
  return sentences.filter((s: string) =>
    /增长|上升|超预期|突破|创新高/.test(s)
  )
})

const issues = computed(() => {
  if (props.msg.analysis?.issues) {
    return props.msg.analysis.issues
  }
  // 从 answer 中提取包含下降/问题等词的句子
  const content = props.msg.content || ''
  const sentences = content.split(/[。.!?]/).filter(Boolean)
  return sentences.filter((s: string) =>
    /下降|下滑|问题|风险|异常/.test(s)
  )
})

const supplementaryInfo = computed(() => {
  return props.msg.supplementary_info || []
})

const suggestions = computed(() => {
  return props.msg.suggest || props.msg.suggestions || []
})

const hasAnalysis = computed(() => {
  return props.msg.analysis && (
    props.msg.analysis.highlights?.length ||
    props.msg.analysis.issues?.length ||
    props.msg.analysis.action_items?.length
  )
})

const hasContent = computed(() => {
  return props.msg.content || resultData.value.length > 0
})

const analysisContent = computed(() => {
  // 详细分析内容，可能是 HTML 或纯文本
  return props.msg.analysis?.content || props.msg.analysis?.detail || ''
})

// ========== 类型C 分析项 ==========
const urgentIssues = computed(() => {
  return props.msg.analysis?.urgent_issues || []
})

const warnings = computed(() => {
  return props.msg.analysis?.warnings || []
})

const positiveItems = computed(() => {
  return props.msg.analysis?.positives || []
})

// ========== 表格列定义 ==========
const columns = computed(() => {
  if (!resultData.value.length) return []

  const row = resultData.value[0]
  const keys = Object.keys(row)

  // 判断前两列是否为关键列（固定）
  const fixedCols = keys.slice(0, 2)

  return keys.map((key: string, index: number) => {
    const isNumeric = typeof row[key] === 'number' ||
      (typeof row[key] === 'string' && /^-?[\d,]+\.?\d*$/.test(row[key]))

    return {
      prop: key,
      label: key,
      sortable: true,
      fixed: fixedCols.includes(key) ? (index < 2 ? key : false) : false,
      formatter: (value: any) => formatCellValue(value, isNumeric)
    }
  })
})

// ========== 格式化 ==========
function formatCellValue(value: any, isNumeric: boolean): string {
  if (value === null || value === undefined) return '-'
  if (!isNumeric) return String(value)

  const num = typeof value === 'string'
    ? parseFloat(value.replace(/,/g, ''))
    : value

  if (isNaN(num)) return String(value)

  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  }).format(num)
}

function isPositiveTrend(value: any): boolean {
  if (typeof value === 'string' && value.includes('+')) return true
  if (typeof value === 'number' && value > 0) return true
  return false
}

function isNegativeTrend(value: any): boolean {
  if (typeof value === 'string' && (value.includes('-') || value.includes('↓'))) return true
  if (typeof value === 'number' && value < 0) return true
  return false
}

const formattedAnswer = computed(() => {
  // 将 answer 中的关键数据加粗
  const content = props.msg.content || ''
  return content.replace(/(\d+\.?\d*)(万|亿|元|%|件|个)?/g, (match) => {
    return `<strong>${match}</strong>`
  })
})

// ========== 交互操作 ==========
function handleRowClick(row: any) {
  // 点击行时，可触发下钻
  const firstCell = Object.values(row)[0]
  if (firstCell) {
    ElMessage({
      message: `点击查看 [${firstCell}] 详细数据`,
      type: 'info',
      duration: 2000
    })
  }
}

function handleHeaderClick(column: any) {
  // 点击表头排序（前端排序）
  // el-table 自带排序功能
}

function handleCopy() {
  // 默认复制为 Excel 格式
  handleCopyFormat('excel')
}

function handleCopyFormat(format: string) {
  if (!resultData.value.length) return

  let content = ''
  const headers = columns.value.map(c => c.label)
  const rows = resultData.value.map(row =>
    columns.value.map(c => row[c.prop])
  )

  if (format === 'excel') {
    content = [headers.join('\t'), ...rows.map(r => r.join('\t'))].join('\n')
  } else if (format === 'markdown') {
    content = ['|' + headers.join('|') + '|', '|' + headers.map(() => '---').join('|') + '|',
      ...rows.map(r => '|' + r.join('|') + '|')].join('\n')
  } else if (format === 'csv') {
    content = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  }

  navigator.clipboard.writeText(content).then(() => {
    ElMessage({ message: '复制成功', type: 'success', duration: 2000 })
  })
}
</script>

<style scoped>
/* 基础容器 */
.document-message {
  width: 100%;
  background: transparent;
  padding: 0;
  border-radius: 0;
  box-shadow: none;
}

/* 标题层级 */
.document-message h1 {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 8px;
}
.document-message h2 {
  font-size: 16px;
  font-weight: bold;
  margin: 16px 0 8px;
}

/* 元信息栏 */
.doc-meta {
  display: flex;
  gap: 24px;
  font-size: 13px;
  color: #666;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 16px;
}

/* 表格 */
.doc-table {
  width: 100%;
  margin-top: 12px;
}
.doc-table :deep(th) {
  background: #f8f9fa !important;
  font-weight: 600;
}
.doc-table :deep(td),
.doc-table :deep(th) {
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
}
.doc-table :deep(tr:hover) {
  background: #f0f9ff !important;
}
.table-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

/* 数字右对齐 */
.numeric { text-align: right; }

/* 趋势颜色 */
.trend-up { color: #10B981; font-weight: 600; }
.trend-down { color: #EF4444; font-weight: 600; }

/* 状态标签 */
.badge-success { color: #10B981; }
.badge-warning { color: #F59E0B; }
.badge-danger { color: #EF4444; }

/* 分析摘要 */
.alert {
  padding: 10px 14px;
  border-radius: 8px;
  margin: 6px 0;
}
.alert-danger { background: #FEF2F2; border-left: 3px solid #EF4444; }
.alert-warning { background: #FFFBEB; border-left: 3px solid #F59E0B; }
.alert-success { background: #F0FDF4; border-left: 3px solid #10B981; }

/* 折叠面板 */
.collapse-panel {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-top: 8px;
  transition: all 0.3s ease;
}
.collapse-header {
  padding: 10px 14px;
  background: #f8f9fa;
  cursor: pointer;
  font-weight: 600;
  border-radius: 8px;
}
.collapse-content {
  padding: 12px;
}

/* 底部操作栏 */
.doc-actions {
  display: flex;
  gap: 8px;
  padding: 12px 0;
  border-top: 1px solid #e5e7eb;
  margin-top: 16px;
}
.doc-actions button {
  padding: 6px 14px;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.doc-actions button:hover { background: #f8f9fa; }
.doc-actions button.active { background: #e0f2fe; border-color: #0369a1; }

/* 建议标签 */
.suggest-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.suggest-tag {
  padding: 6px 14px;
  background: #f0f9ff;
  border: 1px solid #e0f2fe;
  border-radius: 999px;
  font-size: 13px;
  color: #0369a1;
  cursor: pointer;
  transition: all 0.15s;
}
.suggest-tag:hover { background: #e0f2fe; }

/* 类型B极简样式 */
.type-b-answer {
  font-size: 15px;
  line-height: 1.6;
}
.type-b-answer :deep(strong) {
  font-size: 18px;
  color: #1a1a1a;
}

/* 补充信息卡片 */
.supplement-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px 16px;
  margin-top: 12px;
}
.supplement-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: #333;
}
.supplement-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}
.supplement-item .label {
  color: #666;
}
.supplement-item .value {
  color: #333;
  font-weight: 500;
}

/* 分析块 */
.analysis-block {
  margin: 12px 0;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
}

/* 空状态 */
.empty-state,
.error-state {
  text-align: center;
  padding: 24px;
  color: #666;
}
.empty-reasons {
  text-align: left;
  margin: 16px 0;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}
.empty-reasons ul {
  margin: 8px 0 0 20px;
}
.empty-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 16px;
}
.error-detail {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}

/* 骨架屏 */
.skeleton-a,
.skeleton-b,
.skeleton-c {
  padding: 12px;
}
</style>
