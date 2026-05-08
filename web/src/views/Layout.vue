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
        <div class="sidebar-icon" :class="{ active: $route.path === '/dashboard' }" @click="router.push('/dashboard')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="2" y="2" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
              <rect x="11" y="2" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
              <rect x="2" y="11" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
              <rect x="11" y="11" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            </svg>
          </div>
          <span class="nav-text">工作台</span>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/metrics' }" @click="router.push('/metrics')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M3 5V17M7 3V17M11 7V17M15 2V17M19 9V17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </div>
          <span class="nav-text">指标库</span>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/llm-ask-v2' }" @click="router.push('/llm-ask-v2')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="2" y="12" width="4" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
              <rect x="8" y="8" width="4" height="10" rx="1" stroke="currentColor" stroke-width="1.5"/>
              <rect x="14" y="4" width="4" height="14" rx="1" stroke="currentColor" stroke-width="1.5"/>
            </svg>
          </div>
          <span class="nav-text">智能问数</span>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/llm-ask-v2b' }" @click="router.push('/llm-ask-v2b')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/>
              <path d="M10 6V10L13 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <path d="M7 13C7.5 14 8.5 15 10 15C11.5 15 12.5 14 13 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </div>
          <span class="nav-text">问数 B 版</span>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/analysis' }" @click="router.push('/analysis')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M3 14L7 9L10 12L17 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <span class="nav-text">决策分析</span>
        </div>
      </nav>

      <!-- 底部区域：次要入口 + 用户 -->
      <div class="sidebar-bottom">
        <div class="sidebar-divider"></div>
        <!-- 次要入口 -->
        <div class="sidebar-icon" :class="{ active: $route.path === '/feedback' }" @click="router.push('/feedback')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M4 4H16V12H4V4Z" stroke="currentColor" stroke-width="1.5"/>
              <path d="M7 16H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <path d="M7 8L10 11L13 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <span class="nav-text">反馈看板</span>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/ask-analysis' }" @click="router.push('/ask-analysis')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M3 10L7 6L11 9L17 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M3 14L7 10L11 13L17 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.5"/>
            </svg>
          </div>
          <span class="nav-text">问数分析</span>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/nlp-config' }" @click="router.push('/nlp-config')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M4 6L10 4L16 6V14L10 16L4 14V6Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
              <path d="M8 8L12 10L8 12V8Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            </svg>
          </div>
          <span class="nav-text">意图配置</span>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path.startsWith('/config-center') }" @click="router.push('/config-center')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 2L18 6V14L10 18L2 14V6L10 2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
              <path d="M8 10L10 12L12 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <span class="nav-text">配置中心</span>
        </div>
        <div class="sidebar-icon" :class="{ active: $route.path === '/user-management' }" @click="router.push('/user-management')">
          <div class="icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="6" r="3" stroke="currentColor" stroke-width="1.5"/>
              <path d="M3 17C3 13.5 6 11 10 11C14 11 17 13.5 17 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </div>
          <span class="nav-text">用户管理</span>
        </div>
        <el-dropdown trigger="click" @command="handleUserCommand">
          <div class="user-avatar">
            {{ username ? username.charAt(0).toUpperCase() : 'U' }}
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon> 账号设置
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><SwitchButton /></el-icon> 退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="main-wrapper">
      <router-view :key="$route.fullPath" />
    </main>

    <!-- Mobile Hamburger -->
    <button class="hamburger" @click="toggleMobileMenu">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path d="M3 6H21M3 12H21M3 18H21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </button>

    <!-- Mobile Menu Overlay -->
    <div class="mobile-overlay" v-if="mobileMenuVisible" @click="toggleMobileMenu"></div>

    <!-- Mobile Menu Drawer -->
    <transition name="slide">
      <nav v-if="mobileMenuVisible" class="mobile-nav">
        <div class="mobile-nav-header">
          <span class="mobile-nav-title">导航菜单</span>
          <button class="close-btn" @click="toggleMobileMenu">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="mobile-nav-items">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="mobile-nav-item"
            :class="{ active: $route.path === item.path }"
            @click="toggleMobileMenu"
          >
            {{ item.label }}
          </router-link>
        </div>
      </nav>
    </transition>

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
import { SwitchButton, Setting } from '@element-plus/icons-vue'

