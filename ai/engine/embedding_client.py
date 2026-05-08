"""
统一的 Embedding 调用客户端，支持 DeepSeek 和阿里
"""
import os
import httpx
from typing import List, Optional
from ai.config.logging_config import get_logger

logger = get_logger("ai.embedding_client")


class EmbeddingClient:
    """统一的 Embedding 客户端，支持 DeepSeek 和阿里"""

    def __init__(self, provider: str = "deepseek"):
        self.provider = provider
        self._alibaba_client = None

        if provider == "alibaba":
            from ai.engine.alibaba_embedding import alibaba_embedding
            self._alibaba_client = alibaba_embedding

        # DeepSeek 配置
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.api_url = "https://api.deepseek.com/embeddings"
        self.model = "deepseek-embedding"

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        调用 Embedding API 获取文本向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not texts:
            return []

        if self.provider == "alibaba":
            return self._embed_alibaba(texts)
        else:
            return self._embed_deepseek(texts)

    def _embed_alibaba(self, texts: List[str]) -> List[List[float]]:
        """使用阿里 text-embedding-v2"""
        try:
            vectors = self._alibaba_client.embed(texts)
            return vectors
        except Exception as e:
            logger.info(f"阿里 embedding 失败: {e}")
            return [[] for _ in texts]

    def _embed_deepseek(self, texts: List[str]) -> List[List[float]]:
        """使用 DeepSeek embedding"""
        if not self.api_key:
            logger.warning("[EmbeddingClient] DEEPSEEK_API_KEY 未设置")
            return [[] for _ in texts]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "input": texts,
        }

        try:
            response = httpx.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            data = result.get("data", [])
            return [item.get("embedding", []) for item in data]

        except httpx.HTTPStatusError as e:
            logger.info(f"HTTP 错误: {e.response.status_code}")
            return [[] for _ in texts]
        except Exception as e:
            logger.info(f"调用失败: {e}")
            return [[] for _ in texts]

    def embed_single(self, text: str) -> Optional[List[float]]:
        """单个文本向量化"""
        results = self.embed([text])
        return results[0] if results else None


# 全局实例 - 默认使用 DeepSeek
embedding_client = EmbeddingClient(provider="deepseek")

# 阿里 embedding 客户端全局实例
alibaba_embedding_client = EmbeddingClient(provider="alibaba")