import requests
import re

# First question
resp1 = requests.post(
    'http://localhost:8081/api/v1/llm-ask/v2/stream',
    json={'question': '智能云存储销售额', 'user_id': 'test'},
    stream=True,
    timeout=30
)
content1 = resp1.content.decode('utf-8', errors='replace')
for line in content1.split('\n'):
    if '"step": "intent_router"' in line and '"source":' in line:
        m = re.search(r'"source":\s*"([^"]*)"', line)
        if m:
            print("Q1 source:", m.group(1))
        em = re.search(r'"entities":\s*(\[.*?\])', line)
        if em:
            print("Q1 entities:", em.group(1)[:200])
        break

# Second question (simulate follow-up)
resp2 = requests.post(
    'http://localhost:8081/api/v1/llm-ask/v2/stream',
    json={'question': '智能云存储业绩', 'user_id': 'test', 'session_id': 'test-session'},
    stream=True,
    timeout=30
)
content2 = resp2.content.decode('utf-8', errors='replace')
for line in content2.split('\n'):
    if '"step": "intent_router"' in line and '"source":' in line:
        m = re.search(r'"source":\s*"([^"]*)"', line)
        if m:
            print("Q2 source:", m.group(1))
        em = re.search(r'"entities":\s*(\[.*?\])', line)
        if em:
            print("Q2 entities:", em.group(1)[:200])
        break
