-- 更新销售下钻 SQL 模板 (ID=13)
UPDATE sql_templates SET
  sql_template = $$WITH base_data AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS "销售额",
    SUM(TOTALORDERS) AS "总订单数",
    SUM(UNITS_ORDERED) AS "订单量",
    SUM(UNITS_ORDEREDB2B) AS "B2B订单量",
    SUM(totalunits) AS "总销量",
    SUM(UNITS_REFUNDED) AS "退款量",
    SUM(INCOME_BCSS) AS "国内收入",
    SUM(INCOME_BC_TK) AS "跨境收入"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= ''{start_date}'' AND FDATE <= ''{end_date}''
),
mom AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS "销售额_mom",
    SUM(UNITS_ORDERED) AS "订单量_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS "销售额_yoy",
    SUM(UNITS_ORDERED) AS "订单量_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 YEAR)
)
SELECT
  b."销售额",
  b."总订单数",
  b."订单量",
  b."B2B订单量",
  b."总销量",
  b."退款量",
  b."国内收入",
  b."跨境收入",
  ROUND((b."销售额" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."订单量" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate",
  ROUND((b."销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."订单量" - COALESCE(y."订单量_yoy", 0)) / NULLIF(COALESCE(y."订单量_yoy", 0), 0) * 100, 2) AS "订单量_yoy_rate"
FROM base_data b, mom m, yoy y$$,
  metric_names = '["销售额", "总订单数", "订单量", "B2B订单量", "总销量", "退款量", "国内收入", "跨境收入", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"]'::jsonb
WHERE id = 13;
