<template>
  <div class="ai-assistant-dashboard">
    <!-- Hero Section -->
    <div class="hero-section">
      <div class="hero-icon">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <circle cx="24" cy="24" r="22" stroke="#1E40AF" stroke-width="2" opacity="0.2"/>
          <circle cx="24" cy="24" r="16" stroke="#1E40AF" stroke-width="2" opacity="0.4"/>
          <circle cx="24" cy="24" r="10" stroke="#1E40AF" stroke-width="2"/>
          <circle cx="24" cy="20" r="3" fill="#1E40AF"/>
          <path d="M20 28C20 28 21.5 33 24 33C26.5 33 28 28 28 28" stroke="#1E40AF" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
      <h1>AI 智能问数助手</h1>
      <p>您的智能数据分析伙伴，快速查询指标、业务口径和技术细节</p>
      <div class="hero-actions">
        <button class="btn btn-primary" @click="goToChat">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M3 6C3 4.3 4.3 3 6 3H14C15.7 3 17 4.3 17 6V12C17 13.7 15.7 15 14 15H11L7 18V15H6C4.3 15 3 13.7 3 12V6Z" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          开始对话
        </button>
        <button class="btn btn-secondary" @click="$router.push('/metrics')">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="3" y="3" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
            <rect x="11" y="3" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
            <rect x="3" y="11" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
            <rect x="11" y="11" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          查看指标
        </button>
        <button class="btn btn-secondary" @click="goToFavorites">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 2L12.5 7H18L13.5 10.5L15.5 16L10 12.5L4.5 16L6.5 10.5L2 7H7.5L10 2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
          我的收藏
        </button>
      </div>
    </div>

    <!-- Stats Cards Row -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon blue">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/>
            <path d="M12 7V12L15 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.today_total || 0 }}</div>
          <div class="stat-label">今日查询</div>
        </div>
        <div class="stat-trend up">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 10V2M6 2L3 5M6 2L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          12%
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon green">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M17 21V19C17 16.8 15.2 15 13 15H5C2.8 15 1 16.8 1 19V21" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="9" cy="7" r="3" stroke="currentColor" stroke-width="1.5"/>
            <path d="M21 21V19C21 16.8 19.2 15 17 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.session_total || 0 }}</div>
          <div class="stat-label">活跃会话</div>
        </div>
        <div class="stat-trend up">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 10V2M6 2L3 5M6 2L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          5%
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon amber">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L15 8H21L16 12.5L18 19L12 15L6 19L8 12.5L3 8H9L12 2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ hotMetricsCount }}</div>
          <div class="stat-label">热门指标</div>
        </div>
        <div class="stat-trend up">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 10V2M6 2L3 5M6 2L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          8%
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon cyan">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="12" cy="10" r="2" fill="currentColor"/>
            <path d="M9 15C9 15 10.5 17 12 17C13.5 17 15 15 15 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">1.2s</div>
          <div class="stat-label">AI 响应</div>
        </div>
        <div class="stat-badge normal">正常</div>
      </div>
    </div>

    <!-- Main Content Grid -->
    <div class="content-grid">
      <!-- Left Column -->
      <div class="grid-left">
        <!-- Shortcuts Section -->
        <div class="content-card shortcuts-card">
          <div class="card-header">
            <h3>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M9 1L11 7H17L12 11L14 17L9 13L4 17L6 11L1 7H7L9 1Z" fill="#1E40AF" opacity="0.8"/>
              </svg>
              快捷问题
            </h3>
            <button class="btn-text" @click="showShortcutEditor = true">编辑</button>
          </div>
          <div class="shortcuts-list">
            <div
              v-for="(shortcut, index) in shortcuts"
              :key="shortcut.id"
              class="shortcut-item"
              @click="askQuestion(shortcut.question_text)"
            >
              <svg class="shortcut-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
                <circle cx="9" cy="9" r="7" stroke="#1E40AF" stroke-width="1.5" opacity="0.3"/>
                <path d="M6 9L9 12L12 6" stroke="#1E40AF" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span class="shortcut-text" :title="shortcut.question_text">{{ shortcut.question_text }}</span>
              <svg class="arrow-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M6 4L10 8L6 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </div>
          </div>
        </div>

        <!-- Hot Metrics Section -->
        <div class="content-card hot-card">
          <div class="card-header">
            <h3>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M9 1C9 1 13 5 13 9C13 11.2 11.2 13 9 13C6.8 13 5 11.2 5 9C5 5 9 1 9 1Z" stroke="#FF6B6B" stroke-width="1.5"/>
                <path d="M9 13V17" stroke="#FF6B6B" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
              今日热门
            </h3>
          </div>
          <div class="hot-list" v-if="stats.hot_metrics && stats.hot_metrics.length">
            <div
              v-for="(item, index) in stats.hot_metrics"
              :key="index"
              class="hot-item"
              @click="askQuestion(item.metric_name + '是多少')"
            >
              <span class="hot-rank">{{ index + 1 }}</span>
              <span class="hot-name" :title="item.metric_name || item.metric_code">{{ item.metric_name || item.metric_code }}</span>
              <span class="hot-count">{{ item.query_count }}次</span>
            </div>
          </div>
          <div v-else class="empty-state">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="16" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
              <path d="M20 12V20M20 24V26" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.5"/>
            </svg>
            <span>暂无数据</span>
          </div>
        </div>
      </div>

      <!-- Right Column -->
      <div class="grid-right">
        <!-- Trend Chart Section -->
        <div class="content-card trend-card">
          <div class="card-header">
            <h3>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M2 14L6 10L10 12L16 6" stroke="#1E40AF" stroke-width="1.5" stroke-linecap="round"/>
                <circle cx="16" cy="6" r="2" fill="#1E40AF"/>
              </svg>
              本周查询趋势
            </h3>
          </div>
          <div class="trend-container" ref="trendChartRef"></div>
        </div>

        <!-- Recent Sessions Section -->
        <div class="content-card sessions-card">
          <div class="card-header">
            <h3>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M3 6C3 4.3 4.3 3 6 3H12C13.7 3 15 4.3 15 6V10C15 11.7 13.7 13 12 13H9L6 16V13H6C4.3 13 3 11.7 3 10V6Z" stroke="#1E40AF" stroke-width="1.5"/>
              </svg>
              最近会话
            </h3>
          </div>
          <div class="sessions-list" v-if="sessions.length">
            <div
              v-for="session in sessions"
              :key="session.id || session.session_id"
              class="session-item"
              @click="loadSession(session)"
            >
              <div class="session-icon" :class="{ starred: session.starred }">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 2L10 6H14L11 9L12.5 14L8 11L3.5 14L5 9L2 6H6L8 2Z" :fill="session.starred ? '#F59E0B' : 'none'" :stroke="session.starred ? '#F59E0B' : 'currentColor'" stroke-width="1"/>
                </svg>
              </div>
              <div class="session-content">
                <div class="session-title" :title="session.title || '新对话'">{{ session.title || '新对话' }}</div>
                <div class="session-time">{{ formatTime(session.updated_at || session.created_at) }}</div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="16" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
              <path d="M14 18C14 16.9 14.9 16 16 16H24C25.1 16 26 16.9 26 18V24C26 25.1 25.1 26 24 26H16C14.9 26 14 25.1 14 24V18Z" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
            </svg>
            <span>暂无会话</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Shortcut Editor Dialog -->
    <el-dialog v-model="showShortcutEditor" title="编辑快捷问题" width="500px">
      <div class="shortcut-editor">
        <div v-for="(s, i) in editingShortcuts" :key="i" class="shortcut-edit-row">
          <el-input v-model="s.icon" placeholder="图标" class="icon-input" />
          <el-input v-model="s.question_text" placeholder="问题文本" class="text-input" />
          <el-button type="danger" size="small" @click="removeShortcut(i)">删除</el-button>
        </div>
        <el-button type="primary" size="small" @click="addShortcut">添加</el-button>
      </div>
      <template #footer>
        <el-button @click="showShortcutEditor = false">取消</el-button>
        <el-button type="primary" @click="saveShortcuts">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { askAPI } from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()

