"""
规则引擎 - 模板匹配 + 指标知识库 + ML增强
从数据库加载意图模板和 SQL 模板，支持ML意图分类和实体抽取
"""
import re
import httpx
from typing import Optional, Dict, Any, List, Tuple
from ai.graph.state import IntentResult, SQLGenerationResult


class RuleEngine:
    """规则引擎 - 支持数据库配置的模板匹配 + ML增强"""

    def __init__(self, api_base: str = "http://localhost:8080", use_ml: bool = True):
        self.api_base = api_base
        self.metric_templates: Dict[str, Dict] = {}
        self.business_terms: Dict[str, Dict] = {}  # 业务术语映射
        self.intent_patterns: List[Dict] = []
        self.sql_templates: Dict[str, str] = {}
        self.use_ml = use_ml
        self.ml_classifier = None
        self.ml_extractor = None
        self.ml_similarity = None
        # 维度动态加载缓存
        self._dimension_cache: Dict[str, Dict[str, str]] = {}  # {dimension_type: {name: code}}
        self._dimension_cache_time: float = 0
        self._dimension_ttl: float = 3600  # 缓存1小时
        self._load_all()
        self._init_ml()

    def _load_all(self):
        """加载所有配置"""
        self._load_metrics()
        self._load_business_terms()  # 新增：加载业务术语
        self._load_nlp_templates()
        self._load_dimensions()  # 加载维度映射

    def _load_business_terms(self):
        """从 Go API 加载业务术语"""
        try:
            response = httpx.get(f"{self.api_base}/api/v1/metadata/terms", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    terms = data.get("data", [])
                    for t in terms:
                        term = t.get("term", "")
                        if term:
                            self.business_terms[term.lower()] = {
                                "term": term,
                                "description": t.get("description", ""),
                                "metric_ids": t.get("metric_ids", []),
                            }
                    print(f"[RuleEngine] 加载了 {len(self.business_terms)} 个业务术语")
        except Exception as e:
            print(f"[RuleEngine] 加载业务术语失败: {e}")

    def _load_dimensions(self):
        """从 Go API 动态加载维度映射，缓存1小时"""
        import time
        import json

        # 检查缓存是否有效
        if self._dimension_cache and (time.time() - self._dimension_cache_time) < self._dimension_ttl:
            print(f"[RuleEngine] 维度映射使用缓存 (剩余 {int(self._dimension_ttl - (time.time() - self._dimension_cache_time))}s)")
            return

        try:
            response = httpx.get(f"{self.api_base}/api/v1/metadata/dimensions", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    dimensions = data.get("data", [])
                    if dimensions:
                        self._dimension_cache = {}
                        for dim in dimensions:
                            code = dim.get("code", "")
                            values = dim.get("values", {})
                            if values and isinstance(values, dict):
                                # values 已经是 {name: code} 格式
                                self._dimension_cache[code] = values
                            elif values and isinstance(values, list):
                                # values 是列表格式，转换为 {name: code}
                                self._dimension_cache[code] = {v: v for v in values}
                            else:
                                # 尝试解析 JSON 字符串
                                try:
                                    self._dimension_cache[code] = json.loads(values) if isinstance(values, str) else {}
                                except:
                                    self._dimension_cache[code] = {}

                        self._dimension_cache_time = time.time()
                        print(f"[RuleEngine] 从API加载了 {len(self._dimension_cache)} 个维度类型: {list(self._dimension_cache.keys())}")
                        return
        except Exception as e:
            print(f"[RuleEngine] 加载维度映射失败: {e}, 将使用内置默认值")

        # API 为空或失败，使用内置默认值
        self._init_fallback_dimensions()
        self._dimension_cache_time = time.time()

    def _init_fallback_dimensions(self):
        """内置默认维度映射（API 不可用时 fallback）"""
        self._dimension_cache = {
            "platform": {
                "亚马逊": "amazon", "天猫": "tmall", "京东": "jd",
                "淘宝": "taobao", "拼多多": "pdd", "抖音": "douyin",
                "快手": "kuaishou", "ebay": "ebay", "沃尔玛": "walmart"
            },
            "region": {
                "华东": "east_china", "华南": "south_china", "华北": "north_china",
                "国内": "domestic", "海外": "overseas", "国外": "overseas",
                "美国": "usa", "英国": "uk", "欧洲": "europe",
                "东南亚": "seasia", "北美": "north_america",
            },
            "department": {
                "销售部": "sales", "销售": "sales",
                "市场部": "marketing", "市场": "marketing",
                "运营部": "operations", "运营": "operations",
                "客服部": "customer_service", "客服": "customer_service",
                "财务部": "finance", "财务": "finance",
                "人事部": "hr", "人事": "hr",
            },
            "site": {
                "旗舰店": "flagship", "专卖店": "specialty",
                "直营店": "direct", "加盟店": "franchise",
            },
            "category": {
                "美妆": "beauty", "服装": "apparel", "食品": "food",
                "数码": "digital", "家电": "appliance", "母婴": "baby",
                "图书": "books", "家居": "home",
            },
            "device": {
                "PC": "pc", "电脑端": "pc", "网页": "web",
                "移动": "mobile", "手机": "mobile", "APP": "app",
                "小程序": "miniprogram", "H5": "h5",
            },
        }

    def _get_dimension_mapping(self, dim_type: str) -> Dict[str, str]:
        """获取指定维度类型的映射表"""
        if not self._dimension_cache:
            self._load_dimensions()
        return self._dimension_cache.get(dim_type, {})

    def _load_metrics(self):
        """从 Go API 加载指标数据"""
        try:
            response = httpx.get(f"{self.api_base}/api/v1/metadata/metrics", timeout=10)
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
                    print(f"已加载 {len(self.metric_templates)} 个指标到规则引擎")
        except Exception as e:
            print(f"加载指标数据失败: {e}, 将使用内置模板")
            self._init_builtin_templates()

    def _load_nlp_templates(self):
        """从 Go API 加载 NLP 模板"""
        # 先初始化内置的基础意图模式
        self._init_builtin_patterns()
        self._init_builtin_sql_templates()

        try:
            response = httpx.get(f"{self.api_base}/api/v1/nlp/templates", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    nlp_data = data.get("data", {})

                    # 加载意图模板（追加而不是覆盖）
                    intent_templates = nlp_data.get("intent_templates", [])
                    for tpl in intent_templates:
                        patterns = tpl.get("patterns", "")
                        for p in patterns.split(","):
                            p = p.strip()
                            if p:
                                self.intent_patterns.append({
                                    "pattern": p,
                                    "intent": tpl.get("intent"),
                                    "priority": tpl.get("priority", 0),
                                })
                    # 按优先级排序
                    self.intent_patterns.sort(key=lambda x: x["priority"], reverse=True)

                    # 加载 SQL 模板
                    sql_tpls = nlp_data.get("sql_templates", [])
                    for tpl in sql_tpls:
                        key = f"{tpl.get('metric_code')}_{tpl.get('intent')}"
                        self.sql_templates[key] = tpl.get("sql_template", "")

                    print(f"已加载 {len(self.intent_patterns)} 个意图模式, {len(self.sql_templates)} 个 SQL 模板")
        except Exception as e:
            print(f"加载 NLP 模板失败: {e}, 将使用内置模式")
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
            "销售额": {"metric_code": "MKI-01-0001", "metric_name": "销售额", "unit": "元"},
            "营收": {"metric_code": "MKI-01-0001", "metric_name": "销售额", "unit": "元"},
            "收入": {"metric_code": "MKI-01-0001", "metric_name": "销售额", "unit": "元"},
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
        ]

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
            print("[RuleEngine] ML模块初始化完成")
        except Exception as e:
            print(f"[RuleEngine] ML模块初始化失败: {e}")
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
                print(f"[RuleEngine] ML分类失败: {e}")

        # 默认查询值
        return IntentResult(
            intent="query_value",
            confidence=0.5,
            entities={}
        )

    def link_business_terms(self, text: str) -> Dict[str, Any]:
        """链接业务术语到指标"""
        result = {}
        text_lower = text.lower()

        for term, metric_info in self.metric_templates.items():
            if term.lower() in text_lower:
                result.update(metric_info)
                break

        return result

    def link_business_terms_enhanced(self, text: str, current_entities: dict = None) -> Dict[str, Any]:
        """增强的实体链接 - 支持模糊匹配、维度提取和上下文继承"""
        result = {}
        text_lower = text.lower()

        print(f"[DEBUG] 实体链接，输入文本: {text}")
        print(f"[DEBUG] 可用的指标模板数量: {len(self.metric_templates)}")

        # ========== Step 0: 规则优先提取维度信息 ==========
        # 维度提取不依赖于指标匹配，应该在任何匹配之前进行
        extracted_dimensions = self._extract_dimensions(text)
        if extracted_dimensions:
            result.update(extracted_dimensions)
            print(f"[DEBUG] 规则提取维度: {extracted_dimensions}")

        # 先尝试精确匹配
        for term, metric_info in self.metric_templates.items():
            if term.lower() in text_lower:
                print(f"[DEBUG] 精确匹配成功: {term} -> {metric_info.get('metric_name')}")
                result.update(metric_info)
                # 恢复维度信息（不被 metric_info 覆盖）
                result.update(extracted_dimensions)
                return result

        # 尝试模糊匹配（包含关系）
        best_match = None
        best_score = 0

        for term, metric_info in self.metric_templates.items():
            term_lower = term.lower()
            if term_lower in text_lower:
                score = len(term_lower)
                if score > best_score:
                    best_score = score
                    best_match = metric_info
            else:
                common_chars = set(term_lower) & set(text_lower)
                if len(common_chars) >= 3 and len(term_lower) >= 4:
                    score = len(common_chars) / len(term_lower)
                    if score > 0.6 and score > best_score:
                        best_score = score
                        best_match = metric_info

        if best_match:
            print(f"[DEBUG] 模糊匹配成功: {best_match.get('metric_name')}")
            result.update(best_match)
            # 恢复维度信息
            result.update(extracted_dimensions)

        # 如果仍未匹配，使用ML实体抽取
        if not result and self.use_ml and self.ml_extractor:
            try:
                ml_entities = self.ml_extractor.extract(text)
                metric_name = ml_entities.get("metric_name")
                if metric_name:
                    # 尝试用抽取的指标名匹配
                    for term, metric_info in self.metric_templates.items():
                        if metric_name in term or term in metric_name:
                            result.update(metric_info)
                            print(f"[DEBUG] ML实体抽取匹配成功: {metric_name} -> {metric_info.get('metric_name')}")
                            break
                # 提取时间范围（即使没有匹配到指标也提取）
                time_range = ml_entities.get("time_range")
                raw_time = ml_entities.get("raw_time")
                if time_range:
                    # 转换为内部时间范围格式
                    time_range = self._normalize_time_range(time_range, raw_time)
                    result["time_range"] = time_range
                    result["raw_time"] = raw_time
                    print(f"[DEBUG] ML时间抽取: {time_range} (原始: {raw_time})")
                # 恢复维度信息
                result.update(extracted_dimensions)
            except Exception as e:
                print(f"[RuleEngine] ML实体抽取失败: {e}")

        # 继承上下文的指标信息 - 仅当查询是 follow-up 类型时才继承
        # 关键：如果完全没有匹配到任何指标（result为空），不继承上轮指标
        # 因为这说明用户可能在问一个不同的指标（如"用户数呢"问的是用户数，不是上轮的指标）
        if current_entities and not result:
            inherited_metric = current_entities.get("metric_name")
            if inherited_metric:
                # 检查是否是明确的 follow-up 查询（只有元数据相关的词，没有指标名）
                # 真正的 follow-up 示例："技术口径呢"、"业务定义呢"、"怎么计算的"
                # 不是 follow-up 的示例："用户数呢"、"访客数是多少"（这些是新指标查询）
                follow_up_only_indicators = ["定义", "口径", "规则", "怎么", "如何"]
                contains_metric_reference = any(word in text for word in ["数", "量", "额", "率", "次数", "人数", "销售额", "订单", "转化", "访客", "用户"])

                # 只有当查询只包含 follow-up 指示词，且不包含指标相关词汇时，才继承
                is_pure_followup = any(ind in text for ind in follow_up_only_indicators) and not contains_metric_reference

                if is_pure_followup:
                    # 这是 follow-up 查询，继承上轮指标
                    for term, metric_info in self.metric_templates.items():
                        if term == inherited_metric or term.lower() == inherited_metric.lower():
                            result.update(metric_info)
                            break

        print(f"[DEBUG] 实体链接结果: {result}")
        return result

    def _extract_dimensions(self, text: str) -> Dict[str, Any]:
        """
        规则优先提取维度信息（平台、地区、部门、站点等）
        从数据库动态加载维度映射，支持运行时更新
        返回: {"platform": "amazon", "region": "east_china", ...}
        """
        import re
        dimensions = {}

        # 获取动态维度映射
        platform_map = self._get_dimension_mapping("platform")
        region_map = self._get_dimension_mapping("region")
        department_map = self._get_dimension_mapping("department")
        site_map = self._get_dimension_mapping("site")
        category_map = self._get_dimension_mapping("category")
        device_map = self._get_dimension_mapping("device")

        # 平台维度
        for name, code in platform_map.items():
            if name in text:
                dimensions["platform"] = code
                dimensions["platform_name"] = name
                break

        # 地区维度（优先精确匹配）
        for name, code in region_map.items():
            if name in text:
                dimensions["region"] = code
                dimensions["region_name"] = name
                break

        # 如果没有精确匹配，尝试"华东区"、"华北区"等变体
        if "region" not in dimensions:
            # 提取所有地区关键词进行匹配
            region_keywords = list(region_map.keys())
            region_match = re.search(f"({'|'.join(region_keywords)})(区|地区)?", text)
            if region_match:
                name = region_match.group(1)
                if name in region_map:
                    dimensions["region"] = region_map[name]
                    dimensions["region_name"] = name

        # 部门维度
        for name, code in department_map.items():
            if name in text:
                dimensions["department"] = code
                dimensions["department_name"] = name
                break

        # 站点维度（店铺站点）
        for name, code in site_map.items():
            if name in text:
                dimensions["site"] = code
                dimensions["site_name"] = name
                break

        # 品类维度
        for name, code in category_map.items():
            if name in text:
                dimensions["category"] = code
                dimensions["category_name"] = name
                break

        # 设备维度
        for name, code in device_map.items():
            if name in text:
                dimensions["device"] = code
                dimensions["device_name"] = name
                break

        return dimensions

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
                is_definition_query = any(word in text for word in ["是什么", "定义", "含义", "解释", "啥", "什么意思", "由来"])

                if is_definition_query:
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
            print(f"[WARN] metric_code 包含不安全字符: {metric_code}")
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
