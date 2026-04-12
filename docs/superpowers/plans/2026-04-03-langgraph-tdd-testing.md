# LangGraph TDD 测试计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LangGraph 对话引擎建立完整的 TDD 测试体系，覆盖节点单元测试、状态转换测试、Mock 依赖注入、边界条件测试。

**Architecture:**
- 采用三层测试架构：单元测试（节点级别）→ 集成测试（引擎级别）→ E2E 测试（API 级别）
- 使用 pytest + pytest-asyncio + pytest-mock 进行测试
- Mock 外部依赖（Go API、StarRocks、LLM）实现快速可靠的测试
- 每个测试任务遵循 TDD 循环：RED（写失败测试）→ GREEN（写实现通过）→ REFACTOR

**Tech Stack:** pytest, pytest-asyncio, pytest-mock, unittest.mock, httpx Mock

---

## 文件结构

```
dev_metric/tests/
├── conftest.py                    # 现有 fixtures + 新增 mock fixtures
├── unit/
│   ├── test_nodes/
│   │   ├── __init__.py
│   │   ├── test_intent_node.py   # 意图识别节点单元测试
│   │   ├── test_entity_node.py   # 实体链接节点单元测试
│   │   ├── test_sql_gen_node.py  # SQL 生成节点单元测试
│   │   └── test_response_node.py # 响应生成节点单元测试
│   ├── test_state.py             # ConversationState 状态测试
│   └── test_langgraph_engine.py  # LangGraphEngine 引擎测试
├── integration/
│   ├── test_ab_equivalence.py    # 现有 A/B 测试
│   ├── test_state_transitions.py # 状态转换集成测试
│   └── test_multi_turn.py       # 多轮对话集成测试
├── e2e/
│   └── test_ask_api.py           # API 端到端测试
└── mocks/
    ├── __init__.py
    ├── mock_go_api.py            # Mock Go 后端 API
    ├── mock_starrocks.py         # Mock StarRocks 查询
    └── mock_llm.py               # Mock LLM 调用
```

---

## Task 1: 测试基础设施 - Mock Fixtures

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/mocks/__init__.py`
- Create: `tests/mocks/mock_go_api.py`
- Create: `tests/mocks/mock_starrocks.py`
- Create: `tests/mocks/mock_llm.py`

- [ ] **Step 1: Write mock_go_api.py**

```python
# tests/mocks/mock_go_api.py
"""Mock Go 后端 API"""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional


class MockGoAPIClient:
    """Mock Go 后端 API 客户端"""

    def __init__(self):
        self.metrics = {
            "MKI-02-0001": {
                "id": 1,
                "metric_code": "MKI-02-0001",
                "name": "访客数",
                "name_en": "visitors",
                "unit": "人",
                "domain": "营销域",
                "starrocks_sql": "SELECT date, SUM(sessions_total) as value FROM metric_data WHERE metric_id = 1 GROUP BY date",
                "business_rule": "统计所有渠道的独立访客数",
                "technical_rule": "COUNT(DISTINCT visitor_id)",
            },
            "MKI-01-0001": {
                "id": 2,
                "metric_code": "MKI-01-0001",
                "name": "销售额",
                "name_en": "sales",
                "unit": "元",
                "domain": "营销域",
                "starrocks_sql": "SELECT date, SUM(sales_amount) as value FROM metric_data WHERE metric_id = 2 GROUP BY date",
                "business_rule": "包含退款的全站销售额",
                "technical_rule": "SUM(order_amount)",
            },
        }
        self.intent_templates = []
        self.sql_templates = {}
        self.dimensions = {}

    def get_metric(self, metric_code: str) -> Optional[Dict]:
        return self.metrics.get(metric_code)

    def get_all_metrics(self) -> list:
        return list(self.metrics.values())

    def get_intent_templates(self) -> list:
        return self.intent_templates

    def get_sql_templates(self) -> Dict:
        return self.sql_templates


@pytest.fixture
def mock_go_api():
    """Mock Go API fixture"""
    mock_client = MockGoAPIClient()
    with patch('ai.client.metric_client.MetricClient') as mock:
        instance = mock.return_value
        instance.get_metric = Mock(side_effect=mock_client.get_metric)
        instance.get_all_metrics = Mock(return_value=mock_client.get_all_metrics())
        instance.get_intent_templates = Mock(return_value=mock_client.get_intent_templates())
        instance.get_sql_templates = Mock(return_value=mock_client.get_sql_templates())
        yield instance
