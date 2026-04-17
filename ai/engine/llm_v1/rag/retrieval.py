"""
Retrieval - RAG 检索增强
对检索结果进行重排序和过滤
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("ai.llm_v1.retrieval")


@dataclass
class RetrievalResult:
    """检索结果"""
    content: Any  # 检索到的内容
    score: float  # 相似度分数
    metadata: Dict[str, Any] = None  # 元数据


class Retrieval:
    """
    RAG 检索增强

    职责：
    1. 对多路检索结果进行融合
    2. 重排序（Rerank）
    3. 去重和过滤
    4. 上下文窗口控制
    """

    def __init__(self):
        self._similarity_threshold = 0.25  # 相似度阈值

    def retrieve_and_rerank(
        self,
        query: str,
        retrieval_results: List[RetrievalResult],
        top_k: int = 5,
        enable_rerank: bool = True,
    ) -> List[RetrievalResult]:
        """
        检索并重排序

        Args:
            query: 查询文本
            retrieval_results: 多路检索结果
            top_k: 返回数量
            enable_rerank: 是否启用重排序

        Returns:
            重排序后的结果
        """
        if not retrieval_results:
            return []

        # 1. 过滤低相似度结果
        filtered = [
            r for r in retrieval_results
            if r.score >= self._similarity_threshold
        ]

        if not filtered:
            logger.info(f"[Retrieval] 无高于阈值 {self._similarity_threshold} 的结果")
            return []

        # 2. 去重（基于内容哈希）
        deduplicated = self._deduplicate(filtered)

        # 3. 重排序（TODO: 后续实现更复杂的重排序策略）
        if enable_rerank:
            deduplicated.sort(key=lambda x: x.score, reverse=True)

        return deduplicated[:top_k]

    def _deduplicate(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """去重"""
        seen = set()
        deduplicated = []

        for r in results:
            # 使用内容的字符串表示作为去重 key
            content_key = str(r.content)
            if content_key not in seen:
                seen.add(content_key)
                deduplicated.append(r)

        return deduplicated

    def build_context_from_results(
        self,
        results: List[RetrievalResult],
        max_length: int = 4000,
    ) -> str:
        """
        从检索结果构建上下文文本

        Args:
            results: 检索结果
            max_length: 最大长度

        Returns:
            格式化的上下文文本
        """
        if not results:
            return ""

        context_parts = ["=== 相关上下文 ==="]

        total_length = 0
        for i, r in enumerate(results, 1):
            content_str = str(r.content)
            # 简单截断，避免超出长度
            if total_length + len(content_str) > max_length:
                remaining = max_length - total_length
                if remaining > 100:
                    content_str = content_str[:remaining] + "..."
                else:
                    break

            context_parts.append(f"\n--- 结果{i} (相似度: {r.score:.2f}) ---")
            context_parts.append(content_str)
            total_length += len(content_str)

        return "\n".join(context_parts)


# 全局实例
_retrieval: Optional[Retrieval] = None


def get_retrieval() -> Retrieval:
    """获取 Retrieval 实例"""
    global _retrieval
    if _retrieval is None:
        _retrieval = Retrieval()
    return _retrieval
