"""边界条件测试"""
import pytest
from ai.graph.state import ConversationState, ConversationMessage

ConversationNodes = pytest.importorskip("ai.graph.nodes").ConversationNodes


class TestEdgeCases:
    """边界条件测试"""

    @pytest.fixture
    def nodes(self):
        return ConversationNodes()

    def test_very_long_message(self, nodes):
        """超长消息处理"""
        state = ConversationState(session_id="test")
        long_content = "访客数 " * 1000  # 模拟超长输入
        state.messages.append(ConversationMessage(role="user", content=long_content))
        state.current_intent = "query_value"

        # 不应崩溃
        try:
            result = nodes.intent_node(state)
            assert result is not None
        except Exception as e:
            pytest.fail(f"超长消息导致崩溃: {e}")

    def test_special_characters_in_message(self, nodes):
        """特殊字符处理"""
        state = ConversationState(session_id="test")
        special_content = "访客数<script>alert('xss')</script>测试'drop'"
        state.messages.append(ConversationMessage(role="user", content=special_content))
        state.current_intent = "query_value"

        result = nodes.intent_node(state)
        assert result is not None

    def test_emoji_in_message(self, nodes):
        """Emoji 处理"""
        state = ConversationState(session_id="test")
        emoji_content = "访客数是多少 😄🎉"
        state.messages.append(ConversationMessage(role="user", content=emoji_content))
        state.current_intent = "query_value"

        result = nodes.intent_node(state)
        assert result is not None

    def test_empty_entities_dict(self, nodes):
        """空实体字典"""
        state = ConversationState(session_id="test")
        state.messages.append(ConversationMessage(role="user", content="测试"))
        state.current_intent = "query_value"
        state.entities = {}

        result = nodes.entity_node(state)
        assert result is not None

    def test_none_values_in_entities(self, nodes):
        """实体中包含 None 值"""
        state = ConversationState(session_id="test")
        state.messages.append(ConversationMessage(role="user", content="测试"))
        state.current_intent = "query_value"
        state.entities = {
            "metric_name": None,
            "metric_code": None,
            "time_range": None
        }

        result = nodes.entity_node(state)
        assert result is not None

    def test_unicode_metric_names(self, nodes):
        """Unicode 指标名称"""
        state = ConversationState(session_id="test")
        state.messages.append(ConversationMessage(role="user", content="测试指标"))
        state.current_intent = "query_value"
        state.entities = {"metric_name": "测试指标名", "metric_code": "TEST-001"}

        result = nodes.sql_gen_node(state)
        assert result is not None

    def test_concurrent_state_updates(self):
        """并发状态更新（模拟）"""
        import threading
        from ai.graph.state import ConversationState

        state = ConversationState(session_id="test")
        errors = []

        def update_state(i):
            try:
                state.entities[f"key_{i}"] = i
                state.current_intent = f"intent_{i}"
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_state, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 不应该有错误
        assert len(errors) == 0
