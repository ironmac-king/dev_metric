"""
ConfigLoader - LLM.V1 配置加载器
所有配置从数据库读取，启动时缓存 1 小时，禁止硬编码
"""
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .metric_client import get_metric_client

logger = logging.getLogger("ai.llm_v1.config_loader")


@dataclass
class DimensionConfig:
    """维度配置"""
    dimension_name: str  # 中文维度名，如"三级品类"
    column_name: str  # 数据库列名，如"GROUP_3"
    dimension_values: Optional[List[str]] = None  # 可选值列表


@dataclass
class IntentTemplate:
    """意图模板"""
    id: int
    name: str
    intent: str  # intent_type
    patterns: str  # 匹配模式，逗号分隔
    priority: int
    response: str
    status: int


@dataclass
class PromptTemplate:
    """Prompt 模板配置"""
    name: str
    content: str
    model_name: Optional[str] = None


@dataclass
class ChartRule:
    """图表推荐规则"""
    intent_type: str
    data_shape: str  # single_value/multiple_rows/timeseries
    chart_type: str  # bar/line/table/pie


@dataclass
class Config:
    """完整配置对象"""
    dimension_configs: List[DimensionConfig] = field(default_factory=list)
    dimension_map: Dict[str, str] = field(default_factory=dict)  # 中文名→列名
    reverse_dimension_map: Dict[str, str] = field(default_factory=dict)  # 列名→中文名
    intent_templates: List[IntentTemplate] = field(default_factory=list)
    intent_types: List[str] = field(default_factory=list)
    prompt_templates: Dict[str, PromptTemplate] = field(default_factory=dict)
    chart_rules: List[ChartRule] = field(default_factory=list)
    business_terms: Dict[str, str] = field(default_factory=dict)  # 同义词→标准名
    clarification_threshold: float = 0.7
    confident_threshold: float = 0.85
    cache_ttl: int = 3600  # 1小时


