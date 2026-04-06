"""
Prompt 配置管理器 - 从数据库加载 Prompt 配置
"""
import httpx
from typing import Dict, Any, Optional
from ai.config.logging_config import get_logger

logger = get_logger("ai.prompt_manager")


class PromptManager:
    """Prompt 配置管理器"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_version: Dict[str, int] = {}

    def get_prompt_config(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定名称的 Prompt 配置

        Args:
            name: Prompt 配置名称，如 "nl2structure"

        Returns:
            Prompt 配置字典，包含 prompt_text, variables 等
        """
        try:
            response = httpx.get(
                f"{self.base_url}/api/v1/prompt-configs/active",
                params={"name": name},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                config = data.get("data")
                if config:
                    self._cache[name] = config
                    self._cache_version[name] = config.get("version", 0)
                    logger.info(f"[PromptManager] 已加载 Prompt 配置: {name} v{config.get('version')}")
                    return config
                else:
                    logger.warning(f"[PromptManager] Prompt 配置不存在: {name}")
                    return None
            else:
                logger.warning(f"[PromptManager] 获取 Prompt 配置失败: {name}, status={response.status_code}")
                return self._cache.get(name)
        except Exception as e:
            logger.warning(f"[PromptManager] 获取 Prompt 配置异常: {name}, error={e}")
            return self._cache.get(name)

    def get_nl2structure_prompt(self) -> str:
        """
        获取 NL2Structure Prompt（用于意图识别、实体提取、时间解析）

        Returns:
            Prompt 文本
        """
        config = self.get_prompt_config("nl2structure")
        if config:
            return config.get("prompt_text", "")
        # 回退到默认 Prompt
        return self._get_default_nl2structure_prompt()

    def get_sql_generation_prompt(self) -> str:
        """
        获取 SQL 生成 Prompt

        Returns:
            Prompt 文本
        """
        config = self.get_prompt_config("sql_generation")
        if config:
            return config.get("prompt_text", "")
        return ""

    def get_nl2querystate_prompt(self) -> str:
        """
        获取 NL2QueryState Prompt（用于 LLM 生成 QueryState JSON）

        Returns:
            Prompt 文本
        """
        config = self.get_prompt_config("nl2querystate")
        if config:
            return config.get("prompt_text", "")
        # 回退到默认 Prompt
        return self._get_default_nl2querystate_prompt()

    @staticmethod
    def _get_default_nl2querystate_prompt() -> str:
        """
        获取默认的 NL2QueryState Prompt
        """
        return """【角色】
你是一个专业的业务指标查询助手，擅长将用户的自然语言问题转换为结构化的 QueryState JSON。

【任务】
分析用户问题，生成结构化的 QueryState JSON 描述。

【QueryState JSON Schema】
{
  "version": "1.0",
  "session_id": "会话ID",
  "parent_state_id": "父状态ID（用于多轮对话）",

  "intent": "查询意图",
  "confidence": 置信度(0-1),

  "metric": {
    "code": "指标编号，如 MKI-02-0011",
    "name": "指标名称，如 总销售额",
    "starrocks_table": "StarRocks 表名",
    "starrocks_sql": "预置 SQL 模板"
  },

  "time": {
    "type": "时间类型：date_range|relative|absolute_month|quarter",
    "start": "开始日期(YYYY-MM-DD)",
    "end": "结束日期(YYYY-MM-DD)",
    "original_expr": "用户原始时间表达，如 近15天"
  },

  "dimensions": [
    {"type": "维度类型", "column": "中文显示名", "field": "数据库列名", "value": "过滤值"}
  ],

  "metrics": [
    {"name": "指标代码", "display_name": "中文名", "aggregation": "聚合类型", "field": "字段名", "alias": "别名"}
  ],

  "filters": [],

  "comparison": {
    "enabled": true/false,
    "types": ["同比", "环比"]
  },

  "pagination": {"page": 1, "page_size": 100},

  "drill_down": {
    "add_dimensions": ["要添加的维度列名"],
    "original_group_by": ["原始 GROUP BY 列"]
  }
}

【intent 取值范围】
- query_value: 查询指标数值
- query_trend: 查询趋势变化
- query_comparison: 对比分析
- query_metadata: 查询元数据
- greeting: 打招呼
- thanks: 感谢
- bye: 告别
- unknown: 无法识别

【时间类型说明】
- date_range: 日期范围，如 2026-03-01 到 2026-03-15
- relative: 相对表达，如 近15天、最近7天
- absolute_month: 绝对月份，如 2026-03
- quarter: 季度，如 2026-Q1

【聚合类型】
- SUM: 求和
- AVG: 平均值
- COUNT: 计数
- MAX: 最大值
- MIN: 最小值

【维度类型参考】
- GROUP_1: 一级品类
- GROUP_2: 二级品类
- GROUP_3: 三级品类
- SKU: 商品SKU
- FDATE: 日期
- MONTHS: 月份
- REGION: 地区
- PLATFORM: 平台

【对比周期】
- 同比: 去年同月/同周
- 环比: 上月/上周

【示例】

输入: "最近15天销售额最高的SKU是啥，还有同比环比是多少"
输出:
{
  "version": "1.0",
  "session_id": "",
  "intent": "query_value",
  "confidence": 0.95,
  "metric": {
    "code": "MKI-02-0009",
    "name": "总销售额",
    "starrocks_table": "dws.DWS_IMC_BUSINESSREPORT",
    "starrocks_sql": "SELECT SUM(ORDERED_PRODUCTSALES) AS ORDERED_PRODUCTSALES FROM dws.DWS_IMC_BUSINESSREPORT WHERE 1=1"
  },
  "time": {
    "type": "date_range",
    "start": "2026-03-21",
    "end": "2026-04-05",
    "original_expr": "近15天"
  },
  "dimensions": [
    {"type": "SKU", "column": "SKU", "field": "SKU", "value": null}
  ],
  "metrics": [
    {"name": "sales", "display_name": "总销售额", "aggregation": "SUM", "field": "ORDERED_PRODUCTSALES", "alias": "ORDERED_PRODUCTSALES"}
  ],
  "filters": [],
  "comparison": {
    "enabled": true,
    "types": ["同比", "环比"]
  },
  "pagination": {"page": 1, "page_size": 10},
  "drill_down": null
}

输入: "按一级品类汇总销售额"
输出:
{
  "version": "1.0",
  "session_id": "",
  "intent": "query_value",
  "confidence": 0.9,
  "metric": {
    "code": "MKI-02-0009",
    "name": "总销售额",
    "starrocks_table": "dws.DWS_IMC_BUSINESSREPORT",
    "starrocks_sql": "SELECT GROUP_1, SUM(ORDERED_PRODUCTSALES) AS 总销售额 FROM dws.DWS_IMC_BUSINESSREPORT GROUP BY GROUP_1"
  },
  "time": {
    "type": "date_range",
    "start": "2026-03-21",
    "end": "2026-04-05",
    "original_expr": "近15天"
  },
  "dimensions": [
    {"type": "GROUP_1", "column": "一级品类", "field": "GROUP_1", "value": null}
  ],
  "metrics": [
    {"name": "sales", "display_name": "总销售额", "aggregation": "SUM", "field": "ORDERED_PRODUCTSALES", "alias": "总销售额"}
  ],
  "filters": [],
  "comparison": {"enabled": false, "types": []},
  "pagination": {"page": 1, "page_size": 100},
  "drill_down": null
}

【约束条件】
1. 必须输出合法 JSON
2. 只输出 JSON，不要有其他内容
3. confidence 低于 0.5 时，intent 使用 "unknown"
4. 如果无法确定指标 code/name，使用空字符串
5. starrocks_sql 可以为空字符串，后续由系统补充
"""

    def reload_config(self, name: str = None):
        """
        重新加载配置

        Args:
            name: 指定要重新加载的配置名称，None 表示全部
        """
        if name:
            self._cache.pop(name, None)
            self._cache_version.pop(name, None)
            self.get_prompt_config(name)
        else:
            self._cache.clear()
            self._cache_version.clear()
            logger.info("[PromptManager] 已清空 Prompt 缓存")

    @staticmethod
    def _get_default_nl2structure_prompt() -> str:
        """
        获取默认的 NL2Structure Prompt（当数据库没有配置时使用）
        """
        return """【角色】
你是一个专业的业务指标查询助手，擅长从用户的自然语言中准确提取结构化信息。

【任务】
分析用户问题，提取以下结构化字段：

【输出格式 - 必须严格遵守】
{
  "intent": "查询意图",
  "confidence": 置信度(0-1),
  "metric_name": "指标名称",
  "time_range": {
    "type": "时间类型|absolute_month|date_range|relative|quarter",
    "start": "开始日期(YYYY-MM-DD)",
    "end": "结束日期(YYYY-MM-DD)",
    "original": "用户原始表达"
  },
  "dimension": "维度粒度（如按日、按月）",
  "dimension_values": "具体维度值（如GROUP_3=有线网卡，GROUP_2=配件）",
  "comparison_period": "对比周期（可选）"
}

【intent 取值范围 - 必须严格匹配】
- query_value: 查询指标数值
- query_trend: 查询趋势变化
- query_comparison: 对比分析
- query_metadata: 查询元数据
- query_yesterday: 查询昨天数据
- query_today: 查询今天数据
- query_this_week: 查询本周数据
- query_this_month: 查询本月数据
- greeting: 打招呼
- thanks: 感谢
- bye: 告别
- action_intent_ambiguous: 操作意图模糊
- unknown: 无法识别

【系统指标知识】
1. 指标格式：页面访问量、访客数、广告转化率、订单量、销售额
2. 指标编号：MKI-02-0001（格式：MKI-领域-序号）
3. 指标域：营销域、服务域、用户域
4. 常见单位：个、次、%、转化率、点击率

5. 维度值识别：用户输入中可能包含具体的维度值，如"有线网卡"、"笔记本支架"、"无线网卡"等，这些是GROUP_3品类的具体取值
   - 常见品类维度：GROUP_1（一级品类）、GROUP_2（二级品类）、GROUP_3（三级品类）
   - 其他维度：SKU、ASIN、REGION（地区）、PLATFORM（平台）等
   - 当用户提到具体产品名/品牌名/地区名时，很可能是维度值

6. 跨境电商特定场景：
   - 流量：独立站访问量、页面PV、加购率
   - 转化：广告转化率、下单率、支付成功率、弃单率
   - 广告：ROAS、CPC、CPM、CTR、广告消耗
   - 物流：发货时效、妥投率、退货率
   - 客户：新客数、老客复购率、客单价、LTV
   - 品类：爆款商品、滞销品、库存周转率
   - 地区分析：按国家/地区维度（如"美国"、"欧洲"）

7. 供应链业务场景：
   - 采购分析：采购额、采购量、供应商交付及时率、来料合格率
   - 库存管理：库存周转天数、库存周转率、呆滞库存、库存预警
   - 生产制造：产能利用率、生产计划达成率、良品率、次品率
   - 物流配送：配送时效、到货准时率、平均配送成本、破损率
   - 供应商管理：供应商数量、优质供应商占比、供应商准时交货率

8. 人力资源业务场景：
   - 招聘分析：招聘周期、招聘完成率、简历筛选通过率、offer接受率
   - 在职分析：员工总数、编制完成率、人员流失率、留存率
   - 考勤分析：出勤率、请假人次、加班时长、旷工率
   - 绩效分析：绩效评分分布、绩效达标率、人效指标
   - 薪酬分析：人均工资、人工成本占比、薪酬增长率
   - 培训分析：培训时长、培训覆盖率、培训完成率

【intent 取值范围】
- query_value: 查询指标数值
- query_trend: 查询趋势变化
- query_comparison: 对比分析
- query_metadata: 查询元数据（业务口径、技术口径）
- query_yesterday: 查询昨天数据
- query_today: 查询今天数据
- query_this_week: 查询本周数据
- query_this_month: 查询本月数据
- greeting: 打招呼
- thanks: 感谢
- bye: 告别
- unknown: 无法识别

【时间表达识别规则】
1. 固定时间词：昨天、今天、明天、本周、本月、上周、上月、去年、本年
2. 动态时间：最近N天/周/月/年、过去N天/周/月/年、近N天
3. 绝对时间：月份、季度、日期范围
4. 半年表达：上半年、下半年、上半年(1-6月)、下半年(7-12月)
5. 季度表达：Q1、Q2、Q3、Q4、一季度、二季度、三季度、四季度
6. 周期表达：近半年、近一年、近30天、近7天

【指标识别】
- 如提到"业务口径"、"技术口径"，intent应为 query_metadata

【追问处理 - 重要】
当用户说"环比呢"、"同比呢"、"趋势呢"等简短的追问时：
1. 如果上下文中有上轮查询的指标，intent应继承上轮的意图
2. time_range应理解为"当前/本期"，而不是上轮的时间
3. 例如：上轮问"上月销量同比"，本轮问"环比呢" → time_range应为"本月"
4. 这种追问不需要用户重复说明指标名，系统应自动继承上轮指标

【约束条件】
1. 必须输出合法JSON
2. time_range的start和end在没有具体日期时使用null
3. confidence低于0.5时，intent使用"unknown"

请只输出JSON，不要有其他内容。"""


# 全局单例
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """获取 PromptManager 单例"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


def reload_prompt_manager(name: str = None):
    """重新加载 Prompt 配置"""
    manager = get_prompt_manager()
    manager.reload_config(name)
