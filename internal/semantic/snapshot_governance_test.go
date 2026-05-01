package semantic

import (
	"testing"

	"dev_metric/internal/model"
)

func TestCompareSnapshotsDetectsAddedRemovedAndChanged(t *testing.T) {
	from := model.SemanticSnapshot{
		SnapshotID: "snap-from",
		Payload: model.JSONBlob([]byte(`{
			"metrics": {"M1": {"display_name": "sales"}},
			"dimensions": {"FSITE": {"display_name": "site"}},
			"interaction_policies": {"comparison": {"policy": {"default_comparison_type": "同比"}}}
		}`)),
	}
	to := model.SemanticSnapshot{
		SnapshotID: "snap-to",
		Payload: model.JSONBlob([]byte(`{
			"metrics": {"M1": {"display_name": "sales-new"}, "M2": {"display_name": "profit"}},
			"dimensions": {},
			"interaction_policies": {"comparison": {"policy": {"default_comparison_type": "环比"}}}
		}`)),
	}

	diff, err := CompareSnapshots(from, to)
	if err != nil {
		t.Fatalf("compare snapshots failed: %v", err)
	}

	metricDiff := diff.Sections["metrics"]
	if len(metricDiff.Added) != 1 || metricDiff.Added[0] != "M2" {
		t.Fatalf("expected M2 added, got %+v", metricDiff)
	}
	if len(metricDiff.Changed) != 1 || metricDiff.Changed[0] != "M1" {
		t.Fatalf("expected M1 changed, got %+v", metricDiff)
	}

	dimensionDiff := diff.Sections["dimensions"]
	if len(dimensionDiff.Removed) != 1 || dimensionDiff.Removed[0] != "FSITE" {
		t.Fatalf("expected FSITE removed, got %+v", dimensionDiff)
	}

	policyDiff := diff.Sections["interaction_policies"]
	if len(policyDiff.Changed) != 1 || policyDiff.Changed[0] != "comparison" {
		t.Fatalf("expected comparison policy changed, got %+v", policyDiff)
	}

	if diff.Summary["added"] != 1 || diff.Summary["removed"] != 1 || diff.Summary["changed"] != 2 {
		t.Fatalf("unexpected diff summary: %+v", diff.Summary)
	}
}
