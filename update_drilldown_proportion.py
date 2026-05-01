# -*- coding: utf-8 -*-
import urllib.request
import json

base_url = 'http://localhost:8080/api/v1/nlp/sql-templates'

def update_template(tid, sql_template, metric_names):
    data = json.dumps({
        'sql_template': sql_template,
        'metric_names': metric_names
    }, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        f'{base_url}/{tid}',
        data=data,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='PUT'
    )
    with urllib.request.urlopen(req) as resp:
        result = json.load(resp)
        return result.get('code') == 0, result.get('message')

# 1. 站点下钻 (id=28) - 加销售额占比 + mom + yoy
站点下钻_sql = """WITH base_data AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额,
    SUM(TOTALORDERS) AS 总订单数,
    SUM(UNITS_ORDERED) AS 订单量,
    SUM(UNITS_ORDEREDB2B) AS B2B订单量,
    SUM(totalunits) AS 总销量,
    SUM(UNITS_REFUNDED) AS 退款量,
    SUM(INCOME_BCSS) AS 国内收入,
    SUM(INCOME_BC_TK) AS 跨境收入,
    FSITE AS 站点,
    FSITECODE AS 站点编码
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}" AND
   {dimension_filter}
  GROUP BY FSITE, FSITECODE
),
mom AS (
  SELECT
    FSITE,
    FSITECODE,
    SUM(ORDERED_PRODUCTSALES) AS 销售额_mom,
    SUM(UNITS_ORDERED) AS 订单量_mom
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 MONTH) AND
   {dimension_filter}
  GROUP BY FSITE, FSITECODE
),
yoy AS (
  SELECT
    FSITE,
    FSITECODE,
    SUM(ORDERED_PRODUCTSALES) AS 销售额_yoy,
    SUM(UNITS_ORDERED) AS 订单量_yoy
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 YEAR) AND
   {dimension_filter}
  GROUP BY FSITE, FSITECODE
)
SELECT
  b.站点,
  b.站点编码,
  b.销售额,
  ROUND(b.销售额 / SUM(b.销售额) OVER() * 100, 2) AS 销售额占比,
  b.总订单数,
  b.订单量,
  b.B2B订单量,
  b.总销量,
  b.退款量,
  b.国内收入,
  b.跨境收入,
  ROUND(b.销售额 / NULLIF(b.订单量, 0), 2) AS 客单价,
  ROUND((b.销售额 - COALESCE(m.销售额_mom, 0)) / NULLIF(COALESCE(m.销售额_mom, 0), 0) * 100, 2) AS 销售额_mom_rate,
  ROUND((b.订单量 - COALESCE(m.订单量_mom, 0)) / NULLIF(COALESCE(m.订单量_mom, 0), 0) * 100, 2) AS 订单量_mom_rate,
  ROUND((b.销售额 - COALESCE(y.销售额_yoy, 0)) / NULLIF(COALESCE(y.销售额_yoy, 0), 0) * 100, 2) AS 销售额_yoy_rate,
  ROUND((b.订单量 - COALESCE(y.订单量_yoy, 0)) / NULLIF(COALESCE(y.订单量_yoy, 0), 0) * 100, 2) AS 订单量_yoy_rate
FROM base_data b
LEFT JOIN mom m ON b.站点 = m.FSITE AND b.站点编码 = m.FSITECODE
LEFT JOIN yoy y ON b.站点 = y.FSITE AND b.站点编码 = y.FSITECODE
ORDER BY b.销售额 DESC
LIMIT 20"""

