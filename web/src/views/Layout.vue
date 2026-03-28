<template>
  <div class="layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="logo-text">Metrics</span>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/dashboard" class="nav-item" :class="{ active: $route.path === '/dashboard' }">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="2" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.9"/>
            <rect x="11" y="2" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.6"/>
            <rect x="2" y="11" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.6"/>
            <rect x="11" y="11" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.3"/>
          </svg>
          Dashboard
        </router-link>
        <router-link to="/metrics" class="nav-item" :class="{ active: $route.path === '/metrics' }">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M3 13L7 7L11 10L17 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="17" cy="3" r="1.5" fill="currentColor"/>
          </svg>
          指标管理
        </router-link>
        <router-link to="/alerts" class="nav-item" :class="{ active: $route.path === '/alerts' }">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 2C7.5 2 5 3.5 5 7V11L3 14V15H17V14L15 11V7C15 3.5 12.5 2 10 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M8 15V16C8 17.1 8.9 18 10 18C11.1 18 12 17.1 12 16V15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          告警配置
        </router-link>
        <router-link to="/ask" class="nav-item" :class="{ active: $route.path === '/ask' }">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
            <path d="M7 8C7 7.4 7.4 7 8 7H12C12.6 7 13 7.4 13 8C13 8.6 12.6 9 12 9H11V10C11 10.6 10.6 11 10 11C9.4 11 9 10.6 9 10V8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="10" cy="14" r="0.5" fill="currentColor"/>
          </svg>
          智能问数
        </router-link>
        <router-link to="/llm-config" class="nav-item" :class="{ active: $route.path === '/llm-config' }">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="4" cy="10" r="2" fill="currentColor"/>
            <circle cx="10" cy="4" r="2" fill="currentColor" opacity="0.7"/>
            <circle cx="10" cy="16" r="2" fill="currentColor" opacity="0.7"/>
            <circle cx="16" cy="10" r="2" fill="currentColor" opacity="0.5"/>
          </svg>
          LLM 配置
        </router-link>
        <router-link to="/nlp-config" class="nav-item" :class="{ active: $route.path === '/nlp-config' }">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M3 5L10 3L17 5V15L10 17L3 15V5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M7 10L9 12L13 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          意图配置
        </router-link>
        <router-link to="/feedback" class="nav-item" :class="{ active: $route.path === '/feedback' }">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="8" width="3" height="10" rx="1" fill="currentColor"/>
            <rect x="8.5" y="4" width="3" height="14" rx="1" fill="currentColor" opacity="0.8"/>
            <rect x="15" y="2" width="3" height="16" rx="1" fill="currentColor" opacity="0.6"/>
          </svg>
          反馈看板
        </router-link>
      </nav>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.layout {
  min-height: 100vh;
  background: #fafafa;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  display: flex;
}

/* Sidebar */
.sidebar {
  width: 240px;
  background: #fff;
  border-right: 1px solid #ebeef5;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  padding: 24px 0;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 0 24px 24px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 16px;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a1a;
  letter-spacing: -0.5px;
}

.sidebar-nav {
  flex: 1;
  padding: 0 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  color: #7177a4;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  text-decoration: none;
  margin-bottom: 4px;
}

.nav-item:hover {
  background: #f5f5f7;
  color: #1a1a1a;
}

.nav-item.active {
  background: #f0f0ff;
  color: #6366f1;
}

.nav-item svg {
  flex-shrink: 0;
}

/* Main Content */
.main-content {
  flex: 1;
  margin-left: 240px;
  min-height: 100vh;
}
</style>
