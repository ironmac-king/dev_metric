"""
语义服务层 (Semantic Layer)

提供统一的语义理解能力：
- 意图识别（本地模型）
- 实体提取（本地模型 NER）
- 指标解析（语义快照）
- 维度解析（语义快照）
- 语义验证
- 上下文推荐

Usage:
    from ai.services.semantic_layer import SemanticLayerService

    service = SemanticLayerService()
    result = service.parse_query("本月销售额是多少？")

    # 使用语义增强
    from ai.services.semantic_layer.api import EnrichStage
    enrich_result = service.enrich(parse_result, stage=EnrichStage.INTENT_ROUTER)
"""
from .service import SemanticLayerService, get_semantic_layer_service
from .api import EnrichStage, EnrichResult, RecommendContext, RecommendResult

__all__ = [
    "SemanticLayerService",
    "get_semantic_layer_service",
    "EnrichStage",
    "EnrichResult",
    "RecommendContext",
    "RecommendResult",
]
