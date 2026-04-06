"""
单元测试: should_clarify 条件边路由逻辑
"""
import pytest
from ai.engine.langgraph_engine import should_clarify
from ai.graph.state import ConversationState


def test_should_clarify_true():
    """验证 needs_clarification=True 时返回 True"""
    state = ConversationState(session_id="test")
    state.needs_clarification = True
    assert should_clarify(state) is True


def test_should_clarify_false():
    """验证 needs_clarification=False 时返回 False"""
    state = ConversationState(session_id="test")
    state.needs_clarification = False
    assert should_clarify(state) is False


def test_should_clarify_default():
    """验证未设置 needs_clarification 时默认返回 False"""
    state = ConversationState(session_id="test")
    # 不设置 needs_clarification，使用默认值
    assert should_clarify(state) is False


def test_should_clarify_with_none():
    """验证 needs_clarification=None 时返回 False"""
    state = ConversationState(session_id="test")
    state.needs_clarification = None
    assert should_clarify(state) is False


@pytest.mark.asyncio
async def test_langgraph_conditional_edge_routing(langgraph_engine, session_id):
    """验证 LangGraph 条件边正确路由: 需要追问时跳转到 response"""
    # 使用会触发追问的问题
    result = await langgraph_engine.process(
        question="访客数",
        session_id=session_id,
        page=1,
        page_size=10
    )

    # 应该进入追问流程
    assert result.get("needs_clarification") is True
    assert result.get("clarification_message") is not None
    assert result.get("sql") is None  # 追问时不应生成 SQL
