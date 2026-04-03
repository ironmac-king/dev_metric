"""状态转换集成测试"""
import pytest
import asyncio
from ai.graph.state import ConversationState, ConversationMessage, ConversationContext
from ai.graph.nodes import ConversationNodes
from ai.engine.langgraph_engine import create_langgraph_app


class TestStateTransitions:
    """状态转换测试"""

    @pytest.fixture
    def app(self):
        return create_langgraph_app()

    @pytest.fixture
    def nodes(self):
        return ConversationNodes()

    def create_state(self, intent=None, entities=None, messages=None):
        """创建测试状态"""
        state = ConversationState(
            session_id="test-transition",
            current_intent=intent or "query_value",
            entities=entities or {},
        )
        if messages:
            for msg in messages:
                state.messages.append(ConversationMessage(**msg))
        else:
            state.messages.append(ConversationMessage(role="user", content="测试"))
        return state

    @pytest.mark.asyncio
    async def test_intent_to_entity_transition(self, app):
        """意图识别 → 实体链接转换"""
        initial_state = self.create_state(
            intent=None,
            messages=[{"role": "user", "content": "本月访客数"}]
        )

        config = {"configurable": {"thread_id": "test-intent-entity"}}
        result = await app.ainvoke(initial_state, config=config)

        # 验证 intent 被设置
        assert result.get("current_intent") is not None
        # 验证 entities 被填充
        assert len(result.get("entities", {})) > 0

    @pytest.mark.asyncio
    async def test_full_flow_simple_query(self, app):
        """完整流程 - 简单查询"""
        initial_state = self.create_state(
            intent="query_value",
            entities={"metric_name": "访客数", "metric_code": "MKI-02-0001"},
            messages=[{"role": "user", "content": "访客数"}]
        )

        config = {"configurable": {"thread_id": "test-full-flow"}}
        result = await app.ainvoke(initial_state, config=config)

        # 验证最终状态包含 answer
        assert "answer" in result or result.get("needs_clarification") is not None

    @pytest.mark.asyncio
    async def test_flow_with_clarification(self, app):
        """完整流程 - 带追问"""
        initial_state = self.create_state(
            intent="query_value",
            messages=[{"role": "user", "content": "销售额"}]
        )

        config = {"configurable": {"thread_id": "test-clarification"}}
        result = await app.ainvoke(initial_state, config=config)

        # 如果无法确定指标，应该追问
        # 验证返回了 clarification 或者成功生成了 SQL
        assert (
            result.get("needs_clarification") is True or
            result.get("generated_sql") is not None or
            result.get("answer") is not None
        )

    @pytest.mark.asyncio
    async def test_metadata_query_flow(self, app):
        """完整流程 - 元数据查询"""
        initial_state = self.create_state(
            intent="query_metadata",
            entities={"metric_name": "访客数", "metric_code": "MKI-02-0001"},
            messages=[{"role": "user", "content": "访客数的业务口径"}]
        )

        config = {"configurable": {"thread_id": "test-metadata"}}
        result = await app.ainvoke(initial_state, config=config)

        # 元数据查询应该设置 intent_is_metadata_query
        assert result.get("intent_is_metadata_query") is True or result.get("answer") is not None