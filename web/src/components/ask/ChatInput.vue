<template>
  <div class="chat-input-area">
    <div class="input-wrapper relative">
      <el-input
        ref="textareaRef"
        v-model="internalQuestion"
        :placeholder="placeholder || '输入您的问题...'"
        @keyup.enter="handleEnter"
        @input="handleInput"
        @paste="handlePaste"
        @keydown.up.prevent="handleNavigateUp"
        @keydown.down.prevent="handleNavigateDown"
        @keydown.enter.prevent="handleEnterKeydown"
        @keydown.tab.prevent="handleTab"
        @keydown.esc.stop="handleEsc"
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

      <!-- 维度联想下拉 -->
      <div
        v-if="showDimSuggestions && dimSuggestions.length"
        class="dim-suggestions-dropdown"
      >
        <div
          v-for="(item, idx) in dimSuggestions"
          :key="item.dimension_value"
          :class="[
            'dim-suggestion-item',
            { 'selected': idx === dimSelectedIndex }
          ]"
          @click="selectDimSuggestion(item)"
        >
          <span class="candidate-name">{{ item.dimension_value }}</span>
          <span class="candidate-code">[{{ item.dimension_field }}]</span>
        </div>
        <div class="keyboard-hint">
          <span v-if="singleMatch"><kbd>Tab</kbd> 补全</span>
          <span v-else><kbd>↑</kbd><kbd>↓</kbd> 导航</span>
          <span><kbd>Enter</kbd> 选择</span>
          <span><kbd>Esc</kbd> 关闭</span>
        </div>
      </div>

      <!-- / 快捷命令面板 -->
      <div
        v-if="showCommandPanel && commandList.length"
        class="command-panel"
      >
        <div class="command-header">
          <span>快捷命令</span>
          <span class="command-hint">选择后直接发送</span>
        </div>
        <div
          v-for="(cmd, idx) in commandList"
          :key="cmd.text"
          :class="['command-item', { 'selected': idx === commandSelectedIndex }]"
          @click="selectCommand(cmd)"
        >
          <span class="command-slash">/</span>
          <span class="command-text">{{ cmd.title }}</span>
        </div>
      </div>
    </div>
    <div class="input-hint">
      输入 <kbd>/</kbd> 唤起快捷命令，按 Enter 发送，Shift + Enter 换行
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface DimSuggestion {
  dimension_field: string
  dimension_value: string
}

interface Command {
  title: string
  text: string
}

const props = defineProps<{
  modelValue: string
  disabled: boolean
  suggestions: DimSuggestion[]
  showSuggestions: boolean
  selectedIndex: number
  placeholder?: string
  singleMatch: DimSuggestion | null
  commands?: Command[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  input: []
  'navigate-up': []
  'navigate-down': []
  'select-current': []
  'close-suggestions': []
  'select-suggestion': [item: DimSuggestion]
}>()

// 维度联想
const dimSuggestions = computed(() => props.suggestions)
const showDimSuggestions = computed(() => props.showSuggestions && props.suggestions.length)
const dimSelectedIndex = ref(0)

// / 快捷命令
const commandList = computed(() => props.commands || [])
const showCommandPanel = ref(false)
const commandSelectedIndex = ref(0)

const textareaRef = ref()

// 标记
let justSelectedSuggestion = false
let pasteDetected = false

const internalQuestion = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

function handleInput(e: Event) {
  if (pasteDetected) {
    pasteDetected = false
    return
  }

  const value = props.modelValue

  // 检测 / 触发快捷命令
  if (value === '/') {
    showCommandPanel.value = true
    commandSelectedIndex.value = 0
    emit('close-suggestions')
  } else if (showCommandPanel.value) {
    // 过滤命令
    if (value.startsWith('/')) {
      // 继续输入过滤
    } else {
      showCommandPanel.value = false
    }
  }

  emit('input')
}

function handlePaste(e: ClipboardEvent) {
  pasteDetected = true
  setTimeout(() => { pasteDetected = false }, 100)
}

function handleNavigateUp() {
  if (showCommandPanel.value) {
    commandSelectedIndex.value = commandSelectedIndex.value > 0
      ? commandSelectedIndex.value - 1
      : commandList.value.length - 1
  } else {
    emit('navigate-up')
  }
}

function handleNavigateDown() {
  if (showCommandPanel.value) {
    commandSelectedIndex.value = commandSelectedIndex.value < commandList.value.length - 1
      ? commandSelectedIndex.value + 1
      : 0
  } else {
    emit('navigate-down')
  }
}

function handleEnterKeydown(e: KeyboardEvent) {
  // 快捷命令面板优先
  if (showCommandPanel.value && commandList.value.length) {
    e.preventDefault()
    selectCommand(commandList.value[commandSelectedIndex.value])
    return
  }

  if (props.showSuggestions && props.suggestions.length) {
    const idx = props.selectedIndex >= 0 ? props.selectedIndex : 0
    emit('select-suggestion', props.suggestions[idx])
    justSelectedSuggestion = true
    setTimeout(() => { justSelectedSuggestion = false }, 100)
  } else {
    e.preventDefault()
  }
}

function handleTab(e: KeyboardEvent) {
  if (props.singleMatch && props.showSuggestions) {
    e.preventDefault()
    emit('select-suggestion', props.singleMatch)
  }
}

function handleEsc() {
  if (showCommandPanel.value) {
    showCommandPanel.value = false
  } else {
    emit('close-suggestions')
  }
}

function selectDimSuggestion(item: DimSuggestion) {
  emit('select-suggestion', item)
  justSelectedSuggestion = true
  setTimeout(() => { justSelectedSuggestion = false }, 100)
}

function selectCommand(cmd: Command) {
  // 直接发送该命令
  internalQuestion.value = cmd.text
  showCommandPanel.value = false
  // 自动发送
  setTimeout(() => {
    emit('send')
  }, 50)
}

function handleEnter(e: KeyboardEvent) {
  if (justSelectedSuggestion) {
    return
  }
  if (!e.shiftKey) {
    e.preventDefault()
    emit('send')
  }
}

// 暴露方法让父组件可以关闭命令面板
defineExpose({
  closeCommandPanel: () => { showCommandPanel.value = false }
})
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

.input-hint kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 16px;
  padding: 0 4px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-family: inherit;
  font-size: 10px;
  color: var(--text-secondary);
}

/* / 快捷命令面板 */
.command-panel {
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
  max-height: 280px;
  overflow-y: auto;
  animation: dropdownFadeInUp 0.15s ease-out;
}

.command-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-light);
  font-size: 12px;
  color: var(--text-muted);
}

.command-hint {
  font-size: 11px;
}

.command-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.1s ease;
  border-bottom: 1px solid var(--border-light);
}

.command-item:last-child {
  border-bottom: none;
}

.command-item:hover {
  background: var(--bg-primary);
}

.command-item.selected {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  color: white;
}

.command-slash {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
  width: 16px;
}

.command-item.selected .command-slash {
  color: white;
}

.command-text {
  font-size: 14px;
  color: var(--text-primary);
}

.command-item.selected .command-text {
  color: white;
}
</style>
