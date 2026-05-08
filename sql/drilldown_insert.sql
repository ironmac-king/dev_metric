-- 销售经营
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES (
  '销售经营-基础指标',
  '销售经营分析基础指标（销售额 + 订单量 + 收入）',
'WITH base_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额",
    SUM(ORDERED_PRODUCTSALES) AS "亚马逊销售额",
    SUM(TOTALORDERS) AS "总订单数",
    SUM(UNITS_ORDERED) AS "订单量",
    SUM(UNITS_ORDEREDB2B) AS "B2B订单量",
    SUM(UNITS_REFUNDED) AS "退款量",
    SUM(INCOME_BCSS) AS "国内收入",
    SUM(INCOME_BC_TK) AS "跨境收入",
    SUM(TOTALUNITS) AS "总销量"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= ''{start_date}'' AND FDATE <= ''{end_date}''
),
mom AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_mom",
    SUM(UNITS_ORDERED) AS "订单量_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
    SUM(UNITS_ORDERED) AS "订单量_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 YEAR)
)
SELECT
  b."销售额",
  b."亚马逊销售额",
  b."总订单数",
  b."订单量",
  b."B2B订单量",
  b."退款量",
  b."国内收入",
  b."跨境收入",
  b."总销量",
  ROUND((b."销售额" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."订单量" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate",
  ROUND((b."销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."订单量" - COALESCE(y."订单量_yoy", 0)) / NULLIF(COALESCE(y."订单量_yoy", 0), 0) * 100, 2) AS "订单量_yoy_rate"
FROM base_data b, mom m, yoy y',
'drilldown', 1, 'sales',
'["销售额", "亚马逊销售额", "总订单数", "订单量", "B2B订单量", "退款量", "国内收入", "跨境收入", "总销量", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"]'::jsonb,
'drilldown', 1, '基础指标'
);

-- 广告投放
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES (
  '广告投放-基础指标',
  '广告投放分析基础指标（花费 + 流量 + 转化）',
'WITH base_data AS (
  SELECT
    SUM(SPEND) AS "广告花费",
    SUM(IMPRESSIONS) AS "广告展示数",
    SUM(CLICKS) AS "广告点击数",
    SUM(TOTALORDERS) AS "广告订单数",
    SUM(ORDERED_PRODUCTSALES) AS "广告销售额",
    SUM(SESSIONS_TOTAL) AS "总会话数",
    SUM(PAGEVIEWS_TOTAL) AS "总页面浏览量",
    SUM(UNITS_ORDERED) AS "总订单量",
    SUM(CLICKS) / NULLIF(SUM(IMPRESSIONS), 0) * 100 AS "点击率",
    SUM(ORDERED_PRODUCTSALES) / NULLIF(SUM(SPEND), 0) AS "广告ROI",
    SUM(SPEND) / NULLIF(SUM(ORDERED_PRODUCTSALES), 0) * 100 AS "ACOS"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= ''{start_date}'' AND FDATE <= ''{end_date}''
),
mom AS (
  SELECT
    SUM(SPEND) AS "广告花费_mom",
    SUM(ORDERED_PRODUCTSALES) AS "广告销售额_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(SPEND) AS "广告花费_yoy",
    SUM(ORDERED_PRODUCTSALES) AS "广告销售额_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 YEAR)
)
SELECT
  b."广告花费",
  b."广告展示数",
  b."广告点击数",
  b."广告订单数",
  b."广告销售额",
  b."总会话数",
  b."总页面浏览量",
  b."总订单量",
  b."点击率",
  b."广告ROI",
  b."ACOS",
  ROUND((b."广告花费" - COALESCE(m."广告花费_mom", 0)) / NULLIF(COALESCE(m."广告花费_mom", 0), 0) * 100, 2) AS "广告花费_mom_rate",
  ROUND((b."广告销售额" - COALESCE(m."广告销售额_mom", 0)) / NULLIF(COALESCE(m."广告销售额_mom", 0), 0) * 100, 2) AS "广告销售额_mom_rate",
  ROUND((b."广告花费" - COALESCE(y."广告花费_yoy", 0)) / NULLIF(COALESCE(y."广告花费_yoy", 0), 0) * 100, 2) AS "广告花费_yoy_rate",
  ROUND((b."广告销售额" - COALESCE(y."广告销售额_yoy", 0)) / NULLIF(COALESCE(y."广告销售额_yoy", 0), 0) * 100, 2) AS "广告销售额_yoy_rate"
FROM base_data b, mom m, yoy y',
'drilldown', 1, 'ad',
'["广告花费", "广告展示数", "广告点击数", "广告订单数", "广告销售额", "总会话数", "总页面浏览量", "总订单量", "点击率", "广告ROI", "ACOS", "广告花费_mom_rate", "广告销售额_mom_rate", "广告花费_yoy_rate", "广告销售额_yoy_rate"]'::jsonb,
'drilldown', 1, '基础指标'
);

-- 成本毛利
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES (
  '成本毛利-基础指标',
  '成本毛利分析基础指标（成本 + 费用 + 利润）',
'WITH base_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额",
    SUM(COSTFEESS) AS "成本",
    SUM(PROFITBEFORETAX) AS "税前利润",
    SUM(PLATFORM_CONTRIBUTION) AS "平台贡献",
    SUM(FPLATFORMSERVICEFEE) AS "平台服务费",
    SUM(FPROMOTIOFEE) AS "促销费",
    SUM(TRANSPORTATION) AS "运费",
    SUM(TARIFFSFEE_HANDLE) AS "关税",
    SUM(AFTERSALESFEE) AS "售后费",
    SUM(COSTFEESS) / NULLIF(SUM(TOTALSALES), 0) * 100 AS "成本率",
    SUM(PROFITBEFORETAX) / NULLIF(SUM(TOTALSALES), 0) * 100 AS "利润率",
    SUM(PROFITBEFORETAX) / NULLIF(SUM(COSTFEESS), 0) * 100 AS "成本利润率"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= ''{start_date}'' AND FDATE <= ''{end_date}''
),
mom AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_mom",
    SUM(PROFITBEFORETAX) AS "利润_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
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
  b."售后费",
  b."成本率",
  b."利润率",
  b."成本利润率",
  ROUND((b."销售额" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."税前利润" - COALESCE(m."利润_mom", 0)) / NULLIF(COALESCE(m."利润_mom", 0), 0) * 100, 2) AS "利润_mom_rate",
  ROUND((b."利润率" - COALESCE(m."利润_mom", 0)), 2) AS "利润率_mom",
  ROUND((b."销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."税前利润" - COALESCE(y."利润_yoy", 0)) / NULLIF(COALESCE(y."利润_yoy", 0), 0) * 100, 2) AS "利润_yoy_rate"
FROM base_data b, mom m, yoy y',
'drilldown', 1, 'cost',
'["销售额", "成本", "税前利润", "平台贡献", "平台服务费", "促销费", "运费", "关税", "售后费", "成本率", "利润率", "成本利润率", "销售额_mom_rate", "利润_mom_rate", "利润率_mom", "销售额_yoy_rate", "利润_yoy_rate"]'::jsonb,
'drilldown', 1, '基础指标'
);

-- 库存供应链
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES (
  '库存供应链-基础指标',
  '库存供应链分析基础指标（库存 + 周转）',
'WITH base_data AS (
  SELECT
    SUM(WHCOST) AS "仓库成本",
    SUM(FQTY) AS "库存数量",
    SUM(FQTY_TK) AS "在途库存",
    SUM(TOTALSALES) AS "总销售额",
    SUM(COSTFEESS) AS "总成本",
    SUM(UNITS_ORDERED) AS "销售量",
    SUM(UNITS_REFUNDED) AS "退货量",
    SUM(TOTALSALES) / NULLIF(SUM(COSTFEESS), 0) AS "库存周转率",
    SUM(UNITS_REFUNDED) / NULLIF(SUM(UNITS_ORDERED), 0) * 100 AS "退货率"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= ''{start_date}'' AND FDATE <= ''{end_date}''
),
mom AS (
  SELECT
    SUM(COSTFEESS) AS "成本_mom",
    SUM(UNITS_ORDERED) AS "销售量_mom"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
    SUM(COSTFEESS) AS "成本_yoy"
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB(''{start_date}'', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB(''{end_date}'', INTERVAL 1 YEAR)
)
SELECT
  b."仓库成本",
  b."库存数量",
  b."在途库存",
  b."总销售额",
  b."总成本",
  b."销售量",
  b."退货量",
  b."库存周转率",
  b."退货率",
  ROUND((b."库存周转率" - COALESCE(m."成本_mom", 0)), 2) AS "库存周转率_mom",
  ROUND((b."销售量" - COALESCE(m."销售量_mom", 0)) / NULLIF(COALESCE(m."销售量_mom", 0), 0) * 100, 2) AS "销售量_mom_rate",
  ROUND((b."总销售额" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate"
FROM base_data b, mom m, yoy y',
'drilldown', 1, 'inventory',
'["仓库成本", "库存数量", "在途库存", "总销售额", "总成本", "销售量", "退货量", "库存周转率", "退货率", "库存周转率_mom", "销售量_mom_rate", "销售额_yoy_rate"]'::jsonb,
'drilldown', 1, '基础指标'
);