const router = useRouter()
const $route = useRoute()
const showSettings = ref(false)

// 移动端菜单
const mobileMenuVisible = ref(false)
const toggleMobileMenu = () => {
  mobileMenuVisible.value = !mobileMenuVisible.value
}

// 导航配置
const navItems = [
  { label: '工作台', path: '/dashboard' },
  { label: '指标库', path: '/metrics' },
  { label: '智能问数', path: '/llm-ask-v2' },
  { label: '决策分析', path: '/analysis' },
  { label: '反馈看板', path: '/feedback' },
  { label: '问数分析', path: '/ask-analysis' },
  { label: '配置中心', path: '/config-center' },
]

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

function handleUserCommand(command) {
  if (command === 'logout') {
    ElMessage.success('已退出登录')
    localStorage.removeItem('access_token')
    window.location.href = '/login'
  } else if (command === 'settings') {
    showSettings.value = true
  }
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

/* Left Sidebar - Feishu Style */
.sidebar {
  width: 52px;
  background: #fff;
  border-right: 1px solid #E8E8E8;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
  transition: width 200ms ease;
  overflow: hidden;
}

.sidebar:hover {
  width: 140px;
}

.sidebar-logo {
  margin-bottom: 16px;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  padding: 0 10px;
}

.sidebar-logo svg {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 0;
  width: 100%;
}

.sidebar-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: #646A71;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  flex-shrink: 0;
}

.sidebar-icon:hover {
  background: #F5F6F7;
  color: #165DFF;
}

.sidebar-icon.active {
  background: #E8F0FF;
  color: #165DFF;
}

.sidebar-icon.active::after {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: #165DFF;
  border-radius: 0 2px 2px 0;
}

.sidebar-icon .icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
}

.sidebar-icon .nav-text {
  display: none;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

.sidebar:hover .sidebar-icon {
  width: auto;
  min-width: 44px;
}

.sidebar:hover .sidebar-icon .nav-text {
  display: block;
  padding-right: 16px;
}

.sidebar-bottom {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: auto;
  flex-shrink: 0;
  padding-top: 8px;
  border-top: 1px solid #F0F0F0;
  width: 100%;
}

.sidebar-divider {
  display: none;
}

/* Main Content - With Left Sidebar only */
.main-wrapper {
  flex: 1;
  margin-left: 52px;
  min-height: 100vh;
  transition: margin-left 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* User Avatar */
.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1677FF 0%, #0958D9 100%);
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
  box-shadow: 0 4px 12px rgba(22, 119, 255, 0.3);
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
    display: none;
  }
  .main-wrapper {
    margin-left: 0;
  }
  .hamburger {
    display: flex;
  }
}

/* Hamburger Button */
.hamburger {
  display: none;
  position: fixed;
  top: 16px;
  left: 16px;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 10px;
  cursor: pointer;
  color: #6366F1;
  z-index: 1001;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
  transition: all 0.2s ease;
}

.hamburger:hover {
  background: rgba(99, 102, 241, 0.08);
  transform: scale(1.05);
}

/* Mobile Overlay */
.mobile-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1002;
}

/* Mobile Navigation Drawer */
.mobile-nav {
  position: fixed;
  top: 0;
  left: 0;
  width: 280px;
  height: 100vh;
  background: #fff;
  z-index: 1003;
  display: flex;
  flex-direction: column;
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.15);
}

.mobile-nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(99, 102, 241, 0.1);
}

.mobile-nav-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f1f1f;
}

.close-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(99, 102, 241, 0.08);
  color: #6366F1;
}

.mobile-nav-items {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.mobile-nav-item {
  display: block;
  padding: 14px 16px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 500;
  color: #374151;
  text-decoration: none;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.mobile-nav-item:hover {
  background: rgba(99, 102, 241, 0.06);
  color: #6366F1;
}

.mobile-nav-item.active {
  background: rgba(99, 102, 241, 0.1);
  color: #6366F1;
}

/* Slide transition */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.25s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-100%);
}
</style>
