<template>
  <div v-if="visible" class="clarification-tags">
    <div class="clarification-message">
      <span class="message-icon">💡</span>
      <span class="message-text">{{ message }}</span>
    </div>
    <div class="tags-container">
      <el-tag
        v-for="option in options"
        :key="option.value"
        type="primary"
        class="clarification-tag"
        @click="handleSelect(option)"
      >
        {{ option.label }}
      </el-tag>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  message: {
    type: String,
    default: ''
  },
  options: {
    type: Array,
    default: () => []
  },
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['select'])

const handleSelect = (option) => {
  emit('select', option)
}
</script>

<style scoped>
.clarification-tags {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(22, 119, 255, 0.08) 0%, rgba(22, 119, 255, 0.04) 100%);
  border: 1px solid rgba(22, 119, 255, 0.2);
  border-radius: var(--radius-lg, 8px);
}

.clarification-message {
  display: flex;
  align-items: center;
  gap: 8px;
}

.message-icon {
  font-size: 16px;
}

.message-text {
  font-size: 14px;
  color: var(--text-primary, #1F1F1F);
  font-weight: 500;
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.clarification-tag {
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 6px 14px;
  font-weight: 500;
}

.clarification-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.25);
}
</style>
