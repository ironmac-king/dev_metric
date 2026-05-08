"""
LLM.V2 - 基于 LangGraph 的 NL2MQL2SQL 智能问数架构

核心组件：
- schema.py: MQL (Metric Query Language) 数据结构 + V2State 定义
- graph.py: LangGraph StateGraph 编排 + Checkpoint + 边定义
- nodes/: 11 个智能体节点实现
- router.py: API 路由入口
- cache.py: 多级缓存体系（L1 内存 + L2 Redis）
- rag.py: RAG 检索增强
- streaming.py: 流式输出（SSE）
- metrics.py: 性能监控和埋点

架构：
  intent_router → context_enhancer → mql_generator → mql_syntax_validator
      → mql_semantic_validator → sql_generator → sql_security_auditor
      → sql_executor → data_quality_checker → result_analyzer → state_manager

关键特性：
- 强类型 MQL 中间表示
- 多轮对话状态管理（Checkpoint 回退）
- RAG 上下文增强
- 多级缓存（L1 内存 + L2 Redis + 历史查询复用）
- 流式输出支持
- 性能监控和基准测试
"""

__version__ = "2.0.0"

# 核心 Schema
from .schema import (
    MQLSchema,
    V2State,
    MQLIntent,
    MQLMetric,
    MQLDimension,
    MQLFilter,
    TimeRange,
    TimeType,
    CalculationPattern,
    ComparisonSpec,
    PaginationSpec,
    OrderBySpec,
    SQLResult,
    ThinkingStep,
)

# Graph
from .graph import V2Graph, create_v2_graph

# 节点
from .nodes import (
    IntentRouter,
    ContextEnhancer,
    MQLGenerator,
    MQLSyntaxValidator,
    MQLSemanticValidator,
    SQLGeneratorNode,
    SQLSecurityAuditor,
    SQLExecutor,
    DataQualityChecker,
    ResultAnalyzer,
    StateManager,
)

# 缓存
from .cache import (
    L1MemoryCache,
    L2RedisCache,
    MQLSQLCache,
    HistoryReuseCache,
    get_mql_sql_cache,
    get_history_reuse_cache,
)

# RAG
from .rag import (
    EmbeddingGenerator,
    VectorStore,
    get_embedding_generator,
    get_vector_store,
    rag_retrieve,
    rag_index,
)

# 流式输出
from .streaming import (
    StreamingGenerator,
    StreamEvent,
    SSSEvent,
    get_streaming_generator,
    clear_streaming_generator,
)

# 性能监控
from .metrics import (
    PerformanceTracker,
    BenchmarkRunner,
    get_performance_tracker,
)

__all__ = [
    # 版本
    "__version__",
    # Schema
    "MQLSchema",
    "V2State",
    "MQLIntent",
    "MQLMetric",
    "MQLDimension",
    "MQLFilter",
    "TimeRange",
    "TimeType",
    "CalculationPattern",
    "ComparisonSpec",
    "PaginationSpec",
    "OrderBySpec",
    "SQLResult",
    "ThinkingStep",
    # Graph
    "V2Graph",
    "create_v2_graph",
    # 节点
    "IntentRouter",
    "ContextEnhancer",
    "MQLGenerator",
    "MQLSyntaxValidator",
    "MQLSemanticValidator",
    "SQLGeneratorNode",
    "SQLSecurityAuditor",
    "SQLExecutor",
    "DataQualityChecker",
    "ResultAnalyzer",
    "StateManager",
    # 缓存
    "L1MemoryCache",
    "L2RedisCache",
    "MQLSQLCache",
    "HistoryReuseCache",
    "get_mql_sql_cache",
    "get_history_reuse_cache",
    # RAG
    "EmbeddingGenerator",
    "VectorStore",
    "get_embedding_generator",
    "get_vector_store",
    "rag_retrieve",
    "rag_index",
    # 流式输出
    "StreamingGenerator",
    "StreamEvent",
    "SSSEvent",
    "get_streaming_generator",
    "clear_streaming_generator",
    # 性能监控
    "PerformanceTracker",
    "BenchmarkRunner",
    "get_performance_tracker",
]
