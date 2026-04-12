import requests
import json

response = requests.post(
    "http://localhost:8081/api/v1/analysis/analyze",
    json={"query": "广告", "session_id": ""},
    timeout=60
)

data = response.json()
answer = data.get("data", {}).get("answer", "")
charts = data.get("data", {}).get("charts", [])

print(f"Charts count: {len(charts)}")
print(f"Answer length: {len(answer)}")
print(f"Contains CHART_DATA: {'CHART_DATA' in answer}")
print(f"Contains CHART_BLOCK: {'CHART_BLOCK' in answer}")

# 写入文件避免编码问题
with open('/tmp/answer.txt', 'w', encoding='utf-8') as f:
    f.write(answer)
print("\nAnswer written to /tmp/answer.txt")
