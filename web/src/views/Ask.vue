<template>
  <div class="ask-page">
    <!-- 背景装饰 -->
    <div class="bg-gradient"></div>

    <!-- 左侧会话历史 -->
    <aside class="session-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <h3 v-if="!sidebarCollapsed">会话历史</h3>
        <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path v-if="sidebarCollapsed" d="M6 5L11 9L6 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path v-else d="M12 5L7 9L12 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>

      <div class="session-list" v-if="!sidebarCollapsed">
        <AskSessionCard
          v-for="session in sessionHistory"
          :key="session.id || session.session_id"
          :session="session"
          :is-active="sessionId === (session.id || session.session_id)"
          @click="loadSession(session.id || session.session_id)"
          @star="toggleStarSession(session)"
        />

        <div v-if="!sessionHistory.length" class="empty-sessions">
          暂无历史会话
        </div>
      </div>

      <div class="sidebar-footer" v-if="!sidebarCollapsed">
        <button class="new-chat-btn" @click="createNewSession">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          新建对话
        </button>
      </div>
    </aside>

    <!-- 主聊天区域 -->
    <div class="chat-main">
      <!-- 头部 -->
      <header class="chat-header">
        <div class="header-left">
          <el-popover placement="bottom" :width="280" trigger="click">
            <template #reference>
              <div class="ai-avatar" :style="aiAvatarStyle">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/>
                  <circle cx="12" cy="9" r="2.5" fill="currentColor"/>
                  <circle cx="12" cy="15" r="1.5" fill="currentColor" opacity="0.5"/>
                  <path d="M9 15C9 15 10.2 18 12 18C13.8 18 15 15 15 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </div>
            </template>
            <div class="ai-avatar-settings">
              <div class="ai-avatar-preview" :style="aiAvatarStyle">{{ aiAvatarPreviewLetter }}</div>
              <div class="ai-avatar-presets">
                <div
                  v-for="(preset, index) in aiPresets"
                  :key="index"
                  class="ai-preset-item"
                  :class="{ active: aiAvatarPreset === preset.bg }"
                  :style="{ background: preset.bg }"
                  @click="selectAiPreset(preset)"
                >
                  <span class="ai-preset-letter">{{ preset.letter }}</span>
                </div>
              </div>
              <el-upload
                class="ai-avatar-uploader"
                :show-file-list="false"
                :before-upload="handleAiUpload"
                accept="image/*"
              >
                <el-button size="small" class="ai-upload-btn">上传自定义头像</el-button>
              </el-upload>
            </div>
          </el-popover>
          <div class="header-info">
            <h2>智能问数助手</h2>
            <div class="status-indicator">
              <span class="status-dot"></span>
              在线
            </div>
          </div>
        </div>
        <div class="header-actions">
          <button class="action-btn" @click="showPreferencesPanel = true" title="偏好设置">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <circle cx="9" cy="9" r="2" stroke="currentColor" stroke-width="1.5"/>
              <path d="M9 1V3M9 15V17M1 9H3M15 9H17M3.3 3.3L4.7 4.7M13.3 13.3L14.7 14.7M3.3 14.7L4.7 13.3M13.3 4.7L14.7 3.3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <el-dropdown trigger="click" @command="handleCommand">
            <button class="action-btn">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <circle cx="9" cy="4" r="1.5" fill="currentColor"/>
                <circle cx="9" cy="9" r="1.5" fill="currentColor"/>
                <circle cx="9" cy="14" r="1.5" fill="currentColor"/>
              </svg>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="clear">清空当前对话</el-dropdown-item>
                <el-dropdown-item command="export">导出对话记录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 消息区域 -->
      <div class="chat-messages" ref="messagesContainer">
        <!-- 欢迎界面 -->
        <div v-if="!messages.length" class="welcome-screen">
          <div class="welcome-icon">
            <svg width="56" height="56" viewBox="0 0 56 56" fill="none">
              <circle cx="28" cy="28" r="24" stroke="var(--accent)" stroke-width="2" opacity="0.3"/>
              <circle cx="28" cy="28" r="16" stroke="var(--accent)" stroke-width="2" opacity="0.5"/>
              <circle cx="28" cy="28" r="8" stroke="var(--accent)" stroke-width="2"/>
              <circle cx="28" cy="22" r="3" fill="var(--accent)"/>
            </svg>
          </div>
          <h1>有什么可以帮您的？</h1>
          <p>可以问我关于指标数据、业务口径、技术口径等问题</p>
        </div>

        <!-- 消息列表 -->
        <transition-group name="message" tag="div" class="message-list">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            class="message"
            :class="msg.role"
          >
            <div
              class="message-avatar"
              :class="msg.role"
              :style="msg.role === 'assistant' ? aiAvatarStyle : userAvatarStyle"
            >
              <!-- 用户头像：仅在未配置头像时显示默认图标 -->
              <template v-if="msg.role === 'user' && !hasUserAvatar">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style="color: rgba(255,255,255,0.9)">
                  <circle cx="10" cy="7" r="4" fill="currentColor"/>
                  <path d="M3 18C3 15.2 6.1 13 10 13C13.9 13 17 15.2 17 18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </template>
              <!-- AI头像：仅在未配置头像时显示默认图标 -->
              <template v-if="msg.role === 'assistant' && !hasAiAvatar">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
                  <circle cx="10" cy="8" r="2" fill="currentColor"/>
                  <circle cx="10" cy="13" r="1.2" fill="currentColor" opacity="0.5"/>
                  <path d="M7.5 13C7.5 13 8.5 15.5 10 15.5C11.5 15.5 12.5 13 12.5 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </template>
            </div>

            <div class="message-bubble">
              <!-- 思考过程 -->
              <div v-if="msg.thinking_steps && msg.thinking_steps.length > 0" class="thinking-process">
                <div class="thinking-header" @click="toggleThinking(msg)">
                  <div class="thinking-status">
                    <svg v-if="msg.thinking_expanded" width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M3 5L6 8L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    <svg v-else width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M5 3L8 6L5 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    <span>查看分析过程</span>
                  </div>
                  <div class="thinking-progress">
                    <span
                      v-for="(step, sIdx) in msg.thinking_steps"
                      :key="sIdx"
                      class="progress-dot"
                      :class="step.status"
                    ></span>
                  </div>
                </div>
                <div v-if="msg.thinking_expanded" class="thinking-details">
                  <div
                    v-for="(step, sIdx) in msg.thinking_steps"
                    :key="sIdx"
                    class="thinking-step"
                    :class="step.status"
                  >
                    <div class="step-indicator">
                      <span class="step-icon">
                        <svg v-if="step.status === 'completed'" width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                          <path d="M4 7L6 9L10 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                        <svg v-else-if="step.status === 'error'" width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                          <path d="M5 5L9 9M9 5L5 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                        <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                        </svg>
                      </span>
                      <span class="step-name">{{ step.step }}</span>
                    </div>
                    <div v-if="step.content" class="step-content">{{ step.content }}</div>
                  </div>
                  <!-- SQL 步骤 -->
                  <div v-if="msg.sql" class="thinking-step completed">
                    <div class="step-indicator">
                      <span class="step-icon">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                          <path d="M4 7L6 9L10 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                      </span>
                      <span class="step-name">SQL 生成</span>
                    </div>
                    <div class="step-content sql-content">
                      <pre><code>{{ msg.sql }}</code></pre>
                    </div>
                  </div>
                </div>
              </div>

              <div class="message-content" v-if="(!msg.result_data || msg.result_data.length === 0) && (!msg.needs_clarification || !msg.matched_metrics || msg.matched_metrics.length === 0)" v-html="formatMessage(msg.content)"></div>

              <!-- 指标候选选择 -->
              <div v-if="msg.needs_clarification && msg.matched_metrics && msg.matched_metrics.length > 0" class="metric-candidates">
                <div class="candidates-header">请选择要查询的指标：</div>
                <div class="candidates-list">
                  <div
                    v-for="(metric, idx) in msg.matched_metrics"
                    :key="idx"
                    class="candidate-item"
                    :class="{ selected: selectedCandidateIdx === idx }"
                    @click="selectMetricCandidate(idx, metric)"
                  >
                    <span class="candidate-name">{{ metric.name || metric.metric_name }}</span>
                    <span class="candidate-code">{{ metric.metric_code }}</span>
                  </div>
                </div>
              </div>

              <!-- 查询结果表格 -->
              <div v-if="msg.result_data && msg.result_data.length > 0" class="result-table">
                <div class="result-table-header">
                  <span>查询结果</span>
                  <span v-if="msg.total" class="result-total">(共 {{ msg.total }} 条)</span>
                </div>
                <div class="result-table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th v-for="(value, key) in msg.result_data[0]" :key="key">{{ key }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, rowIdx) in msg.result_data" :key="rowIdx">
                        <td v-for="(value, key) in row" :key="key">{{ value }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <!-- 分页 -->
                <div v-if="msg.total && msg.total > 10" class="result-pagination">
                  <el-pagination
                    small
                    layout="prev, pager, next"
                    :total="msg.total"
                    :page-size="msg.page_size || 10"
                    :current-page="msg.page || 1"
                    @current-change="(p) => handlePageChange(p, msg)"
                  />
                </div>
              </div>

              <!-- 下钻维度标签 -->
              <div v-if="msg.drill_down_dims && msg.drill_down_dims.length > 0" class="drill-down-section">
                <div class="drill-down-label">
                  <svg class="label-icon" width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 1L8.5 5H13L9.5 7.5L11 12L7 9L3 12L4.5 7.5L1 5H5.5L7 1Z" fill="currentColor"/>
                  </svg>
                  <span>推荐下钻维度:</span>
                </div>
                <div class="drill-down-tags">
                  <el-tag
                    v-for="dim in msg.drill_down_dims"
                    :key="dim.dimension_name"
                    :type="isDimSelected(dim.dimension_name, msg) ? 'primary' : 'info'"
                    :closable="false"
                    class="drill-down-tag"
                    :class="{ 'dim-selected': isDimSelected(dim.dimension_name, msg) }"
                    @click="toggleDimSelection(dim.dimension_name, msg)"
                  >
                    {{ isDimSelected(dim.dimension_name, msg) ? '✓ ' : '' }}{{ dim.dimension_name }}
                  </el-tag>
                </div>
                <div v-if="hasSelectedDims(msg)" class="drill-down-actions">
                  <el-button type="primary" size="small" class="drill-down-btn" @click="handleDrillDown(msg)">
                    确定下钻
                  </el-button>
                  <el-button size="small" @click="clearDimSelection(msg)">取消</el-button>
                </div>
              </div>

              <!-- 面包屑导航 -->
              <div v-if="msg.breadcrumbs && msg.breadcrumbs.length > 0" class="breadcrumb-section">
                <div class="breadcrumb-nav">
                  <span
                    v-for="(crumb, cIdx) in msg.breadcrumbs"
                    :key="cIdx"
                    class="breadcrumb-item"
                    :class="{ clickable: cIdx < msg.breadcrumbs.length - 1 }"
                    @click="cIdx < msg.breadcrumbs.length - 1 && handleBreadcrumbClick(crumb, cIdx, msg)"
                  >
                    {{ crumb.name }}
                    <span v-if="cIdx < msg.breadcrumbs.length - 1" class="breadcrumb-sep">›</span>
                  </span>
                </div>
                <el-button v-if="msg.breadcrumbs.length > 1" size="small" class="back-btn" @click="handleBack(msg)">
                  返回
                </el-button>
              </div>

              <div class="message-time">{{ formatMessageTime(msg.created_at) }}</div>

              <!-- 反馈按钮 -->
              <div v-if="msg.role === 'assistant'" class="message-feedback">
                <span class="feedback-label">回答满意吗？</span>
                <button
                  class="feedback-btn thumbs-up"
                  :class="{ active: msg.feedback === 1 }"
                  @click="handleFeedback(index, 1)"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 12C7 12 3 9 3 5.5C3 3.6 4.3 2 6 2C6.8 2 7.5 2.5 7 3C6.5 2.5 7.2 2 8 2C9.7 2 11 3.6 11 5.5C11 9 7 12 7 12Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
                <button
                  class="feedback-btn thumbs-down"
                  :class="{ active: msg.feedback === -1 }"
                  @click="handleFeedback(index, -1)"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 2C7 2 11 5 11 8.5C11 10.4 9.7 12 8 12C7.2 12 6.5 11.5 7 11C7.5 11.5 6.8 12 6 12C4.3 12 3 10.4 3 8.5C3 5 7 2 7 2Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </transition-group>

        <!-- 加载动画 -->
        <div v-if="loading" class="message assistant">
          <div class="message-avatar assistant" :style="aiAvatarStyle">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
              <circle cx="10" cy="8" r="2" fill="currentColor"/>
              <circle cx="10" cy="13" r="1.2" fill="currentColor" opacity="0.5"/>
              <path d="M7.5 13C7.5 13 8.5 15.5 10 15.5C11.5 15.5 12.5 13 12.5 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="message-bubble">
            <div class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 操作栏 -->
      <div class="action-bar">
        <button class="bar-btn" @click="handleMyFavorites">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 14L2 9C1 8 1 6.5 2 5.5C3 4.5 4.5 4 5.5 4.5L8 6L10.5 4.5C11.5 4 13 4.5 14 5.5C15 6.5 15 8 14 9L8 14Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>我的收藏</span>
        </button>
        <button class="bar-btn" @click="handleRecommendQuestions">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5"/>
            <path d="M8 5V8M8 11V11.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>推荐问题</span>
        </button>
        <button class="bar-btn" @click="handleRecentQuestions">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5"/>
            <path d="M8 5L8 8L10 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>最近提问</span>
        </button>
        <button class="bar-btn" @click="handleClearContext">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 4H13M6 4V3C6 2.5 6.5 2 7 2H9C9.5 2 10 2.5 10 3V4M12 4V13C12 13.5 11.5 14 11 14H5C4.5 14 4 13.5 4 13V4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>清空上下文</span>
        </button>
      </div>

      <!-- 输入区域 -->
      <div class="chat-input-area">
        <div class="input-wrapper">
          <el-input
            v-model="inputText"
            placeholder="输入您的问题..."
            @keyup.enter="handleSend"
            :disabled="loading"
            resize="none"
            type="textarea"
            autosize
            class="chat-input"
          />
          <button class="send-btn" @click="handleSend" :disabled="loading || !inputText.trim()">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M3 9L15 9M15 9L10 4M15 9L10 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
        <div class="input-hint">
          按 Enter 发送，Shift + Enter 换行
        </div>
      </div>
    </div>

    <!-- 偏好设置面板 -->
    <AskPreferencesPanel v-model="showPreferencesPanel" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { askAPI } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import AskPreferencesPanel from './components/AskPreferencesPanel.vue'
import AskSessionCard from './components/AskSessionCard.vue'

const route = useRoute()

const inputText = ref('')
const messages = ref([])
const loading = ref(false)
const sessionId = ref(localStorage.getItem('ask_session_id') || '')
const sessionHistory = ref([])
const sidebarCollapsed = ref(false)
const messagesContainer = ref(null)
const showPreferencesPanel = ref(false) // 偏好设置面板
const selectedCandidateIdx = ref(null) // 当前选中的候选指标索引

// 下钻相关
const selectedDims = ref({})  // { messageIndex: ['维度1', '维度2'] }
const currentMetricCode = ref('')
const currentSQL = ref('')
const currentGroupBy = ref('')
const drillHistory = ref([])  // 下钻历史，用于返回 { sql, groupBy, breadcrumbs, result_data, ... }

// Avatar configuration
const presetAvatars = [
  { bg: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)', letter: 'A', color: '#fff' },
  { bg: 'linear-gradient(135deg, #00A870 0%, #007B50 100%)', letter: 'B', color: '#fff' },
  { bg: 'linear-gradient(135deg, #722ED1 0%, #4A1080 100%)', letter: 'C', color: '#fff' },
  { bg: 'linear-gradient(135deg, #F5222D 0%, #C41230 100%)', letter: 'D', color: '#fff' },
  { bg: 'linear-gradient(135deg, #FA8C16 0%, #D46B08 100%)', letter: 'E', color: '#fff' },
  { bg: 'linear-gradient(135deg, #52C41A 0%, #389E0D 100%)', letter: 'F', color: '#fff' },
  { bg: 'linear-gradient(135deg, #13C2C2 0%, #08979C 100%)', letter: 'G', color: '#fff' },
  { bg: 'linear-gradient(135deg, #FA541C 0%, #C54B1C 100%)', letter: 'H', color: '#fff' },
]

// AI Avatar presets (different from user)
const aiPresets = [
  { bg: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #722ED1 0%, #4A1080 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #00A870 0%, #007B50 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #F5222D 0%, #C41230 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #FA8C16 0%, #D46B08 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #13C2C2 0%, #08979C 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)', letter: 'AI' },
  { bg: 'linear-gradient(135deg, #EC4899 0%, #BE185D 100%)', letter: 'AI' },
]

const aiAvatarPreset = ref('')
const aiAvatarCustom = ref('')

const userAvatarStyle = computed(() => {
  const custom = localStorage.getItem('user_avatar_custom')
  const preset = localStorage.getItem('user_avatar_preset')
  if (custom) {
    return { background: `url(${custom}) center/cover` }
  }
  if (preset) {
    return { background: preset }
  }
  return { background: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)' }
})

const hasUserAvatar = computed(() => {
  return localStorage.getItem('user_avatar_custom') || localStorage.getItem('user_avatar_preset')
})

const hasAiAvatar = computed(() => {
  return localStorage.getItem('ai_avatar_custom') || localStorage.getItem('ai_avatar_preset')
})

const aiAvatarStyle = computed(() => {
  if (aiAvatarCustom.value) {
    return { background: `url(${aiAvatarCustom.value}) center/cover`, color: 'transparent' }
  }
  if (aiAvatarPreset.value) {
    return { background: aiAvatarPreset.value }
  }
  return { background: 'linear-gradient(135deg, #1677FF 0%, #0055E5 100%)' }
})

const aiAvatarPreviewLetter = computed(() => {
  if (aiAvatarCustom.value) return ''
  if (aiAvatarPreset.value) {
    const preset = aiPresets.find(p => p.bg === aiAvatarPreset.value)
    return preset ? preset.letter : 'AI'
  }
  return 'AI'
})

function selectAiPreset(preset) {
  aiAvatarPreset.value = preset.bg
  aiAvatarCustom.value = ''
  localStorage.setItem('ai_avatar_preset', preset.bg)
  localStorage.setItem('ai_avatar_custom', '')
}

function handleAiUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    aiAvatarCustom.value = e.target.result
    aiAvatarPreset.value = ''
    localStorage.setItem('ai_avatar_custom', e.target.result)
    localStorage.setItem('ai_avatar_preset', '')
  }
  reader.readAsDataURL(file)
  return false
}

