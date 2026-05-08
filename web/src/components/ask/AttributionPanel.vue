<template>
  <el-drawer
    v-model="visible"
    direction="rtl"
    :size="480"
    :show-close="false"
    class="attribution-panel"
  >
    <template #header>
      <div class="drawer-header">
        <div class="drawer-title">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 14L7 9L10 12L17 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>贡献度分析</span>
        </div>
        <button class="close-btn" @click="visible = false">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </template>

    <div class="drawer-content">
      <!-- Trend Chart -->
      <div v-if="trendData && trendData.length > 0" class="trend-section">
        <div class="section-label">主趋势</div>
        <ChartCard
          :data="trendData"
          :height="180"
          type="line"
        />
      </div>

      <!-- Attribution List -->
      <div class="attribution-section">
        <div class="section-label">驱动因素</div>

        <!-- Positive Factors -->
        <div v-if="positiveFactors.length > 0" class="factors-group">
          <div class="factors-group-header positive">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 3V11M7 3L4 6M7 3L10 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>正向驱动</span>
          </div>
          <div class="factors-list">
            <div
              v-for="(factor, idx) in positiveFactors"
              :key="'pos-' + idx"
              class="factor-item"
            >
              <div class="factor-header">
                <span class="factor-rank">{{ idx + 1 }}</span>
                <span class="factor-name">{{ factor.name }}</span>
                <span class="factor-value positive">+{{ formatValue(factor.value) }}</span>
              </div>
              <div class="factor-bar-container">
                <div class="factor-bar-center"></div>
                <div
                  class="factor-bar positive"
                  :style="{ width: getBarWidth(factor.value) + '%' }"
                ></div>
              </div>
              <div class="factor-actions">
                <button class="trace-btn" @click="handleTrace(factor)">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <circle cx="6" cy="6" r="4" stroke="currentColor" stroke-width="1.2"/>
                    <path d="M6 4V6L7.5 7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                  </svg>
                  原因追踪
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Negative Factors -->
        <div v-if="negativeFactors.length > 0" class="factors-group">
          <div class="factors-group-header negative">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 11V3M7 11L4 8M7 11L10 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>负向驱动</span>
          </div>
          <div class="factors-list">
            <div
              v-for="(factor, idx) in negativeFactors"
              :key="'neg-' + idx"
              class="factor-item"
            >
              <div class="factor-header">
                <span class="factor-rank">{{ idx + 1 }}</span>
                <span class="factor-name">{{ factor.name }}</span>
                <span class="factor-value negative">{{ formatValue(factor.value) }}</span>
              </div>
              <div class="factor-bar-container">
                <div class="factor-bar-center"></div>
                <div
                  class="factor-bar negative"
                  :style="{ width: getBarWidth(factor.value) + '%' }"
                ></div>
              </div>
              <div class="factor-actions">
                <button class="trace-btn" @click="handleTrace(factor)">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <circle cx="6" cy="6" r="4" stroke="currentColor" stroke-width="1.2"/>
                    <path d="M6 4V6L7.5 7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                  </svg>
                  原因追踪
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="positiveFactors.length === 0 && negativeFactors.length === 0" class="empty-state">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
            <circle cx="20" cy="20" r="16" stroke="#e5e7eb" stroke-width="2"/>
            <path d="M20 12V20L26 26" stroke="#e5e7eb" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <span>暂无归因数据</span>
        </div>
      </div>

      <!-- Detail Table -->
      <div v-if="detailData && detailData.length > 0" class="detail-section">
        <div class="section-label">详细数据</div>
        <div class="detail-table">
          <div class="table-header">
            <span>因素</span>
            <span>贡献度</span>
            <span>占比</span>
          </div>
          <div
            v-for="(row, idx) in detailData"
            :key="idx"
            class="table-row"
          >
            <span class="row-name">{{ row.name }}</span>
            <span :class="['row-value', row.value >= 0 ? 'positive' : 'negative']">
              {{ row.value >= 0 ? '+' : '' }}{{ formatValue(row.value) }}
            </span>
            <div class="row-bar">
              <div class="bar-bg">
                <div
                  class="bar-fill"
                  :class="row.value >= 0 ? 'positive' : 'negative'"
                  :style="{ width: Math.abs(getPercentage(row)) + '%' }"
                ></div>
              </div>
              <span class="bar-text">{{ getPercentage(row) }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import ChartCard from './ChartCard.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  positiveFactors: {
    type: Array,
    default: () => []
  },
  negativeFactors: {
    type: Array,
    default: () => []
  },
  trendData: {
    type: Array,
    default: () => []
  },
  detailData: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'trace'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// Calculate max absolute value for bar width
