"""测试 SQL 模板引擎片段组合"""
import sys
sys.path.insert(0, '.')

from ai.sql_template_engine import generate_sql
from ai.sql_template_engine.engine import SQLTemplateEngine

# 模拟实体数据
entities = {
    "starrocks_sql": "SELECT SUM(ORDERED_PRODUCTSALES) AS ORDERED_PRODUCTSALES FROM ids.ADS_EC_SALES_V",
    "metric_code": "TEST-001",
    "dimension": "日",  # 中文维度名
    "date_column": "FDATE",
    "time_info": {
        "start_date": "2026-01-01",
        "end_date": "2026-04-12"
    }
}

print("=" * 60)
print("测试 query_trend 意图")
print("=" * 60)

# 解析 field
engine = SQLTemplateEngine()
context = engine._build_context(entities)
print(f"field: {context.get('field')}")
print(f"raw_field: {context.get('raw_field')}")
print(f"alias: {context.get('alias')}")
print(f"table: {context.get('table')}")
print(f"dimension: {context.get('dimension')}")
print(f"date_column: {context.get('date_column')}")
print()

# 生成 SQL
sql = generate_sql("query_trend", entities)
print(f"生成的 SQL:\n{sql}")
print()

# 测试 query_value
print("=" * 60)
print("测试 query_value 意图")
print("=" * 60)
sql_value = generate_sql("query_value", entities)
print(f"生成的 SQL:\n{sql_value}")
