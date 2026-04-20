<template>
  <div class="clarification-card">
    <div class="clarification-header">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="8" stroke="#3B82F6" stroke-width="1.5"/>
        <path d="M10 6V10M10 13H10.01" stroke="#3B82F6" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
      <span class="clarification-title">请选择您要查询的方向：</span>
    </div>

    <div class="clarification-options">
      <div
        v-for="option in options"
        :key="option.id"
        class="clarification-option"
        :class="{ selected: selectedId === option.id }"
        @click="handleSelect(option)"
      >
        <div class="option-radio">
          <div class="radio-inner" :class="{ active: selectedId === option.id }"></div>
        </div>
        <div class="option-content">
          <div class="option-label">{{ option.label }}</div>
          <div v-if="option.description" class="option-desc">{{ option.description }}</div>
          <div v-if="option.metrics" class="option-tags">
            <span v-for="m in option.metrics.slice(0, 3)" :key="m" class="tag">{{ m }}</span>
            <span v-if="option.metrics.length > 3" class="tag more">+{{ option.metrics.length - 3 }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="clarification-actions">
      <button class="btn-confirm" :disabled="!selectedId" @click="handleConfirm">
        确认查询
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  options: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['select', 'confirm'])

const selectedId = ref(null)

function handleSelect(option) {
  selectedId.value = option.id
  emit('select', option)
}

function handleConfirm() {
  const selected = props.options.find(o => o.id === selectedId.value)
  if (selected) {
    emit('confirm', selected)
  }
}
</script>

<style scoped>
.clarification-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  margin: 16px 0;
  max-width: 600px;
}

.clarification-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.clarification-title {
  font-size: 15px;
  font-weight: 500;
  color: #374151;
}

.clarification-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.clarification-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.clarification-option:hover {
  border-color: #3B82F6;
  background: #F8FAFF;
}

.clarification-option.selected {
  border-color: #3B82F6;
  background: #F8FAFF;
}

.option-radio {
  width: 18px;
  height: 18px;
  border: 2px solid #d1d5db;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.option-radio .radio-inner {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: transparent;
  transition: all 0.2s ease;
}

.option-radio .radio-inner.active {
  background: #3B82F6;
}

.option-content {
  flex: 1;
  min-width: 0;
}

.option-label {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  margin-bottom: 4px;
}

.option-desc {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.option-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  font-size: 12px;
  padding: 2px 8px;
  background: #e5e7eb;
  border-radius: 4px;
  color: #374151;
}

.tag.more {
  background: #F3F4F6;
  color: #6b7280;
}

.clarification-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.btn-confirm {
  padding: 10px 24px;
  background: #3B82F6;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-confirm:hover:not(:disabled) {
  background: #2563EB;
}

.btn-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
