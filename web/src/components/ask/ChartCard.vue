<template>
  <div class="chart-card" :class="{ 'has-error': error }">
    <div class="chart-header" v-if="title || $slots.header">
      <slot name="header">
        <span class="chart-title">{{ title }}</span>
      </slot>
      <div class="chart-actions">
        <button v-if="interpretation" class="action-btn" @click="showInterpretation = !showInterpretation" :title="showInterpretation ? '收起解读' : '数据解读'">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1C3.7 1 1 3.7 1 7C1 10.3 3.7 13 7 13C8.5 13 9.9 12.4 11 11.4C11.3 11.1 11.7 11 12 11.2C12.3 11.4 12.4 11.8 12.2 12.1C11.9 12.6 11.5 13 11 13.3C9.6 14.2 7.9 14.7 6.2 14.7C3.5 14.7 1.2 13.2 0 11C0.8 11 1.5 10.5 2.3 10.5C3.2 10.5 3.9 11.2 3.9 12.1C3.9 13 3.2 13.7 2.3 13.7C2 13.7 1.7 13.6 1.5 13.4C2.4 12.5 3 11.3 3 10C3 7 1 1 1 1" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" transform="translate(1, -1) scale(0.55)"/>
            <path d="M5 6H9M5 8H7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
          </svg>
        </button>
        <button class="action-btn" @click="toggleExpand" :title="expanded ? '收起' : '放大'">
          <svg v-if="!expanded" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 5V2H5M9 2H12V5M12 9V12H9M5 12H2V9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M5 2H2V5M9 2H12V5M12 9V12H9M5 12H2V9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>

    <div v-if="error" class="chart-error">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="#EF4444" stroke-width="1.5"/>
        <path d="M12 7V12M12 15V16" stroke="#EF4444" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <span>{{ error }}</span>
    </div>

    <!-- 数字卡片模式 -->
    <div v-else-if="chartType === 'card' && chartOptions" class="metric-card">
      <div class="metric-value">{{ formatMetricValue(chartOptions.value) }}</div>
      <div class="metric-label">{{ chartOptions.label }}</div>
    </div>

    <!-- MoM 对比卡片模式 -->
    <div v-else-if="chartType === 'comparison' && chartOptions" class="comparison-card">
      <div class="comparison-header">
        <span class="comparison-title">{{ props.metricName || '环比对比' }}</span>
        <span v-if="chartOptions.trendText" class="comparison-trend" :class="chartOptions.trendClass">
          {{ chartOptions.trendText }}
        </span>
      </div>
      <div class="comparison-values">
        <div class="comparison-item">
          <div class="comparison-label">{{ props.periodInfo?.comparePeriod || chartOptions.comparePeriod || '上期' }}</div>
          <div class="comparison-value">{{ chartOptions.compareVal }}</div>
        </div>
        <div class="comparison-arrow">→</div>
        <div class="comparison-item">
          <div class="comparison-label">{{ props.periodInfo?.currentPeriod || chartOptions.currentPeriod || '当期' }}</div>
          <div class="comparison-value">{{ chartOptions.currentVal }}</div>
        </div>
        <div class="comparison-item change">
          <div class="comparison-label">变化率</div>
          <div class="comparison-value" :class="chartOptions.trendClass">
            <span v-if="chartOptions.trend === '增长'">↑</span>
            <span v-else-if="chartOptions.trend === '下降'">↓</span>
            {{ chartOptions.changeRate }}
          </div>
        </div>
      </div>
    </div>

    <!-- 多指标表格模式 -->
    <div v-else-if="chartType === 'table' && props.data && props.data.length > 0" class="metric-table">
      <!-- 时间范围标签 -->
      <div v-if="timeRangeLabel" class="time-range-label">{{ timeRangeLabel }}</div>
      <table class="data-table">
        <thead>
          <tr>
            <th
              v-for="(header, idx) in tableHeaders"
              :key="tableKeys[idx]"
              @click="handleSort(tableKeys[idx])"
              :class="{ sortable: true, sorted: sortKey === tableKeys[idx] }"
            >
              {{ header }}
              <span v-if="sortKey === tableKeys[idx]" class="sort-icon">
                {{ sortOrder === 'asc' ? '↑' : '↓' }}
              </span>
              <span v-else class="sort-icon default">↕</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in sortedPaginatedData" :key="idx">
            <td v-for="(key, colIdx) in tableKeys" :key="key" :class="{ numeric: isNumericColumn(key, row[key]) }">
              <span v-if="isSkuColumn(key)" class="sku-link" @click="openProductDetail(row[key])">{{ formatTableCell(key, row[key], colIdx) }}</span>
              <template v-else>{{ formatTableCell(key, row[key], colIdx) }}</template>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="table-pagination" v-if="props.data.length > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="props.data.length"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <div v-else ref="chartContainer" class="chart-container" :style="{ height: height + 'px', width: '100%' }"></div>

    <!-- 数据解读 -->
    <div v-if="interpretation && showInterpretation" class="chart-interpretation">
      <div class="interpretation-header">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M7 1C3.7 1 1 3.7 1 7C1 10.3 3.7 13 7 13C8.5 13 9.9 12.4 11 11.4C11.3 11.1 11.7 11 12 11.2C12.3 11.4 12.4 11.8 12.2 12.1C11.9 12.6 11.5 13 11 13.3C9.6 14.2 7.9 14.7 6.2 14.7C3.5 14.7 1.2 13.2 0 11C0.8 11 1.5 10.5 2.3 10.5C3.2 10.5 3.9 11.2 3.9 12.1C3.9 13 3.2 13.7 2.3 13.7C2 13.7 1.7 13.6 1.5 13.4C2.4 12.5 3 11.3 3 10C3 7 1 1 1 1" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" transform="translate(1, -1) scale(0.55)"/>
          <path d="M5 6H9M5 8H7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
        <span>数据解读</span>
      </div>
      <div class="interpretation-content">{{ interpretation }}</div>
    </div>

    <!-- Fullscreen Overlay -->
    <teleport to="body">
      <transition name="fade">
        <div v-if="expanded" class="chart-fullscreen" @click.self="toggleExpand">
          <div class="fullscreen-content">
            <div class="fullscreen-header">
              <span class="fullscreen-title">{{ title }}</span>
              <button class="close-btn" @click="toggleExpand">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
            <div ref="fullscreenChartContainer" class="fullscreen-chart"></div>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- SKU 产品详情弹窗 -->
    <el-dialog
      v-model="productDialogVisible"
      title="商品详情"
      width="400px"
      :append-to-body="true"
      destroy-on-close
    >
      <ProductCard v-if="selectedSku" :sku="selectedSku" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import ProductCard from './ProductCard.vue'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  type: {
    type: String,
    default: 'auto', // auto, line, bar, pie
    validator: (v) => ['auto', 'line', 'bar', 'pie', 'table'].includes(v)
  },
  title: {
    type: String,
    default: ''
  },
  height: {
    type: Number,
    default: 280
  },
  xAxisKey: {
    type: String,
    default: ''
  },
  yAxisKey: {
    type: String,
    default: ''
  },
  seriesConfig: {
    type: Array,
    default: () => []
  },
  truncationLength: {
    type: Number,
    default: 10
  },
  interpretation: {
    type: String,
    default: ''
  },
  metricName: {
    type: String,
    default: ''
  },
  metricNames: {
    type: Array,
    default: () => []
  },
  metricUnit: {
    type: String,
    default: ''
  },
  timeStart: {
    type: String,
    default: ''
  },
  timeEnd: {
    type: String,
    default: ''
  },
  periodInfo: {
    type: Object,
    default: () => ({ currentPeriod: '', comparePeriod: '' })
  },
  columns: {
    type: Array,
    default: () => []
  }
})

