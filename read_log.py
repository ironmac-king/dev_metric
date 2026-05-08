with open('/tmp/ai_service.log', 'rb') as f:
    content = f.read()

try:
    text = content.decode('utf-8')
except:
    try:
        text = content.decode('gbk')
    except:
        text = content.decode('latin1', errors='ignore')

lines = text.split('\n')
for line in lines:
    if '_build_value_sql' in line or 'sql_result' in line or '追问' in line or 'time_range' in line:
        print(line)
