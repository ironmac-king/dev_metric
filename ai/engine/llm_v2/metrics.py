"""
V2 性能监控和埋点

提供：
1. 性能埋点
2. 基准测试
3. 监控面板数据

性能目标：
- 平均响应时间 < 1s
- 95 分位响应时间 < 2s
- 缓存命中率 > 70%
"""
import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_v2.metrics")

# ==================== 性能埋点 ====================

class PerformanceTracker:
    """
    性能追踪器

    追踪：
    - 各节点耗时
    - LLM 调用次数和耗时
    - SQL 执行时间
    - 缓存命中率
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []
        self._max_records = 1000  # 最多保存 1000 条

        # 各节点累计
        self._node_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "count": 0,
            "total_ms": 0,
            "min_ms": float("inf"),
            "max_ms": 0,
        })

        # LLM 调用统计
        self._llm_stats = {
            "call_count": 0,
            "total_ms": 0,
            "error_count": 0,
        }

        # 缓存统计
        self._cache_stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "history_reuse": 0,
        }

        # 语义层统计
        self._semantic_stats = {
            "total_calls": 0,
            "local_model_hits": 0,
            "snapshot_hits": 0,
            "rule_hits": 0,
            "llm_fallback": 0,
            "avg_confidence": 0.0,
            "clarification_count": 0,
        }
        self._semantic_confidence_sum = 0.0

    def record_request(
        self,
        request_id: str,
        session_id: str,
        question: str,
        start_time: float,
        end_time: float,
        success: bool,
        error: str = None,
    ) -> None:
        """记录请求"""
        duration_ms = (end_time - start_time) * 1000

        record = {
            "request_id": request_id,
            "session_id": session_id,
            "question": question[:100],
            "start_time": datetime.fromtimestamp(start_time).isoformat(),
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
        }

        with self._lock:
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records.pop(0)

        logger.info(f"[PerformanceTracker] 请求完成: {request_id}, 耗时 {duration_ms:.0f}ms, success={success}")

    def record_node(
        self,
        node_name: str,
        duration_ms: int,
        success: bool = True,
    ) -> None:
        """记录节点耗时"""
        with self._lock:
            stats = self._node_stats[node_name]
            stats["count"] += 1
            stats["total_ms"] += duration_ms
            stats["min_ms"] = min(stats["min_ms"], duration_ms)
            stats["max_ms"] = max(stats["max_ms"], duration_ms)

    def record_llm_call(self, duration_ms: int, success: bool = True) -> None:
        """记录 LLM 调用"""
        with self._lock:
            self._llm_stats["call_count"] += 1
            self._llm_stats["total_ms"] += duration_ms
            if not success:
                self._llm_stats["error_count"] += 1

    def record_cache_hit(self, level: str) -> None:
        """记录缓存命中"""
        with self._lock:
            if level == "l1":
                self._cache_stats["l1_hits"] += 1
            elif level == "l2":
                self._cache_stats["l2_hits"] += 1
            elif level == "history":
                self._cache_stats["history_reuse"] += 1

    def record_cache_miss(self, level: str) -> None:
        """记录缓存未命中"""
        with self._lock:
            if level == "l1":
                self._cache_stats["l1_misses"] += 1
            elif level == "l2":
                self._cache_stats["l2_misses"] += 1

    def record_semantic_layer(
        self,
        engine: str,
        confidence: float,
        needs_clarification: bool = False,
    ) -> None:
        """记录语义层解析结果

        Args:
            engine: 使用的引擎 (local_model/snapshot/rule/llm)
            confidence: 解析置信度
            needs_clarification: 是否需要追问
        """
        with self._lock:
            self._semantic_stats["total_calls"] += 1
            self._semantic_confidence_sum += confidence

            if engine == "local_model":
                self._semantic_stats["local_model_hits"] += 1
            elif engine == "snapshot":
                self._semantic_stats["snapshot_hits"] += 1
            elif engine == "rule":
                self._semantic_stats["rule_hits"] += 1
            elif engine == "llm":
                self._semantic_stats["llm_fallback"] += 1

            if needs_clarification:
                self._semantic_stats["clarification_count"] += 1

            total = self._semantic_stats["total_calls"]
            if total > 0:
                self._semantic_stats["avg_confidence"] = self._semantic_confidence_sum / total

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            # 计算请求统计
            recent_records = [r for r in self._records if datetime.now() - datetime.fromisoformat(r["start_time"]) < timedelta(hours=1)]

            durations = [r["duration_ms"] for r in recent_records]
            success_count = sum(1 for r in recent_records if r["success"])

            request_stats = {
                "total_requests": len(recent_records),
                "success_count": success_count,
                "success_rate": success_count / len(recent_records) if recent_records else 0,
                "avg_duration_ms": statistics.mean(durations) if durations else 0,
                "p50_duration_ms": statistics.median(durations) if durations else 0,
                "p95_duration_ms": self._percentile(durations, 0.95) if durations else 0,
                "p99_duration_ms": self._percentile(durations, 0.99) if durations else 0,
            }

            # 节点统计
            node_stats = {}
            for node_name, stats in self._node_stats.items():
                if stats["count"] > 0:
                    node_stats[node_name] = {
                        "count": stats["count"],
                        "avg_ms": stats["total_ms"] / stats["count"],
                        "min_ms": stats["min_ms"] if stats["min_ms"] != float("inf") else 0,
                        "max_ms": stats["max_ms"],
                    }

            # LLM 统计
            llm_stats = dict(self._llm_stats)
            if llm_stats["call_count"] > 0:
                llm_stats["avg_ms"] = llm_stats["total_ms"] / llm_stats["call_count"]

            # 缓存统计
            cache_stats = dict(self._cache_stats)
            total_l1 = cache_stats["l1_hits"] + cache_stats["l1_misses"]
            total_l2 = cache_stats["l2_hits"] + cache_stats["l2_misses"]
            cache_stats["l1_hit_rate"] = cache_stats["l1_hits"] / total_l1 if total_l1 > 0 else 0
            cache_stats["l2_hit_rate"] = cache_stats["l2_hits"] / total_l2 if total_l2 > 0 else 0

            # 语义层统计
            semantic_stats = dict(self._semantic_stats)
            total_engine_hits = (
                semantic_stats["local_model_hits"] +
                semantic_stats["snapshot_hits"] +
                semantic_stats["rule_hits"] +
                semantic_stats["llm_fallback"]
            )
            if total_engine_hits > 0:
                semantic_stats["local_model_rate"] = semantic_stats["local_model_hits"] / total_engine_hits
                semantic_stats["snapshot_rate"] = semantic_stats["snapshot_hits"] / total_engine_hits
                semantic_stats["rule_rate"] = semantic_stats["rule_hits"] / total_engine_hits
                semantic_stats["llm_fallback_rate"] = semantic_stats["llm_fallback"] / total_engine_hits

            return {
                "request": request_stats,
                "nodes": node_stats,
                "llm": llm_stats,
                "cache": cache_stats,
                "semantic_layer": semantic_stats,
            }

    def _percentile(self, data: List[float], p: float) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p)
        return sorted_data[min(idx, len(sorted_data) - 1)]

    def reset(self) -> None:
        """重置统计"""
        with self._lock:
            self._records.clear()
            self._node_stats.clear()
            self._llm_stats = {
                "call_count": 0,
                "total_ms": 0,
                "error_count": 0,
            }
            self._cache_stats = {
                "l1_hits": 0,
                "l1_misses": 0,
                "l2_hits": 0,
                "l2_misses": 0,
                "history_reuse": 0,
            }
            self._semantic_stats = {
                "total_calls": 0,
                "local_model_hits": 0,
                "snapshot_hits": 0,
                "rule_hits": 0,
                "llm_fallback": 0,
                "avg_confidence": 0.0,
                "clarification_count": 0,
            }
            self._semantic_confidence_sum = 0.0


# ==================== 基准测试 ====================

class BenchmarkRunner:
    """
    基准测试运行器

    提供：
    - 典型查询基准测试
    - 性能回归检测
    """

    # 典型查询集
    BENCHMARK_QUERIES = [
        # 简单查询 (20 条)
        ("本月销售额是多少", "query_value"),
        ("本月订单量是多少", "query_value"),
        ("本月访客数是多少", "query_value"),
        ("本月转化率是多少", "query_value"),
        ("本月广告花费是多少", "query_value"),
        ("昨天销售额是多少", "query_value"),
        ("上周订单量是多少", "query_value"),
        ("本月销售额趋势", "query_trend"),
        ("本月访客数趋势", "query_trend"),
        ("本月转化率趋势", "query_trend"),
        ("本月各平台销售额", "query_value"),
        ("本月各店铺销售额", "query_value"),
        ("本月各品类销售额", "query_value"),
        ("本月各站点销售额", "query_value"),
        ("本月各渠道销售额", "query_value"),
        ("销售额同比", "query_comparison"),
        ("订单量环比", "query_comparison"),
        ("访客数对比上周", "query_comparison"),
        ("转化率对比上月", "query_comparison"),
        ("广告花费对比上月", "query_comparison"),

        # 中等查询 (20 条)
        ("上月哪个品类卖得好", "query_ranking"),
        ("本月销量排名前十的SKU", "query_ranking"),
        ("本月销售额最高的前10个店铺", "query_ranking"),
        ("本月各平台销售额占比", "query_ratio"),
        ("本月各品类销售额占比", "query_ratio"),
        ("本月各渠道销售额占比", "query_ratio"),
        ("本月各店铺销售额占比", "query_ratio"),
        ("本月各站点销售额同比变化", "query_comparison"),
        ("本月各品类销售额环比变化", "query_comparison"),
        ("本月各平台广告花费占比", "query_ratio"),
        ("本月广告花费占销售额的比例", "query_ratio"),
        ("本月各类目转化率对比", "query_comparison"),
        ("本月各店铺访客数排名", "query_ranking"),
        ("本月各品类访客数占比", "query_ratio"),
        ("本月各渠道订单量占比", "query_ratio"),
        ("本月各平台订单量环比", "query_comparison"),
        ("本月各站点转化率同比", "query_comparison"),
        ("本月各品牌销售额排名前十", "query_ranking"),
        ("本月各产品线销售额占比", "query_ratio"),
        ("本月各类广告花费占比", "query_ratio"),

        # 复杂查询 (10 条)
        ("本月各平台各品类销售额分布", "query_value"),
        ("本月各店铺各品类销售额排名", "query_ranking"),
        ("本月各站点各渠道销售额占比", "query_ratio"),
        ("本月各平台各品类销售额同比变化", "query_comparison"),
        ("本月各品类各周销售额趋势", "query_trend"),
        ("上月各店铺销售额环比变化趋势", "query_trend"),
        ("本月各平台各品类访客数占比分布", "query_ratio"),
        ("上月各站点各渠道订单量占比对比", "query_comparison"),
        ("本月各品类各价格段销售额分布", "query_value"),
        ("上月各品牌各平台销售额排名", "query_ranking"),
    ]

    def __init__(self, tracker: PerformanceTracker):
        self._tracker = tracker

    async def run(self, graph, sample_size: int = None) -> Dict[str, Any]:
        """
        运行基准测试

        Args:
            graph: V2 Graph
            sample_size: 采样数量（默认全部）

        Returns:
            基准测试结果
        """
        queries = self.BENCHMARK_QUERIES
        if sample_size:
            queries = queries[:sample_size]

        logger.info(f"[BenchmarkRunner] 开始基准测试，共 {len(queries)} 条查询")

        results = []
        success_count = 0
        failure_count = 0

        for i, (question, expected_intent) in enumerate(queries):
            try:
                start_time = time.time()

                # 执行查询
                from ai.engine.llm_v2.schema import create_v2_state
                state = create_v2_state(
                    question=question,
                    session_id=f"benchmark_{i}",
                )

                result = await graph.ainvoke(state)

                duration_ms = (time.time() - start_time) * 1000

                # 判断是否成功
                success = result.answer and not result.error

                # 记录结果
                results.append({
                    "question": question,
                    "expected_intent": expected_intent,
                    "actual_intent": result.mql.intent.value if result.mql else "unknown",
                    "duration_ms": duration_ms,
                    "success": success,
                    "error": result.error,
                })

                if success:
                    success_count += 1
                else:
                    failure_count += 1

                logger.info(f"[BenchmarkRunner] [{i+1}/{len(queries)}] {question[:30]}... -> {'✓' if success else '✗'} ({duration_ms:.0f}ms)")

            except Exception as e:
                logger.error(f"[BenchmarkRunner] [{i+1}/{len(queries)}] {question[:30]}... -> 异常: {e}")
                failure_count += 1
                results.append({
                    "question": question,
                    "expected_intent": expected_intent,
                    "duration_ms": 0,
                    "success": False,
                    "error": str(e),
                })

        # 计算统计
        durations = [r["duration_ms"] for r in results if r["success"]]
        accuracy = success_count / len(queries) if queries else 0

        return {
            "total": len(queries),
            "success": success_count,
            "failure": failure_count,
            "accuracy": accuracy,
            "avg_duration_ms": statistics.mean(durations) if durations else 0,
            "p50_duration_ms": statistics.median(durations) if durations else 0,
            "p95_duration_ms": self._percentile(durations, 0.95) if durations else 0,
            "results": results,
        }

    def _percentile(self, data: List[float], p: float) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p)
        return sorted_data[min(idx, len(sorted_data) - 1)]


# ==================== 全局实例 ====================

_performance_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """获取性能追踪器单例"""
    global _performance_tracker
    if _performance_tracker is None:
        _performance_tracker = PerformanceTracker()
    return _performance_tracker
