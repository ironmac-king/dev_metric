"""
SQL 模板管理模块
从 JSON 加载 SQL 模板配置，支持从 Go API 加载 (template_type=engine)
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SQLTemplate:
    """SQL 模板"""
    intent: str                    # 意图类型: query_value, query_trend, etc.
    name: str                      # 模板名称
    sql_template: str              # SQL 模板字符串
    description: str = ""          # 描述
    placeholders: List[str] = field(default_factory=list)  # 需要的占位符

    def __post_init__(self):
        # 自动提取占位符
        import re
        self.placeholders = re.findall(r'\{(\w+)\}', self.sql_template)


class TemplateManager:
    """模板管理器"""

    def __init__(self, templates_path: Optional[str] = None, api_base: Optional[str] = None):
        if templates_path is None:
            # 默认路径
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            templates_path = os.path.join(base_dir, 'sql_template_engine', 'templates.json')

        self.templates_path = templates_path
        self.api_base = api_base or os.environ.get("GO_API_BASE", "http://localhost:8080")
        self._templates: Dict[str, List[SQLTemplate]] = {}  # intent -> [templates]
        self._load_templates()

    def _load_templates(self):
        """从 Go API 加载模板（优先），失败则从 JSON 文件加载"""
        # 优先从 Go API 加载 engine 类型模板
        if self._load_from_api():
            return

        # API 加载失败，回退到 JSON 文件
        self._load_from_json()

    def _load_from_api(self) -> bool:
        """从 Go API 加载模板，返回是否成功"""
        try:
            from ai.client.http_client import get_http_client
            client = get_http_client()
            response = client.get(
                f"{self.api_base}/api/v1/nlp/templates",
                params={"type": "engine"},
                timeout=5
            )
            if response.status_code != 200:
                print(f"[TemplateManager] API 返回非 200: {response.status_code}")
                return False

            data = response.json()
            if data.get("code") != 0:
                print(f"[TemplateManager] API 返回错误: {data.get('message')}")
                return False

            sql_templates = data.get("data", {}).get("sql_templates", [])
            if not sql_templates:
                print("[TemplateManager] API 无 engine 类型模板")
                return False

            self._templates = {}
            for tpl_data in sql_templates:
                template = SQLTemplate(
                    intent=tpl_data['intent'],
                    name=tpl_data['name'],
                    sql_template=tpl_data['sql_template'],
                    description=tpl_data.get('description', '')
                )
                if template.intent not in self._templates:
                    self._templates[template.intent] = []
                self._templates[template.intent].append(template)

            print(f"[TemplateManager] 已从 API 加载 {len(sql_templates)} 个 SQL 模板（engine）")
            return True

        except Exception as e:
            print(f"[TemplateManager] API 加载失败: {e}")
            return False

    def _load_from_json(self):
        """从 JSON 文件加载模板"""
        if not os.path.exists(self.templates_path):
            print(f"[TemplateManager] 模板文件不存在: {self.templates_path}")
            self._init_builtin_templates()
            return

        try:
            with open(self.templates_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            templates_data = data.get('templates', [])
            for tpl_data in templates_data:
                template = SQLTemplate(
                    intent=tpl_data['intent'],
                    name=tpl_data['name'],
                    sql_template=tpl_data['sql_template'],
                    description=tpl_data.get('description', '')
                )

                if template.intent not in self._templates:
                    self._templates[template.intent] = []
                self._templates[template.intent].append(template)

            print(f"[TemplateManager] 已从 JSON 加载 {len(templates_data)} 个 SQL 模板")

        except Exception as e:
            print(f"[TemplateManager] 加载模板失败: {e}")
            self._init_builtin_templates()

    def _init_builtin_templates(self):
        """初始化内置模板"""
        self._templates = {
            'query_value': [
                SQLTemplate(
                    intent='query_value',
                    name='基础数值查询',
                    sql_template="""SELECT
    {field},
    dt
FROM {table}
WHERE metric_code = '{metric_code}'
  AND dt BETWEEN '{start_date}' AND '{end_date}'
ORDER BY dt DESC""",
                    description='基础数值查询'
                )
            ],
            'query_trend': [
                SQLTemplate(
                    intent='query_trend',
                    name='趋势查询',
                    sql_template="""SELECT
    dt,
    {field} AS metric_value,
    LAG({field}, 1) OVER (ORDER BY dt) AS prev_value,
    {field} - LAG({field}, 1) OVER (ORDER BY dt) AS diff,
    ROUND(({field} - LAG({field}, 1) OVER (ORDER BY dt)) / NULLIF(LAG({field}, 1) OVER (ORDER BY dt), 0) * 100, 2) AS mom_rate
FROM {table}
WHERE metric_code = '{metric_code}'
  AND dt BETWEEN '{start_date}' AND '{end_date}'
ORDER BY dt DESC""",
                    description='环比趋势查询'
                )
            ],
            'query_comparison': [
                SQLTemplate(
                    intent='query_comparison',
                    name='同比查询',
                    sql_template="""SELECT
    t1.dt AS date,
    t1.{field} AS current_value,
    t2.{field} AS last_year_value,
    t1.{field} - t2.{field} AS diff_value,
    ROUND((t1.{field} - t2.{field}) / NULLIF(t2.{field}, 0) * 100, 2) AS yoy_rate
FROM {table} t1
LEFT JOIN {table} t2
    ON t1.dt = DATE_SUB(t2.dt, INTERVAL 1 YEAR)
    AND t1.metric_code = t2.metric_code
WHERE t1.metric_code = '{metric_code}'
  AND t1.dt BETWEEN '{start_date}' AND '{end_date}'
ORDER BY t1.dt DESC""",
                    description='同比对比查询'
                )
            ],
            'query_ranking': [
                SQLTemplate(
                    intent='query_ranking',
                    name='排名查询',
                    sql_template="""SELECT
    {dimension},
    {field} AS metric_value,
    RANK() OVER (ORDER BY {field} DESC) AS rank_num,
    ROUND({field} / SUM({field}) OVER () * 100, 2) AS pct_of_total
FROM {table}
WHERE metric_code = '{metric_code}'
  AND dt BETWEEN '{start_date}' AND '{end_date}'
GROUP BY {dimension}, {field}
ORDER BY rank_num
LIMIT {top_n}""",
                    description='排名查询，支持下钻维度'
                )
            ]
        }
        print(f"[TemplateManager] 已初始化内置模板")

    def get_templates(self, intent: str) -> List[SQLTemplate]:
        """获取指定意图的模板列表"""
        return self._templates.get(intent, [])

    def get_first_template(self, intent: str) -> Optional[SQLTemplate]:
        """获取指定意图的第一个模板"""
        templates = self.get_templates(intent)
        return templates[0] if templates else None

    def list_intents(self) -> List[str]:
        """列出所有支持的意图类型"""
        return list(self._templates.keys())


# 全局单例
_template_manager: Optional[TemplateManager] = None


def get_template_manager() -> TemplateManager:
    """获取模板管理器单例"""
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager
