-- 更新成本毛利下钻 SQL 模板 (ID=16)
UPDATE sql_templates SET
  sql_template = $$WITH base_data AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS "销售额",
    SUM(COSTFEESS) AS "成本",
    SUM(PROFITBEFORETAX) AS "税前利润",
    SUM(PLATFORM_CONTRIBUTION) AS "平台贡献",
    SUM(FPLATFORMSERVICEFEE) AS "平台服务费",
    SUM(FPROMOTIOFEE) AS "促销费",
    SUM(TRANSPORTATION) AS "运费",
    SUM(TARIFFSFEE_HANDLE) AS "关税"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= ''{start_date}'' AND FDATE <= ''{end_date}''
),
mom AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS "销售额_mom",
    SUM(PROFITBEFORETAX) AS "利润_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS "销售额_yoy",
    SUM(PROFITBEFORETAX) AS "利润_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 YEAR)
)
SELECT
  b."销售额",
  b."成本",
  b."税前利润",
  b."平台贡献",
  b."平台服务费",
  b."促销费",
  b."运费",
  b."关税",
  ROUND((b."销售额" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."税前利润" - COALESCE(m."利润_mom", 0)) / NULLIF(COALESCE(m."利润_mom", 0), 0) * 100, 2) AS "利润_mom_rate",
  ROUND((b."销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."税前利润" - COALESCE(y."利润_yoy", 0)) / NULLIF(COALESCE(y."利润_yoy", 0), 0) * 100, 2) AS "利润_yoy_rate"
FROM base_data b, mom m, yoy y$$,
  metric_names = '["销售额", "成本", "税前利润", "平台贡献", "平台服务费", "促销费", "运费", "关税", "销售额_mom_rate", "利润_mom_rate", "销售额_yoy_rate", "利润_yoy_rate"]'::jsonb
WHERE id = 16;
