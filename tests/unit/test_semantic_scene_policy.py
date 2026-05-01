from ai.services.semantic_snapshot_service import SemanticSnapshotService


def test_get_scene_keywords_reads_interaction_policy():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "interaction_policies": {
            "comparison": {
                "policy": {
                    "keywords": ["compare-metrics", "cross-site"],
                }
            },
            "generic_query": {
                "policy": {
                    "core_metrics": ["gmv", "orders"],
                    "drilldown_categories": {
                        "sales": ["sales-deep-dive"],
                    },
                }
            },
        }
    }

    assert service.get_scene_keywords("comparison", ["fallback"]) == ["compare-metrics", "cross-site"]
    assert service.get_scene_core_metrics("generic_query", ["fallback"]) == ["gmv", "orders"]
    assert service.get_scene_drilldown_categories("generic_query", {"fallback": ["x"]}) == {
        "sales": ["sales-deep-dive"],
    }
