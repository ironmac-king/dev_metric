"""
EXNode - SQL 执行节点（Node5）
输入：纠错后的 SQL
输出：{ data, row_count, cached }
职责：
1. 异步 HTTP 请求 StarRocks
2. 结果缓存 Redis
3. 缓存 Key: llm_v1:sql_cache:{SHA256(sql)}，TTL 5分钟
"""
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import httpx

from ..state.session_store import get_session_store

logger = logging.getLogger("ai.llm_v1.ex_node")


@dataclass
class EXOutput:
    """EX 节点输出"""
    data: List[Dict[str, Any]]
    row_count: int
    cached: bool
    columns: List[str]
    sql: str


class EXNode:
    """
    SQL 执行节点（EX - Execute）

    职责：
    1. 异步 HTTP 请求 StarRocks（通过 Go API）
    2. 结果缓存 Redis（Key: llm_v1:sql_cache:{SHA256(sql)}）
    3. TTL: 5分钟
    """

    def __init__(self):
        self._session_store = get_session_store()
        self._redis = None  # TODO: 初始化 Redis
        self._starrocks_api = "http://localhost:8080/api/v1/query/execute"
        self._cache_ttl = 300  # 5分钟

    async def process(
        self,
        sql_output,  # CKOutput
    ) -> EXOutput:
        """
        执行 SQL 查询

        Args:
            sql_output: CK 节点输出的 SQL

        Returns:
            EXOutput: 查询结果
        """
        sql = sql_output.corrected_sql if sql_output.corrected_sql else sql_output.sql
        logger.info(f"[EXNode] 执行 SQL: {sql[:100]}...")

        # Step 1: 检查缓存
        cached_data = self._check_cache(sql)
        if cached_data:
            logger.info("[EXNode] 缓存命中")
            return EXOutput(
                data=cached_data["data"],
                row_count=cached_data["row_count"],
                cached=True,
                columns=cached_data.get("columns", []),
                sql=sql,
            )

        # Step 2: 异步请求 StarRocks
        try:
            result = await self._execute_sql(sql)
            logger.info(f"[EXNode] 查询完成: {result.get('row_count', 0)} 行")
        except Exception as e:
            logger.error(f"[EXNode] 查询失败: {e}")
            # 返回空结果
            result = {
                "data": [],
                "row_count": 0,
                "columns": [],
                "error": str(e),
            }

        # Step 3: 写入缓存
        if result.get("data"):
            self._write_cache(sql, result)

        return EXOutput(
            data=result.get("data", []),
            row_count=result.get("row_count", 0),
            cached=False,
            columns=result.get("columns", []),
            sql=sql,
        )

    def _generate_cache_key(self, sql: str) -> str:
        """生成缓存 Key"""
        sql_hash = hashlib.sha256(sql.encode()).hexdigest()[:16]
        return f"llm_v1:sql_cache:{sql_hash}"

    def _check_cache(self, sql: str) -> Optional[Dict]:
        """检查 Redis 缓存"""
        if not self._redis:
            return None

        try:
            key = self._generate_cache_key(sql)
            data = self._redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"[EXNode] 缓存读取失败: {e}")

        return None

    def _write_cache(self, sql: str, result: Dict):
        """写入 Redis 缓存"""
        if not self._redis:
            return

        try:
            key = self._generate_cache_key(sql)
            self._redis.setex(key, self._cache_ttl, json.dumps(result, ensure_ascii=False))
            logger.info(f"[EXNode] 缓存写入: {key}")
        except Exception as e:
            logger.warning(f"[EXNode] 缓存写入失败: {e}")

    async def _execute_sql(self, sql: str) -> Dict[str, Any]:
        """
        异步请求 StarRocks 执行 SQL

        调用 Go API: POST /api/v1/query/execute
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self._starrocks_api,
                    json={"sql": sql},
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()

                # 解析 Go API 响应格式
                if result.get("code") == 0:
                    data_list = result.get("data", {}).get("data", [])
                    # 从数据中提取列名
                    columns = []
                    if data_list and len(data_list) > 0:
                        columns = list(data_list[0].keys())
                    return {
                        "data": data_list,
                        "row_count": result.get("data", {}).get("count", 0),
                        "columns": columns,
                    }
                else:
                    # API 返回错误
                    logger.error(f"[EXNode] API 错误: {result.get('message')}")
                    return {
                        "data": [],
                        "row_count": 0,
                        "columns": [],
                        "error": result.get("message", "Unknown error"),
                    }

            except httpx.TimeoutException:
                logger.error("[EXNode] 请求超时")
                raise Exception("SQL 执行超时（60秒）")
            except httpx.HTTPStatusError as e:
                logger.error(f"[EXNode] HTTP 错误: {e}")
                raise Exception(f"HTTP 错误: {e.response.status_code}")
            except Exception as e:
                logger.error(f"[EXNode] 执行异常: {e}")
                raise


# 全局实例
_ex_node: Optional[EXNode] = None


def get_ex_node() -> EXNode:
    """获取 EX 节点单例"""
    global _ex_node
    if _ex_node is None:
        _ex_node = EXNode()
    return _ex_node
