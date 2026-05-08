"""Response Node 单元测试"""
import pytest
from ai.graph.state import ConversationState, ConversationMessage

ConversationNodes = pytest.importorskip("ai.graph.nodes").ConversationNodes


class TestResponseNode:
    """响应生成节点测试"""

    @pytest.fixture
    def nodes(self):
        return ConversationNodes()

    @pytest.fixture
    def state_for_response(self):
        """用于生成响应的状态 fixture"""
        def _make_state(intent: str, answer: str = None,
                       needs_clarification: bool = False,
                       clarification_message: str = None):
            state = ConversationState(session_id="test-123")
            state.messages.append(ConversationMessage(role="user", content="测试问题"))
            state.current_intent = intent
            state.generated_sql = "SELECT 1"
            state.sql_result = {"data": [{"value": 100}]}

            if answer:
                state.messages.append(ConversationMessage(role="assistant", content=answer))

            if needs_clarification:
                state.needs_clarification = True
                state.clarification_message = clarification_message or "需要更多信息"

            return state
        return _make_state

    def test_greeting_response(self, nodes, state_for_response):
        """打招呼响应"""
        state = state_for_response("greeting")
        result = nodes.response_node(state)

        assert "answer" in result
        assert len(result["answer"]) > 0

    def test_thanks_response(self, nodes, state_for_response):
        """感谢响应"""
        state = state_for_response("thanks")
        result = nodes.response_node(state)

        assert "answer" in result

    def test_bye_response(self, nodes, state_for_response):
        """告别响应"""
        state = state_for_response("bye")
        result = nodes.response_node(state)

        assert "answer" in result

    def test_clarification_response(self, nodes, state_for_response):
        """追问响应"""
        state = state_for_response("query_value", needs_clarification=True,
                                   clarification_message="请告诉我要查询哪个指标")
        result = nodes.response_node(state)

        assert result.get("needs_clarification") is True
        assert "answer" in result

    def test_value_response(self, nodes, state_for_response):
        """数值查询响应"""
        state = state_for_response("query_value")
        state.sql_result = {"data": [{"date": "2026-04-02", "value": 12345}]}
        result = nodes.response_node(state)

        assert "answer" in result
        # 应该包含数据或暂无数据提示
        assert len(result["answer"]) > 0

    def test_empty_result_response(self, nodes, state_for_response):
        """空结果响应"""
        state = state_for_response("query_value")
        state.sql_result = {"data": [], "message": "暂无数据"}
        result = nodes.response_node(state)

        assert "answer" in result
        # 应该给出建议
        assert "suggest_questions" in result or result.get("needs_clarification") is True

    def test_suggestions_returned(self, nodes, state_for_response):
        """建议问题返回"""
        state = state_for_response("query_value")
        state.entities["metric_name"] = "访客数"
        result = nodes.response_node(state)

        assert "suggest_questions" in result
        assert isinstance(result["suggest_questions"], list)
