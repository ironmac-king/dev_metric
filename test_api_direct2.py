"""
测试不同意图的问题，看猜你想问是否正常工作
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import json

url = "http://localhost:8081/api/v1/ask"

# 测试1: 排名意图 (应该被识别为 query_ranking)
test_cases = [
    ("上月增长最快的是哪个店铺", "排名意图测试"),
    ("本月销售额是多少", "数值意图测试"),
    ("各店铺销售额对比", "对比意图测试"),
]

for question, desc in test_cases:
    print(f"\n{'='*60}")
    print(f"测试: {desc}")
    print(f"问题: {question}")
    print('='*60)

    data = {
        "question": question,
        "session_id": f"test-{desc}"
    }

    try:
        response = requests.post(url, json=data, timeout=60)
        result = response.json()

        print(f"\n意图识别: {result.get('thinking_steps', [{}])[0].get('content', 'N/A') if result.get('thinking_steps') else 'N/A'}")
        print(f"实体识别: {result.get('thinking_steps', [{}])[1].get('content', 'N/A') if len(result.get('thinking_steps', [])) > 1 else 'N/A'}")
        print(f"\nclarification_type: {result.get('clarification_type')}")
        print(f"needs_clarification: {result.get('needs_clarification')}")
        print(f"\n建议追问:")
        for s in result.get('suggest', []):
            print(f"  - {s}")

    except Exception as e:
        print(f"Error: {e}")