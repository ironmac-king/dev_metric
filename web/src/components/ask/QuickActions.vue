<template>
  <div class="action-bar">
    <button class="bar-btn cursor-pointer" @click="$emit('my-favorites')">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 14L2 9C1 8 1 6.5 2 5.5C3 4.5 4.5 4 5.5 4.5L8 6L10.5 4.5C11.5 4 13 4.5 14 5.5C15 6.5 15 8 14 9L8 14Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>我的收藏</span>
    </button>

    <!-- 推荐问题按钮 + 下拉面板 -->
    <div class="dropdown-wrap" ref="recommendWrap">
      <button
        class="bar-btn cursor-pointer"
        :class="{ active: showRecommend }"
        @click="toggleRecommend"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M8 2L9.5 6H14L10.5 8.5L12 13L8 10.5L4 13L5.5 8.5L2 6H6.5L8 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>推荐问题</span>
        <svg class="arrow" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M3 5L6 8L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      <!-- 推荐问题下拉面板 -->
      <Transition name="dropdown">
        <div v-if="showRecommend" class="dropdown-panel recommend-panel">
          <div class="panel-header">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 2L9.5 6H14L10.5 8.5L12 13L8 10.5L4 13L5.5 8.5L2 6H6.5L8 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>推荐问题</span>
          </div>
          <div class="panel-list" v-if="recommendQuestions.length > 0">
            <div
              v-for="(q, idx) in recommendQuestions"
              :key="idx"
              class="panel-item cursor-pointer"
              @click="selectRecommend(q)"
            >
              <span class="item-icon">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 1L8.5 5H13L9.5 7.5L11 12L7 9L3 12L4.5 7.5L1 5H5.5L7 1Z" fill="currentColor"/>
                </svg>
              </span>
              <span class="item-text">{{ q }}</span>
            </div>
          </div>
          <div v-else class="panel-empty">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/>
              <path d="M12 8V12M12 16H12.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span>暂无推荐问题</span>
          </div>
        </div>
      </Transition>
    </div>

    <!-- 最近提问按钮 + 下拉面板 -->
    <div class="dropdown-wrap" ref="recentWrap">
      <button
        class="bar-btn cursor-pointer"
        :class="{ active: showRecent }"
        @click="toggleRecent"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5"/>
          <path d="M8 5L8 8L10 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>最近提问</span>
        <svg class="arrow" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M3 5L6 8L9 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      <!-- 最近提问下拉面板 -->
      <Transition name="dropdown">
        <div v-if="showRecent" class="dropdown-panel recent-panel">
          <div class="panel-header">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5"/>
              <path d="M8 5L8 8L10 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>最近提问</span>
          </div>
          <div class="panel-list" v-if="recentQuestions.length > 0">
            <div
              v-for="(q, idx) in recentQuestions"
              :key="idx"
              class="panel-item cursor-pointer"
              @click="selectRecent(q)"
            >
              <span class="item-num">{{ idx + 1 }}</span>
              <span class="item-text">{{ q }}</span>
            </div>
          </div>
          <div v-else class="panel-empty">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/>
              <path d="M12 8V12M12 16H12.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span>暂无最近提问</span>
          </div>
        </div>
      </Transition>
    </div>

    <button class="bar-btn cursor-pointer" @click="$emit('clear-context')">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M3 4H13M6 4V3C6 2.5 6.5 2 7 2H9C9.5 2 10 2.5 10 3V4M12 4V13C12 13.5 11.5 14 11 14H5C4.5 14 4 13.5 4 13V4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>清空上下文</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  recommendQuestions: string[]
  recentQuestions: string[]
}>()

const emit = defineEmits<{
  'my-favorites': []
  'select-recommend': [question: string]
  'select-recent': [question: string]
  'clear-context': []
  'open-recommend': []
  'open-recent': []
}>()

const showRecommend = ref(false)
const showRecent = ref(false)
const recommendWrap = ref<HTMLElement | null>(null)
const recentWrap = ref<HTMLElement | null>(null)

function toggleRecommend() {
  showRecent.value = false
  showRecommend.value = !showRecommend.value
  if (showRecommend.value) {
    emit('open-recommend')
  }
}

function toggleRecent() {
  showRecommend.value = false
  showRecent.value = !showRecent.value
  if (showRecent.value) {
    emit('open-recent')
  }
}

function selectRecommend(q: string) {
  showRecommend.value = false
  emit('select-recommend', q)
}

function selectRecent(q: string) {
  showRecent.value = false
  emit('select-recent', q)
}

function handleClickOutside(e: MouseEvent) {
  if (recommendWrap.value && !recommendWrap.value.contains(e.target as Node)) {
    showRecommend.value = false
  }
  if (recentWrap.value && !recentWrap.value.contains(e.target as Node)) {
    showRecent.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.action-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-primary);
  border-top: 1px solid var(--border);
  justify-content: flex-start;
  flex-wrap: wrap;
  position: relative;
  z-index: 100;
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

.bar-btn.active {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-glow);
}

.arrow {
  transition: transform 0.2s ease;
}

.bar-btn.active .arrow {
  transform: rotate(180deg);
}

/* 下拉面板 */
.dropdown-wrap {
  position: relative;
}

.dropdown-panel {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  min-width: 320px;
  max-width: 420px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  overflow: hidden;
  z-index: 200;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-header svg {
  color: var(--primary);
}

.panel-list {
  max-height: 280px;
  overflow-y: auto;
  padding: 8px;
}

.panel-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  transition: all 0.15s ease;
}

.panel-item:hover {
  background: var(--bg-primary);
}

.item-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
}

.item-num {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
}

.item-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
  word-break: break-all;
}

.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--text-muted);
  font-size: 13px;
}

/* 过渡动画 */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
