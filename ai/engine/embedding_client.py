"""
阿里云百炼 Embedding 调用客户端
"""
import os
import httpx
from typing import List, Optional


class EmbeddingClient:
    """阿里云百炼 Embedding 客户端"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.api_url = "https://dashscope.aliyuncs.com/compatible-mode/text-embedding/text-embedding-v2"
        self.model = "text-embedding-v2"

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        调用百炼 API 获取文本向量

        Args:
            texts: 文本列表（最多 25 条）

        Returns:
            向量列表，每个向量 1536 维
        """
        if not texts:
            return []

        if not self.api_key:
            print("[EmbeddingClient] 警告：DASHSCOPE_API_KEY 未设置")
            return []

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

            output = result.get("output", {})
            embeddings = output.get("embeddings", [])

            return [e.get("embedding", []) for e in embeddings]

        except httpx.HTTPStatusError as e:
            print(f"[EmbeddingClient] HTTP 错误: {e.response.status_code}")
            return [[] for _ in texts]
        except Exception as e:
            print(f"[EmbeddingClient] 调用失败: {e}")
            return [[] for _ in texts]

    def embed_single(self, text: str) -> Optional[List[float]]:
        """单个文本向量化"""
        results = self.embed([text])
        return results[0] if results else None


# 全局实例
embedding_client = EmbeddingClient()