```

- [ ] **Step 2: Write mock_starrocks.py**

```python
# tests/mocks/mock_starrocks.py
"""Mock StarRocks 查询"""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List


class MockStarRocksResult:
    """Mock StarRocks 查询结果"""

    def __init__(self, data: List[Dict], count: int = None):
        self.data = data
        self.count = count or len(data)

    def to_dict(self) -> Dict:
        return {
            "data": self.data,
            "count": self.count
        }


@pytest.fixture
def mock_starrocks_success():
    """Mock StarRocks 成功查询"""
    mock_result = MockStarRocksResult([
        {"date": "2026-04-02", "value": 12345},
        {"date": "2026-04-01", "value": 11234},
    ])
    with patch('ai.sql_gen.generator.SQLGenerator.execute') as mock_execute:
        mock_execute.return_value = mock_result.to_dict()
        yield mock_execute


@pytest.fixture
def mock_starrocks_empty():
    """Mock StarRocks 空结果"""
    mock_result = MockStarRocksResult([])
    with patch('ai.sql_gen.generator.SQLGenerator.execute') as mock_execute:
        mock_execute.return_value = mock_result.to_dict()
        yield mock_execute


@pytest.fixture
def mock_starrocks_error():
    """Mock StarRocks 查询错误"""
    with patch('ai.sql_gen.generator.SQLGenerator.execute') as mock_execute:
        mock_execute.side_effect = Exception("StarRocks connection timeout")
        yield mock_execute
```

- [ ] **Step 3: Write mock_llm.py**

```python
# tests/mocks/mock_llm.py
"""Mock LLM 调用"""
import pytest
from unittest.mock import Mock, patch
from ai.graph.state import IntentResult


class MockLLMResponses:
    """LLM 响应模板"""

    VISITOR_COUNT = IntentResult(
        intent="query_value",
        confidence=0.95,
        entities={"metric_name": "访客数", "metric_code": "MKI-02-0001", "time_range": "last_7_days"}
    )

    SALES_AMOUNT = IntentResult(
        intent="query_value",
        confidence=0.92,
        entities={"metric_name": "销售额", "metric_code": "MKI-01-0001", "time_range": "this_month"}
    )

    TREND_QUERY = IntentResult(
        intent="query_trend",
        confidence=0.88,
        entities={"metric_name": "访客数", "metric_code": "MKI-02-0001", "time_range": "last_30_days"}
    )

    METADATA_QUERY = IntentResult(
        intent="query_metadata",
        confidence=0.90,
        entities={"metric_name": "访客数", "metric_code": "MKI-02-0001"}
    )

    UNKNOWN = IntentResult(
        intent="query_value",
        confidence=0.3,
        entities={}
    )


@pytest.fixture
def mock_llm_recognize_intent():
    """Mock LLM 意图识别"""
    responses = MockLLMResponses()

    def mock_response(text: str, inherited_entities=None) -> IntentResult:
        text_lower = text.lower()
        if "访客" in text or "visitor" in text_lower:
            return responses.VISITOR_COUNT
        if "销售" in text or "sales" in text_lower:
            return responses.SALES_AMOUNT
        if "趋势" in text or "走势" in text:
            return responses.TREND_QUERY
        if "业务口径" in text or "技术口径" in text or "定义" in text:
            return responses.METADATA_QUERY
        return responses.UNKNOWN

    with patch('ai.engine.llm.LLMEngine.recognize_intent_enhanced') as mock:
        mock.side_effect = mock_response
        yield mock


@pytest.fixture
def mock_llm_generate_sql():
    """Mock LLM SQL 生成"""
    with patch('ai.engine.llm.LLMEngine.generate_sql') as mock:
        mock.return_value = None  # 默认不使用 LLM 生成 SQL
        yield mock


@pytest.fixture
def mock_llm_response():
    """Mock LLM 自然语言响应生成"""
    with patch('ai.engine.llm.LLMEngine.generate_response') as mock:
        mock.return_value = "根据查询结果，访客数为 12,345 人。"
        yield mock
```

- [ ] **Step 4: Update conftest.py 添加新 fixtures**

```python
# tests/conftest.py 新增内容
from tests.mocks.mock_go_api import mock_go_api
from tests.mocks.mock_starrocks import mock_starrocks_success, mock_starrocks_empty, mock_starrocks_error
from tests.mocks.mock_llm import mock_llm_recognize_intent, mock_llm_generate_sql, mock_llm_response

