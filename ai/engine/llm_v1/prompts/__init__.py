"""
LLM.V1 Prompt 模块
各节点的 Prompt 模板定义
"""
from .lu_prompt import LU_PROMPT
from .sql_prompt import SQL_PROMPT
from .ck_prompt import CK_PROMPT
from .rv_prompt import RV_PROMPT

__all__ = [
    "LU_PROMPT",
    "SQL_PROMPT",
    "CK_PROMPT",
    "RV_PROMPT",
]