function loadAiAvatarConfig() {
  aiAvatarPreset.value = localStorage.getItem('ai_avatar_preset') || ''
  aiAvatarCustom.value = localStorage.getItem('ai_avatar_custom') || ''
}

const quickQueries = [
  { icon: '📊', text: '昨天的访客数是多少' },
  { icon: '📈', text: '本周订单量如何' },
  { icon: '📉', text: '本月销售额趋势' },
  { icon: '📝', text: '广告转化率的业务口径是什么' },
]

onMounted(() => {
  loadAiAvatarConfig()
  loadSessionHistory()

  // 处理 URL 参数中的问题或会话
  const questionParam = route.query.q
  const sessionParam = route.query.session_id

  if (questionParam && typeof questionParam === 'string') {
    inputText.value = questionParam
    setTimeout(() => {
      handleSend()
    }, 100)
  } else if (sessionParam && typeof sessionParam === 'string') {
    // 从 Dashboard 加载指定会话
    loadSession(sessionParam)
  } else if (sessionId.value) {
    loadSession(sessionId.value)
  }
})

async function loadSessionHistory() {
  try {
    // 使用 /sessions 端点获取所有会话列表
    const res = await askAPI.getSessions()
    console.log('API 响应:', res)
    if (res.data) {
      sessionHistory.value = [...res.data]
      console.log('更新后的 sessionHistory:', sessionHistory.value)
    }
  } catch (e) {
    console.error('加载会话历史失败:', e)
  }
}

