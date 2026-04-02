<template>
  <el-drawer
    v-model="visible"
    title="偏好设置"
    direction="rtl"
    size="320px"
    :before-close="handleClose"
  >
    <div class="preferences-content">
      <!-- 主题 -->
      <div class="pref-section">
        <h4 class="pref-title">主题</h4>
        <div class="pref-options">
          <div
            class="pref-option"
            :class="{ active: preferences.theme === 'light' }"
            @click="updatePref('theme', 'light')"
          >
            <div class="option-preview light">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="10" r="4" stroke="currentColor" stroke-width="1.5"/>
                <path d="M10 2V4M10 16V18M2 10H4M16 10H18M4.5 4.5L5.8 5.8M14.2 14.2L15.5 15.5M4.5 15.5L5.8 14.2M14.2 5.8L15.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </div>
            <span>浅色</span>
          </div>
          <div
            class="pref-option"
            :class="{ active: preferences.theme === 'dark' }"
            @click="updatePref('theme', 'dark')"
          >
            <div class="option-preview dark">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M17 10.5C16.5 14 13.5 16.5 10 16.5C6 16.5 3 13.5 3 10.5C3 7 6 4 10 4C13.5 4 16.5 6.5 17 10.5Z" stroke="currentColor" stroke-width="1.5"/>
              </svg>
            </div>
            <span>深色</span>
          </div>
        </div>
      </div>

      <!-- 消息样式 -->
      <div class="pref-section">
        <h4 class="pref-title">消息样式</h4>
        <div class="pref-options">
          <div
            class="pref-option"
            :class="{ active: preferences.message_style === 'bubbles' }"
            @click="updatePref('message_style', 'bubbles')"
          >
            <div class="option-preview bubble-preview">
              <div class="bubble bubble-left"></div>
              <div class="bubble bubble-right"></div>
            </div>
            <span>气泡</span>
          </div>
          <div
            class="pref-option"
            :class="{ active: preferences.message_style === 'cards' }"
            @click="updatePref('message_style', 'cards')"
          >
            <div class="option-preview card-preview">
              <div class="msg-card left"></div>
              <div class="msg-card right"></div>
            </div>
            <span>卡片</span>
          </div>
        </div>
      </div>

      <!-- 字体大小 -->
      <div class="pref-section">
        <h4 class="pref-title">字体大小</h4>
        <div class="pref-options">
          <div
            class="pref-option text-option small"
            :class="{ active: preferences.font_size === 'small' }"
            @click="updatePref('font_size', 'small')"
          >
            <span>A</span>
            <span>小</span>
          </div>
          <div
            class="pref-option text-option medium"
            :class="{ active: preferences.font_size === 'medium' }"
            @click="updatePref('font_size', 'medium')"
          >
            <span>A</span>
            <span>中</span>
          </div>
          <div
            class="pref-option text-option large"
            :class="{ active: preferences.font_size === 'large' }"
            @click="updatePref('font_size', 'large')"
          >
            <span>A</span>
            <span>大</span>
          </div>
        </div>
      </div>

      <!-- 显示设置 -->
      <div class="pref-section">
        <h4 class="pref-title">显示设置</h4>
        <div class="pref-toggles">
          <div class="toggle-item">
            <span>显示思考过程</span>
            <el-switch
              :model-value="preferences.show_thinking"
              @change="updatePref('show_thinking', $event)"
            />
          </div>
          <div class="toggle-item">
            <span>紧凑模式</span>
            <el-switch
              :model-value="preferences.compact_mode"
              @change="updatePref('compact_mode', $event)"
            />
          </div>
        </div>
      </div>

      <!-- 快捷问题管理 -->
      <div class="pref-section">
        <div class="section-header">
          <h4 class="pref-title">快捷问题</h4>
          <el-button size="small" @click="showShortcutEditor = true">编辑</el-button>
        </div>
        <div class="shortcut-list">
          <div v-for="(s, i) in shortcuts" :key="i" class="shortcut-item">
            <span class="shortcut-icon">{{ s.icon }}</span>
            <span class="shortcut-text">{{ s.question_text }}</span>
          </div>
        </div>
      </div>

      <!-- 快捷问题编辑对话框 -->
      <el-dialog v-model="showShortcutEditor" title="编辑快捷问题" width="500px">
        <div class="shortcut-editor">
          <div v-for="(s, i) in editingShortcuts" :key="i" class="shortcut-edit-row">
            <el-input v-model="s.icon" placeholder="图标" class="icon-input" />
            <el-input v-model="s.question_text" placeholder="问题文本" class="text-input" />
            <el-button type="danger" size="small" @click="removeShortcut(i)">删除</el-button>
          </div>
          <el-button type="primary" size="small" @click="addShortcut">添加</el-button>
        </div>
        <template #footer>
          <el-button @click="showShortcutEditor = false">取消</el-button>
          <el-button type="primary" @click="saveShortcuts">保存</el-button>
        </template>
      </el-dialog>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { askAPI } from '@/api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(false)

