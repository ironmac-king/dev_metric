# -*- coding: utf-8 -*-
import re

# 用户实际输入（"那个"不是"哪个"）
text = "上月那个品类卖的比较好啊"
print('Text:', text)

# 检测"比较好"
has_better_keyword = re.search(r'比较[好差]', text)
print('\nhas_better_keyword (比较[好差]):', has_better_keyword)
if has_better_keyword:
    print('  matched:', has_better_keyword.group(0))

# 检测维度词
dimension_words = ['品', '类', '店', '铺', '品', '牌', '道', '路', '区', '域', '台', '站', '国', '家', '客', '户', '商', 'ASIN', 'SKU']
has_dimension_word = any(dim in text for dim in dimension_words)
print('\nhas_dimension_word:', has_dimension_word)

# 检查哪些维度词在text中
found_dims = [dim for dim in dimension_words if dim in text]
print('found_dims:', found_dims)

# 完整条件
if has_better_keyword and has_dimension_word:
    print('\n条件满足，会触发ranking override')
else:
    print('\n条件不满足')
    print('  - has_better_keyword:', bool(has_better_keyword))
    print('  - has_dimension_word:', has_dimension_word)