async function toggleStarSession(session) {
  try {
    const sessionIdToUse = session.id || session.session_id
    await askAPI.starSession(sessionIdToUse)
    // 更新本地状态
    session.starred = !session.starred
  } catch (e) {
    console.error('星标失败:', e)
    ElMessage.error('星标失败')
  }
}

async function loadSession(id) {
  try {
    const res = await askAPI.getHistory(id)
    if (res.data?.messages) {
      sessionId.value = id
      localStorage.setItem('ask_session_id', id)
      messages.value = res.data.messages.map(m => ({
        role: m.role,
        content: m.content,
        sql: m.sql,
        created_at: m.created_at,
        thinking_expanded: true,
        thinking_steps: []
      }))
      await scrollToBottom()
    }
  } catch (e) {}
}

async function createNewSession() {
  sessionId.value = ''
  localStorage.removeItem('ask_session_id')
  messages.value = []
  await loadSessionHistory()
}

async function deleteSession(id) {
  try {
    await ElMessageBox.confirm('确定要删除这个会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await askAPI.clearSession(id)
    // 删除成功后，直接从本地列表中移除
    const idx = sessionHistory.value.findIndex(s => s.id === id)
    if (idx !== -1) {
      sessionHistory.value.splice(idx, 1)
    }
    if (sessionId.value === id) {
      await createNewSession()
    }
    ElMessage.success('删除成功')
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除会话失败:', e)
      ElMessage.error('删除失败，请重试')
    }
  }
}

