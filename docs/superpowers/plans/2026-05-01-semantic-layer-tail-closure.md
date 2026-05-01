# Semantic Layer Tail Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last two gaps in the independent semantic layer by making newly published snapshots visible to the next `LLM.V2` request and by removing runtime fallback from `SemanticSnapshotService` to `DimensionService`.

**Architecture:** Refresh the active semantic snapshot once at the start of each `LLM.V2` request so Go-side `publish/rollback` becomes effective on the next ask without restarting Python. Extend the compiled semantic snapshot payload to carry dimension values from `dim_value_mapping`, then make Python semantic resolution use only snapshot runtime data (`dimensions`, `term_index`, `dimension_values`) and stop reading dimension data from legacy runtime APIs.

**Tech Stack:** Python FastAPI, Python `LLM.V2` router/service layer, Go Gin/GORM semantic bootstrap pipeline, pytest, Go test

---

### Task 1: Refresh active semantic snapshot at `LLM.V2` request entry

**Files:**
- Modify: `ai/engine/llm_v2/router.py`
- Test: `tests/unit/test_llm_v2_router_semantic_refresh.py`

- [ ] **Step 1: Add a dedicated refresh helper in the V2 router**

```python
from ai.services.semantic_snapshot_service import get_semantic_snapshot_service


def _refresh_semantic_snapshot_for_request() -> None:
    service = get_semantic_snapshot_service()
    try:
        service.get_active_snapshot(force_refresh=True)
    except Exception as exc:
        logger.warning(f"[V2 Semantic] refresh failed: {exc}")
```

- [ ] **Step 2: Call the helper before building request state in both V2 entrypoints**

In `ask_question_v2()` and `ask_question_v2_stream()`, insert the refresh immediately after `session_id` is finalized and before `create_v2_state(...)` / graph execution:

```python
_refresh_semantic_snapshot_for_request()
```

This is the chosen policy:
- refresh once per incoming V2 request
- do not refresh mid-graph
- allow the current request to continue if refresh fails, using the last cached snapshot

- [ ] **Step 3: Write a focused router unit test**

Create `tests/unit/test_llm_v2_router_semantic_refresh.py`:

```python
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
    )

    router_module._refresh_semantic_snapshot_for_request()

    assert calls == {"force_refresh": True}
```

- [ ] **Step 4: Run the smallest proof**

Run:

```bash
pytest -q tests/unit/test_llm_v2_router_semantic_refresh.py
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add ai/engine/llm_v2/router.py tests/unit/test_llm_v2_router_semantic_refresh.py
git commit -m "fix(semantic): refresh active snapshot at llm v2 request entry"
```

---

### Task 2: Compile dimension values into the runtime semantic snapshot

**Files:**
- Modify: `internal/semantic/bootstrap.go`
- Modify: `internal/api/handler/semantic.go`
- Test: `internal/semantic/bootstrap_test.go`

- [ ] **Step 1: Add dimension values to bootstrap seeds**

Extend the seed model and builder:

```go
type BootstrapSeeds struct {
	Metrics         []model.SemanticMetric
	Dimensions      []model.SemanticDimension
	Capabilities    []model.SemanticAnalysisCapability
	Policies        []model.SemanticInteractionPolicy
	Actions         []model.SemanticAction
	Terms           []model.BusinessTerm
	MetricAliases   map[string]string
	DimensionValues []model.DimensionValueMapping
}
```

Update `BuildBootstrapSeeds(...)` to accept `dimensionValues []model.DimensionValueMapping` and assign it to `DimensionValues`.

- [ ] **Step 2: Load `dim_value_mapping` rows when compiling snapshots**

In `internal/api/handler/semantic.go`, add:

```go
var dimensionValues []model.DimensionValueMapping
if err := db.Where("status = ?", 1).Find(&dimensionValues).Error; err != nil {
	return semantic.BootstrapSeeds{}, err
}
```

Pass `dimensionValues` into `semantic.BuildBootstrapSeeds(...)`.

Make the same change in `internal/semantic/bootstrap.go` inside `SeedSemanticBootstrap(...)` so bootstrap-created snapshots and manually compiled snapshots produce the same runtime shape.

- [ ] **Step 3: Add `dimension_values` to the snapshot payload**

In `CompileSnapshot(...)`, add a new runtime key:

```go
"dimension_values": buildDimensionValuesPayload(seeds.DimensionValues),
```

Add a grouped payload builder:

