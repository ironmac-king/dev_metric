"""
SQL 模板渲染器
替换占位符，生成完整 SQL
"""

import re
from typing import Any, Dict, Optional

from .templates import SQLTemplate


class TemplateRenderer:
    """模板渲染器"""

    def __init__(self):
        pass

    def render(self, template: SQLTemplate, context: Dict[str, Any]) -> str:
        """
        渲染 SQL 模板，替换占位符

        Args:
            template: SQL 模板
            context: 上下文数据，包含占位符的值

        Returns:
            渲染后的完整 SQL
        """
        sql = template.sql_template

        # 替换每个占位符
        for placeholder in template.placeholders:
            value = self._get_value(context, placeholder)
            if value is None:
                # 占位符没有提供值，使用默认值
                value = self._get_default_value(placeholder)
                print(f"[TemplateRenderer] 占位符 {{{placeholder}}} 使用默认值: {value}")

            # 替换占位符
            sql = sql.replace(f'{{{placeholder}}}', str(value))

        return sql

    def _get_value(self, context: Dict[str, Any], key: str) -> Optional[str]:
        """从上下文获取值"""
        # 支持多层级的 key，如 "metric.starrocks_sql"
        keys = key.split('.')
        value = context

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

            if value is None:
                return None

        return str(value) if value is not None else None

    def _get_default_value(self, key: str) -> str:
        """获取占位符的默认值"""
        defaults = {
            'metric_code': 'UNKNOWN',
            'field': '*',
            'table': 'metric_table',
            'start_date': '2026-01-01',
            'end_date': '2026-04-12',
            'dimension': 'dt',
            'top_n': '10',
            'start_date_comp': '2025-01-01',
            'end_date_comp': '2025-04-12',
        }
        return defaults.get(key, '')

    def render_drill_down(self, template: SQLTemplate, context: Dict[str, Any], extra_dims: list) -> str:
        """
        渲染下钻 SQL，{dimension} 替换为多个维度

        Args:
            template: SQL 模板
            context: 上下文数据
            extra_dims: 额外的下钻维度列表

        Returns:
            渲染后的 SQL
        """
        # 合并维度
        original_dim = context.get('dimension', 'dt')
        all_dims = [original_dim] + extra_dims
        context['dimension'] = ', '.join(all_dims)

        return self.render(template, context)


# 全局单例
_renderer: Optional[TemplateRenderer] = None


def get_renderer() -> TemplateRenderer:
    """获取渲染器单例"""
    global _renderer
    if _renderer is None:
        _renderer = TemplateRenderer()
    return _renderer
