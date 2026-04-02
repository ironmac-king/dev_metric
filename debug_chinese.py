# Debug _chinese_to_int for '十一'
CHINESE_DIGITS = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '零': 0, '两': 2,
}

s = '十一'
print(f'Input: {s}')

chars = []
for c in s:
    if c in CHINESE_DIGITS:
        chars.append(str(CHINESE_DIGITS[c]))
        print(f'  {c} -> {CHINESE_DIGITS[c]} -> appended "{CHINESE_DIGITS[c]}"')
    elif c in '十百千万':
        chars.append(c)
        print(f'  {c} -> appended "ten"')

print(f'Chars: {chars}')

result = 0
current = 0
for i, c in enumerate(chars):
    print(f'  Step {i}: c={c}, current={current}, result={result}')
    if c.isdigit():
        current = current * 10 + int(c)
        print(f'    isdigit: current = {current}')
    elif c == '十':
        result += current * 10
        print(f'    ten: result += {current} * 10 = {current * 10}, result = {result}')
        current = 0
    elif c == '百':
        result += current * 100
        current = 0

result += current
print(f'Final: result={result}')
