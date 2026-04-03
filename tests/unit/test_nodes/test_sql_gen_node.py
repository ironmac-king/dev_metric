"""SQL Gen Node 单元测试"""
import pytest
from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import ConversationNodes


class TestSQLGenNode:
    """SQL 生成节点测试"""

    @pytest.fixture
    def nodes(self):
        return ConversationNodes()

    @pytest.fixture
    def state_with_metric(self):
        """带指标实体的状态 fixture"""
        def _make_state(intent: str, metric_name: str = "访客数",
                       metric_code: str = "MKI-02-0001",
                       time_range: str = None):
            state = ConversationState(session_id="test-123")
            state.messages.append(ConversationMessage(role="user", content="测试"))
            state.current_intent = intent
            state.entities = {
                "metric_name": metric_name,
                "metric_code": metric_code,
            }
            if time_range:
                state.entities["time_range"] = time_range
            return state
        return _make_state

    def test_skip_for_greeting(self, nodes, state_with_metric):
        """打招呼意图跳过 SQL 生成"""
        state = state_with_metric("greeting")
        result = nodes.sql_gen_node(state)

        assert result.get("skip_sql_generation") is True

    def test_skip_for_thanks(self, nodes, state_with_metric):
        """感谢意图跳过 SQL 生成"""
        state = state_with_metric("thanks")
        result = nodes.sql_gen_node(state)

        assert result.get("skip_sql_generation") is True

    def test_metadata_query_flag(self, nodes, state_with_metric):
        """元数据查询意图"""
        state = state_with_metric("query_metadata")
        result = nodes.sql_gen_node(state)

        assert result.get("generated_sql") == "METADATA_QUERY"

    def test_value_query_with_starrocks_sql(self, nodes, state_with_metric):
        """数值查询 - 有预置 SQL"""
        state = state_with_metric("query_value", metric_code="MKI-02-0001", time_range="最近7天")
        state.entities["starrocks_sql"] = "SELECT date, SUM(sessions) as value FROM metric_data WHERE metric_id = 1 GROUP BY date"
        result = nodes.sql_gen_node(state)

        # 有 starrocks_sql 但无 time_info 时，会触发追问（因为 time_range 被识别但 time_info 缺失）
        # 此时要么返回 SQL，要么触发追问
        assert result.get("generated_sql") is not None or result.get("needs_clarification") is True

    def test_value_query_without_sql(self, nodes, state_with_metric):
        """数值查询 - 无预置 SQL"""
        state = state_with_metric("query_value", metric_code="MKI-02-0001")
        state.entities.pop("starrocks_sql", None)
        result = nodes.sql_gen_node(state)

        # 应该返回 fallback SQL 或触发追问
        assert result.get("generated_sql") is not None or result.get("needs_clarification") is True

    def test_trend_query(self, nodes, state_with_metric):
        """趋势查询"""
        state = state_with_metric("query_trend", metric_code="MKI-02-0001", time_range="最近7天")
        state.entities["starrocks_sql"] = "SELECT date, value FROM metric_data WHERE metric_id = 1"
        result = nodes.sql_gen_node(state)

        # 有 starrocks_sql 但无 time_info 时，会触发追问
        assert result.get("generated_sql") is not None or result.get("needs_clarification") is True

    def test_comparison_query(self, nodes, state_with_metric):
        """对比查询"""
        state = state_with_metric("query_comparison", metric_code="MKI-02-0001", time_range="最近7天")
        state.entities["starrocks_sql"] = "SELECT date, value FROM metric_data WHERE metric_id = 1"
        result = nodes.sql_gen_node(state)

        # 有 starrocks_sql 但无 time_info 时，会触发追问
        assert result.get("generated_sql") is not None or result.get("needs_clarification") is True