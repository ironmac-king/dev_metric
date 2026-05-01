import requests
import re

resp1 = requests.post(
    'http://localhost:8081/api/v1/llm-ask/v2/stream',
    json={'question': '智能云存储销售额', 'user_id': 'test'},
    stream=True,
    timeout=30
)
content1 = resp1.content.decode('utf-8', errors='replace')

sid_m = re.search(r'"session_id":\s*"([^"]+)"', content1)
session_id = sid_m.group(1) if sid_m else None
print(f"Session ID: {session_id}")

# Print ALL lines with source
print("\n=== Q1 source lines ===")
for i, line in enumerate(content1.split('\n')):
    if '"source":' in line:
        print(f"Q1 Line {i}: {line[:400]}")

resp2 = requests.post(
    'http://localhost:8081/api/v1/llm-ask/v2/stream',
    json={'question': '智能云存储业绩', 'user_id': 'test', 'session_id': session_id},
    stream=True,
    timeout=30
)
content2 = resp2.content.decode('utf-8', errors='replace')

print("\n=== Q2 source lines ===")
for i, line in enumerate(content2.split('\n')):
    if '"source":' in line:
        print(f"Q2 Line {i}: {line[:400]}")
