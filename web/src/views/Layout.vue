<template>
  <div class="app-layout">
    <!-- Left Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <rect x="2" y="14" width="6" height="12" rx="1.5" fill="url(#logoGrad7)"/>
          <rect x="11" y="8" width="6" height="18" rx="1.5" fill="url(#logoGrad7)" opacity="0.7"/>
          <rect x="20" y="2" width="6" height="24" rx="1.5" fill="url(#logoGrad7)" opacity="0.4"/>
          <defs>
            <linearGradient id="logoGrad7" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#6366F1"/>
              <stop offset="100%" stop-color="#8B5CF6"/>
            </linearGradient>
          </defs>
        </svg>
      </div>
      <nav class="sidebar-nav">
        <!-- 核心页面 -->
        <div class="sidebar-icon" :class="{ active: $route.path === '/dashboard' }" title="工作台" @click="router.push('/dashboard')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="2" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <rect x="11" y="2" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <rect x="2" y="11" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <rect x="11" y="11" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/metrics' }" title="指标库" @click="router.push('/metrics')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M3 5V17M7 3V17M11 7V17M15 2V17M19 9V17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/ai-assistant' }" title="AI 问数" @click="router.push('/ai-assistant')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/>
            <path d="M7 10H13M10 7V13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/llm-ask-v2' }" title="LLM.V2" @click="router.push('/llm-ask-v2')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="12" width="4" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
            <rect x="8" y="8" width="4" height="10" rx="1" stroke="currentColor" stroke-width="1.5"/>
            <rect x="14" y="4" width="4" height="14" rx="1" stroke="currentColor" stroke-width="1.5"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/analysis' }" title="决策分析" @click="router.push('/analysis')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M3 14L7 9L10 12L17 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
      </nav>

      <!-- 底部区域：次要入口 + 用户 -->
      <div class="sidebar-bottom">
        <div class="sidebar-divider"></div>
        <!-- 次要入口 -->
        <div class="sidebar-icon" :class="{ active: $route.path === '/feedback' }" title="反馈看板" @click="router.push('/feedback')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M4 4H16V12H4V4Z" stroke="currentColor" stroke-width="1.5"/>
            <path d="M7 16H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M7 8L10 11L13 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/alerts' }" title="告警配置" @click="router.push('/alerts')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 2C7.24 2 5 4.24 5 7V10L3 13V14H17V13L15 10V7C15 4.24 12.76 2 10 2Z" stroke="currentColor" stroke-width="1.5"/>
            <path d="M8 14V15C8 16.1 8.9 17 10 17C11.1 17 12 16.1 12 15V14H8Z" stroke="currentColor" stroke-width="1.5"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/llm-config' }" title="LLM配置" @click="router.push('/llm-config')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="2.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10 2V4.5M10 15.5V18M18 10H15.5M4.5 10H2M15.5 4.5L14 6M6 14L4.5 15.5M15.5 15.5L14 14M6 6L4.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/nlp-config' }" title="意图配置" @click="router.push('/nlp-config')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M4 6L10 4L16 6V14L10 16L4 14V6Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M8 8L12 10L8 12V8Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/starrocks-config' }" title="数据源配置" @click="router.push('/starrocks-config')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <ellipse cx="10" cy="6" rx="7" ry="3" stroke="currentColor" stroke-width="1.5"/>
            <path d="M3 6V12C3 14.2 6.13 16 10 16C13.87 16 17 14.2 17 12V6" stroke="currentColor" stroke-width="1.5"/>
            <path d="M3 12C3 14.2 6.13 16 10 16C13.87 16 17 14.2 17 12" stroke="currentColor" stroke-width="1.5"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/dimension-config' }" title="维度配置" @click="router.push('/dimension-config')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="3" y="3" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <rect x="11" y="3" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <rect x="3" y="11" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <rect x="11" y="11" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
          </svg>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/user-management' }" title="用户管理" @click="router.push('/user-management')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="6" r="3" stroke="currentColor" stroke-width="1.5"/>
            <path d="M3 17C3 13.5 6 11 10 11C14 11 17 13.5 17 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="user-avatar" @click="handleUserClick">
          {{ username ? username.charAt(0).toUpperCase() : 'U' }}
        </div>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="main-wrapper">
      <router-view />
    </main>

    <!-- Avatar Settings Dialog -->
    <el-dialog v-model="showSettings" title="头像设置" width="500px" class="avatar-dialog">
      <div class="avatar-settings">
        <div class="avatar-preview">
          <div class="avatar-large" :style="avatarStyle">
            <img v-if="selectedAvatar && presetAvatars.find(p => p.bg === selectedAvatar)?.type === 'cartoon'" :src="selectedAvatar" alt="avatar" style="width:100%;height:100%;border-radius:50%;" />
            <span v-else>{{ username ? username.charAt(0).toUpperCase() : 'U' }}</span>
          </div>
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
              :style="preset.type === 'gradient' ? { background: preset.bg } : {}"
              @click="selectPreset(preset)"
            >
              <img v-if="preset.type === 'cartoon'" :src="preset.bg" alt="avatar" style="width:100%;height:100%;border-radius:50%;" />
              <span v-else class="preset-letter" :style="{ color: preset.color }">{{ preset.letter }}</span>
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
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const $route = useRoute()
const showSettings = ref(false)

const username = computed(() => {
  const userInfo = localStorage.getItem('user_info')
  if (userInfo) {
    try {
      return JSON.parse(userInfo).username || ''
    } catch {
      return ''
    }
  }
  return ''
})

function handleUserClick() {
  showSettings.value = true
}

const selectedAvatar = ref('')
const customAvatar = ref('')

