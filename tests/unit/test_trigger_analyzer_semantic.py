import pytest

from ai.engine.llm_v2.nodes.trigger_analyzer import (
    AdEffectTrigger,
    ComparisonTrigger,
    ContextTrigger,
    GenericQueryTrigger,
    InventoryRiskTrigger,
    TriggerAnalyzer,
    VolatilityTrigger,
)
from ai.engine.llm_v2.schema import MQLMetric, MQLSchema


@pytest.mark.asyncio
async def test_generic_query_trigger_prefers_semantic_specific_action():
    trigger = GenericQueryTrigger()

    class FakeSemanticService:
        def resolve_action(self, check="", question="", scene_type="analysis", target_scene_type="drilldown"):
            if check == "sales" and scene_type == "generic_query":
                return {
                    "label": "看销售",
                    "action": "drilldown",
                    "params": {"question": "__DRILLDOWN__:sales__"},
                }
            return None

        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            return []

    trigger._semantic_service = FakeSemanticService()

    mql = MQLSchema(metric=MQLMetric(name="sales"))
    mql.original_question = "销售经营分析"

    result = await trigger.check(mql, {}, state=None)

    assert result.should_analyze is True
    assert result.drilldown_options == [
        {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}}
    ]
    assert "看销售" in result.trigger_reason


@pytest.mark.asyncio
async def test_generic_query_trigger_uses_semantic_drilldown_categories():
    trigger = GenericQueryTrigger()

    class FakeSemanticService:
        def get_scene_keywords(self, scene_type, fallback=None):
            return fallback or []

        def get_scene_core_metrics(self, scene_type, fallback=None):
            return fallback or []

        def get_scene_drilldown_categories(self, scene_type, fallback=None):
            if scene_type == "generic_query":
                return {"sales": ["sales-deep-dive"]}
            return fallback or {}

        def resolve_action(self, check="", question="", scene_type="analysis", target_scene_type="drilldown"):
            if check == "sales":
                return {
                    "label": "看销售",
                    "action": "drilldown",
                    "params": {"question": "__DRILLDOWN__:sales__"},
                }
            return None

        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            return []

    trigger._semantic_service = FakeSemanticService()

    mql = MQLSchema(metric=MQLMetric(name="sales"))
    mql.original_question = "sales-deep-dive"

    result = await trigger.check(mql, {}, state=None)

    assert result.should_analyze is True
    assert result.drilldown_options == [
        {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}}
    ]


@pytest.mark.asyncio
async def test_comparison_trigger_prefers_semantic_actions():
    trigger = ComparisonTrigger()

    class FakeSemanticService:
        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            if scene_type == "comparison":
                return [
                    {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}}
                ]
            return []

    trigger._semantic_service = FakeSemanticService()

    mql = MQLSchema(metric=MQLMetric(name="sales"))
    mql.original_question = "平台对比"
    sql_result = {"data": [{"platform": "A", "value": 1}, {"platform": "B", "value": 2}]}

    result = await trigger.check(mql, sql_result, state=None)

    assert result.should_analyze is True
    assert result.drilldown_options == [
        {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}}
    ]


@pytest.mark.asyncio
async def test_comparison_trigger_uses_semantic_keywords():
    trigger = ComparisonTrigger()

    class FakeSemanticService:
        def get_scene_keywords(self, scene_type, fallback=None):
            if scene_type == "comparison":
                return ["cross-site"]
            return fallback or []

        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            return []

    trigger._semantic_service = FakeSemanticService()

    mql = MQLSchema(metric=MQLMetric(name="sales"))
    mql.original_question = "cross-site"
    sql_result = {"data": [{"platform": "A", "value": 1}, {"platform": "B", "value": 2}]}

    result = await trigger.check(mql, sql_result, state=None)

    assert result.should_analyze is True


