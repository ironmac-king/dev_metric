"""
SQL 模板引擎
意图识别 → 模板匹配 → 占位符替换 → 生成 SQL

模块结构:
- templates.py: 模板管理
- matcher.py: 模板匹配
- renderer.py: 占位符替换
- engine.py: 主引擎
- templates.json: SQL 模板配置
"""

from .engine import SQLTemplateEngine, get_engine, generate_sql
from .matcher import TemplateMatcher, get_matcher
from .renderer import TemplateRenderer, get_renderer
from .templates import SQLTemplate, TemplateManager, get_template_manager

__all__ = [
    'SQLTemplateEngine',
    'get_engine',
    'generate_sql',
    'TemplateMatcher',
    'get_matcher',
    'TemplateRenderer',
    'get_renderer',
    'SQLTemplate',
    'TemplateManager',
    'get_template_manager',
]
