<template>
  <article class="lvdou-message" :class="`is-${msg.role}`">
    <!-- 用户消息 -->
    <template v-if="msg.role === 'user'">
      <div class="user-bubble">{{ msg.content }}</div>
    </template>

    <!-- 助手消息 -->
    <template v-else>
      <!-- 加载中 -->
      <div v-if="msg.loading" class="loading-state">
        <div class="loading-text">{{ msg.processingLabel || '正在分析你的问题…' }}</div>
        <div class="loading-dots"><span></span><span></span><span></span></div>
      </div>

      <!-- 正常回答 -->
      <template v-else>
        <!-- 主回答 -->
        <div class="answer-text" v-html="renderHtml(presentation.lead)"></div>

        <!-- 补充段落（识别模板占位符，插入对应组件） -->
        <template v-if="presentation.paragraphs.length">
          <template v-for="(p, i) in presentation.paragraphs" :key="i">
            <!-- 第三段：数据图表占位 → 插入 ChartCard -->
            <ChartCard
              v-if="isChartPlaceholder(p) && msg.resultData && msg.resultData.length > 0"
              :data="msg.resultData"
              :columns="msg.columns || []"
              :height="280"
              :interpretation="msg.interpretation"
              :metric-name="msg.metricName || ''"
              :metric-names="msg.metricNames || []"
              :time-start="msg.mql?.time?.start"
              :time-end="msg.mql?.time?.end"
              class="data-section"
            />
            <!-- 核心指标段落：加 tooltip -->
            <div v-else-if="isKpiSection(p)" class="kpi-section">
              <div class="kpi-header">
                <strong>{{ kpiSectionTitle(p) }}</strong>
                <span v-if="kpiTooltipText" class="kpi-tip-icon" @mouseenter="showKpiTip = true" @mouseleave="showKpiTip = false">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                </span>
                <div v-if="showKpiTip && kpiTooltipText" class="kpi-popover">
                  <div v-for="line in kpiTooltipLines" :key="line.label" class="kpi-popover-row">
                    <span class="kpi-popover-label">{{ line.label }}</span>
                    <span class="kpi-popover-value">{{ line.value }}</span>
                  </div>
                </div>
              </div>
              <div class="kpi-values" v-html="renderHtml(stripKpiTitle(p))"></div>
            </div>
            <!-- 其他段落正常渲染 -->
            <p v-else-if="!isChartPlaceholder(p)" class="detail-line" v-html="renderHtml(p)"></p>
          </template>
        </template>

        <!-- 补充信息标签 -->
        <div v-if="supplementTags.length" class="tag-strip">
          <span v-for="tag in supplementTags" :key="tag" class="info-tag">{{ tag }}</span>
        </div>

        <!-- 澄清选项 -->
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
        <div v-if="msg.needsClarification && msg.clarificationOptions?.length" class="clarify-section">
          <div class="clarify-msg">{{ msg.clarificationMessage || '请先确认你的意思' }}</div>
          <div class="clarify-options">
            <button v-for="opt in msg.clarificationOptions" :key="opt.value || opt.label" class="clarify-btn"
              @click="$emit('legacy-clarification', opt, msg.originalQuestion)">
              {{ opt.label }}
            </button>
          </div>
        </div>

        <!-- 非模板模式下独立渲染图表（无触发分析时） -->
        <ChartCard
          v-if="!isTemplateMode && msg.resultData && msg.resultData.length > 0"
          :data="msg.resultData"
          :columns="msg.columns || []"
          :height="280"
          :interpretation="msg.interpretation"
          :metric-name="msg.metricName || ''"
          :metric-names="msg.metricNames || []"
          :time-start="msg.mql?.time?.start"
          :time-end="msg.mql?.time?.end"
          class="data-section"
        />

        <!-- 下钻选项（暂隐藏） -->
        <!-- <div v-if="drilldownOptions.length" class="drilldown-section">
          <div class="drilldown-label">深入分析</div>
          <div class="drilldown-list">
            <button v-for="opt in drilldownOptions" :key="opt.label" class="drilldown-btn" @click="$emit('drilldown', opt)">
              {{ opt.label }}
            </button>
          </div>
        </div> -->

        <!-- 建议问题 -->
        <div v-if="msg.suggest && msg.suggest.length" class="suggest-section">
          <div class="suggest-label">你可能还会问</div>
          <div class="suggest-list">
            <button v-for="s in msg.suggest" :key="s" class="suggest-btn" @click="$emit('select-suggestion', s, msg)">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v10M1 6h10" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
              {{ s }}
            </button>
          </div>
        </div>

        <!-- 底部操作栏 -->
        <div class="action-bar">
          <span class="action-time">{{ timeLabel }}</span>
          <div class="action-btns">
            <button class="act-btn" @click="$emit('copy', msg)" title="复制">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <button v-if="reasoningSteps.length || hasThinking" class="act-btn"
              :class="{ active: showReasoning }" @click="showReasoning = !showReasoning" title="分析过程">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
            </button>
            <button class="act-btn" :class="{ active: msg.rating === 'up' }"
              @click="$emit('rate', msg, 'up')" title="有帮助">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
            </button>
            <button class="act-btn" :class="{ active: msg.rating === 'down' }"
              @click="$emit('rate', msg, 'down')" title="没帮助">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
            </button>
          </div>
        </div>

        <!-- 推理链（展开后） -->
        <div v-if="showReasoning && reasoningSteps.length" class="reasoning-section">
          <div v-for="rs in reasoningSteps" :key="rs.label" class="reasoning-row">
            <span class="rs-icon">{{ rs.icon }}</span>
            <span class="rs-label">{{ rs.label }}</span>
            <span class="rs-value">{{ rs.value }}</span>
          </div>
          <button v-if="hasThinking" class="reasoning-expand" @click="$emit('open-process', msg)">
            查看完整过程
          </button>
        </div>
      </template>
    </template>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import ChartCard from './ChartCard.vue'
