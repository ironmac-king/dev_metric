import requests
import json
import re

# First question
resp1 = requests.post(
    'http://localhost:8081/api/v1/llm-ask/v2/stream',
    json={'question': '智能云存储销售额', 'user_id': 'test'},
    stream=True,
    timeout=30
)
content1 = resp1.content.decode('utf-8', errors='replace')

# Find intent_router thinking event with source
for line in content1.split('\n'):
    if '"step": "intent_router"' in line and '"source":' in line:
        m = re.search(r'"source":\s*"([^"]*)"', line)
        if m:
            print("First question source:", m.group(1))
        # Also find entities
        entities_m = re.search(r'"entities":\s*(\[.*?\])', line)
        if entities_m:
            print("First entities:", entities_m.group(1)[:300])
        break

# Now test: is "智能云存储业绩" considered short followup?
from ai.engine.llm_v2.nodes.intent_router import IntentRouter
router = IntentRouter()
q = "智能云存储业绩"
result = router._is_short_followup(q)
print(f"\n_is_short_followup('{q}'): {result}")

q2 = "智能云存储销售额"
result2 = router._is_short_followup(q2)
print(f"_is_short_followup('{q2}'): {result2}")
