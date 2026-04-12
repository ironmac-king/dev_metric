import requests
import json
import sys

response = requests.post(
    "http://localhost:8081/api/v1/analysis/stream",
    json={"query": "广告", "session_id": ""},
    stream=True,
    timeout=30
)

print(f"Status: {response.status_code}", flush=True)

has_chart_event = False
for line in response.iter_lines():
    if line:
        try:
            line_str = line.decode('utf-8')
        except:
            line_str = str(line)
        if line_str.startswith('event:'):
            print(f"Event: {line_str}", flush=True)
            if 'chart' in line_str:
                has_chart_event = True
        elif 'CHART' in line_str or 'CHART_BLOCK' in line_str:
            print(f"FOUND CHART text: {line_str[:100]}", flush=True)

print(f"\nHas chart event: {has_chart_event}", flush=True)
