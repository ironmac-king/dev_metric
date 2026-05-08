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
