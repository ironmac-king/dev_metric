-- =====================================================
-- 四类下钻分析 SQL 模板配置 V2（基于实际字段名）
-- 表：ids.IDS_AMZ_COMPREHENSIVE_DI
-- 时间列：FDATE
-- 使用 {start_date} / {end_date} 占位符
-- =====================================================

-- =====================================================
-- 销售经营分析 (sales)
-- 核心指标：销售额、订单量、客单价、退款额、退款率
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '销售经营-基础指标',
  '销售经营分析基础指标（本期值 + 环比 + 同比）',
$$WITH base_data AS (
  SELECT
    SUM(TOTALSALES)                                    AS "销售额",
    SUM(UNITS_ORDERED)                                 AS "订单量",
    SUM(TOTALORDERS)                                   AS "总订单数",
    SUM(UNITS_REFUNDED)                                AS "退款量",
    SUM(INCOME_BCSS)                                   AS "收入",
    SUM(TOTALSALES) / NULLIF(SUM(UNITS_ORDERED), 0)  AS "客单价",
    SUM(UNITS_REFUNDED) / NULLIF(SUM(UNITS_ORDERED), 0) * 100 AS "退款率"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(TOTALSALES)     AS "销售额_mom",
    SUM(UNITS_ORDERED)  AS "订单量_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES)     AS "销售额_yoy",
    SUM(UNITS_ORDERED)  AS "订单量_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b."销售额",
  b."订单量",
  b."总订单数",
  b."退款量",
  b."收入",
  b."客单价",
  b."退款率",
  ROUND((b."销售额" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."订单量" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate",
  ROUND((b."销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."订单量" - COALESCE(y."订单量_yoy", 0)) / NULLIF(COALESCE(y."订单量_yoy", 0), 0) * 100, 2) AS "订单量_yoy_rate"
FROM base_data b, mom_data m, yoy_data y$$,
'drilldown',
1,
'sales',
'["销售额", "订单量", "总订单数", "退款量", "收入", "客单价", "退款率", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"]'::jsonb,
'drilldown',
1,
'基础指标'
);

-- =====================================================
-- 广告投放分析 (ad)
-- 核心指标：广告花费、点击、转化、展示
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '广告投放-基础指标',
  '广告投放分析基础指标（花费 + 产出 + 效率）',
$$WITH base_data AS (
  SELECT
    SUM(SPEND)                                      AS "广告花费",
    SUM(CLICKS)                                     AS "广告点击数",
    SUM(IMPRESSIONS)                                AS "广告展示数",
    SUM(UNITS_ORDERED)                              AS "总订单量",
    SUM(TOTALSALES)                                 AS "总销售额",
    SUM(CLICKS) / NULLIF(SUM(IMPRESSIONS), 0) * 100    AS "点击率",
    SUM(UNITS_ORDERED) / NULLIF(SUM(CLICKS), 0) * 100  AS "点击转化率",
    SUM(TOTALSALES) / NULLIF(SUM(SPEND), 0)             AS "广告ROI",
    SUM(SPEND) / NULLIF(SUM(TOTALSALES), 0) * 100      AS "广告销售占比"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(SPEND)        AS "广告花费_mom",
    SUM(TOTALSALES)  AS "广告销售额_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(SPEND)        AS "广告花费_yoy",
    SUM(TOTALSALES)  AS "广告销售额_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b."广告花费",
  b."广告点击数",
  b."广告展示数",
  b."总订单量",
  b."总销售额",
  b."点击率",
  b."点击转化率",
  b."广告ROI",
  b."广告销售占比",
  ROUND((b."广告花费" - COALESCE(m."广告花费_mom", 0)) / NULLIF(COALESCE(m."广告花费_mom", 0), 0) * 100, 2) AS "广告花费_mom_rate",
  ROUND((b."广告花费" - COALESCE(y."广告花费_yoy", 0)) / NULLIF(COALESCE(y."广告花费_yoy", 0), 0) * 100, 2) AS "广告花费_yoy_rate"
FROM base_data b, mom_data m, yoy_data y$$,
'drilldown',
1,
'ad',
'["广告花费", "广告点击数", "广告展示数", "总订单量", "总销售额", "点击率", "点击转化率", "广告ROI", "广告销售占比", "广告花费_mom_rate", "广告花费_yoy_rate"]'::jsonb,
'drilldown',
1,
'基础指标'
);

-- =====================================================
-- 成本毛利分析 (cost)
-- 核心指标：成本、毛利、平台费、利润
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '成本毛利-基础指标',
  '成本毛利分析基础指标（收入 + 成本 + 利润）',
$$WITH base_data AS (
  SELECT
    SUM(TOTALSALES)                                 AS "销售额",
    SUM(COSTFEESS)                                 AS "成本",
    SUM(PROFITBEFORETAX)                           AS "税前利润",
    SUM(PLATFORM_CONTRIBUTION)                      AS "平台贡献",
    SUM(FPLATFORMSERVICEFEE)                       AS "平台服务费",
    SUM(FPROMOTIOFEE)                              AS "促销费",
    SUM(TRANSPORTATION)                            AS "运费",
    SUM(PROFITBEFORETAX) / NULLIF(SUM(TOTALSALES), 0) * 100        AS "利润率",
    SUM(COSTFEESS) / NULLIF(SUM(TOTALSALES), 0) * 100               AS "成本率",
    SUM(FPLATFORMSERVICEFEE) / NULLIF(SUM(TOTALSALES), 0) * 100    AS "平台费率"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(TOTALSALES)         AS "销售额_mom",
    SUM(COSTFEESS)         AS "成本_mom",
    SUM(PROFITBEFORETAX)   AS "利润_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES)         AS "销售额_yoy",
    SUM(PROFITBEFORETAX)   AS "利润_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b."销售额",
  b."成本",
  b."税前利润",
  b."平台贡献",
  b."平台服务费",
  b."促销费",
  b."运费",
  b."利润率",
  b."成本率",
  b."平台费率",
  ROUND((b."销售额" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."税前利润" - COALESCE(m."利润_mom", 0)) / NULLIF(COALESCE(m."利润_mom", 0), 0) * 100, 2) AS "利润_mom_rate",
  ROUND((b."利润率" - COALESCE(m."成本_mom", 0)), 2) AS "利润率_mom",
  ROUND((b."销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."税前利润" - COALESCE(y."利润_yoy", 0)) / NULLIF(COALESCE(y."利润_yoy", 0), 0) * 100, 2) AS "利润_yoy_rate"
FROM base_data b, mom_data m, yoy_data y$$,
'drilldown',
1,
'cost',
'["销售额", "成本", "税前利润", "平台贡献", "平台服务费", "促销费", "运费", "利润率", "成本率", "平台费率", "销售额_mom_rate", "利润_mom_rate", "利润率_mom", "销售额_yoy_rate", "利润_yoy_rate"]'::jsonb,
'drilldown',
1,
'基础指标'
);

-- =====================================================
-- 库存供应链分析 (inventory)
-- 核心指标：库存量、库存周转、仓库成本
-- 注：实际库存字段需根据 StarRocks 表确认，此处用已知字段
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '库存供应链-基础指标',
  '库存供应链分析基础指标（库存 + 周转 + 风险）',
$$WITH base_data AS (
  SELECT
    SUM(TOTALSALES)                                 AS "总销售额",
    SUM(COSTFEESS)                                 AS "总成本",
    SUM(TOTALSALES) / NULLIF(SUM(COSTFEESS), 0)   AS "库存周转率",
    SUM(WHCOST)                                     AS "仓库成本",
    SUM(TOTALORDERS)                                AS "总订单数",
    SUM(UNITS_ORDERED)                              AS "总销售量",
    SUM(UNITS_REFUNDED)                             AS "退货量",
    SUM(UNITS_REFUNDED) / NULLIF(SUM(UNITS_ORDERED), 0) * 100 AS "退货率"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(COSTFEESS)   AS "成本_mom",
    SUM(TOTALORDERS) AS "订单数_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES)  AS "销售额_yoy",
    SUM(COSTFEESS)   AS "成本_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b."总销售额",
  b."总成本",
  b."库存周转率",
  b."仓库成本",
  b."总订单数",
  b."总销售量",
  b."退货量",
  b."退货率",
  ROUND((b."库存周转率" - COALESCE(m."成本_mom", 0)), 2) AS "库存周转率_mom",
  ROUND((b."总订单数" - COALESCE(m."订单数_mom", 0)) / NULLIF(COALESCE(m."订单数_mom", 0), 0) * 100, 2) AS "订单数_mom_rate",
  ROUND((b."总销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate"
FROM base_data b, mom_data m, yoy_data y$$,
'drilldown',
1,
'inventory',
'["总销售额", "总成本", "库存周转率", "仓库成本", "总订单数", "总销售量", "退货量", "退货率", "库存周转率_mom", "订单数_mom_rate", "销售额_yoy_rate"]'::jsonb,
'drilldown',
1,
'基础指标'
);
