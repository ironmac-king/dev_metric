#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NER 测试脚本 - 通过 Python AI 服务测试 NER 功能
解决 Windows curl 的 GBK 编码问题
"""
import httpx
import json
import sys

# 确保 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')

GO_API = "http://localhost:8080"
PYTHON_API = "http://localhost:8081"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkZXB0X2lkIjoxLCJleHAiOjE3NzYwOTUxNTcsImlhdCI6MTc3NjA5MTU1Nywicm9sZSI6ImFkbWluIiwidXNlcl9pZCI6MX0.49k0kXWKJIr8YSChusHJZgoU76IzZiZ5TUfPpiXJmX4"


def test_via_python_api(question: str, session_id: str = "test-ner"):
    """直接通过 Python AI 服务测试"""
    print(f"\n{'='*60}")
    print(f"测试: {question}")
    print(f"{'='*60}")

    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{PYTHON_API}/api/v1/ask",
            json={
                "question": question,
                "session_id": session_id,
                "user_id": "1",
                "dept_id": 1,
                "page": 1,
                "page_size": 10,
            },
        )

    result = response.json()
    print(f"\n[结果]")
    print(f"  metric_code: {result.get('metric_code', 'None')}")
    print(f"  clarification: {result.get('clarification_type', 'None')}")
    print(f"  SQL: {result.get('sql', 'None')[:100] if result.get('sql') else 'None'}...")

    print(f"\n[思考步骤]")
    for step in result.get("thinking_steps", []):
        content = step.get("content", "")[:80]
        print(f"  [{step.get('step')}] {content}")

    return result


def test_via_go_api(question: str, session_id: str = "test-ner"):
    """通过 Go 后端测试（模拟前端调用）"""
    print(f"\n{'='*60}")
    print(f"测试 (via Go): {question}")
    print(f"{'='*60}")

    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{GO_API}/api/v1/ask",
            json={
                "question": question,
                "session_id": session_id,
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    result = response.json()
    print(f"\n[结果]")
    print(f"  metric_code: {result.get('metric_code', 'None')}")
    print(f"  clarification: {result.get('clarification_type', 'None')}")
    print(f"  SQL: {result.get('sql', 'None')[:100] if result.get('sql') else 'None'}...")

    return result


def main():
    print("=" * 60)
    print("NER 功能测试")
    print("=" * 60)

    # 测试用例
    test_cases = [
        "计算亚马逊各店铺退款数量在销量中的占比",
        "各平台销售额对比",
        "本月销量趋势",
        "昨天的访客数是多少",
    ]

    print("\n### 直接通过 Python AI 服务测试 ###")
    for i, question in enumerate(test_cases):
        test_via_python_api(question, f"test-python-{i}")

    print("\n\n### 通过 Go 后端测试 (模拟前端) ###")
    for i, question in enumerate(test_cases):
        test_via_go_api(question, f"test-go-{i}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
