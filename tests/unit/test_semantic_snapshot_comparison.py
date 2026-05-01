from ai.services.semantic_snapshot_service import SemanticSnapshotService


def test_build_default_comparison_spec_prefers_policy_and_capability():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "metrics": {
            "M1": {
                "display_name": "sales",
            }
        },
        "metric_aliases": {
            "sales": "M1",
        },
        "capabilities": {
            "metric:M1": {
                "supports_comparison": True,
                "supports_yoy": True,
                "supports_mom": False,
            }
        },
        "interaction_policies": {
            "comparison": {
                "policy": {
                    "default_comparison_type": "同比",
                }
            }
        },
    }

    comparison = service.build_default_comparison_spec("sales对比", metric_name="sales")

    assert comparison == {
        "enabled": True,
        "types": ["同比"],
    }


def test_build_default_comparison_spec_honors_explicit_mom():
    service = SemanticSnapshotService()
    service._active_snapshot = {}

    comparison = service.build_default_comparison_spec("sales环比", metric_name="sales")

    assert comparison == {
        "enabled": True,
        "types": ["环比"],
    }


def test_resolve_action_matches_payload_question():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "actions": {
            "view_sales": {
                "label": "看销售",
                "source_scene_type": "analysis",
                "target_scene_type": "drilldown",
                "target_payload_template": {"question": "__DRILLDOWN__:sales__"},
                "priority": 100,
            }
        }
    }

    action = service.resolve_action(check="sales", scene_type="generic_query")

    assert action == {
        "label": "看销售",
        "action": "drilldown",
        "params": {"question": "__DRILLDOWN__:sales__"},
    }
