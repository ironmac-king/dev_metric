"""
调用 Go 指标平台 API
"""
import httpx
from typing import List, Dict, Any, Optional
from ai.config.logging_config import get_logger

logger = get_logger("ai.metric_client")

# 全局 HTTP 客户端（连接池复用）
_http_client: Optional[httpx.Client] = None


def get_http_client() -> httpx.Client:
    """获取全局 HTTP 客户端（单例，连接池复用）"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
    return _http_client


class MetricClient:
    """指标平台 API 客户端"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self._metrics_cache = None  # 指标列表缓存
        self._dimensions_cache = None  # 维度列表缓存

    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """获取所有指标（带缓存）"""
        if self._metrics_cache is None:
            client = get_http_client()
            response = client.get(f"{self.base_url}/api/v1/metadata/metrics")
            response.raise_for_status()
            self._metrics_cache = response.json()["data"]
        return self._metrics_cache

    def get_metric(self, metric_id: int) -> Dict[str, Any]:
        """获取指标详情"""
        client = get_http_client()
        response = client.get(f"{self.base_url}/api/v1/metadata/metrics/{metric_id}")
        response.raise_for_status()
        return response.json()["data"]

    def get_metric_by_code(self, metric_code: str) -> Optional[Dict[str, Any]]:
        """根据 metric_code 获取指标详情"""
        try:
            # 先获取所有指标，再按 code 过滤
            all_metrics = self.get_all_metrics()
            for m in all_metrics:
                if m.get("metric_code") == metric_code:
                    # 获取关联的维度
                    metric_id = m.get("id")
                    if metric_id:
                        client = get_http_client()
                        response = client.get(
                            f"{self.base_url}/api/v1/metadata/metrics/{metric_id}",
                            timeout=5
                        )
                        if response.status_code == 200:
                            data = response.json().get("data", {})
                            m["dimensions"] = data.get("dimensions", [])
                    return m
            return None
        except Exception as e:
            logger.error(f"获取指标失败: {e}")
            return None

    def get_metric_by_name(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """根据 metric_name 获取指标详情（模糊匹配 + 同义词支持）

        修复：短查询词(<3字符)不使用模糊子串匹配，避免"pv"匹配到"costfeess_rate"等问题
        """
        # 同义词映射表（标准名称 -> 同义词列表）
        SYNONYMS = {
            # 广告相关
            "广告点击率": ["广告转化率", "ctr", "click_rate", "点击率", "广告点击"],
            "广告花费": ["广告成本", "广告支出", "ad_cost", "spend", "广告费用"],
            "广告点击": ["点击量", "clicks", "点击次数"],
            "广告转化率": ["ctr", "cvr", "conversion_rate", "转化率"],
            # 利润相关
            "毛利润": ["税前利润", "利润", "profit"],
            "毛利率": ["税前利润率", "利润率", "profit_margin", "margin", "利润占比"],
            "税前利润": ["毛利润", "利润", "profit"],
            "税前利润率": ["毛利率", "利润率", "profit_margin", "margin"],
            # 销售额相关
            "销售额": ["销售", "sales", "收入", "总销售额", "营收"],
            "订单量": ["订单数", "订单", "orders", "total_orders"],
            "客单价": ["平均订单价值", "aov", "average_order_value"],
            # 访客相关
            "访客数": ["访客", "visitors", "流量", "sessions"],
            "转化率": ["cvr", "conversion_rate"],
            # 页面访问相关
            "页面访问量": ["pv", "PV", "page views", "PageViews", "访问量", "页面pv"],
        }

        # 构建反向映射（从同义词到标准名称）
        SYNONYMS_REVERSE = {}
        for canonical, syns in SYNONYMS.items():
            for syn in syns:
                SYNONYMS_REVERSE[syn.lower()] = canonical

        try:
            all_metrics = self.get_all_metrics()
            metric_name_lower = metric_name.lower()

            # 1. 精确匹配（用户输入 vs 指标名）
            for m in all_metrics:
                name = m.get("name", "")
                name_en = m.get("name_en", "")
                if name.lower() == metric_name_lower or name_en.lower() == metric_name_lower:
                    return self._get_metric_with_details(m)

            # 2. 同义词精确匹配（用户输入 -> 同义词 -> 标准名称 -> 指标）
            # 使用反向映射：pv -> "页面访问量" -> 查找指标名="页面访问量"的指标
            if metric_name_lower in SYNONYMS_REVERSE:
                canonical_name = SYNONYMS_REVERSE[metric_name_lower]
                logger.info(f"[get_metric_by_name] 同义词匹配: '{metric_name}' -> '{canonical_name}'")
                for m in all_metrics:
                    name = m.get("name", "")
                    name_en = m.get("name_en", "")
                    if name == canonical_name or name_en.lower() == canonical_name.lower():
                        return self._get_metric_with_details(m)
                # 如果没找到精确匹配，也尝试模糊匹配标准名称
                for m in all_metrics:
                    name = m.get("name", "").lower()
                    name_en = m.get("name_en", "").lower()
                    if canonical_name.lower() in name or canonical_name.lower() in name_en:
                        return self._get_metric_with_details(m)

            # 3. 短查询词保护：< 3 字符不使用模糊子串匹配
            if len(metric_name_lower) < 3:
                logger.warning(f"[get_metric_by_name] 查询词过短 '{metric_name}'，跳过模糊子串匹配")
                # 仍尝试同义词模糊匹配
                for syn_key, syn_list in SYNONYMS.items():
                    if metric_name_lower in syn_key.lower():
                        for syn in syn_list:
                            syn_lower = syn.lower()
                            for m in all_metrics:
                                name = m.get("name", "").lower()
                                name_en = m.get("name_en", "").lower()
                                if name == syn_lower or name_en == syn_lower:
                                    return self._get_metric_with_details(m)
                return None

            # 4. 模糊匹配（带边界检查，确保是完整词匹配）
            best_match = None
            best_score = 0
            for m in all_metrics:
                name = m.get("name", "").lower()
                name_en = m.get("name_en", "").lower()

                score = 0
                # 完整词匹配（不是子串）
                if metric_name_lower == name_en or metric_name_lower == name:
                    score = 100
                # 同义词完整词匹配
                elif metric_name_lower in synonyms:
                    for syn in synonyms:
                        if syn.lower() == name or syn.lower() == name_en:
                            score = 90
                            break
                # name_en 以查询词结尾（更具体的指标）
                elif name_en.endswith(metric_name_lower):
                    score = 60
                # name 以查询词结尾
                elif name.endswith(metric_name_lower):
                    score = 50

                if score > best_score:
                    best_score = score
                    best_match = m

            if best_score >= 50:
                return self._get_metric_with_details(best_match)

            # 5. 同义词模糊匹配（用户输入 -> 同义词 -> 指标名 in 同义词）
            for syn in synonyms:
                syn_lower = syn.lower()
                for m in all_metrics:
                    name = m.get("name", "")
                    name_en = m.get("name_en", "")
                    if (syn_lower in name.lower()) or (syn_lower in name_en.lower()):
                        return self._get_metric_with_details(m)

            # 6. 反向同义词匹配（指标名在同义词列表中）
            for m in all_metrics:
                name = m.get("name", "")
                name_en = m.get("name_en", "")
                for key, syns in SYNONYMS.items():
                    if (name.lower() == key.lower() or name_en.lower() == key.lower()):
                        # 检查用户输入是否匹配任意同义词
                        if metric_name_lower in [s.lower() for s in syns]:
                            return self._get_metric_with_details(m)

            return None
        except Exception as e:
            logger.error(f"根据名称获取指标失败: {e}")
            return None

    def _get_metric_with_details(self, metric: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取指标的完整详情"""
        try:
            metric_id = metric.get("id")
            if metric_id:
                client = get_http_client()
                response = client.get(
                    f"{self.base_url}/api/v1/metadata/metrics/{metric_id}",
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json().get("data", {})
                    metric["dimensions"] = data.get("dimensions", [])
            return metric
        except Exception as e:
            logger.warning(f"获取指标详情失败: {e}")
            return metric

    def get_all_dimensions(self) -> List[Dict[str, Any]]:
        """获取所有维度（带缓存）"""
        if self._dimensions_cache is None:
            client = get_http_client()
            response = client.get(f"{self.base_url}/api/v1/metadata/dimensions")
            response.raise_for_status()
            self._dimensions_cache = response.json()["data"]
        return self._dimensions_cache

    def get_all_terms(self) -> List[Dict[str, Any]]:
        """获取所有业务术语（兼容旧方法）"""
        client = get_http_client()
        response = client.get(f"{self.base_url}/api/v1/metadata/terms")
        response.raise_for_status()
        return response.json()["data"]

    def get_business_terms(self) -> List[Dict[str, Any]]:
        """获取所有业务术语"""
        return self.get_all_terms()

    def get_metric_data(self, metric_id: int) -> Dict[str, Any]:
        """获取指标数据"""
        client = get_http_client()
        response = client.get(f"{self.base_url}/api/v1/metrics/{metric_id}/data")
        response.raise_for_status()
        return response.json()["data"]

    def get_dimension_configs(self, table_name: str = None) -> List[Dict[str, Any]]:
        """获取维度配置"""
        client = get_http_client()
        params = {}
        if table_name:
            params["table_name"] = table_name
        response = client.get(
            f"{self.base_url}/api/v1/dimension-configs",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("data", [])

    def get_dimension_type_mappings(self) -> List[Dict[str, Any]]:
        """获取全局维度类型→列名映射"""
        client = get_http_client()
        response = client.get(
            f"{self.base_url}/api/v1/dimension-type-mappings",
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("data", [])

    def get_formula_syntax_configs(self) -> List[Dict[str, Any]]:
        """获取所有启用的公式语法配置"""
        import json
        client = get_http_client()
        response = client.get(
            f"{self.base_url}/api/v1/nlp/formula-syntax/enabled",
            timeout=10
        )
        response.raise_for_status()
        # 显式使用 UTF-8 解码避免 Windows 编码问题
        return json.loads(response.content.decode('utf-8')).get("data", [])

    async def get_all_metrics_async(self) -> List[Dict[str, Any]]:
        """异步获取所有指标"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/v1/metadata/metrics")
            response.raise_for_status()
            return response.json()["data"]

    def search_metrics(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索指标 - 在名称、定义、口径中模糊匹配
        返回最相关的指标列表
        """
        try:
            metrics = self.get_all_metrics()
            query_lower = query.lower()
            scored = []

            for m in metrics:
                name = (m.get("name") or "").lower()
                name_en = (m.get("name_en") or "").lower()
                business_def = (m.get("business_definition") or "").lower()
                business_rule = (m.get("business_rule") or "").lower()
                tech_rule = (m.get("technical_rule") or "").lower()

                # 计算匹配分数
                score = 0

                # 1. 名称完全匹配（查询词完全等于指标名）
                if query_lower == name:
                    score += 100
                # 2. 名称包含查询词（关键词在名称中）
                elif query_lower in name:
                    score += 20

                # 英文名匹配
                if query_lower == name_en:
                    score += 50
                elif query_lower in name_en:
                    score += 10

                # 4. 定义/口径匹配（需要查询至少3个字符，且完整匹配才加分，避免"费"匹配到"费用"）
                if len(query_lower) >= 3:
                    if query_lower in business_def:
                        score += 5
                    if query_lower in business_rule:
                        score += 3
                    if query_lower in tech_rule:
                        score += 2

                # 5. 字符级模糊匹配（仅当查询长度>=2，且其他匹配分数<10时）
                if score < 10 and len(query_lower) >= 2:
                    query_chars = set(query_lower)
                    name_chars = set(name.replace(" ", ""))
                    if query_chars and name_chars:
                        intersection = query_chars & name_chars
                        # 要求查询中所有字符都出现在名称中
                        if intersection == query_chars:
                            score += 8
                        elif len(intersection) >= len(query_chars) * 0.8:
                            score += 4

                if score > 0:
                    scored.append((score, m))

            # 按分数排序，取前 limit 个
            scored.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in scored[:limit]]
        except Exception as e:
            logger.warning(f"搜索指标失败: {e}")
            return []

    def create_analysis_log(
        self,
        user_id: str,
        session_id: str,
        question: str,
        intent: str,
        success: bool,
        fail_stage: str = "",
        fail_reason: str = "",
        suggestion: str = "",
        thinking_steps: str = ""
    ) -> bool:
        """写入问数分析日志"""
        try:
            payload = {
                "user_id": user_id,
                "session_id": session_id,
                "question": question,
                "intent": intent,
                "success": success,
                "fail_stage": fail_stage,
                "fail_reason": fail_reason,
                "suggestion": suggestion,
                "thinking_steps": thinking_steps
            }
            client = get_http_client()
            response = client.post(
                f"{self.base_url}/api/v1/internal/ask-analysis/logs",
                json=payload,
                timeout=10
            )
            if response.status_code == 200:
                logger.info(f"分析日志写入成功: session_id={session_id}, success={success}")
                return True
            else:
                logger.warning(f"分析日志写入失败: status={response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"分析日志写入异常: {e}")
            return False
