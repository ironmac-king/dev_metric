import { buildAssistantMessage } from './llmAskAssistantMessage'

export function createLlmAskStreamAccumulator(callbacks = {}) {
  const {
    onThinkingStepsChange,
    onSqlChange,
    onSessionConnected,
    onDone,
    onError,
  } = callbacks

  let finalAnswer = ''
  let finalSql = ''
  let finalResultData = []
  let finalMetricName = ''
  let finalMetricNames = []
  let finalMetricUnit = ''
  let finalAnalysis = null
  let finalMultiMetricData = []
  let finalDimensionalData = {}
  let finalCategory = ''
  let finalSuggest = []
  let finalClarificationOptions = []
  let finalClarificationMessage = ''
  let finalNeedsClarification = false
  let finalThinkingClarificationMessage = ''
  let finalThinkingClarificationOptions = []
  let finalThinkingOriginalQuestion = ''
  let finalStarrocksSql = ''
  let finalMomChange = null
  let finalYoyChange = null
  let finalSupplementaryInfo = []
  let finalExplanation = null
  let finalKpiTooltip = null
  let currentMqlDimensions = []
  let currentMqlTime = null
  const thinkingStepsMap = new Map()

  function emitThinkingSteps() {
    if (onThinkingStepsChange) {
      onThinkingStepsChange(Array.from(thinkingStepsMap.values()))
    }
  }

  // 解析 LLM 返回的 JSON 字符串，提取 summary 和 action_items
  // 返回值：是否成功解析（markdown JSON -> 结构化对象）
  function _parseAnalysisLLMContent(analysis) {
    if (!analysis || typeof analysis.summary !== 'string') return false
    if (!analysis.summary.startsWith('```json')) return false

    let summaryText = analysis.summary
    const jsonMatch = summaryText.match(/```json\n([\s\S]*?)\n```/)
    if (!jsonMatch || !jsonMatch[1]) return false

    try {
      const parsed = JSON.parse(jsonMatch[1].trim())
      if (parsed.summary) {
        analysis.summary = parsed.summary
      }
      if (parsed.action_items && Array.isArray(parsed.action_items) && parsed.action_items.length > 0) {
        analysis.action_items = parsed.action_items
      }
      return true
    } catch (e) {
      return false
    }
  }

  // 解析过的内容缓存，防止被后续 SSE 事件覆盖
  let _cachedParsedSummary = null
  let _cachedParsedActionItems = null

  function handleEvent(currentEvent, data) {
    if (currentEvent === 'step_start') {
      const stepName = data.step
      thinkingStepsMap.set(stepName, {
        step: stepName,
        status: 'in_progress',
        content: '',
        duration: '',
      })
      emitThinkingSteps()
      return
    }

    if (currentEvent === 'step_complete') {
      const stepName = data.step
      const existing = thinkingStepsMap.get(stepName) || { step: stepName }
      thinkingStepsMap.set(stepName, {
        ...existing,
        status: 'completed',
        duration: data.duration_ms ? `${data.duration_ms}ms` : '',
      })
      emitThinkingSteps()
      return
    }

    if (currentEvent === 'thinking') {
      const stepName = data.step
      const existing = thinkingStepsMap.get(stepName) || { step: stepName }
      thinkingStepsMap.set(stepName, {
        ...existing,
        content: data.content,
        entities: data.entities || [],
        llm_used: data.llm_used || false,
        source: data.source || null,
        mql: data.mql || null,
        needsClarification: data.needs_clarification || false,
        clarificationMessage: data.clarification_message || '',
        clarificationOptions: data.clarification_options || [],
        originalQuestion: data.original_question || '',
      })
      if (data.mql?.dimensions?.length) {
        currentMqlDimensions = data.mql.dimensions
      }
      if (data.mql?.time) {
        currentMqlTime = data.mql.time
      }
      if (data.needs_clarification) {
        finalNeedsClarification = true
        finalThinkingClarificationMessage = data.clarification_message || ''
        finalThinkingClarificationOptions = data.clarification_options || []
        finalThinkingOriginalQuestion = data.original_question || ''
      }
      emitThinkingSteps()
      return
    }

    if (currentEvent === 'sql_ready') {
      finalSql = data.sql
      if (onSqlChange) onSqlChange(finalSql)
      return
    }

    if (currentEvent === 'result_ready') {
      finalResultData = data.result_data || []
      finalMetricName = data.metric_name || ''
      finalMetricNames = data.metric_names || []
      finalMetricUnit = data.metric_unit || ''
      finalAnalysis = data.analysis || null
      const didParse = _parseAnalysisLLMContent(finalAnalysis)
      // 只在成功解析 markdown JSON 时更新缓存，防止被后续 result_ready 覆盖
      if (finalAnalysis && didParse) {
        _cachedParsedSummary = finalAnalysis.summary
        _cachedParsedActionItems = finalAnalysis.action_items
      }

      finalMultiMetricData = data.multi_metric_data || []
      finalDimensionalData = data.dimensional_data || {}
      finalCategory = data.category || ''
      finalSupplementaryInfo = data.supplementaryInfo || []
      finalStarrocksSql = data.starrocks_sql || ''
      finalMomChange = data.mom_change ?? null
      finalYoyChange = data.yoy_change ?? null
      return
    }

    if (currentEvent === 'answer_ready') {
      finalAnswer = data.answer
      finalSuggest = data.suggestions || []
      finalClarificationOptions = data.clarification_options || []
      finalClarificationMessage = data.clarification_message || ''
      if (data.analysis) {
        finalAnalysis = data.analysis
        _parseAnalysisLLMContent(finalAnalysis)
        // 应用缓存的解析结果
        if (_cachedParsedSummary && finalAnalysis.summary !== _cachedParsedSummary) {
          finalAnalysis.summary = _cachedParsedSummary
        }
        if (_cachedParsedActionItems && finalAnalysis.action_items !== _cachedParsedActionItems) {
          finalAnalysis.action_items = _cachedParsedActionItems
        }
      }
      if (data.multi_metric_data) finalMultiMetricData = data.multi_metric_data
      if (data.dimensional_data) finalDimensionalData = data.dimensional_data
      if (data.category) finalCategory = data.category
      if (data.explanation) finalExplanation = data.explanation
      if (data.kpi_tooltip) finalKpiTooltip = data.kpi_tooltip
      return
    }

    if (currentEvent === 'connected') {
      if (data.session_id && onSessionConnected) {
        onSessionConnected(data.session_id)
      }
      return
    }

    if (currentEvent === 'done') {
      if (onDone) onDone()
      return
    }

    if (currentEvent === 'error') {
      if (onError) onError(data.error)
    }
  }

  function getFinalSteps() {
    return Array.from(thinkingStepsMap.values()).map(s => ({
      step: s.step,
      status: s.status,
      content: s.content,
      duration: s.duration,
      entities: s.entities || [],
      llm_used: s.llm_used || false,
      source: s.source || null,
      mql: s.mql || null,
    }))
  }

  function buildMessage(currentTime) {
    // 最终兜底解析：在 build 前确保 finalAnalysis 的 markdown JSON 被解析过
    _parseAnalysisLLMContent(finalAnalysis)

    const msg = buildAssistantMessage({
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
      finalSteps: getFinalSteps(),
      finalStarrocksSql,
      finalMomChange,
      finalYoyChange,
      finalSupplementaryInfo,
      finalExplanation,
      finalKpiTooltip,
      currentMqlDimensions,
      currentMqlTime,
      currentTime,
      finalMetricUnit,
    })
    return msg
  }

  function getFinalResultData() {
    return finalResultData
  }

  return {
    handleEvent,
    getFinalSteps,
    buildMessage,
    getFinalResultData,
  }
}
