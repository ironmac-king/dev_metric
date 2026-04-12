"""测试 SSE 格式"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

def test_current_logic(chunk_text):
    """模拟当前后端逻辑"""
    lines = chunk_text.split('\n')
    data_lines = '\n'.join(f'data: {line}' for line in lines)
    return f'event: chunk\n{data_lines}\n\n'

def test_fixed_logic(chunk_text):
    """模拟修复后的逻辑"""
    lines = chunk_text.split('\n')
    data_lines = '\n'.join(f'data: {line}' if line else 'data:' for line in lines)
    return f'event: chunk\n{data_lines}\n\n'

# 测试：包含空行的 markdown chunk
chunk = '## 销售数据分析\n\n| 指标 | 数值 |\n|-----|-----|\n| 销售额 | ¥799 |'

print("=== 当前逻辑生成的 SSE ===")
result1 = test_current_logic(chunk)
print(result1)

print("\n=== 修复后的 SSE ===")
result2 = test_fixed_logic(chunk)
print(result2)

# 解析测试
print("\n=== 解析当前 SSE ===")
lines = result1.split('\n')
for i, line in enumerate(lines):
    print(f"{i}: {repr(line)}")

print("\n=== 解析修复后的 SSE ===")
lines2 = result2.split('\n')
for i, line in enumerate(lines2):
    print(f"{i}: {repr(line)}")
