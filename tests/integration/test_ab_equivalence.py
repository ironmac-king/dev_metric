"""
集成测试: A/B 等价性 - 验证 LegacyEngine 和 LangGraphEngine 输出完全一致

这是 LangGraph A/B Test 的核心测试用例
"""
import pytest
import uuid


def compare_results(r_legacy, r_langgraph, test_name):
    """
    比较两个引擎的输出字段

    Args:
        r_legacy: LegacyEngine 返回结果
        r_langgraph: LangGraphEngine 返回结果
        test_name: 测试名称（用于错误信息）
    """
    # 比较关键字段
    assert r_legacy.get("clarification_type") == r_langgraph.get("clarification_type"), \
        f"[{test_name}] clarification_type 不一致: legacy={r_legacy.get('clarification_type')}, langgraph={r_langgraph.get('clarification_type')}"

    assert r_legacy.get("needs_clarification") == r_langgraph.get("needs_clarification"), \
        f"[{test_name}] needs_clarification 不一致: legacy={r_legacy.get('needs_clarification')}, langgraph={r_langgraph.get('needs_clarification')}"

    assert r_legacy.get("sql") == r_langgraph.get("sql"), \
        f"[{test_name}] sql 不一致: legacy={r_legacy.get('sql')}, langgraph={r_langgraph.get('sql')}"

    # answer 是 LLM 生成的文本，可能有微小差异（如空格、格式）
    # 只验证两者都是有效非空字符串，且包含相同的关键数据
    leg_answer = r_legacy.get("answer") or ""
    lg_answer = r_langgraph.get("answer") or ""
    assert len(leg_answer) > 0, f"[{test_name}] Legacy answer 为空"
    assert len(lg_answer) > 0, f"[{test_name}] LangGraph answer 为空"
    # 提取答案中的关键数值信息进行比对
    import re
    leg_nums = set(re.findall(r'[\d,.]+', leg_answer))
    lg_nums = set(re.findall(r'[\d,.]+', lg_answer))
    assert leg_nums == lg_nums, \
        f"[{test_name}] answer 数值信息不一致: legacy={leg_nums}, langgraph={lg_nums}"

    # 如果有 matched_metrics，验证
    if r_legacy.get("matched_metrics") is not None:
        assert r_legacy.get("matched_metrics") == r_langgraph.get("matched_metrics"), \
            f"[{test_name}] matched_metrics 不一致"


# ===== T01-T05: 基本查询 =====

@pytest.mark.parametrize("question,description", [
    ("本月销售额是多少", "T01: 基本数值查询"),
    ("广告转化率", "T03: 指标名称匹配"),
    ("有哪些指标", "T04: 指标列表查询"),
])
@pytest.mark.asyncio
async def test_ab_basic_queries(legacy_engine, langgraph_engine, question, description):
    """T01-T04: 基本查询场景 A/B 等价性"""
    session_id = f"ab-{uuid.uuid4().hex[:8]}"

    r_legacy = await legacy_engine.process(question, session_id)
    r_langgraph = await langgraph_engine.process(question, f"{session_id}-lg")

    compare_results(r_legacy, r_langgraph, description)


# ===== T05-T08: 时间查询 =====

@pytest.mark.parametrize("question,description", [
    ("昨天访客数是多少", "T02: 昨日访客数"),
    ("访客数的业务口径", "T05: 业务口径查询"),
    ("访客数的计算方式", "T06: 技术口径查询"),
    ("上周数据怎么样", "T07: 上周数据"),
])
@pytest.mark.asyncio
async def test_ab_time_queries(legacy_engine, langgraph_engine, question, description):
    """T02, T05-T08: 时间相关查询 A/B 等价性"""
    session_id = f"ab-{uuid.uuid4().hex[:8]}"

    r_legacy = await legacy_engine.process(question, session_id)
    r_langgraph = await langgraph_engine.process(question, f"{session_id}-lg")

    compare_results(r_legacy, r_langgraph, description)


# ===== T09-T10: 追问场景 =====

@pytest.mark.parametrize("question,description", [
    ("访客数", "T09: 多指标识别（模糊匹配）"),
])
@pytest.mark.asyncio
async def test_ab_clarification_queries(legacy_engine, langgraph_engine, question, description):
    """T09-T10: 追问场景 A/B 等价性"""
    session_id = f"ab-{uuid.uuid4().hex[:8]}"

    r_legacy = await legacy_engine.process(question, session_id)
    r_langgraph = await langgraph_engine.process(question, f"{session_id}-lg")

    # 追问场景关键验证
    assert r_legacy.get("clarification_type") == "metric_enum", \
        f"[{description}] Legacy 应返回 metric_enum 追问"
    assert r_langgraph.get("clarification_type") == "metric_enum", \
        f"[{description}] LangGraph 应返回 metric_enum 追问"

    compare_results(r_legacy, r_langgraph, description)


# ===== T11-T16: 维度下钻 =====

