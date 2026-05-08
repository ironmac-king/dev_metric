<template>
  <div class="thinking-timeline" :class="{ 'dark-mode': darkMode }">
    <div class="timeline-header" @click="toggleExpand">
      <div class="header-left">
        <span class="timeline-icon">🧠</span>
        <span class="timeline-title">分析过程</span>
        <span class="step-count">{{ steps.length }} 步</span>
        <span v-if="totalDuration" class="total-duration">{{ totalDuration }}ms</span>
      </div>
      <div class="header-right">
        <el-tag :type="allCompleted ? 'success' : 'info'" size="small">
          {{ allCompleted ? '已完成' : '进行中' }}
        </el-tag>
        <span class="expand-icon">{{ expanded ? '▲' : '▼' }}</span>
      </div>
    </div>

    <transition name="expand">
      <div v-if="expanded" class="timeline-content">
        <div class="timeline-steps">
          <div
            v-for="(step, index) in steps"
            :key="index"
            class="timeline-step"
            :class="step.status"
          >
            <div class="step-indicator">
              <span v-if="step.status === 'completed'" class="status-icon completed">✓</span>
              <span v-else-if="step.status === 'failed'" class="status-icon failed">✗</span>
              <span v-else class="status-icon pending">●</span>
              <span v-if="index < steps.length - 1" class="connector"></span>
            </div>
            <div class="step-content">
              <div class="step-header">
                <span class="step-name">{{ formatStepName(step.step) }}</span>
                <span v-if="step.duration_ms" class="step-duration">{{ step.duration_ms }}ms</span>
                <el-tag v-if="step.llm_used" type="warning" size="small" class="llm-tag">LLM</el-tag>
              </div>
              <div v-if="step.content" class="step-description">{{ step.content }}</div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  steps: {
    type: Array,
    default: () => []
  },
  darkMode: {
    type: Boolean,
    default: false
  }
})

const expanded = ref(true)

const toggleExpand = () => {
  expanded.value = !expanded.value
}

const totalDuration = computed(() => {
  if (!props.steps.length) return 0
  return props.steps.reduce((sum, step) => sum + (step.duration_ms || 0), 0)
})

const allCompleted = computed(() => {
  return props.steps.every(step => step.status === 'completed')
})

const formatStepName = (name) => {
  if (!name) return ''
  const names = {
    'intent_router': '意图路由',
    'context_enhancer': '上下文增强',
    'mql_generator': 'MQL生成',
    'mql_syntax_validator': 'MQL语法校验',
    'mql_semantic_validator': 'MQL语义校验',
    'sql_generator': 'SQL生成',
    'sql_security_auditor': 'SQL安全审计',
    'sql_executor': 'SQL执行',
    'data_quality_checker': '数据质量检查',
    'result_analyzer': '结果分析',
    'state_manager': '状态管理'
  }
  return names[name] || name
}
</script>

<style scoped>
.thinking-timeline {
  background: var(--bg-card, #fff);
  border: 1px solid var(--border, #e8e8e8);
  border-radius: var(--radius-lg, 8px);
  overflow: hidden;
}

.thinking-timeline.dark-mode {
  background: #1a1a2e;
  border-color: #2d2d4a;
}

.timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.timeline-header:hover {
  background: rgba(0, 0, 0, 0.02);
}

.dark-mode .timeline-header:hover {
  background: rgba(255, 255, 255, 0.05);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.timeline-icon {
  font-size: 16px;
}

.timeline-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1F1F1F);
}

.dark-mode .timeline-title {
  color: #fff;
}

.step-count {
  font-size: 12px;
  color: var(--text-muted, #999);
  padding: 2px 8px;
  background: var(--bg-primary, #f2f3f5);
  border-radius: 10px;
}

.dark-mode .step-count {
  background: #2d2d4a;
  color: #aaa;
}

.total-duration {
  font-size: 12px;
  color: var(--text-muted, #999);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.expand-icon {
  font-size: 10px;
  color: var(--text-muted, #999);
}

.timeline-content {
  border-top: 1px solid var(--border, #e8e8e8);
  padding: 16px;
}

.dark-mode .timeline-content {
  border-color: #2d2d4a;
}

.timeline-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-step {
  display: flex;
  gap: 12px;
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 20px;
  flex-shrink: 0;
}

.status-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

.status-icon.completed {
  background: #00A870;
  color: #fff;
}

.status-icon.failed {
  background: #F56C6C;
  color: #fff;
}

.status-icon.pending {
  background: #E6A23C;
  color: #fff;
}

.connector {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: var(--border, #e8e8e8);
  margin: 4px 0;
}

.dark-mode .connector {
  background: #2d2d4a;
}

.step-content {
  flex: 1;
  padding-bottom: 16px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.step-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #1F1F1F);
}

.dark-mode .step-name {
  color: #fff;
}

.step-duration {
  font-size: 12px;
  color: var(--text-muted, #999);
}

.llm-tag {
  font-size: 10px;
  padding: 0 4px;
}

.step-description {
  font-size: 12px;
  color: var(--text-secondary, #666);
  line-height: 1.5;
}

.dark-mode .step-description {
  color: #aaa;
}

/* Expand transition */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.expand-enter-to,
.expand-leave-from {
  max-height: 500px;
}
</style>
