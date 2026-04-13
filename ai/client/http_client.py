"""
全局 HTTP 客户端 - 连接池复用
"""
import httpx
from typing import Optional

# 全局 HTTP 客户端（连接池复用）
_http_client: Optional[httpx.Client] = None


def get_http_client(
    timeout: float = 10.0,
    max_connections: int = 100,
    max_keepalive: int = 20
) -> httpx.Client:
    """获取全局 HTTP 客户端（单例，连接池复用）"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(
                max_keepalive_connections=max_keepalive,
                max_connections=max_connections
            )
        )
    return _http_client


def close_http_client():
    """关闭全局 HTTP 客户端"""
    global _http_client
    if _http_client is not None:
        _http_client.close()
        _http_client = None
