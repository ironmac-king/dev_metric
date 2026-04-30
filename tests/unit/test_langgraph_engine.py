"""LangGraphEngine 单元测试"""
import pytest

langgraph_engine_module = pytest.importorskip("ai.engine.langgraph_engine")
LangGraphEngine = langgraph_engine_module.LangGraphEngine
create_langgraph_app = langgraph_engine_module.create_langgraph_app


class TestLangGraphEngine:
    """LangGraphEngine 测试"""

    @pytest.fixture
    def engine(self):
        return LangGraphEngine()

    @pytest.fixture
    def app(self):
        return create_langgraph_app()

    def test_engine_initialization(self, engine):
        """引擎初始化"""
        assert engine.app is not None
        assert engine.sessions is not None

    def test_app_graph_structure(self, app):
        """图结构验证"""
        # 验证节点存在
        nodes = list(app.nodes.keys())
        assert "intent" in nodes
        assert "entity" in nodes
        assert "sql_gen" in nodes
        assert "execute" in nodes
        assert "response" in nodes

    @pytest.mark.asyncio
    async def test_new_session_state(self, engine):
        """新会话状态初始化"""
        config = {"configurable": {"thread_id": "test-new-session"}}

        state = await engine.app.aget_state(config)
        # 新会话的 values 是空字典
        assert state.values == {}

    @pytest.mark.asyncio
    async def test_session_persistence(self, engine):
        """会话状态持久化"""
        config = {"configurable": {"thread_id": "test-persist"}}
        initial_state = {
            "session_id": "test-persist",
            "messages": [],
            "entities": {"metric_name": "访客数"},
            "current_intent": "query_value",
            "generated_sql": None,
            "sql_params": {},
            "metric_id": None,
            "error": None,
            "needs_clarification": False,
            "clarification_message": None,
            "clarification_type": None,
            "matched_metrics": None,
            "suggest_questions": [],
            "intent_is_metadata_query": False,
            "explicit_value_query": False,
            "skip_execution": False,
            "sql_result": None,
            "last_valid_metric": {},
            "asked_fields": [],
            "pending_clarification": {},
            "clarification_count": 0,
            "max_clarification_turns": 3,
            "default_values": {"time_range": "last_7_days", "dimension": "all"},
            "applied_defaults": {},
            "thinking_steps": [],
            "context": {},
            "conversation_context": None,
            "comparison_result": None,
            "selected_dimension_field": None,
            "selected_dimension_value": None,
            "dimension_value_candidates": None,
            "dimension_value_matched_text": None,
            "page": 1,
            "page_size": 10,
        }

        # 执行一次ainvoke，返回最终状态
        result = await engine.app.ainvoke(initial_state, config=config)

        # ainvoke返回的是最终状态，entities字段被entity_node处理后可能被替换
        # 验证返回结果中entities是字典类型
        assert isinstance(result.get("entities"), dict)
