"""ConversationState 单元测试"""
import pytest
from ai.graph.state import (
    ConversationState, ConversationMessage, ConversationContext,
    IntentResult, SQLGenerationResult, ThinkingStep
)
from datetime import datetime


class TestConversationState:
    """ConversationState 测试"""

    def test_create_empty_state(self):
        """创建空状态"""
        state = ConversationState()
        assert state.session_id == ""
        assert state.messages == []
        assert state.entities == {}
        assert state.current_intent is None

    def test_create_state_with_values(self):
        """创建带值的状态"""
        state = ConversationState(
            session_id="test-123",
            current_intent="query_value",
            entities={"metric_name": "访客数", "metric_code": "MKI-02-0001"}
        )
        assert state.session_id == "test-123"
        assert state.current_intent == "query_value"
        assert state.entities["metric_name"] == "访客数"

    def test_state_default_values(self):
        """测试默认值"""
        state = ConversationState()
        assert state.default_values["time_range"] == "last_7_days"
        assert state.default_values["dimension"] == "all"
        assert state.max_clarification_turns == 3

    def test_add_message(self):
        """添加消息"""
        state = ConversationState()
        state.messages.append(ConversationMessage(role="user", content="本月销售额"))
        assert len(state.messages) == 1
        assert state.messages[0].role == "user"
        assert state.messages[0].content == "本月销售额"

    def test_update_entities(self):
        """更新实体"""
        state = ConversationState()
        state.entities = {"metric_name": "访客数"}
        state.entities.update({"metric_code": "MKI-02-0001", "time_range": "last_7_days"})
        assert "metric_code" in state.entities
        assert state.entities["time_range"] == "last_7_days"

    def test_clarification_fields(self):
        """测试追问字段"""
        state = ConversationState()
        state.needs_clarification = True
        state.clarification_type = "metric_missing"
        state.clarification_message = "请告诉我要查询哪个指标"
        assert state.needs_clarification is True
        assert state.clarification_type == "metric_missing"


class TestConversationContext:
    """ConversationContext 测试"""

    def test_create_empty_context(self):
        """创建空上下文"""
        ctx = ConversationContext()
        assert ctx.current_metric_code is None
        assert ctx.current_metric_name is None
        assert ctx.current_dimensions == {}

    def test_context_inheritance(self):
        """测试上下文继承"""
        ctx = ConversationContext(
            current_metric_name="访客数",
            current_metric_code="MKI-02-0001",
            current_time_expr="last_7_days",
            current_dimensions={"platform": "amazon"}
        )
        assert ctx.current_metric_name == "访客数"
        assert ctx.current_dimensions["platform"] == "amazon"

    def test_to_dict_from_dict(self):
        """测试序列化/反序列化"""
        ctx = ConversationContext(
            current_metric_name="销售额",
            current_metric_code="MKI-01-0001",
            current_time_expr="this_month"
        )
        d = ctx.to_dict()
        restored = ConversationContext.from_dict(d)
        assert restored.current_metric_name == ctx.current_metric_name
        assert restored.current_metric_code == ctx.current_metric_code


class TestThinkingStep:
    """ThinkingStep 测试"""

    def test_create_thinking_step(self):
        """创建思考步骤"""
        step = ThinkingStep(
            step="意图理解",
            status="completed",
            content="识别为 query_value",
            llm_used=True
        )
        assert step.step == "意图理解"
        assert step.status == "completed"
        assert step.llm_used is True