import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000  // 2 minutes for AI generation
})

// 请求拦截器
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 指标 API
export const metricAPI = {
  list: (params) => api.get('/metrics', { params }),
  get: (id) => api.get(`/metrics/${id}`),
  create: (data) => api.post('/metrics', data),
  update: (id, data) => api.put(`/metrics/${id}`, data),
  delete: (id) => api.delete(`/metrics/${id}`),
  getData: (id) => api.get(`/metrics/${id}/data`),
  getStats: () => api.get('/metrics/stats'),
  importPreview: (formData) => api.post('/metrics/import-preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  importCommit: (token) => api.post('/metrics/import-commit', { token })
}

// StarRocks 配置 API
export const starrocksAPI = {
  getConfig: () => api.get('/starrocks/config'),
  updateConfig: (data) => api.put('/starrocks/config', data),
  testConnection: (data) => api.post('/starrocks/config/test', data)
}

// 维度配置 API
export const dimensionConfigAPI = {
  list: (params) => api.get('/dimension-configs', { params }),
  getTables: () => api.get('/dimension-configs/tables'),
  create: (data) => api.post('/dimension-configs', data),
  update: (id, data) => api.put(`/dimension-configs/${id}`, data),
  delete: (id) => api.delete(`/dimension-configs/${id}`)
}

// 告警 API
export const alertAPI = {
  list: (params) => api.get('/alerts', { params }),
  create: (data) => api.post('/alerts', data),
  update: (id, data) => api.put(`/alerts/${id}`, data),
  delete: (id) => api.delete(`/alerts/${id}`),
  getHistory: (id, params) => api.get(`/alerts/${id}/history`, { params })
}

// Dashboard API
export const dashboardAPI = {
  getSummary: () => api.get('/dashboard/summary'),
  getCharts: () => api.get('/dashboard/charts'),
  getMetricCards: () => api.get('/dashboard/metric-cards')
}

// 智能问数 API
export const askAPI = {
  ask: (data) => api.post('/ask', data),
  getHistory: (sessionId) => api.get('/ask/history', { params: { session_id: sessionId } }),
  clearSession: (sessionId) => api.post('/ask/clear', { session_id: sessionId }),
  getSuggest: () => api.get('/ask/suggest'),
  sendFeedback: (data) => api.post('/ask/feedback', data),
  drillDown: (data) => api.post('/ask/drill_down', data),
  // 消息持久化
  getMessages: (sessionId) => api.get('/ask/messages', { params: { session_id: sessionId } }),
  deleteMessages: (sessionId) => api.delete('/ask/messages', { params: { session_id: sessionId } }),
  // Dashboard 相关
  getDashboardStats: () => api.get('/ask/dashboard/stats'),
  getSessions: () => api.get('/ask/sessions'),
  starSession: (id) => api.put(`/ask/sessions/${id}/star`),
  getFavorites: () => api.get('/ask/favorites'),
  addFavorite: (data) => api.post('/ask/favorites', data),
  deleteFavorite: (id) => api.delete(`/ask/favorites/${id}`),
  getPreferences: () => api.get('/ask/preferences'),
  updatePreferences: (data) => api.put('/ask/preferences', data),
  getRecentQuestions: () => api.get('/ask/recent-questions'),
  // 快捷问题
  getShortcuts: () => api.get('/ask/shortcuts'),
  createShortcut: (data) => api.post('/ask/shortcuts', data),
  updateShortcut: (id, data) => api.put(`/ask/shortcuts/${id}`, data),
  deleteShortcut: (id) => api.delete(`/ask/shortcuts/${id}`)
}

// LLM 配置 API
export const llmAPI = {
  list: () => api.get('/llm/configs'),
  get: (id) => api.get(`/llm/configs/${id}`),
  create: (data) => api.post('/llm/configs', data),
  update: (id, data) => api.put(`/llm/configs/${id}`, data),
  delete: (id) => api.delete(`/llm/configs/${id}`),
  setDefault: (id) => api.put(`/llm/configs/${id}/default`),
  test: (data) => api.post('/llm/configs/test', data)
}

// 反馈看板 API
export const feedbackAPI = {
  getStats: () => api.get('/feedback/stats'),
  getTrend: (period) => api.get('/feedback/trend', { params: { period } }),
  getList: (params) => api.get('/feedback/list', { params }),
  getByType: () => api.get('/feedback/by-type')
}

// 认证 API
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  refresh: (data) => api.post('/auth/refresh', data),
  logout: () => api.post('/auth/logout')
}

// Prompt 配置 API
export const promptConfigAPI = {
  list: () => api.get('/prompt-configs'),
  get: (id) => api.get(`/prompt-configs/${id}`),
  getActive: (name) => api.get('/prompt-configs/active', { params: { name } }),
  getVersions: (id) => api.get(`/prompt-configs/${id}/versions`),
  create: (data) => api.post('/prompt-configs', data),
  update: (id, data) => api.put(`/prompt-configs/${id}`, data),
  delete: (id) => api.delete(`/prompt-configs/${id}`),
  rollback: (id, data) => api.post(`/prompt-configs/${id}/rollback`, data),
  generate: (data) => api.post('/prompt-configs/generate', data)
}

export default api
