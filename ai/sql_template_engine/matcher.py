"""
SQL 模板匹配器
根据意图类型匹配对应模板
"""

from typing import Optional

from .templates import SQLTemplate, get_template_manager


class TemplateMatcher:
    """模板匹配器"""

    def __init__(self):
        self.manager = get_template_manager()

    def match(self, intent: str) -> Optional[SQLTemplate]:
        """
        根据意图类型匹配模板

        Args:
            intent: 意图类型 (query_value, query_trend, query_comparison, query_ranking)

        Returns:
            匹配的模板，如果没有则返回 None
        """
        if not intent:
            return None

        return self.manager.get_first_template(intent)

    def match_with_fallback(self, intent: str) -> Optional[SQLTemplate]:
        """
        匹配模板，fallback 到 query_value

        Args:
            intent: 意图类型

        Returns:
            匹配的模板，fallback 到 query_value
        """
        template = self.match(intent)
        if template:
            return template

        # Fallback 到 query_value
        print(f"[TemplateMatcher] 未找到 intent={intent} 的模板，fallback 到 query_value")
        return self.match('query_value')


# 全局单例
_matcher: Optional[TemplateMatcher] = None


def get_matcher() -> TemplateMatcher:
    """获取匹配器单例"""
    global _matcher
    if _matcher is None:
        _matcher = TemplateMatcher()
    return _matcher
