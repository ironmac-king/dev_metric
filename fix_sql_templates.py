# -*- coding: utf-8 -*-
import urllib.request
import json

base_url = 'http://localhost:8080/api/v1/nlp/sql-templates'

def update_template(tid, sql_template):
    data = json.dumps({'sql_template': sql_template}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        f'{base_url}/{tid}',
        data=data,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='PUT'
    )
    with urllib.request.urlopen(req) as resp:
        result = json.load(resp)
        return result.get('code') == 0, result.get('message')

# Sales template (ID=24)
sales_sql = """WITH base_data AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额,
    SUM(TOTALORDERS) AS 总订单数,
    SUM(UNITS_ORDERED) AS 订单量,
    SUM(UNITS_ORDEREDB2B) AS B2B订单量,
    SUM(totalunits) AS 总销量,
    SUM(UNITS_REFUNDED) AS 退款量,
    SUM(INCOME_BCSS) AS 国内收入,
    SUM(INCOME_BC_TK) AS 跨境收入
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}"
),
mom AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额_mom,
    SUM(UNITS_ORDERED) AS 订单量_mom
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额_yoy,
    SUM(UNITS_ORDERED) AS 订单量_yoy
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 YEAR)
)
SELECT
  b.销售额,
  b.总订单数,
  b.订单量,
  b.B2B订单量,
  b.总销量,
  b.退款量,
  b.国内收入,
  b.跨境收入,
  ROUND((b.销售额 - COALESCE(m.销售额_mom, 0)) / NULLIF(COALESCE(m.销售额_mom, 0), 0) * 100, 2) AS 销售额_mom_rate,
  ROUND((b.订单量 - COALESCE(m.订单量_mom, 0)) / NULLIF(COALESCE(m.订单量_mom, 0), 0) * 100, 2) AS 订单量_mom_rate,
  ROUND((b.销售额 - COALESCE(y.销售额_yoy, 0)) / NULLIF(COALESCE(y.销售额_yoy, 0), 0) * 100, 2) AS 销售额_yoy_rate,
  ROUND((b.订单量 - COALESCE(y.订单量_yoy, 0)) / NULLIF(COALESCE(y.订单量_yoy, 0), 0) * 100, 2) AS 订单量_yoy_rate
FROM base_data b, mom m, yoy y"""

# Ad template (ID=25)
ad_sql = """WITH base_data AS (
  SELECT
    SUM(SPEND) AS 广告花费,
    SUM(IMPRESSIONS) AS 广告展示数,
    SUM(CLICKS) AS 广告点击数,
    SUM(TOTALORDERS) AS 广告订单数,
    SUM(ORDERED_PRODUCTSALES) AS 广告销售额,
    SUM(SESSIONS_TOTAL) AS 总会话数,
    SUM(PAGEVIEWS_TOTAL) AS 总页面浏览量
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}"
),
mom AS (
  SELECT
    SUM(SPEND) AS 广告花费_mom,
    SUM(ORDERED_PRODUCTSALES) AS 广告销售额_mom
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(SPEND) AS 广告花费_yoy,
    SUM(ORDERED_PRODUCTSALES) AS 广告销售额_yoy
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 YEAR)
)
SELECT
  b.广告花费,
  b.广告展示数,
  b.广告点击数,
  b.广告订单数,
  b.广告销售额,
  b.总会话数,
  b.总页面浏览量,
  ROUND((b.广告花费 - COALESCE(m.广告花费_mom, 0)) / NULLIF(COALESCE(m.广告花费_mom, 0), 0) * 100, 2) AS 广告花费_mom_rate,
  ROUND((b.广告销售额 - COALESCE(m.广告销售额_mom, 0)) / NULLIF(COALESCE(m.广告销售额_mom, 0), 0) * 100, 2) AS 广告销售额_mom_rate,
  ROUND((b.广告花费 - COALESCE(y.广告花费_yoy, 0)) / NULLIF(COALESCE(y.广告花费_yoy, 0), 0) * 100, 2) AS 广告花费_yoy_rate,
  ROUND((b.广告销售额 - COALESCE(y.广告销售额_yoy, 0)) / NULLIF(COALESCE(y.广告销售额_yoy, 0), 0) * 100, 2) AS 广告销售额_yoy_rate
FROM base_data b, mom m, yoy y"""

