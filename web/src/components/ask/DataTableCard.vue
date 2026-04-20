<template>
  <div class="data-table-card" :class="{ 'dark-mode': darkMode }">
    <div class="card-header">
      <div class="header-left">
        <span class="card-title">{{ title }}</span>
        <el-tag v-if="subtitle" type="info" size="small">{{ subtitle }}</el-tag>
      </div>
      <div class="header-right">
        <el-button v-if="showViewToggle" text size="small" @click="toggleView">
          {{ viewMode === 'table' ? '卡片' : '表格' }}视图
        </el-button>
        <slot name="header-actions"></slot>
      </div>
    </div>

    <div class="card-content">
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="3" animated />
      </div>

      <div v-else-if="!data || data.length === 0" class="empty-container">
        <el-empty description="暂无数据" />
      </div>

      <div v-else>
        <!-- Table View -->
        <el-table
          v-if="viewMode === 'table'"
          :data="data"
          stripe
          border
          class="data-table"
          :header-cell-style="{ background: darkMode ? '#2d2d4a' : '#f5f7fa', color: darkMode ? '#fff' : '#1F1F1F' }"
        >
          <el-table-column
            v-for="col in columns"
            :key="col.prop"
            :prop="col.prop"
            :label="col.label"
            :width="col.width"
            :align="col.align || 'left'"
          >
            <template #default="{ row }">
              <template v-if="col.type === 'number'">
                {{ formatNumber(row[col.prop]) }}
              </template>
              <template v-else-if="col.type === 'percent'">
                <span :class="getPercentClass(row[col.prop])">
                  {{ formatPercent(row[col.prop]) }}
                </span>
              </template>
              <template v-else-if="col.type === 'anomaly'">
                <span v-if="row[col.prop] < 0" class="anomaly-badge">
                  {{ formatPercent(row[col.prop]) }}
                </span>
                <span v-else>{{ formatPercent(row[col.prop]) }}</span>
              </template>
              <template v-else>
                {{ row[col.prop] }}
              </template>
            </template>
          </el-table-column>
        </el-table>

        <!-- Card View -->
        <div v-else class="card-view">
          <div
            v-for="(item, index) in data"
            :key="index"
            class="data-card"
          >
            <div class="card-item" v-for="col in columns" :key="col.prop">
              <span class="item-label">{{ col.label }}</span>
              <span class="item-value">
                <template v-if="col.type === 'number'">
                  {{ formatNumber(item[col.prop]) }}
                </template>
                <template v-else-if="col.type === 'percent'">
                  <span :class="getPercentClass(item[col.prop])">
                    {{ formatPercent(item[col.prop]) }}
                  </span>
                </template>
                <template v-else>
                  {{ item[col.prop] }}
                </template>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showPagination && data.length > 0" class="card-footer">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        small
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: '数据表格'
  },
  subtitle: {
    type: String,
    default: ''
  },
  data: {
    type: Array,
    default: () => []
  },
  columns: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  darkMode: {
    type: Boolean,
    default: false
  },
  showViewToggle: {
    type: Boolean,
    default: false
  },
  showPagination: {
    type: Boolean,
    default: true
  },
  total: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['page-change'])

const viewMode = ref('table')
const currentPage = ref(1)
const pageSize = ref(20)

const toggleView = () => {
  viewMode.value = viewMode.value === 'table' ? 'card' : 'table'
}

const formatNumber = (value) => {
  if (value === null || value === undefined) return '-'
  const num = Number(value)
  if (isNaN(num)) return value
  return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

const formatPercent = (value) => {
  if (value === null || value === undefined) return '-'
  const num = Number(value)
  if (isNaN(num)) return value
  const sign = num > 0 ? '+' : ''
  return `${sign}${num.toFixed(1)}%`
}

const getPercentClass = (value) => {
  if (value === null || value === undefined) return ''
  const num = Number(value)
  if (num > 0) return 'text-success'
  if (num < 0) return 'text-danger'
  return ''
}

const handleSizeChange = (val) => {
  pageSize.value = val
  emit('page-change', { page: currentPage.value, pageSize: val })
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  emit('page-change', { page: val, pageSize: pageSize.value })
}
</script>

<style scoped>
.data-table-card {
  background: var(--bg-card, #fff);
  border: 1px solid var(--border, #e8e8e8);
  border-radius: var(--radius-lg, 8px);
  overflow: hidden;
}

.data-table-card.dark-mode {
  background: #1a1a2e;
  border-color: #2d2d4a;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border, #e8e8e8);
}

.dark-mode .card-header {
  border-color: #2d2d4a;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1F1F1F);
}

.dark-mode .card-title {
  color: #fff;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-content {
  padding: 0;
}

.loading-container,
.empty-container {
  padding: 40px;
  text-align: center;
}

.data-table {
  width: 100%;
}

.dark-mode .data-table {
  background: #1a1a2e;
  color: #fff;
}

.card-view {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  padding: 16px;
}

.data-card {
  background: var(--bg-primary, #f2f3f5);
  border-radius: var(--radius-md, 6px);
  padding: 12px;
}

.dark-mode .data-card {
  background: #2d2d4a;
}

.card-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
}

.card-item:not(:last-child) {
  border-bottom: 1px solid var(--border, #e8e8e8);
}

.dark-mode .card-item:not(:last-child) {
  border-color: #3d3d5a;
}

.item-label {
  font-size: 13px;
  color: var(--text-muted, #999);
}

.dark-mode .item-label {
  color: #888;
}

.item-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #1F1F1F);
}

.dark-mode .item-value {
  color: #fff;
}

.text-success {
  color: #00A870;
}

.text-danger {
  color: #F56C6C;
}

.anomaly-badge {
  background: rgba(245, 108, 108, 0.1);
  color: #F56C6C;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.card-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border, #e8e8e8);
  display: flex;
  justify-content: flex-end;
}

.dark-mode .card-footer {
  border-color: #2d2d4a;
}
</style>
