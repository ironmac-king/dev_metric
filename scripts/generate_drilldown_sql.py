#!/usr/bin/env python3
"""
生成下钻SQL - 最终版
基于实际 IDS_AMZ_COMPREHENSIVE_DI 表的字段
"""
import json
import re
import urllib.request

API_BASE = "http://127.0.0.1:8080/api/v1"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkZXB0X2lkIjoxLCJleHAiOjE3NzcyMTU0MzEsImlhdCI6MTc3NzIxMTgzMSwicm9sZSI6ImFkbWluIiwidXNlcl9pZCI6MX0.t1VtD3U5o31gX_DoKNhXEh86totFO57LyKB-VC3usig"

SQL_KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL',
    'AS', 'ON', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'GROUP',
    'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'UNION', 'ALL',
    'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'IF', 'IFNULL', 'COALESCE',
    'SUM', 'AVG', 'COUNT', 'MAX', 'MIN', 'DISTINCT', 'ABS', 'ROUND',
    'DATE', 'DATE_ADD', 'DATE_SUB', 'INTERVAL', 'MONTH', 'YEAR', 'DAY',
    '1', 'TRUE', 'FALSE', '0'
}

def api_get(path):
    req = urllib.request.Request(f"{API_BASE}{path}", headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))

def extract_fields(sql):
    fields = set()
    func_pattern = re.findall(r'(?:SUM|AVG|COUNT|MAX|MIN)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)', sql, re.IGNORECASE)
    for f in func_pattern:
        f_upper = f.upper()
        if f_upper not in SQL_KEYWORDS and not f_upper.isdigit():
            fields.add(f_upper)
    ifnull_pattern = re.findall(r'IFNULL\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,', sql, re.IGNORECASE)
    for f in ifnull_pattern:
        f_upper = f.upper()
        if f_upper not in SQL_KEYWORDS and not f_upper.isdigit():
            fields.add(f_upper)
    return sorted(fields)

