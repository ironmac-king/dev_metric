<template>
  <div class="plan-confirm-card">
    <div class="plan-header">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="8" stroke="#3B82F6" stroke-width="1.5"/>
        <path d="M7 10L9 12L13 8" stroke="#3B82F6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span class="plan-title">查询方案确认</span>
    </div>

    <div class="plan-content">
      <div class="plan-item">
        <span class="plan-label">时间范围</span>
        <span class="plan-value">{{ plan.time_range || '未指定' }}</span>
      </div>
      <div class="plan-item">
        <span class="plan-label">指标</span>
        <div class="plan-tags">
          <span v-for="m in plan.metrics" :key="m" class="tag metric-tag">{{ m }}</span>
        </div>
      </div>
      <div v-if="plan.dimensions && plan.dimensions.length" class="plan-item">
        <span class="plan-label">维度</span>
        <div class="plan-tags">
          <span v-for="d in plan.dimensions" :key="d" class="tag dimension-tag">{{ d }}</span>
        </div>
      </div>
    </div>

    <div class="plan-actions">
      <button class="btn-modify" @click="handleModify">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M10.5 1.5L12.5 3.5L4 12H2V10L10.5 1.5Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        修改方案
      </button>
      <button class="btn-confirm" @click="handleConfirm">
        开始分析
      </button>
    </div>

    <!-- 标签化配置台弹窗 -->
    <div v-if="showTagSelector" class="tag-selector-overlay" @click.self="showTagSelector = false">
      <div class="tag-selector-modal">
        <div class="modal-header">
          <span>修改查询方案</span>
          <button class="modal-close" @click="showTagSelector = false">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <div class="selector-section">
            <div class="selector-label">时间范围</div>
            <el-select v-model="editTimeRange" placeholder="选择时间范围" class="selector-input">
              <el-option label="今天" value="今天" />
              <el-option label="昨天" value="昨天" />
              <el-option label="近7天" value="近7天" />
              <el-option label="近30天" value="近30天" />
              <el-option label="本月" value="本月" />
              <el-option label="上月" value="上月" />
              <el-option label="本年" value="本年" />
            </el-select>
          </div>

          <div class="selector-section">
            <div class="selector-label">指标</div>
            <div class="tag-input-wrapper">
              <el-select
                v-model="editMetrics"
                multiple
                placeholder="选择或搜索指标"
                class="selector-input"
                filterable
              >
                <el-option
                  v-for="m in availableMetrics"
                  :key="m"
                  :label="m"
                  :value="m"
                />
              </el-select>
            </div>
          </div>

          <div class="selector-section">
            <div class="selector-label">维度</div>
            <div class="tag-input-wrapper">
              <el-select
                v-model="editDimensions"
                multiple
                placeholder="选择或搜索维度"
                class="selector-input"
                filterable
              >
                <el-option
                  v-for="d in availableDimensions"
                  :key="d"
                  :label="d"
                  :value="d"
                />
              </el-select>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn-cancel" @click="showTagSelector = false">取消</button>
          <button class="btn-save" @click="handleSaveEdit">保存方案</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  plan: {
    type: Object,
    default: () => ({
      time_range: '',
      metrics: [],
      dimensions: []
    })
  },
  availableMetrics: {
    type: Array,
    default: () => []
  },
  availableDimensions: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['confirm', 'modify'])

const showTagSelector = ref(false)
const editTimeRange = ref('')
const editMetrics = ref([])
const editDimensions = ref([])

watch(() => props.plan, (newPlan) => {
  editTimeRange.value = newPlan.time_range || ''
  editMetrics.value = [...(newPlan.metrics || [])]
  editDimensions.value = [...(newPlan.dimensions || [])]
}, { immediate: true })

function handleModify() {
  showTagSelector.value = true
}

function handleConfirm() {
  emit('confirm', props.plan)
}

function handleSaveEdit() {
  const modifiedPlan = {
    time_range: editTimeRange.value,
    metrics: editMetrics.value,
    dimensions: editDimensions.value
  }
  emit('modify', modifiedPlan)
  showTagSelector.value = false
}
</script>

<style scoped>
.plan-confirm-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  margin: 16px 0;
  max-width: 600px;
}

.plan-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.plan-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.plan-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plan-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.plan-label {
  font-size: 13px;
  color: #6b7280;
  min-width: 60px;
  padding-top: 4px;
}

.plan-value {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}

.plan-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
}

.metric-tag {
  background: #EEF2FF;
  color: #4F46E5;
}

.dimension-tag {
  background: #F0FDF4;
  color: #16A34A;
}

.plan-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.btn-modify {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-modify:hover {
  border-color: #3B82F6;
  color: #3B82F6;
}

.btn-confirm {
  padding: 8px 20px;
  background: #3B82F6;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-confirm:hover {
  background: #2563EB;
}

/* 标签选择器弹窗 */
.tag-selector-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.tag-selector-modal {
  background: #fff;
  border-radius: 12px;
  width: 480px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  font-size: 16px;
  color: #1f2937;
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  color: #9ca3af;
  padding: 4px;
}

.modal-close:hover {
  color: #374151;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.selector-section {
  margin-bottom: 20px;
}

.selector-section:last-child {
  margin-bottom: 0;
}

.selector-label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

.selector-input {
  width: 100%;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
}

.btn-cancel {
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
}

.btn-save {
  padding: 8px 20px;
  background: #3B82F6;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.btn-save:hover {
  background: #2563EB;
}
</style>