const maxAbsValue = computed(() => {
  const allFactors = [...props.positiveFactors, ...props.negativeFactors]
  if (allFactors.length === 0) return 100
  return Math.max(...allFactors.map(f => Math.abs(f.value)), 1)
})

function getBarWidth(value) {
  return (Math.abs(value) / maxAbsValue.value) * 50 // 50% is max width (one side)
}

function formatValue(value) {
  if (typeof value === 'number') {
    if (Math.abs(value) >= 10000) {
      return (value / 10000).toFixed(1) + '万'
    }
    return value.toFixed(1) + '%'
  }
  return value
}

function getPercentage(row) {
  const total = [...props.positiveFactors, ...props.negativeFactors]
    .reduce((sum, f) => sum + Math.abs(f.value), 0)
  if (total === 0) return 0
  return Math.round((Math.abs(row.value) / total) * 100)
}

function handleTrace(factor) {
  emit('trace', factor)
}
</script>

<style scoped>
.attribution-panel {
  --el-drawer-bg-color: #fff;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}

.drawer-title svg {
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

.drawer-content {
  padding: 16px 0;
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

/* Trend Section */
.trend-section {
  margin-bottom: 24px;
}

/* Attribution Section */
.attribution-section {
  margin-bottom: 24px;
}

.factors-group {
  margin-bottom: 20px;
}

.factors-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 10px;
  padding: 6px 10px;
  border-radius: 6px;
}

.factors-group-header.positive {
  color: #10B981;
  background: rgba(16, 185, 129, 0.08);
}

.factors-group-header.negative {
  color: #EF4444;
  background: rgba(239, 68, 68, 0.08);
}

.factors-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.factor-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 10px;
}

.factor-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.factor-rank {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.factor-name {
  flex: 1;
  font-size: 13px;
  color: #374151;
}

.factor-value {
  font-size: 13px;
  font-weight: 600;
}

.factor-value.positive {
  color: #10B981;
}

.factor-value.negative {
  color: #EF4444;
}

/* Center-origin Progress Bar */
.factor-bar-container {
  position: relative;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  margin-bottom: 8px;
}

.factor-bar-center {
  position: absolute;
  left: 50%;
  top: -2px;
  bottom: -2px;
  width: 2px;
  background: #9ca3af;
  border-radius: 1px;
  transform: translateX(-50%);
}

.factor-bar {
  position: absolute;
  top: 0;
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.factor-bar.positive {
  left: 50%;
  background: linear-gradient(90deg, #10B981 0%, #34D399 100%);
}

.factor-bar.negative {
  right: 50%;
  background: linear-gradient(270deg, #EF4444 0%, #F87171 100%);
}

.factor-actions {
  display: flex;
  justify-content: flex-end;
}

.trace-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  color: #6b7280;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.trace-btn:hover {
  background: rgba(99, 102, 241, 0.06);
  border-color: rgba(99, 102, 241, 0.3);
  color: #6366F1;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: #9ca3af;
  font-size: 13px;
}

/* Detail Table */
.detail-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}

.detail-table {
  background: #f9fafb;
  border-radius: 10px;
  overflow: hidden;
}

.table-header {
  display: grid;
  grid-template-columns: 1fr 80px 100px;
  gap: 8px;
  padding: 10px 12px;
  background: #f3f4f6;
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
}

.table-row {
  display: grid;
  grid-template-columns: 1fr 80px 100px;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  align-items: center;
}

.table-row:last-child {
  border-bottom: none;
}

.row-name {
  font-size: 12px;
  color: #374151;
}

.row-value {
  font-size: 12px;
  font-weight: 600;
}

.row-value.positive {
  color: #10B981;
}

.row-value.negative {
  color: #EF4444;
}

.row-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-bg {
  flex: 1;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.bar-fill.positive {
  background: #10B981;
}

.bar-fill.negative {
  background: #EF4444;
}

.bar-text {
  font-size: 10px;
  color: #9ca3af;
  min-width: 36px;
  text-align: right;
}
</style>
