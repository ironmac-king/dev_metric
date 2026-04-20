<template>
  <header class="app-header">
    <!-- Logo -->
    <div class="header-logo">
      <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
        <rect x="2" y="14" width="6" height="12" rx="1.5" fill="#6366F1"/>
        <rect x="11" y="8" width="6" height="18" rx="1.5" fill="#6366F1" opacity="0.7"/>
        <rect x="20" y="2" width="6" height="24" rx="1.5" fill="#6366F1" opacity="0.4"/>
      </svg>
      <span class="logo-text">Metrics</span>
    </div>

    <!-- Navigation -->
    <nav class="header-nav">
      <div
        v-for="item in navItems"
        :key="item.path"
        class="nav-item-wrapper"
      >
        <router-link
          v-if="!item.children"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          {{ item.label }}
        </router-link>

        <el-dropdown v-else trigger="hover" @command="(path) => router.push(path)">
          <span class="nav-item nav-dropdown" :class="{ active: isActiveGroup(item.children) }">
            {{ item.label }}
            <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="child in item.children"
                :key="child.path"
                :command="child.path"
                :class="{ active: $route.path === child.path }"
              >
                {{ child.label }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </nav>

    <!-- Right Actions -->
    <div class="header-actions">
      <!-- Notification -->
      <el-badge :value="3" class="notification-badge">
        <el-icon class="action-icon"><Bell /></el-icon>
      </el-badge>

      <!-- User Dropdown -->
      <el-dropdown trigger="click" @command="handleUserCommand">
        <div class="user-trigger">
          <div class="avatar" :style="avatarStyle">
            <img v-if="selectedAvatar && presetAvatars.find(p => p.bg === selectedAvatar)?.type === 'cartoon'" :src="selectedAvatar" alt="avatar" style="width:100%;height:100%;border-radius:50%;" />
            <span v-else>{{ username ? username.charAt(0).toUpperCase() : 'U' }}</span>
          </div>
          <span class="username">{{ username }}</span>
          <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
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

    <!-- Mobile Hamburger -->
    <button class="hamburger" @click="toggleMobileMenu">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path d="M3 6H21M3 12H21M3 18H21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </button>

    <!-- Mobile Menu Overlay -->
    <div class="mobile-overlay" v-if="mobileMenuVisible" @click="toggleMobileMenu"></div>

    <!-- Mobile Menu -->
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

        <div v-for="item in navItems" :key="item.path" class="mobile-nav-section">
          <template v-if="!item.children">
            <router-link :to="item.path" class="mobile-nav-item" :class="{ active: $route.path === item.path }" @click="toggleMobileMenu">
              {{ item.label }}
            </router-link>
          </template>
          <template v-else>
            <span class="mobile-nav-section-label">{{ item.label }}</span>
            <router-link
              v-for="child in item.children"
              :key="child.path"
              :to="child.path"
              class="mobile-nav-item child"
              :class="{ active: $route.path === child.path }"
              @click="toggleMobileMenu"
            >
              {{ child.label }}
            </router-link>
          </template>
        </div>
      </nav>
    </transition>
  </header>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { authAPI, menuAPI } from '../../api'
import { ElMessage } from 'element-plus'
import { ArrowDown, Bell, Setting, SwitchButton } from '@element-plus/icons-vue'

const router = useRouter()
const $route = useRoute()

// 导航配置
const navItems = [
  { label: '工作台', path: '/dashboard' },
  { label: '指标库', path: '/metrics' },
  {
    label: '智能问数',
    children: [
      { label: 'AI 问数', path: '/ai-assistant' },
      { label: 'LLM.V1', path: '/llm-ask' },
      { label: 'LLM.V2', path: '/llm-ask-v2' },
      { label: '问数分析', path: '/ask-analysis' },
      { label: '决策分析', path: '/analysis' },
    ]
  },
  {
    label: '系统配置',
    children: [
      { label: '告警配置', path: '/alerts' },
      { label: 'LLM 配置', path: '/llm-config' },
      { label: '意图配置', path: '/nlp-config' },
      { label: '数据源配置', path: '/starrocks-config' },
      { label: '维度配置', path: '/dimension-config' },
      { label: '用户管理', path: '/user-management' },
      { label: '角色权限', path: '/role-permission' },
    ]
  },
]

// 检查分组是否激活
function isActiveGroup(children) {
  return children?.some(c => $route.path === c.path)
}

// 用户菜单权限
const userMenus = ref([])

async function fetchUserMenus() {
  try {
    const res = await menuAPI.getMyMenus()
    userMenus.value = res.data || []
  } catch (e) {
    console.error('获取菜单权限失败:', e)
    userMenus.value = []
  }
}

// 用户角色
const userRole = computed(() => {
  const userInfo = localStorage.getItem('user_info')
  if (userInfo) {
    try {
      return JSON.parse(userInfo).role || 'user'
    } catch {
      return 'user'
    }
  }
  return 'user'
})

// 用户名
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

// 检查用户是否有某个菜单的权限
function hasMenu(path) {
  if (userRole.value === 'admin') return true
  if (userMenus.value.length === 0) {
    if (userRole.value === 'analyst') {
      return ['/dashboard', '/metrics', '/alerts', '/ai-assistant', '/llm-ask', '/ask-analysis', '/analysis'].includes(path)
    }
    if (userRole.value === 'user') {
      return ['/dashboard', '/llm-ask', '/analysis'].includes(path)
    }
    return false
  }
  return userMenus.value.includes(path)
}

// 用户菜单处理
const handleUserCommand = async (command) => {
  if (command === 'logout') {
    try {
      await authAPI.logout()
    } catch (e) {
      // 忽略登出API错误
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    ElMessage.success('已退出登录')
    router.push('/login')
  } else if (command === 'settings') {
    router.push('/settings')
  }
}

// 移动端菜单
const mobileMenuVisible = ref(false)
const toggleMobileMenu = () => {
  mobileMenuVisible.value = !mobileMenuVisible.value
}

// 头像相关
const selectedAvatar = ref('')
const customAvatar = ref('')

const presetAvatars = [
  { bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', letter: 'A', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', letter: 'B', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', letter: 'C', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', letter: 'D', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)', letter: 'E', color: '#fff', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)', letter: 'F', color: '#333', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #d299c2 0%, #fef9d7 100%)', letter: 'G', color: '#333', type: 'gradient' },
  { bg: 'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)', letter: 'H', color: '#fff', type: 'gradient' },
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

function loadAvatarConfig() {
  selectedAvatar.value = localStorage.getItem('user_avatar_preset') || ''
  customAvatar.value = localStorage.getItem('user_avatar_custom') || ''
}

onMounted(() => {
  loadAvatarConfig()
  fetchUserMenus()
})
</script>

<style scoped>
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--header-height, 60px);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(99, 102, 241, 0.08);
  display: flex;
  align-items: center;
  padding: 0 24px;
  z-index: 1000;
}

/* Logo */
.header-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-right: 40px;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Navigation */
.header-nav {
  display: flex;
  align-items: center;
  flex: 1;
}

.nav-item-wrapper {
  margin-right: 4px;
}

.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
  text-decoration: none;
  border-radius: 8px;
  transition: all 0.2s;
}

