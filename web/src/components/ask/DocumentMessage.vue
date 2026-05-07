<template>
  <div class="document-message">

    <!-- 骨架屏 -->
    <template v-if="loading">
      <div class="skeleton-content">
        <el-skeleton :rows="3" animated />
      </div>
    </template>

    <!-- 实际内容 -->
    <template v-else>

      <!-- 类型 A / A_SIMPLE / C：文档结构 -->
      <template v-if="queryType === 'A' || queryType === 'A_SIMPLE' || queryType === 'C'">
        <div class="assistant-document">
          <!-- 元信息 -->
          <div class="meta-info" v-if="timeRange || dataSource">
            <span v-if="timeRange">查询时间：{{ timeRange }}</span>
            <span v-if="dataSource">数据来源：{{ dataSource }}</span>
            <span v-if="dataStatusText">{{ dataStatusText }}</span>
          </div>

          <!-- 核心结论 -->
          <div class="conclusion" v-if="coreConclusion">
            <div class="conclusion-title">重要提示</div>
            <div class="conclusion-content">{{ coreConclusion }}</div>
          </div>

          <!-- 核心数据表格 -->
          <div class="data-table-wrapper" v-if="resultData.length">
            <table class="data-table">
              <thead>
                <tr>
                  <th v-for="col in columns" :key="col.prop">{{ col.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in resultData" :key="idx">
                  <td v-for="col in columns" :key="col.prop" :class="{ abnormal: isAbnormalCell(row[col.prop]) }">
                    {{ formatCellValue(row[col.prop], col) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 你可能还会问 -->
          <div class="related-questions" v-if="suggestions.length">
            <div class="related-questions-title">你可能还会问</div>
            <a
              v-for="s in suggestions"
              :key="s"
              href="javascript:void(0)"
              @click="$emit('select-suggestion', s, msg)"
            >{{ s }}</a>
          </div>

          <!-- 底部操作栏 -->
          <div class="action-bar">
            <button class="doubao-icon-btn" title="复制" @click="handleCopy">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="重新生成" @click="$emit('retry')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"></path>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="点赞" @click="$emit('feedback', 1)" :class="{ active: userFeedback === 1 }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="点踩" @click="$emit('feedback', -1)" :class="{ active: userFeedback === -1 }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="分享" @click="$emit('share')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="更多" @click="toggleMoreMenu" :class="{ active: showMoreMenu }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="19" cy="12" r="1"></circle>
                <circle cx="5" cy="12" r="1"></circle>
              </svg>
            </button>

            <!-- 更多下拉菜单 -->
            <div class="more-menu" :class="{ show: showMoreMenu }">
              <div class="more-menu-item" @click="handleExportExcel">导出Excel</div>
              <div class="more-menu-item" @click="$emit('toggle-thinking'); showMoreMenu = false">查看分析过程</div>
              <div class="more-menu-divider"></div>
              <div class="more-menu-item" @click="handleCopyMarkdown">复制为Markdown</div>
              <div class="more-menu-item" @click="handleSaveImage">保存为图片</div>
            </div>
          </div>
        </div>
      </template>

      <!-- 类型 B：极简一句话 + 补充信息 -->
      <template v-else-if="queryType === 'B'">
        <div class="assistant-document">
          <div class="type-b-content">
            <div class="type-b-answer" v-html="formattedAnswer"></div>

            <!-- 补充信息 -->
            <div class="supplement-list" v-if="supplementaryInfo.length">
              <div v-for="item in supplementaryInfo" :key="item.label" class="supplement-item">
                <span class="supplement-label">{{ item.label }}</span>
                <span class="supplement-value">
                  {{ item.value }}
                  <span v-if="item.trend" :class="item.trend.startsWith('+') ? 'trend-up' : 'trend-down'">
                    {{ item.trend }}
                  </span>
                </span>
              </div>
            </div>
          </div>

          <!-- 建议问题 -->
          <div class="related-questions" v-if="suggestions.length">
            <div class="related-questions-title">你可能还会问</div>
            <a
              v-for="s in suggestions"
              :key="s"
              href="javascript:void(0)"
              @click="$emit('select-suggestion', s, msg)"
            >{{ s }}</a>
          </div>

          <!-- 底部操作栏 -->
          <div class="action-bar">
            <button class="doubao-icon-btn" title="复制" @click="handleCopy">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="重新生成" @click="$emit('retry')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"></path>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="点赞" @click="$emit('feedback', 1)" :class="{ active: userFeedback === 1 }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="点踩" @click="$emit('feedback', -1)" :class="{ active: userFeedback === -1 }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
              </svg>
            </button>
            <button class="doubao-icon-btn" title="分享" @click="$emit('share')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
            </button>
          </div>
        </div>
      </template>

    </template>

    <!-- 空状态 -->
    <div v-if="!loading && !hasContent" class="empty-state">
      <p>暂无数据</p>
      <div class="empty-reasons">
        <p>可能原因：</p>
        <ul>
          <li>所选时间范围内没有销售记录</li>
          <li>数据尚未同步完成（通常延迟15分钟）</li>
        </ul>
      </div>
      <div class="empty-actions">
        <el-button size="small" @click="$emit('retry')">刷新重试</el-button>
        <el-button size="small" @click="$emit('view-alternative')">查看昨天的数据</el-button>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-if="error" class="error-state">
      <p>查询失败，请稍后重试</p>
      <p class="error-detail">错误信息：{{ error }}</p>
      <div class="empty-actions">
        <el-button size="small" @click="$emit('retry')">重试</el-button>
        <el-button size="small" @click="$emit('contact-support')">联系技术支持</el-button>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  msg: {
    content?: string
    resultData?: any[]
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
  mergeView?: boolean
}>()

const emit = defineEmits<{
  'select-suggestion': [item: string, contextMsg?: any]
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

const showMoreMenu = ref(false)

function toggleMoreMenu() {
  showMoreMenu.value = !showMoreMenu.value
}

// 点击其他地方关闭菜单
if (typeof document !== 'undefined') {
  document.addEventListener('click', () => {
    showMoreMenu.value = false
  })
}

// ========== 查询类型判断 ==========
function classifyQuery(msg: any): 'A' | 'B' | 'C' | 'A_SIMPLE' {
  if (msg.force_query_type) return msg.force_query_type

  const { intent, resultData, content } = msg
  const row = resultData?.[0]
  const colCount = row ? Object.keys(row).length : 0

  if (
    intent === 'query_ranking' ||
    intent === 'query_comparison' ||
    (resultData?.length > 3 && colCount > 3)
  ) {
    return 'A'
  }

  const analysisKeywords = ['为什么', '原因', '分析', '趋势', '预测', '怎么回事', '下滑', '增长', '波动']
  const isAnalysisIntent =
    intent === 'query_anomaly' ||
    analysisKeywords.some((k: string) => content?.includes(k))

  if (isAnalysisIntent) {
    return 'C'
  }

  if (resultData?.length > 3 && colCount <= 3) {
    return 'A_SIMPLE'
  }

  return 'B'
}

const queryType = computed(() => classifyQuery(props.msg))

// ========== 数据解析 ==========
const dataSource = computed(() => '指标系统')

const timeRange = computed(() => {
  const time = props.msg.mql?.time
  if (time?.start && time?.end) {
    return `${time.start} ~ ${time.end}`
  }
  return ''
})

const dataStatusText = computed(() => {
  const data = props.msg.resultData
  if (!data || data.length === 0) return '数据为空'
  return `包含${data.length}条记录`
})

const resultData = computed(() => {
  return props.msg.resultData || []
})

const coreConclusion = computed(() => {
  if (props.msg.analysis?.summary) {
    return props.msg.analysis.summary
  }
  const content = props.msg.content || ''
  const sentences = content.split(/[。.!?]/).filter(Boolean)
  return sentences[0] || content
})

const supplementaryInfo = computed(() => {
  return props.msg.supplementary_info || []
})

const suggestions = computed(() => {
  return props.msg.suggest || props.msg.suggestions || []
})

const hasContent = computed(() => {
  return props.msg.content || resultData.value.length > 0
})

// ========== 表格列定义 ==========
const columns = computed(() => {
  if (!resultData.value.length) return []

  const row = resultData.value[0]
  const keys = Object.keys(row)
  const dateKeys = ['FDATE', 'FDATE_END', 'FDATE_START', 'MONTHS', '日期', '月份', '年份', '时间']

  return keys.map((key: string) => {
    const isDateCol = dateKeys.includes(key) || /date|时间|日期|月份|年份/i.test(key)
    const isNumeric = !isDateCol && (typeof row[key] === 'number' ||
      (typeof row[key] === 'string' && /^-?[\d,]+\.?\d*$/.test(row[key])))

    return {
      prop: key,
      label: key,
      isNumeric
    }
  })
})

// ========== 格式化 ==========
function formatCellValue(value: any, col: any): string {
  if (value === null || value === undefined) return '-'
  if (!col.isNumeric) return String(value)

  const num = typeof value === 'string'
    ? parseFloat(value.replace(/,/g, ''))
    : value

  if (isNaN(num)) return String(value)

  const abs = Math.abs(num)
  if (abs >= 100000000) {
    return (num / 100000000).toFixed(2) + '亿'
  } else if (abs >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  } else if (Number.isInteger(num)) {
    return num.toLocaleString('zh-CN')
  } else {
    return num.toFixed(2)
  }
}

function isAbnormalCell(value: any): boolean {
  if (value === null || value === undefined) return false
  if (typeof value === 'string' && (value.includes('缺失') || value.includes('异常') || value.includes('0') || value === '-')) {
    return true
  }
  if (typeof value === 'number' && value === 0) return true
  return false
}

const formattedAnswer = computed(() => {
  const content = props.msg.content || ''
  return content.replace(/(\d+\.?\d*)(万|亿|元|%|件|个)?/g, (match) => {
    return `<strong>${match}</strong>`
  })
})

// ========== 交互操作 ==========
function handleCopy() {
  if (!resultData.value.length) {
    navigator.clipboard.writeText(props.msg.content || '').then(() => {
      ElMessage({ message: '复制成功', type: 'success', duration: 2000 })
    })
    return
  }

  const headers = columns.value.map(c => c.label)
  const rows = resultData.value.map(row =>
    columns.value.map(c => row[c.prop])
  )

  const content = [headers.join('\t'), ...rows.map(r => r.join('\t'))].join('\n')
  navigator.clipboard.writeText(content).then(() => {
    ElMessage({ message: '复制成功', type: 'success', duration: 2000 })
  })
}

function handleCopyMarkdown() {
  showMoreMenu.value = false
  if (!resultData.value.length) return

  const headers = columns.value.map(c => c.label)
  const rows = resultData.value.map(row =>
    columns.value.map(c => row[c.prop])
  )

  const md = [
    '|' + headers.join('|') + '|',
    '|' + headers.map(() => '---').join('|') + '|',
    ...rows.map(r => '|' + r.join('|') + '|')
  ].join('\n')

  navigator.clipboard.writeText(md).then(() => {
    ElMessage({ message: '复制成功', type: 'success', duration: 2000 })
  })
}

function handleExportExcel() {
  showMoreMenu.value = false
  emit('export')
}

function handleSaveImage() {
  showMoreMenu.value = false
  ElMessage({ message: '功能开发中', type: 'info', duration: 2000 })
}
</script>

<style scoped>
.document-message {
  width: 100%;
  background: transparent;
  padding: 0 24px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: #1f2329;
  line-height: 1.6;
}

/* 元信息栏 */
.meta-info {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 16px;
  display: flex;
  gap: 16px;
}

/* 结论卡片 */
.conclusion {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 16px 18px;
  margin-bottom: 20px;
}

.conclusion-title {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.conclusion-content {
  font-size: 15px;
  color: #374151;
  line-height: 1.7;
  font-weight: 500;
}

/* 数据表格 */
.data-table-wrapper {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 4px;
  margin-bottom: 24px;
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.data-table th {
  background: #f1f5f9;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  text-align: left;
  padding: 10px 16px;
  white-space: nowrap;
  border-bottom: 1px solid #e2e8f0;
}

.data-table td {
  padding: 10px 16px;
  color: #1f2329;
  border-bottom: 1px solid #f1f5f9;
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.data-table tbody tr:nth-child(even) {
  background: rgba(241, 245, 249, 0.5);
}

.data-table .abnormal {
  font-weight: 600;
  color: #dc2626;
}

/* 相关问题 */
.related-questions {
  margin-bottom: 24px;
}

.related-questions-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 10px;
}

.related-questions a {
  display: inline-block;
  padding: 6px 14px;
  font-size: 13px;
  color: #334155;
  background: #ffffff;
  border: 1px solid #dbe4f0;
  border-radius: 999px;
  text-decoration: none;
  margin-right: 8px;
  line-height: 1.3;
  cursor: pointer;
  transition: all 0.18s ease;
}

.related-questions a:hover {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
  text-decoration: none;
}

/* 底部操作栏 */
.action-bar {
  display: flex;
  align-items: center;
  position: relative;
  padding-top: 16px;
  border-top: 1px solid #e5e6eb;
}

.doubao-icon-btn {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #86909c;
  cursor: pointer;
  margin-right: 8px;
  transition: background-color 0.15s ease;
}

.doubao-icon-btn:last-child {
  margin-right: 0;
}

.doubao-icon-btn:hover {
  background-color: #f2f3f5;
}

.doubao-icon-btn:active {
  background-color: #e5e6eb;
}

.doubao-icon-btn.active {
  background-color: #e5e6eb;
}

.doubao-icon-btn svg {
  width: 20px;
  height: 20px;
  stroke-width: 2px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* 更多菜单 */
.more-menu {
  position: absolute;
  bottom: 40px;
  right: 0;
  background-color: #ffffff;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  min-width: 160px;
  z-index: 1000;
  display: none;
}

.more-menu.show {
  display: block;
}

.more-menu-item {
  padding: 10px 16px;
  font-size: 14px;
  color: #1f2329;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.more-menu-item:first-child {
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.more-menu-item:last-child {
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
}

.more-menu-item:hover {
  background-color: #f2f3f5;
}

.more-menu-divider {
  height: 1px;
  background-color: #f2f3f5;
  margin: 4px 0;
}

/* 类型B */
.type-b-content {
  margin-bottom: 20px;
}

.type-b-answer {
  font-size: 16px;
  line-height: 1.7;
  color: #0f172a;
  font-weight: 500;
  margin-bottom: 16px;
}

.type-b-answer :deep(strong) {
  font-weight: 600;
}

.supplement-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.supplement-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
}

.supplement-label {
  color: #64748b;
  font-size: 12px;
}

.supplement-value {
  color: #0f172a;
  font-weight: 500;
}

.trend-up {
  color: #10B981;
  margin-left: 4px;
}

.trend-down {
  color: #86909c;
  margin-left: 4px;
}

/* 空状态 */
.empty-state,
.error-state {
  text-align: center;
  padding: 24px;
  color: #4e5969;
}

.empty-reasons {
  text-align: left;
  margin: 16px 0;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
  font-size: 14px;
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
  color: #86909c;
  margin-top: 8px;
}

.skeleton-content {
  padding: 12px;
}
</style>
