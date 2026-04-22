-- 槽位追问配置表迁移脚本
-- 创建时间: 2026-04-15

-- 1. slot_definitions 槽位定义表
CREATE TABLE IF NOT EXISTS slot_definitions (
    id              SERIAL PRIMARY KEY,
    slot_name       VARCHAR(64) NOT NULL UNIQUE,
    slot_type       VARCHAR(32) NOT NULL,
    display_name    VARCHAR(128),
    priority        INT DEFAULT 0,
    max_clarify_turns INT DEFAULT 3,
    default_value   VARCHAR(256),
    value_type      VARCHAR(32),
    allowed_values  TEXT,
    value_mapping   TEXT,
    question_templates TEXT,
    dynamic_source  VARCHAR(64),
    dimension_name  VARCHAR(64),
    column_name     VARCHAR(64),
    status          SMALLINT DEFAULT 1,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- 2. slot_dependencies 槽位依赖表
CREATE TABLE IF NOT EXISTS slot_dependencies (
    id              SERIAL PRIMARY KEY,
    parent_slot     VARCHAR(64),
    child_slot      VARCHAR(64),
    condition_expr  TEXT,
    status          SMALLINT DEFAULT 1,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 3. slot_relations 指标-槽位关联表
CREATE TABLE IF NOT EXISTS slot_relations (
    id              SERIAL PRIMARY KEY,
    metric_category VARCHAR(64),
    slot_name       VARCHAR(64) NOT NULL,
    slot_required   SMALLINT DEFAULT 0,
    default_value   VARCHAR(256),
    status          SMALLINT DEFAULT 1,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 4. 初始化跨境电商场景的槽位数据

-- time_range 槽位（静态）
INSERT INTO slot_definitions (slot_name, slot_type, display_name, priority, value_type, allowed_values, question_templates, status)
VALUES ('time_range', 'required', '时间范围', 90, 'static', '["昨天","近7天","近30天","本月","上月","去年同期"]', '["请问想查询哪个时间段？"]', 1)
ON CONFLICT (slot_name) DO NOTHING;

-- ad_type 槽位（静态）
INSERT INTO slot_definitions (slot_name, slot_type, display_name, priority, value_type, allowed_values, question_templates, status)
VALUES ('ad_type', 'optional', '广告类型', 50, 'static', '["SP","SC","SB","SD"]', '["请问想查询哪种广告类型？"]', 1)
ON CONFLICT (slot_name) DO NOTHING;

-- logistics 槽位（静态）
INSERT INTO slot_definitions (slot_name, slot_type, display_name, priority, value_type, allowed_values, question_templates, status)
VALUES ('logistics', 'optional', '物流方式', 40, 'static', '["FBA","FBM","海外仓"]', '["请问想查询哪种物流？"]', 1)
ON CONFLICT (slot_name) DO NOTHING;

-- caliber 槽位（静态）
INSERT INTO slot_definitions (slot_name, slot_type, display_name, priority, value_type, allowed_values, question_templates, status)
VALUES ('caliber', 'optional', '数据口径', 30, 'static', '["含广告费","不含广告费","毛利润","净利润"]', '["请问用哪种口径？"]', 1)
ON CONFLICT (slot_name) DO NOTHING;

-- metric 槽位（动态，从metrics表按category分类）
INSERT INTO slot_definitions (slot_name, slot_type, display_name, priority, value_type, dynamic_source, question_templates, status)
VALUES ('metric', 'required', '指标', 100, 'dynamic', 'metric_category', '["请问想查询哪个指标？"]', 1)
ON CONFLICT (slot_name) DO NOTHING;

-- platform 槽位（动态，从dimension_configs表）
INSERT INTO slot_definitions (slot_name, slot_type, display_name, priority, value_type, dynamic_source, dimension_name, question_templates, status)
VALUES ('platform', 'required', '平台', 80, 'dynamic', 'dimension_config', '平台', '["请问想查询哪个平台？","是亚马逊、TikTok还是Temu呢？"]', 1)
ON CONFLICT (slot_name) DO NOTHING;

-- site 槽位（动态，从dimension_configs表）
INSERT INTO slot_definitions (slot_name, slot_type, display_name, priority, value_type, dynamic_source, dimension_name, question_templates, status)
VALUES ('site', 'conditional', '站点', 70, 'dynamic', 'dimension_config', '站点', '["请问想查询哪个站点？"]', 1)
ON CONFLICT (slot_name) DO NOTHING;

-- entity 槽位（动态，从dimension_configs表）
INSERT INTO slot_definitions (slot_name, slot_type, display_name, priority, value_type, dynamic_source, dimension_name, question_templates, status)
VALUES ('entity', 'required', '主体维度', 60, 'dynamic', 'dimension_config', '品类', '["请问想查询哪个维度？"]', 1)
ON CONFLICT (slot_name) DO NOTHING;