const shortcuts = ref([])
const stats = ref({
  hot_metrics: [],
  trend_data: [],
  today_total: 0,
  session_total: 0
})
const sessions = ref([])
const showShortcutEditor = ref(false)
const editingShortcuts = ref([])
const trendChartRef = ref(null)
let trendChartInstance = null

const hotMetricsCount = computed(() => stats.value.hot_metrics?.length || 0)

async function loadData() {
  try {
    const [shortcutsRes, statsRes, sessionsRes] = await Promise.all([
      askAPI.getShortcuts(),
      askAPI.getDashboardStats(),
      askAPI.getSessions()
    ])

    if (shortcutsRes.data) {
      shortcuts.value = shortcutsRes.data
      editingShortcuts.value = JSON.parse(JSON.stringify(shortcutsRes.data))
    }

    if (statsRes.data) {
      stats.value = statsRes.data
    }

    if (sessionsRes.data && sessionsRes.data.length) {
      sessions.value = sessionsRes.data.slice(0, 5)
    }
  } catch (e) {
    console.error('加载数据失败:', e)
    shortcuts.value = [
      { id: 1, question_text: '广告转化率是多少？', icon: '📊' },
      { id: 2, question_text: '今日 DAU 是多少？', icon: '📈' },
      { id: 3, question_text: '本周 GMV 趋势如何？', icon: '📊' },
      { id: 4, question_text: '业务口径是什么？', icon: '📝' }
    ]
  }

  await nextTick()
  renderTrendChart()
}

