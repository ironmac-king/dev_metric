from ai.engine.llm_v2 import router as router_module


def test_refresh_semantic_snapshot_for_request_uses_force_refresh(monkeypatch):
    calls = {}

    class FakeService:
        def get_active_snapshot(self, force_refresh=False):
            calls["force_refresh"] = force_refresh
            return {"semantic_version": "v1"}

    monkeypatch.setattr(
        router_module,
        "get_semantic_snapshot_service",
        lambda: FakeService(),
        raising=False,
    )

    router_module._refresh_semantic_snapshot_for_request()

    assert calls == {"force_refresh": True}