```go
func buildDimensionValuesPayload(items []model.DimensionValueMapping) map[string][]map[string]any {
	result := map[string][]map[string]any{}
	for _, item := range items {
		if item.Status == 0 || strings.TrimSpace(item.ColumnName) == "" || strings.TrimSpace(item.DimensionValue) == "" {
			continue
		}
		result[item.ColumnName] = append(result[item.ColumnName], map[string]any{
			"dimension_value": item.DimensionValue,
			"dimension_type":  item.DimensionType,
			"frequency":       item.Frequency,
		})
	}
	for _, values := range result {
		sort.Slice(values, func(i, j int) bool {
			li := values[i]["frequency"].(int64)
			lj := values[j]["frequency"].(int64)
			if li == lj {
				return values[i]["dimension_value"].(string) < values[j]["dimension_value"].(string)
			}
			return li > lj
		})
	}
	return result
}
```

Chosen runtime contract:
- payload key name: `dimension_values`
- shape: `map[column_name][]entry`
- each entry contains `dimension_value`, `dimension_type`, `frequency`
- exclude disabled rows and rows with empty `dimension_value`

- [ ] **Step 4: Add a Go test that proves dimension values enter the snapshot**

Extend `internal/semantic/bootstrap_test.go` with a case like:

```go
func TestCompileSnapshotIncludesDimensionValues(t *testing.T) {
	seeds := BootstrapSeeds{
		Dimensions: []model.SemanticDimension{
			{DimensionCode: "FSITE", DisplayName: "站点"},
		},
		DimensionValues: []model.DimensionValueMapping{
			{ColumnName: "FSITE", DimensionType: "站点", DimensionValue: "amazon-us", Frequency: 10, Status: 1},
			{ColumnName: "FSITE", DimensionType: "站点", DimensionValue: "amazon-uk", Frequency: 5, Status: 1},
		},
		MetricAliases: map[string]string{},
	}

	snapshot, err := CompileSnapshot(seeds, "tester", "dimension values")
	if err != nil {
		t.Fatalf("compile snapshot failed: %v", err)
	}

	var payload map[string]any
	if err := json.Unmarshal(snapshot.Payload, &payload); err != nil {
		t.Fatalf("unmarshal payload failed: %v", err)
	}

	grouped := payload["dimension_values"].(map[string]any)
	values := grouped["FSITE"].([]any)
	if len(values) != 2 {
		t.Fatalf("expected 2 dimension values, got %d", len(values))
	}
}
```

- [ ] **Step 5: Run the smallest proof**

Run:

```bash
go test ./internal/semantic -run "CompileSnapshotIncludesDimensionValues|BuildBootstrap"
```

Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add internal/semantic/bootstrap.go internal/api/handler/semantic.go internal/semantic/bootstrap_test.go
git commit -m "feat(semantic): compile dimension values into runtime snapshots"
```

---

### Task 3: Remove runtime fallback from `SemanticSnapshotService`

**Files:**
- Modify: `ai/services/semantic_snapshot_service.py`
- Test: `tests/unit/test_semantic_snapshot_service.py`

- [ ] **Step 1: Replace runtime fallback with snapshot-only helpers**

Add one helper near the existing snapshot helpers:

```python
def _get_snapshot_dimension_values(self) -> Dict[str, List[Dict[str, Any]]]:
    snapshot = self.get_active_snapshot()
    value_map = (snapshot or {}).get("dimension_values", {}) or {}
    return value_map if isinstance(value_map, dict) else {}
```

Delete `_get_dimension_service()` entirely after the migration in this task is complete.

- [ ] **Step 2: Rewrite the affected methods to use only snapshot data**

Implement these rules in `ai/services/semantic_snapshot_service.py`:

```python
def get_all_types(self) -> List[Dict[str, str]]:
    dimensions = ((self.get_active_snapshot() or {}).get("dimensions", {}) or {})
    return [
        {"column_name": code, "dimension_type": str(entry.get("display_name") or code).strip()}
        for code, entry in dimensions.items()
        if code
    ]


def search_dimension_values(self, candidate: str, limit: int = 20, column_name: Optional[str] = None) -> List[Dict[str, Any]]:
    normalized = self._normalize_text(candidate).lower()
    if not normalized:
        return []

    results: List[Dict[str, Any]] = []
    seen = set()

    term_match = self._resolve_dimension_from_term_index(candidate)
    if term_match and not term_match.get("is_generic"):
        key = (term_match["column_name"], term_match["dimension_value"])
        seen.add(key)
        results.append({
            "column_name": term_match["column_name"],
            "dimension_type": term_match["dimension_type"],
            "dimension_value": term_match["dimension_value"],
            "match_type": "semantic_term",
        })

    for dim_code, items in self._get_snapshot_dimension_values().items():
        if column_name and dim_code != column_name:
            continue
        for item in items:
            value = self._normalize_text(item.get("dimension_value"))
            if not value or normalized not in value.lower():
                continue
            key = (dim_code, value)
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "column_name": dim_code,
                "dimension_type": self._normalize_text(item.get("dimension_type")),
                "dimension_value": value,
                "match_type": "snapshot_dimension_value",
            })
            if len(results) >= limit:
                return results
    return results
