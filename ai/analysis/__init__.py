"""
决策分析模块

提供基于模板的智能决策分析功能，支持：
- 模板匹配（Embedding 向量相似度）
- 洞察预计算（趋势、异常、周期、预测）
- SSE 流式输出
"""
from .agent import AnalysisAgent, AnalysisRequest, run_analysis
from .router import router
from .template_loader import template_loader
from .template_matcher import template_matcher, MatchResult
from .sse_utils import SSEEvent, create_sse_event

__all__ = [
    "AnalysisAgent",
    "AnalysisRequest",
    "run_analysis",
    "router",
    "template_loader",
    "template_matcher",
    "MatchResult",
    "SSEEvent",
    "create_sse_event",
]
