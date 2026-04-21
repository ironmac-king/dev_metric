"""
规则引擎 - 模板匹配 + 指标知识库 + ML增强
从数据库加载意图模板和 SQL 模板，支持ML意图分类和实体抽取
"""
import re
import httpx
from typing import Optional, Dict, Any, List, Tuple
from ai.graph.state import IntentResult, SQLGenerationResult
from ai.config.logging_config import get_logger
from ai.client.http_client import get_http_client

logger = get_logger("ai.rule_engine")


class RuleEngine:
    """规则引擎 - 支持数据库配置的模板匹配 + ML增强"""

    # 类级缓存，防止多次初始化（防止模块重载导致重复初始化）
    _initialized = False
    _shared_metrics: Dict[str, Dict] = {}
    _shared_business_terms: Dict[str, Dict] = {}
    _shared_intent_patterns: List[Dict] = []
    _shared_sql_templates: Dict[str, str] = {}

    def __init__(self, api_base: str = "http://localhost:8080", use_ml: bool = True):
        self.api_base = api_base
        self.use_ml = use_ml
        # 如果已经初始化过，直接使用类级缓存
        if RuleEngine._initialized:
            self.metric_templates = RuleEngine._shared_metrics
            self.business_terms = RuleEngine._shared_business_terms
            self.intent_patterns = RuleEngine._shared_intent_patterns
            self.sql_templates = RuleEngine._shared_sql_templates
            self.ml_classifier = None
            self.ml_extractor = None
            self.ml_similarity = None
            self._dimension_cache: Dict[str, Dict[str, str]] = {}
            self._dimension_cache_time: float = 0
            self._dimension_ttl: float = 3600
            logger.info("[RuleEngine] 使用已缓存的配置（模块已加载）")
            return

        self.metric_templates: Dict[str, Dict] = {}
        self.business_terms: Dict[str, Dict] = {}  # 业务术语映射
        self.intent_patterns: List[Dict] = []
        self.sql_templates: Dict[str, str] = {}
        self.ml_classifier = None
        self.ml_extractor = None
        self.ml_similarity = None
        # 维度动态加载缓存
        self._dimension_cache: Dict[str, Dict[str, str]] = {}  # {dimension_type: {name: code}}
        self._dimension_cache_time: float = 0
        self._dimension_ttl: float = 3600  # 缓存1小时
        self._load_all()
        self._init_ml()

        # 标记已初始化并缓存数据
        RuleEngine._initialized = True
        RuleEngine._shared_metrics = self.metric_templates
        RuleEngine._shared_business_terms = self.business_terms
        RuleEngine._shared_intent_patterns = self.intent_patterns
        RuleEngine._shared_sql_templates = self.sql_templates
        logger.info("[RuleEngine] 首次初始化完成，数据已缓存")

    def _load_all(self):
        """加载所有配置"""
        self._load_metrics()
        self._load_business_terms()  # 新增：加载业务术语
        self._load_nlp_templates()
        self._load_dimensions()  # 加载维度映射

    def reload_business_terms(self):
        """热更新业务术语（无需重启服务）"""
        logger.info("[RuleEngine] 热更新业务术语...")
        self.business_terms = {}
        self._load_business_terms()
        RuleEngine._shared_business_terms = self.business_terms
        logger.info("[RuleEngine] 热更新业务术语完成")

    def _load_business_terms(self):
        """从 Go API 加载业务术语"""
        try:
            client = get_http_client()
            response = client.get(f"{self.api_base}/api/v1/metadata/terms", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    terms = data.get("data", [])
                    for t in terms:
                        term = t.get("term", "")
                        if term:
                            # 处理 synonyms 可能是字符串（PostgreSQL数组格式如"{三级品类,三级类目}"）或列表
                            synonyms_raw = t.get("synonyms", [])
                            if isinstance(synonyms_raw, str):
                                # PostgreSQL 数组格式字符串，解析为列表
                                synonyms_raw = synonyms_raw.strip("{}").split(",") if synonyms_raw else []
                            synonyms = synonyms_raw if isinstance(synonyms_raw, list) else []

                            dim_field = t.get("dimension_field", "")
                            if dim_field:
                                logger.info(f"[RuleEngine] 加载业务术语: term={term}, synonyms={synonyms}, dimension_field={dim_field}")

                            self.business_terms[term.lower()] = {
                                "term": term,
                                "description": t.get("description", ""),
                                "metric_ids": t.get("metric_ids", []),
                                "synonyms": synonyms,  # 加载同义词
                                "dimension_field": dim_field,  # 维度字段
                                "dimension_value": t.get("dimension_value", ""),  # 维度值
                            }
                    logger.info(f"[RuleEngine] 加载了 {len(self.business_terms)} 个业务术语")
        except Exception as e:
            logger.info(f"[RuleEngine] 加载业务术语失败: {e}")

    def _load_dimensions(self):
        """从 Go API 动态加载维度映射，缓存1小时"""
        import time
        import json

        # 检查缓存是否有效
        if self._dimension_cache and (time.time() - self._dimension_cache_time) < self._dimension_ttl:
            logger.info(f"[RuleEngine] 维度映射使用缓存 (剩余 {int(self._dimension_ttl - (time.time() - self._dimension_cache_time))}s)")
            return

        try:
            # 从 dimension_configs 获取维度配置（支持"三级品类"等多级维度）
            client = get_http_client()
            response = client.get(f"{self.api_base}/api/v1/dimension-configs", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    configs = data.get("data", [])
                    if configs:
                        self._dimension_cache = {}
                        for cfg in configs:
                            dim_name = cfg.get("dimension_name", "")
                            column_name = cfg.get("column_name", "")
                            if dim_name and column_name and cfg.get("status") == 1:
                                # dimension_name 作为 key，{dimension_name: column_name} 作为值
                                self._dimension_cache[dim_name] = {dim_name: column_name}
                        self._dimension_cache_time = time.time()
                        logger.info(f"[RuleEngine] 从dimension_configs加载了 {len(self._dimension_cache)} 个维度: {list(self._dimension_cache.keys())}")
                        return
        except Exception as e:
            logger.info(f"[RuleEngine] 加载维度映射失败: {e}, 将使用内置默认值")

        # API 为空或失败，使用内置默认值
        self._init_fallback_dimensions()
        self._dimension_cache_time = time.time()

    def _init_fallback_dimensions(self):
        """
        内置默认维度映射（API 不可用时 fallback）
        重要：fallback 不用于模糊匹配，只作为最后保险
        移除容易误匹配的 department，避免"销量"匹配到"销售"等问题
        """
        self._dimension_cache = {
            "platform": {
                # 注意："亚马逊"等站点词已移到 site 维度，避免与 site 混淆
                "ebay": "ebay", "沃尔玛": "walmart"
            },
            "region": {
                "华东": "east_china", "华南": "south_china", "华北": "north_china",
                "国内": "domestic", "海外": "overseas", "国外": "overseas",
                "美国": "usa", "英国": "uk", "欧洲": "europe",
                "东南亚": "seasia", "北美": "north_america",
            },
            # site 站点维度 - 店铺/平台站点映射
            "site": {
                "亚马逊": "amazon", "亚马逊美国站": "amazon_us",
                "亚马逊欧洲站": "amazon_eu", "亚马逊日本站": "amazon_jp",
                "天猫": "tmall", "京东": "jd", "淘宝": "taobao",
                "拼多多": "pdd", "抖音": "douyin", "快手": "kuaishou",
            },
            # department 已移除，避免"销量"等词被错误匹配到"销售"
            # 如需启用，请确保 dimensions 表中有对应配置
        }
        logger.warning("[RuleEngine] 使用 fallback 维度映射，API 配置未加载或加载失败")

    def _get_dimension_mapping(self, dim_type: str) -> Dict[str, str]:
        """获取指定维度类型的映射表"""
        if not self._dimension_cache:
            self._load_dimensions()
        return self._dimension_cache.get(dim_type, {})

    def _load_metrics(self):
        """从 Go API 加载指标数据"""
        api_loaded = False
        try:
            client = get_http_client()
            response = client.get(f"{self.api_base}/api/v1/metadata/metrics", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    metrics = data.get("data", [])
                    for m in metrics:
                        name = m.get("name", "")
                        name_en = m.get("name_en", "") or ""
                        self.metric_templates[name] = {
                            "metric_code": m.get("metric_code", ""),
                            "metric_name": name,
                            "metric_id": m.get("id"),
                            "unit": m.get("unit", ""),
                            "starrocks_sql": m.get("starrocks_sql", ""),
                        }
                        if name_en:
                            self.metric_templates[name_en.lower()] = self.metric_templates[name]
                    api_loaded = True
                    logger.info(f"已加载 {len(self.metric_templates)} 个指标到规则引擎")
        except Exception as e:
            logger.warning(f"加载指标数据失败: {e}, 将使用内置模板")

        # 内置模板作为补充：API加载失败时完全替代，API加载成功时补充（防止数据库缺少某些常用指标）
        if not api_loaded:
            self._init_builtin_templates()
        else:
            # 补充加载内置模板（API数据可能缺少某些常用指标如"访客数"）
            builtin = {
                "访客数": {"metric_code": "MKI-02-0001", "metric_name": "访客数", "unit": "人"},
                "visitor": {"metric_code": "MKI-02-0001", "metric_name": "访客数", "unit": "人"},
                "visitors": {"metric_code": "MKI-02-0001", "metric_name": "访客数", "unit": "人"},
            }
            for k, v in builtin.items():
                if k not in self.metric_templates:
                    self.metric_templates[k] = v
            if builtin:
                logger.info(f"补充加载 {len(builtin)} 个内置指标模板")

    def _load_nlp_templates(self):
        """从 Go API 加载 NLP 模板（配置驱动：DB 优先，builtin 作为 fallback）"""
        try:
            client = get_http_client()
            response = client.get(f"{self.api_base}/api/v1/nlp/templates", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    nlp_data = data.get("data", {})

                    # 加载意图模板
                    intent_templates = nlp_data.get("intent_templates", [])
                    if intent_templates:
                        # DB 有配置，清空 builtin，使用 DB 配置
                        self.intent_patterns = []
                        self.intent_configs = {}  # 存储每个 intent 的完整配置
                        for tpl in intent_templates:
                            patterns = tpl.get("patterns", "")
                            intent = tpl.get("intent")
                            priority = tpl.get("priority", 0)
                            dimension_required = tpl.get("dimension_required", 0)
                            invalid_keywords = tpl.get("invalid_keywords", "")

                            # 解析泛指关键词列表
                            invalid_kw_list = [kw.strip() for kw in invalid_keywords.split(",") if kw.strip()]

                            # 存储完整配置（按 intent 类型分组，取最高优先级）
                            if intent not in self.intent_configs or priority > self.intent_configs[intent]["priority"]:
                                self.intent_configs[intent] = {
                                    "priority": priority,
                                    "dimension_required": dimension_required,
                                    "invalid_keywords": invalid_kw_list,
                                }

                            for p in patterns.split(","):
                                p = p.strip()
                                if p:
                                    self.intent_patterns.append({
                                        "pattern": p,
                                        "intent": intent,
                                        "priority": priority,
                                        "dimension_required": dimension_required,
                                        "invalid_keywords": invalid_kw_list,
                                    })
                        # 按优先级排序
                        self.intent_patterns.sort(key=lambda x: x["priority"], reverse=True)
                        logger.info(f"[RuleEngine] 已从 DB 加载 {len(self.intent_patterns)} 个意图模式，{len(self.intent_configs)} 个意图配置")
                    else:
                        # DB 没有配置，使用 builtin
                        logger.info("[RuleEngine] DB 无意图模板，使用 builtin 模式")
                        self._init_builtin_patterns()

                    # 加载 SQL 模板（仅 legacy 类型）
                    sql_tpls = nlp_data.get("sql_templates", [])
                    if sql_tpls:
                        self.sql_templates = {}
                        for tpl in sql_tpls:
                            # 只加载 legacy 类型模板，忽略 engine 类型
                            template_type = tpl.get("template_type", "legacy")
                            if template_type != "legacy":
                                continue
                            key = f"{tpl.get('metric_code')}_{tpl.get('intent')}"
                            self.sql_templates[key] = tpl.get("sql_template", "")
                        logger.info(f"[RuleEngine] 已从 DB 加载 {len(self.sql_templates)} 个 SQL 模板（legacy）")
                    else:
                        self._init_builtin_sql_templates()

                    return
        except Exception as e:
            logger.warning(f"[RuleEngine] 加载 NLP 模板失败: {e}, 使用内置模式")

        # Fallback: 使用内置模式
        self._init_builtin_patterns()
        self._init_builtin_sql_templates()

    def _init_builtin_templates(self):
        """内置指标模板"""
        self.metric_templates = {
            "访客数": {"metric_code": "MKI-02-0001", "metric_name": "访客数", "unit": "人"},
            "visitor": {"metric_code": "MKI-02-0001", "metric_name": "访客数", "unit": "人"},
            "visitors": {"metric_code": "MKI-02-0001", "metric_name": "访客数", "unit": "人"},
            "订单量": {"metric_code": "MKI-03-0001", "metric_name": "订单量", "unit": "笔"},
            "订单数": {"metric_code": "MKI-03-0001", "metric_name": "订单量", "unit": "笔"},
            "销售额": {"metric_code": "MKI-02-0009", "metric_name": "销售额", "unit": "元"},
            "营收": {"metric_code": "MKI-02-0009", "metric_name": "销售额", "unit": "元"},
            "收入": {"metric_code": "MKI-02-0009", "metric_name": "销售额", "unit": "元"},
        }

    def _init_builtin_patterns(self):
        """内置意图模式"""
        self.intent_patterns = [
            # 基础交互意图 - 最高优先级
            {"pattern": "你好", "intent": "greeting", "priority": 15},
            {"pattern": "您好", "intent": "greeting", "priority": 15},
            {"pattern": "hi", "intent": "greeting", "priority": 15},
            {"pattern": "hello", "intent": "greeting", "priority": 15},
            {"pattern": "嗨", "intent": "greeting", "priority": 15},
            {"pattern": "谢谢", "intent": "thanks", "priority": 15},
            {"pattern": "感谢", "intent": "thanks", "priority": 15},
            {"pattern": "再见", "intent": "bye", "priority": 15},
            {"pattern": "拜拜", "intent": "bye", "priority": 15},
            # 时间相关
            {"pattern": "昨天", "intent": "query_yesterday", "priority": 10},
            {"pattern": "昨日", "intent": "query_yesterday", "priority": 10},
            {"pattern": "今天", "intent": "query_today", "priority": 10},
            {"pattern": "今日", "intent": "query_today", "priority": 10},
            {"pattern": "本周", "intent": "query_this_week", "priority": 10},
            {"pattern": "本月", "intent": "query_this_month", "priority": 10},
            # 趋势对比
            {"pattern": "趋势", "intent": "query_trend", "priority": 8},
            {"pattern": "走势", "intent": "query_trend", "priority": 8},
            {"pattern": "对比", "intent": "query_comparison", "priority": 8},
            {"pattern": "同比", "intent": "query_comparison", "priority": 8},
            {"pattern": "环比", "intent": "query_comparison", "priority": 8},
            # 元数据查询
            {"pattern": "业务口径", "intent": "query_metadata", "priority": 12},
            {"pattern": "技术口径", "intent": "query_metadata", "priority": 12},
            {"pattern": "业务定义", "intent": "query_metadata", "priority": 12},
            {"pattern": "技术定义", "intent": "query_metadata", "priority": 12},
            {"pattern": "指标定义", "intent": "query_metadata", "priority": 12},
            {"pattern": "怎么算", "intent": "query_metadata", "priority": 10},
            {"pattern": "如何计算", "intent": "query_metadata", "priority": 10},
            # 排名分析 - 直接排名（不需要维度词配合）
            {"pattern": "最高", "intent": "query_ranking", "priority": 15, "dimension_required": 0, "invalid_keywords": []},
            {"pattern": "最低", "intent": "query_ranking", "priority": 15, "dimension_required": 0, "invalid_keywords": []},
            {"pattern": "最好", "intent": "query_ranking", "priority": 15, "dimension_required": 0, "invalid_keywords": []},
            {"pattern": "最差", "intent": "query_ranking", "priority": 15, "dimension_required": 0, "invalid_keywords": []},
            {"pattern": "第一名", "intent": "query_ranking", "priority": 15, "dimension_required": 0, "invalid_keywords": []},
            # 排名分析 - 需要维度词配合
            {"pattern": "比较好", "intent": "query_ranking", "priority": 14, "dimension_required": 1, "invalid_keywords": ["品类", "类目", "商品类", "产品类"]},
            {"pattern": "比较差", "intent": "query_ranking", "priority": 14, "dimension_required": 1, "invalid_keywords": ["品类", "类目", "商品类", "产品类"]},
        ]

        # 内置意图配置（按 intent 类型存储）
        self.intent_configs = {
            "query_ranking": {
                "priority": 15,
                "dimension_required": 0,
                "invalid_keywords": ["品类", "类目", "商品类", "产品类"],
            },
            "query_comparison": {
                "priority": 8,
                "dimension_required": 0,
                "invalid_keywords": [],
            },
        }

    def _init_builtin_sql_templates(self):
        """内置 SQL 模板"""
        self.sql_templates = {
            "query_yesterday": "SELECT * FROM metric_data WHERE metric_id = '{metric_id}' AND date = CURRENT_DATE - INTERVAL '1 day'",
            "query_today": "SELECT * FROM metric_data WHERE metric_id = '{metric_id}' AND date = CURRENT_DATE",
            "query_this_week": "SELECT * FROM metric_data WHERE metric_id = '{metric_id}' AND date >= DATE_TRUNC('week', CURRENT_DATE)",
            "query_this_month": "SELECT * FROM metric_data WHERE metric_id = '{metric_id}' AND date >= DATE_TRUNC('month', CURRENT_DATE)",
            "query_trend": "SELECT date, value FROM metric_data WHERE metric_id = '{metric_id}' ORDER BY date DESC LIMIT 30",
            "query_total": "SELECT SUM(value) as total FROM metric_data WHERE metric_id = '{metric_id}'",
        }

    def _init_ml(self):
        """初始化ML模块"""
        if not self.use_ml:
            return

        try:
            from ai.ml import get_intent_classifier, get_entity_extractor, get_similar_recommender
            self.ml_classifier = get_intent_classifier()
            self.ml_extractor = get_entity_extractor()
            self.ml_similarity = get_similar_recommender()
            logger.info("[RuleEngine] ML模块初始化完成")
        except Exception as e:
            logger.info(f"[RuleEngine] ML模块初始化失败: {e}")
            self.use_ml = False

    def recognize_intent(self, text: str) -> Optional[IntentResult]:
        """识别用户意图"""
        text_lower = text.lower()

        # 使用数据库配置的意图模式
        for item in self.intent_patterns:
            if item["pattern"].lower() in text_lower:
                return IntentResult(
                    intent=item["intent"],
                    confidence=0.9,
                    entities={"intent_pattern": item["pattern"]}
                )

        # 规则未匹配，使用ML分类器
        if self.use_ml and self.ml_classifier:
            try:
                ml_intent, ml_confidence = self.ml_classifier.predict(text)
                if ml_intent != "unknown" and ml_confidence > 0.5:
                    return IntentResult(
                        intent=ml_intent,
                        confidence=ml_confidence,
                        entities={"intent_pattern": f"[ML]{text[:10]}..."}
                    )
            except Exception as e:
                logger.info(f"[RuleEngine] ML分类失败: {e}")

        # 默认查询值
        return IntentResult(
            intent="query_value",
            confidence=0.5,
            entities={}
        )

    def detect_intent_override(self, text: str, current_intent: str) -> Optional[Dict]:
        """
        检测意图覆盖模式（配置化实现）

        当用户的查询匹配特定模式时（如"比较好/差+维度词"），需要强制覆盖当前意图。
        这个方法处理那些需要组合条件判断的复杂模式：
        1. 基础关键词匹配（如"比较"）
        2. invalid_keywords 检查（如"品类"等泛指词存在则跳过）
        3. dimension_required 检查（需要同时存在维度词）

        返回: 如果匹配返回覆盖信息 {"intent": "...", "confidence": 0.95, "entities": {...}}，否则返回 None
        """
        text_lower = text.lower()

        # 通用维度词列表（用于检测是否存在维度词）
        dimension_words = ['品', '类', '店', '铺', '牌', '道', '路', '区', '域', '台', '站', '国', '家', '客', '户', '商', 'ASIN', 'SKU']

        for pattern_info in self.intent_patterns:
            pattern = pattern_info.get("pattern", "").lower()
            if not pattern or pattern not in text_lower:
                continue

            intent = pattern_info.get("intent")
            if not intent:
                continue

            # 【Bug Fix 4 修复】检查 dimension_required=1 的模式
            # 注意：这个检查必须在 current_intent == intent 判断之前！
            # 因为 dimension_required=1 的目的是在意图识别正确时也要追问（用户用了泛指词如"品类"）
            if pattern_info.get("dimension_required") == 1:
                has_dimension_word = any(dim in text_lower for dim in dimension_words)
                if has_dimension_word:
                    # 检查 invalid_keywords
                    invalid_keywords = pattern_info.get("invalid_keywords", [])
                    # 【Bug Fix】只检查独立的泛指词，排除"三级品类"等具体级别
                    # "品类"出现在"三级品类"里不算invalid，只有单独的"品类"才算
                    category_level_prefixes = ["一级", "二级", "三级", "四级", "五级"]
                    has_invalid_kw = False
                    for inv_kw in invalid_keywords:
                        if inv_kw in text_lower:
                            # 检查是否是"X级品类"或"X品类"格式（具体级别，不是泛指）
                            is_specific_level = False
                            for prefix in category_level_prefixes:
                                if f"{prefix}{inv_kw}" in text_lower:
                                    is_specific_level = True
                                    break
                            if not is_specific_level:
                                has_invalid_kw = True
                                break
                    logger.info(f"[detect_intent_override] dimension_required=1: text='{text}', has_dimension_word={has_dimension_word}, has_invalid_kw={has_invalid_kw}, invalid_kws={invalid_keywords}")
                    for inv_kw in invalid_keywords:
                        logger.info(f"[detect_intent_override] checking inv_kw='{inv_kw}', in text={inv_kw in text_lower}")
                    if has_invalid_kw:
                        # 【废弃旧追问逻辑】不再在此触发 category_level 追问
                        # 槽位追问统一由 SlotClarificationEngine._check_required_slots() 处理
                        # 这里只返回 intent 识别结果，不触发追问
                        logger.info(f"[detect_intent_override] 检测到泛指词但已废弃旧追问逻辑，跳过追问，交给 SlotClarificationEngine 统一处理")
                        pass  # 不再触发追问

            # 如果当前意图已经是这个 intent，不需要覆盖
            if current_intent == intent:
                continue

            # 【Bug Fix 4 修复】检查 dimension_required=1 的模式 END

            # 检查 invalid_keywords（如果配置了）
            invalid_keywords = pattern_info.get("invalid_keywords", [])
            if invalid_keywords:
                # 检查是否有 invalid_keyword 命中
                has_invalid_kw = False
                for inv_kw in invalid_keywords:
                    if inv_kw in text_lower:
                        has_invalid_kw = True
                        logger.debug(f"[detect_intent_override] invalid_keyword '{inv_kw}' 命中")
                        break
                if has_invalid_kw:
                    # 返回追问标记
                    return {
                        "intent": intent,
                        "confidence": 0.95,
                        "entities": {
                            "override_reason": f"pattern: {pattern}, invalid_kw_triggered"
                        }
                    }

            # 不需要维度词配合或没有触发追问条件，直接匹配
            return {
                "intent": intent,
                "confidence": 0.95,
                "entities": {
                    "override_reason": f"pattern: {pattern}"
                }
            }

        return None

    def link_business_terms(self, text: str) -> Dict[str, Any]:
        """链接业务术语到指标"""
        result = {}
        text_lower = text.lower()

        for term, metric_info in self.metric_templates.items():
            if term.lower() in text_lower:
                result.update(metric_info)
                break

        return result

    def _match_by_synonyms(self, text: str) -> Optional[str]:
        """通过同义词匹配找到标准术语或维度值映射

        匹配策略：分词整词匹配为主 + 短词子串兜底
        - 缩写类（DAU、UV）用子串匹配，避免分词破坏
        - 完整词类用分词后整词匹配，避免误匹配

        返回值格式：
        - 维度值映射: __DIM_VALUE__{dimension_field}__{dimension_value}
        - 指标映射: __METRIC__{metric_id}
        - 标准术语: 术语名称（用于后续指标匹配）
        """
        import jieba

        tokens = jieba.lcut(text)  # 分词
        text_lower = text.lower()

        for term, info in self.business_terms.items():
            synonyms = info.get("synonyms", [])
            if not synonyms:
                continue
            for syn in synonyms:
                if not syn:
                    continue
                syn_lower = syn.lower()
                # 短词（<=3字符）用子串匹配，兼容缩写类
                if len(syn) <= 3:
                    if syn_lower in text_lower:
                        logger.debug(f"同义词匹配成功: '{syn}' -> 术语 '{info.get('term')}'")
                        # 返回维度值映射或指标映射
                        dimension_value = info.get("dimension_value", "")
                        if dimension_value:
                            dimension_field = info.get("dimension_field", "")
                            return f"__DIM_VALUE__{dimension_field}__{dimension_value}"
                        metric_ids = info.get("metric_ids", [])
                        if metric_ids:
                            return f"__METRIC__{metric_ids[0]}"
                        return info.get("term")
                else:
                    # 长词用分词后整词匹配
                    token_lowers = [t.lower() for t in tokens]
                    if syn_lower in token_lowers:
                        logger.debug(f"同义词匹配成功: '{syn}' -> 术语 '{info.get('term')}'")
                        # 返回维度值映射或指标映射
                        dimension_value = info.get("dimension_value", "")
                        if dimension_value:
                            dimension_field = info.get("dimension_field", "")
                            return f"__DIM_VALUE__{dimension_field}__{dimension_value}"
                        metric_ids = info.get("metric_ids", [])
                        if metric_ids:
                            return f"__METRIC__{metric_ids[0]}"
                        return info.get("term")
        return None

    def link_business_terms_enhanced(self, text: str, current_entities: dict = None) -> Dict[str, Any]:
        """增强的实体链接 - 支持模糊匹配、维度提取和上下文继承"""
        result = {}
        text_lower = text.lower()

        logger.debug(f"实体链接，输入文本: {text}")
        logger.debug(f"可用的指标模板数量: {len(self.metric_templates)}")

        # 标志：是否成功匹配到指标（用于判断是否需要同义词兜底）
        found_metric = False

        # ========== Step 0: 规则优先提取维度信息 ==========
        # 维度提取不依赖于指标匹配，应该在任何匹配之前进行
        extracted_dimensions = self._extract_dimensions(text)
        if extracted_dimensions:
            logger.debug(f"规则提取维度: {extracted_dimensions}")

        # ========== Step 0.5: 否定检测（处理"不含税收入"vs"含税收入"等）==========
        # 当查询包含否定词时，优先匹配也包含"未"/"不含"的指标，而非"含"的指标
        negation_prefixes = ["不含", "未", "无", "非"]
        has_negation = any(neg in text for neg in negation_prefixes)
        negation_term = None
        for neg in negation_prefixes:
            if neg in text:
                negation_term = neg
                break
        logger.debug(f"否定检测: has_negation={has_negation}, negation_term={negation_term}")

        # 收集所有匹配（精确+模糊），不 early return
        all_matches = []  # (score, metric_info) tuples

        # 【修复】创建去空格版本的文本，用于处理用户输入带空格的情况
        # 如 "B2B APP会话量" -> "b2bapp会话量"
        text_lower = text.lower().strip()  # 处理前后空白
        text_no_space_lower = text_lower.replace(" ", "").replace("　", "")

        # 精确匹配（双向包含，支持去空格匹配）
        for term, metric_info in self.metric_templates.items():
            term_lower = term.lower()
            term_no_space_lower = term_lower.replace(" ", "").replace("　", "")
            # 原文匹配
            if term_lower in text_lower or text_lower in term_lower:
                logger.debug(f"双向精确匹配: {term} -> {metric_info.get('metric_name')}")
                all_matches.append((1.0, term, metric_info))
            # 去空格匹配（用户输入带空格，如 "B2B APP" 匹配 "B2BAPP"）
            elif term_no_space_lower in text_no_space_lower or text_no_space_lower in term_no_space_lower:
                logger.debug(f"双向精确匹配(去空格): {term} -> {metric_info.get('metric_name')}")
                all_matches.append((0.99, term, metric_info))  # 略低于原文匹配

        # 模糊匹配（字符重叠，支持去空格）
        for term, metric_info in self.metric_templates.items():
            term_lower = term.lower()
            term_no_space_lower = term_lower.replace(" ", "").replace("　", "")
            # 跳过已精确匹配的
            if any(term == t for _, t, _ in all_matches):
                continue
            # 原文模糊匹配
            if term_lower in text_lower:
                score = len(term_lower) / max(len(text_lower), 1)
                all_matches.append((score, term, metric_info))
            elif term_no_space_lower in text_no_space_lower:
                # 去空格模糊匹配
                score = len(term_no_space_lower) / max(len(text_no_space_lower), 1) * 0.95  # 略低
                all_matches.append((score, term, metric_info))
            else:
                # 字符重叠也去掉空格计算
                common_chars = set(term_no_space_lower) & set(text_no_space_lower)
                if len(common_chars) >= 2 and len(term_no_space_lower) >= 3:
                    score = len(common_chars) / len(term_no_space_lower)
                    if score > 0.25:  # 降低阈值到 0.25
                        all_matches.append((score, term, metric_info))

        # ========== Step 2.5: 语义搜索增强 ==========
        # 语义搜索能理解"未税收入"是"不含税收入"的语义匹配，
        # 而不是字符重叠的"含税收入"(子串匹配得1.0分但语义错误)
        semantic_info, semantic_confidence = self.semantic_search_metric(text)
        if semantic_info and semantic_confidence == "high":
            # 高置信度语义匹配：直接覆盖字符重叠结果
            logger.debug(f"语义搜索高置信度命中: {text} -> {semantic_info.get('metric_name')}")
            result.update(semantic_info)
            result.update(extracted_dimensions)
            return result

        # 中低置信度语义匹配：增加加成权重以克服字符子串匹配
        semantic_boost = 0.0
        if semantic_info and semantic_info.get("metric_code"):
            if semantic_confidence == "medium":
                semantic_boost = 0.25  # 中置信度加 0.25
            elif semantic_confidence == "low":
                semantic_boost = 0.15  # 低置信度加 0.15

        # 重新计算所有匹配分数，结合语义加成
        if semantic_boost > 0 and semantic_info:
            semantic_code = semantic_info.get("metric_code")
            for i, (score, term, metric_info) in enumerate(all_matches):
                if metric_info.get("metric_code") == semantic_code:
                    new_score = score + semantic_boost
                    all_matches[i] = (new_score, term, metric_info)
                    logger.debug(f"语义加成: {term} +{semantic_boost:.2f} -> {new_score:.2f}")

        # ========== Step 2.6: 否定惩罚 ==========
        # 当查询包含"不含/未/无/非"时，对包含"含"但不含"未/不含/无/非"的指标进行惩罚
        # 例如："不含税收入"不应匹配"含税收入"，需要惩罚到比未税收入(0.75)还低
        if has_negation and negation_term:
            negation_penalty = 0.55  # 必须足够大才能克服子串匹配(1.0)和字符重叠(0.75)
            for i, (score, term, metric_info) in enumerate(all_matches):
                term_lower_for_penalty = term.lower()
                # 如果指标名包含"含"但不含"未"/"不含"/"无"/"非"，施加惩罚
                has_han = "含" in term_lower_for_penalty
                has_negation_indicator = any(neg in term_lower_for_penalty for neg in ["未", "不含", "无", "非", "不含税", "未税", "无税", "非税"])
                if has_han and not has_negation_indicator:
                    new_score = score - negation_penalty
                    all_matches[i] = (new_score, term, metric_info)
                    logger.debug(f"否定惩罚: {term} -{negation_penalty:.2f} -> {new_score:.2f} (因为含但不匹配否定)")

        # 按分数排序，取最高分（去重，相同 metric_name 只取最高分）
        seen_metrics = set()
        sorted_matches = []
        for score, term, metric_info in sorted(all_matches, key=lambda x: -x[0]):
            mn = metric_info.get('metric_name', '')
            if mn not in seen_metrics:
                seen_metrics.add(mn)
                sorted_matches.append((score, term, metric_info))

        if sorted_matches:
            top_score, top_term, top_metric = sorted_matches[0]
            logger.debug(f"最佳匹配: {top_term} (score={top_score:.2f}) -> {top_metric.get('metric_name')}")
            result.update(top_metric)
            found_metric = True
            result.update(extracted_dimensions)
            # 如果有多个不同指标，返回多指标列表
            if len(sorted_matches) > 1:
                result["_multi_metrics"] = [
                    {"term": t, "score": s, **m}
                    for s, t, m in sorted_matches[:5]  # 最多5个
                ]

        # 如果仍未匹配，使用ML实体抽取
        if not found_metric and self.use_ml and self.ml_extractor:
            try:
                ml_entities = self.ml_extractor.extract(text)
                metric_name = ml_entities.get("metric_name")
                if metric_name:
                    # 尝试用抽取的指标名匹配
                    for term, metric_info in self.metric_templates.items():
                        if metric_name in term or term in metric_name:
                            result.update(metric_info)
                            found_metric = True
                            logger.debug(f"ML实体抽取匹配成功: {metric_name} -> {metric_info.get('metric_name')}")
                            break
                # 提取时间范围（即使没有匹配到指标也提取）
                time_range = ml_entities.get("time_range")
                raw_time = ml_entities.get("raw_time")
                if time_range:
                    # 转换为内部时间范围格式
                    time_range = self._normalize_time_range(time_range, raw_time)
                    result["time_range"] = time_range
                    result["raw_time"] = raw_time
                    logger.debug(f"ML时间抽取: {time_range} (原始: {raw_time})")
                # 恢复维度信息
                result.update(extracted_dimensions)
            except Exception as e:
                logger.info(f"[RuleEngine] ML实体抽取失败: {e}")

        # ========== Step 5: 同义词匹配（规则+ML失败后兜底）==========
        if not found_metric:
            matched_term = self._match_by_synonyms(text)
            if matched_term:
                # 处理维度值映射格式: __DIM_VALUE__{dimension_field}__{dimension_value}
                if matched_term.startswith("__DIM_VALUE__"):
                    parts = matched_term.split("__")
                    if len(parts) >= 4:
                        dimension_field = parts[2]
                        dimension_value = parts[3]
                        result[f"dim_{dimension_field}"] = dimension_value
                        logger.debug(f"同义词维度值匹配成功: '{dimension_field}' = '{dimension_value}'")
                        result.update(extracted_dimensions)
                # 处理指标映射格式: __METRIC__{metric_id}
                elif matched_term.startswith("__METRIC__"):
                    metric_id = matched_term.split("__")[2]
                    result["metric_id"] = int(metric_id)
                    logger.debug(f"同义词指标匹配成功: metric_id = {metric_id}")
                    result.update(extracted_dimensions)
                else:
                    # 用匹配到的标准术语再次匹配指标
                    for term, metric_info in self.metric_templates.items():
                        if term.lower() == matched_term.lower():
                            result.update(metric_info)
                            logger.debug(f"同义词标准术语匹配成功: '{matched_term}' -> {metric_info.get('metric_name')}")
                            result.update(extracted_dimensions)
                            break

        # 继承上下文的指标信息 - 仅当查询是 follow-up 类型时才继承
        # 关键：如果完全没有匹配到任何指标（result为空），不继承上轮指标
        # 因为这说明用户可能在问一个不同的指标（如"用户数呢"问的是用户数，不是上轮的指标）
        if current_entities and not result:
            inherited_metric = current_entities.get("metric_name")
            if inherited_metric:
                # 检查是否是明确的 follow-up 查询（只有元数据相关的词，没有指标名）
                # 真正的 follow-up 示例："技术口径呢"、"业务定义呢"、"怎么计算的"
                # 不是 follow-up 的示例："用户数呢"、"访客数是多少"（这些是新指标查询）
                follow_up_only_indicators = ["定义", "口径", "规则", "怎么", "如何", "环比", "同比"]
                # 注意：环比/同比是意图词，不是指标名，不要加入 contains_metric_reference
                contains_metric_reference = any(word in text for word in ["数", "量", "额", "率", "次数", "人数", "销售额", "订单", "转化", "访客", "用户"])

                # 只有当查询只包含 follow-up 指示词，且不包含指标相关词汇时，才继承
                is_pure_followup = any(ind in text for ind in follow_up_only_indicators) and not contains_metric_reference

                if is_pure_followup:
                    # 这是 follow-up 查询，继承上轮指标
                    for term, metric_info in self.metric_templates.items():
                        if term == inherited_metric or term.lower() == inherited_metric.lower():
                            result.update(metric_info)
                            break

        logger.debug(f"实体链接结果: {result}")
        return result

    def _extract_dimensions(self, text: str) -> Dict[str, Any]:
        """
        规则优先提取维度信息（平台、地区、部门、站点等）
        从数据库动态加载维度映射，支持运行时更新
        返回: {"platform": "amazon", "region": "east_china", ...}

        使用分词精确匹配：按标点和空格分词后检查，避免"销量"匹配到"销售"等问题
        """
        import re
        dimensions = {}

        # 分词：按标点和空格切分，"上月销量是多少，亚马逊" → ["上月销量是多少", "亚马逊"]
        words = re.split(r'[,，、\s]+', text)
        words = [w.strip() for w in words if w.strip()]

        # ========== Step 0.5: 匹配 "SKU 数字" 模式（如 "SKU 10101"）==========
        # 匹配 SKU/ASIN + 数字的模式
        sku_pattern = re.search(r'SKU\s*(\d+)', text, re.IGNORECASE)
        if sku_pattern:
            dimensions["SKU"] = sku_pattern.group(1)
            logger.debug(f"[RuleEngine] SKU数字匹配: SKU={sku_pattern.group(1)}")

        asin_pattern = re.search(r'ASIN\s*([A-Z0-9]+)', text, re.IGNORECASE)
        if asin_pattern:
            dimensions["ASIN"] = asin_pattern.group(1)
            logger.debug(f"[RuleEngine] ASIN匹配: ASIN={asin_pattern.group(1)}")

        # ========== Step 1: 优先从 business_terms 同义词匹配 ==========
        # 如果 business_terms 有 synonyms 配置，优先检查
        if self.business_terms:
            for term_key, term_info in self.business_terms.items():
                synonyms = term_info.get("synonyms", [])
                dimension_field = term_info.get("dimension_field", "")
                dimension_value = term_info.get("dimension_value", "")
                # 检查用户输入是否包含该同义词（支持子串匹配）
                for syn in synonyms:
                    if not syn:
                        continue
                    # 检查原始文本中是否包含该同义词
                    if syn in text or syn.lower() in text.lower():
                        if dimension_field:
                            # 即使 dimension_value 为空，也记录 dimension_field
                            # 这表示用户提到了这个维度（如"平台"作为"店铺"的同义词）
                            dimensions[dimension_field] = dimension_value if dimension_value else "__SYNONYM__"
                            dimensions[f"{dimension_field}_name"] = term_key  # 用术语名作为维度显示名
                            logger.debug(f"[RuleEngine] 同义词匹配: '{syn}' -> {dimension_field}={dimension_value} (term={term_key})")
                            break
                if dimensions:
                    break

        # 如果已从同义词匹配到维度，直接返回
        if dimensions:
            return dimensions

        # ========== 动态维度匹配：从 dimension_configs 加载的所有维度 ==========
        # _dimension_cache 的结构: {"维度名": {"维度名": "列名"}, ...}
        # 例如: {"三级品类": {"三级品类": "GROUP_3"}, "站点": {"站点": "FSITECODE"}, ...}
        for dim_name, dim_mapping in self._dimension_cache.items():
            for name, code in dim_mapping.items():
                # 分词精确匹配
                if name in words:
                    # 如果 code == name（如 "ASIN" == "ASIN"），表示这是维度类型而非具体值
                    # 设置为 __SYNONYM__ 表示"识别了维度类型但无具体值"
                    if code == name:
                        dimensions[dim_name] = "__SYNONYM__"
                    else:
                        dimensions[dim_name] = code
                    dimensions[f"{dim_name}_name"] = name
                    break
                # 子串匹配（支持"三级品类"在文本中间的情况）
                if name in text:
                    if code == name:
                        dimensions[dim_name] = "__SYNONYM__"
                    else:
                        dimensions[dim_name] = code
                    dimensions[f"{dim_name}_name"] = name
                    break

        # 备选：地区维度变体匹配（"华东区"、"华北区"等）
        if "region" not in dimensions and "华东" not in dimensions and "华北" not in dimensions:
            for dim_name, dim_mapping in self._dimension_cache.items():
                for name, code in dim_mapping.items():
                    if re.search(f"({'|'.join(['华东', '华南', '华北', '华西', '西南'])})区?", text):
                        dimensions["region"] = code
                        dimensions["region_name"] = name
                        break

        return dimensions

    def _validate_all_dimensions(self, dimensions: Dict[str, Any]) -> tuple:
        """
        校验所有提取到的维度，只保留 dimensions 表中配置过的值
        返回: (valid_dimensions, invalid_dimensions)
        """
        from typing import Tuple, List, Any
        valid = {}
        invalid = []
        for dim_type, dim_value in dimensions.items():
            dim_map = self._get_dimension_mapping(dim_type)
            # 检查 dim_value 是否在配置的映射表中（支持 code 或 name 两种方式）
            if dim_value in dim_map.values() or dim_value in dim_map.keys():
                valid[dim_type] = dim_value
            else:
                invalid.append(f"{dim_type}={dim_value}")
        return valid, invalid

    def _normalize_time_range(self, time_type: str, raw_time: str = None) -> str:
        """
        将ML提取的时间类型转换为内部格式
        例如: recent_days + "最近7天" -> last_7_days
        """
        import re
        # 映射表：ML格式 -> 内部格式
        time_mapping = {
            "yesterday": "yesterday",
            "today": "today",
            "tomorrow": "tomorrow",
            "this_week": "this_week",
            "last_week": "last_week",
            "next_week": "next_week",
            "this_month": "this_month",
            "last_month": "last_month",
            "next_month": "next_month",
            "this_year": "this_year",
            "last_year": "last_year",
            "this_quarter": "this_quarter",
            "last_quarter": "last_quarter",
        }
        if time_type in time_mapping:
            return time_mapping[time_type]
        # 处理 recent_days, past_days 等动态时间
        if time_type in ("recent_days", "past_days") and raw_time:
            # 从原始文本中提取数字，如"最近7天" -> 7
            match = re.search(r'(\d+)', raw_time)
            if match:
                days = match.group(1)
                return f"last_{days}_days"
        if time_type == "recent_weeks" and raw_time:
            match = re.search(r'(\d+)', raw_time)
            if match:
                weeks = match.group(1)
                return f"last_{weeks}_weeks"
        if time_type == "recent_months" and raw_time:
            match = re.search(r'(\d+)', raw_time)
            if match:
                months = match.group(1)
                return f"last_{months}_months"
        # 默认返回原值
        return time_type

    def recognize_business_term(self, text: str) -> Optional[Dict[str, Any]]:
        """
        识别业务术语查询
        如果用户问的是业务术语（如ASIN、SKU）的定义，返回术语解释

        Returns:
            如果识别到业务术语查询，返回 {"is_business_term": True, "term": "...", "description": "..."}
            否则返回 None
        """
        text_lower = text.lower()

        # 检查是否包含业务术语
        for term_key, term_info in self.business_terms.items():
            if term_key in text_lower:
                # 找到了业务术语
                term = term_info.get("term", "")
                description = term_info.get("description", "")

                # 判断用户意图：是想了解术语含义，还是想查数据
                # 问"是什么"、"定义"、"含义" → 查术语解释
                # 问"数据"、"多少"、"怎么查" → 查相关指标

                # 【重要】如果用户同时问了指标相关的问题（如"销售额"、"访问量"、
                # "排名"、"最高"等），说明用户是想查数据，不是问术语定义
                # 例如："销售额最高的SKU是啥" → 不是问 SKU 定义，而是问哪个 SKU 销售额最高
                data_related_keywords = ["销售额", "访问量", "销量", "订单", "转化", "排名", "最高", "最低", "最多", "最少", "前几", "第几", "第一名"]
                is_data_query = any(kw in text for kw in data_related_keywords)

                is_definition_query = any(word in text for word in ["是什么", "定义", "含义", "解释", "啥", "什么意思", "由来"])

                # 只有当用户明确问术语定义，且没有同时问数据问题时，才返回术语解释
                if is_definition_query and not is_data_query:
                    return {
                        "is_business_term": True,
                        "term": term,
                        "description": description,
                        "intent": "query_term_definition",
                        "related_metrics": term_info.get("metric_ids", []),
                    }

        return None

    def try_match_sql(self, intent: str, entities: Dict[str, Any]) -> Optional[SQLGenerationResult]:
        """尝试规则匹配 SQL"""
        metric_code = entities.get("metric_code", "")

        # 安全校验：metric_code 只允许字母、数字、连字符、下划线
        import re
        if metric_code and not re.match(r'^[\w-]+$', metric_code):
            logger.warning(f"metric_code 包含不安全字符: {metric_code}")
            return None

        # 先查数据库配置的 SQL 模板
        if metric_code:
            key = f"{metric_code}_{intent}"
            if key in self.sql_templates:
                sql = self.sql_templates[key].format(metric_id=metric_code)
                return SQLGenerationResult(
                    sql=sql,
                    params={"metric_code": metric_code},
                    is_safe=True
                )

        # 使用内置 SQL 模板
        if intent not in self.sql_templates:
            return None

        if not metric_code:
            return None

        sql = self.sql_templates[intent].format(metric_id=metric_code)

        return SQLGenerationResult(
            sql=sql,
            params={"metric_code": metric_code},
            is_safe=True
        )

    def semantic_search_intent(self, query: str) -> Tuple[Optional[str], float]:
        """语义搜索意图 - 返回原始相似度分数"""
        from ai.engine.semantic_search import semantic_search
        return semantic_search.search_intent(query)

    def semantic_search_metric(self, query: str) -> Tuple[Optional[Dict], float]:
        """语义搜索指标（委托给 SemanticSearch）"""
        from ai.engine.semantic_search import semantic_search
        return semantic_search.match_metric(query)