async function handleSend() {
  if (!inputText.value.trim() || loading.value) return

  // 清空下钻历史
  drillHistory.value = []
  const question = inputText.value.trim()
  inputText.value = ''

  messages.value.push({
    role: 'user',
    content: question,
    created_at: new Date().toISOString(),
    thinking_expanded: true,
    thinking_steps: []
  })

  await scrollToBottom()
  loading.value = true

  try {
    const res = await askAPI.ask({
      question,
      session_id: sessionId.value || undefined
    })

    if (res.data) {
      console.log('AI 响应 result_data:', res.data.result_data)
      if (!sessionId.value && res.data.session_id) {
        sessionId.value = res.data.session_id
        localStorage.setItem('ask_session_id', sessionId.value)
        await loadSessionHistory()
      }

      // 保存 metric_code 和 sql（从 thinking_steps 或响应中提取）
      const metricCode = extractMetricCode(res.data)
      const sql = res.data.sql || ''
      if (metricCode) currentMetricCode.value = metricCode
      if (sql) currentSQL.value = sql

      messages.value.push({
        role: 'assistant',
        content: res.data.answer,
        sql: res.data.sql,
        result_data: res.data.result_data || null,
        drill_down_dims: res.data.drill_down_dims || [],
        breadcrumbs: res.data.breadcrumbs || [],
        created_at: new Date().toISOString(),
        thinking_expanded: false,
        thinking_steps: res.data.thinking_steps || [],
        needs_clarification: res.data.needs_clarification || false,
        clarification_message: res.data.clarification_message || null,
        clarification_type: res.data.clarification_type || null,
        matched_metrics: res.data.matched_metrics || []
      })
    }
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，服务暂时不可用，请稍后再试。',
      created_at: new Date().toISOString(),
      thinking_expanded: false,
      thinking_steps: []
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

// 从响应中提取 metric_code
function extractMetricCode(data) {
  if (data.metric_code) return data.metric_code
  // 从 thinking_steps 中查找
  if (data.thinking_steps) {
    for (const step of data.thinking_steps) {
      if (step.content && step.content.includes('指标：')) {
        const match = step.content.match(/指标[：:]\s*([^\s|]+)/)
        if (match) return match[1]
      }
    }
  }
  return ''
}

function handleSuggest(text) {
  inputText.value = text
  handleSend()
}

// 选择指标候选
function selectMetricCandidate(idx, metric) {
  selectedCandidateIdx.value = idx
  // 用「指标名（编号）」作为新问题发送
  const question = `${metric.name || metric.metric_name}（${metric.metric_code}）`
  inputText.value = question
  handleSend()
}

async function handleCommand(command) {
  if (command === 'clear') {
    messages.value = []
    ElMessage.success('对话已清空')
  } else if (command === 'export') {
    const content = messages.value.map(m =>
      `${m.role === 'user' ? '我' : '助手'}：${m.content}`
    ).join('\n\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `对话记录_${new Date().toLocaleDateString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function toggleThinking(msg) {
  msg.thinking_expanded = !msg.thinking_expanded
}

function formatTime(time) {
  if (!time) return ''
  const d = new Date(time)
  const now = new Date()
  const diff = now - d

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatMessageTime(time) {
  if (!time) return ''
  return new Date(time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatMessage(content) {
  if (!content) return ''
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

async function handleFeedback(index, feedback) {
  const msg = messages.value[index]
  if (msg.feedback) {
    ElMessage.info('您已经反馈过了')
    return
  }

  msg.feedback = feedback

  try {
    await askAPI.sendFeedback({
      session_id: sessionId.value,
      turn_index: index,
      feedback: feedback,
      metric_id: msg.metric_id || null,
      clarification_type: msg.clarification_type || null,
      clarification_question: msg.clarification_question || null
    })
    ElMessage.success(feedback === 1 ? '感谢您的肯定！' : '感谢您的反馈，我们会继续优化')
  } catch (e) {
    msg.feedback = null
    ElMessage.error('反馈失败，请重试')
  }
}

// 下钻相关方法
function isDimSelected(dimName, msg) {
  const index = messages.value.indexOf(msg)
  return selectedDims.value[index]?.includes(dimName) || false
}

function hasSelectedDims(msg) {
  const index = messages.value.indexOf(msg)
  return selectedDims.value[index]?.length > 0
}

function toggleDimSelection(dimName, msg) {
  const index = messages.value.indexOf(msg)
  if (!selectedDims.value[index]) {
    selectedDims.value[index] = []
  }
  const idx = selectedDims.value[index].indexOf(dimName)
  if (idx >= 0) {
    selectedDims.value[index].splice(idx, 1)
  } else {
    selectedDims.value[index].push(dimName)
  }
}

function clearDimSelection(msg) {
  const index = messages.value.indexOf(msg)
  selectedDims.value[index] = []
}

async function handleDrillDown(msg) {
  const index = messages.value.indexOf(msg)
  const selected = selectedDims.value[index] || []
  if (selected.length === 0) {
    ElMessage.warning('请选择至少一个维度')
    return
  }

  // 保存当前上下文到历史（用于返回）
  drillHistory.value.push({
    sql: currentSQL.value,
    groupBy: currentGroupBy.value,
    breadcrumbs: JSON.parse(JSON.stringify(msg.breadcrumbs || [])),
    result_data: msg.result_data,
    drill_down_dims: msg.drill_down_dims,
    content: msg.content
  })

  loading.value = true
  try {
    const res = await askAPI.drillDown({
      session_id: sessionId.value,
      dimension_names: selected,
      metric_code: currentMetricCode.value,
      current_sql: currentSQL.value,
      current_group_by: currentGroupBy.value
    })

    if (res.data) {
      console.log('下钻响应:', res.data)
      // 保存下钻后的上下文
      currentSQL.value = res.data.sql
      currentGroupBy.value = res.data.breadcrumbs?.map(b => b.value).join(',') || ''

      // 更新当前消息，而不是创建新消息
      msg.content = res.data.answer
      msg.sql = res.data.sql
      msg.result_data = res.data.result_data || null
      msg.drill_down_dims = res.data.drill_down_dims || []
      msg.breadcrumbs = res.data.breadcrumbs || []
      msg.thinking_expanded = false
      await scrollToBottom()
    }
  } catch (e) {
    ElMessage.error('下钻失败，请重试')
  } finally {
    loading.value = false
    clearDimSelection(msg)
    await scrollToBottom()
  }
}

async function handlePageChange(page, msg) {
  // 处理分页切换 - 重新查询当前消息的数据
  const index = messages.value.indexOf(msg)
  loading.value = true
  try {
    const res = await askAPI.ask({
      question: msg.content || '当前数据',
      session_id: sessionId.value,
      page: page,
      page_size: 10
    })

    if (res.data) {
      msg.result_data = res.data.result_data || null
      msg.page = res.data.page
      msg.page_size = res.data.page_size
      msg.total = res.data.total
      msg.sql = res.data.sql
      await scrollToBottom()
    }
  } catch (e) {
    ElMessage.error('分页查询失败')
  } finally {
    loading.value = false
  }
}

async function handleBreadcrumbClick(crumb, cIdx, msg) {
  // 返回到指定层级 - 从历史中恢复
  if (drillHistory.value.length === 0) {
    ElMessage.warning('没有可返回的历史')
    return
  }

  // 弹出从当前层级之前的历史
  const previousState = drillHistory.value[drillHistory.value.length - 1]
  drillHistory.value.pop()

  // 恢复状态
  currentSQL.value = previousState.sql
  currentGroupBy.value = previousState.groupBy

  // 恢复消息内容
  msg.content = previousState.content
  msg.sql = previousState.sql
  msg.result_data = previousState.result_data
  msg.drill_down_dims = previousState.drill_down_dims
  msg.breadcrumbs = previousState.breadcrumbs

  ElMessage.success(`已返回到: ${crumb.name}`)
  await scrollToBottom()
}

async function handleBack(msg) {
  // 返回上一级
  if (msg.breadcrumbs && msg.breadcrumbs.length > 1) {
    const parentCrumb = msg.breadcrumbs[msg.breadcrumbs.length - 2]
    await handleBreadcrumbClick(parentCrumb, msg.breadcrumbs.length - 2, msg)
  } else if (drillHistory.value.length > 0) {
    // 如果没有面包屑但有历史，也允许返回
    const previousState = drillHistory.value[drillHistory.value.length - 1]
    drillHistory.value.pop()
    currentSQL.value = previousState.sql
    currentGroupBy.value = previousState.groupBy
    msg.content = previousState.content
    msg.sql = previousState.sql
    msg.result_data = previousState.result_data
    msg.drill_down_dims = previousState.drill_down_dims
    msg.breadcrumbs = previousState.breadcrumbs
    ElMessage.success('已返回上一级')
    await scrollToBottom()
  } else {
    ElMessage.warning('没有可返回的历史')
  }
}

// 操作栏方法
function handleMyFavorites() {
  ElMessage.info('我的收藏功能开发中')
}

function handleRecommendQuestions() {
  ElMessage.info('推荐问题功能开发中')
}

function handleRecentQuestions() {
  ElMessage.info('最近提问功能开发中')
}

async function handleClearContext() {
  try {
    await ElMessageBox.confirm('确定要清空当前会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await askAPI.clearSession(sessionId.value)
    messages.value = []
    currentMetricCode.value = ''
    currentSQL.value = ''
    currentGroupBy.value = ''
    selectedDims.value = {}
    ElMessage.success('上下文已清空')
  } catch (e) {}
}
</script>

<style scoped>
.ask-page {
  height: 100vh;
  display: flex;
  position: relative;
  overflow: hidden;
  background: var(--bg-primary);
}

/* 背景装饰 */
.bg-gradient {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-primary);
  pointer-events: none;
}

/* 侧边栏 */
.session-sidebar {
  width: 220px;
  background: var(--bg-card);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  position: relative;
  z-index: 10;
  border-right: 1px solid var(--border);
}

.session-sidebar.collapsed {
  width: 0;
  overflow: hidden;
}

.sidebar-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-header h3 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.collapse-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 0.15s;
}

.collapse-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 2px;
}

.session-item:hover {
  background: var(--bg-primary);
}

.session-item.active {
  background: var(--primary-glow);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-item.active .session-title {
  color: var(--primary);
}

.session-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.delete-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 0.15s;
}

.delete-btn:hover {
  background: #fef2f2;
  color: #ef4444;
}

.empty-sessions {
  text-align: center;
  padding: 40px 16px;
  color: var(--text-muted);
  font-size: 13px;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border);
}

.new-chat-btn {
  width: 100%;
  padding: 10px;
  border: 1px dashed var(--border);
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.new-chat-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-glow);
}

/* 主聊天区域 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 5;
}

/* 头部 */
.chat-header {
  padding: 16px 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ai-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
}

.header-info h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #16a34a;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #16a34a;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.action-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.action-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

/* 消息区域 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.welcome-screen {
  text-align: center;
  padding: 60px 20px;
  animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.welcome-icon {
  margin-bottom: 20px;
}

.welcome-screen h1 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.welcome-screen p {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 28px;
}

.quick-queries {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  max-width: 480px;
  margin: 0 auto;
}

.quick-query {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid var(--border);
}

.quick-query:hover {
  border-color: var(--primary);
  background: var(--primary-glow);
}

.query-icon {
  font-size: 18px;
}

.query-text {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

/* 消息列表 */
.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 10px;
}

@keyframes messageIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-avatar.user {
  /* User avatar style is set via inline style from userAvatarStyle */
}

.message-avatar.assistant {
  color: #ffffff;
}

.message-bubble {
  max-width: 72%;
  min-width: 60px;
}

.message-content {
  background: var(--bg-card);
  padding: 12px 16px;
  border-radius: 20px;
  border: 1px solid var(--border);
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
}

.message.user .message-content {
  background: var(--primary);
  color: #ffffff;
  border: none;
}

.message-sql {
  margin-top: 12px;
  background: #1E1E2E;
  border-radius: 10px;
  overflow: hidden;
}

.sql-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: #2D2D3F;
  font-size: 11px;
  font-weight: 600;
  color: #A6ADC8;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.message-sql pre {
  padding: 16px;
  margin: 0;
  overflow-x: auto;
}

.message-sql code {
  font-size: 13px;
  font-family: 'JetBrains Mono', 'SF Mono', Monaco, monospace;
  color: #CDD6F4;
  line-height: 1.6;
}

.message-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  text-align: right;
}

.message.user .message-time {
  text-align: left;
}

/* 思考过程 */
.thinking-process {
  margin-bottom: 12px;
  background: var(--bg-card);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
}

.thinking-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.15s;
  background: var(--bg-primary);
  border-radius: 8px;
}

