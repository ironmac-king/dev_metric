from ai.engine.llm_v2.nodes.intent_router import IntentRouter
from ai.engine.llm_v2.schema import MQLDimension, MQLSchema


def test_validate_generic_dimensions_uses_semantic_snapshot_service():
    router = IntentRouter()

    class FakeSemanticService:
        def get_all_types(self):
            return [{"column_name": "GROUP_2", "dimension_type": "category_l2"}]

        def find_dimension_column_by_type(self, candidate):
            return None

        def search_dimension_values(self, candidate, limit=10):
            if candidate == "cloud-storage":
                return [
                    {
                        "column_name": "GROUP_2",
                        "dimension_type": "category_l2",
                        "dimension_value": "cloud-storage",
                    }
                ]
            return []

    router._semantic_service = FakeSemanticService()

    mql = MQLSchema(dimensions=[MQLDimension(type="CATEGORY", value=None)])

    result = router._validate_generic_dimensions(mql, f"cloud-storage{chr(20170)}{chr(24180)}sales")

    assert result.dimensions[0].type == "category_l2"
    assert result.dimensions[0].column == "GROUP_2"
    assert result.dimensions[0].value == "cloud-storage"


def test_resolve_additional_dimensions_uses_semantic_generic_alias():
    router = IntentRouter()
    router._dimension_type_mappings = []

    class FakeSemanticService:
        def find_dimension_column_by_type(self, candidate):
            return None

        def resolve_dimension(self, candidate):
            if candidate == "shop":
                return {
                    "column_name": "FSITE",
                    "dimension_type": "site",
                    "dimension_value": None,
                    "is_generic": True,
                }
            return None

    router._semantic_service = FakeSemanticService()

    result = router._resolve_additional_dimensions("add shop", ["add"])

    assert result == [{"column_name": "FSITE", "label": "site"}]


def test_build_mql_from_local_converts_metric_entity_to_dimension_value():
    router = IntentRouter()

    class FakeSemanticService:
        def resolve_dimension(self, candidate):
            if candidate == "shop":
                return {
                    "column_name": "FSITE",
                    "dimension_type": "site",
                    "dimension_value": "shop",
                    "is_generic": False,
                }
            return None

    router._semantic_service = FakeSemanticService()

    result = router._build_mql_from_local(
        {
            "intent": "query_value",
            "confidence": 0.98,
            "entities": [{"text": "shop", "type": "METRIC"}],
            "match_success": True,
        },
        "shop",
    )

    assert result.metric is None
    assert [(item.type, item.column, item.value) for item in result.dimensions] == [("site", "FSITE", "shop")]


def test_build_mql_from_local_numeric_fallback_uses_semantic_service():
    router = IntentRouter()
    router._dimension_type_mappings = [{"dimension_name": "sku", "column_name": "SKU"}]

    class FakeSemanticService:
        def resolve_dimension(self, candidate):
            if candidate == "15719":
                return {
                    "column_name": "SKU",
                    "dimension_type": "sku",
                    "dimension_value": "15719",
                    "is_generic": False,
                }
            return None

    router._semantic_service = FakeSemanticService()

    result = router._build_mql_from_local(
        {
            "intent": "query_value",
            "confidence": 0.93,
            "entities": [{"text": "sales", "type": "METRIC"}],
            "match_success": True,
        },
        "sales 15719",
    )

    assert result.metric.name == "sales"
    assert [(item.type, item.column, item.value) for item in result.dimensions] == [("sku", "SKU", "15719")]