const preferences = ref({
  theme: 'light',
  message_style: 'bubbles',
  font_size: 'medium',
  show_thinking: true,
  compact_mode: false
})

const shortcuts = ref([])
const showShortcutEditor = ref(false)
const editingShortcuts = ref([])

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    loadPreferences()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

async function loadPreferences() {
  try {
    const [prefRes, shortcutRes] = await Promise.all([
      askAPI.getPreferences(),
      askAPI.getShortcuts()
    ])

    if (prefRes.data) {
      preferences.value = { ...preferences.value, ...prefRes.data }
      applyTheme(preferences.value.theme)
    }

    if (shortcutRes.data) {
      shortcuts.value = shortcutRes.data
      editingShortcuts.value = JSON.parse(JSON.stringify(shortcutRes.data))
    }
  } catch (e) {
    console.error('加载偏好设置失败:', e)
  }
}

async function updatePref(key, value) {
  const oldValue = preferences.value[key]
  preferences.value[key] = value

  // 立即应用主题变化
  if (key === 'theme') {
    applyTheme(value)
  }

  try {
    await askAPI.updatePreferences({ [key]: value })
  } catch (e) {
    // 回滚
    preferences.value[key] = oldValue
    if (key === 'theme') {
      applyTheme(oldValue)
    }
    ElMessage.error('保存失败')
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('ask_theme', theme)
}

function handleClose() {
  visible.value = false
}

// 快捷问题管理
function addShortcut() {
  editingShortcuts.value.push({ icon: '📊', question_text: '', sort_order: editingShortcuts.value.length + 1, status: 1 })
}

function removeShortcut(index) {
  editingShortcuts.value.splice(index, 1)
}

async function saveShortcuts() {
  try {
    // 简单实现：删除旧的，创建新的
    // 实际生产环境应该使用批量更新
    for (const s of shortcuts.value) {
      if (s.id) {
        await askAPI.deleteShortcut(s.id)
      }
    }
    for (const s of editingShortcuts.value) {
      await askAPI.createShortcut(s)
    }
    shortcuts.value = JSON.parse(JSON.stringify(editingShortcuts.value))
    showShortcutEditor.value = false
    ElMessage.success('保存成功')
  } catch (e) {
    console.error('保存快捷问题失败:', e)
    ElMessage.error('保存失败')
  }
}
</script>

<style scoped>
.preferences-content {
  padding: 0 16px;
}

.pref-section {
  margin-bottom: 28px;
}

.pref-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.pref-options {
  display: flex;
  gap: 10px;
}

.pref-option {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.pref-option:hover {
  border-color: var(--border-color);
}

.pref-option.active {
  border-color: var(--accent);
  background: var(--bg-active);
}

.pref-option span:last-child {
  font-size: 12px;
  color: var(--text-primary);
}

.option-preview {
  width: 48px;
  height: 36px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.option-preview.light {
  background: #F5F5F5;
  color: #333;
}

.option-preview.dark {
  background: #1E1E1E;
  color: #E8E8E8;
}

.bubble-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.bubble-preview .bubble {
  height: 8px;
  border-radius: 4px;
}

.bubble-preview .bubble-left {
  width: 28px;
  background: #E8E8E8;
}

.bubble-preview .bubble-right {
  width: 20px;
  background: #1677FF;
}

.card-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.card-preview .msg-card {
  height: 8px;
  border-radius: 2px;
}

.card-preview .msg-card.left {
  width: 28px;
  background: #E8E8E8;
}

.card-preview .msg-card.right {
  width: 20px;
  background: #1677FF;
}

.text-option {
  padding: 12px 8px;
}

.text-option span:first-child {
  font-weight: 600;
}

.text-option.small span:first-child {
  font-size: 14px;
}

.text-option.medium span:first-child {
  font-size: 18px;
}

.text-option.large span:first-child {
  font-size: 22px;
}

.pref-toggles {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toggle-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}

.toggle-item span {
  font-size: 13px;
  color: var(--text-primary);
}

/* 快捷问题管理 */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-header .pref-title {
  margin-bottom: 0;
}

.shortcut-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shortcut-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
}

.shortcut-icon {
  font-size: 16px;
}

.shortcut-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
}

/* 快捷问题编辑器 */
.shortcut-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.shortcut-edit-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.shortcut-edit-row .icon-input {
  width: 60px;
  flex-shrink: 0;
}

.shortcut-edit-row .text-input {
  flex: 1;
}
</style>
