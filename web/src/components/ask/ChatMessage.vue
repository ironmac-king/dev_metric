<template>
  <div class="chat-messages" ref="messagesContainer" :class="containerClasses">
    <!-- 欢迎界面 -->
    <div v-if="!messages.length && !progress" class="welcome-screen">
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

    <!-- 分析进度指示器 -->
    <div v-if="progress > 0 || progressStage" class="progress-indicator">
      <div class="progress-bar-container">
        <div class="progress-bar" :style="{ width: progress + '%' }"></div>
      </div>
      <div class="progress-stages">
        <span :class="{ active: progress >= 25 }">● 加载模板</span>
        <span :class="{ active: progress >= 50 }">● 计算洞察</span>
        <span :class="{ active: progress >= 75 }">● 生成解读</span>
        <span :class="{ active: progress >= 100 }">○ 完成</span>
      </div>
    </div>

    <!-- 文档样式切换按钮 -->
    <div v-if="messages.length > 0" class="document-style-toggle">
      <button
        class="toggle-btn"
        :class="{ active: enableDocumentStyle }"
        @click="enableDocumentStyle = !enableDocumentStyle"
        title="切换文档样式"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="2" y="1" width="10" height="12" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
          <path d="M4 4H10M4 7H10M4 10H8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
        <span>{{ enableDocumentStyle ? '文档样式' : '气泡样式' }}</span>
      </button>
      <button
        v-if="enableDocumentStyle"
        class="toggle-btn secondary"
        :class="{ active: mergeView }"
        @click="mergeView = !mergeView"
        title="合并/分离视图"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="1" y="2" width="5" height="10" rx="1" stroke="currentColor" stroke-width="1.2"/>
          <rect x="8" y="2" width="5" height="10" rx="1" stroke="currentColor" stroke-width="1.2"/>
        </svg>
        <span>{{ mergeView ? '合并视图' : '分离视图' }}</span>
      </button>
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
          <!-- 用户头像 -->
          <template v-if="msg.role === 'user' && !hasUserAvatar">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style="color: rgba(255,255,255,0.9)">
              <circle cx="10" cy="7" r="4" fill="currentColor"/>
              <path d="M3 18C3 15.2 6.1 13 10 13C13.9 13 17 15.2 17 18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </template>
          <!-- AI头像 -->
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
            <div class="thinking-header cursor-pointer" @click="toggleThinking(msg)">
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
                <div v-if="step.content" class="step-content" :class="{ warning: isWarningContent(step.content) }">{{ step.content }}</div>
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
                  <pre><code>{{ formatSQL(msg.sql) }}</code></pre>
                </div>
              </div>
            </div>
          </div>

          <!-- 文档样式渲染（enableDocumentStyle=true 时） -->
          <DocumentMessage
            v-if="enableDocumentStyle && msg.result_data && msg.result_data.length > 0 && msg.role === 'assistant'"
            :msg="msg"
            :user-feedback="msg.feedback"
            @select-suggestion="(item) => $emit('select-suggestion', item)"
            @export="handleExport"
            @share="handleShare"
            @copy="handleCopy"
            @toggle-thinking="toggleThinking(msg)"
            @feedback="(value) => $emit('feedback', index, value)"
            @drilldown="(dimValue) => $emit('drill-down', { ...msg, dimValue })"
            @retry="handleRetry"
            @view-alternative="handleViewAlternative"
          />

          <!-- 消息内容（当有result_data时不显示，因为表格里已有结果） -->
          <div class="message-content" v-if="editingMessageIndex !== index && (!msg.needs_clarification || !msg.matched_metrics || msg.matched_metrics.length === 0) && (!msg.result_data || msg.result_data.length === 0) && msg.content && msg.content.trim()" v-html="formatMessage(msg.content)"></div>

          <!-- 追问提示消息（当needs_clarification为true但没有候选选项时显示clarification_message） -->
          <div v-if="msg.needs_clarification && msg.clarification_message && (!msg.matched_metrics || msg.matched_metrics.length === 0) && (!msg.dimension_value_candidates || msg.dimension_value_candidates.length === 0) && msg.clarification_type !== 'category_level' && msg.clarification_type !== 'slot_missing'" class="clarification-message">
            {{ msg.clarification_message }}
          </div>

          <!-- 指标候选选择 -->
          <div v-if="msg.needs_clarification && msg.matched_metrics && msg.matched_metrics.length > 0" class="metric-candidates">
            <div class="candidates-header">请选择要查询的指标：</div>
            <div class="candidates-list">
              <div
                v-for="(metric, idx) in msg.matched_metrics"
                :key="idx"
                class="candidate-item cursor-pointer"
                :class="{ selected: selectedCandidateIdx === idx }"
                @click="$emit('select-metric', idx, metric)"
              >
                <span class="candidate-name">{{ metric.name || metric.metric_name }}</span>
                <span class="candidate-code">{{ metric.metric_code }}</span>
              </div>
            </div>
          </div>

          <!-- 维度值候选选择 -->
          <div v-if="msg.needs_clarification && msg.dimension_value_candidates && msg.dimension_value_candidates.length > 0" class="metric-candidates">
            <div class="candidates-header">请选择维度值：</div>
            <div class="candidates-list">
              <div
                v-for="(dimValue, idx) in msg.dimension_value_candidates"
                :key="idx"
                class="candidate-item cursor-pointer"
                :class="{ selected: selectedDimValueIdx === idx }"
                @click="$emit('select-dim-value', idx, dimValue)"
              >
                <span class="candidate-name">{{ dimValue.dimension_value }}</span>
                <span class="candidate-code">[{{ dimValue.dimension_field }}]</span>
              </div>
            </div>
          </div>

          <!-- 品类级别选择 -->
          <div v-if="msg.needs_clarification && msg.clarification_type === 'category_level'" class="metric-candidates">
            <div class="candidates-list">
              <div
                v-for="(level, idx) in (msg.category_level_options || ['一级品类', '二级品类', '三级品类'])"
                :key="idx"
                class="candidate-item cursor-pointer"
                :class="{ selected: selectedCategoryLevelIdx === idx }"
                @click="$emit('select-category-level', idx, level)"
              >
                <span class="candidate-name">{{ level }}</span>
                <span class="candidate-code">[{{ idx + 1 }}]</span>
              </div>
            </div>
          </div>

          <!-- 槽位选择（slot_missing） -->
          <div v-if="msg.needs_clarification && msg.clarification_type === 'slot_missing'" class="metric-candidates">
            <div class="candidates-list">
              <div
                v-for="(option, idx) in (msg.pending_slot_options || msg._pending_slot_options || [])"
                :key="idx"
                class="candidate-item cursor-pointer"
                :class="{ selected: selectedSlotIdx === idx }"
                @click="$emit('select-slot', idx, option)"
              >
                <span class="candidate-name">{{ option }}</span>
              </div>
            </div>
            <div v-if="msg.pending_slots && msg.pending_slots.length > 1" class="slot-progress">
              还需选择：{{ getPendingSlotsDisplay(msg.pending_slots, msg.pending_slot_name) }}
            </div>
          </div>

          <!-- 查询结果表格 -->
          <div v-if="msg.result_data && (msg.result_data.length > 0 || (msg.result_data.data && msg.result_data.data.length > 0))" class="result-table">
            <div class="result-table-header">
              <span>查询结果</span>
              <span v-if="msg.total" class="result-total">(共 {{ msg.total }} 条)</span>
            </div>
            <div class="result-table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th
                      v-for="(value, key) in (msg.result_data[0] || (msg.result_data.data && msg.result_data.data[0]) || {})"
                      :key="key"
                      class="sortable-th"
                      @click="handleSort(msg, key)"
                    >
                      <span class="th-content">
                        {{ key }}
                        <span class="sort-icon" :class="{ active: getSortIcon(msg, key) !== 'none' }">
                          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                            <path d="M5 2L7.5 5.5H2.5L5 2Z" :fill="getSortIcon(msg, key) === 'asc' ? 'var(--primary-color, #1677ff)' : 'currentColor'" :opacity="getSortIcon(msg, key) === 'asc' ? 1 : 0.5"/>
                            <path d="M5 8L2.5 4.5H7.5L5 8Z" :fill="getSortIcon(msg, key) === 'desc' ? 'var(--primary-color, #1677ff)' : 'currentColor'" :opacity="getSortIcon(msg, key) === 'desc' ? 1 : 0.5"/>
                          </svg>
                        </span>
                      </span>
                    </th>
                    <template v-if="!hasRowComparison(msg) && msg.comparison_results && msg.comparison_results.length > 0">
                      <th v-for="comp in msg.comparison_results" :key="'th-' + comp.comparison_type">
                        {{ comp.comparison_type === '同比' ? '同比变化率' : '环比变化率' }}
                      </th>
                    </template>
                    <th v-else-if="msg.comparison_result && !hasRowComparison(msg)">{{ msg.comparison_result.comparison_type === '同比' ? '同比变化率' : '环比变化率' }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rowIdx) in getSortedData(msg)" :key="rowIdx">
                    <td v-for="(value, key) in row" :key="key" v-html="formatCellValue(value, key, msg)"></td>
                    <template v-if="!hasRowComparison(msg) && msg.comparison_results && msg.comparison_results.length > 0">
                      <td v-for="comp in msg.comparison_results" :key="'td-' + comp.comparison_type">
                        <span :style="{ color: comp.change_rate >= 0 ? '#67c23a' : '#f56c6c', fontWeight: 'bold' }">
                          {{ comp.change_rate >= 0 ? '↑' : '↓' }}
                          {{ Math.abs(comp.change_rate).toFixed(2) }}%
                        </span>
                      </td>
                    </template>
                    <td v-else-if="msg.comparison_result && !hasRowComparison(msg)">
                      <span :style="{ color: msg.comparison_result.change_rate >= 0 ? '#67c23a' : '#f56c6c', fontWeight: 'bold' }">
                        {{ msg.comparison_result.change_rate >= 0 ? '↑' : '↓' }}
                        {{ Math.abs(msg.comparison_result.change_rate).toFixed(2) }}%
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <!-- 分页 -->
            <div v-if="msg.total && msg.total > 10" class="result-pagination">
              <el-pagination
                small
                layout="sizes, prev, pager, next"
                :total="msg.total"
                :page-size="msg.page_size || 10"
                :page-sizes="[10, 50, 100]"
                :current-page="msg.page || 1"
                @current-change="(p) => $emit('page-change', p, msg)"
                @size-change="(s) => $emit('page-size-change', s, msg)"
              />
            </div>
          </div>

          <!-- 猜你想问建议 -->
          <div v-if="msg.suggest && msg.suggest.length > 0" class="suggest-questions">
            <div class="suggest-header">您是否想了解：</div>
            <div class="suggest-list">
              <div
                v-for="(item, idx) in msg.suggest"
                :key="idx"
                class="suggest-item"
                @click="$emit('select-suggestion', item)"
              >
                {{ item }}
              </div>
            </div>
          </div>

          <!-- 下钻维度标签 -->
          <div v-if="msg.result_data && msg.result_data.length > 0 && msg.drill_down_dims && msg.drill_down_dims.length > 0" class="drill-down-section">
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
                class="drill-down-tag cursor-pointer"
                :class="{ 'dim-selected': isDimSelected(dim.dimension_name, msg) }"
                @click="toggleDimSelection(dim.dimension_name, msg)"
              >
                {{ isDimSelected(dim.dimension_name, msg) ? '✓ ' : '' }}{{ dim.dimension_name }}
              </el-tag>
            </div>
            <div v-if="hasSelectedDims(msg)" class="drill-down-actions">
              <el-button type="primary" size="small" class="drill-down-btn cursor-pointer" @click="$emit('drill-down', msg)">
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
                @click="cIdx < msg.breadcrumbs.length - 1 && $emit('breadcrumb-click', crumb, cIdx, msg)"
              >
                {{ crumb.name }}
                <span v-if="cIdx < msg.breadcrumbs.length - 1" class="breadcrumb-sep">›</span>
              </span>
            </div>
            <el-button v-if="msg.breadcrumbs.length > 1" size="small" class="back-btn cursor-pointer" @click="$emit('back', msg)">
              返回
            </el-button>
          </div>

          <div class="message-time">{{ formatMessageTime(msg.created_at) }}</div>

          <!-- 反馈按钮 -->
          <div v-if="msg.role === 'assistant'" class="message-feedback">
            <span class="feedback-label">回答满意吗？</span>
            <button
              class="feedback-btn thumbs-up cursor-pointer"
              :class="{ active: msg.feedback === 1 }"
              @click="$emit('feedback', index, 1)"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 12C7 12 3 9 3 5.5C3 3.6 4.3 2 6 2C6.8 2 7.5 2.5 7 3C6.5 2.5 7.2 2 8 2C9.7 2 11 3.6 11 5.5C11 9 7 12 7 12Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button
              class="feedback-btn thumbs-down cursor-pointer"
              :class="{ active: msg.feedback === -1 }"
              @click="$emit('feedback', index, -1)"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 2C7 2 11 5 11 8.5C11 10.4 9.7 12 8 12C7.2 12 6.5 11.5 7 11C7.5 11.5 6.8 12 6 12C4.3 12 3 10.4 3 8.5C3 5 7 2 7 2Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- 用户消息编辑按钮 -->
        <div v-if="msg.role === 'user'" class="message-edit-area">
          <div v-if="editingMessageIndex === index" class="edit-area">
            <textarea
              v-model="localEditingContent"
              class="edit-textarea"
              rows="3"
              @keydown.enter.ctrl="$emit('resend')"
              @keydown.esc="$emit('cancel-edit')"
              placeholder="输入修改内容..."
            ></textarea>
            <div class="edit-actions">
              <button class="btn-send cursor-pointer" @click="$emit('resend')" :disabled="!localEditingContent.trim()">
                发送
              </button>
              <button class="btn-cancel cursor-pointer" @click="$emit('cancel-edit')">
                取消
              </button>
            </div>
          </div>
          <button
            v-else
            class="edit-btn cursor-pointer"
            @click="$emit('start-edit', index)"
            title="编辑消息"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M10.5 2.5L11.5 3.5L4 11H3V10L10.5 2.5Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>编辑</span>
          </button>
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
</template>

