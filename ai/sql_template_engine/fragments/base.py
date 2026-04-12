"""SQL 片段基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class SQLFragment(ABC):
    """SQL 片段基类"""

    @abstractmethod
    def render(self, context: Dict[str, Any]) -> str:
        """渲染片段为 SQL 字符串"""

    def required_context(self) -> List[str]:
        """返回渲染所需的最少 context 键"""
        return []