站点下钻_metrics = ["销售额", "销售额占比", "总订单数", "订单量", "B2B订单量", "总销量", "退款量", "国内收入", "跨境收入", "客单价", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"]

# 2. 一级品类下钻 (id=29) - 加销售额占比 + mom + yoy
一级品类下钻_sql = """WITH base_data AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额,
    SUM(TOTALORDERS) AS 总订单数,
    SUM(UNITS_ORDERED) AS 订单量,
    SUM(UNITS_ORDEREDB2B) AS B2B订单量,
    SUM(INCOME_BCSS) AS 国内收入,
    SUM(INCOME_BC_TK) AS 跨境收入,
    GROUP_1 AS 一级品类
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}" AND
   {dimension_filter}
  GROUP BY GROUP_1
),
mom AS (
  SELECT
    GROUP_1,
    SUM(ORDERED_PRODUCTSALES) AS 销售额_mom,
    SUM(UNITS_ORDERED) AS 订单量_mom
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 MONTH) AND
   {dimension_filter}
  GROUP BY GROUP_1
),
yoy AS (
  SELECT
    GROUP_1,
    SUM(ORDERED_PRODUCTSALES) AS 销售额_yoy,
    SUM(UNITS_ORDERED) AS 订单量_yoy
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 YEAR) AND
   {dimension_filter}
  GROUP BY GROUP_1
)
SELECT
  b.一级品类,
  b.销售额,
  ROUND(b.销售额 / SUM(b.销售额) OVER() * 100, 2) AS 销售额占比,
  b.总订单数,
  b.订单量,
  b.B2B订单量,
  b.国内收入,
  b.跨境收入,
  ROUND(b.国内收入 / NULLIF(b.销售额, 0) * 100, 2) AS 国内收入占比,
  ROUND(b.跨境收入 / NULLIF(b.销售额, 0) * 100, 2) AS 跨境收入占比,
  ROUND(b.销售额 / NULLIF(b.订单量, 0), 2) AS 客单价,
  ROUND((b.销售额 - COALESCE(m.销售额_mom, 0)) / NULLIF(COALESCE(m.销售额_mom, 0), 0) * 100, 2) AS 销售额_mom_rate,
  ROUND((b.订单量 - COALESCE(m.订单量_mom, 0)) / NULLIF(COALESCE(m.订单量_mom, 0), 0) * 100, 2) AS 订单量_mom_rate,
  ROUND((b.销售额 - COALESCE(y.销售额_yoy, 0)) / NULLIF(COALESCE(y.销售额_yoy, 0), 0) * 100, 2) AS 销售额_yoy_rate,
  ROUND((b.订单量 - COALESCE(y.订单量_yoy, 0)) / NULLIF(COALESCE(y.订单量_yoy, 0), 0) * 100, 2) AS 订单量_yoy_rate
FROM base_data b
LEFT JOIN mom m ON b.一级品类 = m.GROUP_1
LEFT JOIN yoy y ON b.一级品类 = y.GROUP_1
ORDER BY b.销售额 DESC
LIMIT 20"""

一级品类下钻_metrics = ["销售额", "销售额占比", "总订单数", "订单量", "B2B订单量", "国内收入", "跨境收入", "国内收入占比", "跨境收入占比", "客单价", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"]

# 3. 平台下钻 (id=30) - 加销售额占比 + mom + yoy
平台下钻_sql = """WITH base_data AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额,
    SUM(TOTALORDERS) AS 总订单数,
    SUM(UNITS_ORDERED) AS 订单量,
    SUM(UNITS_ORDEREDB2B) AS B2B订单量,
    SUM(INCOME_BCSS) AS 国内收入,
    SUM(INCOME_BC_TK) AS 跨境收入,
    PLATFORM AS 平台
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}" AND
   {dimension_filter}
  GROUP BY PLATFORM
),
mom AS (
  SELECT
    PLATFORM,
    SUM(ORDERED_PRODUCTSALES) AS 销售额_mom,
    SUM(UNITS_ORDERED) AS 订单量_mom
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 MONTH) AND
   {dimension_filter}
  GROUP BY PLATFORM
),
yoy AS (
  SELECT
    PLATFORM,
    SUM(ORDERED_PRODUCTSALES) AS 销售额_yoy,
    SUM(UNITS_ORDERED) AS 订单量_yoy
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 YEAR) AND
   {dimension_filter}
  GROUP BY PLATFORM
)
SELECT
  b.平台,
  b.销售额,
  ROUND(b.销售额 / SUM(b.销售额) OVER() * 100, 2) AS 销售额占比,
  b.总订单数,
  b.订单量,
  b.B2B订单量,
  b.国内收入,
  b.跨境收入,
  ROUND(b.销售额 / NULLIF(b.订单量, 0), 2) AS 客单价,
  ROUND((b.销售额 - COALESCE(m.销售额_mom, 0)) / NULLIF(COALESCE(m.销售额_mom, 0), 0) * 100, 2) AS 销售额_mom_rate,
  ROUND((b.订单量 - COALESCE(m.订单量_mom, 0)) / NULLIF(COALESCE(m.订单量_mom, 0), 0) * 100, 2) AS 订单量_mom_rate,
  ROUND((b.销售额 - COALESCE(y.销售额_yoy, 0)) / NULLIF(COALESCE(y.销售额_yoy, 0), 0) * 100, 2) AS 销售额_yoy_rate,
  ROUND((b.订单量 - COALESCE(y.订单量_yoy, 0)) / NULLIF(COALESCE(y.订单量_yoy, 0), 0) * 100, 2) AS 订单量_yoy_rate
FROM base_data b
LEFT JOIN mom m ON b.平台 = m.PLATFORM
LEFT JOIN yoy y ON b.平台 = y.PLATFORM
ORDER BY b.销售额 DESC"""

平台下钻_metrics = ["销售额", "销售额占比", "总订单数", "订单量", "B2B订单量", "国内收入", "跨境收入", "客单价", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"]

# 4. ASIN下钻 (id=31) - 加销售额占比 + mom + yoy
ASIN下钻_sql = """WITH base_data AS (
  SELECT
    SUM(ORDERED_PRODUCTSALES) AS 销售额,
    SUM(TOTALORDERS) AS 总订单数,
    SUM(UNITS_ORDERED) AS 订单量,
    SUM(UNITS_REFUNDED) AS 退款量,
    ASIN AS ASIN
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}" AND
   {dimension_filter}
  GROUP BY ASIN
),
mom AS (
  SELECT
    ASIN,
    SUM(ORDERED_PRODUCTSALES) AS 销售额_mom,
    SUM(UNITS_ORDERED) AS 订单量_mom
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 MONTH) AND
   {dimension_filter}
  GROUP BY ASIN
),
yoy AS (
  SELECT
    ASIN,
    SUM(ORDERED_PRODUCTSALES) AS 销售额_yoy,
    SUM(UNITS_ORDERED) AS 订单量_yoy
  FROM ids.IDS_AMZ_COMPREHENSIVE_DI
  WHERE FDATE >= DATE_SUB("{start_date}", INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB("{end_date}", INTERVAL 1 YEAR) AND
   {dimension_filter}
  GROUP BY ASIN
)
SELECT
  b.ASIN,
  b.销售额,
  ROUND(b.销售额 / SUM(b.销售额) OVER() * 100, 2) AS 销售额占比,
  b.总订单数,
  b.订单量,
  b.退款量,
  ROUND(b.销售额 / NULLIF(b.订单量, 0), 2) AS 客单价,
  ROUND(b.退款量 / NULLIF(b.订单量, 0) * 100, 2) AS 退款率,
  ROUND((b.销售额 - COALESCE(m.销售额_mom, 0)) / NULLIF(COALESCE(m.销售额_mom, 0), 0) * 100, 2) AS 销售额_mom_rate,
  ROUND((b.订单量 - COALESCE(m.订单量_mom, 0)) / NULLIF(COALESCE(m.订单量_mom, 0), 0) * 100, 2) AS 订单量_mom_rate,
  ROUND((b.销售额 - COALESCE(y.销售额_yoy, 0)) / NULLIF(COALESCE(y.销售额_yoy, 0), 0) * 100, 2) AS 销售额_yoy_rate,
  ROUND((b.订单量 - COALESCE(y.订单量_yoy, 0)) / NULLIF(COALESCE(y.订单量_yoy, 0), 0) * 100, 2) AS 订单量_yoy_rate
FROM base_data b
LEFT JOIN mom m ON b.ASIN = m.ASIN
LEFT JOIN yoy y ON b.ASIN = y.ASIN
ORDER BY b.销售额 DESC
LIMIT 20"""

ASIN下钻_metrics = ["销售额", "销售额占比", "总订单数", "订单量", "退款量", "客单价", "退款率", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"]

templates = [
    (28, 站点下钻_sql, 站点下钻_metrics, "站点下钻"),
    (29, 一级品类下钻_sql, 一级品类下钻_metrics, "一级品类下钻"),
    (30, 平台下钻_sql, 平台下钻_metrics, "平台下钻"),
    (31, ASIN下钻_sql, ASIN下钻_metrics, "ASIN下钻"),
]

for tid, sql, metrics, name in templates:
    ok, msg = update_template(tid, sql, metrics)
    print(f"{name} (ID={tid}): {'OK' if ok else 'FAIL: ' + str(msg)}")