import ClarificationCard from './ClarificationCard.vue'
import PlanConfirmCard from './PlanConfirmCard.vue'
import { buildAssistantPresentation } from '../../utils/assistantResponsePresentation'

const props = defineProps({
  msg: { type: Object, required: true },
  idx: { type: Number, required: true },
  expandedInterpretation: { type: Boolean, default: false },
})

defineEmits([
  'copy', 'toggle-interpretation', 'rate', 'open-process',
  'select-suggestion', 'clarification-select', 'clarification-confirm',
  'plan-confirm', 'plan-modify', 'legacy-clarification', 'drilldown',
])

marked.setOptions({ breaks: true, gfm: true })

const showReasoning = ref(false)
const presentation = computed(() => buildAssistantPresentation(props.msg))

const CHART_PLACEHOLDER_RE = /数据图表|前端展示|维度对比图|贡献占比图/

const isTemplateMode = computed(() => {
  return presentation.value.paragraphs.some(p => CHART_PLACEHOLDER_RE.test(p))
})

function isChartPlaceholder(text) {
  return CHART_PLACEHOLDER_RE.test(text)
}

function isKpiSection(text) {
  return /^\*\*[一二三四五六]、核心指标\*\*/.test(text)
}

function stripKpiTitle(text) {
  return text.replace(/^\*\*[一二三四五六]、核心指标\*\*\n?/, '')
}

function kpiSectionTitle(text) {
  const m = text.match(/^\*\*([一二三四五六]、核心指标)\*\*/)
  return m ? m[1] : '核心指标'
}

const showKpiTip = ref(false)

const kpiTooltipText = computed(() => {
  const tip = props.msg.kpiTooltip
  if (!tip) return ''
  const lines = []
  if (tip.metric_definition) lines.push(tip.metric_definition)
  if (tip.current_period) lines.push(`查询期间：${tip.current_period}`)
  if (tip.compare_period) lines.push(`对比期间：${tip.compare_period}`)
  if (tip.mom_period) lines.push(tip.mom_period)
  if (tip.yoy_period) lines.push(tip.yoy_period)
  return lines.join('\n')
})

