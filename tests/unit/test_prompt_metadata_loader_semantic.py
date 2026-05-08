from ai.engine.prompt_metadata_loader import PromptMetadataLoader


def test_load_metrics_prefers_semantic_service():
    loader = PromptMetadataLoader()

    class FakeSemanticService:
        def get_metric_names(self):
            return ["gross_profit", "sales"]

    loader._semantic_service = FakeSemanticService()

    assert loader._load_metrics() == ["gross_profit", "sales"]


def test_load_dimensions_prefers_semantic_service():
    loader = PromptMetadataLoader()

    class FakeSemanticService:
        def get_dimension_mapping_pairs(self):
            return [{"name": "site", "code": "FSITE"}, {"name": "category_l2", "code": "GROUP_2"}]

    loader._semantic_service = FakeSemanticService()

    assert loader._load_dimensions() == [
        {"name": "site", "code": "FSITE"},
        {"name": "category_l2", "code": "GROUP_2"},
    ]


def test_build_metric_names_section_uses_semantic_metrics():
    loader = PromptMetadataLoader()

    class FakeSemanticService:
        def get_metric_names(self):
            return ["gross_profit", "sales"]

    loader._semantic_service = FakeSemanticService()

    assert loader.build_metric_names_section(max_count=10) == "gross_profit、sales（共2个）"


def test_build_dimension_mappings_section_uses_semantic_pairs():
    loader = PromptMetadataLoader()

    class FakeSemanticService:
        def get_dimension_mapping_pairs(self):
            return [{"name": "site", "code": "FSITE"}, {"name": "category_l2", "code": "GROUP_2"}]

    loader._semantic_service = FakeSemanticService()

    assert loader.build_dimension_mappings_section() == "site=FSITE、category_l2=GROUP_2"
