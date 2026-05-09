"""
槽位追问引擎 - 配置化驱动
从数据库加载槽位定义，支持动态数据源（dimension_configs、metrics表）
"""
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from ai.config.logging_config import get_logger
from ai.config.runtime import get_go_api_base
from ai.client.metric_client import MetricClient, get_http_client
from ai.engine.semantic_search import SemanticSearch

logger = get_logger("ai.slot_clarification_engine")


@dataclass
class SlotClarification:
    """槽位追问对象"""
    slot_name: str
    display_name: str
    question: str
    priority: int
    slot_type: str  # required/optional
    allowed_values: List[str] = field(default_factory=list)
    default_value: Optional[str] = None
    reason: str = "missing"  # missing/ambiguous/conflict


class SlotClarificationEngine:
    """配置化槽位追问引擎"""

    # 类级缓存
    _initialized = False
    _shared_slot_definitions: Dict[str, Dict] = {}
    _shared_slot_dependencies: Dict[str, List] = {}
    _shared_slot_relations: List[Dict] = {}

    def __init__(self, api_base: Optional[str] = None):
        self.api_base = api_base or get_go_api_base()
        self.metric_client = MetricClient(self.api_base)

        # 如果已经初始化过，直接使用类级缓存
        if SlotClarificationEngine._initialized:
            self.slot_definitions = SlotClarificationEngine._shared_slot_definitions
            self.slot_dependencies = SlotClarificationEngine._shared_slot_dependencies
            self.slot_relations = SlotClarificationEngine._shared_slot_relations
            self._slot_cache_time = time.time()
            logger.info("[SlotClarificationEngine] 使用已缓存的槽位配置")
            return

        self.slot_definitions: Dict[str, Dict] = {}
        self.slot_dependencies: Dict[str, List] = {}
        self.slot_relations: List[Dict] = {}
        self._slot_cache_time: float = 0
        self._slot_cache_ttl: float = 300  # 5分钟缓存

        # 维度名称 embedding 缓存（用于余弦相似度匹配）
        self._dimension_names: List[str] = []
        self._dimension_name_embeddings: List[List[float]] = []

        self._load_config()
        self._load_dimension_name_embeddings()
        self._initialized = True
        SlotClarificationEngine._shared_slot_definitions = self.slot_definitions
        SlotClarificationEngine._shared_slot_dependencies = self.slot_dependencies
        SlotClarificationEngine._shared_slot_relations = self.slot_relations
        logger.info("[SlotClarificationEngine] 首次初始化完成")

    def _load_config(self):
        """从 API 加载槽位配置"""
        try:
            client = get_http_client()

            # 加载槽位定义
            response = client.get(f"{self.api_base}/api/v1/nlp/slot-configs")
            data = response.json()

            if data.get("code") == 0:
                payload = data.get("data", {})
                slots = payload.get("slot_definitions", [])

                for slot in slots:
                    slot_name = slot.get("slot_name")
                    if slot_name:
                        self.slot_definitions[slot_name] = slot

                logger.info(f"[SlotClarificationEngine] 加载了 {len(self.slot_definitions)} 个槽位定义")
            else:
                logger.warning(f"[SlotClarificationEngine] 加载槽位定义失败: {data}")
                self._load_fallback_config()

            # 加载槽位依赖
            try:
                dep_response = client.get(f"{self.api_base}/api/v1/nlp/slot-dependencies")
                dep_data = dep_response.json()
                if dep_data.get("code") == 0:
                    deps = dep_data.get("data", [])
                    for dep in deps:
                        parent = dep.get("parent_slot")
                        if parent:
                            if parent not in self.slot_dependencies:
                                self.slot_dependencies[parent] = []
                            self.slot_dependencies[parent].append(dep)
                    logger.info(f"[SlotClarificationEngine] 加载了 {len(deps)} 条槽位依赖")
            except Exception as e:
                logger.warning(f"[SlotClarificationEngine] 加载槽位依赖异常: {e}")

            # 加载槽位关联
            try:
                rel_response = client.get(f"{self.api_base}/api/v1/nlp/slot-relations")
                rel_data = rel_response.json()
                if rel_data.get("code") == 0:
                    self.slot_relations = rel_data.get("data", [])
                    logger.info(f"[SlotClarificationEngine] 加载了 {len(self.slot_relations)} 条槽位关联")
            except Exception as e:
                logger.warning(f"[SlotClarificationEngine] 加载槽位关联异常: {e}")

        except Exception as e:
            logger.warning(f"[SlotClarificationEngine] 加载槽位配置异常: {e}")
            # 使用硬编码的兜底配置
            self._load_fallback_config()

    def _load_fallback_config(self):
        """加载兜底配置（当 API 不可用时）"""
        logger.info("[SlotClarificationEngine] 使用兜底配置")
        self.slot_definitions = {
            "time_range": {
                "slot_name": "time_range",
                "display_name": "时间范围",
                "slot_type": "required",
                "priority": 90,
                "value_type": "static",
                "allowed_values": json.dumps(["昨天", "近7天", "近30天", "本月", "上月", "去年同期"]),
                "question_templates": json.dumps(["请问想查询哪个时间段？"])
            },
            "metric": {
                "slot_name": "metric",
                "display_name": "指标",
                "slot_type": "required",
                "priority": 100,
                "value_type": "dynamic",
                "dynamic_source": "metric_category",
                "question_templates": json.dumps(["请问想查询哪个指标？"])
            },
            "platform": {
                "slot_name": "platform",
                "display_name": "平台",
                "slot_type": "required",
                "priority": 80,
                "value_type": "dynamic",
                "dynamic_source": "dimension_config",
                "dimension_name": "平台",
                "question_templates": json.dumps(["请问想查询哪个平台？", "是亚马逊、TikTok还是Temu呢？"])
            },
            "site": {
                "slot_name": "site",
                "display_name": "站点",
                "slot_type": "conditional",
                "priority": 70,
                "value_type": "dynamic",
                "dynamic_source": "dimension_config",
                "dimension_name": "站点",
                "question_templates": json.dumps(["请问想查询哪个站点？"])
            },
            "entity": {
                "slot_name": "entity",
                "display_name": "主体维度",
                "slot_type": "required",
                "priority": 60,
                "value_type": "dynamic",
                "dynamic_source": "dimension_config",
                "dimension_name": "品类",
                "question_templates": json.dumps(["请问想查询哪个维度？"])
            },
            "ad_type": {
                "slot_name": "ad_type",
                "display_name": "广告类型",
                "slot_type": "optional",
                "priority": 50,
                "value_type": "static",
                "allowed_values": json.dumps(["SP", "SC", "SB", "SD"]),
                "question_templates": json.dumps(["请问想查询哪种广告类型？"])
            },
            "logistics": {
                "slot_name": "logistics",
                "display_name": "物流方式",
                "slot_type": "optional",
                "priority": 40,
                "value_type": "static",
                "allowed_values": json.dumps(["FBA", "FBM", "海外仓"]),
                "question_templates": json.dumps(["请问想查询哪种物流？"])
            },
            "caliber": {
                "slot_name": "caliber",
                "display_name": "数据口径",
                "slot_type": "optional",
                "priority": 30,
                "value_type": "static",
                "allowed_values": json.dumps(["含广告费", "不含广告费", "毛利润", "净利润"]),
                "question_templates": json.dumps(["请问用哪种口径？"])
            },
        }

    def _load_allowed_values(self, slot_def: Dict[str, Any], slot_value: str = None) -> List[str]:
        """加载槽位可选值（支持静态和动态两种模式）"""
        slot_name = slot_def.get("slot_name", "")
        value_type = slot_def.get("value_type", "static")

        # entity 槽位特殊处理：用余弦相似度搜索 dimension_configs 中相似的 dimension_name
        if slot_name == "entity" and value_type == "dynamic" and slot_value:
            return self._search_dimension_names_by_embedding(slot_value)

        if value_type == "static":
            allowed_values = slot_def.get("allowed_values", "[]")
            if isinstance(allowed_values, str):
                return json.loads(allowed_values)
            return allowed_values or []

        if value_type == "dynamic":
            dynamic_source = slot_def.get("dynamic_source", "")
            if dynamic_source == "dimension_config":
                return self._load_from_dimension_config(slot_def)
            elif dynamic_source == "metric_category":
                return self._load_from_metric_category()

        return []

    def _search_dimension_names_by_embedding(self, user_input: str) -> List[str]:
        """用余弦相似度搜索与 user_input 相似的 dimension_name

        只返回与 user_input 真正相关的维度，过滤掉不相关的（如时间维度等）
        """
        if not user_input or not self._dimension_names or not self._dimension_name_embeddings:
            return ["一级品类", "二级品类", "三级品类"]

        try:
            from ai.engine.embedding_client import alibaba_embedding_client
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            # 生成用户输入的 embedding
            user_emb = alibaba_embedding_client.embed_single(user_input)
            if not user_emb:
                return ["一级品类", "二级品类", "三级品类"]

            user_vec = np.array(user_emb).reshape(1, -1)

            # 计算与所有 dimension_name 的相似度
            results = []
            for i, dim_emb in enumerate(self._dimension_name_embeddings):
                dim_vec = np.array(dim_emb).reshape(1, -1)
                sim = cosine_similarity(user_vec, dim_vec)[0][0]
                results.append({
                    "dimension_name": self._dimension_names[i],
                    "similarity": float(sim)
                })

            # 按相似度降序排序
            results.sort(key=lambda x: x["similarity"], reverse=True)

            # 【关键】根据用户输入过滤结果
            # 如果用户说的是"品类"相关的泛指词，只返回品类级别的维度
            GENERIC_CATEGORY_WORDS = {"品类", "类目", "商品类", "产品类", "商品", "产品", "分类"}
            CATEGORY_KEYWORDS = ["品类", "等级", "级别", "分类"]

            if user_input in GENERIC_CATEGORY_WORDS:
                # 用户输入是泛指品类词，只返回包含品类关键词的 dimension_name
                filtered = []
                for r in results:
                    name = r["dimension_name"]
                    # 只保留包含品类关键词的维度
                    if any(kw in name for kw in CATEGORY_KEYWORDS):
                        filtered.append(name)
                    # 也保留常见的品类级别维度（即使没有关键词）
                    elif name in {"一级品类", "二级品类", "三级品类", "四级品类", "产品等级", "产品等级"}:
                        filtered.append(name)
                matched = filtered
            else:
                # 非泛指词，返回所有相似度高的
                matched = [r["dimension_name"] for r in results if r["similarity"] > 0.5]

            logger.info(f"[_search_dimension_names_by_embedding] user_input={user_input}, matched={matched}")
            return matched if matched else ["一级品类", "二级品类", "三级品类"]

        except Exception as e:
            logger.warning(f"[_search_dimension_names_by_embedding] 搜索失败: {e}")
            return ["一级品类", "二级品类", "三级品类"]

    def _load_from_dimension_config(self, slot_def: Dict[str, Any]) -> List[str]:
        """从 StarRocks ids.dim_value_mapping 表获取维度值（按需查询）"""
        # 硬编码的兜底值（当 StarRocks 无数据时使用）
        fallback_values = {
            "PLATFORM": ["亚马逊", "TikTok Shop", "Temu", "Shopee", "eBay"],
            "SITE": ["美国", "英国", "德国", "日本", "东南亚"],
            "GROUP_1": ["数码电子", "服装鞋帽", "家居用品", "美妆护肤", "母婴用品"],
            "GROUP_2": ["手机配件", "电脑配件", "户外运动", "礼品箱包"],
            "GROUP_3": ["蓝牙耳机", "移动电源", "智能手表"],
        }

        try:
            # 获取槽位配置的 column_name 作为 dimension_field
            column_name = slot_def.get("column_name", "")
            if not column_name:
                logger.warning(f"[SlotClarificationEngine] column_name 为空，无法查询维度值")
                return fallback_values.get("PLATFORM", [])

            # 调用 Go API 从 StarRocks 查询维度值
            # 使用空的 query 获取该 dimension_field 下所有值
            client = get_http_client()
            url = f"{self.api_base}/api/v1/dimension-values/search"
            params = {"dimension_field": column_name, "query": "", "limit": 50}

            response = client.get(url, params=params)
            if response.status_code != 200:
                logger.warning(f"[SlotClarificationEngine] 查询维度值失败: HTTP {response.status_code}")
                return fallback_values.get(column_name, [])

            data = response.json()
            if data.get("code") != 0:
                logger.warning(f"[SlotClarificationEngine] 查询维度值失败: {data.get('message')}")
                return fallback_values.get(column_name, [])

            # 提取 dimension_value
            values = []
            for item in data.get("data", []):
                dv = item.get("dimension_value")
                if dv:
                    values.append(dv)

            # 如果 StarRocks 返回空，使用兜底值
            if not values:
                fallback = fallback_values.get(column_name, [])
                logger.info(f"[SlotClarificationEngine] StarRocks 无数据，使用兜底值: {column_name} -> {len(fallback)} 个")
                return fallback

            logger.info(f"[SlotClarificationEngine] 从 StarRocks 加载维度值: {column_name} -> {len(values)} 个")
            return values

        except Exception as e:
            logger.warning(f"[SlotClarificationEngine] 加载维度配置异常: {e}")
            return fallback_values.get(column_name, [])

    def _load_from_metric_category(self) -> List[str]:
        """从 metrics 表获取指标分类"""
        try:
            metrics = self.metric_client.get_all_metrics()
            categories = set()
            for m in metrics:
                # 按 category_1 分类
                cat = m.get("category_1") or m.get("category_2") or m.get("category_3")
                if cat:
                    categories.add(cat)
            return sorted(categories)
        except Exception as e:
            logger.warning(f"[SlotClarificationEngine] 加载指标分类失败: {e}")
            return []

    def _load_dimension_name_embeddings(self):
        """从 dimension_configs 加载 dimension_name 的 embedding 用于余弦相似度匹配"""
        try:
            dim_configs = self.metric_client.get_dimension_configs()
            self._dimension_names = [cfg.get("dimension_name", "") for cfg in dim_configs if cfg.get("dimension_name")]
            # 【新增】加载 column_name 到 dimension_name 的映射（用于匹配 GROUP_3 -> 三级品类）
            self._column_to_dimension_name = {}
            for cfg in dim_configs:
                col = cfg.get("column_name", "")
                name = cfg.get("dimension_name", "")
                if col and name:
                    self._column_to_dimension_name[col] = name
            if not self._dimension_names:
                logger.warning("[SlotClarificationEngine] dimension_configs 中没有 dimension_name")
                return

            # 使用阿里 embedding 生成向量
            from ai.engine.embedding_client import alibaba_embedding_client
            self._dimension_name_embeddings = []
            for name in self._dimension_names:
                emb = alibaba_embedding_client.embed_single(name)
                if emb:
                    self._dimension_name_embeddings.append(emb)
                else:
                    # 如果 embedding 失败，用零向量占位
                    self._dimension_name_embeddings.append([0.0] * 1536)
            logger.info(f"[SlotClarificationEngine] 加载了 {len(self._dimension_names)} 个 dimension_name embeddings")
            logger.info(f"[SlotClarificationEngine] column_to_dimension_name 映射: {self._column_to_dimension_name}")
        except Exception as e:
            logger.warning(f"[SlotClarificationEngine] 加载 dimension_name embeddings 失败: {e}")
            self._dimension_names = []
            self._dimension_name_embeddings = []
            self._column_to_dimension_name = {}

    def _match_dimension_name(self, user_input: str) -> bool:
        """精确匹配用户输入的维度是否在 dimension_configs 的 dimension_name 中

        Returns:
            True 表示精确匹配上了（不需要追问）
            False 表示匹配不上（需要追问）
        """
        if not user_input:
            return True  # 无法判断时默认不追问

        # 【关键修复】同时支持 dimension_name 和 column_name 的匹配
        # 1. 先检查是否直接匹配 dimension_name（如"三级品类"）
        if self._dimension_names and user_input in self._dimension_names:
            logger.info(f"[_match_dimension_name] user_input={user_input} 匹配 dimension_name")
            return True

        # 2. 再检查是否匹配 column_name（如"GROUP_3"）
        column_to_dim = getattr(self, '_column_to_dimension_name', {})
        if user_input in column_to_dim:
            logger.info(f"[_match_dimension_name] user_input={user_input} 匹配 column_name（对应 dimension_name={column_to_dim[user_input]}）")
            return True

        logger.info(f"[_match_dimension_name] user_input={user_input}, matched=False")
        return False

    def check_required_slots(
        self,
        state: "ConversationState",
        intent: str = None
    ) -> List[SlotClarification]:
        """检查必选槽位是否缺失或值无效，返回需要追问的槽位列表"""
        clarifications = []

        # 获取当前意图需要的槽位
        required_slots = self._get_required_slots(intent)
        logger.info(f"[check_required_slots] intent={intent}, required_slots={required_slots}")

        for slot_name in required_slots:
            slot_def = self.slot_definitions.get(slot_name)
            if not slot_def:
                continue

            # 先获取槽位值
            slot_value = self._get_slot_value(state, slot_name)

            # 懒加载 allowed_values（传入 slot_value 用于 entity 槽位的余弦相似度搜索）
            allowed_values = self._load_allowed_values(slot_def, slot_value)

            # 【调试】打印所有槽位值
            logger.info(f"[check_required_slots] slot={slot_name}, value={slot_value}, allowed={allowed_values}")
            if slot_name == "time_range":
                entities_debug = getattr(state, "entities", {}) or {}
                logger.debug(f"[check_required_slots] DEBUG time_range: entities={entities_debug}")

            # 【修改】值有效性校验：对于 entity 槽位，用余弦相似度判断是否匹配 dimension_configs
            # 对于其他槽位，检查是否在 allowed_values 中
            is_invalid_value = False
            if slot_name == "metric":
                # metric 槽位：allowed_values 是指标分类，不是具体指标，所以不校验
                is_invalid_value = False
            elif slot_name == "entity" and slot_value:
                # entity 槽位：精确匹配检查是否在 dimension_configs 中
                is_invalid_value = not self._match_dimension_name(slot_value)
                logger.info(f"[check_required_slots] entity 槽位精确匹配: value={slot_value}, is_invalid={is_invalid_value}")
            elif slot_value and allowed_values:
                # time_range 槽位特殊处理：使用原始时间表达式比较（因为 slot_value 是标准化后的 key 如 last_month，但 allowed_values 是中文显示名如"上月"）
                if slot_name == "time_range":
                    entities = getattr(state, "entities", {}) or {}
                    time_info = entities.get("time_info", {}) or {}
                    original_time = time_info.get("original") or entities.get("raw_time") or slot_value
                    is_invalid_value = original_time not in allowed_values
                    logger.info(f"[check_required_slots] time_range 特殊处理: slot_value={slot_value}, original_time={original_time}, allowed={allowed_values}, is_invalid={is_invalid_value}")
                else:
                    is_invalid_value = slot_value not in allowed_values
            logger.info(f"[check_required_slots] slot={slot_name}, is_invalid={is_invalid_value}")

            if not slot_value or is_invalid_value:
                # 【调试】打印关键值
                logger.debug(f"[check_required_slots] DEBUG: slot_name={slot_name}, intent={intent}, slot_value={slot_value}, is_invalid={is_invalid_value}")
                # 【关键修复】对于 query_ranking 意图 + entity 维度是品类级别的情况，
                # 跳过 metric 追问，让 sql_gen_node 的回退逻辑（搜索"销量"指标）处理
                if slot_name == "metric" and intent == "query_ranking":
                    entity_dim = self._get_slot_value(state, "entity")
                    logger.debug(f"[check_required_slots] DEBUG: metric检查, entity_dim={entity_dim}")
                    # 检测是否是品类级别维度（一级品类/二级品类/三级品类/四级品类）
                    category_level_keywords = ["品类", "类目"]
                    is_category_level = entity_dim and any(kw in entity_dim for kw in category_level_keywords)
                    logger.debug(f"[check_required_slots] DEBUG: is_category_level={is_category_level}")
                    if is_category_level:
                        logger.info(f"[check_required_slots] query_ranking + 品类级别维度，跳过 metric 追问: entity_dim={entity_dim}")
                        continue

                question = self._get_question(slot_def)

                clar = SlotClarification(
                    slot_name=slot_name,
                    display_name=slot_def.get("display_name", slot_name),
                    question=question,
                    priority=slot_def.get("priority", 0),
                    slot_type=slot_def.get("slot_type", "optional"),
                    allowed_values=allowed_values,
                    default_value=slot_def.get("default_value"),
                )
                clarifications.append(clar)
                logger.info(f"[check_required_slots] 追加追问: slot={slot_name}, question={question}")

        # 按优先级降序排序，但 entity 槽位匹配不上 dimension_configs 时优先追问
        def sort_key(x: SlotClarification) -> int:
            slot_val = self._get_slot_value(state, x.slot_name)
            # entity 槽位匹配不上 dimension_configs 时，置顶（priority + 1000 确保排最前）
            if x.slot_name == "entity" and slot_val:
                # 精确匹配判断是否匹配不上
                matched = self._match_dimension_name(slot_val)
                if not matched:
                    boosted = x.priority + 1000
                    logger.info(f"[check_required_slots] entity 槽位匹配不上，置顶: slot={x.slot_name}, value={slot_val}, boosted_priority={boosted}")
                    return boosted
            logger.info(f"[check_required_slots] 排序: slot={x.slot_name}, value={slot_val}, priority={x.priority}")
            return x.priority

        clarifications.sort(key=sort_key, reverse=True)
        return clarifications

    def _get_required_slots(self, intent: str = None) -> List[str]:
        """获取意图需要的槽位列表（只返回 required 类型的槽位）"""
        # 只返回 required 类型的槽位（排除 optional 槽位）
        required = []
        for name, slot in self.slot_definitions.items():
            if slot.get("slot_type") == "required":
                required.append(name)

        # 按 priority 降序排序（priority 大的在前）
        required.sort(key=lambda x: self.slot_definitions.get(x, {}).get("priority", 0), reverse=True)
        return required

    def _get_slot_value(self, state: "ConversationState", slot_name: str) -> Any:
        """从 state.entities 映射获取槽位值"""
        # slot_name -> entities 字段映射
        mapping = {
            "metric": ["metric_code", "metric_name"],
            "time_range": ["time_range", "time_info"],
            "platform": ["platform", "dim_platform"],
            "site": ["site", "dim_site"],
            "entity": ["dimension", "dimensions", "dim_field"],
            "ad_type": ["ad_type", "dim_ad_type"],
            "logistics": ["logistics"],
            "caliber": ["caliber"],
        }

        entities = getattr(state, "entities", {}) or {}
        # 【调试】打印 entities 中的 time 相关字段
        if slot_name == "time_range":
            logger.info(f"[_get_slot_value] time_range check: entities={entities}, time_range in entities: {'time_range' in entities}, time_info in entities: {'time_info' in entities}")

        for field_name in mapping.get(slot_name, []):
            value = entities.get(field_name)
            if value:
                return value

        return None

    def _get_question(self, slot_def: Dict[str, Any], turn: int = 0) -> str:
        """获取当前轮次的追问话术"""
        templates = slot_def.get("question_templates", "[]")
        if isinstance(templates, str):
            templates = json.loads(templates)

        if not templates:
            return f"请问选择{slot_def.get('display_name', '某个选项')}？"

        # 按轮次返回对应的话术
        if turn < len(templates):
            return templates[turn]
        return templates[-1]

    def get_slot_display_name(self, slot_name: str) -> str:
        """获取槽位显示名称"""
        slot_def = self.slot_definitions.get(slot_name, {})
        return slot_def.get("display_name", slot_name)