const chartContainer = ref(null)
const fullscreenChartContainer = ref(null)
const expanded = ref(false)
const error = ref('')
const showInterpretation = ref(false)

let chartInstance = null
let fullscreenChartInstance = null

// 分页
const currentPage = ref(1)
const pageSize = ref(10)

// 排序
const sortKey = ref('')
const sortOrder = ref('') // 'asc' | 'desc' | ''

const productDialogVisible = ref(false)
const selectedSku = ref('')

function openProductDetail(sku) {
  selectedSku.value = String(sku)
  productDialogVisible.value = true
}

// 排序后且分页的数据
const sortedPaginatedData = computed(() => {
  if (!props.data || props.data.length === 0) return []
  let data = [...props.data]
  // 排序
  if (sortKey.value) {
    const key = sortKey.value
    const order = sortOrder.value
    data.sort((a, b) => {
      const aVal = a[key]
      const bVal = b[key]
      if (aVal === null || aVal === undefined) return 1
      if (bVal === null || bVal === undefined) return -1
      // 尝试将值转换为数值进行比较（处理 "40084806.65" 这样的字符串数字）
      const aNum = typeof aVal === 'number' ? aVal : (typeof aVal === 'string' && !isNaN(parseFloat(aVal)) ? parseFloat(aVal) : null)
      const bNum = typeof bVal === 'number' ? bVal : (typeof bVal === 'string' && !isNaN(parseFloat(bVal)) ? parseFloat(bVal) : null)
      if (aNum !== null && bNum !== null) {
        return order === 'asc' ? aNum - bNum : bNum - aNum
      }
      const aStr = String(aVal)
      const bStr = String(bVal)
      return order === 'asc' ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr)
    })
  }
  // 分页
  const start = (currentPage.value - 1) * pageSize.value
  return data.slice(start, start + pageSize.value)
})

function handleSort(key) {
  if (sortKey.value === key) {
    if (sortOrder.value === 'asc') {
      sortOrder.value = 'desc'
    } else if (sortOrder.value === 'desc') {
      sortOrder.value = ''
      sortKey.value = ''
    } else {
      sortOrder.value = 'asc'
    }
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
  currentPage.value = 1
}

function handlePageChange(page) {
  currentPage.value = page
}

function handleSizeChange() {
  currentPage.value = 1
}

// 时间范围标签（统一格式：YYYY-MM-DD ~ YYYY-MM-DD）
const timeRangeLabel = computed(() => {
  // 优先使用 props.timeStart 和 props.timeEnd（从 MQL 传递的日期范围）
  if (props.timeStart && props.timeEnd) {
    if (props.timeStart === props.timeEnd) {
      return `日期范围：${props.timeStart}`
    }
    return `日期范围：${props.timeStart} ~ ${props.timeEnd}`
  }

  if (!props.data || props.data.length === 0) return ''
  const firstRow = props.data[0]
  const keys = Object.keys(firstRow)

  // 兜底：从 FDATE 列提取日期范围
  if (keys.includes('FDATE')) {
    const dates = props.data.map(r => r.FDATE).filter(d => d && typeof d === 'string' && d.includes('-'))
    if (dates.length > 0) {
      const sortedDates = [...dates].sort()
      const min = sortedDates[0]
      const max = sortedDates[sortedDates.length - 1]
      if (min === max) {
        return `日期范围：${min}`
      }
      return `日期范围：${min} ~ ${max}`
    }
  }

  return ''
})

// 多指标表格的列 keys（排除时间维度列）
// 优先使用 columns 数组（来自后端的列元数据，顺序与 SQL SELECT 一致）
// 如果没有 columns，则 fallback 到 Object.keys（不保证顺序）
const tableKeys = computed(() => {
  // 优先使用后端返回的 columns 元数据
  if (props.columns && props.columns.length > 0) {
    // 过滤掉日期维度列（保留 MONTHS，月份是用户可读的维度列）
    return props.columns.filter(k => k !== 'FDATE' && k !== 'FDATE_START' && k !== 'FDATE_END')
  }
  // Fallback: 从数据对象提取 keys（不保证顺序）
  if (!props.data || props.data.length === 0) return []
  const keys = Object.keys(props.data[0])
  // 过滤掉日期维度列（保留 MONTHS，月份是用户可读的维度列）
  const filteredKeys = keys.filter(k => k !== 'FDATE' && k !== 'FDATE_START' && k !== 'FDATE_END')
  return filteredKeys
})

// 判断是否是维度列（用于 tableKeys 排序）
function isDimensionColumn(key) {
  const dimColumnPatterns = [
    'SKU', 'ASIN', 'FSITE', 'FSITECODE', 'SHOP', 'STORE', 'BRAND',
    'PLATFORM', 'COUNTRY', 'CITY', 'REGION', 'CHANNEL', 'CAMPAIGN',
    'PRODUCT', 'CATEGORY', 'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4',
  ]
  const upperKey = key.toUpperCase()
  return dimColumnPatterns.some(pattern => upperKey.includes(pattern))
}

// 字段英文名到中文的映射（用于图表 tooltip 显示）
const FIELD_NAME_MAP = {
  'ORDERED_PRODUCTSALES': '销售额',
  'REFUND_QTY': '退款数量',
  'REFUND_AMOUNT': '退款金额',
  'VISITORS': '访客数',
  'ORDERS': '订单数',
  'UNITS': '销售单元',
  'PROFIT': '利润',
  'GMV': 'GMV',
  'CR': '转化率',
  'CVR': '转化率',
  'CTR': '点击率',
  'ACP': '平均客单价',
  'AOV': '平均订单价值',
}

// 维度列类型到中文名的映射
const DIM_TYPE_NAME_MAP = {
  'GROUP_1': '一级品类',
  'GROUP_2': '二级品类',
  'GROUP_3': '三级品类',
  'GROUP_4': '四级品类',
  'FSITE': '站点',
  'PLATFORM': '平台',
  'REGION': '地区',
  'FDATE': '日期',
  'MONTHS': '月份',
  'SKU': 'SKU',
  'ASIN': 'ASIN',
}

// 判断是否是数值列（排除时间维度列 MONTHS/FDATE/FDATE_START/FDATE_END 及类似列）
function isNumericColumn(key, val) {
  // 已知维度列（不是指标列）
  if (['MONTHS', 'FDATE', 'FDATE_START', 'FDATE_END', 'SKU', 'ASIN', 'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4', 'BRAND', 'PLATFORM', 'SHOP', 'FSITE', 'FSITECODE'].includes(key)) return false
  if (val === null || val === '') return false
  // SKU 格式：5位数字 + 0-2个字母（如 12345、12345AB），不是数值
  if (typeof val === 'string' && /^[0-9]+[A-Za-z]{0,2}$/.test(val)) return false
  // 日期格式字符串（如 "2026-04-01"）不是数值
  if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}/.test(val)) return false
  // 对于字符串：parseFloat 后必须等于自身（排除 "2026-04-01" → 2026, "3430.94万" → 3430.94）
  if (typeof val === 'string') {
    const parsed = parseFloat(val)
    if (isNaN(parsed)) return false
    // 纯数值字符串（如 "123", "3430.94"）才是数值
    // 也接受带百分号的对比列值（如 "-35.43%", "+12.5%"）
    if (/^-?\d+(\.\d+)?%?$/.test(val)) return true
    return false
  }
  return typeof val === 'number'
}

