"""
LangGraph 对话状态定义
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class ConversationMessage(BaseModel):
    """对话消息"""
    role: Literal["user", "assistant", "system"] = "user"
    content: str
    sql: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    # 响应数据（仅 assistant 消息有）
    result_data: Optional[List[Dict[str, Any]]] = None
    comparison_results: Optional[List[Dict[str, Any]]] = None
    drill_down_dims: Optional[List[Dict[str, str]]] = None
    breadcrumbs: Optional[List[Dict[str, str]]] = None


class ThinkingStep(BaseModel):
    """思考步骤"""
    step: str                                    # 步骤名称
    status: str = "pending"                      # pending/completed/error
    content: Optional[str] = None                 # 步骤内容/详情
    llm_used: bool = False                       # 是否使用了 LLM
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationState(BaseModel):
    """LangGraph 对话状态"""
    session_id: str = ""                          # 会话 ID
    messages: List[ConversationMessage] = []    # 对话历史
    current_intent: Optional[str] = None          # 当前意图
    entities: Dict[str, Any] = {}                 # 识别的实体
    previous_entities: Dict[str, Any] = {}      # 上一轮实体（用于多轮对话）
    generated_sql: Optional[str] = None           # 生成的 SQL
    sql_params: Dict[str, Any] = {}              # SQL 参数
    metric_id: Optional[int] = None              # 关联的指标 ID
    error: Optional[str] = None                   # 错误信息
    needs_clarification: bool = False            # 是否需要追问
    clarification_message: Optional[str] = None  # 追问内容
    clarification_type: Optional[str] = None     # 追问类型
    matched_metrics: Optional[List[Dict[str, Any]]] = None  # 匹配的指标列表（用于 metric_enum 追问）
    suggest_questions: List[str] = []             # 建议问题
    intent_is_metadata_query: bool = False       # 是否元数据查询
    explicit_value_query: bool = False           # 是否显式数值查询
    skip_execution: bool = False                  # 跳过执行
    sql_result: Any = None                       # SQL 查询结果
    last_valid_metric: Dict[str, Any] = {}      # 最后一个有效的指标（用于follow-up，不轻易清除）
    # ========== 智能追问相关字段 ==========
    asked_fields: List[str] = []                 # 已追问过的字段（如 time_range, region）
    pending_clarification: Dict[str, Any] = {}  # 等待澄清的信息
    clarification_count: int = 0                 # 追问次数计数（按字段）
    max_clarification_turns: int = 3            # 最大追问次数
    # 默认值配置
    default_values: Dict[str, Any] = {
        "time_range": "last_7_days",
        "dimension": "all",  # 默认不分维度
    }
    # 记录的默认值（用于在回复中告知用户）
    applied_defaults: Dict[str, Any] = {}
    # ========== 思考过程相关字段 ==========
    thinking_steps: List[ThinkingStep] = Field(default_factory=list)  # 思考步骤列表
    # ========== 图谱上下文相关字段 ==========
    context: Dict[str, Any] = {}                 # 知识图谱上下文（上游/下游/相关指标）
    # ========== 多轮对话上下文继承 ==========
    conversation_context: Optional[ConversationContext] = None  # 对话上下文
    # ========== 对比计算结果（同比环比）==========
    comparison_results: Optional[List[Dict[str, Any]]] = None  # 支持多个对比结果（同比+环比）
    # ========== 维度值频次学习 ==========
    selected_dimension_field: Optional[str] = None  # 用户选择的维度字段
    selected_dimension_value: Optional[str] = None  # 用户选择的维度值
    dimension_value_candidates: Optional[List[Dict[str, Any]]] = None  # 维度值候选列表（用于追问选择）
    dimension_value_matched_text: Optional[str] = None  # 匹配维度值时的原始文本（如"1011"）
    # ========== 公式语法匹配结果 ==========
    matched_formula_syntax: Optional[Dict[str, Any]] = None  # 匹配到的公式语法配置
    # ========== QueryState 相关 ==========
    _query_state: Optional[Dict[str, Any]] = None  # LLM 生成的 QueryState JSON
    # ========== SQL 生成模式 (A/B Test) ==========
    sql_mode: str = "llm"  # SQL生成模式: "llm" | "template"
    # ========== response_node 结果缓存（避免重复执行）==========
    result_data: Any = None  # 缓存查询结果
    answer: Optional[str] = None  # 缓存生成的回答
    # ========== 数据权限相关字段 ==========
    user_id: str = "default"  # 用户ID
    dept_id: int = 0  # 部门ID
    data_filter: str = ""  # 自定义SQL WHERE条件


class IntentResult(BaseModel):
    """意图识别结果"""
    intent: str
    confidence: float
    entities: Dict[str, Any] = {}


class ConversationContext(BaseModel):
    """多轮对话上下文 - 用于继承上轮对话的关键信息"""
    current_metric_code: Optional[str] = None
    current_metric_name: Optional[str] = None
    current_time_expr: Optional[str] = None
    current_dimensions: Dict[str, str] = {}
    current_metrics: list = []  # 多指标列表，用于多指标查询的上下文继承
    time_inherited: bool = False
    dimensions_inherited: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_metric_code": self.current_metric_code,
            "current_metric_name": self.current_metric_name,
            "current_time_expr": self.current_time_expr,
            "current_dimensions": self.current_dimensions,
            "current_metrics": self.current_metrics,
            "time_inherited": self.time_inherited,
            "dimensions_inherited": self.dimensions_inherited,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        return cls(**data) if data else cls()


class SQLGenerationResult(BaseModel):
    """SQL 生成结果"""
    sql: str
    params: Dict[str, Any] = {}
    is_safe: bool = True
    error: Optional[str] = None


class ClarificationDecision(BaseModel):
    """LLM 追问决策结果 - 基于 BI 查询场景的完整追问类型"""
    needs_clarification: bool = False
    clarification_type: Optional[str] = None  # 追问类型枚举
    question: Optional[str] = None  # 自然语言追问内容
    reason: Optional[str] = None  # 追问原因（用于日志）
    missing_fields: List[str] = []  # 缺少的字段列表
    suggested_defaults: Dict[str, Any] = {}  # 建议的默认值
    max_retries: int = 2  # 该字段最多允许追问次数


class ClarificationType:
    """追问类型枚举常量"""
    # 结构化信息缺失（核心场景）
    METRIC_MISSING = "metric_missing"              # 指标缺失
    TIME_RANGE_MISSING = "time_range_missing"     # 时间范围缺失
    DIMENSION_MISSING = "dimension_missing"        # 维度/分组缺失
    FILTER_CONDITION_MISSING = "filter_condition_missing"  # 过滤条件缺失
    ACTION_INTENT_AMBIGUOUS = "action_intent_ambiguous"  # 操作意图模糊

    # 意图模糊（更通用）
    TERM_AMBIGUOUS = "term_ambiguous"             # 术语歧义
    SCOPE_TOO_BROAD = "scope_too_broad"          # 范围太宽

    # 系统策略
    HIGH_RISK_OPERATION = "high_risk_operation"  # 高风险操作确认
    PERMISSION_REQUIRED = "permission_required"    # 权限不足
    COSTLY_QUERY_WARNING = "costly_query_warning"  # 高成本查询预警

    # 交互优化
    DEFAULT_VALUE_CONFIRMATION = "default_value_confirmation"  # 默认值确认
    IMPLICIT_NEED_DISCOVERY = "implicit_need_discovery"  # 隐含需求挖掘

    @classmethod
    def all_types(cls) -> list:
        return [
            cls.METRIC_MISSING,
            cls.TIME_RANGE_MISSING,
            cls.DIMENSION_MISSING,
            cls.FILTER_CONDITION_MISSING,
            cls.ACTION_INTENT_AMBIGUOUS,
            cls.TERM_AMBIGUOUS,
            cls.SCOPE_TOO_BROAD,
            cls.HIGH_RISK_OPERATION,
            cls.PERMISSION_REQUIRED,
            cls.COSTLY_QUERY_WARNING,
            cls.DEFAULT_VALUE_CONFIRMATION,
            cls.IMPLICIT_NEED_DISCOVERY,
        ]
