-- =====================================================
-- 四类下钻分析 SQL 模板配置
-- 每个模板返回单行数据，列名 = 指标名，供 LLM 分析
-- 使用 {start_date} / {end_date} 占位符
-- =====================================================

-- =====================================================
-- 销售经营分析 (sales)
-- 核心指标：销售额、订单量、客单价、退款额、退款率、GMV
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '销售经营-基础指标',
  '销售经营分析基础指标（本期值 + 环比 + 同比）',
$$WITH base_data AS (
  SELECT
    SUM(FDAMOUNT)                               AS "销售额",
    SUM(FQUANTITY)                               AS "订单量",
    SUM(FQUANTITY_B2C)                          AS "B2C订单量",
    SUM(FQUANTITY_B2B)                           AS "B2B订单量",
    SUM(FQUANTITY_COD)                           AS "COD订单量",
    SUM(FRETURNAMOUNT)                           AS "退款额",
    SUM(FRETURNQUANTITY)                          AS "退款量",
    SUM(FGMV)                                    AS "GMV",
    SUM(FDAMOUNT) / NULLIF(SUM(FQUANTITY), 0)    AS "客单价",
    SUM(FRETURNAMOUNT) / NULLIF(SUM(FDAMOUNT), 0) * 100 AS "退款率",
    SUM(FQUANTITY_B2C) / NULLIF(SUM(FQUANTITY), 0) * 100 AS "B2C占比"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(FDAMOUNT)                               AS "销售额_mom",
    SUM(FQUANTITY)                              AS "订单量_mom",
    SUM(FGMV)                                   AS "GMV_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(FDAMOUNT)                               AS "销售额_yoy",
    SUM(FQUANTITY)                              AS "订单量_yoy",
    SUM(FGMV)                                   AS "GMV_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b."销售额",
  b."订单量",
  b."B2C订单量",
  b."B2B订单量",
  b."COD订单量",
  b."退款额",
  b."退款量",
  b."GMV",
  b."客单价",
  b."退款率",
  b."B2C占比",
  ROUND((b."销售额" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."订单量" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate",
  ROUND((b."GMV" - COALESCE(m."GMV_mom", 0)) / NULLIF(COALESCE(m."GMV_mom", 0), 0) * 100, 2) AS "GMV_mom_rate",
  ROUND((b."销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."订单量" - COALESCE(y."订单量_yoy", 0)) / NULLIF(COALESCE(y."订单量_yoy", 0), 0) * 100, 2) AS "订单量_yoy_rate"
FROM base_data b, mom_data m, yoy_data y$$,
'drilldown',
1,
'sales',
'["销售额", "订单量", "B2C订单量", "B2B订单量", "COD订单量", "退款额", "退款量", "GMV", "客单价", "退款率", "B2C占比", "销售额_mom_rate", "订单量_mom_rate", "GMV_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"]'::jsonb,
'drilldown',
1,
'基础指标'
);

-- =====================================================
-- 广告投放分析 (ad)
-- 核心指标：广告花费、广告GMV、广告ROI、点击率、转化率、ACOS
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '广告投放-基础指标',
  '广告投放分析基础指标（花费 + 产出 + 效率）',
$$WITH base_data AS (
  SELECT
    SUM(FADSpend)                               AS "广告花费",
    SUM(FADGMV)                                AS "广告GMV",
    SUM(FADQUANTITY)                            AS "广告订单量",
    SUM(FADCLICK)                               AS "广告点击数",
    SUM(FADSHOW)                                AS "广告展示数",
    SUM(FQUANTITY)                              AS "总订单量",
    SUM(FDAMOUNT)                              AS "总销售额",
    SUM(FADGMV) / NULLIF(SUM(FADSpend), 0)    AS "广告ROI",
    SUM(FADCLICK) / NULLIF(SUM(FADSHOW), 0) * 100 AS "点击率",
    SUM(FADQUANTITY) / NULLIF(SUM(FADCLICK), 0) * 100 AS "点击转化率",
    SUM(FADSpend) / NULLIF(SUM(FADGMV), 0) * 100    AS "ACOS",
    SUM(FADGMV) / NULLIF(SUM(FDAMOUNT), 0) * 100    AS "广告销售占比"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(FADSpend)                               AS "广告花费_mom",
    SUM(FADGMV)                                AS "广告GMV_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(FADSpend)                               AS "广告花费_yoy",
    SUM(FADGMV)                                AS "广告GMV_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b."广告花费",
  b."广告GMV",
  b."广告订单量",
  b."广告点击数",
  b."广告展示数",
  b."总订单量",
  b."总销售额",
  b."广告ROI",
  b."点击率",
  b."点击转化率",
  b."ACOS",
  b."广告销售占比",
  ROUND((b."广告花费" - COALESCE(m."广告花费_mom", 0)) / NULLIF(COALESCE(m."广告花费_mom", 0), 0) * 100, 2) AS "广告花费_mom_rate",
  ROUND((b."广告GMV" - COALESCE(m."广告GMV_mom", 0)) / NULLIF(COALESCE(m."广告GMV_mom", 0), 0) * 100, 2) AS "广告GMV_mom_rate",
  ROUND((b."广告花费" - COALESCE(y."广告花费_yoy", 0)) / NULLIF(COALESCE(y."广告花费_yoy", 0), 0) * 100, 2) AS "广告花费_yoy_rate",
  ROUND((b."广告GMV" - COALESCE(y."广告GMV_yoy", 0)) / NULLIF(COALESCE(y."广告GMV_yoy", 0), 0) * 100, 2) AS "广告GMV_yoy_rate"
FROM base_data b, mom_data m, yoy_data y$$,
'drilldown',
1,
'ad',
'["广告花费", "广告GMV", "广告订单量", "广告点击数", "广告展示数", "总订单量", "总销售额", "广告ROI", "点击率", "点击转化率", "ACOS", "广告销售占比", "广告花费_mom_rate", "广告GMV_mom_rate", "广告花费_yoy_rate", "广告GMV_yoy_rate"]'::jsonb,
'drilldown',
1,
'基础指标'
);

-- =====================================================
-- 库存供应链分析 (inventory)
-- 核心指标：库存量、库存周转天数、在途库存、滞销库存、缺货率
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '库存供应链-基础指标',
  '库存供应链分析基础指标（库存 + 周转 + 风险）',
$$WITH base_data AS (
  SELECT
    SUM(FSALABLEQUANTITY)                       AS "可售库存量",
    SUM(FONWAYQUANTITY)                         AS "在途库存量",
    SUM(FINVQUANTITY)                           AS "总库存量",
    SUM(FSTOCKOUTDAYS) / NULLIF(COUNT(DISTINCT FDATE), 0) AS "平均缺货天数",
    SUM(FDEADSTOCKQUANTITY)                     AS "滞销库存量",
    SUM(FDEADSTOCKAMOUNT)                       AS "滞销库存金额",
    SUM(FSTOCKOUTDAYS)                          AS "缺货天数",
    SUM(FREPLENISHMENTLEADTIME) / NULLIF(COUNT(DISTINCT FDATE), 0) AS "平均补货周期",
    SUM(FINVENTORYTURNS) / NULLIF(COUNT(DISTINCT FDATE), 0) AS "库存周转率",
    SUM(FINVENTORYVALUE)                        AS "库存金额",
    SUM(FDEADSTOCKQUANTITY) / NULLIF(SUM(FSALABLEQUANTITY), 0) * 100 AS "滞销占比"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(FSALABLEQUANTITY)                       AS "可售库存量_mom",
    SUM(FINVENTORYTURNS) / NULLIF(COUNT(DISTINCT FDATE), 0) AS "库存周转率_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(FSALABLEQUANTITY)                       AS "可售库存量_yoy",
    SUM(FINVENTORYVALUE)                        AS "库存金额_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b."可售库存量",
  b."在途库存量",
  b."总库存量",
  b."平均缺货天数",
  b."滞销库存量",
  b."滞销库存金额",
  b."缺货天数",
  b."平均补货周期",
  b."库存周转率",
  b."库存金额",
  b."滞销占比",
  ROUND((b."可售库存量" - COALESCE(m."可售库存量_mom", 0)) / NULLIF(COALESCE(m."可售库存量_mom", 0), 0) * 100, 2) AS "可售库存量_mom_rate",
  ROUND((b."库存周转率" - COALESCE(m."库存周转率_mom", 0)), 2) AS "库存周转率_mom",
  ROUND((b."可售库存量" - COALESCE(y."可售库存量_yoy", 0)) / NULLIF(COALESCE(y."可售库存量_yoy", 0), 0) * 100, 2) AS "可售库存量_yoy_rate"
FROM base_data b, mom_data m, yoy_data y$$,
'drilldown',
1,
'inventory',
'["可售库存量", "在途库存量", "总库存量", "平均缺货天数", "滞销库存量", "滞销库存金额", "缺货天数", "平均补货周期", "库存周转率", "库存金额", "滞销占比", "可售库存量_mom_rate", "库存周转率_mom", "可售库存量_yoy_rate"]'::jsonb,
'drilldown',
1,
'基础指标'
);

-- =====================================================
-- 成本毛利分析 (cost)
-- 核心指标：毛利率、平台费、配送费、毛利、成本、边际贡献
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '成本毛利-基础指标',
  '成本毛利分析基础指标（收入 + 成本 + 利润）',
$$WITH base_data AS (
  SELECT
    SUM(FDAMOUNT)                               AS "销售额",
    SUM(FCOST)                                 AS "成本",
    SUM(FPROFIT)                               AS "毛利",
    SUM(FPLATFORMFEE)                          AS "平台费",
    SUM(FFULFILLMENTFEE)                       AS "配送费",
    SUM(FADSPEND)                              AS "广告费",
    SUM(FOTHERFEE)                             AS "其他费用",
    SUM(FPROFIT) / NULLIF(SUM(FDAMOUNT), 0) * 100     AS "毛利率",
    SUM(FPROFIT) / NULLIF(SUM(FCOST), 0) * 100        AS "成本利润率",
    SUM(FPROFIT) - SUM(FADSPEND)                       AS "扣除广告后毛利",
    (SUM(FPROFIT) - SUM(FADSPEND)) / NULLIF(SUM(FDAMOUNT), 0) * 100 AS "广告后毛利率",
    SUM(FPLATFORMFEE) / NULLIF(SUM(FDAMOUNT), 0) * 100     AS "平台费率",
    SUM(FFULFILLMENTFEE) / NULLIF(SUM(FDAMOUNT), 0) * 100   AS "配送费率",
    SUM(FPLATFORMFEE) + SUM(FFULFILLMENTFEE) + SUM(FADSPEND) AS "总费用"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(FDAMOUNT)                               AS "销售额_mom",
    SUM(FPROFIT)                               AS "毛利_mom",
    SUM(FPROFIT) / NULLIF(SUM(FDAMOUNT), 0) * 100     AS "毛利率_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(FDAMOUNT)                               AS "销售额_yoy",
    SUM(FPROFIT)                               AS "毛利_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b."销售额",
  b."成本",
  b."毛利",
  b."平台费",
  b."配送费",
  b."广告费",
  b."其他费用",
  b."毛利率",
  b."成本利润率",
  b."扣除广告后毛利",
  b."广告后毛利率",
  b."平台费率",
  b."配送费率",
  b."总费用",
  ROUND((b."销售额" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."毛利" - COALESCE(m."毛利_mom", 0)) / NULLIF(COALESCE(m."毛利_mom", 0), 0) * 100, 2) AS "毛利_mom_rate",
  ROUND((b."毛利率" - COALESCE(m."毛利率_mom", 0)), 2) AS "毛利率_mom",
  ROUND((b."销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."毛利" - COALESCE(y."毛利_yoy", 0)) / NULLIF(COALESCE(y."毛利_yoy", 0), 0) * 100, 2) AS "毛利_yoy_rate"
FROM base_data b, mom_data m, yoy_data y$$,
'drilldown',
1,
'cost',
'["销售额", "成本", "毛利", "平台费", "配送费", "广告费", "其他费用", "毛利率", "成本利润率", "扣除广告后毛利", "广告后毛利率", "平台费率", "配送费率", "总费用", "销售额_mom_rate", "毛利_mom_rate", "毛利率_mom", "销售额_yoy_rate", "毛利_yoy_rate"]'::jsonb,
'drilldown',
1,
'基础指标'
);
