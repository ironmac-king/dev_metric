function normalizeText(value) {
  return String(value || '').replace(/\r\n/g, '\n').trim()
}

function splitParagraphs(text) {
  return normalizeText(text)
    .split(/\n+/)
    .map(item => item.trim())
    .filter(Boolean)
}

function tryParseNumber(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const normalized = value.replace(/,/g, '').trim()
    if (/^-?\d+(\.\d+)?$/.test(normalized)) {
      const parsed = Number.parseFloat(normalized)
      if (Number.isFinite(parsed)) return parsed
    }
  }
  return null
}

function formatMetricValue(value) {
  const numeric = tryParseNumber(value)
  if (numeric === null) return normalizeText(value)
  if (Number.isInteger(numeric)) return String(numeric)
  return numeric.toFixed(2).replace(/\.00$/, '')
}

function buildRankingLead(message) {
  const rows = Array.isArray(message?.resultData) ? message.resultData : []
  if (rows.length === 0) return ''

  const sample = rows[0] || {}
  const keys = Object.keys(sample)
  if (keys.length < 2) return ''

  const metricName = normalizeText(message?.metricName) || '指标'
  const numericKey = keys.find(key => tryParseNumber(sample[key]) !== null)
  const labelKey = keys.find(key => key !== numericKey && typeof sample[key] === 'string')

  if (!numericKey || !labelKey) return ''

  const rankingRows = rows
    .map(row => ({
      label: normalizeText(row[labelKey]),
      value: tryParseNumber(row[numericKey]),
    }))
    .filter(row => row.label && row.value !== null)
    .sort((a, b) => b.value - a.value)

  if (rankingRows.length === 0) return ''

  if (rankingRows.length === 1) {
    return `按${metricName}看，${rankingRows[0].label}为 ${formatMetricValue(rankingRows[0].value)}。`
  }

  return `按${metricName}看，${rankingRows[0].label}最高（${formatMetricValue(rankingRows[0].value)}），${rankingRows[1].label}次之（${formatMetricValue(rankingRows[1].value)}）。`
}

function buildFallbackLead(message) {
  const summary = normalizeText(message?.analysis?.summary)
  if (summary) return summary

  const rankingLead = buildRankingLead(message)
  if (rankingLead) return rankingLead

  const metricName = normalizeText(message?.metricName)
  const resultCount = Array.isArray(message?.resultData) ? message.resultData.length : 0
  if (metricName && resultCount > 0) {
    return `已整理「${metricName}」结果，共 ${resultCount} 条，重点如下。`
  }
  if (resultCount > 0) {
    return `已整理 ${resultCount} 条结果，重点如下。`
  }
  return '我已经整理好这次分析的重点。'
}

function buildAnalysisParagraphs(message) {
  const analysis = message?.analysis
  if (!analysis) return []

  const paragraphs = []
  const urgent = normalizeText(analysis.top_urgent_action)
  if (urgent) paragraphs.push(urgent)

  const actionItems = Array.isArray(analysis.action_items) ? analysis.action_items : []
  for (const item of actionItems) {
    const text = normalizeText(item?.text || item)
    if (text) paragraphs.push(text)
  }

  return paragraphs
}

export function buildAssistantPresentation(message = {}) {
  const rawContent = normalizeText(
    message.needsClarification
      ? (message.clarificationMessage || message.content)
      : message.content
  )
  const rawParagraphs = splitParagraphs(rawContent)
  const lead = rawParagraphs[0] || buildFallbackLead(message)

  const paragraphs = rawParagraphs.length > 0
    ? rawParagraphs.slice(rawParagraphs[0] === lead ? 1 : 0)
    : buildAnalysisParagraphs(message)

  return {
    lead,
    paragraphs,
    hasEvidence: Boolean(
      (Array.isArray(message.resultData) && message.resultData.length > 0) ||
      message.analysis
    ),
    hasSuggestions: Boolean(
      Array.isArray(message.suggest) && message.suggest.length > 0
    ),
  }
}
