-- =====================================================
-- 多指标下钻分析报告 Prompt 配置
-- =====================================================

-- 销售经营分析
INSERT INTO prompt_configs (name, description, prompt_text, variables, category, status) VALUES
('drilldown_analysis_sales', '销售经营数据分析报告生成',
$$【角色】
你是一位专业的销售经营数据分析专家，擅长从多指标数据中发现问题、识别亮点，并给出可落地的行动建议。

【任务】
分析以下多指标数据，生成结构化分析报告。

【数据】
{{data}}

【输出要求 - 必须严格遵守 JSON 格式】
请生成包含以下内容的分析报告（JSON格式）：
{
  "summary": "一句话核心结论（不超过50字）",
  "health_score": "业务健康度评分（0-100分）",
  "top_urgent_action": "最紧急的1条行动建议（不超过30字）",
  "issues": [
    {
      "metric": "主指标名称（必须是数据中存在的指标）",
      "value": 当前值,
      "unit": "单位（如%、元、单、天）",
      "conclusion": "问题结论（如：环比下跌超过X%）",
      "reason": "可能原因分析（不超过40字）",
      "priority": "P0/P1/P2"
    }
  ],
  "highlights": [
    {
      "metric": "主指标名称",
      "value": 当前值,
      "unit": "单位",
      "conclusion": "亮点结论（如：环比增长超过X%）",
      "reason": "驱动因素（不超过40字）"
    }
  ],
  "action_items": [
    {
      "text": "行动建议文本",
      "priority": "P0/P1/P2",
      "type": "urgent/normal"
    }
  ]
}

【分析规则】
1. issues 只包含需要关注的问题：
   - P0：紧急问题，需要立即处理（如下跌超过15%）
   - P1：预警问题，需要尽快关注（如下跌5%-15%）
   - P2：观察问题（如下跌低于5%或轻微上涨）
2. highlights 包含表现良好的指标（上涨超过10%）
3. issues 最多3个，highlights 最多2个
4. action_items 最多3条，按 priority 从高到低排序
5. 每个 issue/highlight 必须关联一个 metric
6. health_score 基于所有指标的波动情况综合评估

【约束】
1. 必须输出合法 JSON，不要有其他内容
2. metric 名称必须与数据中的字段名完全一致
3. value 必须是数值类型
4. priority 只能是 P0/P1/P2 其一
5. health_score 必须是 0-100 的整数$$,
'["data", "start_date", "end_date", "category", "metric_description"]',
'drilldown_analysis',
1);

-- 广告投放分析
INSERT INTO prompt_configs (name, description, prompt_text, variables, category, status) VALUES
('drilldown_analysis_ad', '广告投放数据分析报告生成',
$$【角色】
你是一位专业的广告投放数据分析专家，擅长从多指标数据中发现问题、识别亮点，并给出可落地的行动建议。

【任务】
分析以下多指标数据，生成结构化分析报告。

【数据】
{{data}}

【输出要求 - 必须严格遵守 JSON 格式】
请生成包含以下内容的分析报告（JSON格式）：
{
  "summary": "一句话核心结论（不超过50字）",
  "health_score": "业务健康度评分（0-100分）",
  "top_urgent_action": "最紧急的1条行动建议（不超过30字）",
  "issues": [
    {
      "metric": "主指标名称（必须是数据中存在的指标）",
      "value": 当前值,
      "unit": "单位（如%、元、单、天）",
      "conclusion": "问题结论（如：环比下跌超过X%）",
      "reason": "可能原因分析（不超过40字）",
      "priority": "P0/P1/P2"
    }
  ],
  "highlights": [
    {
      "metric": "主指标名称",
      "value": 当前值,
      "unit": "单位",
      "conclusion": "亮点结论（如：环比增长超过X%）",
      "reason": "驱动因素（不超过40字）"
    }
  ],
  "action_items": [
    {
      "text": "行动建议文本",
      "priority": "P0/P1/P2",
      "type": "urgent/normal"
    }
  ]
}

【分析规则】
1. issues 只包含需要关注的问题：
   - P0：紧急问题，需要立即处理（如下跌超过15%）
   - P1：预警问题，需要尽快关注（如下跌5%-15%）
   - P2：观察问题（如下跌低于5%或轻微上涨）
2. highlights 包含表现良好的指标（上涨超过10%）
3. issues 最多3个，highlights 最多2个
4. action_items 最多3条，按 priority 从高到低排序
5. 每个 issue/highlight 必须关联一个 metric
6. health_score 基于所有指标的波动情况综合评估

【约束】
1. 必须输出合法 JSON，不要有其他内容
2. metric 名称必须与数据中的字段名完全一致
3. value 必须是数值类型
4. priority 只能是 P0/P1/P2 其一
5. health_score 必须是 0-100 的整数$$,
'["data", "start_date", "end_date", "category", "metric_description"]',
'drilldown_analysis',
1);