```

Apply the same snapshot-only rule to:
- `resolve_dimension()`
- `get_dimension_keywords()`
- `get_dimension_values_context()`
- `get_level_keywords()`
- `get_dimension_fallback_map()`

Chosen behavior when no active snapshot exists:
- list methods return `[]`, `{}`, or `""`
- resolvers return `None`
- no network fallback to `/dimension-type-mappings` or `/dimension-values/*`

- [ ] **Step 3: Add pytest coverage that proves no legacy fallback is used**

Append cases to `tests/unit/test_semantic_snapshot_service.py`:

```python
def test_search_dimension_values_uses_snapshot_dimension_values_without_dimension_service():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "dimensions": {"FSITE": {"display_name": "站点"}},
        "dimension_values": {
            "FSITE": [
                {"dimension_value": "amazon-us", "dimension_type": "站点", "frequency": 10},
                {"dimension_value": "amazon-uk", "dimension_type": "站点", "frequency": 5},
            ]
        },
        "term_index": {},
    }
    service._dimension_service = object()

    results = service.search_dimension_values("amazon", limit=10)

    assert [item["dimension_value"] for item in results] == ["amazon-us", "amazon-uk"]


def test_get_dimension_values_context_reads_snapshot_only():
    service = SemanticSnapshotService()
    service._active_snapshot = {
        "dimensions": {"FSITE": {"display_name": "站点"}},
        "dimension_values": {
            "FSITE": [
                {"dimension_value": "amazon-us", "dimension_type": "站点", "frequency": 10},
                {"dimension_value": "amazon-uk", "dimension_type": "站点", "frequency": 5},
            ]
        },
        "term_index": {},
    }

    context = service.get_dimension_values_context(["FSITE"])

    assert "FSITE(站点): amazon-us, amazon-uk" in context
```

- [ ] **Step 4: Run the smallest proof**

Run:

```bash
pytest -q tests/unit/test_semantic_snapshot_service.py
```

Expected: all semantic snapshot service tests pass

- [ ] **Step 5: Run the combined semantic regression check**

Run:

```bash
pytest -q tests/unit/test_semantic_snapshot_service.py tests/unit/test_mql_generator_semantic.py tests/unit/test_trigger_analyzer_semantic.py tests/unit/test_prompt_metadata_loader_semantic.py tests/unit/test_intent_router_semantic_dimensions.py tests/unit/test_nodes/test_result_analyzer_semantic.py tests/unit/test_llm_v2_router_semantic_refresh.py
go test ./internal/semantic ./internal/api/handler -run "Semantic|Snapshot"
```

Expected:
- pytest suite passes
- Go semantic/snapshot tests pass

- [ ] **Step 6: Commit**

```bash
git add ai/services/semantic_snapshot_service.py tests/unit/test_semantic_snapshot_service.py tests/unit/test_llm_v2_router_semantic_refresh.py
git commit -m "refactor(semantic): remove runtime dimension fallback from snapshot service"
```

---

## Important Interface Changes

- Runtime semantic snapshot payload adds `dimension_values`.
- `SemanticSnapshotService` becomes snapshot-only for dimension metadata and dimension value resolution.
- `LLM.V2` request entry always refreshes the active snapshot before graph execution.

## Test Plan

- Publish or rollback a semantic snapshot in Go, then send the next `/api/v1/llm-ask/v2` request without restarting Python; the new request must read the newly active snapshot.
- Compile a semantic snapshot from DB data containing `dim_value_mapping` rows and verify the snapshot payload includes `dimension_values`.
- Resolve generic dimensions, exact dimension values, and follow-up suggestions using only snapshot payload plus existing semantic tests.

## Assumptions

- `dim_value_mapping` is the source of truth for runtime dimension values; no additional alias source is required beyond existing `business_terms`.
- Refreshing the snapshot once per incoming V2 request is acceptable overhead and is preferred over TTL-based eventual consistency.
- Snapshot compilation may increase payload size, but the current dimension-value scale is small enough to keep in process memory for Python AI.