function renderTrendChart() {
  if (!trendChartRef.value) return

  // 清理旧实例
  if (trendChartInstance) {
    trendChartInstance.dispose()
    trendChartInstance = null
  }

  if (!stats.value.trend_data?.length) {
    // 渲染空状态
    trendChartInstance = echarts.init(trendChartRef.value)
    trendChartInstance.setOption({
      title: {
        text: '暂无数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#999', fontSize: 14, fontWeight: 'normal' }
      },
      grid: { show: false },
      xAxis: { show: false },
      yAxis: { show: false }
    })
    return
  }

  trendChartInstance = echarts.init(trendChartRef.value)

  const dates = stats.value.trend_data.map(d => d.date?.slice(5) || '')
  const counts = stats.value.trend_data.map(d => d.query_count || 0)

  const option = {
    grid: {
      left: 40,
      right: 20,
      top: 20,
      bottom: 30
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#E8E8E8' } },
      axisLabel: { color: '#666', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#F0F0F0' } },
      axisLabel: { color: '#666', fontSize: 11 }
    },
    series: [{
      data: counts,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { color: '#1E40AF', width: 2.5 },
      itemStyle: { color: '#1E40AF' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(30, 64, 175, 0.25)' },
          { offset: 1, color: 'rgba(30, 64, 175, 0.02)' }
        ])
      }
    }]
  }

  trendChartInstance.setOption(option)
}

function goToChat() {
  router.push('/ask')
}

function goToFavorites() {
  router.push('/ask')
}

function askQuestion(text) {
  router.push({ path: '/ask', query: { q: text } })
}

function loadSession(session) {
  router.push({ path: '/ask', query: { session_id: session.id || session.session_id } })
}

function formatTime(timeStr) {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date

  if (diff < 60 * 1000) return '刚刚'
  if (diff < 60 * 60 * 1000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 24 * 60 * 60 * 1000) return Math.floor(diff / 3600000) + '小时前'
  if (diff < 7 * 24 * 60 * 60 * 1000) return Math.floor(diff / 86400000) + '天前'

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

// Shortcut editor
function addShortcut() {
  editingShortcuts.value.push({ icon: '📊', question_text: '', sort_order: editingShortcuts.value.length + 1, status: 1 })
}

function removeShortcut(index) {
  editingShortcuts.value.splice(index, 1)
}

async function saveShortcuts() {
  try {
    for (const s of shortcuts.value) {
      if (s.id) await askAPI.deleteShortcut(s.id)
    }
    for (const s of editingShortcuts.value) {
      await askAPI.createShortcut(s)
    }
    shortcuts.value = JSON.parse(JSON.stringify(editingShortcuts.value))
    showShortcutEditor.value = false
    ElMessage.success('保存成功')
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error('保存失败')
  }
}

onMounted(() => {
  loadData()
})

onUnmounted(() => {
  if (trendChartInstance) {
    trendChartInstance.dispose()
    trendChartInstance = null
  }
})
</script>

<style scoped>
.ai-assistant-dashboard {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

/* Hero Section */
.hero-section {
  text-align: center;
  padding: 48px 0 56px;
}

.hero-icon {
  margin-bottom: 24px;
}

.hero-section h1 {
  font-size: 32px;
  font-weight: 700;
  color: #1E3A8A;
  margin: 0 0 16px;
  letter-spacing: -0.5px;
}

.hero-section p {
  font-size: 16px;
  color: #666;
  margin: 0 0 32px;
  max-width: 480px;
  margin-left: auto;
  margin-right: auto;
}

.hero-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%);
  color: #fff;
  box-shadow: 0 4px 12px rgba(30, 64, 175, 0.25);
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(30, 64, 175, 0.35);
}