class ConfigLoader:
    """
    配置加载器
    - 启动时从数据库加载所有配置
    - 缓存 1 小时后自动刷新
    - 所有配置必须通过此类获取，禁止硬编码
    """

    _instance: Optional['ConfigLoader'] = None
    _config: Optional[Config] = None
    _last_load_time: float = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._config = None
        self._last_load_time = 0
        self._metric_client = None

    def _get_metric_client(self):
        """获取指标客户端"""
        if self._metric_client is None:
            self._metric_client = get_metric_client()
        return self._metric_client

    def get_config(self, force_reload: bool = False) -> Config:
        """
        获取配置（带缓存）
        force_reload: 是否强制重新加载
        """
        current_time = time.time()

        # 检查缓存是否过期（1小时）
        if (
            not force_reload
            and self._config is not None
            and (current_time - self._last_load_time) < 3600
        ):
            return self._config

        # 重新加载配置
        self._load_config()
        self._last_load_time = current_time
        return self._config

    def _load_config(self):
        """从数据库加载所有配置"""
        logger.info("[ConfigLoader] 开始加载配置...")

        config = Config()
        metric_client = self._get_metric_client()

        # 1. 加载维度配置
        config.dimension_configs = self._load_dimension_configs(metric_client)
        config.dimension_map = {
            d.dimension_name: d.column_name for d in config.dimension_configs
        }
        config.reverse_dimension_map = {
            d.column_name: d.dimension_name for d in config.dimension_configs
        }

        # 2. 加载意图模板（TODO: 从 Go API 获取）
        config.intent_templates = self._load_intent_templates()
        config.intent_types = ["query_value", "query_ranking", "query_trend", "compare", "query_dimension", "query_metadata", "other"]

        # 3. 加载 Prompt 模板（TODO: 从 Go API 获取）
        config.prompt_templates = self._load_prompt_templates()

        # 4. 加载图表规则（TODO: 从 Go API 获取）
        config.chart_rules = self._load_chart_rules()

        # 5. 加载业务术语（同义词）
        config.business_terms = self._load_business_terms(metric_client)

        # 6. 加载阈值配置
        config.clarification_threshold = 0.7
        config.confident_threshold = 0.85

        self._config = config
        logger.info(
            f"[ConfigLoader] 配置加载完成: "
            f"维度{len(config.dimension_configs)}个, "
            f"意图{len(config.intent_types)}种, "
            f"Prompt模板{len(config.prompt_templates)}个"
        )

    def _load_dimension_configs(self, metric_client) -> List[DimensionConfig]:
        """从 dimension_configs 表加载维度配置"""
        configs = metric_client.get_dimension_configs()
        result = []
        for c in configs:
            result.append(DimensionConfig(
                dimension_name=c.get("dimension_name", ""),
                column_name=c.get("column_name", ""),
                dimension_values=c.get("dimension_values"),
            ))
        return result

    def _load_intent_templates(self) -> List[IntentTemplate]:
        """从 intent_templates 表加载意图模板"""
        # TODO: 从 Go API 获取 intent_templates
        # 暂时返回默认意图模板
        return [
            IntentTemplate(
                id=1,
                name="查指标值",
                intent="query_value",
                patterns="是多少,有多少,多少",
                priority=10,
                response="好的，我来查询这个指标",
                status=1,
            ),
            IntentTemplate(
                id=2,
                name="查排名",
                intent="query_ranking",
                patterns="前10,排名,Top N",
                priority=10,
                response="好的，我来查询排名",
                status=1,
            ),
        ]

    def _load_prompt_templates(self) -> Dict[str, PromptTemplate]:
        """从 prompt_configs 表加载 Prompt 模板"""
        try:
            import httpx
            # 从 Go API 获取所有 prompt 配置
            resp = httpx.get("http://localhost:8080/api/v1/prompt-configs", timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0 and result.get("data"):
                    templates = {}
                    for item in result["data"]:
                        name = item.get("name", "")
                        if name:
                            templates[name] = PromptTemplate(
                                name=name,
                                content=item.get("prompt_text", ""),
                                model_name=item.get("model_name")
                            )
                    logger.info(f"[ConfigLoader] 加载 {len(templates)} 个 Prompt 模板")
                    return templates
            logger.warning("[ConfigLoader] 获取 Prompt 模板失败，使用空配置")
            return {}
        except Exception as e:
            logger.warning(f"[ConfigLoader] 加载 Prompt 模板异常: {e}，使用空配置")
            return {}

    def _load_chart_rules(self) -> List[ChartRule]:
        """从 prompt_configs 表加载图表推荐规则"""
        # TODO: 从 Go API 获取图表规则配置
        # 暂时返回默认规则
        return [
            ChartRule(intent_type="query_value", data_shape="single", chart_type="table"),
            ChartRule(intent_type="query_ranking", data_shape="multiple", chart_type="bar"),
            ChartRule(intent_type="query_trend", data_shape="timeseries", chart_type="line"),
            ChartRule(intent_type="compare", data_shape="multiple", chart_type="bar"),
        ]

    def _load_business_terms(self, metric_client) -> Dict[str, str]:
        """从 business_terms 表加载业务术语（同义词）

        Go API 返回的 business_terms 结构：
        - term: 标准术语名（如"未税收入"）
        - synonyms: 同义词数组（如 ["不含税收入", "净收入", "Net Revenue"]）
        """
        terms = metric_client.get_all_terms()
        result = {}
        for t in terms:
            standard_name = t.get("term", "")  # 标准术语名
            synonyms = t.get("synonyms", []) or []  # 同义词数组
            # 处理 PostgreSQL 数组格式（可能是 "{a,b,c}" 字符串）
            if isinstance(synonyms, str):
                synonyms = [s.strip().strip('"') for s in synonyms.strip("{}").split(",") if s.strip()]
            for synonym in synonyms:
                if synonym and standard_name:
                    result[synonym] = standard_name
        return result

    # ==================== 对外接口 ====================

    def get_dimension_map(self) -> Dict[str, str]:
        """获取维度映射表：中文名 → 列名"""
        return self.get_config().dimension_map

    def get_reverse_dimension_map(self) -> Dict[str, str]:
        """获取反向维度映射表：列名 → 中文名"""
        return self.get_config().reverse_dimension_map

    def get_column_name(self, dimension_name: str) -> Optional[str]:
        """将中文维度名转换为列名"""
        return self.get_config().dimension_map.get(dimension_name)

    def get_dimension_name(self, column_name: str) -> Optional[str]:
        """将列名反向转换为中文维度名（仅用于展示）"""
        return self.get_config().reverse_dimension_map.get(column_name)

    def get_intent_types(self) -> List[str]:
        """获取意图类型列表"""
        return self.get_config().intent_types

    def get_intent_template(self, intent: str) -> Optional[IntentTemplate]:
        """根据意图类型获取模板"""
        templates = self.get_config().intent_templates
        for t in templates:
            if t.intent == intent:
                return t
        return None

    def get_prompt_template(self, name: str) -> Optional[PromptTemplate]:
        """获取 Prompt 模板"""
        return self.get_config().prompt_templates.get(name)

    def get_business_term(self, term: str) -> Optional[str]:
        """查询业务术语（返回标准名称）"""
        return self.get_config().business_terms.get(term)

    def resolve_synonym(self, term: str) -> str:
        """解析同义词，返回标准名称"""
        return self.get_business_term(term) or term

    def reload_business_terms(self):
        """热更新业务术语配置（无需重启服务）

        调用此方法会重新从数据库加载业务术语同义词映射，
        用于在修改 business_terms 表后刷新缓存。
        """
        if self._config is None:
            self._config = self.get_config()
        metric_client = self._get_metric_client()
        new_business_terms = self._load_business_terms(metric_client)
        self._config.business_terms = new_business_terms
        logger.info(f"[ConfigLoader] 热更新业务术语完成，共 {len(new_business_terms)} 条同义词映射")

    def get_clarification_threshold(self) -> float:
        """获取澄清阈值"""
        return self.get_config().clarification_threshold

    def get_confident_threshold(self) -> float:
        """获取置信阈值"""
        return self.get_config().confident_threshold

    def get_chart_rules(self) -> List:
        """获取图表推荐规则"""
        return self.get_config().chart_rules

    def get_metric_by_code(self, metric_code: str) -> Optional[Dict[str, Any]]:
        """根据 metric_code 获取指标详情"""
        return self._get_metric_client().get_metric_by_code(metric_code)

    def get_metric_by_name(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """根据 metric_name 获取指标详情（模糊匹配）"""
        return self._get_metric_client().get_metric_by_name(metric_name)


# 全局单例
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """获取配置加载器单例"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader
