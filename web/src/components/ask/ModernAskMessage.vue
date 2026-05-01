<template>
  <article class="modern-message" :class="`is-${msg.role}`">
    <div class="avatar-shell" :class="`avatar-${msg.role}`">
      <span v-if="msg.role === 'user'">你</span>
      <span v-else>AI</span>
    </div>

    <div class="message-body">
      <div class="message-meta">
        <span class="speaker">{{ msg.role === 'user' ? '你' : '数据助手' }}</span>
        <span v-if="dateRange" class="date-range">{{ dateRange }}</span>
        <span class="timestamp">{{ timeLabel }}</span>
      </div>

      <div v-if="msg.role === 'user'" class="user-bubble">
        <div class="user-text">{{ msg.content }}</div>
      </div>

      <div v-else class="assistant-surface" :class="{ pending: msg.loading }">
        <template v-if="msg.loading">
          <div class="pending-lead">{{ msg.processingLabel || '正在分析你的问题…' }}</div>
          <div class="pending-sub">先整理结论，再补充证据和过程。</div>
          <div class="pending-dots">
            <span></span><span></span><span></span>
          </div>
        </template>

        <template v-else>
          <div class="assistant-main">
            <div class="assistant-lead" v-html="renderHtml(presentation.lead)"></div>
            <div v-if="presentation.paragraphs.length" class="assistant-details">
              <p
                v-for="(paragraph, paragraphIdx) in presentation.paragraphs"
                :key="`${idx}-paragraph-${paragraphIdx}`"
                class="detail-paragraph"
                v-html="renderHtml(paragraph)"
              ></p>
            </div>
          </div>

          <div v-if="metaChips.length" class="meta-chips">
            <span
              v-for="chip in metaChips"
              :key="chip"
              class="meta-chip"
            >
              {{ chip }}
            </span>
          </div>

          <ClarificationCard
            v-if="msg.action_type === 'clarify' && msg.clarify_options"
            :options="msg.clarify_options"
            @select="$emit('clarification-select', $event)"
            @confirm="$emit('clarification-confirm', $event)"
          />

          <PlanConfirmCard
            v-if="msg.action_type === 'confirm' && msg.confirm_plan"
            :plan="msg.confirm_plan"
            @confirm="$emit('plan-confirm', $event)"
            @modify="$emit('plan-modify', $event)"
          />

          <div
            v-if="msg.needsClarification && msg.clarificationOptions && msg.clarificationOptions.length"
            class="clarification-strip"
          >
            <div class="clarification-title">{{ msg.clarificationMessage || '请先确认你的意思' }}</div>
            <div class="clarification-options">
              <button
                v-for="option in msg.clarificationOptions"
                :key="option.value || option.label"
                class="clarification-option"
                @click="$emit('legacy-clarification', option, msg.originalQuestion)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <div v-if="msg.analysis" class="analysis-summary-card">
            <div class="analysis-summary-head">
              <span class="analysis-title">分析摘要</span>
              <span
                v-if="msg.analysis.health_score != null"
                class="health-pill"
                :class="healthClass"
              >
                {{ msg.analysis.health_score }}分
              </span>
            </div>
            <div v-if="msg.analysis.top_urgent_action" class="analysis-alert">
              {{ msg.analysis.top_urgent_action }}
            </div>
            <div v-if="highlightItems.length" class="analysis-list">
              <div
                v-for="(item, itemIdx) in highlightItems"
                :key="`${idx}-highlight-${itemIdx}`"
                class="analysis-item"
              >
                <div class="analysis-item-title">
                  <span class="analysis-item-metric">{{ item.metric || item.title || '重点' }}</span>
                  <span v-if="item.conclusion" class="analysis-item-conclusion">{{ item.conclusion }}</span>
                </div>
                <div v-if="item.reason" class="analysis-item-reason">{{ item.reason }}</div>
              </div>
            </div>
          </div>

          <ChartCard
            v-if="msg.resultData && msg.resultData.length > 0"
            :data="msg.resultData"
            :columns="msg.columns || []"
            :height="280"
            :interpretation="msg.interpretation"
            :metric-name="msg.metricName || ''"
            :metric-names="msg.metricNames || []"
            :time-start="msg.mql?.time?.start"
            :time-end="msg.mql?.time?.end"
            class="evidence-card"
          />

          <div
            v-if="msg.category"
            class="drilldown-strip"
          >
            <button class="drilldown-btn" @click="$emit('drilldown', { check: 'sales' })">看销售</button>
            <button class="drilldown-btn" @click="$emit('drilldown', { check: 'ad' })">看广告</button>
            <button class="drilldown-btn" @click="$emit('drilldown', { check: 'inventory' })">看库存</button>
            <button class="drilldown-btn" @click="$emit('drilldown', { check: 'profit' })">看利润</button>
          </div>

          <div v-if="msg.suggest && msg.suggest.length" class="followups">
            <div class="followup-label">你可能还会问</div>
            <div class="followup-list">
              <button
                v-for="suggestion in msg.suggest"
                :key="suggestion"
                class="followup-btn"
                @click="$emit('select-suggestion', suggestion)"
              >
                {{ suggestion }}
              </button>
            </div>
          </div>

          <div class="assistant-actions">
            <button
              v-if="hasThinking"
              class="assistant-action"
              @click="$emit('open-process', msg)"
            >
              分析过程
            </button>
            <button
              v-if="msg.interpretation"
              class="assistant-action"
              :class="{ active: expandedInterpretation }"
              @click="$emit('toggle-interpretation', idx)"
            >
              数据解读
            </button>
            <button class="assistant-action" @click="$emit('copy', msg)">复制</button>
            <button
              class="assistant-action icon"
              :class="{ active: msg.rating === 'up' }"
              @click="$emit('rate', msg, 'up')"
            >
              赞
            </button>
            <button
              class="assistant-action icon"
              :class="{ active: msg.rating === 'down' }"
              @click="$emit('rate', msg, 'down')"
            >
              踩
            </button>
          </div>

          <div v-if="msg.interpretation && expandedInterpretation" class="interpretation-panel">
            {{ msg.interpretation }}
          </div>
        </template>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