const kpiTooltipLines = computed(() => {
  const tip = props.msg.kpiTooltip
  if (!tip) return []
  const lines = []
  if (tip.metric_definition) lines.push({ label: '指标定义', value: tip.metric_definition })
  if (tip.current_period) lines.push({ label: '查询期间', value: tip.current_period })
  if (tip.compare_period) lines.push({ label: '对比期间', value: tip.compare_period })
  if (tip.mom_period) lines.push({ label: '环比期间', value: tip.mom_period })
  if (tip.yoy_period) lines.push({ label: '同比期间', value: tip.yoy_period })
  return lines
})

const timeLabel = computed(() => {
  const v = props.msg.time || props.msg.created_at
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return ''
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

const supplementTags = computed(() => {
  const tags = []
  if (Array.isArray(props.msg.supplementary_info)) {
    props.msg.supplementary_info.forEach(info => {
      if (info.label && info.value) tags.push(`${info.label} ${info.value}`)
    })
  }
  return tags
})

const hasThinking = computed(() => Array.isArray(props.msg.thinkingSteps) && props.msg.thinkingSteps.length > 0)

const drilldownOptions = computed(() => {
  const opts = props.msg.analysis?.drilldown_options
  if (!Array.isArray(opts) || opts.length === 0) return []
  return opts.filter(o => o.label && o.action === 'drilldown')
})

function isNegative(val) {
  return typeof val === 'string' && val.startsWith('-')
}

const reasoningSteps = computed(() => {
  if (props.msg.role !== 'assistant' || props.msg.loading) return []
  const steps = []
  const explanation = props.msg.explanation
  if (explanation?.metric_meaning) {
    steps.push({ icon: '\u{1F4A1}', label: '理解问题', value: explanation.metric_meaning })
  } else if (props.msg.metricName) {
    steps.push({ icon: '\u{1F4A1}', label: '理解问题', value: `查询${props.msg.metricName}` })
  }
  const entityParts = []
  if (props.msg.metricName) entityParts.push(`指标：${props.msg.metricName}`)
  const timeRange = props.msg.timeRange || props.msg.mql?.time
  if (timeRange?.original) entityParts.push(`时间：${timeRange.original}`)
  else if (timeRange?.start) {
    const s = String(timeRange.start).slice(0, 10)
    const e = timeRange.end ? String(timeRange.end).slice(0, 10) : ''
    entityParts.push(`时间：${s === e ? s : s + ' ~ ' + e}`)
  }
  if (props.msg.dimensionFilters?.length) {
    const dims = props.msg.dimensionFilters.map(d => d.value || d.type || '').filter(Boolean).join('、')
    if (dims) entityParts.push(`维度：${dims}`)
  }
  if (entityParts.length) steps.push({ icon: '\u{1F50D}', label: '识别要素', value: entityParts.join('，') })
  if (explanation?.data_source) steps.push({ icon: '\u{1F4CA}', label: '查询数据', value: `来源：${explanation.data_source}` })
  const resultParts = []
  if (Array.isArray(props.msg.supplementary_info)) {
    props.msg.supplementary_info.forEach(info => { if (info.label && info.value) resultParts.push(`${info.label}${info.value}`) })
  }
  if (props.msg.momChange != null) resultParts.push(`环比${props.msg.momChange >= 0 ? '+' : ''}${(props.msg.momChange * 100).toFixed(1)}%`)
  if (props.msg.yoyChange != null) resultParts.push(`同比${props.msg.yoyChange >= 0 ? '+' : ''}${(props.msg.yoyChange * 100).toFixed(1)}%`)
  if (resultParts.length) steps.push({ icon: '✅', label: '得出结论', value: resultParts.join('，') })
  return steps
})

function renderHtml(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(String(text)))
}
</script>

<style scoped>
.lvdou-message { width: 100%; }

/* 用户气泡 */
.user-bubble {
  display: inline-block;
  max-width: min(600px, 85%);
  padding: 10px 16px;
  background: #3370ff;
  color: #fff;
  border-radius: 16px 16px 4px 16px;
  font-size: 14px;
  line-height: 1.6;
  float: right;
  word-break: break-word;
}
.doubao-message.is-user::after { content: ''; display: table; clear: both; }

/* 加载 */
.loading-state { display: flex; align-items: center; gap: 12px; }
.loading-text { font-size: 14px; color: #86909c; }
.loading-dots { display: flex; gap: 4px; }
.loading-dots span {
  width: 6px; height: 6px; border-radius: 50%; background: #c9cdd4;
  animation: dotPulse 1.2s ease-in-out infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.15s; }
.loading-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

/* 主回答 */
.answer-text {
  font-size: 15px;
  line-height: 1.8;
  color: #1f2329;
  font-weight: 400;
}
.answer-text :deep(p) { margin: 0; }
.answer-text :deep(strong) { font-weight: 600; }

.answer-details { margin-top: 8px; }
.detail-line {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #4e5969;
}
.detail-line :deep(p) { margin: 0; }

/* 核心指标 tooltip */
.kpi-section {
  margin-top: 4px;
}
.kpi-header {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  position: relative;
}
.kpi-header strong {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
.kpi-tip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: #a0a4b0;
  cursor: help;
  transition: color 0.2s;
  flex-shrink: 0;
}
.kpi-tip-icon:hover {
  color: #3370ff;
}
.kpi-popover {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 315px;
  max-width: 515px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08), 0 2px 6px rgba(0, 0, 0, 0.04);
  padding: 12px 14px;
  z-index: 100;
  animation: kpi-popover-in 0.15s ease;
}
@keyframes kpi-popover-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.kpi-popover-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 0;
  font-size: 13px;
  line-height: 1.5;
}
.kpi-popover-row + .kpi-popover-row {
  border-top: 1px solid #f2f3f5;
}
.kpi-popover-label {
  color: #86909c;
  white-space: nowrap;
  flex-shrink: 0;
  font-weight: 500;
}
.kpi-popover-value {
  color: #1f2329;
  word-break: break-all;
}
.kpi-values {
  font-size: 14px;
  line-height: 1.8;
  color: #4e5969;
  margin-top: 4px;
}
.kpi-values :deep(p) { margin: 0; }

