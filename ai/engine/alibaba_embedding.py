"""
阿里 text-embedding-v2 接入
使用 dashscope SDK
"""
from typing import List, Optional
import os
from dashscope import TextEmbedding

from ai.config.runtime import get_go_api_base

class AlibabaEmbedding:
    """阿里 text-embedding-v2 客户端"""

    def __init__(self, api_key: str = None):
        self._api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = 'text-embedding-v2'

    def _get_api_key(self) -> str:
        """获取 API key，优先环境变量，其次数据库"""
        if self._api_key:
            return self._api_key

        # 从数据库 LLM 配置加载 embedding key
        db_key = self._load_embedding_key_from_db()
        if db_key:
            self._api_key = db_key
            return db_key

        return os.getenv("DASHSCOPE_API_KEY", "")

    def _load_embedding_key_from_db(self) -> Optional[str]:
        """从数据库 LLM 配置加载 embedding key"""
        try:
            import httpx
            response = httpx.get(
                f"{get_go_api_base()}/api/v1/llm/configs",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                configs = data.get("data", [])

                # 找默认配置
                default_config = None
                for cfg in configs:
                    if cfg.get("is_default") == 1 or cfg.get("is_default") == True:
                        default_config = cfg
                        break

                # 如果没有默认的，用第一个
                if not default_config and configs:
                    default_config = configs[0]

                if default_config:
                    key = default_config.get("embedding_api_key", "")
                    if key:
                        return key
        except Exception as e:
            print(f"[AlibabaEmbedding] 从DB加载embedding key失败: {e}")
        return None

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        api_key = self._get_api_key()
        if not api_key:
            raise Exception("Embedding API key not configured")

        response = TextEmbedding.call(
            model=self.model,
            input=texts,
            api_key=api_key  # 通过参数传递，而不是设置类属性
        )

        if response.status_code == 200:
            return [item['embedding'] for item in response.output['embeddings']]
        else:
            raise Exception(f"Embedding API error: {response.code}")

    def embed_single(self, text: str) -> Optional[List[float]]:
        results = self.embed([text])
        return results[0] if results else None

alibaba_embedding = AlibabaEmbedding()
