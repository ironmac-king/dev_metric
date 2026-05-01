import pytest

from ai.engine.llm_v2.nodes.result_analyzer import ResultAnalyzer
from ai.engine.llm_v2.schema import MQLIntent, MQLMetric, MQLSchema, SQLResult, TimeRange, TimeType


class FakeLLMEngine:
    def call(self, *args, **kwargs):
        raise AssertionError("LLM should not be called in this test")


class FakeSemanticService:
    def recommend_next_questions(self, mql, scene_type):
        return ["查看本月各二级品类销售额变化", "查看本月销售额同比变化"]


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

    assert result["suggestions"] == ["查看本月各二级品类销售额变化", "查看本月销售额同比变化"]
