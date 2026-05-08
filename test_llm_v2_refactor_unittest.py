import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.engine.llm_v2.schema import (
    ContextScope,
    MQLDimension,
    MQLIntent,
    MQLMetric,
    MQLSchema,
    TimeRange,
    TimeType,
    create_v2_state,
)
from ai.engine.llm_v2.nodes.intent_router import IntentRouter
from ai.engine.llm_v2.session_store import V2SessionStore
from ai.engine.llm_v2.nodes.state_manager import StateManager


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, _ttl, value):
        self.store[key] = value

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)

    def keys(self, pattern):
        if pattern == "v2:session:*":
            return list(self.store.keys())
        return []


class ContextScopeTests(unittest.TestCase):
    def test_context_scope_keeps_dict_style_compatibility(self):
        scope = ContextScope()

        scope["clarification_message"] = "请选择维度"
        scope["suggestions"] = ["看趋势"]
        scope["conversation_summary"] = {"original_turns": 3}

        self.assertEqual(scope.clarification_message, "请选择维度")
        self.assertEqual(scope.get("suggestions"), ["看趋势"])
        self.assertEqual(scope["conversation_summary"]["original_turns"], 3)
        self.assertEqual(scope.to_dict()["conversation_summary"]["original_turns"], 3)

    def test_metric_info_cache_is_no_longer_a_first_class_context_key(self):
        scope = ContextScope.from_dict({"metric_info_cache": {"metric_code": "M1"}})

        self.assertNotIn("metric_info_cache", ContextScope._KNOWN_KEYS)
        self.assertEqual(scope.get("metric_info_cache")["metric_code"], "M1")
        self.assertIn("metric_info_cache", scope.extras)

    def test_v2_state_serialization_exposes_first_class_internal_state(self):
        state = create_v2_state(session_id="session-serialize", user_id="user-1", question="销售额")
        state.session_state = {"is_followup": True}
        state.multi_metric_mode = True
        state.drilldown_category = "sales"
        state.conversation_summary = {"original_turns": 4}

        data = state.to_dict()

        self.assertEqual(data["session_state"]["is_followup"], True)
        self.assertEqual(data["multi_metric_mode"], True)
        self.assertEqual(data["drilldown_category"], "sales")
        self.assertEqual(data["conversation_summary"]["original_turns"], 4)

    def test_mqlschema_roundtrip_preserves_multi_metrics(self):
        original = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="MAIN", name="业绩"),
            metrics=[
                MQLMetric(code="M1", name="毛利"),
                MQLMetric(code="M2", name="广告花费"),
            ],
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
        )

        restored = MQLSchema.from_dict(original.to_dict())

        self.assertEqual(restored.metric.name, "业绩")
        self.assertEqual([m.name for m in restored.metrics], ["毛利", "广告花费"])

    def test_graph_and_router_stop_using_dict_style_for_known_context_scope_keys(self):
        files = [
            Path("ai/engine/llm_v2/graph.py"),
            Path("ai/engine/llm_v2/router.py"),
        ]
        forbidden_snippets = [
            'context_cache["drilldown_type"]',
            'context_cache["clarification_message"]',
            'context_cache["clarification_options"]',
            'context_cache["similar_cases"]',
            'context_cache["suggestions"]',
            'context_cache.get("drilldown_type"',
            'context_cache.get("clarification_message"',
            'context_cache.get("clarification_options"',
            'context_cache.get("similar_cases"',
            'context_cache.get("suggestions"',
            'context_cache.get("comparison_results"',
        ]

        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for snippet in forbidden_snippets:
            self.assertNotIn(snippet, combined)


class SessionStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_state_manager_and_session_store_share_durable_state(self):
        store = V2SessionStore(redis_client=FakeRedis(), ttl_seconds=60)
        manager = StateManager(session_store=store)

        state = create_v2_state(session_id="session-1", user_id="user-1", question="销售额")
        state.mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="M1", name="销售额"),
            time=TimeRange(original="近7天"),
        )
        state.conversation_summary = {"original_turns": 2, "last_metric": "销售额"}
        state.history_stack = [
            json.dumps(state.mql.to_dict(), ensure_ascii=False),
        ]

        await manager.update(state)

        inherited_mql = store.get_mql("session-1")
        restored_state = await manager.get_state("session-1")

        self.assertIsNotNone(inherited_mql)
        self.assertEqual(inherited_mql.metric.name, "销售额")
        self.assertIsNotNone(restored_state)
        self.assertEqual(restored_state.history_stack, state.history_stack)
        self.assertEqual(restored_state.conversation_summary["last_metric"], "销售额")
        self.assertIsNone(state.context_cache.get("conversation_summary"))
        self.assertIsNone(restored_state.context_cache.get("conversation_summary"))

    async def test_session_store_persists_summary_only_from_first_class_field(self):
        store = V2SessionStore(redis_client=FakeRedis(), ttl_seconds=60)
        state = create_v2_state(session_id="session-2", user_id="user-2", question="销售额")
        state.context_cache["conversation_summary"] = {"original_turns": 99}

        store.set_state(state)
        restored_state = store.get_state("session-2")

        self.assertIsNotNone(restored_state)
        self.assertIsNone(restored_state.conversation_summary)
        self.assertIsNone(restored_state.context_cache.get("conversation_summary"))

    async def test_session_store_does_not_mirror_remote_writes_to_memory_when_redis_is_healthy(self):
        store = V2SessionStore(redis_client=FakeRedis(), ttl_seconds=60)
        state = create_v2_state(session_id="session-healthy-1", user_id="user-2", question="销售额")
        state.mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="M1", name="销售额"),
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
        )

        store.set_state(state)

        self.assertEqual(store._memory_store, {})

    async def test_followup_add_metric_uses_metric_client_synonyms(self):
        router = IntentRouter()
        inherited_mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="SALES", name="销售额", field="ORDERED_PRODUCTSALES"),
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
        )

        class FakeMetricClient:
            def get_metric_by_name(self, metric_name):
                if metric_name == "毛利":
                    return {
                        "metric_code": "GROSS_PROFIT",
                        "name": "毛利润",
                        "starrocks_table": "ids.IDS_AMZ_COMPREHENSIVE_DI",
                        "starrocks_field": "GROSS_PROFIT",
                        "starrocks_sql": "SELECT SUM(GROSS_PROFIT) AS GROSS_PROFIT FROM ids.IDS_AMZ_COMPREHENSIVE_DI",
                        "unit": "元",
                    }
                return None

            def search_metrics(self, query, limit=5):
                return []

        with patch("ai.client.metric_client.MetricClient", return_value=FakeMetricClient()):
            result = await router._handle_followup("增加毛利", inherited_mql)

        self.assertEqual(result["source"], "followup_add_metric")
        self.assertFalse(result["needs_clarification"])
        self.assertIsNotNone(result["mql"])
        self.assertEqual(result["mql"].metric.name, "销售额")
        self.assertIn("毛利润", [m.name for m in result["mql"].metrics])

    async def test_followup_add_dimension_appends_dimension_code(self):
        router = IntentRouter()
        router._dimension_type_mappings = [
            {"dimension_type": "ASIN", "column_name": "ASIN"},
            {"dimension_type": "站点", "column_name": "FSITE"},
        ]
        inherited_mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="SALES", name="业绩", field="ORDERED_PRODUCTSALES"),
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
        )

        result = await router._handle_followup("增加ASIN", inherited_mql)

        self.assertEqual(result["source"], "followup_add_dimension")
        self.assertFalse(result["needs_clarification"])
        self.assertEqual(result["mql"].metric.name, "业绩")
        self.assertEqual([d.type for d in result["mql"].dimensions], ["ASIN"])

    async def test_followup_add_dimension_supports_dimension_synonym(self):
        router = IntentRouter()
        router._dimension_type_mappings = [
            {"dimension_type": "站点", "column_name": "FSITE"},
        ]
        inherited_mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="SALES", name="业绩", field="ORDERED_PRODUCTSALES"),
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
        )

        class FakeDimensionService:
            def find_column_by_type(self, dimension_type):
                return None

            def find_dimension_info(self, dimension_value):
                if dimension_value == "店铺":
                    return {
                        "column_name": "FSITE",
                        "dimension_value": "站点",
                        "is_generic": True,
                        "dimension_type": "站点",
                    }
                return None

        with patch.object(router, "_get_dimension_service", return_value=FakeDimensionService()):
            result = await router._handle_followup("增加店铺", inherited_mql)

        self.assertEqual(result["source"], "followup_add_dimension")
        self.assertFalse(result["needs_clarification"])
        self.assertEqual([d.type for d in result["mql"].dimensions], ["FSITE"])

    async def test_followup_add_dimension_accumulates_without_duplication(self):
        router = IntentRouter()
        router._dimension_type_mappings = [
            {"dimension_type": "ASIN", "column_name": "ASIN"},
            {"dimension_type": "站点", "column_name": "FSITE"},
        ]
        inherited_mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="SALES", name="业绩", field="ORDERED_PRODUCTSALES"),
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
            dimensions=[MQLDimension(type="ASIN", value=None)],
        )

        result = await router._handle_followup("增加ASIN", inherited_mql)
        self.assertEqual([d.type for d in result["mql"].dimensions], ["ASIN"])

        result2 = await router._handle_followup("增加站点", result["mql"])
        self.assertEqual([d.type for d in result2["mql"].dimensions], ["ASIN", "FSITE"])

    async def test_followup_remove_metric_supports_synonyms(self):
        router = IntentRouter()
        inherited_mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="SALES", name="业绩", field="ORDERED_PRODUCTSALES"),
            metrics=[MQLMetric(code="GP", name="毛利润"), MQLMetric(code="AD", name="广告花费")],
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
        )

        class FakeMetricClient:
            def get_metric_by_name(self, metric_name):
                if metric_name == "毛利":
                    return {"metric_code": "GP", "name": "毛利润"}
                if metric_name == "推广费":
                    return {"metric_code": "AD", "name": "广告花费"}
                return None

            def search_metrics(self, query, limit=5):
                return []

        with patch("ai.client.metric_client.MetricClient", return_value=FakeMetricClient()):
            result = await router._handle_followup("去掉毛利", inherited_mql)

        self.assertEqual(result["source"], "followup_remove_metric")
        self.assertEqual(result["mql"].metric.name, "业绩")
        self.assertEqual([m.name for m in result["mql"].metrics], ["广告花费"])

    async def test_followup_remove_primary_metric_promotes_next_metric(self):
        router = IntentRouter()
        inherited_mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="SALES", name="业绩", field="ORDERED_PRODUCTSALES"),
            metrics=[MQLMetric(code="GP", name="毛利润"), MQLMetric(code="AD", name="广告花费")],
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
        )

        class FakeMetricClient:
            def get_metric_by_name(self, metric_name):
                if metric_name == "业绩":
                    return {"metric_code": "SALES", "name": "业绩"}
                return None

            def search_metrics(self, query, limit=5):
                return []

        with patch("ai.client.metric_client.MetricClient", return_value=FakeMetricClient()):
            result = await router._handle_followup("去掉业绩", inherited_mql)

        self.assertEqual(result["source"], "followup_remove_metric")
        self.assertEqual(result["mql"].metric.name, "毛利润")
        self.assertEqual([m.name for m in result["mql"].metrics], ["广告花费"])

    async def test_followup_remove_dimension_supports_synonyms(self):
        router = IntentRouter()
        router._dimension_type_mappings = [
            {"dimension_type": "站点", "column_name": "FSITE"},
            {"dimension_type": "ASIN", "column_name": "ASIN"},
        ]
        inherited_mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="SALES", name="业绩", field="ORDERED_PRODUCTSALES"),
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
            dimensions=[MQLDimension(type="FSITE", value=None), MQLDimension(type="ASIN", value=None)],
        )

        class FakeDimensionService:
            def find_column_by_type(self, dimension_type):
                return None

            def find_dimension_info(self, dimension_value):
                if dimension_value == "店铺":
                    return {
                        "column_name": "FSITE",
                        "dimension_value": "站点",
                        "is_generic": True,
                        "dimension_type": "站点",
                    }
                return None

        with patch.object(router, "_get_dimension_service", return_value=FakeDimensionService()):
            result = await router._handle_followup("去掉店铺", inherited_mql)

        self.assertEqual(result["source"], "followup_remove_dimension")
        self.assertEqual([d.type for d in result["mql"].dimensions], ["ASIN"])


if __name__ == "__main__":
    unittest.main()
