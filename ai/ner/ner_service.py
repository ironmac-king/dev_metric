"""
NER 服务层 - 管理 NER 组件的生命周期
"""
import time
import logging
from typing import List, Dict, Optional
from ai.ner.trie_ner import DimNER
from ai.config.runtime import get_go_api_base

logger = logging.getLogger("ai.ner_service")

# 全局 NER 服务单例
_ner_service: Optional["NERService"] = None


class NERService:
    """
    NER 服务（单例）

    管理 DimNER 组件的生命周期：
    - 启动时从 Go API 加载 business_terms
    - 定时刷新缓存
    - 提供 reload 接口
    """

    def __init__(self):
        self.dim_ner = DimNER()
        self._last_load_time: float = 0
        self._cache_ttl: int = 300  # 5分钟
        self._base_url: str = get_go_api_base()
        self._terms_count: int = 0
        self._metrics_count: int = 0

    def _load_from_api(self) -> List[Dict]:
        """从 Go API 获取 business_terms"""
        import httpx

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    f"{self._base_url}/api/v1/metadata/terms",
                    params={"status": 1},
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    logger.warning(f"[NERService] API 返回错误: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"[NERService] 加载 business_terms 失败: {e}")
            return []

    def _load_metrics_from_api(self) -> List[Dict]:
        """从 Go API 获取指标列表"""
        import httpx

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    f"{self._base_url}/api/v1/metadata/metrics",
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    logger.warning(f"[NERService] Metrics API 返回错误: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"[NERService] 加载 metrics 失败: {e}")
            return []

    def _need_reload(self) -> bool:
        """检查是否需要重新加载"""
        if self._terms_count == 0 and self._metrics_count == 0:
            return True
        elapsed = time.time() - self._last_load_time
        return elapsed > self._cache_ttl

    def load(self):
        """加载 business_terms 和 metrics 到 NER"""
        logger.info("[NERService] 开始加载 business_terms 和 metrics...")

        # 加载 business_terms
        terms = self._load_from_api()
        if terms:
            self.dim_ner.load_terms(terms)
            self._terms_count = len(terms)
            logger.info(f"[NERService] 加载 {self._terms_count} 个 business_terms")
        else:
            logger.warning("[NERService] 未获取到 business_terms")

        # 加载 metrics
        metrics = self._load_metrics_from_api()
        if metrics:
            self.dim_ner.load_metrics(metrics)
            self._metrics_count = len(metrics)
            logger.info(f"[NERService] 加载 {self._metrics_count} 个指标")
        else:
            logger.warning("[NERService] 未获取到 metrics")

        self._last_load_time = time.time()
        logger.info(f"[NERService] 加载完成，共 {self._terms_count} 个术语 + {self._metrics_count} 个指标")

    def ensure_loaded(self):
        """确保 NER 已加载"""
        if self._need_reload():
            self.load()

    def reload(self):
        """强制重新加载"""
        logger.info("[NERService] 强制重新加载...")
        self._terms_count = 0
        self._metrics_count = 0
        self.load()

    def recognize(self, text: str) -> List[Dict]:
        """
        识别文本中的维度

        Args:
            text: 用户输入

        Returns:
            List[Dict]: 识别结果
        """
        self.ensure_loaded()
        return self.dim_ner.recognize(text)

    def get_status(self) -> Dict:
        """获取 NER 服务状态"""
        return {
            "loaded": self._terms_count > 0 or self._metrics_count > 0,
            "terms_count": self._terms_count,
            "metrics_count": self._metrics_count,
            "last_load_time": self._last_load_time,
            "cache_ttl": self._cache_ttl,
            "need_reload": self._need_reload()
        }


def get_ner_service() -> NERService:
    """获取 NER 服务单例"""
    global _ner_service
    if _ner_service is None:
        _ner_service = NERService()
    return _ner_service


def reload_ner_service():
    """强制重新加载 NER"""
    service = get_ner_service()
    service.reload()