function isSkuColumn(key) {
  return key === 'SKU'
}

// 已知维度列名（用于过滤 metricNames 中的维度名）
const KNOWN_DIM_COLUMNS = new Set([
  'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4',
  'FDATE', 'FDATE_START', 'FDATE_END', 'MONTHS',
  'SKU', 'ASIN', 'FSITE', 'FSITECODE', 'SHOP', 'STORE', 'BRAND',
  'PLATFORM', 'COUNTRY', 'CITY', 'REGION', 'CHANNEL', 'CAMPAIGN', 'PRODUCT', 'CATEGORY'
])

// 多指标表格的列 header（中文名）
// 对比查询列名后缀映射
const COMP_SUFFIX_MAP = {
  '_raw': '',
  '_mom_val': '(上期)',
  '_mom_change': '(环比)',
  '_yoy_val': '(同比上期)',
  '_yoy_change': '(同比)',
}

// 解析对比查询列名：销售额_mom_change → { base: '销售额', label: '(环比)' }
function parseCompColumn(key) {
  for (const [suffix, label] of Object.entries(COMP_SUFFIX_MAP)) {
    if (key.endsWith(suffix)) {
      return { base: key.slice(0, -suffix.length), label }
    }
  }
  return null
}

// 保持与 tableKeys 完全一致的顺序（按 result_data 原始 key 顺序）
const tableHeaders = computed(() => {
  if (!props.data || props.data.length === 0) return []
  const keys = Object.keys(props.data[0])
  // 过滤出数值列（metric 对应的列，排除 MONTHS/FDATE）
  const numericKeys = keys.filter(k => isNumericColumn(k, props.data[0][k]))
  // 过滤掉时间维度列（保持原始 key 顺序，保留 MONTHS）
  const filteredKeys = keys.filter(k => k !== 'FDATE' && k !== 'FDATE_START' && k !== 'FDATE_END')

  // 构建 key → header 映射（与 tableKeys 顺序完全一致）
  // metricNames 负责映射数值列的中文名，其他列直接用 key 或中文映射
  const metricNames = props.metricNames || []
  const metricNameSet = new Set(metricNames)

  return filteredKeys.map(k => {
    // 数值列：优先用 metricNames 中对应的中文名
    if (numericKeys.includes(k)) {
      // 精确匹配优先：key === metricNames 中的某一项
      const exactIdx = metricNames.findIndex(name => name === k)
      if (exactIdx >= 0) {
        return k
      }
      // 子串匹配：metricNames 中某一项包含 key（如 "毛利率" 包含 "毛利"）
      const foundIdx = metricNames.findIndex(name => name.includes(k))
      if (foundIdx >= 0) {
        return metricNames[foundIdx]
      }
      // 对比查询列名：销售额_mom_change → 销售额(环比)
      const comp = parseCompColumn(k)
      if (comp) {
        const baseName = metricNames.find(n => n.includes(comp.base) || comp.base.includes(n)) || comp.base
        return `${baseName}${comp.label}`
      }
      // fallback：用 FIELD_NAME_MAP 映射
      return FIELD_NAME_MAP[k] || k
    }
    // 非数值列（维度列）：中文映射
    // 对比查询列名可能因值为 null/百分比字符串被判为非数值列
    const comp = parseCompColumn(k)
    if (comp) {
      const baseName = metricNames.find(n => n.includes(comp.base) || comp.base.includes(n)) || comp.base
      return `${baseName}${comp.label}`
    }
    if (k === 'GROUP_2') return '二级品类'
    if (k === 'GROUP_1') return '一级品类'
    if (k === 'GROUP_3') return '三级品类'
    if (k === 'GROUP_4') return '四级品类'
    if (k === 'FDATE') return '日期'
    if (k === 'MONTHS') return '月份'
    // 使用 DIM_TYPE_NAME_MAP 映射维度列
    if (DIM_TYPE_NAME_MAP[k]) return DIM_TYPE_NAME_MAP[k]
    return k
  })
})