def test_trigger_analyzer_merges_primary_and_semantic_drilldowns():
    analyzer = TriggerAnalyzer()

    merged = analyzer._merge_drilldown_options(
        [
            {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}},
        ],
        [
            {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}},
            {"label": "看广告", "action": "drilldown", "params": {"question": "__DRILLDOWN__:ad__"}},
        ],
    )

    assert merged == [
        {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}},
        {"label": "看广告", "action": "drilldown", "params": {"question": "__DRILLDOWN__:ad__"}},
    ]


@pytest.mark.asyncio
async def test_ad_effect_trigger_prefers_semantic_actions():
    trigger = AdEffectTrigger()

    class FakeSemanticService:
        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            if scene_type == "ad_effect":
                return [
                    {"label": "看广告", "action": "drilldown", "params": {"question": "__DRILLDOWN__:ad__"}}
                ]
            return []

    trigger._semantic_service = FakeSemanticService()

    mql = MQLSchema(metric=MQLMetric(name="sales"))
    mql.original_question = "广告效果"

    result = await trigger.check(mql, {}, state=None)

    assert result.should_analyze is True
    assert result.drilldown_options == [
        {"label": "看广告", "action": "drilldown", "params": {"question": "__DRILLDOWN__:ad__"}}
    ]


@pytest.mark.asyncio
async def test_inventory_trigger_prefers_semantic_actions():
    trigger = InventoryRiskTrigger()

    class FakeSemanticService:
        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            if scene_type == "inventory_risk":
                return [
                    {"label": "看库存", "action": "drilldown", "params": {"question": "__DRILLDOWN__:inventory__"}}
                ]
            return []

    trigger._semantic_service = FakeSemanticService()

    result = await trigger.check(MQLSchema(), {"data": [{"inventory_days": 2}]}, state=None)

    assert result.should_analyze is True
    assert result.drilldown_options == [
        {"label": "看库存", "action": "drilldown", "params": {"question": "__DRILLDOWN__:inventory__"}}
    ]


@pytest.mark.asyncio
async def test_context_trigger_prefers_semantic_actions():
    trigger = ContextTrigger()

    class FakeSemanticService:
        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            if scene_type == "context_followup":
                return [
                    {"label": "按站点归因", "action": "drilldown", "params": {"question": "__DRILLDOWN__:site__"}}
                ]
            return []

    trigger._semantic_service = FakeSemanticService()

    mql = MQLSchema(metric=MQLMetric(name="sales"))
    mql.original_question = "为什么"

    result = await trigger.check(mql, {}, state={"last_query_type": "metric"})

    assert result.should_analyze is True
    assert result.drilldown_options == [
        {"label": "按站点归因", "action": "drilldown", "params": {"question": "__DRILLDOWN__:site__"}}
    ]


def test_volatility_trigger_uses_semantic_actions_when_no_affected_dimensions():
    trigger = VolatilityTrigger()

    class FakeSemanticService:
        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            if scene_type == "volatility":
                return [
                    {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}}
                ]
            return []

    trigger._semantic_service = FakeSemanticService()

    result = trigger._build_drilldowns([])

    assert result == [
        {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}}
    ]


def test_volatility_trigger_merges_dynamic_and_semantic_drilldowns():
    trigger = VolatilityTrigger()

    class FakeSemanticService:
        def recommend_actions(self, scene_type, target_scene_type="drilldown", limit=4):
            if scene_type == "volatility":
                return [
                    {"label": "看广告", "action": "drilldown", "params": {"question": "__DRILLDOWN__:ad__"}}
                ]
            return []

    trigger._semantic_service = FakeSemanticService()

    result = trigger._build_drilldowns([
        {"dimension": "US", "raw_value": "amazon-us"},
    ])

    assert result == [
        {"label": "🏪 US流量分析", "action": "drilldown", "params": {"dimension": "traffic", "site": "amazon-us"}},
        {"label": "📢 US广告效果", "action": "drilldown", "params": {"metric": "ad_roas", "site": "amazon-us"}},
        {"label": "看广告", "action": "drilldown", "params": {"question": "__DRILLDOWN__:ad__"}},
    ]
