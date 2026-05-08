-- 业务术语同义词扩展
-- 为 business_terms 表增加 synonyms 字段，支持同义词配置

-- 添加同义词数组字段
ALTER TABLE business_terms ADD COLUMN IF NOT EXISTS synonyms TEXT[] DEFAULT '{}';

-- 为 synonyms 字段添加注释
COMMENT ON COLUMN business_terms.synonyms IS '同义词列表，如 ["PV", "访问量", "浏览量"]';

-- 示例数据：页面访问量
-- UPDATE business_terms SET synonyms = ARRAY['PV', '访问量', '浏览量'] WHERE term = '页面访问量';