<script setup lang="ts">
import { ref, nextTick, watch, computed } from 'vue'
import { formatSQL } from '@/utils/sqlFormatter'
import DocumentMessage from './DocumentMessage.vue'

const props = defineProps<{
  messages: Array<{
    role: 'user' | 'assistant'
    content: string
    sql?: string
    created_at?: string
    result_data?: any
    comparison_result?: any
    comparison_results?: any[]
    drill_down_dims?: any[]
    breadcrumbs?: any[]
    metric_code?: string
    thinking_expanded?: boolean
    thinking_steps?: Array<{
      step: string
      status: string
      content?: string
    }>
    needs_clarification?: boolean
    matched_metrics?: any[]
    dimension_value_candidates?: any[]
    feedback?: number
    [key: string]: any
  }>
  loading: boolean
  aiAvatarStyle: any
  userAvatarStyle: any
  hasAiAvatar: boolean
  hasUserAvatar: boolean
  editingMessageIndex: number
  editingContent: string
  selectedCandidateIdx: number | null
  selectedDimValueIdx: number | null
  selectedCategoryLevelIdx: number | null
  selectedSlotIdx: number | null
  selectedDims: Record<string, string[]>
  progress?: number
  progressStage?: string
  // 偏好设置 props
  messageStyle?: 'bubbles' | 'cards'
  fontSize?: 'small' | 'medium' | 'large'
  compactMode?: boolean
  showThinking?: boolean
}>()

