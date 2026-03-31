"""
阿里 text-embedding-v2 接入
使用 dashscope SDK
"""
from typing import List, Optional
from dashscope import TextEmbedding

class AlibabaEmbedding:
    """阿里 text-embedding-v2 客户端"""

    def __init__(self, api_key: str = None):
        if api_key:
            TextEmbedding.api_key = api_key
        else:
            import os
            TextEmbedding.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.model = 'text-embedding-v2'

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        response = TextEmbedding.call(
            model=self.model,
            input=texts
        )

        if response.status_code == 200:
            return [item['embedding'] for item in response.output['embeddings']]
        else:
            raise Exception(f"Embedding API error: {response.code}")

    def embed_single(self, text: str) -> Optional[List[float]]:
        results = self.embed([text])
        return results[0] if results else None

alibaba_embedding = AlibabaEmbedding()