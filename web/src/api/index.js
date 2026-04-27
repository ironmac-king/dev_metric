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

// 文件下载（绕过响应拦截器，直接返回完整response）
export const downloadFile = (url, filename) => {
  const token = localStorage.getItem('access_token')
  return axios({
    url: url,
    baseURL: '/api/v1',
    method: 'GET',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    responseType: 'blob'
  }).then(res => {
    const blob = new Blob([res.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  })
}

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

// 维度配置 API (dimension_configs 表 - SQL 生成用)
export const dimensionConfigAPI = {
  list: (params) => api.get('/dimension-configs', { params }),
  getTables: () => api.get('/dimension-configs/tables'),
  create: (data) => api.post('/dimension-configs', data),
  update: (id, data) => api.put(`/dimension-configs/${id}`, data),
  delete: (id) => api.delete(`/dimension-configs/${id}`),
  deleteTable: (tableName) => api.delete(`/dimension-configs/tables/${tableName}`)
}

// 维度类型映射 API (全局维度类型→列名映射)
export const dimensionTypeMappingAPI = {
  list: (params) => api.get('/dimension-type-mappings', { params }),
  search: (params) => api.get('/dimension-type-mappings/search', { params }),
  create: (data) => api.post('/dimension-type-mappings', data),
  update: (id, data) => api.put(`/dimension-type-mappings/${id}`, data),
  delete: (id) => api.delete(`/dimension-type-mappings/${id}`)
}

// 统一维度值映射 API (dim_value_mapping 表 - 新)
export const dimensionValueAPI = {
  list: (params) => api.get('/dimension-values', { params }),
  get: (id) => api.get(`/dimension-values/${id}`),
  update: (id, data) => api.put(`/dimension-values/${id}`, data),
  delete: (id) => api.delete(`/dimension-values/${id}`),
  batchDelete: (ids) => api.delete('/dimension-values/batch', { data: { ids } }),
  getColumns: (params) => api.get('/dimension-values/columns', { params }),
  search: (params) => api.get('/dimension-values/search', { params }),
  sync: (data) => api.post('/dimension-values/sync', data),
  syncBySQL: (sql) => api.post('/dimension-values/sync/sql', { sql }),
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

// 问数分析 API
export const askAnalysisAPI = {
  getLogs: (params) => api.get('/ask-analysis/logs', { params }),
  getLog: (id) => api.get(`/ask-analysis/logs/${id}`)
}

// 认证 API
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  refresh: (data) => api.post('/auth/refresh', data),
  logout: () => api.post('/auth/logout')
}

// 用户管理 API
export const userAPI = {
  list: () => api.get('/users'),
  get: (id) => api.get(`/users/${id}`),
  create: (data) => api.post('/users', data),
  update: (id, data) => api.put(`/users/${id}`, data),
  delete: (id) => api.delete(`/users/${id}`)
}

// 角色权限 API
export const roleAPI = {
  list: () => api.get('/roles'),
  getAllMenus: () => api.get('/roles/all-menus'),
  getMenus: (roleName) => api.get(`/roles/${roleName}/menus`),
  updateMenus: (roleName, menus) => api.put(`/roles/${roleName}/menus`, { menus }),
  create: (data) => api.post('/roles', data),
  update: (id, data) => api.put(`/roles/role/${id}`, data),
  delete: (id) => api.delete(`/roles/role/${id}`)
}

// 当前用户菜单权限
export const menuAPI = {
  getMyMenus: () => api.get('/my-menus')
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
  deleteVersion: (id, version) => api.delete(`/prompt-configs/${id}/version`, { params: { version } }),
  generate: (data) => api.post('/prompt-configs/generate', data)
}

// 槽位配置 API
export const slotConfigAPI = {
  list: () => api.get('/nlp/slots'),
  get: (id) => api.get(`/nlp/slots/${id}`),
  create: (data) => api.post('/nlp/slots', data),
  update: (id, data) => api.put(`/nlp/slots/${id}`, data),
  delete: (id) => api.delete(`/nlp/slots/${id}`),
  // 槽位依赖
  listDependencies: () => api.get('/nlp/slot-dependencies'),
  createDependency: (data) => api.post('/nlp/slot-dependencies', data),
  deleteDependency: (id) => api.delete(`/nlp/slot-dependencies/${id}`),
  // 槽位关联
  listRelations: () => api.get('/nlp/slot-relations'),
  createRelation: (data) => api.post('/nlp/slot-relations', data),
  deleteRelation: (id) => api.delete(`/nlp/slot-relations/${id}`)
}

// 触发规则配置 API
export const triggerConfigAPI = {
  list: (params) => api.get('/nlp/trigger-configs', { params }),
  get: (id) => api.get(`/nlp/trigger-configs/${id}`),
  create: (data) => api.post('/nlp/trigger-configs', data),
  update: (id, data) => api.put(`/nlp/trigger-configs/${id}`, data),
  delete: (id) => api.delete(`/nlp/trigger-configs/${id}`)
}

// 触发器开关配置 API
export const triggerSwitchAPI = {
  list: (params) => api.get('/nlp/trigger-switches', { params }),
  get: (type) => api.get(`/nlp/trigger-switches/${type}`),
  set: (type, data) => api.put(`/nlp/trigger-switches/${type}`, data),
  delete: (type) => api.delete(`/nlp/trigger-switches/${type}`)
}

// 输出模板配置 API
export const outputTemplateAPI = {
  list: (params) => api.get('/nlp/output-templates', { params }),
  get: (id) => api.get(`/nlp/output-templates/${id}`),
  create: (data) => api.post('/nlp/output-templates', data),
  update: (id, data) => api.put(`/nlp/output-templates/${id}`, data),
  delete: (id) => api.delete(`/nlp/output-templates/${id}`)
}

// 业务维度标签 API
export const dimensionLabelAPI = {
  list: (params) => api.get('/nlp/labels', { params }),
  get: (id) => api.get(`/nlp/labels/${id}`),
  create: (data) => api.post('/nlp/labels', data),
  update: (id, data) => api.put(`/nlp/labels/${id}`, data),
  delete: (id) => api.delete(`/nlp/labels/${id}`)
}

export default api
