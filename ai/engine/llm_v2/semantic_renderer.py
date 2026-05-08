"""
SemanticRenderer - Jinja2 CTE SQL 渲染器

职责：
- 将语义 JSON 渲染为三层 CTE SQL
- 由 sql_generator 调用，不走 LLM
"""
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Any, Dict, List
from datetime import date
import logging

logger = logging.getLogger(__name__)


class SemanticRenderer:
    def __init__(self):
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=False
        )
        self.env.filters["partition_cols"] = self._partition_cols
        self.env.filters["escape"] = self._escape_value

    def _partition_cols(self, dims: List[str]) -> str:
        """将维度列表转为 PARTITION BY 子句"""
        return ", ".join(dims) if dims else "1"

    def _escape_value(self, value: Any) -> str:
        """SQL 单引号转义"""
        if isinstance(value, str):
            return value.replace("'", "''")
        return str(value)

    def _escape_filters(self, filters: List[dict]) -> List[dict]:
        """对 filters 中的 value 做 SQL 转义"""
        return [{**f, "value": self._escape_value(f["value"])} for f in filters]

    def render(self, semantic_json: dict) -> str:
        """
        渲染语义 JSON 为 SQL

        Args:
            semantic_json: 语义 JSON，格式见 plan Phase 3

        Returns:
            SQL 字符串
        """
        template = self.env.get_template("sql_cte_template.sql.j2")
        return template.render(
            tables=semantic_json.get("tables", []),
            dimensions=semantic_json.get("dimensions", []),
            metrics=semantic_json.get("metrics", []),
            filters=self._escape_filters(semantic_json.get("filters", [])),
            calculated_metrics=semantic_json.get("calculated_metrics", []),
            time_params=semantic_json.get("time_params", {}),
            joins=semantic_json.get("joins", []),
            order_by=semantic_json.get("order_by", []),
            limit=semantic_json.get("limit", 1000),
            end_date=self._get_end_date(semantic_json),
            dt_column=semantic_json.get("dt_column", "FDATE"),
        )

    def _get_end_date(self, semantic_json: dict) -> str:
        """从 filters 提取结束日期，兜底返回当前日期"""
        date_fields = {"dt", "fdate", "date", "stat_date"}
        max_date = None

        for f in semantic_json.get("filters", []):
            field = f.get("field", "").lower()
            if field not in date_fields:
                continue

            op = f.get("op", "")
            value = f.get("value", "")

            if op in (">=", "<=", "=") and isinstance(value, str) and len(value) == 10:
                if max_date is None or value > max_date:
                    max_date = value
            elif op.lower() == "between" and isinstance(value, (list, tuple)) and len(value) >= 2:
                end = value[1] if len(value) > 1 else value[0]
                if isinstance(end, str) and len(end) == 10:
                    if max_date is None or end > max_date:
                        max_date = end

        if not max_date:
            max_date = date.today().strftime("%Y-%m-%d")
            logger.warning(f"[SemanticRenderer] 无法从 filters 提取日期，使用当前日期: {max_date}")

        return max_date
