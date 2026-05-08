import json

with open('C:/tmp/metrics.json', encoding='utf-8') as f:
    d = json.load(f)

metrics = d.get('data', [])

# 搜索关键词
keywords = ['roas', 'acos', 'cpc', 'ctr', '转化', '点击', '广告', '销售', '花费', '订单']

print("=== 亚马逊广告相关指标 ===")
for m in metrics:
    name = m.get('name', '')
    code = m.get('metric_code', '')
    name_lower = name.lower()
    for k in keywords:
        if k.lower() in name_lower:
            sql = m.get('starrocks_sql', '')
            print(f"\n{code} - {name}")
            print(f"  SQL: {sql[:100]}..." if sql else "  SQL: (空)")
            break
