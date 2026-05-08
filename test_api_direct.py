"""
直接测试 AI 服务的 API
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import json

url = "http://localhost:8081/api/v1/ask"
data = {
    "question": "上月增长最快的是哪个店铺",
    "session_id": "test-001"
}

try:
    response = requests.post(url, json=data, timeout=60)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
except Exception as e:
    print(f"Error: {e}")