.thinking-header:hover {
  background: var(--border);
}

.thinking-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
}

.thinking-progress {
  display: flex;
  align-items: center;
  gap: 4px;
}

.progress-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #d4d4d8;
  transition: all 0.2s;
}

.progress-dot.completed {
  background: #16a34a;
}

.progress-dot.error {
  background: #dc2626;
}

.progress-dot.pending {
  background: #d4d4d8;
  animation: pulse-dot 1.5s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.thinking-details {
  padding: 0 14px 12px;
  max-height: 300px;
  overflow-y: auto;
}

.sql-content {
  background: #1E1E2E;
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 6px;
  overflow-x: auto;
}

.sql-content pre {
  margin: 0;
}

.sql-content code {
  font-size: 12px;
  font-family: 'JetBrains Mono', 'SF Mono', Monaco, monospace;
  color: #CDD6F4;
  white-space: pre;
}

.thinking-step {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.thinking-step:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.step-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-icon {
  display: flex;
  align-items: center;
}

.thinking-step.completed .step-icon {
  color: #16a34a;
}

.thinking-step.error .step-icon {
  color: #dc2626;
}

.thinking-step.pending .step-icon {
  color: var(--text-muted);
}

.step-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.step-content {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  padding-left: 28px;
  word-break: break-all;
}

/* 反馈按钮 */
.message-feedback {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}

.feedback-label {
  font-size: 11px;
  color: var(--text-muted);
}

.feedback-btn {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 0.15s;
}

.feedback-btn:hover {
  background: var(--bg-primary);
}

.feedback-btn.thumbs-up:hover,
.feedback-btn.thumbs-up.active {
  color: #16a34a;
  background: #dcfce7;
}

.feedback-btn.thumbs-down:hover,
.feedback-btn.thumbs-down.active {
  color: #dc2626;
  background: #fef2f2;
}

/* 加载动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 7px;
  height: 7px;
  background: var(--text-muted);
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* 输入区域 */
.chat-input-area {
  padding: 14px 16px 18px;
  background: var(--bg-card);
  border-top: 1px solid var(--border);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: var(--bg-card);
  border-radius: 8px;
  padding: 8px 8px 8px 16px;
  border: 1px solid var(--border);
  transition: all 0.15s ease;
}

.input-wrapper:focus-within {
  border-color: var(--primary);
}

.chat-input {
  flex: 1;
}

.chat-input :deep(.el-textarea__inner) {
  border: none;
  padding: 6px 0;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  box-shadow: none !important;
  background: transparent;
}

.send-btn {
  width: 40px;
  height: 36px;
  border: none;
  background: var(--primary);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-light);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-hint {
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
  margin-top: 8px;
}

/* 消息过渡动画 */
.message-enter-active {
  transition: all 0.3s ease;
}
.message-leave-active {
  transition: all 0.2s ease;
}
.message-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.message-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* AI Avatar Settings */
.ai-avatar-settings {
  padding: 8px 0;
}

.ai-avatar-preview {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
  margin: 0 auto 16px;
  box-shadow: 0 4px 12px rgba(22, 119, 255, 0.35);
}

.ai-avatar-presets {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 0 4px;
  margin-bottom: 14px;
}

.ai-preset-item {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.ai-preset-item:hover {
  transform: scale(1.08);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.ai-preset-item.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-glow);
}

.ai-preset-letter {
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
}

.ai-avatar-uploader {
  display: flex;
  justify-content: center;
}

.ai-upload-btn {
  width: 100%;
  border: 1px dashed var(--border);
  color: var(--text-secondary);
  font-size: 12px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.ai-upload-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-glow);
}

/* 操作栏 */
.action-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-primary);
  border-top: 1px solid var(--border);
  justify-content: flex-start;
  flex-wrap: wrap;
}