/* 数据标签 */
.tag-strip { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.info-tag {
  padding: 3px 8px;
  background: #f2f3f5;
  border-radius: 4px;
  font-size: 12px;
  color: #4e5969;
}

/* 澄清 */
.clarify-section { margin-top: 12px; }
.clarify-msg { font-size: 14px; color: #4e5969; margin-bottom: 8px; }
.clarify-options { display: flex; flex-wrap: wrap; gap: 8px; }
.clarify-btn {
  padding: 6px 14px; background: #fff; border: 1px solid #e5e6eb; border-radius: 6px;
  font-size: 13px; color: #4e5969; cursor: pointer; transition: all 0.15s;
}
.clarify-btn:hover { border-color: #3370ff; color: #3370ff; }

/* 数据区 */
.data-section { margin-top: 16px; }

/* 归因分析 */
.breakdown-section { margin-top: 16px; }
.breakdown-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: #1f2329; margin-bottom: 10px;
}
.breakdown-list { display: flex; flex-direction: column; gap: 6px; }
.breakdown-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; background: #f7f8fa; border-radius: 8px;
  font-size: 13px; border-left: 3px solid transparent;
}
.breakdown-row.main_drag { border-left-color: #ef4444; }
.breakdown-row.main_boost { border-left-color: #22c55e; }
.breakdown-row.positive_contributor { border-left-color: #22c55e; }
.breakdown-row.negative_contributor { border-left-color: #ef4444; }
.bd-dim { flex: 1; min-width: 0; color: #1f2329; font-weight: 500; }
.bd-change { font-weight: 600; font-size: 13px; min-width: 56px; text-align: right; }
.bd-change.neg { color: #ef4444; }
.bd-change.pos { color: #22c55e; }
.bd-impact { color: #86909c; font-size: 12px; min-width: 80px; text-align: right; }
.bd-priority {
  padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 600;
}
.bd-priority.p-p0 { background: #fef2f2; color: #ef4444; }
.bd-priority.p-p1 { background: #fffbeb; color: #f59e0b; }
.bd-priority.p-p2 { background: #f0f9ff; color: #3b82f6; }

/* 行动建议 */
.action-items-section { margin-top: 16px; }
.action-items-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: #1f2329; margin-bottom: 10px;
}
.action-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 6px 0; font-size: 13px; line-height: 1.6;
}
.ai-dot {
  width: 6px; height: 6px; border-radius: 50%; margin-top: 7px; flex-shrink: 0;
}
.action-item.urgent .ai-dot { background: #ef4444; }
.action-item.urgent .ai-text { color: #ef4444; }
.action-item.warning .ai-dot { background: #f59e0b; }
.action-item.warning .ai-text { color: #92400e; }
.action-item.normal .ai-dot { background: #3b82f6; }
.action-item.normal .ai-text { color: #4e5969; }

/* 下钻选项 */
.drilldown-section { margin-top: 16px; }
.drilldown-label { font-size: 13px; font-weight: 500; color: #86909c; margin-bottom: 8px; }
.drilldown-list { display: flex; flex-wrap: wrap; gap: 8px; }
.drilldown-btn {
  display: inline-flex; align-items: center;
  padding: 7px 14px; background: #fff; border: 1px solid #e5e6eb; border-radius: 8px;
  font-size: 13px; color: #2468f2; cursor: pointer; transition: all 0.15s;
}
.drilldown-btn:hover { border-color: #2468f2; background: #e8f0fe; }

/* 建议问题 */
.suggest-section { margin-top: 16px; }
.suggest-label { font-size: 13px; font-weight: 500; color: #86909c; margin-bottom: 8px; }
.suggest-list { display: flex; flex-wrap: wrap; gap: 8px; }
.suggest-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px; background: #fff; border: 1px solid #e5e6eb; border-radius: 8px;
  font-size: 13px; color: #4e5969; cursor: pointer; transition: all 0.15s;
}
.suggest-btn svg { color: #c9cdd4; flex-shrink: 0; }
.suggest-btn:hover { border-color: #3370ff; color: #3370ff; background: #eff4ff; }
.suggest-btn:hover svg { color: #3370ff; }

/* 底部操作栏 */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid #f2f3f5;
}
.action-time { font-size: 12px; color: #c9cdd4; }
.action-btns { display: flex; gap: 4px; }
.act-btn {
  width: 28px; height: 28px; display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%; border: none; background: transparent; color: #c9cdd4; cursor: pointer;
  transition: all 0.15s;
}
.act-btn:hover { background: #f2f3f5; color: #4e5969; }
.act-btn.active { color: #3370ff; background: #eff4ff; }

/* 推理链 */
.reasoning-section {
  margin-top: 12px;
  padding: 10px 14px;
  background: #f7f8fa;
  border-radius: 8px;
}
.reasoning-row {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size: 13px;
}
.rs-icon { font-size: 14px; flex-shrink: 0; }
.rs-label { color: #86909c; font-weight: 500; white-space: nowrap; }
.rs-value { color: #1f2329; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.reasoning-expand {
  margin-top: 6px; padding: 4px 10px; background: transparent;
  border: 1px solid #e5e6eb; border-radius: 6px;
  font-size: 12px; color: #3370ff; cursor: pointer; transition: all 0.15s;
}
.reasoning-expand:hover { background: #eff4ff; border-color: #3370ff; }

/* ChartCard 表格覆盖 */
.data-section :deep(.chart-card) {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: none;
}
.data-section :deep(.chart-card .chart-header) {
  display: none;
}
.data-section :deep(.metric-table) {
  background: #fff;
}
.data-section :deep(.metric-table .data-table th) {
  background: #f7f8fa;
  font-size: 12px;
  font-weight: 600;
  color: #86909c;
  padding: 8px 12px;
  border-bottom: 1px solid #e5e6eb;
}
.data-section :deep(.metric-table .data-table td) {
  padding: 10px 12px;
  font-size: 13px;
  color: #1f2329;
  border-bottom: 1px solid #f2f3f5;
}
.data-section :deep(.metric-table .data-table tbody tr:last-child td) {
  border-bottom: none;
}
.data-section :deep(.metric-table .data-table tbody tr:hover) {
  background: #f7f8fa;
}

/* 比较卡片覆盖 */
.data-section :deep(.comparison-card) {
  background: #f7f8fa;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 16px;
}
</style>
