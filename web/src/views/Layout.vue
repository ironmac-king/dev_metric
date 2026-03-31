<template>
  <div class="app-layout">
    <!-- Dark Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="2" y="14" width="6" height="12" rx="1.5" fill="#6366F1"/>
            <rect x="11" y="8" width="6" height="18" rx="1.5" fill="#6366F1" opacity="0.7"/>
            <rect x="20" y="2" width="6" height="24" rx="1.5" fill="#6366F1" opacity="0.4"/>
          </svg>
          <span class="logo-text">Metrics</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section">
          <span class="nav-section-label">工作台</span>
          <router-link to="/dashboard" class="nav-item" :class="{ active: $route.path === '/dashboard' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <rect x="2" y="2" width="6" height="6" rx="1.5" fill="currentColor" opacity="0.9"/>
              <rect x="10" y="2" width="6" height="6" rx="1.5" fill="currentColor" opacity="0.6"/>
              <rect x="2" y="10" width="6" height="6" rx="1.5" fill="currentColor" opacity="0.6"/>
              <rect x="10" y="10" width="6" height="6" rx="1.5" fill="currentColor" opacity="0.3"/>
            </svg>
            <span>Dashboard</span>
          </router-link>
          <router-link to="/metrics" class="nav-item" :class="{ active: $route.path === '/metrics' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M3 12L6.5 7.5L10 9.5L15 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="15" cy="4" r="1.5" fill="currentColor"/>
            </svg>
            <span>指标管理</span>
          </router-link>
          <router-link to="/alerts" class="nav-item" :class="{ active: $route.path === '/alerts' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 2C6.8 2 5 3.5 5 6V10L3.5 12.5V13.5H14.5V12.5L13 10V6C13 3.5 11.2 2 9 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M7.5 13.5V14.5C7.5 15.3 8.2 16 9 16C9.8 16 10.5 15.3 10.5 14.5V13.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span>告警配置</span>
          </router-link>
        </div>

        <div class="nav-section">
          <span class="nav-section-label">智能分析</span>
          <router-link to="/ai-assistant" class="nav-item" :class="{ active: $route.path === '/ai-assistant' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="1.5"/>
              <circle cx="9" cy="6" r="1.5" fill="currentColor"/>
              <path d="M6.5 10.5C6.5 10.5 7.5 13 9 13C10.5 13 11.5 10.5 11.5 10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span>AI 问数</span>
          </router-link>
          <router-link to="/ask" class="nav-item" :class="{ active: $route.path === '/ask' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M3 6C3 4.3 4.3 3 6 3H12C13.7 3 15 4.3 15 6V10C15 11.7 13.7 13 12 13H9L6 16V13H6C4.3 13 3 11.7 3 10V6Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="6" cy="7.5" r="0.75" fill="currentColor"/>
              <circle cx="8" cy="7.5" r="0.75" fill="currentColor"/>
              <circle cx="10" cy="7.5" r="0.75" fill="currentColor"/>
            </svg>
            <span>智能问数</span>
          </router-link>
        </div>

        <div class="nav-section">
          <span class="nav-section-label">系统配置</span>
          <router-link to="/llm-config" class="nav-item" :class="{ active: $route.path === '/llm-config' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <circle cx="4" cy="9" r="1.5" fill="currentColor"/>
              <circle cx="9" cy="4" r="1.5" fill="currentColor" opacity="0.7"/>
              <circle cx="9" cy="14" r="1.5" fill="currentColor" opacity="0.7"/>
              <circle cx="14" cy="9" r="1.5" fill="currentColor" opacity="0.5"/>
            </svg>
            <span>LLM 配置</span>
          </router-link>
          <router-link to="/nlp-config" class="nav-item" :class="{ active: $route.path === '/nlp-config' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M3 5L9 3L15 5V13L9 15L3 13V5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
              <path d="M6.5 9L8 10.5L11.5 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>意图配置</span>
          </router-link>
          <router-link to="/starrocks-config" class="nav-item" :class="{ active: $route.path === '/starrocks-config' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <ellipse cx="9" cy="9" rx="7" ry="4" stroke="currentColor" stroke-width="1.5"/>
              <ellipse cx="9" cy="5" rx="7" ry="4" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
              <ellipse cx="9" cy="13" rx="7" ry="4" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
            </svg>
            <span>数据源配置</span>
          </router-link>
          <router-link to="/dimension-config" class="nav-item" :class="{ active: $route.path === '/dimension-config' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <rect x="2" y="2" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
              <rect x="10" y="2" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
              <rect x="2" y="10" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
              <rect x="10" y="10" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
            </svg>
            <span>维度配置</span>
          </router-link>
          <router-link to="/prompt-config" class="nav-item" :class="{ active: $route.path === '/prompt-config' }">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M3 3h12v12H3V3z" stroke="currentColor" stroke-width="1.5"/>
              <path d="M6 7h6M6 10h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span>Prompt配置</span>
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer">
        <div class="user-info" @click="showSettings = true">
          <div class="avatar" :style="avatarStyle">A</div>
          <div class="user-details">
            <span class="user-name">Admin</span>
            <span class="user-role">管理员</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="main-wrapper">
      <router-view />
    </main>

    <!-- Avatar Settings Dialog -->
    <el-dialog v-model="showSettings" title="头像设置" width="420px" class="avatar-dialog">
      <div class="avatar-settings">
        <div class="avatar-preview">
          <div class="avatar-large" :style="avatarStyle">A</div>
          <span class="avatar-hint">点击选择或上传头像</span>
        </div>

        <div class="preset-avatars">
          <div class="preset-label">预设头像</div>
          <div class="preset-grid">
            <div
              v-for="(preset, index) in presetAvatars"
              :key="index"
              class="preset-item"
              :class="{ active: selectedAvatar === preset.bg }"
              :style="{ background: preset.bg }"
              @click="selectPreset(preset)"
            >
              <span class="preset-letter">{{ preset.letter }}</span>
            </div>
          </div>
        </div>

        <div class="upload-section">
          <div class="upload-label">自定义上传</div>
          <el-upload
            class="avatar-uploader"
            :show-file-list="false"
            :before-upload="handleUpload"
            accept="image/*"
          >
            <el-button class="upload-btn">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 3V10M8 3L5 6M8 3L11 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M2 11V12C2 12.5 2.4 13 3 13H13C13.6 13 14 12.5 14 12V11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
              上传图片
            </el-button>
          </el-upload>
          <span class="upload-hint">支持 JPG、PNG，建议尺寸 128x128</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const showSettings = ref(false)
