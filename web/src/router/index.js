import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
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
        path: 'ask',
        name: 'Ask',
        component: () => import('../views/Ask.vue')
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
        path: 'feedback',
        name: 'Feedback',
        component: () => import('../views/FeedbackDashboard.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
