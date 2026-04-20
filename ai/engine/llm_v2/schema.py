"""
MQL Schema - V2 的强类型中间表示

MQL (Metric Query Language) 是连接自然语言和 SQL 的桥梁，
提供可审计、可验证的结构化查询描述。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, TypedDict, Literal, Annotated
from datetime import datetime


class MQLIntent(str, Enum):
    """MQL 意图类型"""
    # 查询类
    QUERY_VALUE = "query_value"          # 查询指标数值
    QUERY_TREND = "query_trend"         # 查询趋势变化
    QUERY_COMPARISON = "query_comparison" # 对比分析
    QUERY_RANKING = "query_ranking"     # 排名分析
    QUERY_RATIO = "query_ratio"         # 占比分析
    QUERY_RETENTION = "query_retention"  # 留存分析

    # 元数据类
    QUERY_METADATA = "query_metadata"   # 查询元数据（业务口径、技术口径）

    # 会话类
    GREETING = "greeting"               # 打招呼
    THANKS = "thanks"                   # 感谢
    BYE = "bye"                        # 告别

    # 异常类
    UNKNOWN = "unknown"                 # 无法识别


class CalculationPattern(str, Enum):
    """9 种核心计算模式"""
    # 1. 同比/环比
    YOY = "yoy"                        # 同比 (Year-over-Year)
    MOM = "mom"                        # 环比 (Month-over-Month)
    WOW = "wow"                        # 周对比 (Week-over-Week)

    # 2. 占比/份额
    PERCENTAGE = "percentage"          # 占比

    # 3. 排名/排序
    RANKING = "ranking"                # 排名

    # 4. Top/Bottom N
    TOP_N = "top_n"                    # Top N
    BOTTOM_N = "bottom_n"              # Bottom N

    # 5. 趋势/走势
    TREND = "trend"                    # 趋势

    # 6. 集中度
    CONCENTRATION = "concentration"     # 集中度

    # 7. 均值/统计
    MEAN = "mean"                      # 均值
    STATISTICS = "statistics"           # 统计

    # 8. 倍数/比率
    MULTIPLIER = "multiplier"          # 倍数
    RATIO = "ratio"                    # 比率

    # 9. 增量/增速
    DELTA = "delta"                    # 增量
    VELOCITY = "velocity"              # 增速


class TimeType(str, Enum):
    """时间类型"""
    DATE_RANGE = "date_range"          # 日期范围
    RELATIVE = "relative"              # 相对表达（近7天）
    ABSOLUTE_MONTH = "absolute_month"  # 绝对月份
    ABSOLUTE_QUARTER = "absolute_quarter"  # 绝对季度
    ABSOLUTE_YEAR = "absolute_year"    # 绝对年度


class AggregationType(str, Enum):
    """聚合类型"""
    SUM = "SUM"
    AVG = "AVG"
    COUNT = "COUNT"
    MAX = "MAX"
    MIN = "MIN"
    COUNT_DISTINCT = "COUNT_DISTINCT"


class OperatorType(str, Enum):
    """比较操作符"""
    EQ = "eq"           # 等于
    NE = "ne"           # 不等于
    GT = "gt"           # 大于
    GTE = "gte"         # 大于等于
    LT = "lt"           # 小于
    LTE = "lte"         # 小于等于
    IN = "in"           # 在列表中
    NOT_IN = "not_in"   # 不在列表中
    LIKE = "like"       # 模糊匹配
    BETWEEN = "between"  # 范围


@dataclass
class MQLMetric:
    """MQL 指标定义"""
    code: str = ""                    # 指标编号，如 MKI-02-0011
    name: str = ""                    # 指标名称，如 总销售额
    table: str = ""                   # StarRocks 表名
    field: str = ""                   # 字段名
    aggregation: AggregationType = AggregationType.SUM  # 聚合类型
    unit: str = ""                    # 单位
    starrocks_sql: str = ""            # 预置 SQL 模板

    # 公式类指标
    is_formula: bool = False          # 是否公式指标
    formula_type: str = ""             # 公式类型
    molecule_metric: str = ""          # 分子指标
    denominator_metric: str = ""       # 分母指标

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "table": self.table,
            "field": self.field,
            "aggregation": self.aggregation.value if isinstance(self.aggregation, Enum) else self.aggregation,
            "unit": self.unit,
            "is_formula": self.is_formula,
            "formula_type": self.formula_type,
            "molecule_metric": self.molecule_metric,
            "denominator_metric": self.denominator_metric,
        }


@dataclass
class MQLDimension:
    """MQL 维度定义"""
    type: str = ""                    # 维度类型（中文显示名）
    column: str = ""                  # 数据库列名
    field: str = ""                   # 同 column
    value: Any = None                 # 过滤值（可选）

    # 层级信息
    hierarchy: str = ""                # 层级，如 GROUP_1, GROUP_2, GROUP_3
    level: int = 0                    # 层级深度

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "column": self.column,
            "field": self.field,
            "value": self.value,
            "hierarchy": self.hierarchy,
            "level": self.level,
        }


@dataclass
class MQLFilter:
    """MQL 筛选条件"""
    field: str = ""                   # 字段名
    operator: OperatorType = OperatorType.EQ  # 操作符
    value: Any = None                 # 值

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value if isinstance(self.operator, Enum) else self.operator,
            "value": self.value,
        }


@dataclass
class TimeRange:
    """MQL 时间范围"""
    type: TimeType = TimeType.RELATIVE
    start: str = ""                   # 开始日期 (YYYY-MM-DD)
    end: str = ""                     # 结束日期 (YYYY-MM-DD)
    original: str = ""                 # 原始表达，如 近30天

    # 相对时间计算
    days: int = 0                     # 相对天数

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "start": self.start,
            "end": self.end,
            "original": self.original,
            "days": self.days,
        }


@dataclass
class ComparisonSpec:
    """对比规格（同比/环比）"""
    enabled: bool = False
    types: List[str] = field(default_factory=list)  # ["同比", "环比"]

    # 对比周期
    compare_period_start: str = ""
    compare_period_end: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "types": self.types,
            "compare_period_start": self.compare_period_start,
            "compare_period_end": self.compare_period_end,
        }


@dataclass
class PaginationSpec:
    """分页规格"""
    page: int = 1
    page_size: int = 100
    total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total": self.total,
        }


@dataclass
class OrderBySpec:
    """排序规格"""
    field: str = ""
    direction: str = "DESC"  # ASC / DESC

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "direction": self.direction,
        }


@dataclass
class DrillDownSpec:
    """下钻规格"""
    add_dimensions: List[str] = field(default_factory=list)  # 要添加的维度列
    original_group_by: List[str] = field(default_factory=list)  # 原始 GROUP BY 列

    def to_dict(self) -> Dict[str, Any]:
        return {
            "add_dimensions": self.add_dimensions,
            "original_group_by": self.original_group_by,
        }


@dataclass
class MQLSchema:
    """
    MQL (Metric Query Language) 结构化查询表示

    这是 V2 的核心中间表示，连接自然语言和 SQL。
    """
    version: str = "1.0"

    # 基础信息
    session_id: str = ""              # 会话 ID
    parent_state_id: str = ""          # 父状态 ID（用于多轮对话）

    # 意图与置信度
    intent: MQLIntent = MQLIntent.QUERY_VALUE
    confidence: float = 0.7

    # 指标信息
    metric: Optional[MQLMetric] = None
    metrics: List[MQLMetric] = field(default_factory=list)  # 多指标查询

    # 时间范围
    time: Optional[TimeRange] = None

    # 维度信息
    dimensions: List[MQLDimension] = field(default_factory=list)

    # 筛选条件
    filters: List[MQLFilter] = field(default_factory=list)

    # 对比规格
    comparison: Optional[ComparisonSpec] = None

    # 分页
    pagination: Optional[PaginationSpec] = None

    # 排序
    order_by: Optional[OrderBySpec] = None

    # 下钻
    drill_down: Optional[DrillDownSpec] = None

    # 计算模式（9 种核心）
    calculation_patterns: List[CalculationPattern] = field(default_factory=list)

    # 计算指标（率指标时的分子分母）
    molecule_metric: Optional[MQLMetric] = None
    denominator_metric: Optional[MQLMetric] = None

    # Top N
    top_n: int = 0
    bottom_n: int = 0

    # 原始问题
    original_question: str = ""

    # 解析后的问题（同义词替换）
    resolved_question: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version": self.version,
            "session_id": self.session_id,
            "parent_state_id": self.parent_state_id,
            "intent": self.intent.value if isinstance(self.intent, Enum) else self.intent,
            "confidence": self.confidence,
            "metric": self.metric.to_dict() if self.metric else None,
            "metrics": [m.to_dict() for m in self.metrics],
            "time": self.time.to_dict() if self.time else None,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "filters": [f.to_dict() for f in self.filters],
            "comparison": self.comparison.to_dict() if self.comparison else None,
            "pagination": self.pagination.to_dict() if self.pagination else None,
            "order_by": self.order_by.to_dict() if self.order_by else None,
            "drill_down": self.drill_down.to_dict() if self.drill_down else None,
            "calculation_patterns": [p.value if isinstance(p, Enum) else p for p in self.calculation_patterns],
            "molecule_metric": self.molecule_metric.to_dict() if self.molecule_metric else None,
            "denominator_metric": self.denominator_metric.to_dict() if self.denominator_metric else None,
            "top_n": self.top_n,
            "bottom_n": self.bottom_n,
            "original_question": self.original_question,
            "resolved_question": self.resolved_question,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MQLSchema":
        """从字典创建 MQLSchema"""
        schema = cls()

        # 基本字段
        schema.version = data.get("version", "1.0")
        schema.session_id = data.get("session_id", "")
        schema.parent_state_id = data.get("parent_state_id", "")

        # 意图
        intent_val = data.get("intent", "query_value")
        try:
            schema.intent = MQLIntent(intent_val)
        except ValueError:
            schema.intent = MQLIntent.UNKNOWN

        schema.confidence = data.get("confidence", 0.7)

        # 指标
        metric_data = data.get("metric")
        if metric_data:
            schema.metric = MQLMetric(**metric_data)

        # 时间
        time_data = data.get("time")
        if time_data:
            try:
                schema.time = TimeRange(
                    type=TimeType(time_data.get("type", "relative")),
                    start=time_data.get("start", ""),
                    end=time_data.get("end", ""),
                    original=time_data.get("original", ""),
                )
            except ValueError:
                schema.time = TimeRange()

        # 维度
        for dim_data in data.get("dimensions", []):
            schema.dimensions.append(MQLDimension(**dim_data))

        return schema

    def is_valid(self) -> tuple:
        """验证 MQL 有效性，返回 (is_valid, error_message)"""
        if not self.metric and not self.metrics:
            return False, "缺少指标信息"

        if self.intent == MQLIntent.UNKNOWN:
            return False, "意图无法识别"

        if self.intent not in [MQLIntent.GREETING, MQLIntent.THANKS, MQLIntent.BYE]:
            if not self.time:
                return False, "缺少时间范围"

        return True, ""


@dataclass
class ThinkingStep:
    """思考步骤（用于调试和追踪）"""
    step: str                          # 步骤名称
    status: str                        # pending / running / completed / failed
    content: Optional[str] = None      # 内容
    timestamp: Optional[str] = None    # 时间戳
    llm_used: bool = False            # 是否使用 LLM
    duration_ms: int = 0               # 耗时（毫秒）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "status": self.status,
            "content": self.content,
            "timestamp": self.timestamp,
            "llm_used": self.llm_used,
            "duration_ms": self.duration_ms,
        }


@dataclass
class SQLResult:
    """SQL 执行结果"""
    sql: str = ""                      # 生成的 SQL
    params: Dict[str, Any] = field(default_factory=dict)  # SQL 参数
    executed: bool = False             # 是否已执行
    execution_time_ms: int = 0         # 执行耗时
    data: List[Dict[str, Any]] = field(default_factory=list)  # 结果数据
    total: int = 0                     # 总记录数
    error: str = ""                    # 错误信息

    def is_success(self) -> bool:
        return self.executed and not self.error


@dataclass
class AnomalyAnnotation:
    """异常标注"""
    type: str = ""                    # 异常类型：significant_drop / significant_yoy_drop / zero_value
    metric: str = ""                  # 指标名称
    value: float = 0.0               # 异常值（如变化百分比）
    threshold: float = 0.0            # 触发阈值
    message: str = ""                 # 标注消息

    # 额外上下文
    dimension: str = ""              # 关联维度
    dimension_value: str = ""        # 维度值
    suggestion: str = ""             # 建议

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
            "dimension": self.dimension,
            "dimension_value": self.dimension_value,
            "suggestion": self.suggestion,
        }


@dataclass
class V2State:
    """
    V2 LangGraph 状态定义

    这是 LangGraph StateGraph 的状态容器，
    包含全局会话状态、当前查询状态、历史状态栈、临时缓存。
    """
    # ===== 全局会话状态 =====
    session_id: str = ""               # 会话 ID
    user_id: str = "default"          # 用户 ID
    user_permissions: Dict[str, Any] = field(default_factory=dict)  # 权限

    # ===== 当前查询状态 =====
    question: str = ""                 # 用户问题
    mql: Optional[MQLSchema] = None   # 当前 MQL
    sql: str = ""                      # 生成的 SQL
    sql_result: Optional[SQLResult] = None  # SQL 执行结果
    answer: str = ""                   # 最终回答
    error: str = ""                    # 错误信息

    # ===== 思考过程 =====
    thinking_steps: List[ThinkingStep] = field(default_factory=list)

    # ===== 历史状态栈（支持回退） =====
    history_stack: List[str] = field(default_factory=list)  # MQL JSON 字符串列表

    # ===== 上下文继承 =====
    inherited_mql: Optional[MQLSchema] = None  # 继承的 MQL（用于多轮对话）

    # ===== 临时缓存 =====
    context_cache: Dict[str, Any] = field(default_factory=dict)  # RAG 结果等

    # ===== 元数据 =====
    created_at: str = ""               # 创建时间
    updated_at: str = ""               # 更新时间

    # ===== 状态控制 =====
    current_step: str = ""             # 当前步骤
    retry_count: int = 0              # 重试次数
    max_retries: int = 3              # 最大重试次数

    # ===== 泛指维度处理 =====
    is_generic_result: bool = False   # 是否为泛指默认结果
    clarification_options: List[Dict[str, Any]] = field(default_factory=list)  # 细化选项

    def add_thinking_step(self, step: str, status: str = "completed",
                          content: str = None, llm_used: bool = False,
                          duration_ms: int = 0):
        """添加思考步骤"""
        self.thinking_steps.append(ThinkingStep(
            step=step,
            status=status,
            content=content,
            timestamp=datetime.now().isoformat(),
            llm_used=llm_used,
            duration_ms=duration_ms,
        ))

    def push_history(self, mql_json: str):
        """将当前 MQL 压入历史栈（支持回退）"""
        self.history_stack.append(mql_json)
        # 限制历史栈大小
        if len(self.history_stack) > 10:
            self.history_stack = self.history_stack[-10:]

    def pop_history(self) -> Optional[str]:
        """从历史栈弹出上一个 MQL（用于回退）"""
        if len(self.history_stack) > 1:
            self.history_stack.pop()
            return self.history_stack[-1] if self.history_stack else None
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "question": self.question,
            "mql": self.mql.to_dict() if self.mql else None,
            "sql": self.sql,
            "answer": self.answer,
            "error": self.error,
            "thinking_steps": [s.to_dict() for s in self.thinking_steps],
            "history_stack": self.history_stack,
            "current_step": self.current_step,
            "retry_count": self.retry_count,
        }


# ==================== V2State 辅助函数 ====================

def add_thinking_step(state: V2State, step: str, status: str = "completed",
                       content: str = None, llm_used: bool = False,
                       duration_ms: int = 0) -> None:
    """添加思考步骤到状态"""
    state["thinking_steps"].append(ThinkingStep(
        step=step,
        status=status,
        content=content,
        timestamp=datetime.now().isoformat(),
        llm_used=llm_used,
        duration_ms=duration_ms,
    ))


def push_history(state: V2State, mql_json: str) -> None:
    """将当前 MQL 压入历史栈（支持回退）"""
    state.history_stack.append(mql_json)
    # 限制历史栈大小
    if len(state.history_stack) > 10:
        state.history_stack = state.history_stack[-10:]


def pop_history(state: V2State) -> Optional[str]:
    """从历史栈弹出上一个 MQL（用于回退）"""
    if len(state.history_stack) > 1:
        state.history_stack.pop()
        return state.history_stack[-1] if state.history_stack else None
    return None


def v2state_to_dict(state: V2State) -> Dict[str, Any]:
    """将 V2State 转换为字典"""
    return {
        "session_id": state.session_id,
        "user_id": state.user_id,
        "question": state.question,
        "mql": state.mql.to_dict() if state.mql else None,
        "sql": state.sql,
        "answer": state.answer,
        "error": state.error,
        "thinking_steps": [s.to_dict() for s in state.thinking_steps],
        "history_stack": state.history_stack,
        "current_step": state.current_step,
        "retry_count": state.retry_count,
    }


def create_v2_state(session_id: str = "", user_id: str = "default",
                    question: str = "", created_at: str = None) -> V2State:
    """创建初始 V2State"""
    return V2State(
        session_id=session_id,
        user_id=user_id,
        user_permissions={},
        question=question,
        mql=None,
        sql="",
        sql_result=None,
        answer="",
        error="",
        thinking_steps=[],
        history_stack=[],
        inherited_mql=None,
        context_cache={},
        created_at=created_at or datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        current_step="",
        retry_count=0,
        max_retries=3,
    )