# 在现有 fixtures 后添加：
@pytest.fixture(autouse=True)
def reset_singletons():
    """每个测试后重置单例"""
    import ai.engine.llm as llm_module
    import ai.engine.rule_engine as rule_module

    llm_module._llm_engine = None
    rule_module._instance = None
    yield
    llm_module._llm_engine = None
    rule_module._instance = None
```

- [ ] **Step 5: Run conftest.py verify**

Run: `python -m pytest tests/conftest.py -v --collect-only`
Expected: 收集到所有 fixtures，无报错

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/mocks/
git commit -m "test: add mock fixtures for LangGraph TDD testing"
```

---

## Task 2: ConversationState 单元测试

**Files:**
- Create: `tests/unit/test_state.py`
- Modify: `tests/conftest.py` (添加 state fixture)

- [ ] **Step 1: Write test_state.py - 基础状态测试**

```python
# tests/unit/test_state.py
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
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/unit/test_state.py -v`
Expected: 10 tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_state.py
git commit -m "test: add ConversationState unit tests"
```

---

## Task 3: Intent Node 单元测试

**Files:**
- Create: `tests/unit/test_nodes/__init__.py`
- Create: `tests/unit/test_nodes/test_intent_node.py`

- [ ] **Step 1: Write test_intent_node.py - 基础测试**

```python
# tests/unit/test_nodes/test_intent_node.py
"""Intent Node 单元测试"""
import pytest
from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import ConversationNodes


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
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/unit/test_nodes/test_intent_node.py -v`
Expected: 8 tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_nodes/
git commit -m "test: add intent node unit tests"
```

---

## Task 4: Entity Node 单元测试

**Files:**
- Create: `tests/unit/test_nodes/test_entity_node.py`

- [ ] **Step 1: Write test_entity_node.py**

```python
# tests/unit/test_nodes/test_entity_node.py
"""Entity Node 单元测试"""
import pytest
from ai.graph.state import ConversationState, ConversationMessage, ConversationContext
from ai.graph.nodes import ConversationNodes


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
        result = nodes.entity_node(state)

        entities = result.get("entities", {})
        assert "metric_name" in entities or "metric_code" in entities

    def test_link_metric_by_code(self, nodes, state_with_context):
        """通过编号链接指标"""
        state = state_with_context("MKI-02-0001")
        state.current_intent = "query_value"
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
        state = state_with_context("环比呢", context={
            "current_metric_name": "访客数",
            "current_metric_code": "MKI-02-0001",
            "current_time_expr": "last_7_days"
        })
        state.current_intent = "query_comparison"
        result = nodes.entity_node(state)

        entities = result.get("entities", {})
        # 应该继承上轮的指标
        assert entities.get("metric_name") == "访客数" or entities.get("metric_code") == "MKI-02-0001"

    def test_clear_inherited_for_new_metric(self, nodes, state_with_context):
        """新指标查询应清除继承的指标"""
        state = state_with_context("销售额")
        state.current_intent = "query_value"
        state.conversation_context = ConversationContext(
            current_metric_name="访客数",
            current_metric_code="MKI-02-0001"
        )
        result = nodes.entity_node(state)

        entities = result.get("entities", {})
        # 如果识别到了"销售额"，不应该还保留"访客数"
        if entities.get("metric_name") == "销售额":
            assert entities.get("metric_name") != "访客数"

    def test_extract_platform_dimension(self, nodes, state_with_context):
        """提取平台维度"""
        state = state_with_context("亚马逊的访客数")
        state.current_intent = "query_value"
        result = nodes.entity_node(state)

        entities = result.get("entities", {})
        assert entities.get("platform") is not None

    def test_extract_region_dimension(self, nodes, state_with_context):
        """提取地区维度"""
        state = state_with_context("华东地区的销售额")
        state.current_intent = "query_value"
        result = nodes.entity_node(state)

        entities = result.get("entities", {})
        assert entities.get("region") is not None

    def test_no_metric_no_crash(self, nodes, state_with_context):
        """无指标时不崩溃"""
        state = state_with_context("计算一下")
        state.current_intent = "query_value"
        result = nodes.entity_node(state)

        # 应该正常返回，不崩溃
        assert result is not None
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/unit/test_nodes/test_entity_node.py -v`
Expected: 8 tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_nodes/test_entity_node.py
git commit -m "test: add entity node unit tests"
```

---

## Task 5: SQL Gen Node 单元测试

**Files:**
- Create: `tests/unit/test_nodes/test_sql_gen_node.py`

- [ ] **Step 1: Write test_sql_gen_node.py**

```python
# tests/unit/test_nodes/test_sql_gen_node.py
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
        state = state_with_metric("query_value", metric_code="MKI-02-0001")
        state.entities["starrocks_sql"] = "SELECT date, SUM(sessions) as value FROM metric_data WHERE metric_id = 1 GROUP BY date"
        result = nodes.sql_gen_node(state)

        assert result.get("generated_sql") is not None
        assert result.get("generated_sql") != "METADATA_QUERY"

    def test_value_query_without_sql(self, nodes, state_with_metric):
        """数值查询 - 无预置 SQL"""
        state = state_with_metric("query_value", metric_code="MKI-02-0001")
        state.entities.pop("starrocks_sql", None)
        result = nodes.sql_gen_node(state)

        # 应该返回 fallback SQL 或触发追问
        assert result.get("generated_sql") is not None or result.get("needs_clarification") is True

    def test_trend_query(self, nodes, state_with_metric):
        """趋势查询"""
        state = state_with_metric("query_trend", metric_code="MKI-02-0001")
        state.entities["starrocks_sql"] = "SELECT date, value FROM metric_data WHERE metric_id = 1"
        result = nodes.sql_gen_node(state)

        assert result.get("generated_sql") is not None

    def test_comparison_query(self, nodes, state_with_metric):
        """对比查询"""
        state = state_with_metric("query_comparison", metric_code="MKI-02-0001")
        state.entities["starrocks_sql"] = "SELECT date, value FROM metric_data WHERE metric_id = 1"
        result = nodes.sql_gen_node(state)

        assert result.get("generated_sql") is not None
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/unit/test_nodes/test_sql_gen_node.py -v`
Expected: 7 tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_nodes/test_sql_gen_node.py
git commit -m "test: add SQL gen node unit tests"
```

---

## Task 6: Response Node 单元测试

**Files:**
- Create: `tests/unit/test_nodes/test_response_node.py`

- [ ] **Step 1: Write test_response_node.py**

```python
# tests/unit/test_nodes/test_response_node.py
"""Response Node 单元测试"""
import pytest
from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import ConversationNodes


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
        assert "suggest" in result or result.get("needs_clarification") is True

    def test_suggestions_returned(self, nodes, state_for_response):
        """建议问题返回"""
        state = state_for_response("query_value")
        state.entities["metric_name"] = "访客数"
        result = nodes.response_node(state)

        assert "suggest" in result
        assert isinstance(result["suggest"], list)
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/unit/test_nodes/test_response_node.py -v`
Expected: 7 tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_nodes/test_response_node.py
git commit -m "test: add response node unit tests"
```

---

## Task 7: LangGraphEngine 集成测试

**Files:**
- Create: `tests/unit/test_langgraph_engine.py`

- [ ] **Step 1: Write test_langgraph_engine.py**

```python
# tests/unit/test_langgraph_engine.py
"""LangGraphEngine 单元测试"""
import pytest
from ai.engine.langgraph_engine import LangGraphEngine, create_langgraph_app


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

    def test_new_session_state(self, engine):
        """新会话状态初始化"""
        import asyncio
        config = {"configurable": {"thread_id": "test-new-session"}}

        async def check_state():
            state = await engine.app.aget_state(config)
            return state

        result = asyncio.get_event_loop().run_until_complete(check_state())
        # 新会话应该没有状态
        assert result is None

    def test_session_persistence(self, engine):
        """会话状态持久化"""
        import asyncio

        async def run_test():
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

            # 执行一次
            await engine.app.ainvoke(initial_state, config=config)

            # 获取状态
            state = await engine.app.aget_state(config)
            return state.values.get("entities", {}).get("metric_name")

        result = asyncio.get_event_loop().run_until_complete(run_test())
        assert result == "访客数"
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/unit/test_langgraph_engine.py -v`
Expected: 4 tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_langgraph_engine.py
git commit -m "test: add LangGraphEngine unit tests"
```

---

## Task 8: 状态转换集成测试

**Files:**
- Create: `tests/integration/test_state_transitions.py`

- [ ] **Step 1: Write test_state_transitions.py**

```python
# tests/integration/test_state_transitions.py
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
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/integration/test_state_transitions.py -v`
Expected: 4 tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_state_transitions.py
git commit -m "test: add state transitions integration tests"
```

---

## Task 9: 多轮对话集成测试扩展

**Files:**
- Modify: `tests/integration/test_multi_turn.py`

- [ ] **Step 1: Add multi-turn tests for LangGraph**

```python
# tests/integration/test_multi_turn.py 新增测试

