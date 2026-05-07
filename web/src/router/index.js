import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/llm-ask-v2'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue')
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue')
      },
      {
        path: 'metrics',
        name: 'Metrics',
        component: () => import('../views/Metrics.vue')
      },
      {
        path: 'alerts',
        name: 'Alerts',
        component: () => import('../views/Alerts.vue')
      },
      {
        path: 'ask-analysis',
        name: 'AskAnalysis',
        component: () => import('../views/AskAnalysis.vue')
      },
      {
        path: 'analysis',
        name: 'Analysis',
        component: () => import('../views/AnalysisPage.vue')
      },
      {
        path: 'ai-assistant',
        name: 'AIAssistant',
        component: () => import('../views/components/AskDashboard.vue')
      },
      {
        path: 'llm-ask-v2',
        name: 'LLMAskV2',
        component: () => import('../views/LLMAskV2A.vue')
      },
      {
        path: 'llm-ask-v2b',
        name: 'LLMAskV2B',
        component: () => import('../views/LLMAskV2B.vue')
      },
      {
        path: 'llm-config',
        name: 'LLMConfig',
        component: () => import('../views/LLMConfig.vue')
      },
      {
        path: 'nlp-config',
        name: 'NLPConfig',
        component: () => import('../views/NLPConfig.vue')
      },
      {
        path: 'config-center',
        name: 'ConfigCenter',
        component: () => import('../views/ConfigCenter.vue')
      },
      {
        path: 'feedback',
        name: 'Feedback',
        component: () => import('../views/FeedbackDashboard.vue')
      },
      {
        path: 'starrocks-config',
        name: 'StarRocksConfig',
        component: () => import('../views/StarRocksConfig.vue')
      },
      {
        path: 'dimension-config',
        name: 'DimensionConfig',
        component: () => import('../views/DimensionConfig.vue')
      },
      {
        path: 'user-management',
        name: 'UserManagement',
        component: () => import('../views/UserManagement.vue')
      },
      {
        path: 'role-permission',
        name: 'RolePermission',
        component: () => import('../views/RolePermission.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：检查登录状态
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  // 不需要登录的路径
  const whiteList = ['/login']
  if (!token && !whiteList.includes(to.path)) {
    next('/login')
  } else if (to.path === '/login' && token) {
    // 已登录访问登录页，跳转到首页
    next('/dashboard')
  } else {
    next()
  }
})

export default router
