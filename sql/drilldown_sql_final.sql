-- 四类下钻SQL模板 (由脚本自动生成)
-- 表: ids.IDS_AMZ_COMPREHENSIVE_DI
-- 生成时间: 2026-04-26

-- =====================================================
-- 销售经营 (sales)
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '销售经营-基础指标',
  '销售经营分析基础指标（销售额 + 订单量 + 收入）',
'$$WITH base_data AS (
  SELECT
    SUM(INCOME_BCSS) AS "INCOME_BCSS"
    SUM(INCOME_BC_TK) AS "INCOME_BC_TK"
    SUM(INCOME_NBCSS) AS "INCOME_NBCSS"
    SUM(ORDERED_PRODUCTSALES) AS "ORDERED_PRODUCTSALES"
    SUM(ORDERED_PRODUCTSALESB2B) AS "ORDERED_PRODUCTSALESB2B"
    SUM(TOTALORDERS) AS "TOTALORDERS"
    SUM(TOTALSALES) AS "TOTALSALES"
    SUM(TOTALUNITS) AS "TOTALUNITS"
    SUM(TOTAL_ORDERITEMS) AS "TOTAL_ORDERITEMS"
    SUM(TOTAL_ORDERITEMSB2B) AS "TOTAL_ORDERITEMSB2B"
    SUM(UNITS_ORDERED) AS "UNITS_ORDERED"
    SUM(UNITS_ORDEREDB2B) AS "UNITS_ORDEREDB2B"
    SUM(UNITS_REFUNDED) AS "UNITS_REFUNDED"
    SUM(UNITS_REFUNDED_B2B) AS "UNITS_REFUNDED_B2B"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_mom",
    SUM(UNITS_ORDERED) AS "订单量_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
    SUM(UNITS_ORDERED) AS "订单量_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b.*,
  ROUND((b."TOTALSALES" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."TOTALSALES" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."UNITS_ORDERED" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate"
FROM base_data b, mom_data m, yoy_data y$$',
  'drilldown',
  1,
  'sales',
  '["INCOME_BCSS", "INCOME_BC_TK", "INCOME_NBCSS", "ORDERED_PRODUCTSALES", "ORDERED_PRODUCTSALESB2B", "TOTALORDERS", "TOTALSALES", "TOTALUNITS", "TOTAL_ORDERITEMS", "TOTAL_ORDERITEMSB2B", "UNITS_ORDERED", "UNITS_ORDEREDB2B", "UNITS_REFUNDED", "UNITS_REFUNDED_B2B"]'::jsonb,
  'drilldown',
  1,
  '基础指标'
);


-- =====================================================
-- 广告投放 (ad)
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '广告投放-基础指标',
  '广告投放分析基础指标（花费 + 流量 + 转化）',
'$$WITH base_data AS (
  SELECT
    SUM(CLICKS) AS "CLICKS"
    SUM(FEATUREDOFFER_BUYBOX_PERCENTAGE) AS "FEATUREDOFFER_BUYBOX_PERCENTAGE"
    SUM(IMPRESSIONS) AS "IMPRESSIONS"
    SUM(PAGEVIEWS_BROWSER) AS "PAGEVIEWS_BROWSER"
    SUM(PAGEVIEWS_BROWSER_B2B) AS "PAGEVIEWS_BROWSER_B2B"
    SUM(PAGEVIEWS_MOBILEAPP) AS "PAGEVIEWS_MOBILEAPP"
    SUM(PAGEVIEWS_MOBILEAPP_B2B) AS "PAGEVIEWS_MOBILEAPP_B2B"
    SUM(PAGEVIEWS_TOTAL) AS "PAGEVIEWS_TOTAL"
    SUM(PAGEVIEWS_TOTAL_B2B) AS "PAGEVIEWS_TOTAL_B2B"
    SUM(SESSIONS_BROWSER) AS "SESSIONS_BROWSER"
    SUM(SESSIONS_BROWSER_B2B) AS "SESSIONS_BROWSER_B2B"
    SUM(SESSIONS_MOBILEAPP) AS "SESSIONS_MOBILEAPP"
    SUM(SESSIONS_MOBILEAPP_B2B) AS "SESSIONS_MOBILEAPP_B2B"
    SUM(SESSIONS_TOTAL) AS "SESSIONS_TOTAL"
    SUM(SESSIONS_TOTAL_B2B) AS "SESSIONS_TOTAL_B2B"
    SUM(SPEND) AS "SPEND"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_mom",
    SUM(UNITS_ORDERED) AS "订单量_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
    SUM(UNITS_ORDERED) AS "订单量_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b.*,
  ROUND((b."TOTALSALES" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."TOTALSALES" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."UNITS_ORDERED" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate"
FROM base_data b, mom_data m, yoy_data y$$',
  'drilldown',
  1,
  'ad',
  '["CLICKS", "FEATUREDOFFER_BUYBOX_PERCENTAGE", "IMPRESSIONS", "PAGEVIEWS_BROWSER", "PAGEVIEWS_BROWSER_B2B", "PAGEVIEWS_MOBILEAPP", "PAGEVIEWS_MOBILEAPP_B2B", "PAGEVIEWS_TOTAL", "PAGEVIEWS_TOTAL_B2B", "SESSIONS_BROWSER", "SESSIONS_BROWSER_B2B", "SESSIONS_MOBILEAPP", "SESSIONS_MOBILEAPP_B2B", "SESSIONS_TOTAL", "SESSIONS_TOTAL_B2B", "SPEND"]'::jsonb,
  'drilldown',
  1,
  '基础指标'
);


-- =====================================================
-- 成本毛利 (cost)
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '成本毛利-基础指标',
  '成本毛利分析基础指标（成本 + 费用 + 利润）',
'$$WITH base_data AS (
  SELECT
    SUM(AFTERSALESFEE) AS "AFTERSALESFEE"
    SUM(CHEMICALFEE) AS "CHEMICALFEE"
    SUM(CONSULTINGFEE) AS "CONSULTINGFEE"
    SUM(COSTFEESS) AS "COSTFEESS"
    SUM(DSP) AS "DSP"
    SUM(FFBAFEE) AS "FFBAFEE"
    SUM(FGIFTWRAPCREDITS) AS "FGIFTWRAPCREDITS"
    SUM(FPLATFORMSERVICEFEE) AS "FPLATFORMSERVICEFEE"
    SUM(FPROMOTIOFEE) AS "FPROMOTIOFEE"
    SUM(FSELLINGFEE) AS "FSELLINGFEE"
    SUM(IMPORTFEE) AS "IMPORTFEE"
    SUM(INCOMETAXFEE) AS "INCOMETAXFEE"
    SUM(MEDIAFEE) AS "MEDIAFEE"
    SUM(PACKINGFEE) AS "PACKINGFEE"
    SUM(PLATFORM_CONTRIBUTION) AS "PLATFORM_CONTRIBUTION"
    SUM(PROFITBEFORETAX) AS "PROFITBEFORETAX"
    SUM(REFUSEFEE) AS "REFUSEFEE"
    SUM(SAMPLEFEE) AS "SAMPLEFEE"
    SUM(TARIFFSFEE_HANDLE) AS "TARIFFSFEE_HANDLE"
    SUM(TRANSPORTATION) AS "TRANSPORTATION"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_mom",
    SUM(UNITS_ORDERED) AS "订单量_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
    SUM(UNITS_ORDERED) AS "订单量_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b.*,
  ROUND((b."TOTALSALES" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."TOTALSALES" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."UNITS_ORDERED" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate"
FROM base_data b, mom_data m, yoy_data y$$',
  'drilldown',
  1,
  'cost',
  '["AFTERSALESFEE", "CHEMICALFEE", "CONSULTINGFEE", "COSTFEESS", "DSP", "FFBAFEE", "FGIFTWRAPCREDITS", "FPLATFORMSERVICEFEE", "FPROMOTIOFEE", "FSELLINGFEE", "IMPORTFEE", "INCOMETAXFEE", "MEDIAFEE", "PACKINGFEE", "PLATFORM_CONTRIBUTION", "PROFITBEFORETAX", "REFUSEFEE", "SAMPLEFEE", "TARIFFSFEE_HANDLE", "TRANSPORTATION"]'::jsonb,
  'drilldown',
  1,
  '基础指标'
);


-- =====================================================
-- 库存供应链 (inventory)
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '库存供应链-基础指标',
  '库存供应链分析基础指标（库存 + 周转）',
'$$WITH base_data AS (
  SELECT
    SUM(FINVQUANTITY) AS "FINVQUANTITY"
    SUM(FQTY) AS "FQTY"
    SUM(FQTY_TK) AS "FQTY_TK"
    SUM(FREPLENISHMENT) AS "FREPLENISHMENT"
    SUM(FSALABLEQUANTITY) AS "FSALABLEQUANTITY"
    SUM(WHCOST) AS "WHCOST"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'
),
mom_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_mom",
    SUM(UNITS_ORDERED) AS "订单量_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
    SUM(UNITS_ORDERED) AS "订单量_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB('{start_date}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{end_date}', INTERVAL 1 YEAR)
)
SELECT
  b.*,
  ROUND((b."TOTALSALES" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."TOTALSALES" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."UNITS_ORDERED" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate"
FROM base_data b, mom_data m, yoy_data y$$',
  'drilldown',
  1,
  'inventory',
  '["FINVQUANTITY", "FQTY", "FQTY_TK", "FREPLENISHMENT", "FSALABLEQUANTITY", "WHCOST"]'::jsonb,
  'drilldown',
  1,
  '基础指标'
);


