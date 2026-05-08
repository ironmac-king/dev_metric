from ai.engine.llm_v2.schema import MQLDimension, MQLIntent, MQLMetric, MQLSchema, TimeRange, TimeType
from ai.services.semantic_snapshot_service import SemanticSnapshotService


def test_recommend_next_questions_uses_metric_and_dimension_semantics():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "metrics": {
            "M1": {
                "display_name": "销售额",
                "recommended_dimension_codes": ["FSITE", "GROUP_2"],
                "preferred_followups": ["查看销售额趋势", "查看销售额同比变化"],
            }
        },
        "dimensions": {
            "FSITE": {"display_name": "站点"},
            "GROUP_2": {"display_name": "二级品类"},
        },
        "capabilities": {
            "metric:M1": {
                "supports_trend": True,
                "supports_comparison": True,
                "supports_yoy": True,
                "supports_mom": True,
            }
        },
        "interaction_policies": {
            "simple_query": {
                "scene_type": "simple_query",
                "max_suggestions": 3,
            }
        },
    }

    mql = MQLSchema(
        intent=MQLIntent.QUERY_VALUE,
        metric=MQLMetric(code="M1", name="销售额"),
        dimensions=[MQLDimension(type="站点", column="FSITE")],
        time=TimeRange(type=TimeType.RELATIVE, original="本月"),
    )

    suggestions = service.recommend_next_questions(mql, scene_type="simple_query")

    assert suggestions
    assert all("站点" not in s for s in suggestions)
    assert any("二级品类" in s for s in suggestions)
    assert len(suggestions) <= 3


def test_recommend_actions_prefers_semantic_snapshot_actions():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "actions": {
            "view_sales": {
                "label": "看销售",
                "source_scene_type": "analysis",
                "target_scene_type": "drilldown",
                "target_payload_template": {"question": "__DRILLDOWN__:sales__"},
                "priority": 100,
            },
            "view_ad": {
                "label": "看广告",
                "source_scene_type": "analysis",
                "target_scene_type": "drilldown",
                "target_payload_template": {"question": "__DRILLDOWN__:ad__"},
                "priority": 90,
            },
        }
    }

    actions = service.recommend_actions("comparison", target_scene_type="drilldown")

    assert actions == [
        {"label": "看销售", "action": "drilldown", "params": {"question": "__DRILLDOWN__:sales__"}},
        {"label": "看广告", "action": "drilldown", "params": {"question": "__DRILLDOWN__:ad__"}},
    ]


def test_resolve_metric_prefers_metric_aliases():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "metrics": {
            "M_GROSS_PROFIT": {
                "display_name": "毛利",
            }
        },
        "metric_aliases": {
            "毛利": "M_GROSS_PROFIT",
            "gross profit": "M_GROSS_PROFIT",
        },
    }

    metric = service.resolve_metric("毛利")

    assert metric == {
        "metric_code": "M_GROSS_PROFIT",
        "name": "毛利",
        "code": "M_GROSS_PROFIT",
    }


def test_search_dimension_values_uses_snapshot_dimension_values_without_dimension_service(monkeypatch):
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "dimensions": {
            "FSITE": {"display_name": "站点"},
        },
        "dimension_values": {
            "FSITE": [
                {"dimension_value": "amazon-us", "dimension_type": "站点", "frequency": 10},
                {"dimension_value": "amazon-uk", "dimension_type": "站点", "frequency": 5},
            ]
        },
        "term_index": {},
    }

    monkeypatch.setattr(
        service,
        "_get_dimension_service",
        lambda: (_ for _ in ()).throw(AssertionError("dimension service should not be used")),
        raising=True,
    )

    results = service.search_dimension_values("amazon", limit=10)

    assert [item["dimension_value"] for item in results] == ["amazon-us", "amazon-uk"]
    assert all(item["column_name"] == "FSITE" for item in results)


def test_get_dimension_values_context_reads_snapshot_only(monkeypatch):
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "dimensions": {
            "FSITE": {"display_name": "站点"},
        },
        "dimension_values": {
            "FSITE": [
                {"dimension_value": "amazon-us", "dimension_type": "站点", "frequency": 10},
                {"dimension_value": "amazon-uk", "dimension_type": "站点", "frequency": 5},
            ]
        },
        "term_index": {},
    }

    monkeypatch.setattr(
        service,
        "_get_dimension_service",
        lambda: (_ for _ in ()).throw(AssertionError("dimension service should not be used")),
        raising=True,
    )

    context = service.get_dimension_values_context(["FSITE"])

    assert "FSITE(站点): amazon-us, amazon-uk" in context
