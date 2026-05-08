"""
SQL 安全校验 - 统一入口

所有 SQL 注入防护逻辑集中在此处，其他模块统一 import 这里，
避免 generator.py / sql_generator.py 中各自维护不一致的黑名单。
"""
import re

# 预编译：去除注释与字符串字面量的正则
_RE_SINGLE_COMMENT = re.compile(r'--.*$', re.MULTILINE)
_RE_MULTI_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
_RE_SINGLE_QUOTE = re.compile(r"'(?:[^']|'')*'")
_RE_DOUBLE_QUOTE = re.compile(r'"(?:[^"]|"")*"')

# 预编译：禁止的 DDL/DML/系统调用关键字（使用词边界，覆盖高级注入技法）
_FORBIDDEN_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    r'\bdrop\b', r'\bdelete\b', r'\bupdate\b', r'\binsert\b',
    r'\btruncate\b', r'\balter\b', r'\bcreate\b', r'\bgrant\b',
    r'\brevoke\b', r'\bexec\b', r'\bexecute\b', r'\bsp_executesql\b',
    r'\bxp_cmdshell\b', r'\bopenrowset\b', r'\bopendatasource\b',
]]


def validate_sql(sql: str) -> bool:
    """校验 SQL 是否安全（只允许 SELECT 类查询）

    先去除注释和字符串字面量，再检查禁止关键字，
    防止注释包裹或大小写混淆绕过检测。

    Returns:
        True 表示安全，False 表示包含危险关键字
    """
    clean = _RE_SINGLE_COMMENT.sub('', sql)
    clean = _RE_MULTI_COMMENT.sub('', clean)
    clean = _RE_SINGLE_QUOTE.sub("''", clean)
    clean = _RE_DOUBLE_QUOTE.sub('""', clean)
    return not any(p.search(clean) for p in _FORBIDDEN_PATTERNS)


def validate_data_filter(data_filter: str) -> bool:
    """校验用户传入的 data_filter 条件字符串是否安全"""
    return validate_sql(data_filter)
