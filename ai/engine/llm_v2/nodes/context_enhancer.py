"""
步骤 2: 上下文增强节点（RAG）

职责：
- 从历史查询中检索相似案例
- 增强当前查询上下文
- 提供 RAG 上下文给 MQL 生成
"""
from typing import Dict, Any, List, Optional
from ai.config.logging_config import get_logger
from ..schema import MQLSchema, MQLMetric, MQLDimension
from ..rag import rag_retrieve, rag_index

logger = get_logger("ai.llm_v2.context_enhancer")


class ContextEnhancer:
    """
    上下文增强节点

    使用 RAG（检索增强生成）从历史查询中检索相似案例，
    增强 MQL 生成的上下文。
    """

    def __init__(self):
        self._similarity_threshold = 0.7  # 相似度阈值
        self._top_k = 3  # 返回 top-k 相似案例

    async def enhance(
        self,
        question: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        增强上下文

        Args:
            question: 当前问题
            context: 当前上下文（metric, time, dimensions 等）

        Returns:
            {
                "similar_cases": [...],  # 相似案例列表
                "suggested_mql": MQLSchema,  # 建议的 MQL
            }
        """
        logger.info(f"[ContextEnhancer] 增强上下文: {question[:50]}...")

        # 1. RAG 检索相似案例
        similar_cases = await rag_retrieve(question, top_k=self._top_k)

        # 2. 构建增强上下文
        enhanced_context = {
            "similar_cases": similar_cases,
            "suggested_mql": None,
        }

        # 3. 如果有高相似度案例，建议复用
        if similar_cases and similar_cases[0].get("similarity", 0) > 0.85:
            mql_data = similar_cases[0].get("metadata", {}).get("mql")
            if mql_data:
                try:
                    suggested_mql = MQLSchema.from_dict(mql_data)
                    enhanced_context["suggested_mql"] = suggested_mql
                    logger.info(f"[ContextEnhancer] 高相似度匹配: similarity={similar_cases[0]['similarity']:.2f}")
                except Exception as e:
                    logger.warning(f"[ContextEnhancer] MQL 解析失败: {e}")

        return enhanced_context

    async def _retrieve_similar_cases(self, question: str) -> List[Dict[str, Any]]:
        """
        检索相似案例

        使用 RAG 从向量数据库检索相似历史查询。
        """
        try:
            results = await rag_retrieve(question, top_k=self._top_k)
            return results
        except Exception as e:
            logger.error(f"[ContextEnhancer] RAG 检索失败: {e}")
            return []

    async def _build_rag_context(
        self,
        similar_cases: List[Dict[str, Any]],
        current_context: Dict[str, Any],
    ) -> str:
        """
        构建 RAG 上下文字符串

        Args:
            similar_cases: 相似案例列表
            current_context: 当前上下文

        Returns:
            RAG 上下文字符串
        """
        context_parts = []

        # 添加相似案例
        if similar_cases:
            context_parts.append("【相似案例】")
            for i, case in enumerate(similar_cases[:3], 1):
                similarity = case.get("similarity", 0)
                context_parts.append(f"\n案例 {i} (相似度: {similarity:.2f}):")
                context_parts.append(f"  问题: {case.get('text', '')}")
                metadata = case.get("metadata", {})
                if metadata:
                    mql_data = metadata.get("mql", {})
                    if mql_data:
                        context_parts.append(f"  指标: {mql_data.get('metric', {}).get('name', 'N/A')}")
                        context_parts.append(f"  时间: {mql_data.get('time', {}).get('original', 'N/A')}")
                        context_parts.append(f"  SQL: {metadata.get('sql', 'N/A')}")

        # 添加当前上下文
        if current_context:
            context_parts.append("\n【当前上下文】")
            if current_context.get("metric"):
                metric = current_context["metric"]
                if isinstance(metric, MQLMetric):
                    context_parts.append(f"  指标: {metric.name} ({metric.code})")
                elif isinstance(metric, dict):
                    context_parts.append(f"  指标: {metric.get('name', '')} ({metric.get('code', '')})")

            if current_context.get("time"):
                time_obj = current_context["time"]
                if hasattr(time_obj, "original"):
                    context_parts.append(f"  时间: {time_obj.original}")
                else:
                    context_parts.append(f"  时间: {time_obj}")

            if current_context.get("dimensions"):
                dims = current_context["dimensions"]
                if dims:
                    dim_names = []
                    for d in dims:
                        if isinstance(d, MQLDimension):
                            dim_names.append(d.type)
                        elif isinstance(d, dict):
                            dim_names.append(d.get("type", ""))
                    context_parts.append(f"  维度: {', '.join(dim_names)}")

        return "\n".join(context_parts) if context_parts else ""

    async def index_success_case(
        self,
        question: str,
        mql: MQLSchema,
        sql: str,
    ) -> bool:
        """
        索引成功的查询案例

        Args:
            question: 用户问题
            mql: 生成的 MQL
            sql: 生成的 SQL

        Returns:
            是否成功
        """
        try:
            mql_dict = mql.to_dict() if mql else {}
            return await rag_index(question, mql_dict, sql)
        except Exception as e:
            logger.error(f"[ContextEnhancer] 索引失败: {e}")
            return False


def get_context_enhancer() -> ContextEnhancer:
    """获取 ContextEnhancer 单例"""
    return ContextEnhancer()