.bar-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  transition: all 0.15s ease;
}

.bar-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-glow);
}

/* 查询结果表格 */
.result-table {
  margin-top: 12px;
  background: var(--bg-primary);
  border-radius: 10px;
  border: 1px solid var(--border);
  overflow: hidden;
}

.result-table-header {
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}

.result-table-wrapper {
  max-height: 240px;
  overflow-y: auto;
}

.result-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.result-table th {
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.result-table td {
  padding: 8px 12px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.result-table tbody tr:last-child td {
  border-bottom: none;
}

.result-table tbody tr:hover {
  background: var(--bg-primary);
}

.result-table-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-total {
  font-weight: normal;
  color: var(--text-secondary);
  font-size: 12px;
}

.result-pagination {
  display: flex;
  justify-content: center;
  padding: 8px;
  border-top: 1px solid var(--border);
}

/* 指标候选选择 */
.metric-candidates {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  border: 1px solid var(--border);
}
.candidates-header {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.candidates-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.candidate-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-white);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.candidate-item:hover {
  border-color: var(--color-primary);
  background: var(--bg-primary);
}
.candidate-item.selected {
  border-color: var(--color-primary);
  background: var(--bg-primary-light);
}
.candidate-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}
.candidate-code {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
}

/* 下钻维度 */
.drill-down-section {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 10px;
  border: 1px solid var(--border);
}

.drill-down-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--primary);
  margin-bottom: 10px;
  font-weight: 600;
}

.label-icon {
  color: var(--primary);
}

.drill-down-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.drill-down-tag {
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: 8px;
  font-size: 12px;
  padding: 4px 10px;
}

.drill-down-tag.dim-selected {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.drill-down-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.drill-down-btn {
  background: var(--primary);
  border-color: var(--primary);
}

/* 面包屑 */
.breadcrumb-section {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.breadcrumb-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.breadcrumb-item {
  color: var(--text-secondary);
  font-weight: 500;
}

.breadcrumb-item.clickable {
  cursor: pointer;
  color: var(--primary);
}

.breadcrumb-item.clickable:hover {
  text-decoration: underline;
}

.breadcrumb-sep {
  margin: 0 4px;
  color: var(--text-muted);
}

.back-btn {
  font-size: 12px;
  padding: 5px 14px;
  border-radius: 8px;
}
</style>