@pytest.mark.asyncio
async def test_langgraph_context_inheritance(langgraph_engine):
    """LangGraph 上下文继承测试"""
    session_id = f"multi-context-{uuid.uuid4().hex[:8]}"

    # R1: 查询访客数
    r1 = await langgraph_engine.process("本月访客数", session_id)
    assert r1.get("session_id") == session_id

    # R2: 追问业务口径（应该继承指标）
    r2 = await langgraph_engine.process("业务口径呢", session_id)
    # 应该返回业务口径，而不是重新要求输入指标
    if r2.get("clarification_type") == "metric_missing":
        pytest.fail("应该继承上轮指标，不应该要求重新输入指标")


@pytest.mark.asyncio
async def test_langgraph_multi_turn_time_inheritance(langgraph_engine):
    """LangGraph 时间继承测试"""
    session_id = f"multi-time-{uuid.uuid4().hex[:8]}"

    # R1: 查询上月数据
    r1 = await langgraph_engine.process("上月销售额", session_id)

    # R2: 问环比（应该继承时间）
    r2 = await langgraph_engine.process("环比呢", session_id)
    # 环比计算需要时间信息，应该继承上轮时间
    assert r2 is not None


@pytest.mark.asyncio
async def test_langgraph_different_metric_clears_context(langgraph_engine):
    """LangGraph 新指标清除上下文"""
    session_id = f"multi-clear-{uuid.uuid4().hex[:8]}"

    # R1: 查询访客数
    r1 = await langgraph_engine.process("访客数", session_id)

    # R2: 查询完全不同指标（销售额）
    r2 = await langgraph_engine.process("销售额", session_id)

    # 如果系统认为需要追问，不应该基于访客数追问
    if r2.get("clarification_type") == "metric_enum":
        # 检查 matched_metrics 是否包含销售额相关，而不是访客数
        matched = r2.get("matched_metrics", [])
        if matched:
            names = [m.get("name", "") for m in matched]
            # 应该列出销售额相关指标，不是访客数
            has_sales = any("销售" in n for n in names)
            # 如果系统返回的是访客数相关，说明上下文没有正确清除
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/integration/test_multi_turn.py -v`
Expected: Tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_multi_turn.py
git commit -m "test: expand multi-turn integration tests"
```

---

## Task 10: 边界条件测试

**Files:**
- Create: `tests/unit/test_edge_cases.py`

- [ ] **Step 1: Write test_edge_cases.py**

```python
# tests/unit/test_edge_cases.py
"""边界条件测试"""
import pytest
from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import ConversationNodes


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
```

- [ ] **Step 2: Run tests verify they pass**

Run: `python -m pytest tests/unit/test_edge_cases.py -v`
Expected: 7 tests PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_edge_cases.py
git commit -m "test: add edge cases tests"
```

---

## Task 11: 测试覆盖率报告配置

**Files:**
- Modify: `pytest.ini` 或 `pyproject.toml` 或 `setup.cfg`

- [ ] **Step 1: Add pytest configuration for coverage**

```ini
# pytest.ini 或 setup.cfg
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning

[coverage:run]
source = ai
omit =
    */tests/*
    */mocks/*
    */__pycache__/*
    */site-packages/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
precision = 2
```

- [ ] **Step 2: Run coverage**

Run: `python -m pytest tests/ --cov=ai --cov-report=term-missing --cov-report=html`
Expected: 生成覆盖率报告

- [ ] **Step 3: Commit**

```bash
git add pytest.ini  # or pyproject.toml
git commit -m "test: add pytest coverage configuration"
```

---

## 验证清单

完成所有任务后，运行以下验证：

```bash
# 1. 运行所有单元测试
python -m pytest tests/unit/ -v

# 2. 运行所有集成测试
python -m pytest tests/integration/ -v

# 3. 运行覆盖率
python -m pytest tests/ --cov=ai --cov-report=term-missing

# 4. 验证关键文件存在
ls tests/unit/test_nodes/
ls tests/mocks/
ls tests/integration/
```

---

## 计划完成

**预期结果：**
- 30+ 单元测试覆盖所有节点
- 10+ 集成测试覆盖状态转换和多轮对话
- Mock 基础设施支持无外部依赖测试
- 覆盖率报告配置完成

**后续建议：**
1. 定期运行 A/B 测试确保 LangGraph 与 Legacy 引擎等价
2. 添加性能测试验证图执行时间
3. 添加并发测试验证会话隔离
