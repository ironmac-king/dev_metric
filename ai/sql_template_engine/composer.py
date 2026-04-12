"""片段组装器"""
from typing import List, Dict, Any
from .fragments.base import SQLFragment


class FragmentComposer:
    """片段组装器"""

    def __init__(self):
        self.fragments: List[SQLFragment] = []

    def add(self, fragment: SQLFragment) -> "FragmentComposer":
        """添加片段，支持链式调用"""
        self.fragments.append(fragment)
        return self

    def render(self, context: Dict[str, Any]) -> str:
        """渲染所有片段为完整 SQL"""
        parts = []
        for f in self.fragments:
            rendered = f.render(context)
            if rendered:
                parts.append(rendered)
        return "\n".join(parts)

    def clear(self) -> "FragmentComposer":
        """清空所有片段"""
        self.fragments = []
        return self
