"""
调试 semantic_search 返回什么
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 直接 import 并调用
from ai.engine.semantic_search import semantic_search

# 确保加载了向量
semantic_search.ensure_loaded()

# 搜索指标
query = "上月增长最快的是哪个店铺"
candidates = semantic_search.search_metric(query, top_k=5)

print(f"Query: {query}")
print(f"\n返回了 {len(candidates)} 个候选指标:")
for i, c in enumerate(candidates):
    print(f"\n[{i+1}] metric_code: {c.get('metric_code')}")
    print(f"    metric_name: {c.get('metric_name')}")
    print(f"    similarity: {c.get('similarity')}")

# 测试 _infer_metric_properties
print("\n\n=== 测试 _infer_metric_properties ===")
test_names = ["新开发供应商数量", "B2B销售额", "数量", "访客数", "转化率"]
for name in test_names:
    # 简单模拟
    not_ranking_keywords = ["率", "占比", "ROAS", "ACOS", "CPC", "CPM", "客单价", "平均", "人均", "单均"]
    ranking_keywords = ["额", "量", "数", "销量", "销售额", "订单量", "访客数", "买家数", "退款额", "成交额"]
    name_lower = name.lower()
    is_not_ranking = any(kw in name_lower for kw in not_ranking_keywords)
    is_ranking = any(kw in name_lower for kw in ranking_keywords) and not is_not_ranking
    print(f"{name}: ranking={is_ranking}")