import ChartCard from './ChartCard.vue'
import ClarificationCard from './ClarificationCard.vue'
import PlanConfirmCard from './PlanConfirmCard.vue'
import { buildAssistantPresentation } from '../../utils/assistantResponsePresentation'

const props = defineProps({
  msg: {
    type: Object,
    required: true,
  },
  idx: {
    type: Number,
    required: true,
  },
  expandedInterpretation: {
    type: Boolean,
    default: false,
  },
})

defineEmits([
  'copy',
  'toggle-interpretation',
  'rate',
  'open-process',
  'select-suggestion',
  'clarification-select',
  'clarification-confirm',
  'plan-confirm',
  'plan-modify',
  'legacy-clarification',
  'drilldown',
])

marked.setOptions({
  breaks: true,
  gfm: true,
})

const presentation = computed(() => buildAssistantPresentation(props.msg))

const metaChips = computed(() => {
  if (props.msg.role !== 'assistant') return []
  const chips = []
  if (props.msg.analysis) chips.push('已生成分析摘要')
  if (Array.isArray(props.msg.resultData) && props.msg.resultData.length > 0) {
    chips.push(`包含 ${props.msg.resultData.length} 条证据`)
  }
  if (props.msg.needsClarification) chips.push('等待确认')
  return chips
})

const timeLabel = computed(() => {
  const value = props.msg.time || props.msg.created_at
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
})

const dateRange = computed(() => {
  const start = props.msg?.mql?.time?.start
  const end = props.msg?.mql?.time?.end
  if (!start) return ''
  const startDate = String(start).slice(0, 10)
  const endDate = String(end || start).slice(0, 10)
  return startDate === endDate ? startDate : `${startDate} ~ ${endDate}`
})

const highlightItems = computed(() => {
  const analysis = props.msg.analysis
  if (!analysis) return []
  if (Array.isArray(analysis.highlights) && analysis.highlights.length) return analysis.highlights.slice(0, 2)
  if (Array.isArray(analysis.issues) && analysis.issues.length) return analysis.issues.slice(0, 2)
  return []
})

const hasThinking = computed(() => {
  return Array.isArray(props.msg.thinkingSteps) && props.msg.thinkingSteps.length > 0
})

const healthClass = computed(() => {
  const score = props.msg?.analysis?.health_score
  if (score >= 90) return 'excellent'
  if (score >= 70) return 'good'
  return 'warning'
})

