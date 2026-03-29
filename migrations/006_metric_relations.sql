-- 指标关系表（存储指标间的因果/相关关系）
-- 用于 Neo4j 图数据库的关??
CREATE TABLE metric_relations (
    id SERIAL PRIMARY KEY,
    source_metric_code VARCHAR(64) NOT NULL,
    target_metric_code VARCHAR(64) NOT NULL,
    relation_type VARCHAR(32) NOT NULL,
    weight DECIMAL(3,2) DEFAULT 1.0,
    description TEXT,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_source_metric FOREIGN KEY (source_metric_code) REFERENCES metrics(metric_code),
    CONSTRAINT fk_target_metric FOREIGN KEY (target_metric_code) REFERENCES metrics(metric_code),
    CONSTRAINT uq_metric_relation UNIQUE (source_metric_code, target_metric_code, relation_type)
);

-- 关系类型说明：
-- derives_from: A 由 B 推导而出（如：转化率 derives_from 点击量）
-- impacts: A 影响 B（如：广告投放 impacts 曝光量）
-- correlates_with: A 与 B 相关（如：转化率 correlates_with 复购率）

-- 创建索引加速查询
CREATE INDEX idx_relations_source ON metric_relations(source_metric_code);
CREATE INDEX idx_relations_target ON metric_relations(target_metric_code);
CREATE INDEX idx_relations_type ON metric_relations(relation_type);