// 容器类名 - 基于偏好设置
const containerClasses = computed(() => {
  const classes: string[] = []
  if (props.messageStyle) {
    classes.push(`style-${props.messageStyle}`)
  }
  if (props.fontSize) {
    classes.push(`font-${props.fontSize}`)
  }
  if (props.compactMode) {
    classes.push('compact-mode')
  }
  if (props.showThinking === false) {
    classes.push('hide-thinking')
  }
  return classes
})

const emit = defineEmits<{
  'toggle-thinking': [msg: any]
  'select-metric': [idx: number, metric: any]
  'select-dim-value': [idx: number, dimValue: any]
  'select-suggestion': [item: string]
  'page-change': [page: number, msg: any]
  'drill-down': [msg: any]
  'breadcrumb-click': [crumb: any, cIdx: number, msg: any]
  'back': [msg: any]
  'feedback': [index: number, value: number]
  'start-edit': [index: number]
  'resend': []
  'cancel-edit': []
  'toggle-dim': [dimName: string, msg: any]
  'clear-dims': [msg: any]
}>()

const messagesContainer = ref<HTMLElement | null>(null)
const localEditingContent = ref('')

// 文档样式开关（初期 false，之后可改为 true 开启）
const enableDocumentStyle = ref(false)

// 合并视图开关（文档样式启用时生效）
const mergeView = ref(false)

