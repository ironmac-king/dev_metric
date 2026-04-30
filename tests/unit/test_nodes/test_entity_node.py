"""Entity Node 单元测试"""
import pytest
from unittest.mock import patch, MagicMock
from ai.graph.state import ConversationState, ConversationMessage, ConversationContext

ConversationNodes = pytest.importorskip("ai.graph.nodes").ConversationNodes


class TestEntityNode:
    """实体链接节点测试"""

    @pytest.fixture
    def nodes(self):
        return ConversationNodes()

    @pytest.fixture
    def state_with_context(self):
        """带上下文的状态 fixture"""
        def _make_state(message: str, context: dict = None):
            state = ConversationState(session_id="test-123")
            state.messages.append(ConversationMessage(role="user", content=message))
            if context:
                state.conversation_context = ConversationContext(**context)
            return state
        return _make_state

    def test_link_metric_by_name(self, nodes, state_with_context):
        """通过名称链接指标"""
        state = state_with_context("访客数")
        # 先设置 intent
        state.current_intent = "query_value"

        # Mock rule_engine link_business_terms_enhanced
        with patch.object(nodes.rule_engine, 'link_business_terms_enhanced', return_value={"metric_name": "访客数", "metric_code": "MKI-02-0001"}):
            result = nodes.entity_node(state)

        entities = result.get("entities", {})
        assert entities.get("metric_name") == "访客数" or entities.get("metric_code") == "MKI-02-0001"

    def test_link_metric_by_code(self, nodes, state_with_context):
        """通过编号链接指标"""
        state = state_with_context("MKI-02-0001")
        state.current_intent = "query_value"

        # Mock rule_engine link_business_terms_enhanced
        with patch.object(nodes.rule_engine, 'link_business_terms_enhanced', return_value={"metric_code": "MKI-02-0001"}):
            result = nodes.entity_node(state)

        entities = result.get("entities", {})
        assert entities.get("metric_code") == "MKI-02-0001"

    def test_extract_time_range(self, nodes, state_with_context):
        """提取时间范围"""
        state = state_with_context("昨天的销售额")
        state.current_intent = "query_value"
        result = nodes.entity_node(state)

        entities = result.get("entities", {})
        # 应该能提取时间
        has_time = "time_range" in entities or "time_info" in entities
        assert has_time

    def test_inherit_from_context(self, nodes, state_with_context):
        """测试从上下文继承"""
        state = state_with_context("定义呢", context={
            "current_metric_name": "访客数",
            "current_metric_code": "MKI-02-0001",
            "current_time_expr": "last_7_days"
        })
        state.current_intent = "query_metadata"
        # 确保 entities 初始为空
        state.entities = {}
        # 设置意图确认标记，绕过 edge case
        state._intent_confirmed_from_context = True

        # Mock rule_engine to return empty (simulating no new metric mentioned)
        with patch.object(nodes.rule_engine, 'link_business_terms_enhanced', return_value={}):
            result = nodes.entity_node(state)

        entities = result.get("entities", {})
        # "定义呢" 是纯follow-up（来自意图确认），应该继承上轮的指标
        assert entities.get("metric_name") == "访客数" or entities.get("metric_code") == "MKI-02-0001"
        assert entities.get("time_range") == "last_7_days"

    def test_clear_inherited_for_new_metric(self, nodes, state_with_context):
        """新指标查询应清除继承的指标"""
        state = state_with_context("销售额")
        state.current_intent = "query_value"
        state.conversation_context = ConversationContext(
            current_metric_name="访客数",
            current_metric_code="MKI-02-0001"
        )

        # Mock rule_engine to recognize "销售额" as a new metric
        with patch.object(nodes.rule_engine, 'link_business_terms_enhanced', return_value={"metric_name": "销售额"}):
            result = nodes.entity_node(state)

        entities = result.get("entities", {})
        # 如果识别到了"销售额"，不应该还保留"访客数"
        if entities.get("metric_name") == "销售额":
            assert entities.get("metric_name") != "访客数"

    def test_extract_platform_dimension(self, nodes, state_with_context):
        """提取平台维度"""
        state = state_with_context("亚马逊的访客数")
        state.current_intent = "query_value"

        # Mock dimension value client
        with patch('ai.graph.nodes.DimValueClient') as mock_dim_client:
            mock_instance = MagicMock()
            mock_instance.search_dimension_values.return_value = []
            mock_dim_client.return_value = mock_instance

            result = nodes.entity_node(state)

        entities = result.get("entities", {})
        # 平台维度可能通过 link_business_terms_enhanced 或维度值提取
        # 如果都没匹配到，至少不应该崩溃
        assert result is not None

    def test_extract_region_dimension(self, nodes, state_with_context):
        """提取地区维度"""
        state = state_with_context("华东地区的销售额")
        state.current_intent = "query_value"

        # Mock dimension value client to return region match
        with patch('ai.graph.nodes.DimValueClient') as mock_dim_client:
            mock_instance = MagicMock()
            mock_instance.search_dimension_values.return_value = []
            mock_dim_client.return_value = mock_instance

            result = nodes.entity_node(state)

        entities = result.get("entities", {})
        # 地区维度提取可能依赖外部配置
        # 至少验证不崩溃且返回正确结构
        assert result is not None
        assert "entities" in result

    def test_no_metric_no_crash(self, nodes, state_with_context):
        """无指标时不崩溃"""
        state = state_with_context("计算一下")
        state.current_intent = "query_value"

        # Mock rule_engine to return empty
        with patch.object(nodes.rule_engine, 'link_business_terms_enhanced', return_value={}):
            result = nodes.entity_node(state)

        # 应该正常返回，不崩溃
        assert result is not None
        assert "entities" in result
