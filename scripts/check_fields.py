#!/usr/bin/env python3
import json
import re
import sys

with open('C:/Users/4014/Desktop/dev_metric/metrics_check.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

metrics = data.get('data', {}).get('list', [])
target_table = 'ids.ids_amz_comprehensive_di'

target_metrics = []
for m in metrics:
    sql = m.get('starrocks_sql', '') or ''
    if target_table in sql.lower():
        target_metrics.append(m)

print(f'Metrics with IDS_AMZ_COMPREHENSIVE_DI: {len(target_metrics)}')

# 按category分类统计
by_cat = {}
for m in target_metrics:
    cat1 = m.get('category_1', '未知')
    if cat1 not in by_cat:
        by_cat[cat1] = []
    by_cat[cat1].append(m)

for cat, mets in sorted(by_cat.items()):
    print(f'\n[{cat}] ({len(mets)} metrics)')

# 提取所有字段
all_fields = set()
for m in target_metrics:
    sql = m.get('starrocks_sql', '')
    fields = re.findall(r'(?:SUM|IFNULL|COUNT|AVG|MAX|MIN)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*', sql, re.IGNORECASE)
    all_fields.update([f.upper() for f in fields])

print(f'\n=== ALL FIELDS ({len(all_fields)}) ===')
for f in sorted(all_fields):
    print(f'  {f}')

# 打印每个指标的SQL
print('\n=== METRIC SQL SAMPLES ===')
for m in target_metrics[:10]:
    name = m.get('name', '')
    code = m.get('metric_code', '')
    sql = m.get('starrocks_sql', '')[:200]
    print(f'\n[{code}] {name}:')
    print(f'  {sql}')