const selectedAvatar = ref('')
const customAvatar = ref('')

const presetAvatars = [
  { bg: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)', letter: 'A', color: '#fff' },
  { bg: 'linear-gradient(135deg, #00A870 0%, #007B50 100%)', letter: 'B', color: '#fff' },
  { bg: 'linear-gradient(135deg, #722ED1 0%, #4A1080 100%)', letter: 'C', color: '#fff' },
  { bg: 'linear-gradient(135deg, #F5222D 0%, #C41230 100%)', letter: 'D', color: '#fff' },
  { bg: 'linear-gradient(135deg, #FA8C16 0%, #D46B08 100%)', letter: 'E', color: '#fff' },
  { bg: 'linear-gradient(135deg, #52C41A 0%, #389E0D 100%)', letter: 'F', color: '#fff' },
  { bg: 'linear-gradient(135deg, #13C2C2 0%, #08979C 100%)', letter: 'G', color: '#fff' },
  { bg: 'linear-gradient(135deg, #FA541C 0%, #C54B1C 100%)', letter: 'H', color: '#fff' },
]

const avatarStyle = computed(() => {
  if (customAvatar.value) {
    return {
      background: `url(${customAvatar.value}) center/cover`,
      color: 'transparent'
    }
  }
  const preset = presetAvatars.find(p => p.bg === selectedAvatar.value)
  if (preset) {
    return { background: preset.bg }
  }
  return { background: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)' }
})

function selectPreset(preset) {
  selectedAvatar.value = preset.bg
  customAvatar.value = ''
  saveAvatarConfig()
}

function handleUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    customAvatar.value = e.target.result
    selectedAvatar.value = ''
    saveAvatarConfig()
  }
  reader.readAsDataURL(file)
  return false
}

function saveAvatarConfig() {
  localStorage.setItem('user_avatar_preset', selectedAvatar.value)
  localStorage.setItem('user_avatar_custom', customAvatar.value)
}

function loadAvatarConfig() {
  selectedAvatar.value = localStorage.getItem('user_avatar_preset') || ''
  customAvatar.value = localStorage.getItem('user_avatar_custom') || ''
}

// Provide avatar style globally for other components
window.getAvatarStyle = () => {
  if (customAvatar.value) {
    return {
      background: `url(${customAvatar.value}) center/cover`,
      color: 'transparent'
    }
  }
  const preset = presetAvatars.find(p => p.bg === selectedAvatar.value)
  if (preset) {
    return { background: preset.bg }
  }
  return { background: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)' }
}