.btn-secondary {
  background: #fff;
  color: #1E40AF;
  border: 1px solid #E8E8E8;
}

.btn-secondary:hover {
  background: #F8FAFC;
  border-color: #1E40AF;
}

.btn-text {
  background: none;
  border: none;
  color: #3B82F6;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
}

.btn-text:hover {
  color: #1E40AF;
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03);
  transition: box-shadow 0.2s;
  height: 88px;
  box-sizing: border-box;
}

.stat-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06), 0 8px 24px rgba(0, 0, 0, 0.05);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon.blue { background: rgba(30, 64, 175, 0.1); color: #1E40AF; }
.stat-icon.green { background: rgba(16, 185, 129, 0.1); color: #10B981; }
.stat-icon.amber { background: rgba(245, 158, 11, 0.1); color: #F59E0B; }
.stat-icon.cyan { background: rgba(6, 182, 212, 0.1); color: #06B6D4; }

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1F2937;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: #6B7280;
  margin-top: 2px;
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
}

.stat-trend.up {
  color: #10B981;
  background: rgba(16, 185, 129, 0.1);
}

.stat-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
}

.stat-badge.normal {
  color: #10B981;
  background: rgba(16, 185, 129, 0.1);
}

/* Content Grid */
.content-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  align-items: stretch;
}

.grid-left,
.grid-right {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 0;
}

.content-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03);
  box-sizing: border-box;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.card-header h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1F2937;
  margin: 0;
}

/* Shortcuts */
.shortcuts-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  flex: 1;
}

.shortcut-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #F8FAFC;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  min-height: 36px;
}

.shortcut-item:hover {
  background: #EEF2FF;
}

.shortcut-item:hover .arrow-icon {
  opacity: 1;
  color: #1E40AF;
}

.shortcut-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.shortcut-text {
  flex: 1;
  font-size: 13px;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow-icon {
  color: #9CA3AF;
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

/* Hot List */
.hot-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  flex: 1;
}

.hot-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  cursor: pointer;
  min-height: 32px;
}

.hot-item:hover .hot-name {
  color: #1E40AF;
}

.hot-rank {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1E40AF;
  color: #fff;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.hot-name {
  flex: 1;
  font-size: 13px;
  color: #374151;
  transition: color 0.15s;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hot-count {
  font-size: 11px;
  color: #9CA3AF;
  flex-shrink: 0;
}

/* Trend Chart */
.trend-container {
  flex: 1;
  min-height: 0;
}

/* Sessions */
.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  flex: 1;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #F8FAFC;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  min-height: 36px;
}

.session-item:hover {
  background: #F0F4FF;
}

.session-icon {
  color: #9CA3AF;
  flex-shrink: 0;
}

.session-icon.starred {
  color: #F59E0B;
}

.session-content {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  color: #374151;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.session-time {
  font-size: 11px;
  color: #9CA3AF;
  margin-top: 2px;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: #9CA3AF;
  font-size: 13px;
  gap: 8px;
  flex: 1;
}

/* Shortcut Editor */
.shortcut-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.shortcut-edit-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.shortcut-edit-row .icon-input {
  width: 60px;
  flex-shrink: 0;
}

.shortcut-edit-row .text-input {
  flex: 1;
}

/* Responsive */
@media (max-width: 1024px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .content-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }
}

@media (max-width: 768px) {
  .ai-assistant-dashboard {
    padding: 20px 16px;
  }

  .hero-section {
    padding: 32px 0 40px;
  }

  .hero-section h1 {
    font-size: 24px;
  }

  .hero-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .btn {
    justify-content: center;
  }

  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>
