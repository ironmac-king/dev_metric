import pytest

from ai.engine.llm_v2.nodes.result_analyzer import ResultAnalyzer
from ai.engine.llm_v2.schema import MQLIntent, MQLMetric, MQLSchema, SQLResult, TimeRange, TimeType


class FakeLLMEngine:
    def call(self, *args, **kwargs):
        raise AssertionError("LLM should not be called in this test")


class FakeSemanticService:
    def recommend_next_questions(self, mql, scene_type):
        return ["查看本月各二级品类销售额变化", "查看本月销售额同比变化"]

    def get_active_snapshot(self):
        return None


@pytest.mark.asyncio
async def test_result_analyzer_prefers_semantic_suggestions(monkeypatch):
    monkeypatch.setattr("ai.engine.llm_v2.nodes.result_analyzer.get_llm_engine", lambda: FakeLLMEngine())

    analyzer = ResultAnalyzer()
    analyzer._semantic_service = FakeSemanticService()

    mql = MQLSchema(
        intent=MQLIntent.QUERY_VALUE,
        metric=MQLMetric(code="M1", name="销售额", unit="元"),
        time=TimeRange(type=TimeType.RELATIVE, original="本月"),
    )
    sql_result = SQLResult(sql="SELECT 1", data=[{"销售额": 12345}], columns=["销售额"], total=1, executed=True)

    result = await analyzer.analyze(mql, sql_result, "本月销售额")

    assert "查看本月各二级品类销售额变化" in result["suggestions"]
    assert "查看本月销售额同比变化" in result["suggestions"]


class FakeSemanticServiceWithSnapshot:
    def recommend_next_questions(self, mql, scene_type):
        return []

    def get_active_snapshot(self):
        return {
            "capabilities": {
                "metric:M1": {
                    "supports_yoy": True,
                    "supports_mom": True,
                    "supports_trend": False,
                    "supports_comparison": False,
                    "supports_ranking": False,
                    "supports_ratio": False,
                    "supports_attribution": False,
                    "supports_drilldown": False,
                }
            }
        }


@pytest.mark.asyncio
async def test_supplementary_info_returns_yoy_when_supported(monkeypatch):
    monkeypatch.setattr("ai.engine.llm_v2.nodes.result_analyzer.get_llm_engine", lambda: FakeLLMEngine())

    analyzer = ResultAnalyzer()
    analyzer._semantic_service = FakeSemanticServiceWithSnapshot()

    mql = MQLSchema(
        intent=MQLIntent.QUERY_VALUE,
        metric=MQLMetric(code="M1", name="销售额", unit="元"),
        time=TimeRange(type=TimeType.RELATIVE, original="本月"),
    )
    sql_result = SQLResult(
        sql="SELECT 1",
        data=[{"销售额": 12345, "yoy_change": "+12.3%"}],
        columns=["销售额", "yoy_change"],
        total=1,
        executed=True,
    )

    result = await analyzer.analyze(mql, sql_result, "本月销售额")

    # M1 supports_yoy=True, so supplementary_info should contain 同比
    supplementary = result.get("supplementary_info", [])
    labels = [item["label"] for item in supplementary]
    assert "同比" in labels
    yoy_item = next(item for item in supplementary if item["label"] == "同比")
    assert yoy_item["value"] == "+12.3%"
    assert yoy_item["trend"] == "+"


@pytest.mark.asyncio
async def test_supplementary_info_empty_when_no_snapshot(monkeypatch):
    monkeypatch.setattr("ai.engine.llm_v2.nodes.result_analyzer.get_llm_engine", lambda: FakeLLMEngine())

    analyzer = ResultAnalyzer()
    analyzer._semantic_service = FakeSemanticService()

    mql = MQLSchema(
        intent=MQLIntent.QUERY_VALUE,
        metric=MQLMetric(code="M1", name="销售额", unit="元"),
        time=TimeRange(type=TimeType.RELATIVE, original="本月"),
    )
    sql_result = SQLResult(
        sql="SELECT 1",
        data=[{"销售额": 12345, "yoy_change": "+12.3%"}],
        columns=["销售额", "yoy_change"],
        total=1,
        executed=True,
    )

    result = await analyzer.analyze(mql, sql_result, "本月销售额")

    # No snapshot, so supplementary_info should be empty
    assert result.get("supplementary_info", []) == []


@pytest.mark.asyncio
async def test_supplementary_info_no_yoy_when_not_supported(monkeypatch):
    class FakeSemanticServiceNoYoY:
        def recommend_next_questions(self, mql, scene_type):
            return []

        def get_active_snapshot(self):
            return {
                "capabilities": {
                    "metric:M1": {
                        "supports_yoy": False,  # YoY not supported
                        "supports_mom": False,
                    }
                }
            }

    monkeypatch.setattr("ai.engine.llm_v2.nodes.result_analyzer.get_llm_engine", lambda: FakeLLMEngine())

    analyzer = ResultAnalyzer()
    analyzer._semantic_service = FakeSemanticServiceNoYoY()

    mql = MQLSchema(
        intent=MQLIntent.QUERY_VALUE,
        metric=MQLMetric(code="M1", name="销售额", unit="元"),
        time=TimeRange(type=TimeType.RELATIVE, original="本月"),
    )
    sql_result = SQLResult(
        sql="SELECT 1",
        data=[{"销售额": 12345, "yoy_change": "+12.3%"}],
        columns=["销售额", "yoy_change"],
        total=1,
        executed=True,
    )

    result = await analyzer.analyze(mql, sql_result, "本月销售额")

    # YoY not supported, so supplementary_info should not contain 同比
    supplementary = result.get("supplementary_info", [])
    labels = [item["label"] for item in supplementary]
    assert "同比" not in labels


@pytest.mark.asyncio
async def test_supplementary_info_returns_mom_when_supported(monkeypatch):
    class FakeSemanticServiceWithMoM:
        def recommend_next_questions(self, mql, scene_type):
            return []

        def get_active_snapshot(self):
            return {
                "capabilities": {
                    "metric:M1": {
                        "supports_yoy": False,
                        "supports_mom": True,
                    }
                }
            }

    monkeypatch.setattr("ai.engine.llm_v2.nodes.result_analyzer.get_llm_engine", lambda: FakeLLMEngine())

    analyzer = ResultAnalyzer()
    analyzer._semantic_service = FakeSemanticServiceWithMoM()

    mql = MQLSchema(
        intent=MQLIntent.QUERY_VALUE,
        metric=MQLMetric(code="M1", name="销售额", unit="元"),
        time=TimeRange(type=TimeType.RELATIVE, original="本月"),
    )
    sql_result = SQLResult(
        sql="SELECT 1",
        data=[{"销售额": 12345, "mom_change": "-5.2%"}],
        columns=["销售额", "mom_change"],
        total=1,
        executed=True,
    )

    result = await analyzer.analyze(mql, sql_result, "本月销售额")

    supplementary = result.get("supplementary_info", [])
    labels = [item["label"] for item in supplementary]
    assert "环比" in labels
    mom_item = next(item for item in supplementary if item["label"] == "环比")
    assert mom_item["value"] == "-5.2%"
    assert mom_item["trend"] == "-"
