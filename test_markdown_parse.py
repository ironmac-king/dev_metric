"""测试 Markdown 流式解析问题"""
import re

def format_result_current(text):
    """当前前端的 formatResult 逻辑"""
    # 替换加粗 **...**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    lines = text.split('\n')
    result = []
    in_table = False

    for i, line in enumerate(lines):
        trimmed = line.strip()

        # 表格检测
        if trimmed.startswith('|') and trimmed.endswith('|'):
            if not in_table:
                result.append('<table class="result-table">')
                in_table = True
            cells = trimmed.split('|')
            cells = [c for c in cells if c.strip() and c.strip() != '---']
            if cells:
                result.append(f'<tr><td>{"</td><td>".join(cells)}</td></tr>')
            continue

        # 表分隔符
        if re.match(r'^\|[\s\-:|]+\|$', trimmed):
            continue

        if in_table:
            result.append('</tbody></table>')
            in_table = False

        # 标题
        if trimmed.startswith('### '):
            result.append(f'<h3>{trimmed[4:]}</h3>')
        elif trimmed.startswith('## '):
            result.append(f'<h2>{trimmed[3:]}</h2>')
        elif trimmed.startswith('# '):
            result.append(f'<h1>{trimmed[2:]}</h1>')
        else:
            result.append(f'<p>{trimmed}</p>')

    if in_table:
        result.append('</tbody></table>')

    return '\n'.join(result)

# 测试流式传输场景：markdown 被拆分成多个 chunk
print("=== Chunk 1: '## 销售数据' ===")
chunk1 = '## 销售数据'
result1 = format_result_current(chunk1)
print(result1)
print()

print("=== Chunk 2: 接收完整文本 '## 销售数据**分析**' ===")
combined = '## 销售数据**分析**'
result2 = format_result_current(combined)
print(result2)
print()

print("=== 关键问题分析 ===")
print("当只有 '## 销售数据' 时：")
print("- 没有 **...** 模式，正则替换无效")
print("- 标题被正确提取为 <h2>")
print()
print("当文本变成 '## 销售数据**分析**' 时：")
print("- 正则替换把 **分析** 变成 <strong>分析</strong>")
print("- 但 '## 销售数据<strong>分析</strong>' 不是有效的标题格式！")
print("- 所以它会被当作普通段落处理")
print()
print("=== 验证 ===")
combined2 = '## 销售数据<strong>分析</strong>'
result3 = format_result_current(combined2)
print(f"输入: {combined2}")
print(f"输出: {result3}")