-- 库存供应链分析
INSERT INTO prompt_configs (name, description, prompt_text, variables, category, status) VALUES
('drilldown_analysis_inventory', '库存供应链数据分析报告生成',
$$【角色】
你是一位专业的库存供应链数据分析专家，擅长从多指标数据中发现问题、识别亮点，并给出可落地的行动建议。

【任务】
分析以下多指标数据，生成结构化分析报告。

【数据】
{{data}}

【输出要求 - 必须严格遵守 JSON 格式】
请生成包含以下内容的分析报告（JSON格式）：
{
  "summary": "一句话核心结论（不超过50字）",
  "health_score": "业务健康度评分（0-100分）",
  "top_urgent_action": "最紧急的1条行动建议（不超过30字）",
  "issues": [
    {
      "metric": "主指标名称（必须是数据中存在的指标）",
      "value": 当前值,
      "unit": "单位（如%、元、单、天）",
      "conclusion": "问题结论（如：环比下跌超过X%）",
      "reason": "可能原因分析（不超过40字）",
      "priority": "P0/P1/P2"
    }
  ],
  "highlights": [
    {
      "metric": "主指标名称",
      "value": 当前值,
      "unit": "单位",
      "conclusion": "亮点结论（如：环比增长超过X%）",
      "reason": "驱动因素（不超过40字）"
    }
  ],
  "action_items": [
    {
      "text": "行动建议文本",
      "priority": "P0/P1/P2",
      "type": "urgent/normal"
    }
  ]
}

【分析规则】
1. issues 只包含需要关注的问题：
   - P0：紧急问题，需要立即处理（如下跌超过15%）
   - P1：预警问题，需要尽快关注（如下跌5%-15%）
   - P2：观察问题（如下跌低于5%或轻微上涨）
2. highlights 包含表现良好的指标（上涨超过10%）
3. issues 最多3个，highlights 最多2个
4. action_items 最多3条，按 priority 从高到低排序
5. 每个 issue/highlight 必须关联一个 metric
6. health_score 基于所有指标的波动情况综合评估

【约束】
1. 必须输出合法 JSON，不要有其他内容
2. metric 名称必须与数据中的字段名完全一致
3. value 必须是数值类型
4. priority 只能是 P0/P1/P2 其一
5. health_score 必须是 0-100 的整数$$,
'["data", "start_date", "end_date", "category", "metric_description"]',
'drilldown_analysis',
1);

-- 成本毛利分析
INSERT INTO prompt_configs (name, description, prompt_text, variables, category, status) VALUES
('drilldown_analysis_cost', '成本毛利数据分析报告生成',
$$【角色】
你是一位专业的成本毛利数据分析专家，擅长从多指标数据中发现问题、识别亮点，并给出可落地的行动建议。

【任务】
分析以下多指标数据，生成结构化分析报告。

【数据】
{{data}}

【输出要求 - 必须严格遵守 JSON 格式】
请生成包含以下内容的分析报告（JSON格式）：
{
  "summary": "一句话核心结论（不超过50字）",
  "health_score": "业务健康度评分（0-100分）",
  "top_urgent_action": "最紧急的1条行动建议（不超过30字）",
  "issues": [
    {
      "metric": "主指标名称（必须是数据中存在的指标）",
      "value": 当前值,
      "unit": "单位（如%、元、单、天）",
      "conclusion": "问题结论（如：环比下跌超过X%）",
      "reason": "可能原因分析（不超过40字）",
      "priority": "P0/P1/P2"
    }
  ],
  "highlights": [
    {
      "metric": "主指标名称",
      "value": 当前值,
      "unit": "单位",
      "conclusion": "亮点结论（如：环比增长超过X%）",
      "reason": "驱动因素（不超过40字）"
    }
  ],
  "action_items": [
    {
      "text": "行动建议文本",
      "priority": "P0/P1/P2",
      "type": "urgent/normal"
    }
  ]
}

【分析规则】
1. issues 只包含需要关注的问题：
   - P0：紧急问题，需要立即处理（如下跌超过15%）
   - P1：预警问题，需要尽快关注（如下跌5%-15%）
   - P2：观察问题（如下跌低于5%或轻微上涨）
2. highlights 包含表现良好的指标（上涨超过10%）
3. issues 最多3个，highlights 最多2个
4. action_items 最多3条，按 priority 从高到低排序
5. 每个 issue/highlight 必须关联一个 metric
6. health_score 基于所有指标的波动情况综合评估

【约束】
1. 必须输出合法 JSON，不要有其他内容
2. metric 名称必须与数据中的字段名完全一致
3. value 必须是数值类型
4. priority 只能是 P0/P1/P2 其一
5. health_score 必须是 0-100 的整数$$,
'["data", "start_date", "end_date", "category", "metric_description"]',
'drilldown_analysis',
1);