function renderHtml(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(String(text)))
}
</script>

<style scoped>
.modern-message {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.avatar-shell {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  position: sticky;
  top: 8px;
}

.avatar-assistant {
  background: linear-gradient(180deg, #111827 0%, #1f2937 100%);
  color: #f9fafb;
}

.avatar-user {
  background: linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%);
  color: #eff6ff;
}

.message-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  color: #94a3b8;
}

.speaker {
  color: #0f172a;
  font-weight: 600;
}

.assistant-surface,
.user-bubble {
  border-radius: 24px;
  overflow: hidden;
}

.assistant-surface {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.06);
  padding: 22px 22px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.assistant-surface.pending {
  background: rgba(255, 255, 255, 0.82);
}

.user-bubble {
  align-self: flex-end;
  max-width: min(720px, 100%);
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
  color: #eff6ff;
  padding: 16px 18px;
  box-shadow: 0 18px 40px rgba(37, 99, 235, 0.22);
}

.user-text {
  font-size: 15px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.assistant-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.assistant-lead :deep(p),
.detail-paragraph :deep(p) {
  margin: 0;
}

.assistant-lead {
  font-size: 18px;
  line-height: 1.7;
  color: #0f172a;
  font-weight: 600;
}

.assistant-details {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-paragraph {
  margin: 0;
  font-size: 15px;
  line-height: 1.8;
  color: #334155;
}

.meta-chips,
.followup-list,
.clarification-options,
.drilldown-strip {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-chip {
  padding: 4px 9px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-size: 11px;
  color: #64748b;
}

.analysis-summary-card,
.interpretation-panel,
.clarification-strip {
  border-radius: 18px;
  padding: 16px 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.analysis-summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.analysis-title {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.health-pill {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.health-pill.excellent {
  background: #dcfce7;
  color: #166534;
}

.health-pill.good {
  background: #fef3c7;
  color: #92400e;
}

.health-pill.warning {
  background: #fee2e2;
  color: #b91c1c;
}

.analysis-alert {
  margin-bottom: 12px;
  font-size: 13px;
  line-height: 1.7;
  color: #b45309;
}

.analysis-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.analysis-item {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid #e2e8f0;
}

.analysis-item-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
}

.analysis-item-reason {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.65;
  color: #475569;
}

.clarification-title,
.followup-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 10px;
}

.clarification-option,
.followup-btn,
.drilldown-btn,
.assistant-action {
  border: 1px solid #dbe4f0;
  background: #ffffff;
  color: #334155;
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.3;
  cursor: pointer;
  transition: all 0.18s ease;
}

.clarification-option:hover,
.followup-btn:hover,
.drilldown-btn:hover,
.assistant-action:hover,
.assistant-action.active {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}

.assistant-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  opacity: 0.92;
}

.assistant-action.icon {
  min-width: 38px;
  text-align: center;
}

.assistant-action {
  padding: 7px 11px;
  font-size: 12px;
}

.followup-btn,
.clarification-option,
.drilldown-btn {
  font-size: 12px;
  padding: 8px 11px;
}

.interpretation-panel {
  font-size: 14px;
  line-height: 1.8;
  color: #334155;
}

.pending-lead {
  font-size: 16px;
  line-height: 1.7;
  color: #0f172a;
  font-weight: 600;
}

.pending-sub {
  font-size: 14px;
  color: #64748b;
}

.pending-dots {
  display: flex;
  gap: 6px;
}

.pending-dots span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #94a3b8;
  animation: pulse 1.2s infinite ease-in-out;
}

.pending-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.pending-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes pulse {
  0%, 80%, 100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@media (max-width: 768px) {
  .modern-message {
    grid-template-columns: 32px minmax(0, 1fr);
    gap: 10px;
  }

  .avatar-shell {
    width: 32px;
    height: 32px;
    border-radius: 12px;
    font-size: 10px;
  }

  .assistant-surface {
    padding: 16px 16px 14px;
    border-radius: 20px;
    gap: 14px;
  }

  .user-bubble {
    padding: 13px 14px;
    border-radius: 20px;
  }

  .assistant-lead {
    font-size: 16px;
  }

  .detail-paragraph,
  .interpretation-panel {
    font-size: 14px;
  }
}
</style>
