# Phase 0 PoC 测试用例集
# 来源：从 ask_analysis_logs 表提取的高频查询 + 手工设计边界场景

# ===================== 从日志提取的高频查询 =====================
# 按意图分组，选取各类型Top查询

HIGH_FREQ_CASES = [
    # query_value - 问指标值（最多）
    {"query": "本月销售额是多少？", "expected_intent": "query_value", "source": "log"},
    {"query": "本月销售额多少", "expected_intent": "query_value", "source": "log"},
    {"query": "本月销售额", "expected_intent": "query_value", "source": "log"},
    {"query": "销售额如何", "expected_intent": "query_value", "source": "log"},
    {"query": "销售额怎么样", "expected_intent": "query_value", "source": "log"},
    {"query": "智能云存储毛利率", "expected_intent": "query_value", "source": "log"},
    {"query": "智能云存储销售额", "expected_intent": "query_value", "source": "log"},
    {"query": "上月智能云存储毛利率", "expected_intent": "query_value", "source": "log"},
    {"query": "本月一级品类销售额是多少？", "expected_intent": "query_value", "source": "log"},
    {"query": "本月三级品类销售额是多少？", "expected_intent": "query_value", "source": "log"},
    {"query": "本月各品类销售额是多少？", "expected_intent": "query_value", "source": "log", "note": "可能被识别为drilldown"},
    {"query": "当月美国站业绩", "expected_intent": "query_value", "source": "log"},
    {"query": "今年德国亚马逊业绩", "expected_intent": "query_value", "source": "log"},
    {"query": "今日GMV", "expected_intent": "query_value", "source": "log"},
    {"query": "今年我们一共被亚马逊抽水抽走了多少钱？", "expected_intent": "query_value", "source": "log"},
    {"query": "上上个月这个10494卖了多少钱，并且告诉我数量", "expected_intent": "query_value", "source": "log"},
    {"query": "本月充电器的销售毛利和销售毛利率分别是多少？", "expected_intent": "query_value", "source": "log"},
    {"query": "各站点健康度怎么样？", "expected_intent": "query_value", "source": "log"},
    {"query": "智能云3月业绩", "expected_intent": "query_value", "source": "log"},

    # query_trend - 问趋势
    {"query": "查看近7天访客数趋势", "expected_intent": "query_trend", "source": "log"},
    {"query": "本月销售毛利趋势变化", "expected_intent": "query_trend", "source": "log"},
    {"query": "今年智能云存储销售额变化趋势", "expected_intent": "query_trend", "source": "log"},
    {"query": "今年一季度广告花费整体变化趋势", "expected_intent": "query_trend", "source": "log"},
    {"query": "2026年销售额变化趋势", "expected_intent": "query_trend", "source": "log"},
    {"query": "查看本月销售毛利趋势变化", "expected_intent": "query_trend", "source": "log"},
    {"query": "帮我看看最近一周亚马逊店铺的总访问人次趋势。", "expected_intent": "query_trend", "source": "log"},

    # query_comparison - 问对比
    {"query": "本月销售额和上月对比", "expected_intent": "query_comparison", "source": "log"},
    {"query": "为啥3月比2月高", "expected_intent": "query_comparison", "source": "log", "note": "因果分析，实际是comparison"},
    {"query": "3月销售额环比2月", "expected_intent": "query_comparison", "source": "log"},
    {"query": "本月销售额同比去年变化", "expected_intent": "query_comparison", "source": "log"},
    {"query": "本月销售额环比", "expected_intent": "query_comparison", "source": "log"},
    {"query": "查看各站点销售额同比变化", "expected_intent": "query_comparison", "source": "log"},
    {"query": "智能云存储今年业绩多少，同比环比呢", "expected_intent": "query_comparison", "source": "log"},

    # query_ranking - 问排名
    {"query": "请展示上季度亚马逊平台销售额排名前三的站点，并列出对应的销售额及销量。", "expected_intent": "query_ranking", "source": "log"},
    {"query": "查看销售额排名前10", "expected_intent": "query_ranking", "source": "log"},
    {"query": "今年第一季度哪个月的自然订单量最少，是多少？", "expected_intent": "query_ranking", "source": "log"},

    # drilldown - 下钻（通过__DRILLDOWN__触发）
    {"query": "__DRILLDOWN__:sales__", "expected_intent": "drilldown", "source": "log"},
    {"query": "__DRILLDOWN__:ad__", "expected_intent": "drilldown", "source": "log"},

    # greeting - 打招呼
    {"query": "今天怎么样", "expected_intent": "greeting", "source": "log"},

    # unknown - 无法识别
    {"query": "广告效果分析", "expected_intent": "unknown", "source": "log"},
]

# ===================== 手工设计边界场景 =====================
# 覆盖快照可能覆盖不了的复杂场景

EDGE_CASES = [
    # 复杂时间表达式
    {"query": "上周一到周五的访客数", "expected_intent": "query_value", "source": "manual", "note": "复杂时间范围"},
    {"query": "上个月最后一周的销售额", "expected_intent": "query_value", "source": "manual", "note": "模糊时间"},
    {"query": "最近三个月趋势", "expected_intent": "query_trend", "source": "manual", "note": "近N天/月"},

    # 模糊表述
    {"query": "销售额好像不太对", "expected_intent": "query_value", "source": "manual", "note": "模糊表述"},
    {"query": "有没有什么异常", "expected_intent": "volatility", "source": "manual", "note": "异常检测"},
    {"query": "最近有没有什么问题", "expected_intent": "volatility", "source": "manual", "note": "问题发现"},

    # 多指标组合
    {"query": "同时查看销售额和成本", "expected_intent": "query_value", "source": "manual", "note": "多指标"},
    {"query": "销售额和转化率对比", "expected_intent": "query_comparison", "source": "manual", "note": "多指标对比"},

    # 口语化表达
    {"query": "帮我查一下", "expected_intent": "unknown", "source": "manual", "note": "口语化"},
    {"query": "看看这个", "expected_intent": "unknown", "source": "manual", "note": "指代不明"},
    {"query": "和竞品对比一下", "expected_intent": "query_comparison", "source": "manual", "note": "外部对比"},

    # 因果分析
    {"query": "为什么这个月销售额下降了", "expected_intent": "analysis", "source": "manual", "note": "因果分析"},
    {"query": "是哪些原因导致转化率变低", "expected_intent": "analysis", "source": "manual", "note": "归因分析"},

    # 建议类
    {"query": "我应该怎么优化广告投放", "expected_intent": "recommendation", "source": "manual", "note": "优化建议"},
    {"query": "有什么可以改进的地方", "expected_intent": "recommendation", "source": "manual", "note": "改进建议"},
]

# ===================== 合并所有测试用例 =====================
ALL_TEST_CASES = HIGH_FREQ_CASES + EDGE_CASES

# 统计信息
INTENT_DISTRIBUTION = {}
for case in ALL_TEST_CASES:
    intent = case["expected_intent"]
    INTENT_DISTRIBUTION[intent] = INTENT_DISTRIBUTION.get(intent, 0) + 1

print(f"总测试用例数: {len(ALL_TEST_CASES)}")
print(f"意图分布: {INTENT_DISTRIBUTION}")
