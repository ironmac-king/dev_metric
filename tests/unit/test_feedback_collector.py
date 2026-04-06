"""
单元测试: FeedbackCollector JSON 序列化修复验证
"""
import pytest
import json
from ai.feedback.collector import FeedbackRecord, FeedbackType, FeedbackSource


def test_feedback_record_to_dict():
    """验证 FeedbackRecord.to_dict() 正确序列化"""
    record = FeedbackRecord(
        session_id="test-123",
        turn_index=1,
        feedback_source=FeedbackSource.AUTO.value,
        feedback=FeedbackType.NO_FEEDBACK.value,
        fail_reason="test_reason",
        clarification_type="metric_enum",
        clarification_question="请确认指标",
        metric_id=1,
        created_at="2026-04-03T00:00:00"
    )

    d = record.to_dict()

    # 验证基本字段
    assert d["session_id"] == "test-123"
    assert d["turn_index"] == 1
    assert d["fail_reason"] == "test_reason"
    assert d["clarification_type"] == "metric_enum"
    assert d["clarification_question"] == "请确认指标"

    # 验证 context_snapshot 序列化为 JSON 字符串
    assert d["context_snapshot"] is None or isinstance(d["context_snapshot"], str)


def test_feedback_record_with_context_snapshot():
    """验证带 context_snapshot 的记录正确序列化"""
    record = FeedbackRecord(
        session_id="test-456",
        turn_index=2,
        feedback_source=FeedbackSource.AUTO.value,
        feedback=FeedbackType.NO_FEEDBACK.value,
        fail_reason="no_data",
        context_snapshot={
            "entities": {"metric_name": "销售额"},
            "current_intent": "query_value",
            "generated_sql": "SELECT SUM(...)"
        }
    )

    d = record.to_dict()

    # context_snapshot 应该是 JSON 字符串
    assert d["context_snapshot"] is not None
    assert isinstance(d["context_snapshot"], str)

    # 反序列化验证
    parsed = json.loads(d["context_snapshot"])
    assert parsed["entities"]["metric_name"] == "销售额"
    assert parsed["current_intent"] == "query_value"


def test_feedback_record_with_missing_fields():
    """验证带 missing_fields 的记录正确序列化"""
    record = FeedbackRecord(
        session_id="test-789",
        turn_index=3,
        feedback_source=FeedbackSource.AUTO.value,
        feedback=FeedbackType.NO_FEEDBACK.value,
        fail_reason="missing_field",
        missing_fields={
            "time_range": "last_7_days",
            "dimension": "category"
        }
    )

    d = record.to_dict()

    # missing_fields 应该是 JSON 字符串
    assert d["missing_fields"] is not None
    assert isinstance(d["missing_fields"], str)

    # 反序列化验证
    parsed = json.loads(d["missing_fields"])
    assert parsed["time_range"] == "last_7_days"
    assert parsed["dimension"] == "category"
