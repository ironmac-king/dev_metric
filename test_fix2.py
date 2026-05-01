import requests
import re

# Fresh question (no session)
resp = requests.post(
    'http://localhost:8081/api/v1/llm-ask/v2/stream',
    json={'question': '智能云存储业绩', 'user_id': 'test'},
    stream=True,
    timeout=30
)
content = resp.content.decode('utf-8', errors='replace')
lines = content.split('\n')
for i, line in enumerate(lines):
    if '"step": "intent_router"' in line and 'source' in line:
        print(f"Line {i}: {line[:400]}")
