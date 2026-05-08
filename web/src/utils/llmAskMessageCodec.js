export function decodeStoredAskMessage(msg) {
  const base = {
    role: msg.role,
    content: msg.content,
    sql: msg.sql,
    resultData: msg.result_data,
    time: msg.created_at || new Date().toISOString(),
  }

  if (!msg.extra_data) {
    return {
      ...base,
      thinkingSteps: [],
      mql: null,
      metricName: '',
      metricNames: [],
      analysis: null,
    }
  }

  try {
    const extra = typeof msg.extra_data === 'string'
      ? JSON.parse(msg.extra_data)
      : msg.extra_data

    return {
      ...base,
      resultData: extra.resultData || msg.result_data,
      metricName: extra.metricName || '',
      metricNames: extra.metricNames || [],
      analysis: extra.analysis || null,
      multiMetricData: extra.multiMetricData || null,
      dimensionalData: extra.dimensionalData || null,
      category: extra.category || null,
      suggest: extra.suggest || [],
      interpretation: extra.interpretation || '',
      columns: extra.columns || [],
      mql: extra.mql || null,
      timeRange: extra.timeRange || null,
      starrocksSql: extra.starrocksSql || msg.sql,
      momChange: extra.momChange ?? null,
      yoyChange: extra.yoyChange ?? null,
      dimensionFilters: extra.dimensionFilters || [],
      thinkingSteps: extra.thinkingSteps || [],
      needsClarification: extra.needsClarification || false,
      clarificationOptions: extra.clarificationOptions || [],
      clarificationMessage: extra.clarificationMessage || '',
      originalQuestion: extra.originalQuestion || '',
    }
  } catch (error) {
    console.warn('[decodeStoredAskMessage] extra_data parse failed:', error)
    return {
      ...base,
      thinkingSteps: [],
      mql: null,
      metricName: '',
      metricNames: [],
      analysis: null,
    }
  }
}

export function buildAssistantExtraData(assistantMsg) {
  return {
    resultData: assistantMsg.resultData,
    metricName: assistantMsg.metricName,
    metricNames: assistantMsg.metricNames,
    analysis: assistantMsg.analysis,
    multiMetricData: assistantMsg.multiMetricData,
    dimensionalData: assistantMsg.dimensionalData,
    category: assistantMsg.category,
    suggest: assistantMsg.suggest,
    interpretation: assistantMsg.interpretation,
    columns: assistantMsg.columns,
    mql: assistantMsg.mql,
    timeRange: assistantMsg.timeRange,
    starrocksSql: assistantMsg.starrocksSql,
    momChange: assistantMsg.momChange,
    yoyChange: assistantMsg.yoyChange,
    dimensionFilters: assistantMsg.dimensionFilters,
    thinkingSteps: assistantMsg.thinkingSteps,
    needsClarification: assistantMsg.needsClarification,
    clarificationOptions: assistantMsg.clarificationOptions,
    clarificationMessage: assistantMsg.clarificationMessage,
    originalQuestion: assistantMsg.originalQuestion,
  }
}
