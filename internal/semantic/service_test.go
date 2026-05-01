package semantic

import (
	"testing"

	"dev_metric/internal/model"
)

func TestBuildSnapshotVersionChangesWithPayload(t *testing.T) {
	baseSeeds := BootstrapSeeds{
		Metrics: []model.SemanticMetric{
			{MetricCode: "M1", DisplayName: "销售额", Status: 1, Version: 1},
		},
		Dimensions: []model.SemanticDimension{
			{DimensionCode: "FSITE", DisplayName: "站点", Status: 1, Version: 1},
		},
		Policies: []model.SemanticInteractionPolicy{
			{PolicyKey: "simple_query", SceneType: "simple_query", AnswerMode: "direct", Status: 1, Version: 1},
		},
	}

	s1, err := CompileSnapshot(baseSeeds, "tester", "first")
	if err != nil {
		t.Fatalf("compile first snapshot failed: %v", err)
	}

	modified := baseSeeds
	modified.Metrics = []model.SemanticMetric{
		{MetricCode: "M1", DisplayName: "销售额（新）", Status: 1, Version: 1},
	}
	s2, err := CompileSnapshot(modified, "tester", "second")
	if err != nil {
		t.Fatalf("compile second snapshot failed: %v", err)
	}

	if s1.Version == s2.Version {
		t.Fatal("expected snapshot version to change when payload changes")
	}
}

func TestComputePublishedStatusesSwitchesActiveVersion(t *testing.T) {
	first := model.SemanticSnapshot{
		SnapshotID:  "snap-1",
		Version:     "v1",
		CompiledBy:  "tester",
		Status:      "active",
		Payload:     model.JSONBlob([]byte(`{"semantic_version":"v1"}`)),
	}
	second := model.SemanticSnapshot{
		SnapshotID:  "snap-2",
		Version:     "v2",
		CompiledBy:  "tester",
		Status:      "draft",
		Payload:     model.JSONBlob([]byte(`{"semantic_version":"v2"}`)),
	}
	snapshots := []model.SemanticSnapshot{first, second}
	snapshots = ComputePublishedStatuses(snapshots, "snap-2")

	statusByID := map[string]string{}
	for _, item := range snapshots {
		statusByID[item.SnapshotID] = item.Status
	}
	if statusByID["snap-1"] != "archived" {
		t.Fatalf("expected snap-1 archived, got %s", statusByID["snap-1"])
	}
	if statusByID["snap-2"] != "active" {
		t.Fatalf("expected snap-2 active, got %s", statusByID["snap-2"])
	}
}
