import requests
import re

# Q1: 智能云存储销售额
resp1 = requests.post(
    'http://localhost:8081/api/v1/llm-ask/v2/stream',
    json={'question': '智能云存储销售额', 'user_id': 'test'},
    stream=True,
    timeout=30
)
content1 = resp1.content.decode('utf-8', errors='replace')

# Extract session_id
sid_m = re.search(r'"session_id":\s*"([^"]+)"', content1)
session_id = sid_m.group(1) if sid_m else None
print(f"Session ID: {session_id}")

# Find Q1 intent_router source and entities
for line in content1.split('\n'):
    if '"step": "intent_router"' in line and '"source":' in line:
        m = re.search(r'"source":\s*"([^"]*)"', line)
        if m: print(f"Q1 source: {m.group(1)}")
        em = re.search(r'"entities":\s*(\[.*?\])', line)
        if em: print(f"Q1 entities: {em.group(1)[:300]}")
        break

print("---")

# Q2: 智能云存储业绩 (with session)
resp2 = requests.post(
    'http://localhost:8081/api/v1/llm-ask/v2/stream',
    json={'question': '智能云存储业绩', 'user_id': 'test', 'session_id': session_id},
    stream=True,
    timeout=30
)
content2 = resp2.content.decode('utf-8', errors='replace')

# Find Q2 intent_router source and entities
for line in content2.split('\n'):
    if '"step": "intent_router"' in line and '"source":' in line:
        m = re.search(r'"source":\s*"([^"]*)"', line)
        if m: print(f"Q2 source: {m.group(1)}")
        em = re.search(r'"entities":\s*(\[.*?\])', line)
        if em: print(f"Q2 entities: {em.group(1)[:300]}")
        break
