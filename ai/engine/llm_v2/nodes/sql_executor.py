"""
步骤 8: SQL 执行节点

职责：
- 执行 SQL 查询
- 返回查询结果
- 应用行级权限过滤
"""
import time
from typing import Dict, Any, Optional
from ai.config.logging_config import get_logger
from ..schema import MQLSchema, SQLResult
from ..permission import RowLevelPermission

logger = get_logger("ai.llm_v2.sql_executor")


class SQLExecutor:
    """
    SQL 执行器

    执行 SQL 查询并返回结果。
    """

    def __init__(self, permission: RowLevelPermission = None):
        self._timeout = 60  # 超时 60 秒
        self._permission = permission

    def set_permission(self, permission: RowLevelPermission) -> None:
        """设置权限控制器"""
        self._permission = permission

    async def execute(
        self,
        sql: str,
        mql: MQLSchema = None,
        user_id: str = None,
    ) -> SQLResult:
        """
        执行 SQL

        Args:
            sql: SQL 语句
            mql: MQL Schema（用于补充信息）
            user_id: 用户 ID（用于权限过滤）

        Returns:
            SQLResult 实例
        """
        # 应用行级权限过滤
        if user_id and self._permission:
            sql = self._permission.filter_sql(sql, user_id)
            logger.info(f"[SQLExecutor] 权限过滤后 SQL: {sql[:100]}...")

        logger.info(f"[SQLExecutor] 执行 SQL: {sql[:100]}...")

        result = SQLResult(sql=sql)
        start_time = time.time()

        try:
            # 1. 调用 Go 后端执行 SQL
            response = await self._execute_via_go_api(sql)

            # 2. 解析响应
            if response.get("code") == 0:
                data = response.get("data", {})
                result.data = data.get("data", [])
                result.total = data.get("count", len(result.data))
                result.executed = True
                result.execution_time_ms = int((time.time() - start_time) * 1000)

                logger.info(f"[SQLExecutor] 查询成功，返回 {len(result.data)} 条数据")
            else:
                result.error = response.get("message", "查询失败")
                logger.error(f"[SQLExecutor] 查询失败: {result.error}")

        except Exception as e:
            result.error = str(e)
            logger.error(f"[SQLExecutor] 执行异常: {e}")

        result.execution_time_ms = int((time.time() - start_time) * 1000)
        return result

    async def _execute_via_go_api(self, sql: str) -> Dict[str, Any]:
        """
        通过 Go 后端 API 执行 SQL

        Args:
            sql: SQL 语句

        Returns:
            API 响应
        """
        import httpx

        go_api_base = "http://localhost:8080"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{go_api_base}/api/v1/query/execute",
                    json={"sql": sql, "timeout": self._timeout},
                )
                return response.json()
        except httpx.TimeoutException:
            logger.error(f"[SQLExecutor] 请求超时: {self._timeout}s")
            return {"code": 500, "message": f"查询超时（{self._timeout}s）"}
        except Exception as e:
            logger.error(f"[SQLExecutor] HTTP 请求失败: {e}")
            return {"code": 500, "message": str(e)}

    async def execute_comparison(
        self,
        sql: str,
        compare_period_start: str,
        compare_period_end: str,
    ) -> SQLResult:
        """
        执行对比 SQL（同比/环比）

        Args:
            sql: 原始 SQL
            compare_period_start: 对比期开始
            compare_period_end: 对比期结束

        Returns:
            SQLResult
        """
        import re

        # 替换时间条件
        def replace_date_condition(sql: str, start: str, end: str) -> str:
            # 替换 FDATE >= '...'
            sql = re.sub(
                r"FDATE\s*>=\s*'[^']*'",
                f"FDATE >= '{start}'",
                sql,
                flags=re.IGNORECASE
            )
            # 替换 FDATE <= '...'
            sql = re.sub(
                r"FDATE\s*<=\s*'[^']*'",
                f"FDATE <= '{end}'",
                sql,
                flags=re.IGNORECASE
            )
            return sql

        # 移除 LIMIT
        sql = re.sub(r'\s+LIMIT\s+\d+', '', sql, flags=re.IGNORECASE)

        # 构建对比 SQL
        comparison_sql = replace_date_condition(sql, compare_period_start, compare_period_end)

        return await self.execute(comparison_sql)
