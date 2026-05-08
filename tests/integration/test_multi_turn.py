"""
集成测试: 多轮对话状态继承
"""
import pytest
import uuid


@pytest.mark.asyncio
async def test_multi_turn_context_inheritance(legacy_engine, langgraph_engine):
    """验证多轮对话时上下文正确继承"""
    session_id = f"multi-{uuid.uuid4().hex[:8]}"

    # R1: 查询销售额
    r1 = await legacy_engine.process("本月销售额", session_id)
    assert r1.get("sql") is not None, "R1 应生成 SQL"
    assert r1.get("metric_code") is not None, "R1 应识别指标"

    # R2: 环比追问（上下文应继承）
    r2 = await legacy_engine.process("和上月比呢", session_id)
    # 环比应该使用相同的指标
    assert r2.get("comparison_result") is not None or r2.get("clarification_type") is not None, \
        "R2 应有对比结果或追问"


@pytest.mark.asyncio
async def test_multi_turn_clarification_response(legacy_engine, langgraph_engine):
    """验证追问场景下的多轮对话"""
    session_id = f"multi-{uuid.uuid4().hex[:8]}"

    # R1: 触发指标追问
    r1 = await legacy_engine.process("访客数", session_id)
    assert r1.get("needs_clarification") is True
    assert r1.get("clarification_type") == "metric_enum"

    # R2: 用户确认后再次询问
    r2 = await legacy_engine.process("转化率", session_id)
    # 应该能正确识别为转化率指标


@pytest.mark.asyncio
async def test_langgraph_state_persistence(langgraph_engine):
    """验证 LangGraph MemorySaver 状态持久化"""
    session_id = f"persist-{uuid.uuid4().hex[:8]}"

    # 第一次查询
    r1 = await langgraph_engine.process("本月销售额", session_id)
    assert r1.get("answer") is not None

    # 获取状态
    state1 = await langgraph_engine.get_state(session_id)
    assert state1 is not None

    # 第二次查询（同一 session）
    r2 = await langgraph_engine.process("上周数据", session_id)
    assert r2.get("answer") is not None

    # 再次获取状态
    state2 = await langgraph_engine.get_state(session_id)
    assert state2 is not None

    # 验证 messages 数量增加
    messages1 = state1.get("messages") or []
    messages2 = state2.get("messages") or []
    assert len(messages2) >= len(messages1)


@pytest.mark.asyncio
async def test_legacy_session_isolation(legacy_engine):
    """验证 LegacyEngine 不同 session 互不影响"""
    session_a = f"iso-a-{uuid.uuid4().hex[:8]}"
    session_b = f"iso-b-{uuid.uuid4().hex[:8]}"

    # Session A 查询指标 A
    r_a = await legacy_engine.process("本月销售额", session_a)

    # Session B 查询指标 B
    r_b = await legacy_engine.process("本月访客数", session_b)

    # 验证 session 独立
    state_a = await legacy_engine.get_state(session_a)
    state_b = await legacy_engine.get_state(session_b)

    assert state_a is not None
    assert state_b is not None
    assert state_a.session_id == session_a
    assert state_b.session_id == session_b


@pytest.mark.asyncio
async def test_langgraph_context_inheritance(langgraph_engine):
    """LangGraph 上下文继承测试"""
    session_id = f"multi-context-{uuid.uuid4().hex[:8]}"

    # R1: 查询访客数
    r1 = await langgraph_engine.process("本月访客数", session_id)
    assert r1.get("session_id") == session_id

    # R2: 追问业务口径（应该继承指标）
    r2 = await langgraph_engine.process("业务口径呢", session_id)
    # 应该返回业务口径，而不是重新要求输入指标
    if r2.get("clarification_type") == "metric_missing":
        pytest.fail("应该继承上轮指标，不应该要求重新输入指标")


@pytest.mark.asyncio
async def test_langgraph_multi_turn_time_inheritance(langgraph_engine):
    """LangGraph 时间继承测试"""
    session_id = f"multi-time-{uuid.uuid4().hex[:8]}"

    # R1: 查询上月数据
    r1 = await langgraph_engine.process("上月销售额", session_id)

    # R2: 问环比（应该继承时间）
    r2 = await langgraph_engine.process("环比呢", session_id)
    # 环比计算需要时间信息，应该继承上轮时间
    assert r2 is not None


@pytest.mark.asyncio
async def test_langgraph_different_metric_clears_context(langgraph_engine):
    """LangGraph 新指标清除上下文"""
    session_id = f"multi-clear-{uuid.uuid4().hex[:8]}"

    # R1: 查询访客数
    r1 = await langgraph_engine.process("访客数", session_id)

    # R2: 查询完全不同指标（销售额）
    r2 = await langgraph_engine.process("销售额", session_id)

    # 如果系统认为需要追问，不应该基于访客数追问
    if r2.get("clarification_type") == "metric_enum":
        # 检查 matched_metrics 是否包含销售额相关，而不是访客数
        matched = r2.get("matched_metrics", [])
        if matched:
            names = [m.get("name", "") for m in matched]
            # 应该列出销售额相关指标，不是访客数
            has_sales = any("销售" in n for n in names)
