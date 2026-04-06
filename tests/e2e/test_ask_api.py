"""
E2E 测试: API 层引擎切换
"""
import pytest
import requests
import uuid

BASE_URL = "http://localhost:8081"


def test_api_health():
    """验证 API 服务健康"""
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


@pytest.mark.parametrize("engine_type", ["legacy", "langgraph"])
def test_api_engine_switch(engine_type):
    """验证 API 支持 engine_type 参数切换引擎"""
    session_id = f"api-{uuid.uuid4().hex[:8]}"

    response = requests.post(
        f"{BASE_URL}/api/v1/ask",
        json={
            "question": "本月销售额是多少",
            "session_id": session_id,
            "engine_type": engine_type
        },
        timeout=30
    )

    assert response.status_code == 200, f"API 请求失败: {response.text}"
    data = response.json()

    assert "answer" in data, "响应缺少 answer 字段"
    assert data.get("answer") is not None, "answer 不应为 None"
    assert "session_id" in data, "响应缺少 session_id 字段"


def test_api_invalid_engine_fallback():
    """验证无效 engine_type 回退到 legacy"""
    session_id = f"api-{uuid.uuid4().hex[:8]}"

    response = requests.post(
        f"{BASE_URL}/api/v1/ask",
        json={
            "question": "本月销售额",
            "session_id": session_id,
            "engine_type": "invalid_engine"
        },
        timeout=30
    )

    assert response.status_code == 200, "无效 engine_type 应回退到 legacy"
    data = response.json()
    assert data.get("answer") is not None, "应返回有效回答"


def test_api_missing_session_id():
    """验证缺失 session_id 时自动生成"""
    response = requests.post(
        f"{BASE_URL}/api/v1/ask",
        json={
            "question": "本月销售额是多少"
        },
        timeout=30
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("session_id") is not None, "应自动生成 session_id"


def test_api_legacy_vs_langgraph_consistency():
    """验证 Legacy 和 LangGraph 引擎 API 输出一致"""
    question = "本月销售额是多少"

    r_leg = requests.post(
        f"{BASE_URL}/api/v1/ask",
        json={"question": question, "session_id": f"api-{uuid.uuid4().hex[:8]}", "engine_type": "legacy"},
        timeout=30
    )
    r_lg = requests.post(
        f"{BASE_URL}/api/v1/ask",
        json={"question": question, "session_id": f"api-{uuid.uuid4().hex[:8]}", "engine_type": "langgraph"},
        timeout=30
    )

    data_leg = r_leg.json()
    data_lg = r_lg.json()

    # 验证关键字段一致
    assert data_leg.get("clarification_type") == data_lg.get("clarification_type"), \
        "clarification_type 不一致"
    assert data_leg.get("needs_clarification") == data_lg.get("needs_clarification"), \
        "needs_clarification 不一致"
    assert data_leg.get("sql") == data_lg.get("sql"), \
        "sql 不一致"


def test_api_drill_down():
    """验证下钻 API 正常工作"""
    session_id = f"api-{uuid.uuid4().hex[:8]}"

    # 先查询基础 SQL
    r1 = requests.post(
        f"{BASE_URL}/api/v1/ask",
        json={"question": "本月销售额", "session_id": session_id, "engine_type": "legacy"},
        timeout=30
    )
    data1 = r1.json()
    sql = data1.get("sql")

    if sql:
        # 下钻
        r2 = requests.post(
            f"{BASE_URL}/api/v1/ask/drill_down",
            json={
                "session_id": session_id,
                "dimension_names": ["一级品类"],
                "metric_code": "SPI-05-065",
                "current_sql": sql,
                "page": 1,
                "page_size": 10
            },
            timeout=30
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert "answer" in data2