// 预设头像列表（帅哥美女卡通头像）
const presetAvatars = [
  // 渐变色头像
  { bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', letter: 'A', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', letter: 'B', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', letter: 'C', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', letter: 'D', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)', letter: 'E', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)', letter: 'F', color: '#333', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #d299c2 0%, #fef9d7 100%)', letter: 'G', color: '#333', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)', letter: 'H', color: '#fff', type: 'gradient' },
  // 卡通头像
  { bg: 'https://api.dicebear.com/7.x/lorelei/svg?seed=avatar1&backgroundColor=ffdfbf', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/lorelei/svg?seed=avatar2&backgroundColor=c0aede', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/lorelei/svg?seed=avatar3&backgroundColor=d1d4f9', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/micah/svg?seed=avatar4&backgroundColor=ffd5dc', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/micah/svg?seed=avatar5&backgroundColor=b6e3f4', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/micah/svg?seed=avatar6&backgroundColor=ffedef', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/avataaars/svg?seed=avatar7&backgroundColor=c0aede', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/avataaars/svg?seed=avatar8&backgroundColor=ffd5dc', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/personas/svg?seed=avatar9&backgroundColor=b6e3f4', letter: '', color: '', type: 'cartoon' },
  { bg: 'https://api.dicebear.com/7.x/personas/svg?seed=avatar10&backgroundColor=ffedef', letter: '', color: '', type: 'cartoon' },
]

const avatarStyle = computed(() => {
  if (customAvatar.value) {
    return {
      backgroundImage: `url(${customAvatar.value})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      color: 'transparent'
    }
  }
  const preset = presetAvatars.find(p => p.bg === selectedAvatar.value)
  if (preset) {
    if (preset.type === 'cartoon') {
      return {
        backgroundImage: `url(${preset.bg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        color: 'transparent'
      }
    }
    return { background: preset.bg }
  }
  return { background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }
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
  /* Primary Colors */
  --primary: #1677FF;
  --primary-light: #4096FF;
  --primary-dark: #0958D9;
  --primary-glow: rgba(22, 119, 255, 0.12);

  /* CTA */
  --cta: #00A870;
  --cta-hover: #007B50;

  /* Backgrounds */
  --bg-primary: #F2F3F5;
  --bg-card: #FFFFFF;
  --bg-sidebar: #FFFFFF;
  --bg-sidebar-hover: rgba(22, 119, 255, 0.06);
  --bg-sidebar-active: rgba(22, 119, 255, 0.12);

  /* Text */
  --text-primary: #1F1F1F;
  --text-secondary: #666666;
  --text-muted: #999999;

  /* Borders */
  --border: #E8E8E8;
  --border-light: #F5F5F5;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.08);

  /* Border Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 10px;
  --radius-2xl: 12px;

  /* Transitions */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.2s ease;
  --transition-bounce: 0.25s ease;

  /* Layout */
  --header-height: 60px;
}

.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Left Sidebar */
.sidebar {
  width: 64px;
  background: #fff;
  border-right: 1px solid rgba(99, 102, 241, 0.08);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0;
  box-shadow: 4px 0 20px rgba(99, 102, 241, 0.04);
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
  transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.sidebar:hover {
  width: 160px;
}

.sidebar-logo {
  margin-bottom: 28px;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 0;
  width: 100%;
}

.sidebar-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  margin: 0 auto;
  flex-shrink: 0;
}

.sidebar-icon::before {
  content: attr(title);
  position: absolute;
  left: 56px;
  background: #1f1f1f;
  color: #fff;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
  z-index: 1000;
}

.sidebar-icon:hover::before {
  opacity: 1;
}

.sidebar-icon:hover {
  background: rgba(99, 102, 241, 0.08);
  color: #6366F1;
}

.sidebar-icon.active {
  background: rgba(99, 102, 241, 0.08);
  color: #6366F1;
  border-left: 3px solid #6366F1;
}

.sidebar-bottom {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: auto;
  flex-shrink: 0;
}

.sidebar-divider {
  width: 32px;
  height: 1px;
  background: rgba(99, 102, 241, 0.15);
  margin: 8px auto;
}

/* Main Content - With Left Sidebar only */
.main-wrapper {
  flex: 1;
  margin-left: 64px;
  min-height: 100vh;
  transition: margin-left 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* User Avatar */
.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-avatar:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
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
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 700;
  color: #ffffff;
  box-shadow: 0 4px 16px rgba(22, 119, 255, 0.3);
  overflow: hidden;
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

/* ========================================
   Responsive Design
   ======================================== */

@media (max-width: 1024px) {
  .sidebar {
    width: 56px;
  }
  .sidebar:hover {
    width: 56px;
  }
  .sidebar-icon::before {
    display: none;
  }
  .sidebar-logo svg {
    width: 24px;
    height: 24px;
  }
  .sidebar-icon {
    width: 36px;
    height: 36px;
  }
  .sidebar-icon svg {
    width: 18px;
    height: 18px;
  }
  .main-wrapper {
    margin-left: 56px;
  }
}

@media (max-width: 768px) {
  .sidebar {
    width: 48px;
  }
  .sidebar:hover {
    width: 48px;
  }
  .sidebar-logo {
    display: none;
  }
  .sidebar-icon {
    width: 32px;
    height: 32px;
  }
  .sidebar-icon svg {
    width: 16px;
    height: 16px;
  }
  .sidebar-divider {
    width: 28px;
  }
  .user-avatar {
    width: 28px;
    height: 28px;
    font-size: 11px;
  }
  .main-wrapper {
    margin-left: 48px;
  }
}
</style>
