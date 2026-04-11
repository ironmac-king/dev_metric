<template>
  <div class="chat-input-area">
    <div class="input-wrapper relative">
      <el-input
        v-model="internalQuestion"
        :placeholder="placeholder || '输入您的问题...'"
        @keyup.enter="handleEnter"
        @input="handleInput"
        @paste="handlePaste"
        @keydown.up.prevent="$emit('navigate-up')"
        @keydown.down.prevent="$emit('navigate-down')"
        @keydown.enter.prevent="handleEnterKeydown"
        @keydown.tab.prevent="handleTab"
        @keydown.esc.stop="$emit('close-suggestions')"
        :disabled="disabled"
        resize="none"
        type="textarea"
        autosize
        class="chat-input"
      />
      <button class="send-btn cursor-pointer" @click="$emit('send')" :disabled="disabled || !internalQuestion.trim()">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M3 9L15 9M15 9L10 4M15 9L10 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>

      <!-- 候选下拉列表 -->
      <div
        v-if="showSuggestions && suggestions.length"
        class="dim-suggestions-dropdown"
      >
        <div
          v-for="(item, idx) in suggestions"
          :key="item.dimension_value"
          :class="[
            'dim-suggestion-item',
            { 'selected': idx === selectedIndex }
          ]"
          @click="$emit('select-suggestion', item)"
        >
          <span class="candidate-name">{{ item.dimension_value }}</span>
          <span class="candidate-code">[{{ item.dimension_field }}]</span>
        </div>
        <!-- 键盘导航提示 -->
        <div class="keyboard-hint">
          <span v-if="singleMatch"><kbd>Tab</kbd> 补全</span>
          <span v-else><kbd>↑</kbd><kbd>↓</kbd> 导航</span>
          <span><kbd>Enter</kbd> 选择</span>
          <span><kbd>Esc</kbd> 关闭</span>
        </div>
      </div>
    </div>
    <div class="input-hint">
      按 Enter 发送，Shift + Enter 换行
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Suggestion {
  dimension_field: string
  dimension_value: string
}

const props = defineProps<{
  modelValue: string
  disabled: boolean
  suggestions: Suggestion[]
  showSuggestions: boolean
  selectedIndex: number
  placeholder?: string
  singleMatch: Suggestion | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  input: []
  'navigate-up': []
  'navigate-down': []
  'select-current': []
  'close-suggestions': []
  'select-suggestion': [item: Suggestion]
}>()

// 标记：刚选择过联想词，阻止发送
let justSelectedSuggestion = false
// 标记：刚粘贴过，阻止触发联想
let pasteDetected = false

const internalQuestion = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

function handleInput(e: Event) {
  // 如果是粘贴操作，不触发联想
  if (pasteDetected) {
    pasteDetected = false
    return
  }
  emit('input')
}

function handlePaste(e: ClipboardEvent) {
  pasteDetected = true
  // 延迟重置标志
  setTimeout(() => { pasteDetected = false }, 100)
}

function handleEnterKeydown(e: KeyboardEvent) {
  // 如果有联想词显示，Enter 键用于选择联想词
  if (props.showSuggestions && props.suggestions.length) {
    const idx = props.selectedIndex >= 0 ? props.selectedIndex : 0
    emit('select-suggestion', props.suggestions[idx])
    justSelectedSuggestion = true
    // 延迟重置标记
    setTimeout(() => { justSelectedSuggestion = false }, 100)
  } else {
    // 没有联想词时，阻止默认换行行为
    e.preventDefault()
  }
}

function handleEnter(e: KeyboardEvent) {
  // 如果刚选择过联想词，不发送消息
  if (justSelectedSuggestion) {
    return
  }
  if (!e.shiftKey) {
    e.preventDefault()
    emit('send')
  }
}

function handleTab(e: KeyboardEvent) {
  // 如果有单一精确匹配，直接补全
  if (props.singleMatch && props.showSuggestions) {
    e.preventDefault()
    emit('select-suggestion', props.singleMatch)
  }
}
</script>

<style scoped>
.chat-input-area {
  padding: 14px 16px 18px;
  background: var(--bg-card);
  border-top: 1px solid var(--border);
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: var(--bg-card);
  border-radius: 8px;
  padding: 8px 8px 8px 16px;
  border: 1px solid var(--border);
  transition: all 0.15s ease;
}

.input-wrapper:focus-within {
  border-color: var(--primary);
}

/* Type-ahead 下拉框样式 - 固定向上展开 */
.dim-suggestions-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 6px);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 12px rgba(0, 0, 0, 0.08);
  z-index: 9999;
  overflow: hidden;
  max-height: 320px;
  overflow-y: auto;
  animation: dropdownFadeInUp 0.2s ease-out;
}

/* 箭头指示器 */
.dim-suggestions-dropdown::before {
  content: '';
  position: absolute;
  bottom: -6px;
  left: 20px;
  width: 10px;
  height: 10px;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  transform: rotate(45deg);
}

@keyframes dropdownFadeInUp {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.dim-suggestion-item {
  padding: 10px 14px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.15s ease;
  border-bottom: 1px solid var(--border-light);
}

.dim-suggestion-item:last-child {
  border-bottom: none;
}

.dim-suggestion-item:first-child {
  border-top-left-radius: 12px;
  border-top-right-radius: 12px;
}

.dim-suggestion-item:last-child {
  border-bottom-left-radius: 12px;
  border-bottom-right-radius: 12px;
}

.dim-suggestion-item:hover {
  background: var(--bg-primary);
}

.dim-suggestion-item.selected {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  color: white;
}

.dim-suggestion-item.selected .candidate-code {
  background: rgba(255, 255, 255, 0.25);
  color: rgba(255, 255, 255, 0.9);
}

.candidate-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.dim-suggestion-item.selected .candidate-name {
  color: white;
}

.candidate-code {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-primary);
  padding: 2px 8px;
  border-radius: 4px;
  transition: all 0.15s ease;
}

/* 键盘导航提示 */
.keyboard-hint {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 8px 14px;
  background: var(--bg-primary);
  border-top: 1px solid var(--border-light);
  font-size: 11px;
  color: var(--text-muted);
}

.keyboard-hint kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 5px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-family: inherit;
  font-size: 10px;
  color: var(--text-secondary);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.chat-input {
  flex: 1;
}

.chat-input :deep(.el-textarea__inner) {
  border: none;
  padding: 6px 0;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  box-shadow: none !important;
  background: transparent;
}

.send-btn {
  width: 40px;
  height: 36px;
  border: none;
  background: var(--primary);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-light);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-hint {
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
  margin-top: 8px;
}
</style>
