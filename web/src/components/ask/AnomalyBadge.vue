<template>
  <div class="anomaly-list">
    <el-alert
      v-for="anomaly in anomalies"
      :key="anomaly.type"
      :type="getAlertType(anomaly.type)"
      :title="anomaly.message"
      :closable="false"
      show-icon
      class="anomaly-alert"
    >
      <template #icon>
        <span class="anomaly-icon">{{ getIcon(anomaly.type) }}</span>
      </template>
    </el-alert>
  </div>
</template>

<script setup>
const props = defineProps({
  anomalies: {
    type: Array,
    default: () => []
  }
})

const getAlertType = (type) => {
  if (type.includes('drop') || type.includes('fall')) {
    return 'warning'
  }
  if (type.includes('rise') || type.includes('increase') || type.includes('spike')) {
    return 'success'
  }
  if (type.includes('zero') || type.includes('empty')) {
    return 'info'
  }
  return 'warning'
}

const getIcon = (type) => {
  if (type.includes('drop') || type.includes('fall')) {
    return '📉'
  }
  if (type.includes('rise') || type.includes('increase') || type.includes('spike')) {
    return '📈'
  }
  if (type.includes('zero') || type.includes('empty')) {
    return '📊'
  }
  return '⚠️'
}
</script>

<style scoped>
.anomaly-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.anomaly-alert {
  border-radius: var(--radius-md, 6px);
}

.anomaly-alert :deep(.el-alert__title) {
  font-size: 13px;
  font-weight: 500;
}

.anomaly-icon {
  font-size: 16px;
}
</style>
