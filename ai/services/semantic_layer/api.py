"""
语义层 API 定义

定义语义服务层的接口和数据结构
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class EnrichStage(str, Enum):
    """语义增强阶段枚举"""
    INTENT_ROUTER = "intent_router"
    MQL_GENERATION = "mql_generation"
    VALIDATION = "validation"
    RESULT_ANALYSIS = "result_analysis"
    TRIGGER_ANALYSIS = "trigger_analysis"


@dataclass
class Entity:
    """实体"""
    text: str                           # 实体文本
    type: str                           # 实体类型: METRIC/TIME/DIM/DIM_VALUE
    start: int = 0                     # 起始位置
    end: int = 0                        # 结束位置


@dataclass
class ParseResult:
    """
    解析结果

    parse_query() 返回的结果，包含意图、实体、时间等
    """
    intent: str                          # 意图类型: query_value/query_trend/query_comparison/drilldown 等
    confidence: float                    # 置信度 0-1
    entities: List[Entity] = field(default_factory=list)  # 提取的实体
    metric_name: Optional[str] = None   # 指标名称
    metric_code: Optional[str] = None   # 指标编码
    dimensions: List[Dict[str, str]] = field(default_factory=list)  # 维度 [{"type": "品类", "value": "手机"}]
    time_expr: Optional[str] = None    # 时间表达式
    time_start: Optional[str] = None   # 时间范围开始
    time_end: Optional[str] = None     # 时间范围结束
    comparison_types: List[str] = field(default_factory=list)  # 对比类型: ["同比", "环比"]
    parse_method: str = ""              # 解析方法: local_model/snapshot/rule/llm
    drilldown_type: Optional[str] = None  # 下钻类型: sales/ad/inventory 等
    raw_result: Dict[str, Any] = field(default_factory=dict)  # 原始结果
    error: Optional[str] = None         # 错误信息


@dataclass
class EnrichResult:
    """
    语义增强结果

    enrich() 返回的结果，stage 不同内容不同

    使用示例:
        enrich_result = semantic_layer.enrich(parse_result, stage=EnrichStage.INTENT_ROUTER)
        if enrich_result.ranking_dimension_options:
            # 使用排名维度选项
    """

    # ===== intent_router 阶段 =====
    ranking_dimension_options: Optional[List[Dict[str, str]]] = None  # [{"label": "按平台", "value": "PLATFORM"}]
    is_generic_dimension: bool = False  # 是否有泛指维度需要追问
    clarification_message: str = ""  # 追问提示消息
    clarification_options: List[Dict] = field(default_factory=list)  # 追问选项

    # ===== mql_generation 阶段 =====
    dimension_name_to_code_map: Optional[Dict[str, str]] = None  # 维度名→代码映射 {"平台": "PLATFORM"}
    business_term_maps: Optional[Dict[str, str]] = None  # 业务术语同义词 {"销售额": "sales_amount"}
    synonym_context: str = ""  # 同义词上下文字符串
    dimension_values_context: str = ""  # 维度值上下文字符串
    level_keywords: Optional[Dict[str, str]] = None  # 品类级别关键词 {"一级品类": "GROUP_1"}
    dimension_fallback_map: Optional[Dict[str, str]] = None  # 维度fallback映射
    default_comparison_spec: Optional[Dict] = None  # 默认对比规格 {"types": ["同比", "环比"]}

    # ===== validation 阶段 =====
    is_valid: bool = True  # 是否有效
    errors: List[str] = field(default_factory=list)  # 错误列表
    warnings: List[str] = field(default_factory=list)  # 警告列表
    starrocks_sql: Optional[str] = None  # StarRocks SQL

    # ===== result_analysis 阶段 =====
    metric_capability: Optional[Dict[str, Any]] = None  # 指标能力配置

    # ===== trigger_analysis 阶段 =====
    scene_keywords: Optional[List[str]] = None  # 场景关键词
    scene_drilldown_categories: Optional[List[Dict]] = None  # 下钻分类


@dataclass
class ValidationResult:
    """
    语义验证结果

    validate_semantic() 返回的结果
    """
    is_valid: bool                      # 是否有效
    metric_exists: bool = True          # 指标是否存在
    dimensions_valid: bool = True        # 维度是否有效
    errors: List[str] = field(default_factory=list)  # 错误列表
    warnings: List[str] = field(default_factory=list)  # 警告列表
    starrocks_sql: Optional[str] = None # StarRocks SQL
    suggestion: Optional[str] = None     # 建议


@dataclass
class RecommendResult:
    """
    推荐结果

    recommend() 返回的结果
    """
    next_questions: List[str] = field(default_factory=list)  # 推荐问题
    actions: List[Dict[str, Any]] = field(default_factory=list)  # 推荐动作 [{"label": "看销售", "action": "drilldown", "params": {...}}]


@dataclass
class RecommendContext:
    """
    推荐上下文

    recommend() 方法的输入参数
    """
    stage: str  # "result_analysis" | "trigger_analysis"
    parse_result: Optional[ParseResult] = None  # 解析结果
    data_result: Optional[Dict[str, Any]] = None  # 查询结果数据
    trigger_type: Optional[str] = None  # 触发器类型: volatility/ad_effect/inventory_risk 等


@dataclass
class SemanticContext:
    """
    语义上下文

    传入 parse_query/recommend 等方法的上下文信息
    """
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    inherited_mql: Optional[Dict[str, Any]] = None  # 上轮 MQL
    history_stack: List[Dict[str, Any]] = field(default_factory=list)  # 历史栈
    conversation_summary: Optional[str] = None  # 会话摘要
    active_task: Optional[Dict[str, Any]] = None  # 当前任务
