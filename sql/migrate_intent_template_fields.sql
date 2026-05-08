-- 为 intent_templates 表添加配置化字段
-- 用于支持 ranking/comparison 意图的关键词配置化

-- 添加 dimension_required 字段：是否需要维度词配合
ALTER TABLE intent_templates ADD COLUMN IF NOT EXISTS dimension_required INT DEFAULT 0;

-- 添加 invalid_keywords 字段：泛指关键词，需要追问具体级别
ALTER TABLE intent_templates ADD COLUMN IF NOT EXISTS invalid_keywords TEXT DEFAULT '';

-- 更新现有 ranking 意图模板配置
-- query_ranking: 排名分析
INSERT INTO intent_templates (name, intent, patterns, priority, dimension_required, invalid_keywords, status) VALUES
('直接排名', 'query_ranking', '最高,最低,最好,最差', 15, 0, '', 1)
ON CONFLICT DO NOTHING;

INSERT INTO intent_templates (name, intent, patterns, priority, dimension_required, invalid_keywords, status) VALUES
('维度配合排名', 'query_ranking', '比较好,比较差,比较好', 14, 1, '品类,类目,商品类,产品类', 1)
ON CONFLICT DO NOTHING;

-- query_comparison: 对比分析
INSERT INTO intent_templates (name, intent, patterns, priority, dimension_required, invalid_keywords, status) VALUES
('对比分析', 'query_comparison', '对比,同比,环比,差异', 12, 0, '', 1)
ON CONFLICT DO NOTHING;