def main():
    TARGET_TABLE = "ids.IDS_AMZ_COMPREHENSIVE_DI"

    print("Fetching all metrics...")
    data = api_get("/metrics?page=1&page_size=500")
    metrics = data.get("data", {}).get("list", [])
    print(f"Total: {len(metrics)}")

    # 按分类收集指标
    all_fields = set()
    categorized = {'sales': [], 'ad': [], 'cost': [], 'inventory': []}

    # 字段→分类映射（基于实际字段语义）
    FIELD_CATEGORY = {
        # 销售相关
        'TOTALSALES': 'sales', 'ORDERED_PRODUCTSALES': 'sales', 'ORDERED_PRODUCTSALESB2B': 'sales',
        'UNITS_ORDERED': 'sales', 'UNITS_ORDEREDB2B': 'sales',
        'TOTALORDERS': 'sales', 'TOTAL_ORDERITEMS': 'sales', 'TOTAL_ORDERITEMSB2B': 'sales',
        'UNITS_REFUNDED': 'sales', 'UNITS_REFUNDED_B2B': 'sales',
        'INCOME_BCSS': 'sales', 'INCOME_BC_TK': 'sales', 'INCOME_NBCSS': 'sales',
        'TOTALUNITS': 'sales',
        # 广告相关
        'SPEND': 'ad', 'CLICKS': 'ad', 'IMPRESSIONS': 'ad',
        'FEATUREDOFFER_BUYBOX_PERCENTAGE': 'ad',
        # 页面/流量
        'SESSIONS_TOTAL': 'ad', 'SESSIONS_BROWSER': 'ad', 'SESSIONS_MOBILEAPP': 'ad',
        'SESSIONS_TOTAL_B2B': 'ad', 'SESSIONS_BROWSER_B2B': 'ad', 'SESSIONS_MOBILEAPP_B2B': 'ad',
        'PAGEVIEWS_TOTAL': 'ad', 'PAGEVIEWS_BROWSER': 'ad', 'PAGEVIEWS_MOBILEAPP': 'ad',
        'PAGEVIEWS_TOTAL_B2B': 'ad', 'PAGEVIEWS_BROWSER_B2B': 'ad', 'PAGEVIEWS_MOBILEAPP_B2B': 'ad',
        # 成本毛利
        'COSTFEESS': 'cost', 'PROFITBEFORETAX': 'cost', 'PLATFORM_CONTRIBUTION': 'cost',
        'FPLATFORMSERVICEFEE': 'cost', 'FPROMOTIOFEE': 'cost', 'TRANSPORTATION': 'cost',
        'TARIFFSFEE_HANDLE': 'cost', 'INCOMETAXFEE': 'cost', 'REFUSEFEE': 'cost',
        'SAMPLEFEE': 'cost', 'CONSULTINGFEE': 'cost', 'CHEMICALFEE': 'cost',
        'AFTERSALESFEE': 'cost', 'MEDIAFEE': 'cost', 'PACKINGFEE': 'cost',
        'FFBAFEE': 'cost', 'FGIFTWRAPCREDITS': 'cost', 'FSELLINGFEE': 'cost',
        'IMPORTFEE': 'cost', 'DSP': 'cost',
        # 库存相关
        'WHCOST': 'inventory', 'FSALABLEQUANTITY': 'inventory', 'FINVQUANTITY': 'inventory',
        'FREPLENISHMENT': 'inventory', 'FQTY': 'inventory', 'FQTY_TK': 'inventory',
    }

    for m in metrics:
        sql = m.get("starrocks_sql") or ""
        if not sql.strip():
            continue
        if TARGET_TABLE.lower() not in sql.lower():
            continue

        fields = extract_fields(sql)
        if not fields:
            continue

        all_fields.update(fields)
        name = m.get("name", "未知")
        code = m.get("metric_code", "")

        # 统计每个分类的字段数量
        cat_counts = {'sales': 0, 'ad': 0, 'cost': 0, 'inventory': 0}
        for f in fields:
            cat = FIELD_CATEGORY.get(f)
            if cat:
                cat_counts[cat] += 1

        # 找出最匹配的分类（字段数最多的）
        max_count = max(cat_counts.values())
        if max_count > 0:
            primary_cat = max(cat_counts, key=cat_counts.get)
            categorized[primary_cat].append({'name': name, 'code': code, 'fields': fields})
        else:
            categorized['sales'].append({'name': name, 'code': code, 'fields': fields})

    # 打印结果
    print(f"\nFields from IDS_AMZ_COMPREHENSIVE_DI: {len(all_fields)}")
    print(f"Fields: {', '.join(sorted(all_fields))}")

    print("\n=== 分类结果 ===")
    for cat, mets in categorized.items():
        fields_in_cat = set()
        for m in mets:
            fields_in_cat.update(m['fields'])
        print(f"\n【{cat}】({len(mets)} metrics)")
        print(f"  Fields: {', '.join(sorted(fields_in_cat))}")

    # 去重
    def dedup(mets):
        seen = set()
        result = []
        for m in mets:
            if m['code'] not in seen:
                seen.add(m['code'])
                result.append(m)
        return result

    for cat in categorized:
        categorized[cat] = dedup(categorized[cat])

    print("\n=== 去重后 ===")
    for cat, mets in categorized.items():
        print(f"{cat}: {len(mets)} metrics")

    # 生成SQL - 销售经营
    sales_fields = {'TOTALSALES', 'ORDERED_PRODUCTSALES', 'ORDERED_PRODUCTSALESB2B',
                     'UNITS_ORDERED', 'UNITS_ORDEREDB2B', 'TOTALORDERS', 'TOTAL_ORDERITEMS',
                     'TOTAL_ORDERITEMSB2B', 'UNITS_REFUNDED', 'UNITS_REFUNDED_B2B',
                     'INCOME_BCSS', 'INCOME_BC_TK', 'INCOME_NBCSS', 'TOTALUNITS'}

    ad_fields = {'SPEND', 'CLICKS', 'IMPRESSIONS', 'FEATUREDOFFER_BUYBOX_PERCENTAGE',
                  'SESSIONS_TOTAL', 'SESSIONS_BROWSER', 'SESSIONS_MOBILEAPP',
                  'SESSIONS_TOTAL_B2B', 'SESSIONS_BROWSER_B2B', 'SESSIONS_MOBILEAPP_B2B',
                  'PAGEVIEWS_TOTAL', 'PAGEVIEWS_BROWSER', 'PAGEVIEWS_MOBILEAPP',
                  'PAGEVIEWS_TOTAL_B2B', 'PAGEVIEWS_BROWSER_B2B', 'PAGEVIEWS_MOBILEAPP_B2B'}

    cost_fields = {'COSTFEESS', 'PROFITBEFORETAX', 'PLATFORM_CONTRIBUTION',
                   'FPLATFORMSERVICEFEE', 'FPROMOTIOFEE', 'TRANSPORTATION', 'TARIFFSFEE_HANDLE',
                   'INCOMETAXFEE', 'REFUSEFEE', 'SAMPLEFEE', 'CONSULTINGFEE', 'CHEMICALFEE',
                   'AFTERSALESFEE', 'MEDIAFEE', 'PACKINGFEE', 'FFBAFEE', 'FGIFTWRAPCREDITS',
                   'FSELLINGFEE', 'IMPORTFEE', 'DSP'}

    inventory_fields = {'WHCOST', 'FSALABLEQUANTITY', 'FINVQUANTITY',
                        'FREPLENISHMENT', 'FQTY', 'FQTY_TK'}

    def make_sql(category_name, field_set, all_metrics):
        selects = []
        for f in sorted(field_set):
            selects.append(f'    SUM({f}) AS "{f}"')

        # 计算环比同比
        mom_sql = f""",
mom_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_mom",
    SUM(UNITS_ORDERED) AS "订单量_mom"
  FROM {TARGET_TABLE}
  WHERE FDATE >= DATE_SUB('{{start_date}}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{{end_date}}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
    SUM(UNITS_ORDERED) AS "订单量_yoy"
  FROM {TARGET_TABLE}
  WHERE FDATE >= DATE_SUB('{{start_date}}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{{end_date}}', INTERVAL 1 YEAR)
)"""

        base_sql = f"""WITH base_data AS (
  SELECT
{chr(10).join(selects)}
  FROM {TARGET_TABLE}
  WHERE FDATE >= '{{start_date}}' AND FDATE <= '{{end_date}}'
){mom_sql}
SELECT"""

        # 添加基础指标
        select_final = ["  b.*"]
        if 'TOTALSALES' in field_set:
            select_final.append('  ROUND((b."TOTALSALES" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate"')
            select_final.append('  ROUND((b."TOTALSALES" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate"')
        if 'UNITS_ORDERED' in field_set:
            select_final.append('  ROUND((b."UNITS_ORDERED" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate"')

        select_final.append('FROM base_data b, mom_data m, yoy_data y')

        full_sql = base_sql + chr(10).join(select_final)

        # 构建metric_names
        metric_names = json.dumps(sorted(field_set), ensure_ascii=False)

        return f"""$$WITH base_data AS (
  SELECT
{chr(10).join(selects)}
  FROM {TARGET_TABLE}
  WHERE FDATE >= '{{start_date}}' AND FDATE <= '{{end_date}}'
),
mom_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_mom",
    SUM(UNITS_ORDERED) AS "订单量_mom"
  FROM {TARGET_TABLE}
  WHERE FDATE >= DATE_SUB('{{start_date}}', INTERVAL 1 MONTH)
    AND FDATE <= DATE_SUB('{{end_date}}', INTERVAL 1 MONTH)
),
yoy_data AS (
  SELECT
    SUM(TOTALSALES) AS "销售额_yoy",
    SUM(UNITS_ORDERED) AS "订单量_yoy"
  FROM {TARGET_TABLE}
  WHERE FDATE >= DATE_SUB('{{start_date}}', INTERVAL 1 YEAR)
    AND FDATE <= DATE_SUB('{{end_date}}', INTERVAL 1 YEAR)
)
SELECT
  b.*,
  ROUND((b."TOTALSALES" - COALESCE(m."销售额_mom", 0)) / NULLIF(COALESCE(m."销售额_mom", 0), 0) * 100, 2) AS "销售额_mom_rate",
  ROUND((b."TOTALSALES" - COALESCE(y."销售额_yoy", 0)) / NULLIF(COALESCE(y."销售额_yoy", 0), 0) * 100, 2) AS "销售额_yoy_rate",
  ROUND((b."UNITS_ORDERED" - COALESCE(m."订单量_mom", 0)) / NULLIF(COALESCE(m."订单量_mom", 0), 0) * 100, 2) AS "订单量_mom_rate"
FROM base_data b, mom_data m, yoy_data y$$"""

    # 生成SQL模板
    templates = [
        ('销售经营', 'sales', sales_fields, '销售经营分析基础指标（销售额 + 订单量 + 收入）'),
        ('广告投放', 'ad', ad_fields, '广告投放分析基础指标（花费 + 流量 + 转化）'),
        ('成本毛利', 'cost', cost_fields, '成本毛利分析基础指标（成本 + 费用 + 利润）'),
        ('库存供应链', 'inventory', inventory_fields, '库存供应链分析基础指标（库存 + 周转）'),
    ]

    print("\n" + "="*70)
    print("GENERATED SQL TEMPLATES (Ready to insert)")
    print("="*70)

    output = []
    for name, cat, fields_set, desc in templates:
        sql = make_sql(name, fields_set, [])
        metric_names = json.dumps(sorted(fields_set), ensure_ascii=False)
        insert = f"""-- =====================================================
-- {name} ({cat})
-- =====================================================
INSERT INTO sql_templates (name, description, sql_template, intent, status, drilldown_category, metric_names, template_type, template_order, template_name)
VALUES
(
  '{name}-基础指标',
  '{desc}',
'{sql}',
  'drilldown',
  1,
  '{cat}',
  '{metric_names}'::jsonb,
  'drilldown',
  1,
  '基础指标'
);

"""
        output.append(insert)
        print(insert)

    # 保存到文件
    with open('sql/drilldown_sql_final.sql', 'w', encoding='utf-8') as f:
        f.write('-- 四类下钻SQL模板 (由脚本自动生成)\n')
        f.write(f'-- 表: {TARGET_TABLE}\n')
        f.write(f'-- 生成时间: 2026-04-26\n\n')
        for o in output:
            f.write(o + '\n')

    print("\n已保存到 sql/drilldown_sql_final.sql")

if __name__ == "__main__":
    main()
