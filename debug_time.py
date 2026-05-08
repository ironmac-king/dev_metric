"""测试 LLM 是否能正确提取 time_range"""
import sys
sys.path.insert(0, '.')

from ai.engine.llm import LLMEngine

llm = LLMEngine()

# 测试 LLM 提取 time_range
test_cases = [
    "最近一个月的页面访问量是多少",
    "最近一个月",
    "最近三十一天",
    "近7天",
    "过去一个月",
]

for text in test_cases:
    result = llm.recognize_intent_enhanced(text)
    print(f"问题: {text}")
    print(f"  intent: {result.intent}")
    print(f"  time_range: {result.entities.get('time_range', 'N/A')}")
    print(f"  metric_name: {result.entities.get('metric_name', 'N/A')}")
    print()