// ========== 表格排序状态 ==========
// 格式: { [messageIndex]: { column: string, order: 'asc' | 'desc' } }
const sortStates = ref<Record<number, { column: string, order: 'asc' | 'desc' }>>({})

function handleSort(msg: any, key: string) {
  const index = props.messages.indexOf(msg)
  const current = sortStates.value[index]
  if (!current || current.column !== key) {
    // 新列，默认降序（大的在前）
    sortStates.value[index] = { column: key, order: 'desc' }
  } else if (current.order === 'desc') {
    // 同一列，切换为升序
    sortStates.value[index] = { column: key, order: 'asc' }
  } else {
    // 再次点击，取消排序
    delete sortStates.value[index]
  }
}

function getSortIcon(msg: any, key: string): 'none' | 'asc' | 'desc' | 'active' {
  const index = props.messages.indexOf(msg)
  const current = sortStates.value[index]
  if (!current || current.column !== key) return 'none'
  return current.order === 'asc' ? 'asc' : 'desc'
}

function getSortedData(msg: any): any[] {
  const data = msg.result_data?.data || msg.result_data || []
  const index = props.messages.indexOf(msg)
  const sortState = sortStates.value[index]
  if (!sortState) return data

  const { column, order } = sortState
  return [...data].sort((a, b) => {
    const valA = a[column]
    const valB = b[column]
    // 数字比较
    const numA = typeof valA === 'number' ? valA : parseFloat(valA)
    const numB = typeof valB === 'number' ? valB : parseFloat(valB)
    if (!isNaN(numA) && !isNaN(numB)) {
      return order === 'asc' ? numA - numB : numB - numA
    }
    // 中文字符串比较
    return order === 'asc'
      ? String(valA).localeCompare(String(valB), 'zh-CN')
      : String(valB).localeCompare(String(valA), 'zh-CN')
  })
}