// 格式化表格单元格（根据指标名决定格式化方式）
function formatTableCell(key, val, colIdx) {
  if (val === null || val === undefined) return '-'

  // 已知维度列（不是指标列），直接返回原始值
  const dimKeys = new Set(['MONTHS', 'FDATE', 'FDATE_START', 'FDATE_END', 'SKU', 'ASIN', 'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4', 'BRAND', 'PLATFORM', 'SHOP', 'FSITE', 'FSITECODE', '月份', '月', '年月', '日期', '年份', '时间', '变化标签'])
  if (dimKeys.has(key)) {
    // MONTHS 列：整数如 202601 → "202601月"；字符串如 "2026-01" → 直接返回
    if (key === 'MONTHS') {
      const num = typeof val === 'number' ? val : parseFloat(val)
      if (!isNaN(num)) return num + '月'
      return val + '月'
    }
    // 月份列（中文）等：直接返回原始值，不要做数字解析
    return val
  }

  // 防御性处理：日期格式字符串（YYYY-MM-DD）不应被 parseFloat 解析为年份
  if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}/.test(val)) {
    return val
  }

  // 已格式化的百分比字符串（如 "+8.9%", "-91.2%"）保留原值，避免丢失符号和 %
  if (typeof val === 'string' && /^[+-]?\d+(\.\d+)?%$/.test(val)) {
    return val
  }

  // 判断该列是否使用千分位格式（销量类指标）
  const useCommaFormat = (() => {
    if (!props.metricNames || props.metricNames.length === 0) return false
    const keys = Object.keys(props.data?.[0] || {})
    // 维度列
    const dimKeys = new Set(['MONTHS', 'FDATE', 'SKU', 'ASIN', 'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4', 'BRAND', 'PLATFORM', 'SHOP', 'FSITE', 'FSITECODE'])
    // 计算 colIdx 之前有多少个维度列，确定该列对应 metricNames 的第几项
    let metricColIdx = 0
    for (let i = 0; i < colIdx; i++) {
      if (!dimKeys.has(keys[i])) metricColIdx++
    }
    if (metricColIdx < 0 || metricColIdx >= props.metricNames.length) return false
    const metricName = props.metricNames[metricColIdx]
    return metricName?.includes('销量')
  })()

  // 判断是否使用百分比格式（率类指标）
  const usePercentFormat = (() => {
    // 列名包含"占比"/"比率"→ 百分比格式
    if (/占比|比率|比例/.test(key)) return true
    if (!props.metricNames || props.metricNames.length === 0) return false
    const metricNames = props.metricNames
    // 精确匹配：key === metricNames 中的某一项
    if (metricNames.includes(key)) return key.includes('率')
    // key 可能带后缀（如"销售毛利率当前值"），检查 metricNames 是否有某项是 key 的前缀
    const matchedMetric = metricNames.find(name => key.startsWith(name))
    if (matchedMetric) return matchedMetric.includes('率')
    // 子串匹配：metricNames 中某一项包含 key（如 "毛利率" 包含 "毛利"）
    const foundName = metricNames.find(name => name.includes(key))
    return foundName ? foundName.includes('率') : false
  })()

  // 同比/环比变化列：值已经是百分比字符串（如 "+3836.557346109200%"），截断小数
  if (key.endsWith('变化')) {
    if (typeof val === 'string' && val.includes('%')) {
      const numMatch = val.match(/([+-]?\d+\.?\d*)/)
      if (numMatch) {
        const num = parseFloat(numMatch[1])
        const sign = num >= 0 ? '+' : ''
        return `${sign}${num.toFixed(1)}%`
      }
    }
    return val
  }

  const rawNum = typeof val === 'number' ? val : parseFloat(String(val).replace(/,/g, ''))
  if (isNaN(rawNum)) return val

  // 指标单位感知格式化
  const unit = props.metricUnit || ''
  if (unit === '%' || usePercentFormat) {
    // 率类指标：显示为百分比
    const pct = rawNum < 1 ? rawNum * 100 : rawNum
    return pct.toFixed(2) + '%'
  }
  if (unit === '$' || unit === '¥' || unit === '￥' || unit === '€') {
    return unit + formatChartValue(rawNum)
  }

  if (useCommaFormat) {
    // 销量：千分位逗号
    return rawNum.toLocaleString()
  }
  // 其他指标：万/亿
  return formatChartValue(rawNum)
}

