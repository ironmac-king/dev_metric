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
          <div class="comparison-label">上期（2月）</div>
          <div class="comparison-value">{{ chartOptions.compareVal }}</div>
        </div>
        <div class="comparison-arrow">→</div>
        <div class="comparison-item">
          <div class="comparison-label">当期（3月）</div>
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
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="(header, idx) in tableHeaders" :key="tableKeys[idx]">{{ header }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in props.data" :key="idx">
            <td v-for="key in tableKeys" :key="key">{{ formatTableCell(key, row[key]) }}</td>
          </tr>
        </tbody>
      </table>
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
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick, computed } from 'vue'
import * as echarts from 'echarts'

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
  }
})

const chartContainer = ref(null)
const fullscreenChartContainer = ref(null)
const expanded = ref(false)
const error = ref('')
const showInterpretation = ref(false)

let chartInstance = null
let fullscreenChartInstance = null

// 多指标表格的列 keys
const tableKeys = computed(() => {
  if (!props.data || props.data.length === 0) return []
  return Object.keys(props.data[0])
})

// 判断是否是数值列（排除时间维度列 MONTHS/FDATE）
function isNumericColumn(key, val) {
  if (key === 'MONTHS' || key === 'FDATE') return false
  if (val === null || val === '') return false
  return typeof val === 'number' || !isNaN(parseFloat(val))
}

// 多指标表格的列 header（中文名）
const tableHeaders = computed(() => {
  if (!props.data || props.data.length === 0) return []
  const keys = Object.keys(props.data[0])
  // 过滤出数值列（metric 对应的列，排除 MONTHS/FDATE）
  const numericKeys = keys.filter(k => isNumericColumn(k, props.data[0][k]))
  console.log('[DEBUG tableHeaders] metricNames:', props.metricNames, 'keys:', keys, 'numericKeys:', numericKeys, 'firstRow:', props.data[0])
  // 维度列（GROUP_X, MONTHS, FDATE）→ 使用中文维度类型名
  const dimensionHeaders = keys
    .filter(k => !numericKeys.includes(k))
    .map(k => {
      // GROUP_X → 二级品类
      if (k === 'GROUP_2') return '二级品类'
      if (k === 'GROUP_1') return '一级品类'
      if (k === 'GROUP_3') return '三级品类'
      if (k === 'GROUP_4') return '四级品类'
      if (k === 'FDATE') return '日期'
      if (k === 'MONTHS') return '月份'
      return k
    })
  // 指标列 → 使用 metricNames
  const metricHeaders = props.metricNames && props.metricNames.length > 0
    ? props.metricNames.slice(0, numericKeys.length)
    : numericKeys
  return [...dimensionHeaders, ...metricHeaders]
})