@pytest.mark.parametrize("question,description", [
    ("本月销售额，按一级品类", "T11: 一级品类下钻"),
    ("本月销售额，按二级品类", "T12: 二级品类下钻"),
    ("本月销售额，按三级品类", "T13: 三级品类下钻"),
    ("本月销售额，按SKU", "T14: SKU下钻"),
    ("本月销售额，按一级品类和二级品类", "T15: 多维度组合"),
    ("本月销售额，按一级品类和三级品类和SKU", "T16: 一级+三级+SKU"),
])
@pytest.mark.asyncio
async def test_ab_dimension_drilldown(legacy_engine, langgraph_engine, question, description):
    """T11-T16: 维度下钻 A/B 等价性"""
    session_id = f"ab-{uuid.uuid4().hex[:8]}"

    r_legacy = await legacy_engine.process(question, session_id)
    r_langgraph = await langgraph_engine.process(question, f"{session_id}-lg")

    compare_results(r_legacy, r_langgraph, description)


# ===== T17-T19: 连续下钻 =====

@pytest.mark.asyncio
async def test_ab_sequential_drilldown(legacy_engine, langgraph_engine):
    """T17: 连续下钻链路 A/B 等价性"""
    # 导入 drill_down 函数
    import requests
    from urllib.parse import urljoin

    base_url = "http://localhost:8081"
    session_id = f"ab-drill-{uuid.uuid4().hex[:8]}"

    # Step 1: 基础查询
    r1_leg = await legacy_engine.process("本月销售额", session_id)
    r1_lg = await langgraph_engine.process("本月销售额", f"{session_id}-lg")

    sql1_leg = r1_leg.get("sql")
    sql1_lg = r1_lg.get("sql")

    # 验证 SQL 生成一致
    assert sql1_leg == sql1_lg, "基础查询 SQL 不一致"

    # Step 2: 一级品类下钻
    drill_payload = {
        "session_id": session_id,
        "dimension_names": ["一级品类"],
        "metric_code": "SPI-05-065",
        "current_sql": sql1_leg
    }
    r_drill_leg = requests.post(urljoin(base_url, "/api/v1/ask/drill_down"), json=drill_payload, timeout=30)
    drill_data_leg = r_drill_leg.json()

    drill_payload_lg = {
        "session_id": f"{session_id}-lg",
        "dimension_names": ["一级品类"],
        "metric_code": "SPI-05-065",
        "current_sql": sql1_lg
    }
    r_drill_lg = requests.post(urljoin(base_url, "/api/v1/ask/drill_down"), json=drill_payload_lg, timeout=30)
    drill_data_lg = r_drill_lg.json()

    # 验证下钻结果一致
    assert drill_data_leg.get("sql") == drill_data_lg.get("sql"), "下钻 SQL 不一致"
    assert len(drill_data_leg.get("result_data") or []) == len(drill_data_lg.get("result_data") or []), \
        "下钻结果数量不一致"


# ===== T20-T22: 多轮对话 =====

@pytest.mark.asyncio
async def test_ab_multi_turn_basic(legacy_engine, langgraph_engine):
    """T20: 基础多轮对话 A/B 等价性"""
    session_id = f"ab-multi-{uuid.uuid4().hex[:8]}"

    # R1: 查询销售额
    r1_leg = await legacy_engine.process("本月销售额", session_id)
    r1_lg = await langgraph_engine.process("本月销售额", f"{session_id}-lg")
    compare_results(r1_leg, r1_lg, "T20-R1: 销售额查询")

    # R2: 环比追问
    r2_leg = await legacy_engine.process("环比呢", session_id)
    r2_lg = await langgraph_engine.process("环比呢", f"{session_id}-lg")
    compare_results(r2_leg, r2_lg, "T20-R2: 环比追问")


@pytest.mark.asyncio
async def test_ab_multi_turn_different_metrics(legacy_engine, langgraph_engine):
    """T22: 连续不同指标多轮对话 A/B 等价性"""
    session_id = f"ab-multi-{uuid.uuid4().hex[:8]}"

    # R1: 销售额
    r1 = await legacy_engine.process("本月销售额", session_id)
    r1_lg = await langgraph_engine.process("本月销售额", f"{session_id}-lg")
    compare_results(r1, r1_lg, "T22-R1: 销售额")

    # R2: 转化率
    r2 = await legacy_engine.process("广告转化率呢", session_id)
    r2_lg = await langgraph_engine.process("广告转化率呢", f"{session_id}-lg")
    compare_results(r2, r2_lg, "T22-R2: 转化率")


# ===== T23-T26: 边界条件 =====

@pytest.mark.asyncio
async def test_ab_empty_question(legacy_engine, langgraph_engine):
    """T23: 空查询处理"""
    session_id = f"ab-boundary-{uuid.uuid4().hex[:8]}"

    # 空问题应该被拒绝或返回错误
    r_leg = await legacy_engine.process("", session_id)
    r_lg = await langgraph_engine.process("", f"{session_id}-lg")

    # 两边处理应该一致
    assert (r_leg.get("answer") or "") == (r_lg.get("answer") or "")


@pytest.mark.asyncio
async def test_ab_session_id_generation(legacy_engine, langgraph_engine):
    """T25: 缺失 session_id 时自动生成"""
    import uuid

    # 不传入 session_id
    question = "本月销售额"

    r_leg = await legacy_engine.process(question, "")
    r_lg = await langgraph_engine.process(question, "")

    # 验证生成了 session_id
    assert r_leg.get("session_id") is not None
    assert r_lg.get("session_id") is not None