.nav-item:hover {
  color: #6366F1;
  background: rgba(99, 102, 241, 0.06);
}

.nav-item.active {
  color: #6366F1;
  background: rgba(99, 102, 241, 0.1);
}

.nav-dropdown {
  cursor: pointer;
}

.dropdown-arrow {
  font-size: 12px;
  margin-left: 2px;
  transition: transform 0.2s;
}

.nav-dropdown:hover .dropdown-arrow {
  transform: rotate(180deg);
}

/* Dropdown Menu */
:deep(.el-dropdown-menu__item) {
  padding: 8px 20px;
  font-size: 14px;
}

:deep(.el-dropdown-menu__item.active) {
  color: #1677ff;
  background: rgba(22, 119, 255, 0.06);
}

/* Right Actions */
.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.notification-badge {
  cursor: pointer;
}

.action-icon {
  font-size: 18px;
  color: #6b7280;
  padding: 4px;
}

.action-icon:hover {
  color: #6366F1;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.user-trigger:hover {
  background: rgba(99, 102, 241, 0.06);
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  overflow: hidden;
}

.username {
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
}

/* Hamburger */
.hamburger {
  display: none;
  width: 40px;
  height: 40px;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: #6b7280;
}

.hamburger:hover {
  background: rgba(99, 102, 241, 0.06);
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
  z-index: 999;
}

/* Mobile Navigation */
.mobile-nav {
  position: fixed;
  top: 0;
  right: 0;
  width: 280px;
  height: 100vh;
  background: #fff;
  z-index: 1001;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.15);
}

.mobile-nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
}

.mobile-nav-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f1f1f;
}

.close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: #595961;
}

.mobile-nav-section {
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
}

.mobile-nav-section-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #8c8c8c;
  margin-bottom: 8px;
  padding: 0 12px;
}

.mobile-nav-item {
  display: block;
  padding: 10px 12px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  color: #595961;
  text-decoration: none;
  transition: all 0.2s;
}

.mobile-nav-item:hover,
.mobile-nav-item.active {
  color: #1677ff;
  background: rgba(22, 119, 255, 0.06);
}

.mobile-nav-item.child {
  padding-left: 24px;
  font-weight: 400;
}

/* Slide transition */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.25s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

/* Responsive */
@media (max-width: 1024px) {
  .header-logo {
    margin-right: 24px;
  }

  .nav-item {
    padding: 8px 12px;
  }
}

@media (max-width: 768px) {
  .app-header {
    padding: 0 16px;
  }

  .header-nav {
    display: none;
  }

  .header-actions {
    display: none;
  }

  .hamburger {
    display: flex;
  }

  .mobile-overlay {
    display: block;
  }

  .username {
    display: none;
  }
}
</style>