# Inventory template (ID=26)
inventory_sql = """WITH base_data AS (
  SELECT
    SUM(FQTY) AS 库存数量,
    SUM(FQTY_TK) AS 在途库存,
    SUM(WHCOST) AS 仓库成本,
    SUM(TOTALSALES) AS 总销售额,
    SUM(COSTFEESS) AS 总成本,
    SUM(UNITS_ORDERED) AS 销售量,
    SUM(UNITS_REFUNDED) AS 退货量
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}"
),
mom AS (
  SELECT
    SUM(COSTFEESS) AS 成本_mom,
    SUM(UNITS_ORDERED) AS 销售量_mom
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(TOTALSALES) AS 销售额_yoy,
    SUM(COSTFEESS) AS 成本_yoy
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 YEAR)
)
SELECT
  b.库存数量,
  b.在途库存,
  b.仓库成本,
  b.总销售额,
  b.总成本,
  b.销售量,
  b.退货量,
  ROUND((b.销售量 - COALESCE(m.销售量_mom, 0)) / NULLIF(COALESCE(m.销售量_mom, 0), 0) * 100, 2) AS 销售量_mom_rate,
  ROUND((b.总销售额 - COALESCE(y.销售额_yoy, 0)) / NULLIF(COALESCE(y.销售额_yoy, 0), 0) * 100, 2) AS 销售额_yoy_rate
FROM base_data b, mom m, yoy y"""

# Cost template (ID=27)
cost_sql = """WITH base_data AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额,
    SUM(COSTFEESS) AS 成本,
    SUM(PROFITBEFORETAX) AS 税前利润,
    SUM(PLATFORM_CONTRIBUTION) AS 平台贡献,
    SUM(FPLATFORMSERVICEFEE) AS 平台服务费,
    SUM(FPROMOTIOFEE) AS 促销费,
    SUM(TRANSPORTATION) AS 运费,
    SUM(TARIFFSFEE_HANDLE) AS 关税
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}"
),
mom AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额_mom,
    SUM(PROFITBEFORETAX) AS 利润_mom
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 MONTH)
),
yoy AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额_yoy,
    SUM(PROFITBEFORETAX) AS 利润_yoy
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 YEAR)
)
SELECT
  b.销售额,
  b.成本,
  b.税前利润,
  b.平台贡献,
  b.平台服务费,
  b.促销费,
  b.运费,
  b.关税,
  ROUND((b.销售额 - COALESCE(m.销售额_mom, 0)) / NULLIF(COALESCE(m.销售额_mom, 0), 0) * 100, 2) AS 销售额_mom_rate,
  ROUND((b.税前利润 - COALESCE(m.利润_mom, 0)) / NULLIF(COALESCE(m.利润_mom, 0), 0) * 100, 2) AS 利润_mom_rate,
  ROUND((b.销售额 - COALESCE(y.销售额_yoy, 0)) / NULLIF(COALESCE(y.销售额_yoy, 0), 0) * 100, 2) AS 销售额_yoy_rate,
  ROUND((b.税前利润 - COALESCE(y.利润_yoy, 0)) / NULLIF(COALESCE(y.利润_yoy, 0), 0) * 100, 2) AS 利润_yoy_rate
FROM base_data b, mom m, yoy y"""

templates = [
    (24, sales_sql, 'sales'),
    (25, ad_sql, 'ad'),
    (26, inventory_sql, 'inventory'),
    (27, cost_sql, 'cost'),
]

for tid, sql, name in templates:
    ok, msg = update_template(tid, sql)
    print(f'{name} (ID={tid}): {"OK" if ok else "FAIL: " + msg}')
