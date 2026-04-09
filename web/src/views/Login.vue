<template>
  <div class="login-page">
    <!-- 左侧插图 -->
    <div class="left-panel">
      <LoginIllustration />
    </div>

    <!-- 右侧表单 -->
    <div class="right-panel">
      <div class="login-form-container">
        <!-- Logo -->
        <div class="logo-section">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
            <rect x="4" y="16" width="8" height="16" rx="2" fill="#00B078"/>
            <rect x="16" y="8" width="8" height="24" rx="2" fill="#00B078" opacity="0.7"/>
            <rect x="28" y="2" width="8" height="30" rx="2" fill="#00B078" opacity="0.5"/>
          </svg>
          <span class="logo-text">Metrics</span>
        </div>

        <!-- 标题 -->
        <div class="form-header">
          <h1>欢迎回来</h1>
          <p>请登录您的账号</p>
        </div>

        <!-- 表单 -->
        <el-form :model="loginForm" class="login-form" @submit.prevent="handleLogin">
          <el-form-item>
            <el-input
              v-model="loginForm.username"
              placeholder="用户名"
              size="large"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <div class="form-options">
            <el-checkbox v-model="rememberMe">记住我</el-checkbox>
            <a href="#" class="forgot-link">忘记密码？</a>
          </div>

          <el-button
            type="primary"
            size="large"
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form>

        <!-- 其他登录方式 -->
        <div class="divider">
          <span>其他登录方式</span>
        </div>

        <div class="social-login">
          <button class="social-btn" @click="handleDingTalkLogin">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15h2v-6h-2v6zm0-8h2V7h-2v2z"/>
            </svg>
            钉钉扫码登录
          </button>
          <button class="social-btn" disabled>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15h2v-6h-2v6zm0-8h2V7h-2v2z"/>
            </svg>
            AI 助手
          </button>
        </div>

        <!-- 协议 -->
        <p class="agreement">
          登录即表示同意<a href="#">《用户协议》</a>和<a href="#">《隐私政策》</a>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '../api'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import LoginIllustration from '../components/LoginIllustration.vue'

const router = useRouter()
const loginForm = ref({
  username: '',
  password: ''
})
const rememberMe = ref(false)
const loading = ref(false)

async function handleLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    const res = await authAPI.login(loginForm.value)
    if (res.data) {
      localStorage.setItem('access_token', res.data.access_token)
      localStorage.setItem('refresh_token', res.data.refresh_token)
      localStorage.setItem('user_info', JSON.stringify(res.data.user))
      if (rememberMe.value) {
        localStorage.setItem('remember_me', 'true')
        localStorage.setItem('username', loginForm.value.username)
      }
      ElMessage.success('登录成功')
      router.push('/dashboard')
    }
  } catch (e) {
    ElMessage.error('用户名或密码错误')
  } finally {
    loading.value = false
  }
}

function handleDingTalkLogin() {
  ElMessage.info('钉钉扫码登录功能开发中')
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

.login-page {
  display: flex;
  min-height: 100vh;
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

.left-panel {
  flex: 0 0 55%;
  background: #00B078;
}

.right-panel {
  flex: 0 0 45%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
}

.login-form-container {
  width: 100%;
  max-width: 380px;
  padding: 40px;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 40px;
}

.logo-text {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a1a;
}

.form-header {
  margin-bottom: 32px;
}

.form-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a1a;
  margin-bottom: 8px;
}

.form-header p {
  font-size: 14px;
  color: #666666;
}

.login-form {
  margin-bottom: 24px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.login-form :deep(.el-input__wrapper) {
  padding: 12px 16px;
  border-radius: 10px;
  box-shadow: none;
  border: 1px solid #e8e8e8;
}

.login-form :deep(.el-input__wrapper:hover),
.login-form :deep(.el-input__wrapper.is-focus) {
  border-color: #00B078;
  box-shadow: none;
}

.login-form :deep(.el-input__inner) {
  font-size: 15px;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.form-options :deep(.el-checkbox__label) {
  font-size: 14px;
  color: #666666;
}

.forgot-link {
  font-size: 14px;
  color: #00B078;
  text-decoration: none;
}

.forgot-link:hover {
  text-decoration: underline;
}

.login-btn {
  width: 100%;
  height: 48px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  background: #00B078;
  border: none;
}

.login-btn:hover {
  background: #00A06B;
}

.divider {
  display: flex;
  align-items: center;
  margin: 24px 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e8e8e8;
}

.divider span {
  padding: 0 16px;
  font-size: 13px;
  color: #999999;
}

.social-login {
  display: flex;
  gap: 12px;
}

.social-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 44px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid #e8e8e8;
  background: #ffffff;
  color: #666666;
}

.social-btn:hover:not(:disabled) {
  border-color: #00B078;
  color: #00B078;
}

.social-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.agreement {
  margin-top: 24px;
  font-size: 12px;
  color: #999999;
  text-align: center;
}

.agreement a {
  color: #00B078;
  text-decoration: none;
}

.agreement a:hover {
  text-decoration: underline;
}

/* 响应式 */
@media (max-width: 1024px) {
  .left-panel {
    display: none;
  }

  .right-panel {
    flex: 1;
  }
}

@media (max-width: 480px) {
  .login-form-container {
    padding: 24px;
  }

  .form-header h1 {
    font-size: 24px;
  }
}
</style>