// Watch editingMessageIndex to initialize localEditingContent when editing starts
watch(() => props.editingMessageIndex, (newIndex) => {
  if (newIndex !== null && newIndex !== undefined && newIndex >= 0) {
    const msg = props.messages[newIndex]
    if (msg) {
      localEditingContent.value = msg.content || ''
    }
  }
})

function toggleThinking(msg) {
  emit('toggle-thinking', msg)
}

function isDimSelected(dimName, msg) {
  const index = props.messages.indexOf(msg)
  return props.selectedDims[index]?.includes(dimName) || false
}

function hasSelectedDims(msg) {
  const index = props.messages.indexOf(msg)
  return props.selectedDims[index]?.length > 0
}

function toggleDimSelection(dimName, msg) {
  emit('toggle-dim', dimName, msg)
}

function clearDimSelection(msg) {
  emit('clear-dims', msg)
}

function formatMessageTime(time) {
  if (!time) return ''
  return new Date(time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatMessage(content) {
  if (!content) return ''
  return content.replace(/\n/g, '<br>')
}

function isWarningContent(content) {
  if (!content) return false
  const warningKeywords = ['未提取', '未匹配', '未识别', '失败', '错误', '无法', '缺失']
  return warningKeywords.some(keyword => content.includes(keyword))
}

function getDimensionColumnNames(drillDownDims) {
  if (!drillDownDims || !Array.isArray(drillDownDims)) return new Set()
  return new Set(drillDownDims.map(d => d.dimension_name).filter(Boolean))
}

function formatCellValue(value, key, msg) {
  if (value === null || value === undefined) return '-'
  const dimensionColNames = getDimensionColumnNames(msg?.drill_down_dims)
  const isDimensionCol = dimensionColNames.has(key)
  const isComparisonCol = key === '同比变化率' || key === '环比变化率'
  // 占比列应该显示为百分比
  const isPercentageCol = key.includes('占比') || key.includes('率') || key.includes('百分比')
  // 时间维度列（日报/月报/年报）不应该被格式化
  const isTimeCol = ['日', '月', '年', '日期', '年份', '月份'].includes(key)
  if (!isComparisonCol) {
    if (typeof value === 'string') {
      if (value.includes(',')) return value
      if (isDimensionCol) return value
      // 如果是时间维度列或看起来像日期的值，不做数字格式化
      if (isTimeCol || /^\d{4}[-\/]\d{2}[-\/]?\d*$/.test(value) || /^\d{4}[-\/]\d{2}$/.test(value)) {
        return value
      }
      // 如果已经是百分比格式（包含%），格式化后保留%
      if (value.includes('%')) {
        const num = parseFloat(value)
        if (!isNaN(num)) {
          return new Intl.NumberFormat('zh-CN', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
          }).format(num) + '%'
        }
        return value
      }
      const num = parseFloat(value)
      if (!isNaN(num)) {
        const formatted = new Intl.NumberFormat('zh-CN', {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2
        }).format(num)
        return isPercentageCol ? formatted + '%' : formatted
      }
    }
    if (typeof value === 'number') {
      if (isDimensionCol || isTimeCol) return value
      const formatted = new Intl.NumberFormat('zh-CN', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
      }).format(value)
      return isPercentageCol ? formatted + '%' : formatted
    }
    return value
  }
  let num = null
  if (typeof value === 'number') {
    num = value
  } else if (typeof value === 'string') {
    num = parseFloat(value)
  }
  if (num === null || isNaN(num)) return value
  const arrow = num >= 0 ? '↑' : '↓'
  const color = num >= 0 ? '#67c23a' : '#f56c6c'
  const formatted = new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1
  }).format(Math.abs(num))
  return `<span style="color:${color};font-weight:bold">${arrow}${formatted}%</span>`
}