onMounted(() => {
  loadAvatarConfig()
})
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  /* ========================================
     DingTalk Style Design System
     钉钉风格 - 专业企业蓝 + 高效信息密度
     ======================================== */

  /* Primary Colors - DingTalk Blue 钉钉蓝 */
  --primary: #1677FF;
  --primary-light: #4096FF;
  --primary-dark: #0958D9;
  --primary-glow: rgba(22, 119, 255, 0.12);

  /* CTA - Enterprise Green */
  --cta: #00A870;
  --cta-hover: #007B50;

  /* Backgrounds - Clean White */
  --bg-primary: #F2F3F5;
  --bg-card: #FFFFFF;
  --bg-sidebar: #FFFFFF;
  --bg-sidebar-hover: rgba(22, 119, 255, 0.06);
  --bg-sidebar-active: rgba(22, 119, 255, 0.12);

  /* Text - Professional */
  --text-primary: #1F1F1F;
  --text-secondary: #666666;
  --text-muted: #999999;
  --text-sidebar: #1F1F1F;
  --text-sidebar-muted: #666666;

  /* Borders */
  --border: #E8E8E8;
  --border-light: #F5F5F5;

  /* ========================================
     DingTalk Shadows - 轻淡专业
     ======================================== */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.08);

  /* 卡片阴影 - 轻淡 */
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.04),
                 0 4px 12px rgba(0, 0, 0, 0.03);
  --shadow-card-hover: 0 2px 8px rgba(0, 0, 0, 0.06),
                    0 8px 24px rgba(0, 0, 0, 0.05);

  /* 按钮阴影 */
  --shadow-btn: 0 2px 8px rgba(22, 119, 255, 0.25);

  /* ========================================
     Border Radius - 简洁中等圆角
     ======================================== */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 10px;
  --radius-2xl: 12px;

  /* ========================================
     DingTalk 动画系统 - 快速轻巧
     ======================================== */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.2s ease;
  --transition-bounce: 0.25s ease;

  /* ========================================
     Legacy Aliases
     ======================================== */
  --sidebar-bg: var(--bg-sidebar);
  --sidebar-hover: var(--bg-sidebar-hover);
  --sidebar-active: var(--bg-sidebar-active);
  --accent: var(--primary);
  --accent-light: var(--primary-light);
}

.app-layout {
  min-height: 100vh;
  display: flex;
  background: var(--bg-primary);
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Sidebar - DingTalk Style */
.sidebar {
  width: 240px;
  background: var(--bg-sidebar);
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  display: flex;
  flex-direction: column;
  z-index: 100;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
  border-right: 1px solid var(--border);
}

.sidebar-header {
  padding: 20px 16px;
  border-bottom: 1px solid var(--border);
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.5px;
}

.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
}

.nav-section {
  margin-bottom: 28px;
}

.nav-section-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-sidebar-muted);
  padding: 0 12px;
  margin-bottom: 10px;
  opacity: 0.7;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  color: var(--text-sidebar-muted);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-decoration: none;
  margin-bottom: 2px;
  position: relative;
}

.nav-item:hover {
  background: var(--bg-sidebar-hover);
  color: var(--text-sidebar);
}

.nav-item.active {
  background: var(--bg-sidebar-active);
  color: var(--primary-light);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 24px;
  background: var(--primary);
  border-radius: 0 4px 4px 0;
  box-shadow: 0 0 12px var(--primary);
}

.nav-item.active svg {
  color: var(--primary-light);
}

.nav-item svg {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  transition: all var(--transition-normal);
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border-radius: var(--radius-md);
  transition: all 0.2s ease;
  cursor: pointer;
}

.user-info:hover {
  background: var(--bg-sidebar-hover);
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-sidebar);
}

.user-role {
  font-size: 12px;
  color: var(--text-sidebar-muted);
}

/* Main Content */
.main-wrapper {
  flex: 1;
  margin-left: 260px;
  min-height: 100vh;
}

/* Avatar Settings Dialog */
.avatar-settings {
  padding: 8px 0;
}

.avatar-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  margin-bottom: 24px;
}

.avatar-large {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: linear-gradient(135deg, #1677FF 0%, #0055E5 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 700;
  color: #ffffff;
  box-shadow: 0 4px 16px rgba(22, 119, 255, 0.3);
}

.avatar-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.preset-avatars {
  margin-bottom: 24px;
}

.preset-label,
.upload-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.preset-item {
  aspect-ratio: 1;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
}

.preset-item:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.preset-item.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.2);
}

.preset-letter {
  font-size: 24px;
  font-weight: 700;
  color: #ffffff;
}

.upload-section {
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: var(--bg-card);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.upload-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.upload-hint {
  display: block;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.avatar-uploader {
  display: inline-block;
}

/* Dialog Styles */
.avatar-dialog :deep(.el-dialog__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.avatar-dialog :deep(.el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.avatar-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.avatar-dialog :deep(.el-dialog__footer) {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}
</style>
