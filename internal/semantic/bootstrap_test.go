package semantic

import (
	"testing"

	"dev_metric/internal/model"
)

func TestBuildBootstrapSeedsCreatesSemanticEntities(t *testing.T) {
	metrics := []model.Metric{
		{
			MetricCode:       "M1",
			Name:             "销售额",
			Unit:             "元",
			MetricType:       "atomic",
			CommonDimensions: "站点,二级品类",
			Frequency:        "daily",
		},
		{
			MetricCode:       "M2",
			Name:             "广告花费",
			Unit:             "元",
			MetricType:       "atomic",
			CommonDimensions: "站点,广告渠道",
			Frequency:        "daily",
		},
	}

	dimensionConfigs := []model.DimensionConfig{
		{DimensionName: "站点", ColumnName: "FSITE", Status: 1},
		{DimensionName: "二级品类", ColumnName: "GROUP_2", Status: 1},
	}

	dimensionTypes := []model.DimensionTypeMapping{
		{DimensionType: "站点", ColumnName: "FSITE", Status: 1},
		{DimensionType: "二级品类", ColumnName: "GROUP_2", Status: 1},
	}

	labels := []model.BusinessDimensionLabel{
		{DimensionType: "站点", RawValue: "美国站", DisplayName: "美国站", Emoji: "🌍"},
	}

	terms := []model.BusinessTerm{
		{Term: "销售额", DimensionField: "", DimensionValue: ""},
		{Term: "站点", DimensionField: "FSITE", DimensionValue: ""},
	}

	triggerConfigs := []model.AnalysisTriggerConfig{
		{TriggerType: "volatility", MetricCode: "销售额"},
	}

	outputTemplates := []model.OutputTemplate{
		{TemplateKey: "volatility_summary", TemplateType: "summary"},
	}

	seeds := BuildBootstrapSeeds(
		metrics,
		dimensionConfigs,
		dimensionTypes,
		labels,
		terms,
		triggerConfigs,
		outputTemplates,
		nil,
	)

	if len(seeds.Metrics) != 2 {
		t.Fatalf("expected 2 semantic metrics, got %d", len(seeds.Metrics))
	}
	if len(seeds.Dimensions) < 2 {
		t.Fatalf("expected at least 2 semantic dimensions, got %d", len(seeds.Dimensions))
	}
	if len(seeds.Capabilities) < 2 {
		t.Fatalf("expected semantic capabilities for metrics, got %d", len(seeds.Capabilities))
	}
	if len(seeds.Policies) == 0 {
		t.Fatal("expected default interaction policies")
	}
	if len(seeds.Actions) == 0 {
		t.Fatal("expected default semantic actions")
	}
}

func TestCompileSnapshotProducesRuntimePayload(t *testing.T) {
	seeds := BootstrapSeeds{
		Metrics: []model.SemanticMetric{
			{
				MetricCode:                "M1",
				DisplayName:               "销售额",
				DefaultAggregation:        "SUM",
				DefaultTimeGrain:          "day",
				DefaultChartType:          "line",
				RecommendedDimensionCodes: model.StringArray{"FSITE"},
				Status:                    1,
				Version:                   1,
			},
		},
		Dimensions: []model.SemanticDimension{
			{
				DimensionCode:     "FSITE",
				DisplayName:       "站点",
				SupportsGroupBy:   true,
				SupportsFilter:    true,
				SupportsDrilldown: true,
				DrilldownTargets:  model.StringArray{"GROUP_2"},
				Status:            1,
				Version:           1,
			},
		},
		Capabilities: []model.SemanticAnalysisCapability{
			{
				SubjectType:        "metric",
				SubjectKey:         "M1",
				SupportsTrend:      true,
				SupportsComparison: true,
				SupportsDrilldown:  true,
				AllowedModes:       model.StringArray{"direct", "analyze"},
				Status:             1,
				Version:            1,
			},
		},
		Policies: []model.SemanticInteractionPolicy{
			{
				PolicyKey:       "simple_query",
				SceneType:       "simple_query",
				AnswerMode:      "direct",
				ClarifyPriority: 10,
				MaxSuggestions:  3,
				Status:          1,
				Version:         1,
			},
		},
		Actions: []model.SemanticAction{
			{
				ActionCode:      "view_sales",
				Label:           "看销售",
				SourceSceneType: "analysis",
				TargetSceneType: "drilldown",
				Priority:        10,
				Status:          1,
				Version:         1,
			},
		},
		Terms: []model.BusinessTerm{
			{Term: "销售额"},
			{Term: "站点", DimensionField: "FSITE"},
		},
	}

	snapshot, err := CompileSnapshot(seeds, "tester", "bootstrap init")
	if err != nil {
		t.Fatalf("compile snapshot failed: %v", err)
	}
	if snapshot.Version == "" {
		t.Fatal("expected snapshot version")
	}
	if len(snapshot.Payload) == 0 {
		t.Fatal("expected snapshot payload")
	}

	payload := map[string]any{}
	if err := snapshot.Payload.Unmarshal(&payload); err != nil {
		t.Fatalf("failed to unmarshal payload: %v", err)
	}

	requiredKeys := []string{"metrics", "dimensions", "interaction_policies", "actions", "semantic_version"}
	for _, key := range requiredKeys {
		if _, ok := payload[key]; !ok {
			t.Fatalf("expected payload key %q", key)
		}
	}
}

func TestCompileSnapshotIncludesDimensionValues(t *testing.T) {
	seeds := BootstrapSeeds{
		Dimensions: []model.SemanticDimension{
			{
				DimensionCode: "FSITE",
				DisplayName:   "站点",
				Status:        1,
				Version:       1,
			},
		},
		DimensionValues: []model.DimensionValueMapping{
			{
				ColumnName:     "FSITE",
				DimensionType:  "站点",
				DimensionValue: "amazon-us",
				Frequency:      10,
				Status:         1,
			},
			{
				ColumnName:     "FSITE",
				DimensionType:  "站点",
				DimensionValue: "amazon-uk",
				Frequency:      5,
				Status:         1,
			},
		},
	}

	snapshot, err := CompileSnapshot(seeds, "tester", "dimension values")
	if err != nil {
		t.Fatalf("compile snapshot failed: %v", err)
	}

	payload := map[string]any{}
	if err := snapshot.Payload.Unmarshal(&payload); err != nil {
		t.Fatalf("failed to unmarshal payload: %v", err)
	}

	dimensionValues, ok := payload["dimension_values"]
	if !ok {
		t.Fatal("expected payload key \"dimension_values\"")
	}
	grouped, ok := dimensionValues.(map[string]any)
	if !ok {
		t.Fatalf("expected dimension_values map, got %T", dimensionValues)
	}
	values, ok := grouped["FSITE"].([]any)
	if !ok || len(values) != 2 {
		t.Fatalf("expected 2 FSITE values, got %#v", grouped["FSITE"])
	}
}