function hasRowComparison(msg) {
  const firstRow = msg.result_data?.data?.[0] || msg.result_data?.[0]
  if (!firstRow) return false
  const keys = Object.keys(firstRow)
  return keys.some(k => k === '去年同期' || k === '同比变化率' || k === '上月同期' || k === '环比变化率')
}

function getPendingSlotsDisplay(pendingSlots: string[], currentSlotName: string): string {
  // 过滤掉当前正在选择的槽位，返回剩余槽位的显示名称
  const slotDisplayNames: Record<string, string> = {
    'metric': '指标',
    'time_range': '时间范围',
    'platform': '平台',
    'site': '站点',
    'entity': '主体维度',
    'ad_type': '广告类型',
    'logistics': '物流方式',
    'caliber': '数据口径'
  }
  return pendingSlots
    .filter(slot => slot !== currentSlotName)
    .map(slot => slotDisplayNames[slot] || slot)
    .join('、')
}

// DocumentMessage 事件处理函数
function handleExport() {
  // TODO: 实现导出功能
  console.log('export')
}

function handleShare() {
  // TODO: 实现分享功能
  console.log('share')
}

function handleCopy() {
  // TODO: 实现复制功能
  console.log('copy')
}

function handleRetry() {
  // TODO: 实现重试功能
  console.log('retry')
}

