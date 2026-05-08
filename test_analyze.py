import requests
import json

response = requests.post(
    "http://localhost:8081/api/v1/analysis/analyze",
    json={"query": "分析近30天广告", "session_id": ""},
    timeout=60
)

data = response.json()
answer = data.get("data", {}).get("answer", "")
charts = data.get("data", {}).get("charts", [])

print(f"Charts count: {len(charts)}")
print(f"Answer length: {len(answer)}")
print(f"\nAnswer preview (first 1000 chars):")
print(answer[:1000])

# 检查是否有未替换的占位符
if "{metric_" in answer:
    print("\n[ERROR] Found unreplaced metric placeholder!")
    import re
    placeholders = re.findall(r'\{metric_[^}]+\}', answer)
    print(f"Unreplaced placeholders: {placeholders}")
