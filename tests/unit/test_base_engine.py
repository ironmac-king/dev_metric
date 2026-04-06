"""
单元测试: ConversationEngine 接口和 get_engine() 工厂函数
"""
import pytest
from ai.engine.base import ConversationEngine, get_engine
from ai.engine.legacy_engine import LegacyEngine
from ai.engine.langgraph_engine import LangGraphEngine


def test_get_engine_legacy():
    """验证 get_engine('legacy') 返回 LegacyEngine 实例"""
    engine = get_engine("legacy")
    assert isinstance(engine, LegacyEngine)
    assert isinstance(engine, ConversationEngine)


def test_get_engine_langgraph():
    """验证 get_engine('langgraph') 返回 LangGraphEngine 实例"""
    engine = get_engine("langgraph")
    assert isinstance(engine, LangGraphEngine)
    assert isinstance(engine, ConversationEngine)


def test_get_engine_default():
    """验证 get_engine() 默认返回 LegacyEngine"""
    engine = get_engine()
    assert isinstance(engine, LegacyEngine)


def test_get_engine_invalid():
    """验证无效 engine_type 回退到 legacy"""
    engine = get_engine("invalid_engine")
    assert isinstance(engine, LegacyEngine)


def test_engine_interface_methods():
    """验证引擎实现必要的接口方法"""
    legacy = get_engine("legacy")
    langgraph = get_engine("langgraph")

    # LegacyEngine
    assert hasattr(legacy, 'process')
    assert hasattr(legacy, 'get_state')
    assert callable(legacy.process)
    assert callable(legacy.get_state)

    # LangGraphEngine
    assert hasattr(langgraph, 'process')
    assert hasattr(langgraph, 'get_state')
    assert callable(langgraph.process)
    assert callable(langgraph.get_state)


@pytest.mark.asyncio
async def test_legacy_engine_process_returns_dict(legacy_engine, session_id):
    """验证 LegacyEngine.process() 返回正确格式的 dict"""
    result = await legacy_engine.process(
        question="本月销售额是多少",
        session_id=session_id,
        page=1,
        page_size=10
    )

    assert isinstance(result, dict)
    assert "answer" in result
    assert "session_id" in result
    assert "sql" in result
    assert "clarification_type" in result
    assert "needs_clarification" in result


@pytest.mark.asyncio
async def test_langgraph_engine_process_returns_dict(langgraph_engine, session_id):
    """验证 LangGraphEngine.process() 返回正确格式的 dict"""
    result = await langgraph_engine.process(
        question="本月销售额是多少",
        session_id=session_id,
        page=1,
        page_size=10
    )

    assert isinstance(result, dict)
    assert "answer" in result
    assert "session_id" in result
    assert "sql" in result
    assert "clarification_type" in result
    assert "needs_clarification" in result