// Determine chart type based on data structure
const chartType = computed(() => {
  if (props.type !== 'auto') return props.type

  console.log('[DEBUG chartType] data length:', props.data?.length, 'keys:', Object.keys(props.data?.[0] || {}), 'metricName:', props.metricName)

  if (!props.data || props.data.length === 0) return 'table'

  // MoM 对比数据检测：同时有 current_val, compare_val, change_rate
  if (props.data.length === 1) {
    const row = props.data[0]
    if (row && 'current_val' in row && 'compare_val' in row && 'change_rate' in row) {
      return 'comparison'
    }
  }

  // 单条汇总数据，显示为数字卡片
  if (props.data.length === 1) {
    const keys = Object.keys(props.data[0])
    // 检查是否存在 GROUP BY 维度列（GROUP_1/2/3/4 等）
    const hasDimensionColumn = keys.some(k =>
      k.startsWith('GROUP_') || k === 'FSITE' || k === 'FSITECODE' ||
      k === 'BRAND' || k === 'PLATFORM' || k === 'REGION' || k === 'SKU' || k === 'ASIN'
    )
    const numericKeys = keys.filter(k => {
      const val = props.data[0][k]
      const isNum = typeof val === 'number' || !isNaN(parseFloat(val))
      return isNum
    })
    console.log('[DEBUG chartType] single row, numericKeys length:', numericKeys.length, 'hasDimensionColumn:', hasDimensionColumn)
    // 如果存在 GROUP BY 维度列，即使只有一个数值也显示为表格（维度名称不能丢失）
    if (hasDimensionColumn) {
      console.log('[DEBUG chartType] returning table because has GROUP BY dimension column')
      return 'table'
    }
    // 如果只有一个数值字段且无维度列，显示为数字卡片；多个数值字段显示为表格
    if (numericKeys.length === 1) {
      return 'card'
    } else if (numericKeys.length > 1) {
      console.log('[DEBUG chartType] returning table because numericKeys length > 1')
      return 'table'
    }
  }

  const keys = Object.keys(props.data[0])

  // 排除非指标列：FDATE系列、MONTHS、ASIN、SKU等分组维度列
  const excludeKeys = ['FDATE', 'FDATE_END', 'FDATE_START', 'MONTHS', 'ASIN', 'SKU', 'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4']
  const numericKeys = keys.filter(k => {
    if (excludeKeys.includes(k)) return false
    // 检查所有行，只要任意一行有有效数值就认为是数值列
    return props.data.some(row => {
      const val = row[k]
      if (val === null || val === '') return false
      // 排除已经是字符串日期格式的值
      if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}/.test(val)) return false
      return typeof val === 'number' || !isNaN(parseFloat(val))
    })
  })

  // 查找维度列（GROUP_X, REGION, PLATFORM, FSITE 等，含中文名）
  const dimChineseNames = new Set([
    '一级品类', '二级品类', '三级品类', '四级品类',
    '站点', '亚马逊站点', '店铺', '平台', '地区', '国家', '区域', '渠道',
    '品牌', 'SKU', 'ASIN', '广告类型', '广告组', '币种', '统计周期',
  ])
  const dimensionKeys = keys.filter(k =>
    k.startsWith('GROUP_') ||
    k === 'REGION' || k === 'PLATFORM' ||
    k === 'FSITE' || k === 'FCOUNTRY' ||
    k === 'FBRAND' || k === 'FPRODUCTLINE' ||
    dimChineseNames.has(k)
  )

  // 查找时间列（FDATE, MONTHS 等）
  const timeKeys = keys.filter(k =>
    k === 'FDATE' || k === 'FDATE_END' || k === 'FDATE_START' ||
    k === 'MONTHS' || k === '日期' || k === '月份' || k === '年份'
  )

  // 优先使用指定的 xAxisKey，如果没有则使用维度列
  const xAxisKey = props.xAxisKey || (dimensionKeys.length > 0 ? dimensionKeys[0] : keys[0])

  // 判断是否时间序列：如果 x 轴值是日期格式且没有分组维度，则是时间序列
  const isTimeSeries = props.data.some(row => {
    const val = row[xAxisKey]
    // 如果有 GROUP_X 等维度列，通常是分类数据，不是时间序列
    if (dimensionKeys.length > 0 && dimensionKeys.includes(xAxisKey)) {
      return false
    }
    return val && (val.includes('-') || val.includes('/') || !isNaN(Date.parse(val)))
  })

  // 多指标且有时间列时，返回 line（多系列折线图）
  const hasTimeColumn = timeKeys.length > 0

  console.log('[DEBUG chartType] keys:', keys, 'numericKeys:', numericKeys, 'dimensionKeys:', dimensionKeys, 'timeKeys:', timeKeys, 'xAxisKey:', xAxisKey, 'isTimeSeries:', isTimeSeries, 'hasTimeColumn:', hasTimeColumn)

  // 多维度数据不适合图表，用表格（维度过多时图表可读性差）
  if (dimensionKeys.length > 1) {
    return 'table'
  }

  // SKU 维度数据用表格（SKU 编码长，条形图可读性差，且需要点击查看产品详情）
  if (dimensionKeys.some(k => k === 'SKU')) {
    return 'table'
  }

  if (numericKeys.length === 1) {
    // 檢測是否是佔比/比率數據，優先顯示餅圖
    const metricName = props.metricName || ''
    const ratioKeywords = ['占比', '比例', '比率', '率']
    const isRatioMetric = ratioKeywords.some(k => metricName.includes(k))
    // 只有當 metricName 包含佔比關鍵詞時，才檢查值範圍
    // 否則金額類指標（如銷售毛利）即使有 0 值也不應顯示為餅圖
    const isPercentageRange = isRatioMetric && props.data.some(row => {
      const val = parseFloat(row[numericKeys[0]])
      return !isNaN(val) && val >= 0 && val <= 100
    })
    console.log('[DEBUG chartType] isRatioMetric:', isRatioMetric, 'isPercentageRange:', isPercentageRange)
    if (isRatioMetric || isPercentageRange) {
      console.log('[DEBUG chartType] returning pie')
      return 'pie'
    }
    return isTimeSeries ? 'line' : 'bar'
  } else if (numericKeys.length > 1) {
    // 多指标：有时间列时用折线图，否则用表格
    if (hasTimeColumn || isTimeSeries) {
      console.log('[DEBUG chartType] multi-metric with time, returning line')
      return 'line'
    }
    return 'table'
  }

  return 'table'
})

