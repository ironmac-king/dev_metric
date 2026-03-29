import httpx
import json

client = httpx.Client(timeout=30)

# Test 1: Ask "销售额"
print("=" * 50)
print("Test 1: 销售额")
resp = client.post('http://localhost:8081/api/v1/ask', json={'question': '销售额'})
print(f"Status: {resp.status_code}")
print(f"Response: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
