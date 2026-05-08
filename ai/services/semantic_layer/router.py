"""
语义层路由（增强版）

智能路由到合适的引擎：
1. 本地模型引擎（高置信度，阈值 >= 0.5）
2. 语义快照引擎（中等置信度，阈值 >= 0.4）
3. 规则引擎（低置信度，兜底）
4. LLM引擎（最后兜底）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from typing import Optional, Dict, Any

from ai.config.logging_config import get_logger
from .api import ParseResult
from .engines.local_model_engine import LocalModelEngine
from .engines.snapshot_engine import SnapshotEngine
from .engines.rule_engine import RuleEngine
from .engines.llm_engine import LLMEngine

logger = get_logger("semantic_layer.router")


class SemanticRouter:
    """
    语义层路由

    智能选择最合适的引擎处理查询

    路由策略：
    1. 本地模型引擎（置信度 >= 0.5）
    2. 语义快照引擎（置信度 >= 0.4）
    3. 规则引擎（置信度 >= 0.3）
    4. LLM引擎（最后兜底）
    """

    # 置信度阈值
    LOCAL_MODEL_THRESHOLD = 0.5  # 本地模型置信度阈值
    SNAPSHOT_THRESHOLD = 0.4       # 语义快照置信度阈值
    RULE_THRESHOLD = 0.3          # 规则引擎置信度阈值

    def __init__(self):
        self._local_model = None
        self._snapshot = None
        self._rule = None
        self._llm = None
        self._initialized = False

    def _ensure_init(self):
        """延迟初始化"""
        if self._initialized:
            return

        self._local_model = LocalModelEngine()
        self._snapshot = SnapshotEngine()
        self._rule = RuleEngine()
        self._llm = LLMEngine()

        self._initialized = True
        logger.info("[SemanticRouter] 初始化成功（4引擎模式）")

    def route(self, query: str, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        路由查询到合适的引擎

        Args:
            query: 用户问题
            context: 上下文

        Returns:
            ParseResult
        """
        self._ensure_init()

        # 1. 先尝试本地模型
        local_result = self._local_model.parse(query, context)
        if local_result.confidence >= self.LOCAL_MODEL_THRESHOLD:
            logger.info(f"[SemanticRouter] 本地模型命中: confidence={local_result.confidence:.2f}")
            return local_result

        # 2. 降级到语义快照
        snapshot_result = self._snapshot.parse(query, context)
        if snapshot_result.confidence >= self.SNAPSHOT_THRESHOLD:
            logger.info(f"[SemanticRouter] 语义快照命中: confidence={snapshot_result.confidence:.2f}")
            return snapshot_result

        # 3. 降级到规则引擎
        rule_result = self._rule.parse(query, context)
        if rule_result.confidence >= self.RULE_THRESHOLD:
            logger.info(f"[SemanticRouter] 规则引擎命中: confidence={rule_result.confidence:.2f}")
            return rule_result

        # 4. 最后兜底到 LLM
        logger.warning(f"[SemanticRouter] 所有引擎置信度都低于阈值，调用 LLM 兜底")
        llm_result = self._llm.parse(query, context)
        return llm_result

    def route_with_fallback(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        max_engines: int = 4
    ) -> ParseResult:
        """
        带降级限制的路由

        Args:
            query: 用户问题
            context: 上下文
            max_engines: 最大使用的引擎数量（1-4）

        Returns:
            ParseResult
        """
        self._ensure_init()

        results = []
        engines = [
            ("local_model", self._local_model, self.LOCAL_MODEL_THRESHOLD),
            ("snapshot", self._snapshot, self.SNAPSHOT_THRESHOLD),
            ("rule", self._rule, self.RULE_THRESHOLD),
        ]

        for name, engine, threshold in engines[:max_engines]:
            result = engine.parse(query, context)
            results.append((name, result))

            if result.confidence >= threshold:
                logger.info(f"[SemanticRouter] {name} 命中: confidence={result.confidence:.2f}")
                return result

        # 最后一个引擎的结果作为兜底
        return results[-1][1]


# 单例
_semantic_router: Optional[SemanticRouter] = None


def get_semantic_router() -> SemanticRouter:
    """获取语义路由单例"""
    global _semantic_router
    if _semantic_router is None:
        _semantic_router = SemanticRouter()
    return _semantic_router
