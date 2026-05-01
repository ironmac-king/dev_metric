import test from 'node:test'
import assert from 'node:assert/strict'

import { buildAssistantMessage } from './llmAskAssistantMessage.js'
import { buildAssistantPresentation } from './assistantResponsePresentation.js'

test('buildAssistantMessage keeps answer text when result data exists', () => {
  const message = buildAssistantMessage({
    finalAnswer: '结论：移动电源增长最快，适配器规模最大。',
    finalSql: 'select 1',
    finalResultData: [{ category: '移动电源', revenue: 12.18 }],
    finalMetricName: '销售额',
    finalMetricNames: ['销售额'],
    finalAnalysis: null,
    finalMultiMetricData: [],
    finalDimensionalData: {},
    finalCategory: '',
    finalSuggest: [],
    finalNeedsClarification: false,
    finalThinkingClarificationMessage: '',
    finalThinkingClarificationOptions: [],
    finalClarificationOptions: [],
    finalClarificationMessage: '',
    finalThinkingOriginalQuestion: '',
    finalSteps: [],
    finalStarrocksSql: '',
    finalMomChange: null,
    finalYoyChange: null,
    currentMqlDimensions: [],
    currentMqlTime: null,
    currentTime: '2026-05-01T12:00:00.000Z',
  })

  assert.equal(message.content, '结论：移动电源增长最快，适配器规模最大。')
})

test('buildAssistantPresentation splits lead and details from multiline answer', () => {
  const presentation = buildAssistantPresentation({
    role: 'assistant',
    content: '结论：移动电源增长最快。\n原因：同比增速最高，且规模已过十亿。\n建议：继续看线上/线下拆分。',
    resultData: [{ category: '移动电源', revenue: 12.18 }],
    metricName: '销售额',
    analysis: null,
    suggest: [],
    needsClarification: false,
  })

  assert.equal(presentation.lead, '结论：移动电源增长最快。')
  assert.deepEqual(presentation.paragraphs, [
    '原因：同比增速最高，且规模已过十亿。',
    '建议：继续看线上/线下拆分。',
  ])
  assert.equal(presentation.hasEvidence, true)
})

test('buildAssistantPresentation builds a readable fallback lead from structured result', () => {
  const presentation = buildAssistantPresentation({
    role: 'assistant',
    content: '',
    resultData: [{ category: '电源适配器', revenue: 18.52 }],
    metricName: '销售额',
    analysis: { summary: '电源适配器规模最大，移动电源增速更快。' },
    suggest: ['继续看境内/境外'],
    needsClarification: false,
  })

  assert.equal(presentation.lead, '电源适配器规模最大，移动电源增速更快。')
  assert.deepEqual(presentation.paragraphs, [])
  assert.equal(presentation.hasSuggestions, true)
})

test('buildAssistantPresentation expands analysis details when plain content is empty', () => {
  const presentation = buildAssistantPresentation({
    role: 'assistant',
    content: '',
    resultData: [{ category: '电源适配器', revenue: 18.52 }],
    metricName: '销售额',
    analysis: {
      summary: '电源适配器规模最大，移动电源增速更快。',
      top_urgent_action: '优先看线上/线下拆分，确认增长来源。',
      action_items: [
        { text: '继续看境内/境外差异。' },
        { text: '再看亚马逊/独立站结构。' },
      ],
    },
    suggest: [],
    needsClarification: false,
  })

  assert.equal(presentation.lead, '电源适配器规模最大，移动电源增速更快。')
  assert.deepEqual(presentation.paragraphs, [
    '优先看线上/线下拆分，确认增长来源。',
    '继续看境内/境外差异。',
    '再看亚马逊/独立站结构。',
  ])
})

test('buildAssistantPresentation preserves a short verdict first when answer already contains structured lines', () => {
  const presentation = buildAssistantPresentation({
    role: 'assistant',
    content: '结论：线上增长主要来自移动电源。\n最值得继续看的是线上/线下差异。\n如果你要，我可以继续拆境内/境外。',
    resultData: [{ channel: '线上', revenue: 12.18 }],
    metricName: '销售额',
    analysis: null,
    suggest: ['继续看境内/境外'],
    needsClarification: false,
  })

  assert.equal(presentation.lead, '结论：线上增长主要来自移动电源。')
  assert.deepEqual(presentation.paragraphs, [
    '最值得继续看的是线上/线下差异。',
    '如果你要，我可以继续拆境内/境外。',
  ])
})

test('buildAssistantPresentation synthesizes a ranking verdict from tabular result data', () => {
  const presentation = buildAssistantPresentation({
    role: 'assistant',
    content: '',
    resultData: [
      { category: '电源适配器', revenue: 18.52 },
      { category: '移动电源', revenue: 12.18 },
      { category: '蓝牙耳机', revenue: 6.31 },
    ],
    metricName: '销售额',
    analysis: null,
    suggest: [],
    needsClarification: false,
  })

  assert.equal(presentation.lead, '按销售额看，电源适配器最高（18.52），移动电源次之（12.18）。')
})