// Generate chart options based on data
const chartOptions = computed(() => {
  if (!props.data || props.data.length === 0) {
    return {}
  }

  const data = props.data
  const keys = Object.keys(data[0])

  // 单值卡片模式：直接提取，避免被 xKey 过滤
  if (chartType.value === 'card') {
    const numericKey = keys.find(k => {
      const val = data[0][k]
      return typeof val === 'number' || (typeof val === 'string' && !isNaN(parseFloat(val)))
    })
    if (numericKey) {
      return {
        type: 'card',
        value: data[0][numericKey],
        label: props.metricName || numericKey
      }
    }
  }

  // 排除非指标列：FDATE系列、MONTHS、ASIN、SKU等分组维度列
  const excludeKeys = ['FDATE', 'FDATE_END', 'FDATE_START', 'MONTHS', 'ASIN', 'SKU', 'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4']

  // 查找维度列（GROUP_X, REGION, PLATFORM, FSITE 等）
  const dimensionKeys = keys.filter(k =>
    k.startsWith('GROUP_') ||
    k === 'REGION' || k === 'PLATFORM' ||
    k === 'FSITE' || k === 'FCOUNTRY' ||
    k === 'FBRAND' || k === 'FPRODUCTLINE'
  )

  // 查找时间列
  const timeKeys = keys.filter(k =>
    k === 'FDATE' || k === 'FDATE_END' || k === 'FDATE_START' ||
    k === 'MONTHS' || k === '日期' || k === '月份' || k === '年份'
  )

  // 优先使用指定的 xAxisKey，否则智能选择：
  // - 维度列优先（GROUP_X 等）
  // - 折线图+有时间列时，用时间列
  // - 否则用第一列
  const xKey = props.xAxisKey ||
    (dimensionKeys.length > 0 ? dimensionKeys[0] :
     (chartType.value === 'line' && timeKeys.length > 0 ? timeKeys[0] : keys[0]))
  // 支持字符串数字
  const isNumeric = (val) => typeof val === 'number' || (!isNaN(parseFloat(val)) && typeof val !== 'boolean')
  // 排除的维度列（时间维度列不是指标）
  const excludeDateKeys = ['FDATE', 'FDATE_END', 'FDATE_START', 'MONTHS', '日期', '月份', '年份', '时间']
  // 计算数值列：排除维度列和 xKey，只要任意一行有有效数值就认为是数值列
  const numericKeys = props.seriesConfig.length > 0
    ? props.seriesConfig.map(s => s.key)
    : keys.filter(k => !excludeDateKeys.includes(k) && k !== xKey && data.some(row => {
        const val = row[k]
        return val !== null && val !== '' && (typeof val === 'number' || !isNaN(parseFloat(val)))
      }))

  // MoM 对比卡片模式优先检查
  if (chartType.value === 'comparison') {
    const row = data[0]
    const currentVal = parseFloat(row.current_val) || 0
    const compareVal = parseFloat(row.compare_val) || 0
    const changeRate = row.change_rate || '0'
    const trend = row.trend || ''

    // 计算期间标签
    const formatPeriod = (dateStr) => {
      if (!dateStr) return ''
      try {
        const d = new Date(dateStr)
        return `${d.getFullYear()}年${d.getMonth() + 1}月`
      } catch {
        return dateStr
      }
    }

    const currentPeriod = formatPeriod(props.timeStart)
    // 对比期：YoY 减1年，MoM 减1个月
    const comparePeriod = (() => {
      if (!props.timeStart) return '上期'
      try {
        const d = new Date(props.timeStart)
        const isYoy = props.timeStart.includes('-04-') // 简单判断：4月同比通常是YoY
        // 通过数据行里的时间范围判断（当前期 vs 对比期年份是否相同）
        // 通用方法：如果 timeStart 存在，用年份差判断
        const currentYear = d.getFullYear()
        // 假设 YoY：对比期是去年
        const compareDate = new Date(d)
        compareDate.setFullYear(currentYear - 1)
        return formatPeriod(compareDate.toISOString().slice(0, 10))
      } catch {
        return '上期'
      }
    })()

    return {
      type: 'comparison',
      currentVal: formatChartValue(currentVal),
      compareVal: formatChartValue(compareVal),
      changeRate: `${changeRate}%`,
      trend: trend,
      trendClass: trend === '增长' ? 'up' : trend === '下降' ? 'down' : 'flat',
      trendText: trend === '增长' ? `↑ ${changeRate}%` : trend === '下降' ? `↓ ${changeRate}%` : '持平',
      currentPeriod,
      comparePeriod
    }
  }

  const baseOptions = {
    backgroundColor: 'transparent',
    grid: {
      left: 80,
      right: 20,
      top: 20,
      bottom: 40
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e5e7eb',
      borderWidth: 1,
      textStyle: {
        color: '#374151',
        fontSize: 12
      },
      axisPointer: {
        type: 'shadow',
        shadowStyle: {
          color: 'rgba(99, 102, 241, 0.05)'
        }
      },
      formatter: (params) => {
        if (!params || params.length === 0) return ''
        const xValue = params[0].axisValue
        let html = `<div style="font-weight:500;margin-bottom:4px">${xValue}</div>`
        params.forEach(p => {
          const formattedValue = formatChartValue(p.value)
          // 单系列时优先使用 props.metricName（后端传递的中文指标名），多系列时用 FIELD_NAME_MAP 映射英文名
          const seriesName = p.seriesName || ''
          const label = (params.length === 1 && props.metricName) ? props.metricName : (FIELD_NAME_MAP[seriesName] || seriesName)
          html += `<div style="display:flex;justify-content:space-between;gap:16px">
            <span style="color:#6b7280">${p.marker}${label}</span>
            <span style="font-weight:500;color:#374151">${formattedValue}</span>
          </div>`
        })
        return html
      }
    }
  }

  if (chartType.value === 'line') {
    // Truncation helper for long labels
    const truncateLabel = (val) => {
      const str = String(val)
      if (str.length > props.truncationLength) {
        return str.substring(0, props.truncationLength) + '...'
      }
      return str
    }

    // 数据超过5个时启用滚动拖动
    const enableDataZoom = data.length > 5

    // 计算标签显示策略：数据多时间隔显示 + 始终显示极值和首尾
    const denseThreshold = 10
    const isDense = data.length > denseThreshold
    const labelStep = isDense ? Math.ceil(data.length / 8) : 1
    const allValues = data.map(row => {
      const v = numericKeys.reduce((sum, key) => sum + (parseFloat(row[key]) || 0), 0)
      return v
    })
    const maxIdx = allValues.indexOf(Math.max(...allValues))
    const minIdx = allValues.indexOf(Math.min(...allValues))
    const showLabelAt = (idx) => {
      if (!isDense) return true
      return idx === 0 || idx === data.length - 1 || idx === maxIdx || idx === minIdx || idx % labelStep === 0
    }

    const options = {
      ...baseOptions,
      // 多系列时显示图例
      ...(numericKeys.length > 1 ? {
        legend: {
          show: true,
          top: 0,
          textStyle: { color: '#6b7280', fontSize: 11 },
          itemWidth: 16,
          itemHeight: 8,
        },
        grid: { left: 80, right: 20, top: 30, bottom: 40 }
      } : {}),
      xAxis: {
        type: 'category',
        data: data.map(row => row[xKey]),
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisLabel: {
          color: '#6b7280',
          fontSize: 11,
          rotate: 0,
          formatter: (val) => truncateLabel(val)
        },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 11, formatter: (val) => formatChartValue(val) },
        splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }
      },
      series: numericKeys.map((key, idx) => ({
        name: numericKeys.length > 1 ? (FIELD_NAME_MAP[key] || key) : (props.metricName || FIELD_NAME_MAP[key] || key),
        type: 'line',
        data: data.map((row, i) => ({
          value: row[key],
          label: { show: showLabelAt(i) }
        })),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: getSeriesColor(idx) },
        itemStyle: { color: getSeriesColor(idx) },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${getSeriesColor(idx)}20` },
            { offset: 1, color: `${getSeriesColor(idx)}05` }
          ])
        },
        label: {
          show: true,
          position: 'top',
          fontSize: 10,
          color: '#6b7280',
          formatter: (params) => formatChartValue(params.value)
        }
      }))
    }

    // 添加滚动拖动支持
    if (enableDataZoom) {
      options.dataZoom = [
        {
          type: 'inside',
          start: 0,
          end: Math.min(100, 3000 / data.length)
        },
        {
          type: 'slider',
          start: 0,
          end: Math.min(100, 3000 / data.length),
          height: 20,
          bottom: 0,
          borderColor: '#e5e7eb',
          fillerColor: 'rgba(99, 102, 241, 0.1)',
          handleStyle: { color: '#6366F1' },
          textStyle: { color: '#6b7280', fontSize: 10 }
        }
      ]
      options.grid.bottom = 40
    }

    return options
  }

  if (chartType.value === 'bar') {
    const truncateLabel = (val) => {
      const str = String(val)
      if (str.length > props.truncationLength) {
        return str.substring(0, props.truncationLength) + '...'
      }
      return str
    }

    // 数据超过5个时启用滚动拖动
    const enableDataZoom = data.length > 5

    // bar 图标签策略：数据多时间隔显示
    const denseThreshold = 10
    const isDense = data.length > denseThreshold
    const labelStep = isDense ? Math.ceil(data.length / 8) : 1
    const showLabelAt = (idx) => {
      if (!isDense) return true
      return idx === 0 || idx === data.length - 1 || idx % labelStep === 0
    }

    const options = {
      ...baseOptions,
      xAxis: {
        type: 'category',
        data: data.map(row => row[xKey]),
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisLabel: {
          color: '#6b7280',
          fontSize: 11,
          rotate: 0,
          formatter: (val) => truncateLabel(val)
        },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 11, formatter: (val) => formatChartValue(val) },
        splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }
      },
      series: numericKeys.map((key, idx) => ({
        name: numericKeys.length > 1 ? (FIELD_NAME_MAP[key] || key) : (props.metricName || FIELD_NAME_MAP[key] || key),
        type: 'bar',
        data: data.map((row, i) => ({
          value: row[key],
          label: { show: showLabelAt(i) }
        })),
        barWidth: '60%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: getSeriesColor(idx) },
            { offset: 1, color: `${getSeriesColor(idx)}80` }
          ]),
          borderRadius: [4, 4, 0, 0]
        },
        label: {
          show: true,
          position: 'top',
          fontSize: 10,
          color: '#6b7280',
          formatter: (params) => formatChartValue(params.value)
        }
      }))
    }

    // 添加滚动拖动支持
    if (enableDataZoom) {
      options.dataZoom = [
        {
          type: 'inside',
          start: 0,
          end: Math.min(100, 3000 / data.length)
        },
        {
          type: 'slider',
          start: 0,
          end: Math.min(100, 3000 / data.length),
          height: 20,
          bottom: 0,
          borderColor: '#e5e7eb',
          fillerColor: 'rgba(99, 102, 241, 0.1)',
          handleStyle: { color: '#6366F1' },
          textStyle: { color: '#6b7280', fontSize: 10 }
        }
      ]
      options.grid.bottom = 40
    }

    return options
  }

  if (chartType.value === 'pie') {
    const labelKey = xKey
    const valueKey = numericKeys[0]
    const metricLabel = props.metricName || valueKey
    console.log('[DEBUG pie] labelKey:', labelKey, 'valueKey:', valueKey, 'metricLabel:', metricLabel)

    // 过滤掉 null/空值，只保留有数据的行
    const validData = data.filter(row => {
      const val = row[valueKey]
      return val !== null && val !== '' && !isNaN(parseFloat(val))
    })
    console.log('[DEBUG pie] validData length:', validData.length, JSON.stringify(validData))

    const options = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e5e7eb',
        borderWidth: 1,
        textStyle: { color: '#374151', fontSize: 12 },
        formatter: (params) => {
          return `<div style="font-weight:500;margin-bottom:4px">${params.name}</div>
                  <div style="display:flex;justify-content:space-between;gap:16px">
                    <span style="color:#6b7280">${params.marker}${metricLabel}</span>
                    <span style="font-weight:500;color:#374151">${params.percent.toFixed(1)}%</span>
                  </div>`
        }
      },
      series: [{
        name: metricLabel,
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['50%', '50%'],
        data: validData.map(row => ({
          name: row[labelKey],
          value: Math.abs(parseFloat(row[valueKey]) || 0)
        })),
        label: {
          show: true,
          formatter: '{b}: {d}%',
          color: '#6b7280',
          fontSize: 11
        },
        labelLine: {
          show: true,
          lineStyle: { color: '#e5e7eb' }
        },
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.3)'
          }
        }
      }]
    }

    return options
  }

  return baseOptions
})

function getSeriesColor(idx) {
  const colors = ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']
  return colors[idx % colors.length]
}

// 格式化数值（图表用，超过1000显示万/亿）
function formatChartValue(val) {
  if (val === null || val === undefined) return '-'
  const num = typeof val === 'number' ? val : parseFloat(String(val).replace(/,/g, ''))
  if (isNaN(num)) return val
  if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(2) + '万'
  if (num >= 1000) return num.toLocaleString()
  return num % 1 === 0 ? num : num.toFixed(2)
}

// 格式化数值（卡片用）
function formatMetricValue(val) {
  if (val === null || val === undefined) return '-'
  const num = typeof val === 'number' ? val : parseFloat(val)
  if (isNaN(num)) return val
  if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(2) + '万'
  if (num >= 1000) return num.toLocaleString()
  return num.toFixed(2)
}

function initChart(container, options) {
  if (!container) return null

  const chart = echarts.init(container)
  chart.setOption(options)
  return chart
}

function updateChart() {
  if (chartInstance) {
    chartInstance.setOption(chartOptions.value, true)
  }
  if (fullscreenChartInstance) {
    fullscreenChartInstance.setOption(chartOptions.value, true)
  }
}

async function toggleExpand() {
  expanded.value = !expanded.value
  await nextTick()
  if (expanded.value) {
    if (!fullscreenChartInstance && fullscreenChartContainer.value) {
      fullscreenChartInstance = initChart(fullscreenChartContainer.value, chartOptions.value)
    }
  }
}

watch(() => props.data, () => {
  nextTick(() => {
    updateChart()
  })
}, { deep: true })

watch(chartOptions, () => {
  updateChart()
}, { deep: true })

onMounted(() => {
  if (chartContainer.value && props.data && props.data.length > 0) {
    try {
      chartInstance = initChart(chartContainer.value, chartOptions.value)
    } catch (err) {
      error.value = '图表渲染失败'
      console.error('Chart error:', err)
    }
  }
})

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  if (fullscreenChartInstance) {
    fullscreenChartInstance.dispose()
    fullscreenChartInstance = null
  }
})
</script>

<style scoped>
.sku-link {
  color: #00B078;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.sku-link:hover {
  color: #00A06B;
}

.chart-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.08);
  margin-top: 16px;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.chart-title {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.chart-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
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

.action-btn:hover {
  background: rgba(99, 102, 241, 0.08);
  color: #6366F1;
}

.chart-container {
  width: 100%;
}

.chart-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 20px;
  color: #9ca3af;
  font-size: 13px;
}

.chart-interpretation {
  margin-top: 12px;
  padding: 12px 16px;
  background: #F8FAFF;
  border: 1px solid #E0E7FF;
  border-radius: 8px;
}

.interpretation-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #4F46E5;
  margin-bottom: 8px;
}

.interpretation-content {
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}

/* 数字卡片 */
.metric-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background: linear-gradient(135deg, #F5F3FF 0%, #FFFFFF 100%);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 12px;
  min-height: 120px;
  width: 100%;
  box-sizing: border-box;
}

.metric-value {
  font-size: 36px;
  font-weight: 600;
  color: #6366F1;
  margin-bottom: 8px;
}

.metric-label {
  font-size: 14px;
  color: #6B7280;
}

/* MoM 对比卡片 */
.comparison-card {
  padding: 20px;
  background: linear-gradient(135deg, #F5F3FF 0%, #FFFFFF 100%);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 12px;
  width: 100%;
  box-sizing: border-box;
}

.comparison-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.comparison-title {
  font-size: 15px;
  font-weight: 500;
  color: #374151;
}

.comparison-trend {
  font-size: 14px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 6px;
}

.comparison-trend.up {
  color: #10B981;
  background: rgba(16, 185, 129, 0.1);
}

.comparison-trend.down {
  color: #EF4444;
  background: rgba(239, 68, 68, 0.1);
}

.comparison-trend.flat {
  color: #6B7280;
  background: rgba(107, 114, 128, 0.1);
}

.comparison-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.comparison-item {
  flex: 1;
  text-align: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 8px;
}

.comparison-item.change {
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.15);
}

.comparison-label {
  font-size: 12px;
  color: #6B7280;
  margin-bottom: 6px;
}

.comparison-value {
  font-size: 20px;
  font-weight: 600;
  color: #374151;
}

.comparison-value.up {
  color: #10B981;
}

.comparison-value.down {
  color: #EF4444;
}

.comparison-arrow {
  font-size: 20px;
  color: #9CA3AF;
  flex-shrink: 0;
}

/* Fullscreen */
.chart-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.fullscreen-content {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 1200px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.fullscreen-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.fullscreen-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}

.close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #f3f4f6;
  color: #1f1f1f;
}

.fullscreen-chart {
  flex: 1;
  padding: 20px;
  min-height: 400px;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 多指标表格 */
.time-range-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  padding: 0 4px;
}

.metric-table {
  width: 100%;
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  background: #F9FAFB;
  color: #374151;
  font-weight: 600;
  text-align: left;
  padding: 10px 12px;
  border-bottom: 2px solid #E5E7EB;
  cursor: pointer;
  user-select: none;
}

.data-table th.sortable:hover {
  background: #F0F1F3;
}

.sort-icon {
  margin-left: 4px;
  color: #9CA3AF;
  font-size: 11px;
}

.sort-icon.default {
  color: #D1D5DB;
}

.data-table th.sorted .sort-icon {
  color: #3B82F6;
}

.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #F3F4F6;
  color: #374151;
}

.data-table tr:hover td {
  background: #F9FAFB;
}

/* ========================================
   Mobile Table Optimizations
   ======================================== */

@media (max-width: 768px) {
  .metric-table {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    /* 隐藏滚动条但保持功能 */
    scrollbar-width: none;
    -ms-overflow-style: none;
  }

  .metric-table::-webkit-scrollbar {
    display: none;
  }

  .data-table {
    /* 确保文字不折行 */
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .data-table th,
  .data-table td {
    /* 首列固定 */
    position: sticky;
    left: 0;
    z-index: 1;
    background: inherit;
  }

  .data-table th {
    /* 表头固定 */
    position: sticky;
    top: 0;
    z-index: 2;
  }

  /* 关键数据列突出 */
  .data-table td:first-child {
    font-weight: 600;
    color: #1F1F1F;
  }

  /* 数值列右对齐 */
  .data-table td.numeric {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  /* 表格行点击反馈 */
  .data-table tbody tr {
    cursor: pointer;
    transition: background-color 0.15s ease;
  }

  .data-table tbody tr:active td {
    background: rgba(0, 0, 0, 0.05);
  }

  .data-table th {
    background: #F9FAFB;
  }
}
</style>
