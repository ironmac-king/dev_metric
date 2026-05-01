from ai.engine.llm_v2.nodes.mql_generator import MQLGenerator


def test_get_dimension_values_context_prefers_semantic_service():
    generator = MQLGenerator()

    class FakeSemanticService:
        def get_dimension_values_context(self):
            return "  FSITE(site): amazon-us, amazon-uk"

    generator._semantic_service = FakeSemanticService()

    assert generator._get_dimension_values_context() == "  FSITE(site): amazon-us, amazon-uk"


def test_load_dimension_configs_prefers_semantic_service():
    generator = MQLGenerator()

    class FakeSemanticService:
        def get_dimension_name_to_code_map(self):
            return {"site": "FSITE", "category_l2": "GROUP_2"}

    generator._semantic_service = FakeSemanticService()
    generator._dimension_name_to_column = None

    generator._load_dimension_configs()

    assert generator._dimension_name_to_column == {"site": "FSITE", "category_l2": "GROUP_2"}


def test_get_synonym_context_prefers_semantic_service():
    generator = MQLGenerator()

    class FakeSemanticService:
        def get_dimension_synonym_context(self):
            return '【重要】以下用户词对应具体的数据库维度值，遇到这些词必须生成 filter：\n  us-store → filter={"field": "FSITE", "value": "amazon-us"}'

    generator._semantic_service = FakeSemanticService()

    assert "us-store" in generator._get_synonym_context()


def test_correct_category_level_uses_semantic_service():
    generator = MQLGenerator()

    class FakeSemanticService:
        def get_level_keywords(self):
            return {"L2 category": "GROUP_2"}

    generator._semantic_service = FakeSemanticService()

    assert generator._correct_category_level("GROUP_1", "show L2 category sales") == "GROUP_2"


def test_parse_mql_uses_semantic_fallback_map_for_dimensions():
    generator = MQLGenerator()
    generator._dimension_name_to_column = {}

    class FakeSemanticService:
        def get_dimension_fallback_map(self):
            return {"site": "FSITE"}

    generator._semantic_service = FakeSemanticService()
    generator._get_dimension_keywords_list = lambda: []
    generator._load_business_terms = lambda: ({}, set())

    mql = generator._parse_mql(
        {
            "intent": "query_value",
            "confidence": 0.91,
            "metric": {"name": "sales"},
            "dimensions": [{"type": "site", "value": None}],
            "filters": [],
        },
        "show sales by site",
    )

    assert [item.type for item in mql.dimensions] == ["FSITE"]


def test_load_business_terms_prefers_semantic_service():
    generator = MQLGenerator()

    class FakeSemanticService:
        def get_business_term_maps(self):
            return ({"us-store": "amazon-us"}, {"us-store", "amazon-us"})

    generator._semantic_service = FakeSemanticService()

    synonym_map, valid_values = generator._load_business_terms()

    assert synonym_map == {"us-store": "amazon-us"}
    assert valid_values == {"us-store", "amazon-us"}


def test_fill_defaults_injects_comparison_from_semantic_service():
    generator = MQLGenerator()

    class FakeSemanticService:
        def build_default_comparison_spec(self, question, metric_code="", metric_name="", scene_type="comparison"):
            assert question == "sales对比"
            assert metric_name == "sales"
            return {
                "enabled": True,
                "types": ["同比"],
            }

    generator._semantic_service = FakeSemanticService()

    from ai.engine.llm_v2.schema import MQLIntent, MQLMetric, MQLSchema

    mql = MQLSchema(
        intent=MQLIntent.QUERY_COMPARISON,
        metric=MQLMetric(name="sales"),
    )
    mql.original_question = "sales对比"

    generator._fill_defaults(mql, None)

    assert mql.comparison is not None
    assert mql.comparison.enabled is True
    assert mql.comparison.types == ["同比"]