function handleViewAlternative() {
  // TODO: 实现查看替代数据功能
  console.log('view-alternative')
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

defineExpose({ scrollToBottom, getContainer: () => messagesContainer.value })
</script>

<style scoped>
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  position: relative;
}

/* 文档样式切换按钮 */
.document-style-toggle {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  gap: 8px;
  padding: 8px 0;
  margin-bottom: 12px;
  background: linear-gradient(to bottom, var(--bg-primary) 60%, transparent);
}

.toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--border);
  background: var(--bg-white);
  border-radius: 16px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.toggle-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.toggle-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.toggle-btn.secondary {
  background: var(--bg-primary);
}

.toggle-btn.secondary.active {
  background: var(--text-secondary);
  border-color: var(--text-secondary);
  color: #fff;
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

/* 分析进度指示器 */
.progress-indicator {
  padding: 16px 20px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-light);
}

.progress-bar-container {
  height: 4px;
  background: #E2E8F0;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--primary) 0%, var(--primary-light) 100%);
  transition: width 0.3s ease;
}

.progress-stages {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-muted);
}

.progress-stages span.active {
  color: var(--primary);
  font-weight: 500;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.message {
  display: flex;
  gap: 10px;
  width: 100%;
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

.message-avatar.assistant {
  color: #ffffff;
}

.message-bubble {
  max-width: 100%;
  min-width: 60px;
  flex-shrink: 0;
}

.message-content {
  background: var(--bg-card);
  padding: 8px 11px;
  border-radius: 20px;
  border: 1px solid var(--border);
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
}

.message.user .message-content {
  background: var(--primary);
  color: #ffffff;
  border: none;
}

.clarification-message {
  background: var(--bg-card);
  padding: 12px 16px;
  border-radius: 20px;
  border: 1px solid var(--border);
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  margin-top: 8px;
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

.progress-dot.requires_clarification {
  background: #f59e0b;
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

.thinking-step.requires_clarification .step-icon {
  color: #f59e0b;
}

.thinking-step.requires_clarification {
  border-left: 3px solid #f59e0b;
  background: #fffbeb;
}

.step-content.warning {
  color: #d97706;
  font-weight: 500;
  padding: 4px 8px;
  background: #fef3c7;
  border-radius: 4px;
  margin-top: 4px;
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
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-total {
  font-weight: normal;
  color: var(--text-secondary);
  font-size: 12px;
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

/* 可排序列头 */
.sortable-th {
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.sortable-th:hover {
  background: var(--bg-primary);
}
.sortable-th .th-content {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.sort-icon {
  display: inline-flex;
  align-items: center;
  opacity: 0.4;
  transition: opacity 0.15s;
}
.sort-icon.active {
  opacity: 1;
}
.sortable-th:hover .sort-icon {
  opacity: 0.75;
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

/* 猜你想问建议 */
.suggest-questions {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 10px;
  border: 1px solid var(--border);
}

.suggest-header {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.suggest-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggest-item {
  padding: 10px 14px;
  background: var(--bg-white);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  color: var(--text-primary);
}

.suggest-item:hover {
  border-color: var(--color-primary);
  background: var(--bg-primary);
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

/* 用户消息编辑区域 */
.message-edit-area {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  min-height: 28px;
}

.edit-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 12px;
  transition: all 0.15s;
  opacity: 0;
}

.message.user:hover .edit-btn {
  opacity: 1;
}

.edit-btn:hover {
  background: var(--bg-primary);
  color: var(--primary);
}

.edit-area {
  flex: 1;
  margin-top: 8px;
}

.edit-textarea {
  width: 100%;
  min-height: 60px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.edit-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.edit-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  justify-content: flex-end;
}

.btn-send {
  padding: 7px 18px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
}

.btn-send:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.btn-cancel {
  padding: 7px 18px;
  background: var(--bg-primary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-cancel:hover {
  border-color: var(--text-muted);
  color: var(--text-primary);
}

/* ==================== 偏好设置样式 ==================== */

/* 消息样式 - 气泡风格 (类应用在 .chat-messages 上) */
.chat-messages.style-bubbles :deep(.message-content) {
  background: var(--bg-card) !important;
  padding: 8px 11px;
  border-radius: 20px;
  border: 1px solid var(--border);
}

.chat-messages.style-bubbles :deep(.message.user .message-content) {
  background: var(--primary) !important;
  color: #ffffff;
  border: none;
  border-radius: 20px;
}

/* 消息样式 - 卡片风格 */
.chat-messages.style-cards :deep(.message-content) {
  background: var(--bg-card) !important;
  padding: 10px 13px;
  border-radius: 12px;
  border: 1px solid var(--border);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.chat-messages.style-cards :deep(.message.user .message-content) {
  background: var(--primary) !important;
  color: #ffffff;
  border: none;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
}

/* 字体大小 */
.chat-messages.font-small :deep(.message-content) {
  font-size: 12px !important;
  line-height: 1.5;
  padding: 7px 10px;
}

.chat-messages.font-medium :deep(.message-content) {
  font-size: 14px !important;
  line-height: 1.5;
  padding: 8px 11px;
}

.chat-messages.font-large :deep(.message-content) {
  font-size: 16px !important;
  line-height: 1.5;
  padding: 10px 13px;
}

/* 紧凑模式 */
.chat-messages.compact-mode :deep(.message-content) {
  padding: 6px 8px !important;
}

.chat-messages.compact-mode :deep(.thinking-process) {
  margin-bottom: 8px;
}

.chat-messages.compact-mode :deep(.thinking-header) {
  padding: 8px 10px;
}

.chat-messages.compact-mode :deep(.thinking-details) {
  padding: 0 10px 8px;
}

.chat-messages.compact-mode :deep(.result-table) {
  margin-top: 8px;
}

.chat-messages.compact-mode :deep(.result-table-header) {
  padding: 6px 10px;
}

.chat-messages.compact-mode :deep(.metric-candidates) {
  margin-top: 8px;
  padding: 10px;
}

.chat-messages.compact-mode :deep(.drill-down-section) {
  margin-top: 8px;
  padding: 10px;
}

.chat-messages.compact-mode :deep(.breadcrumb-section) {
  margin-top: 8px;
  padding: 6px 10px;
}

/* 紧凑模式头像缩小 */
.chat-messages.compact-mode :deep(.message-avatar) {
  width: 28px;
  height: 28px;
}

/* 隐藏思考过程 */
.chat-messages.hide-thinking :deep(.thinking-process) {
  display: none !important;
}

/* Markdown 内容样式 */
.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3),
.message-content :deep(h4),
.message-content :deep(h5),
.message-content :deep(h6) {
  margin: 0.5em 0;
  font-weight: 600;
  line-height: 1.3;
}

.message-content :deep(h1) { font-size: 1.4em; }
.message-content :deep(h2) { font-size: 1.25em; }
.message-content :deep(h3) { font-size: 1.1em; }

.message-content :deep(p) {
  margin: 0.5em 0;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.message-content :deep(li) {
  margin: 0.25em 0;
}

.message-content :deep(code) {
  background: var(--bg-primary);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: 'JetBrains Mono', 'SF Mono', Monaco, monospace;
}

.message-content :deep(pre) {
  background: #1E1E2E;
  border-radius: 8px;
  padding: 12px;
  margin: 0.5em 0;
  overflow-x: auto;
}

.message-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: #CDD6F4;
}

.message-content :deep(strong) {
  font-weight: 600;
}

.message-content :deep(table) {
  border-collapse: collapse;
  margin: 0.5em 0;
  width: 100%;
}

.message-content :deep(th),
.message-content :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}

.message-content :deep(th) {
  background: var(--bg-primary);
  font-weight: 600;
}

.message-content :deep(blockquote) {
  margin: 0.5em 0;
  padding: 0.5em 1em;
  border-left: 3px solid var(--primary);
  background: var(--bg-primary);
  color: var(--text-secondary);
}
</style>
