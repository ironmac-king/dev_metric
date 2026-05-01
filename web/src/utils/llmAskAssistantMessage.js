export function buildAssistantMessage({
  finalAnswer,
  finalSql,
  finalResultData,
  finalMetricName,
  finalMetricNames,
  finalAnalysis,
  finalMultiMetricData,
  finalDimensionalData,
  finalCategory,
  finalSuggest,
  finalNeedsClarification,
  finalThinkingClarificationMessage,
  finalThinkingClarificationOptions,
  finalClarificationOptions,
  finalClarificationMessage,
  finalThinkingOriginalQuestion,
  finalSteps,
  finalStarrocksSql,
  finalMomChange,
  finalYoyChange,
  currentMqlDimensions,
  currentMqlTime,
  currentTime,
}) {
  let displayAnswer = finalAnswer
  if (!displayAnswer && finalResultData && finalResultData.length > 0) {
    const firstRow = finalResultData[0]
    const keys = Object.keys(firstRow)
    if (keys.length === 1) {
      const val = firstRow[keys[0]]
      if (!isNaN(parseFloat(val))) {
        const num = parseFloat(val)
        let formatted = num.toLocaleString()
        if (num >= 100000000) formatted = (num / 100000000).toFixed(2) + '亿'
        else if (num >= 10000) formatted = (num / 10000).toFixed(2) + '万'
        displayAnswer = `查询结果：${formatted}`
      }
    }
  }

  const effectiveClarificationOptions = finalNeedsClarification && finalThinkingClarificationOptions.length > 0
    ? finalThinkingClarificationOptions
    : finalClarificationOptions
  const effectiveClarificationMessage = finalNeedsClarification && finalThinkingClarificationMessage
    ? finalThinkingClarificationMessage
    : finalClarificationMessage

  const extractedMql = (() => {
    for (let i = finalSteps.length - 1; i >= 0; i--) {
      if (finalSteps[i].mql) {
        return finalSteps[i].mql
      }
    }
    return null
  })()

  let finalContent = ''
  if (finalNeedsClarification && finalThinkingClarificationMessage) {
    finalContent = finalThinkingClarificationMessage
  } else {
    finalContent =
      displayAnswer ||
      finalAnalysis?.summary ||
      (finalResultData && finalResultData.length > 0
        ? `已整理 ${finalResultData.length} 条结果，重点如下。`
        : '抱歉，我没有找到相关数据。')
  }

  return {
    role: 'assistant',
    content: finalContent,
    sql: finalSql,
    thinkingSteps: finalSteps,
    mql: extractedMql,
    resultData: finalResultData,
    metricName: finalMetricName,
    metricNames: finalMetricNames,
    analysis: finalAnalysis,
    multiMetricData: finalMultiMetricData,
    dimensionalData: finalDimensionalData,
    category: finalCategory,
    suggest: finalSuggest,
    needsClarification: finalNeedsClarification || effectiveClarificationOptions.length > 0,
    clarificationOptions: effectiveClarificationOptions,
    clarificationMessage: effectiveClarificationMessage,
    originalQuestion: finalThinkingOriginalQuestion,
    starrocksSql: finalStarrocksSql,
    momChange: finalMomChange,
    yoyChange: finalYoyChange,
    dimensionFilters: currentMqlDimensions,
    timeRange: currentMqlTime,
    time: currentTime,
  }
}
