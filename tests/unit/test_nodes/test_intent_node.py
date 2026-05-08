"""Intent Node 单元测试"""
import pytest
from ai.graph.state import ConversationState, ConversationMessage

ConversationNodes = pytest.importorskip("ai.graph.nodes").ConversationNodes


class TestIntentNode:
    """意图识别节点测试"""

    @pytest.fixture
    def nodes(self):
        """节点实例 fixture"""
        return ConversationNodes()

    @pytest.fixture
    def state_with_message(self):
        """带消息的状态 fixture"""
        def _make_state(message: str):
            state = ConversationState(session_id="test-123")
            state.messages.append(ConversationMessage(role="user", content=message))
            return state
        return _make_state

    def test_recognize_value_query(self, nodes, state_with_message):
        """识别数值查询意图"""
        state = state_with_message("本月销售额是多少")
        result = nodes.intent_node(state)

        assert result["current_intent"] in ["query_value", "query_trend", "query_comparison"]
        assert "entities" in result

    def test_recognize_trend_query(self, nodes, state_with_message):
        """识别趋势查询意图"""
        state = state_with_message("访客数的趋势是什么")
        result = nodes.intent_node(state)

        assert result["current_intent"] == "query_trend"

    def test_recognize_metadata_query(self, nodes, state_with_message):
        """识别元数据查询意图"""
        state = state_with_message("访客数的业务口径是什么")
        result = nodes.intent_node(state)

        assert result["current_intent"] == "query_metadata"

    def test_recognize_greeting(self, nodes, state_with_message):
        """识别打招呼"""
        state = state_with_message("你好")
        result = nodes.intent_node(state)

        assert result["current_intent"] == "greeting"

    def test_recognize_comparison(self, nodes, state_with_message):
        """识别对比查询"""
        state = state_with_message("本月销售额对比上月")
        result = nodes.intent_node(state)

        assert result["current_intent"] in ["query_comparison", "query_value"]

    def test_recognize_with_time(self, nodes, state_with_message):
        """识别时间范围"""
        state = state_with_message("昨天的访客数")
        result = nodes.intent_node(state)

        entities = result.get("entities", {})
        # 应该能识别出时间
        assert "time_range" in entities or "time_info" in entities

    def test_empty_message(self, nodes, state_with_message):
        """空消息处理"""
        state = state_with_message("")
        result = nodes.intent_node(state)

        # 空消息不应崩溃
        assert result is not None
        assert "current_intent" in result

    def test_confidence_threshold(self, nodes, state_with_message):
        """置信度阈值测试"""
        state = state_with_message("模糊不清的内容xyz123")
        result = nodes.intent_node(state)

        # 应该能返回结果，即使是 low confidence
        assert "current_intent" in result or state.needs_clarification