// 格式化表格单元格
function formatTableCell(key, val) {
  if (val === null || val === undefined) return '-'
  // 月份列：数字或字符串数字加"月"后缀
  if (key === 'MONTHS') {
    const num = typeof val === 'number' ? val : parseFloat(val)
    if (!isNaN(num)) return num + '月'
    return val + '月'
  }
  if (typeof val === 'number') {
    const formatted = formatChartValue(val)
    console.log('[DEBUG formatTableCell] raw:', val, 'formatted:', formatted)
    return formatted
  }
  // 尝试解析字符串数字
  const parsed = parseFloat(String(val).replace(/,/g, ''))
  if (!isNaN(parsed)) {
    const formatted = formatChartValue(parsed)
    console.log('[DEBUG formatTableCell] string raw:', val, 'parsed:', parsed, 'formatted:', formatted)
    return formatted
  }
  return val
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
    const numericKeys = keys.filter(k => {
      const val = props.data[0][k]
      const isNum = typeof val === 'number' || !isNaN(parseFloat(val))
      return isNum
    })
    console.log('[DEBUG chartType] single row, numericKeys length:', numericKeys.length)
    // 如果只有一个数值字段，显示为数字卡片；多个数值字段显示为表格
    if (numericKeys.length === 1) {
      return 'card'
    } else if (numericKeys.length > 1) {
      console.log('[DEBUG chartType] returning table because numericKeys length > 1')
      return 'table'
    }
  }

  const keys = Object.keys(props.data[0])
  const isTimeSeries = props.data.some(row => {
    const val = row[props.xAxisKey || keys[0]]
    return val && (val.includes('-') || val.includes('/') || !isNaN(Date.parse(val)))
  })

  const numericKeys = keys.filter(k => {
    // 检查所有行，只要任意一行有有效数值就认为是数值列
    return props.data.some(row => {
      const val = row[k]
      return val !== null && val !== '' && (typeof val === 'number' || !isNaN(parseFloat(val)))
    })
  })

  console.log('[DEBUG chartType] keys:', keys, 'numericKeys:', numericKeys)

  if (numericKeys.length === 1) {
    // 檢測是否是佔比/比率數據，優先顯示餅圖
    const metricName = props.metricName || ''
    const ratioKeywords = ['占比', '比例', '比率', '率']
    const isRatioMetric = ratioKeywords.some(k => metricName.includes(k))
    const isPercentageRange = props.data.some(row => {
      // 只要有一行及以上数据在 0-100 范围内就认为是占比数据
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
    return 'table'  // 多指标用表格展示
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
  const xKey = props.xAxisKey || keys[0]
  // 支持字符串数字
  const isNumeric = (val) => typeof val === 'number' || (!isNaN(parseFloat(val)) && typeof val !== 'boolean')
  // 计算数值列：检查所有行，只要任意一行有有效数值就认为是数值列
  const numericKeys = props.seriesConfig.length > 0
    ? props.seriesConfig.map(s => s.key)
    : keys.filter(k => data.some(row => {
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
    return {
      type: 'comparison',
      currentVal: formatChartValue(currentVal),
      compareVal: formatChartValue(compareVal),
      changeRate: `${changeRate}%`,
      trend: trend,
      trendClass: trend === '增长' ? 'up' : trend === '下降' ? 'down' : 'flat',
      trendText: trend === '增长' ? `↑ ${changeRate}%` : trend === '下降' ? `↓ ${changeRate}%` : '持平'
    }
  }

  // 单值卡片模式优先检查
  if (chartType.value === 'card' && numericKeys.length > 0) {
    const numericKey = numericKeys[0]
    const value = data[0][numericKey]
    return {
      type: 'card',
      value: value,
      label: props.metricName || numericKey
    }
  }

  const baseOptions = {
    backgroundColor: 'transparent',
    grid: {
      left: 50,
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
          // 单系列时使用中文指标名，多系列时使用各系列自己的名字（如 current_val、compare_val）
          const label = (params.length === 1 && props.metricName) ? props.metricName : p.seriesName
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

    const options = {
      ...baseOptions,
      xAxis: {
        type: 'category',
        data: data.map(row => row[xKey]),
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisLabel: {
          color: '#6b7280',
          fontSize: 11,
          rotate: 30,
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
        name: numericKeys.length === 1 && props.metricName ? props.metricName : key,
        type: 'line',
        data: data.map(row => row[key]),
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

    const options = {
      ...baseOptions,
      xAxis: {
        type: 'category',
        data: data.map(row => row[xKey]),
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisLabel: {
          color: '#6b7280',
          fontSize: 11,
          rotate: 30,
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
        name: numericKeys.length === 1 && props.metricName ? props.metricName : key,
        type: 'bar',
        data: data.map(row => row[key]),
        barWidth: '60%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: getSeriesColor(idx) },
            { offset: 1, color: `${getSeriesColor(idx)}80` }
          ]),
          borderRadius: [4, 4, 0, 0]
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

// 格式化数值（图表用，超过10000显示万/亿）
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
}

.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #F3F4F6;
  color: #374151;
}

.data-table tr:hover td {
  background: #F9FAFB;
}
</style>
