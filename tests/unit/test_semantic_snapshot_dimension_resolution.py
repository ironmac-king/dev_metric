from ai.services.semantic_snapshot_service import SemanticSnapshotService


def test_resolve_dimension_uses_term_index_for_generic_dimension_alias():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "dimensions": {
            "FSITE": {
                "display_name": "site",
            }
        },
        "term_index": {
            "site": {
                "synonyms": ["shop"],
                "dimension_field": "FSITE",
                "dimension_value": "site",
            }
        },
    }

    dimension = service.resolve_dimension("shop")

    assert dimension == {
        "column_name": "FSITE",
        "dimension_value": None,
        "is_generic": True,
        "dimension_type": "site",
    }


def test_search_dimension_values_uses_term_index_for_concrete_dimension_value():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "dimensions": {
            "FSITE": {
                "display_name": "site",
            }
        },
        "term_index": {
            "amazon-us": {
                "synonyms": ["us-store"],
                "dimension_field": "FSITE",
                "dimension_value": "amazon-us",
            }
        },
    }

    results = service.search_dimension_values("us-store", limit=5)

    assert results == [
        {
            "column_name": "FSITE",
            "dimension_type": "site",
            "dimension_value": "amazon-us",
            "match_type": "semantic_term",
        }
    ]


def test_get_business_term_maps_uses_term_index():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "term_index": {
            "amazon-us": {
                "synonyms": ["us-store", "usa-shop"],
                "dimension_field": "FSITE",
                "dimension_value": "amazon-us",
            }
        }
    }

    synonym_map, valid_values = service.get_business_term_maps()

    assert synonym_map["amazon-us"] == "amazon-us"
    assert synonym_map["us-store"] == "amazon-us"
    assert "usa-shop" in valid_values
