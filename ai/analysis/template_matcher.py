"""
模板匹配器 - 基于 Embedding 向量相似度匹配模板
"""
from typing import Dict, List, Optional, Any, Tuple
import httpx
import json
import os
import numpy as np
from dataclasses import dataclass
from ai.config.runtime import get_go_api_base


@dataclass
class MatchResult:
    """匹配结果"""
    template: Optional[Dict[str, Any]]
    confidence: float
    matched_reason: str = ""
    needs_confirmation: bool = False
    candidates: List[Dict] = None


class TemplateMatcher:
    """决策分析模板匹配器"""

    HIGH_THRESHOLD = 0.85   # >0.85 直接确认
    LOW_THRESHOLD = 0.25    # <0.25 追问用户

    def __init__(self, api_base: str = None):
        self.api_base = api_base or get_go_api_base()
        self._embeddings_cache: Dict[int, np.ndarray] = {}
        self._initialized = False

    async def _get_embeddings_batch(self, texts: List[str]) -> Dict[int, Optional[List[float]]]:
        """批量获取文本的 embedding 向量

        Returns:
            Dict[int, Optional[List[float]]]: 索引到 embedding 向量的映射
        """
        if not texts:
            return {}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base}/api/v1/nlp/generate-embeddings",
                    json={"texts": texts}
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        embeddings_list = data.get("data", [])
                        result = {}
                        for i, emb_data in enumerate(embeddings_list):
                            if emb_data and "embedding" in emb_data:
                                result[i] = emb_data["embedding"]
                            else:
                                result[i] = None
                        return result
        except Exception as e:
            print(f"[TemplateMatcher] 批量获取 embedding 失败: {e}")
        return {i: None for i in range(len(texts))}

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def _build_query_text(self, query: str, context: Dict) -> str:
        """构建查询文本"""
        parts = [query]
        if context.get("metric_name"):
            parts.append(str(context["metric_name"]))
        if context.get("metric_code"):
            parts.append(str(context["metric_code"]))
        return " ".join(parts)

    async def match(
        self,
        query: str,
        context: Dict,
        templates: List[Dict[str, Any]]
    ) -> MatchResult:
        """
        匹配最合适的模板

        Args:
            query: 用户查询
            context: 上下文信息（metric_name, metric_code 等）
            templates: 可用模板列表

        Returns:
            MatchResult
        """
        if not templates:
            return MatchResult(
                template=None,
                confidence=0,
                matched_reason="无可用模板",
                needs_confirmation=True
            )

        # 构建查询文本
        query_text = self._build_query_text(query, context)

        # 获取查询向量
        query_embeddings_map = await self._get_embeddings_batch([query_text])
        query_embedding = query_embeddings_map.get(0)
        if not query_embedding:
            # 无法获取 embedding，使用关键词匹配降级
            return self._fallback_keyword_match(query_text, templates)

        # 批量获取所有模板的 embedding
        template_texts = []
        for template in templates:
            template_text = f"{template.get('name', '')} {template.get('keywords', '')}"
            prompt_preview = template.get('prompt_text', '')[:200]  # 取前200字
            template_text += f" {prompt_preview}"
            template_texts.append(template_text)

        embeddings_map = await self._get_embeddings_batch(template_texts)

        # 计算与每个模板的相似度
        best_match = None
        best_similarity = 0

        for i, template in enumerate(templates):
            template_embedding = embeddings_map.get(i)
            if not template_embedding:
                continue

            similarity = self._cosine_similarity(query_embedding, template_embedding)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = template

        if not best_match:
            return MatchResult(
                template=None,
                confidence=0,
                matched_reason="无法计算相似度",
                needs_confirmation=True,
                candidates=templates[:3]
            )

        # 根据阈值返回结果
        if best_similarity >= self.HIGH_THRESHOLD:
            return MatchResult(
                template=best_match,
                confidence=best_similarity,
                matched_reason=f"相似度 {best_similarity:.2f} > {self.HIGH_THRESHOLD}，直接确认"
            )
        elif best_similarity >= self.LOW_THRESHOLD:
            # 需要 LLM 确认
            return MatchResult(
                template=best_match,
                confidence=best_similarity,
                matched_reason=f"相似度 {best_similarity:.2f} 在阈值范围，需要确认",
                needs_confirmation=True,
                candidates=[best_match]
            )
        else:
            # 相似度太低
            return MatchResult(
                template=None,
                confidence=best_similarity,
                matched_reason=f"相似度 {best_similarity:.2f} < {self.LOW_THRESHOLD}，无匹配",
                needs_confirmation=True,
                candidates=templates[:3]
            )

    def _fallback_keyword_match(
        self,
        query_text: str,
        templates: List[Dict[str, Any]]
    ) -> MatchResult:
        """关键词匹配降级方案"""
        query_lower = query_text.lower()

        best_match = None
        best_score = 0

        for template in templates:
            keywords = template.get('keywords', '').lower()
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]

            # 计算命中分数
            score = 0
            for kw in keyword_list:
                if kw in query_lower:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = template

        if best_match and best_score > 0:
            return MatchResult(
                template=best_match,
                confidence=best_score / 10,  # 假设最高10分
                matched_reason=f"关键词匹配，得分 {best_score}"
            )

        return MatchResult(
            template=None,
            confidence=0,
            matched_reason="关键词匹配无结果",
            needs_confirmation=True,
            candidates=templates[:3]
        )


# 全局实例
template_matcher = TemplateMatcher()
