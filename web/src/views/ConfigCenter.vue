<template>
  <div class="config-center-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="page-icon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M11 2L20 6V16L11 20L2 16V6L11 2Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
            <path d="M8 11L10 13L14 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="header-text">
          <h1>配置中心</h1>
          <p>管理智能问数后台配置</p>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="config-tabs-wrapper">
      <el-tabs v-model="activeTab" class="config-tabs">
        <!-- 数据源配置 -->
        <el-tab-pane label="数据源配置" name="datasource">
          <StarRocksConfig />
        </el-tab-pane>

        <!-- 触发规则 -->
        <el-tab-pane label="触发规则" name="trigger">
          <TriggerConfig />
        </el-tab-pane>

        <!-- 开关管理 -->
        <el-tab-pane label="开关管理" name="switch">
          <SwitchConfig />
        </el-tab-pane>

        <!-- 模板配置 -->
        <el-tab-pane label="模板配置" name="template">
          <TemplateConfig />
        </el-tab-pane>

        <!-- 维度标签 -->
        <el-tab-pane label="维度标签" name="label">
          <LabelConfig />
        </el-tab-pane>

        <!-- 维度配置 -->
        <el-tab-pane label="维度配置" name="dimension">
          <DimensionConfig />
        </el-tab-pane>

        <!-- 意图配置 -->
        <el-tab-pane label="意图配置" name="intent">
          <IntentConfig />
        </el-tab-pane>

        <!-- LLM配置 -->
        <el-tab-pane label="LLM配置" name="llm">
          <LLMConfigPanel />
        </el-tab-pane>

        <!-- 告警配置 -->
        <el-tab-pane label="告警配置" name="alert">
          <AlertConfigPanel />
        </el-tab-pane>

        <!-- 语义层 -->
        <el-tab-pane label="语义层" name="semantic">
          <SemanticConfigPanel />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import TriggerConfig from './config/TriggerConfig.vue'
import SwitchConfig from './config/SwitchConfig.vue'
import TemplateConfig from './config/TemplateConfig.vue'
import LabelConfig from './config/LabelConfig.vue'
import DimensionConfig from './DimensionConfig.vue'
import IntentConfig from './config/IntentConfig.vue'
import LLMConfigPanel from './config/LLMConfigPanel.vue'
import AlertConfigPanel from './config/AlertConfigPanel.vue'
import SemanticConfigPanel from './config/SemanticConfigPanel.vue'
import StarRocksConfig from './StarRocksConfig.vue'

const activeTab = ref('trigger')
</script>

<style scoped>
.config-center-page {
  padding: 24px;
  min-height: 100vh;
  background: #f5f3ff;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #6366f1, #818cf8);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.header-text h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1e1b4b;
  font-family: 'Fira Code', monospace;
}

.header-text p {
  margin: 4px 0 0;
  font-size: 14px;
  color: #6b7280;
}

.config-tabs-wrapper {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

:deep(.config-tabs) {
  --el-color-primary: #6366f1;
}

:deep(.config-tabs .el-tabs__header) {
  margin-bottom: 20px;
}

:deep(.config-tabs .el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
  color: #6b7280;
  padding: 0 20px;
  height: 40px;
  line-height: 40px;
}

:deep(.config-tabs .el-tabs__item:hover) {
  color: #6366f1;
}

:deep(.config-tabs .el-tabs__item.is-active) {
  color: #6366f1;
  font-weight: 600;
}

:deep(.config-tabs .el-tabs__nav-wrap::after) {
  background-color: #e5e7eb;
  height: 1px;
}

:deep(.config-tabs .el-tabs__active-bar) {
  background-color: #6366f1;
  height: 2px;
  border-radius: 1px;
}
</style>
