"""
SQL 生成器 - 优化版
支持元数据查询和数值查询，带缓存
"""
from typing import Dict, Any, Optional
import httpx
from ai.sql_gen.cache import get_sql_cache


class SQLGenerator:
    """SQL 生成和执行"""

    def __init__(self, api_base: str = "http://localhost:8080", use_cache: bool = True):
        self.api_base = api_base
        self.use_cache = use_cache
        self._cache = get_sql_cache()

    async def execute(self, sql: str, params: Dict[str, Any],
                     dept_id: int = 0, data_filter: str = "") -> Any:
        """执行 SQL 查询（StarRocks），带缓存"""
        # 应用数据权限过滤
        sql = self.apply_data_filter(sql, dept_id, data_filter)

        # 检查缓存
        if self.use_cache:
            cached_result = self._cache.get(sql)
            if cached_result is not None:
                return cached_result

        # 执行查询
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/api/v1/query/execute",
                json={"sql": sql, "params": params},
                timeout=30.0
            )
            if response.status_code != 200:
                raise Exception(f"查询失败: {response.text}")
            result = response.json()

        # 写入缓存
        if self.use_cache:
            self._cache.set(sql, result)

        return result

    def apply_data_filter(self, sql: str, dept_id: int = 0, data_filter: str = "") -> str:
        """
        应用数据权限过滤：dept_id + 自定义 data_filter
        拼接到 SQL WHERE 条件后面
        """
        filters = []

        # 1. dept_id 强制过滤（如果存在）
        if dept_id and dept_id > 0:
            if "where" in sql.lower():
                filters.append(f"dept_id = {dept_id}")
            else:
                filters.append(f"WHERE dept_id = {dept_id}")

        # 2. 自定义 data_filter 条件
        if data_filter and data_filter.strip():
            # 安全检查：确保 data_filter 不包含危险关键字
            dangerous = ["drop", "delete", "update", "insert", "truncate",
                        "alter", "create", "grant", "revoke", "exec", "execute"]
            filter_lower = data_filter.lower()
            for kw in dangerous:
                if kw in filter_lower:
                    # 跳过危险filter，防止SQL注入
                    return sql
            filters.append(f"({data_filter})")

        if not filters:
            return sql

        # 拼接到 SQL 末尾
        if "where" in sql.lower():
            return f"{sql} AND {' AND '.join(filters)}"
        else:
            # 没有 WHERE 子句，在 FROM 后面加 WHERE
            parts = sql.split("FROM", 1)
            if len(parts) == 2:
                return f"{parts[0]}FROM{parts[1]} WHERE {' AND '.join(filters)}"
        return sql

    def query_metadata(self, metric_name: str = None, metric_code: str = None) -> Dict[str, Any]:
        """查询指标元数据（从 PostgreSQL）"""
        import httpx

        with httpx.Client(timeout=10.0) as client:
            # 获取所有指标
            response = client.get(f"{self.api_base}/api/v1/metadata/metrics")
            if response.status_code != 200:
                raise Exception(f"获取指标列表失败: {response.text}")

            data = response.json()
            metrics = data.get("data", []) if isinstance(data, dict) else data

            # 按名称或编号查找
            for m in metrics:
                if metric_name and (m.get("name") == metric_name or m.get("name_en", "").lower() == metric_name.lower()):
                    return self._format_metric_info(m)
                if metric_code and m.get("metric_code") == metric_code:
                    return self._format_metric_info(m)

            # 如果没找到指定指标，返回所有指标让调用方选择
            if not metric_name and not metric_code:
                return {"metrics": metrics[:10], "type": "list"}

            return {"error": f"未找到指标: {metric_name or metric_code}", "type": "error"}

    def _format_metric_info(self, metric: Dict[str, Any]) -> Dict[str, Any]:
        """格式化指标信息"""
        return {
            "type": "metric_info",
            "metric_code": metric.get("metric_code"),
            "metric_name": metric.get("name"),
            "domain": metric.get("domain"),
            "category_1": metric.get("category_1"),
            "business_definition": metric.get("business_definition"),
            "business_rule": metric.get("business_rule"),
            "technical_rule": metric.get("technical_rule"),
            "unit": metric.get("unit"),
            "frequency": metric.get("frequency"),
            "starrocks_sql": metric.get("starrocks_sql"),
        }


class SQLValidator:
    """SQL 安全校验"""

    FORBIDDEN_KEYWORDS = [
        "drop", "delete", "update", "insert", "truncate",
        "alter", "create", "grant", "revoke", "exec", "execute"
    ]

    def validate(self, sql: str) -> bool:
        """校验 SQL 安全性"""
        import re
        sql_lower = sql.lower()

        # 去除注释和字符串字面量后再检查
        # 去除单行注释 --
        sql_clean = re.sub(r'--.*$', '', sql_lower, flags=re.MULTILINE)
        # 去除多行注释 /* */
        sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)
        # 去除字符串字面量 '...' 和 "..."
        sql_clean = re.sub(r"'(?:[^']|'')*'", "''", sql_clean)
        sql_clean = re.sub(r'"(?:[^"]|"")*"', '""', sql_clean)

        # 检查禁止关键字（考虑大小写混淆）
        forbidden_patterns = [
            r'\bdrop\b', r'\bdelete\b', r'\bupdate\b', r'\binsert\b',
            r'\btruncate\b', r'\balter\b', r'\bcreate\b', r'\bgrant\b',
            r'\brevoke\b', r'\bexec\b', r'\bexecute\b', r'\bsp_executesql\b',
            r'\bxp_cmdshell\b', r'\bopenrowset\b', r'\bopendatasource\b'
        ]

        for pattern in forbidden_patterns:
            if re.search(pattern, sql_clean, re.IGNORECASE):
                return False

        return True

    def enforce_dept_filter(self, sql: str, dept_id: int) -> str:
        """强制注入部门权限"""
        # 安全校验：dept_id 必须是正整数
        if not isinstance(dept_id, int) or dept_id <= 0:
            return sql  # 无效的 dept_id，不修改 SQL

        if "where" in sql.lower():
            return f"{sql} AND dept_id = {dept_id}"
        return f"{sql} WHERE dept_id = {dept_id}"
