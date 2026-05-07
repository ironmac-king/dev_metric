package semantic

import (
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strings"
	"time"

	"dev_metric/internal/model"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

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

func BuildBootstrapSeeds(
	metrics []model.Metric,
	dimensionConfigs []model.DimensionConfig,
	dimensionTypes []model.DimensionTypeMapping,
	labels []model.BusinessDimensionLabel,
	terms []model.BusinessTerm,
	triggerConfigs []model.AnalysisTriggerConfig,
	outputTemplates []model.OutputTemplate,
	dimensionValues []model.DimensionValueMapping,
) BootstrapSeeds {
	return BootstrapSeeds{
		Metrics:         buildSemanticMetrics(metrics, dimensionTypes),
		Dimensions:      buildSemanticDimensions(dimensionConfigs, dimensionTypes, labels),
		Capabilities:    buildMetricCapabilities(metrics, dimensionTypes, triggerConfigs),
		Policies:        buildInteractionPolicies(),
		Actions:         buildSemanticActions(triggerConfigs, outputTemplates),
		Terms:           terms,
		MetricAliases:   buildMetricAliases(metrics, terms),
		DimensionValues: dimensionValues,
	}
}

func CompileSnapshot(seeds BootstrapSeeds, compiledBy, releaseNote string) (model.SemanticSnapshot, error) {
	payload := map[string]any{
		"semantic_version":     "v1",
		"compiled_at":          time.Now().UTC().Format(time.RFC3339),
		"metrics":              buildMetricPayload(seeds.Metrics),
		"dimensions":           buildDimensionPayload(seeds.Dimensions),
		"dimension_values":     buildDimensionValuesPayload(seeds.DimensionValues),
		"capabilities":         buildCapabilityPayload(seeds.Capabilities),
		"interaction_policies": buildPolicyPayload(seeds.Policies),
		"actions":              buildActionPayload(seeds.Actions),
		"term_index":           buildTermPayload(seeds.Terms),
		"metric_aliases":       seeds.MetricAliases,
	}

	raw, err := json.Marshal(payload)
	if err != nil {
		return model.SemanticSnapshot{}, err
	}
	sum := sha1.Sum(raw)
	version := fmt.Sprintf("v1-%s", hex.EncodeToString(sum[:])[:12])

	return model.SemanticSnapshot{
		SnapshotID:  version,
		Version:     version,
		CompiledAt:  time.Now().UTC(),
		CompiledBy:  compiledBy,
		Payload:     model.JSONBlob(raw),
		Status:      "active",
		ReleaseNote: releaseNote,
	}, nil
}

func SeedSemanticBootstrap(db *gorm.DB, compiledBy string) error {
	if db == nil {
		return fmt.Errorf("db is nil")
	}

	var metrics []model.Metric
	if err := db.Find(&metrics).Error; err != nil {
		return err
	}
	var dimensionConfigs []model.DimensionConfig
	if err := db.Find(&dimensionConfigs).Error; err != nil {
		return err
	}
	var dimensionTypes []model.DimensionTypeMapping
	if err := db.Find(&dimensionTypes).Error; err != nil {
		return err
	}
	var labels []model.BusinessDimensionLabel
	if err := db.Find(&labels).Error; err != nil {
		return err
	}
	var terms []model.BusinessTerm
	if err := db.Find(&terms).Error; err != nil {
		return err
	}
	var dimensionValues []model.DimensionValueMapping
	if err := db.Where("status = ?", 1).Find(&dimensionValues).Error; err != nil {
		return err
	}
	var triggerConfigs []model.AnalysisTriggerConfig
	_ = db.Find(&triggerConfigs).Error
	var outputTemplates []model.OutputTemplate
	_ = db.Find(&outputTemplates).Error

	seeds := BuildBootstrapSeeds(metrics, dimensionConfigs, dimensionTypes, labels, terms, triggerConfigs, outputTemplates, dimensionValues)

	if err := upsertSemanticMetrics(db, seeds.Metrics); err != nil {
		return err
	}
	if err := upsertSemanticDimensions(db, seeds.Dimensions); err != nil {
		return err
	}
	if err := upsertSemanticCapabilities(db, seeds.Capabilities); err != nil {
		return err
	}
	if err := upsertSemanticPolicies(db, seeds.Policies); err != nil {
		return err
	}
	if err := upsertSemanticActions(db, seeds.Actions); err != nil {
		return err
	}

	var activeCount int64
	if err := db.Model(&model.SemanticSnapshot{}).Where("status = ?", "active").Count(&activeCount).Error; err != nil {
		return err
	}
	if activeCount == 0 {
		snapshot, err := CompileSnapshot(seeds, compiledBy, "bootstrap init")
		if err != nil {
			return err
		}
		if err := db.Create(&snapshot).Error; err != nil {
			return err
		}
	}

	return nil
}

func ComputePublishedStatuses(items []model.SemanticSnapshot, activeSnapshotID string) []model.SemanticSnapshot {
	result := make([]model.SemanticSnapshot, len(items))
	copy(result, items)
	for i := range result {
		switch {
		case result[i].SnapshotID == activeSnapshotID:
			result[i].Status = "active"
		case result[i].Status == "active":
			result[i].Status = "archived"
		case result[i].Status == "":
			result[i].Status = "draft"
		}
	}
	return result
}

func PublishSnapshot(db *gorm.DB, snapshotID string, operator string, note string) error {
	return activateSnapshot(db, snapshotID, operator, note, "publish")
}

func RollbackSnapshot(db *gorm.DB, snapshotID string, operator string, note string) error {
	return activateSnapshot(db, snapshotID, operator, note, "rollback")
}

func activateSnapshot(db *gorm.DB, snapshotID string, operator string, note string, eventType string) error {
	if db == nil {
		return fmt.Errorf("db is nil")
	}
	return db.Transaction(func(tx *gorm.DB) error {
		var previousActive model.SemanticSnapshot
		err := tx.Where("status = ?", "active").Order("compiled_at DESC").First(&previousActive).Error
		if err != nil && err != gorm.ErrRecordNotFound {
			return err
		}

		var target model.SemanticSnapshot
		if err := tx.Where("snapshot_id = ?", snapshotID).First(&target).Error; err != nil {
			return err
		}

		if previousActive.SnapshotID == snapshotID {
			return RecordSnapshotAudit(
				tx,
				snapshotID,
				eventType,
				target.Status,
				target.Status,
				operator,
				note,
				model.JSONMap{"no_op": true},
			)
		}

		if previousActive.SnapshotID != "" {
			if err := tx.Model(&model.SemanticSnapshot{}).
				Where("snapshot_id = ?", previousActive.SnapshotID).
				Updates(map[string]any{"status": "archived", "updated_at": time.Now().UTC()}).Error; err != nil {
				return err
			}
			if err := RecordSnapshotAudit(
				tx,
				previousActive.SnapshotID,
				"archive",
				"active",
				"archived",
				operator,
				note,
				model.JSONMap{"replaced_by": snapshotID, "activation_event": eventType},
			); err != nil {
				return err
			}
		}

		if err := tx.Model(&model.SemanticSnapshot{}).
			Where("snapshot_id = ?", snapshotID).
			Updates(map[string]any{"status": "active", "updated_at": time.Now().UTC()}).Error; err != nil {
			return err
		}
		if err := RecordSnapshotAudit(
			tx,
			snapshotID,
			eventType,
			target.Status,
			"active",
			operator,
			note,
			model.JSONMap{"previous_active_snapshot_id": previousActive.SnapshotID},
		); err != nil {
			return err
		}
		return nil
	})
}

// parseAggregation 从 starrocks_sql 提取聚合表达式
// 例如: "SELECT SUM(sales_amt) AS total FROM ..." → "SUM(sales_amt)"
func parseAggregation(sql string) string {
	if sql == "" {
		return ""
	}
	re := regexp.MustCompile(`(?i)(SUM|AVG|COUNT|MAX|MIN|COUNT_DISTINCT)\s*\(\s*([^)]+)\s*\)`)
	matches := re.FindStringSubmatch(sql)
	if len(matches) >= 3 {
		return matches[1] + "(" + matches[2] + ")"
	}
	return ""
}

// parseTableFromSQL 从 starrocks_sql 提取表名
// "SELECT ... FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE ..." → "ids.IDS_AMZ_COMPREHENSIVE_DI"
func parseTableFromSQL(sql string) string {
	if sql == "" {
		return ""
	}
	re := regexp.MustCompile(`(?i)\bFROM\s+([a-zA-Z_][\w.]*(?:\.[a-zA-Z_][\w.]*)?)`)
	matches := re.FindStringSubmatch(sql)
	if len(matches) >= 2 {
		return strings.TrimSpace(matches[1])
	}
	return ""
}

// parseFieldFromAggExpression 从聚合表达式提取裸字段名
// "SUM(INCOME_NBCSS)" → "INCOME_NBCSS"
// "COUNT(DISTINCT VISITOR_NAME)" → "VISITOR_NAME"
func parseFieldFromAggExpression(aggExpr string) string {
	if aggExpr == "" {
		return ""
	}
	// SUM/AVG/MAX/MIN(field)
	re := regexp.MustCompile(`(?i)(?:SUM|AVG|MAX|MIN)\s*\(\s*([A-Za-z_]\w*)\s*\)`)
	matches := re.FindStringSubmatch(aggExpr)
	if len(matches) >= 2 {
		return matches[1]
	}
	// COUNT(DISTINCT field)
	re2 := regexp.MustCompile(`(?i)COUNT\s*\(\s*DISTINCT\s+([A-Za-z_]\w*)\s*\)`)
	matches2 := re2.FindStringSubmatch(aggExpr)
	if len(matches2) >= 2 {
		return matches2[1]
	}
	return ""
}

func buildSemanticMetrics(metrics []model.Metric, dimensionTypes []model.DimensionTypeMapping) []model.SemanticMetric {
	if len(metrics) == 0 {
		return nil
	}

	dimensionLookup := map[string]string{}
	for _, item := range dimensionTypes {
		if item.Status == 0 {
			continue
		}
		dimensionLookup[item.DimensionType] = item.ColumnName
	}

	out := make([]model.SemanticMetric, 0, len(metrics))
	for _, metric := range metrics {
		if metric.MetricCode == "" || metric.Name == "" {
			continue
		}
		metricType := metric.MetricType
		if metricType == "" {
			metricType = "atomic"
		}
		out = append(out, model.SemanticMetric{
			MetricCode:                metric.MetricCode,
			DisplayName:               metric.Name,
			BusinessSummary:           firstNonEmpty(metric.BusinessDefinition, metric.BusinessRule, metric.TechnicalRule),
			DefaultAggregation:        inferAggregation(metric),
			DefaultTimeGrain:          inferTimeGrain(metric.Frequency),
			DefaultChartType:          inferChartType(metric.Name),
			RecommendedDimensionCodes: resolveRecommendedDimensions(metric.CommonDimensions, dimensionLookup),
			PreferredFollowups:        inferPreferredFollowups(metric),
			Tags:                      collectMetricTags(metric),
			Status:                    normalizeStatus(metric.Status),
			Version:                   1,
			UpdatedBy:                 "semantic-bootstrap",
			// CTE 渲染所需字段
			AggExpression:   parseAggregation(metric.StarRocksSQL),
			MetricType:      metricType,
			StarRocksTable:  parseTableFromSQL(metric.StarRocksSQL),
			StarRocksField:  parseFieldFromAggExpression(parseAggregation(metric.StarRocksSQL)),
			StarRocksSQL:    metric.StarRocksSQL,
		})
	}

	sort.Slice(out, func(i, j int) bool { return out[i].MetricCode < out[j].MetricCode })
	return out
}

func buildSemanticDimensions(
	dimensionConfigs []model.DimensionConfig,
	dimensionTypes []model.DimensionTypeMapping,
	labels []model.BusinessDimensionLabel,
) []model.SemanticDimension {
	seeds := map[string]*dimSeed{}
	for _, item := range dimensionConfigs {
		if item.ColumnName == "" || item.Status == 0 {
			continue
		}
		seed := ensureDimensionSeed(seeds, item.ColumnName, item.DimensionName)
		seed.Level = max(seed.Level, inferHierarchyLevel(item.DimensionName))
	}
	for _, item := range dimensionTypes {
		if item.ColumnName == "" || item.Status == 0 {
			continue
		}
		seed := ensureDimensionSeed(seeds, item.ColumnName, item.DimensionType)
		seed.Level = max(seed.Level, inferHierarchyLevel(item.DimensionType))
	}
	for _, label := range labels {
		if label.DimensionType == "" {
			continue
		}
		if seed, ok := seeds[label.DimensionType]; ok {
			if label.Emoji != "" {
				seed.Tags["emoji:"+label.Emoji] = struct{}{}
			}
			if label.PriorityTag != "" {
				seed.Tags["priority:"+label.PriorityTag] = struct{}{}
			}
		}
	}

	categoryByLevel := map[int]string{}
	for code, seed := range seeds {
		if strings.Contains(seed.DisplayName, "品类") {
			categoryByLevel[seed.Level] = code
		}
	}

	out := make([]model.SemanticDimension, 0, len(seeds))
	for code, seed := range seeds {
		drilldownTargets := model.StringArray{}
		parentCode := ""
		if strings.Contains(seed.DisplayName, "品类") {
			if nextCode, ok := categoryByLevel[seed.Level+1]; ok && nextCode != code {
				drilldownTargets = append(drilldownTargets, nextCode)
			}
			if prevCode, ok := categoryByLevel[seed.Level-1]; ok && prevCode != code {
				parentCode = prevCode
			}
		}

		out = append(out, model.SemanticDimension{
			DimensionCode:       code,
			DisplayName:         seed.DisplayName,
			HierarchyLevel:      seed.Level,
			ParentDimensionCode: parentCode,
			SupportsGroupBy:     true,
			SupportsFilter:      true,
			SupportsDrilldown:   len(drilldownTargets) > 0,
			DrilldownTargets:    drilldownTargets,
			AllowedMetricCodes:  model.StringArray{},
			DefaultSortPriority: inferDimensionSortPriority(seed.DisplayName, seed.Level),
			Tags:                mapKeys(seed.Tags),
			Status:              1,
			Version:             1,
			UpdatedBy:           "semantic-bootstrap",
		})
	}

	sort.Slice(out, func(i, j int) bool { return out[i].DimensionCode < out[j].DimensionCode })
	return out
}

func buildMetricCapabilities(
	metrics []model.Metric,
	dimensionTypes []model.DimensionTypeMapping,
	triggerConfigs []model.AnalysisTriggerConfig,
) []model.SemanticAnalysisCapability {
	triggeredMetrics := map[string]struct{}{}
	for _, item := range triggerConfigs {
		if item.MetricCode != "" {
			triggeredMetrics[item.MetricCode] = struct{}{}
		}
	}

	hasCategoryDimension := false
	for _, item := range dimensionTypes {
		if item.Status != 0 && strings.Contains(item.DimensionType, "品类") {
			hasCategoryDimension = true
			break
		}
	}

	out := make([]model.SemanticAnalysisCapability, 0, len(metrics))
	for _, metric := range metrics {
		if metric.MetricCode == "" {
			continue
		}
		ratioMetric := strings.Contains(metric.Name, "率") || strings.Contains(metric.Name, "占比") || strings.Contains(metric.Name, "比重")
		_, hasTrigger := triggeredMetrics[metric.Name]
		allowsDrilldown := strings.TrimSpace(metric.CommonDimensions) != "" || hasCategoryDimension

		out = append(out, model.SemanticAnalysisCapability{
			SubjectType:         "metric",
			SubjectKey:          metric.MetricCode,
			SupportsValue:       true,
			SupportsTrend:       true,
			SupportsComparison:  true,
			SupportsYoY:         true,
			SupportsMoM:         true,
			SupportsRanking:     true,
			SupportsRatio:       ratioMetric,
			SupportsAttribution: hasTrigger || allowsDrilldown,
			SupportsDrilldown:   allowsDrilldown,
			AllowedModes:        inferAllowedModes(metric, ratioMetric, hasTrigger, allowsDrilldown),
			ConstraintsJSON: model.JSONMap{
				"query_frequency":   strings.TrimSpace(metric.Frequency),
				"common_dimensions": splitCSV(metric.CommonDimensions),
			},
			Status:    normalizeStatus(metric.Status),
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		})
	}

	sort.Slice(out, func(i, j int) bool { return out[i].SubjectKey < out[j].SubjectKey })
	return out
}

func buildInteractionPolicies() []model.SemanticInteractionPolicy {
	return []model.SemanticInteractionPolicy{
		{
			PolicyKey:       "simple_query",
			SceneType:       "simple_query",
			AnswerMode:      "direct",
			ClarifyPriority: 10,
			MaxSuggestions:  3,
			ConfidenceThresholds: model.JSONMap{
				"direct":  0.85,
				"clarify": 0.60,
			},
			FallbackStrategy: "clarify",
			PolicyJSON: model.JSONMap{
				"prefer_chart_for_trend": true,
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "followup",
			SceneType:       "followup",
			AnswerMode:      "analyze",
			ClarifyPriority: 90,
			MaxSuggestions:  4,
			ConfidenceThresholds: model.JSONMap{
				"inherit_context": 0.70,
			},
			FallbackStrategy: "inherit_or_clarify",
			PolicyJSON: model.JSONMap{
				"prefer_context_task": true,
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "ambiguity",
			SceneType:       "ambiguity",
			AnswerMode:      "clarify",
			ClarifyPriority: 100,
			MaxSuggestions:  0,
			ConfidenceThresholds: model.JSONMap{
				"force_clarify": 0.60,
			},
			FallbackStrategy: "stop_and_clarify",
			PolicyJSON: model.JSONMap{
				"show_candidates": true,
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "drilldown",
			SceneType:       "drilldown",
			AnswerMode:      "analyze",
			ClarifyPriority: 70,
			MaxSuggestions:  4,
			ConfidenceThresholds: model.JSONMap{
				"drilldown_ready": 0.75,
			},
			FallbackStrategy: "fallback_to_summary",
			PolicyJSON: model.JSONMap{
				"prefer_existing_focus": true,
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "no_data",
			SceneType:       "no_data",
			AnswerMode:      "clarify",
			ClarifyPriority: 80,
			MaxSuggestions:  3,
			ConfidenceThresholds: model.JSONMap{
				"retry_with_context": 0.50,
			},
			FallbackStrategy: "suggest_alternatives",
			PolicyJSON: model.JSONMap{
				"allow_time_relaxation": true,
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "generic_query",
			SceneType:       "generic_query",
			AnswerMode:      "analyze",
			ClarifyPriority: 50,
			MaxSuggestions:  4,
			ConfidenceThresholds: model.JSONMap{
				"scene_detect": 0.60,
			},
			FallbackStrategy: "fallback_to_analysis",
			PolicyJSON: model.JSONMap{
				"keywords":     []string{"怎么样", "怎么", "如何", "今天", "最近", "情况", "生意"},
				"core_metrics": []string{"gmv", "orders"},
				"drilldown_categories": map[string]any{
					"sales":     []string{"销售经营", "销售分析", "销售概览"},
					"ad":        []string{"广告投放", "广告效果", "广告分析", "投放分析"},
					"inventory": []string{"库存供应", "库存分析", "供应链", "补货分析"},
					"cost":      []string{"成本毛利", "成本分析", "毛利分析", "利润分析"},
				},
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "comparison",
			SceneType:       "comparison",
			AnswerMode:      "analyze",
			ClarifyPriority: 60,
			MaxSuggestions:  4,
			ConfidenceThresholds: model.JSONMap{
				"scene_detect": 0.65,
			},
			FallbackStrategy: "fallback_to_analysis",
			PolicyJSON: model.JSONMap{
				"keywords":                []string{"哪个", "对比", "比较", "平台表现", "站点", "国家"},
				"default_comparison_type": "同比",
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "ad_effect",
			SceneType:       "ad_effect",
			AnswerMode:      "analyze",
			ClarifyPriority: 55,
			MaxSuggestions:  4,
			ConfidenceThresholds: model.JSONMap{
				"scene_detect": 0.60,
			},
			FallbackStrategy: "fallback_to_analysis",
			PolicyJSON: model.JSONMap{
				"keywords": []string{"广告", "ROAS", "ROI", "花费", "投产", "效果", "推广"},
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "inventory_risk",
			SceneType:       "inventory_risk",
			AnswerMode:      "analyze",
			ClarifyPriority: 55,
			MaxSuggestions:  4,
			ConfidenceThresholds: model.JSONMap{
				"scene_detect": 0.60,
			},
			FallbackStrategy: "fallback_to_analysis",
			PolicyJSON: model.JSONMap{
				"keywords": []string{"库存", "可售", "断货", "补货", "周转"},
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			PolicyKey:       "context_followup",
			SceneType:       "context_followup",
			AnswerMode:      "analyze",
			ClarifyPriority: 65,
			MaxSuggestions:  4,
			ConfidenceThresholds: model.JSONMap{
				"scene_detect": 0.65,
			},
			FallbackStrategy: "fallback_to_followup",
			PolicyJSON: model.JSONMap{
				"keywords": []string{"为什么", "原因", "为啥", "哪个", "什么导致"},
			},
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
	}
}

func buildSemanticActions(triggerConfigs []model.AnalysisTriggerConfig, outputTemplates []model.OutputTemplate) []model.SemanticAction {
	actions := []model.SemanticAction{
		{
			ActionCode:      "view_sales",
			Label:           "看销售",
			SourceSceneType: "analysis",
			TargetSceneType: "drilldown",
			SourceConstraintsJSON: model.JSONMap{
				"check": "sales",
			},
			TargetPayloadTemplate: model.JSONMap{
				"question": "__DRILLDOWN__:sales__",
			},
			Priority:  100,
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			ActionCode:      "view_ad",
			Label:           "看广告",
			SourceSceneType: "analysis",
			TargetSceneType: "drilldown",
			SourceConstraintsJSON: model.JSONMap{
				"check": "ad",
			},
			TargetPayloadTemplate: model.JSONMap{
				"question": "__DRILLDOWN__:ad__",
			},
			Priority:  90,
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			ActionCode:      "view_inventory",
			Label:           "看库存",
			SourceSceneType: "analysis",
			TargetSceneType: "drilldown",
			SourceConstraintsJSON: model.JSONMap{
				"check": "inventory",
			},
			TargetPayloadTemplate: model.JSONMap{
				"question": "__DRILLDOWN__:inventory__",
			},
			Priority:  80,
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
		{
			ActionCode:      "view_profit",
			Label:           "看利润",
			SourceSceneType: "analysis",
			TargetSceneType: "drilldown",
			SourceConstraintsJSON: model.JSONMap{
				"check": "profit",
			},
			TargetPayloadTemplate: model.JSONMap{
				"question": "__DRILLDOWN__:profit__",
			},
			Priority:  70,
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		},
	}

	templateIndex := map[string]struct{}{}
	for _, tpl := range outputTemplates {
		templateIndex[tpl.TemplateKey] = struct{}{}
	}
	for _, cfg := range triggerConfigs {
		if cfg.TriggerType == "context_followup" {
			actions = append(actions, model.SemanticAction{
				ActionCode:      "context_followup_probe",
				Label:           "继续分析",
				SourceSceneType: "followup",
				TargetSceneType: "analyze",
				SourceConstraintsJSON: model.JSONMap{
					"trigger_type": cfg.TriggerType,
					"metric_name":  cfg.MetricCode,
				},
				TargetPayloadTemplate: model.JSONMap{
					"mode": "followup",
				},
				Priority:  60,
				Status:    1,
				Version:   1,
				UpdatedBy: "semantic-bootstrap",
			})
		}
	}
	if _, ok := templateIndex["volatility_summary"]; ok {
		actions = append(actions, model.SemanticAction{
			ActionCode:      "view_volatility_reason",
			Label:           "看波动归因",
			SourceSceneType: "comparison",
			TargetSceneType: "attribution",
			SourceConstraintsJSON: model.JSONMap{
				"requires_template": "volatility_summary",
			},
			TargetPayloadTemplate: model.JSONMap{
				"analysis_type": "volatility",
			},
			Priority:  85,
			Status:    1,
			Version:   1,
			UpdatedBy: "semantic-bootstrap",
		})
	}

	sort.Slice(actions, func(i, j int) bool { return actions[i].ActionCode < actions[j].ActionCode })
	return dedupeActions(actions)
}

func buildMetricPayload(items []model.SemanticMetric) map[string]map[string]any {
	result := map[string]map[string]any{}
	for _, item := range items {
		result[item.MetricCode] = map[string]any{
			"display_name":                item.DisplayName,
			"business_summary":            item.BusinessSummary,
			"default_aggregation":         item.DefaultAggregation,
			"default_time_grain":          item.DefaultTimeGrain,
			"default_chart_type":          item.DefaultChartType,
			"recommended_dimension_codes": []string(item.RecommendedDimensionCodes),
			"preferred_followups":         []string(item.PreferredFollowups),
			"tags":                        []string(item.Tags),
			"version":                     item.Version,
			// CTE 渲染所需字段
			"agg_expression":  item.AggExpression,
			"metric_type":     item.MetricType,
			"starrocks_table": item.StarRocksTable,
			"starrocks_field": item.StarRocksField,
			"starrocks_sql":   item.StarRocksSQL,
		}
	}
	return result
}

func buildDimensionPayload(items []model.SemanticDimension) map[string]map[string]any {
	result := map[string]map[string]any{}
	for _, item := range items {
		result[item.DimensionCode] = map[string]any{
			"display_name":          item.DisplayName,
			"hierarchy_level":       item.HierarchyLevel,
			"parent_dimension_code": item.ParentDimensionCode,
			"supports_group_by":     item.SupportsGroupBy,
			"supports_filter":       item.SupportsFilter,
			"supports_drilldown":    item.SupportsDrilldown,
			"drilldown_targets":     []string(item.DrilldownTargets),
			"allowed_metric_codes":  []string(item.AllowedMetricCodes),
			"default_sort_priority": item.DefaultSortPriority,
			"tags":                  []string(item.Tags),
			"version":               item.Version,
		}
	}
	return result
}

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

	for key, values := range result {
		sort.Slice(values, func(i, j int) bool {
			leftFreq, _ := values[i]["frequency"].(int64)
			rightFreq, _ := values[j]["frequency"].(int64)
			if leftFreq == rightFreq {
				leftValue, _ := values[i]["dimension_value"].(string)
				rightValue, _ := values[j]["dimension_value"].(string)
				return leftValue < rightValue
			}
			return leftFreq > rightFreq
		})
		result[key] = values
	}

	return result
}

func buildCapabilityPayload(items []model.SemanticAnalysisCapability) map[string]map[string]any {
	result := map[string]map[string]any{}
	for _, item := range items {
		key := fmt.Sprintf("%s:%s", item.SubjectType, item.SubjectKey)
		result[key] = map[string]any{
			"supports_value":       item.SupportsValue,
			"supports_trend":       item.SupportsTrend,
			"supports_comparison":  item.SupportsComparison,
			"supports_yoy":         item.SupportsYoY,
			"supports_mom":         item.SupportsMoM,
			"supports_ranking":     item.SupportsRanking,
			"supports_ratio":       item.SupportsRatio,
			"supports_attribution": item.SupportsAttribution,
			"supports_drilldown":   item.SupportsDrilldown,
			"allowed_modes":        []string(item.AllowedModes),
			"constraints":          item.ConstraintsJSON,
			"version":              item.Version,
		}
	}
	return result
}

func buildPolicyPayload(items []model.SemanticInteractionPolicy) map[string]map[string]any {
	result := map[string]map[string]any{}
	for _, item := range items {
		result[item.PolicyKey] = map[string]any{
			"scene_type":            item.SceneType,
			"answer_mode":           item.AnswerMode,
			"clarify_priority":      item.ClarifyPriority,
			"max_suggestions":       item.MaxSuggestions,
			"confidence_thresholds": item.ConfidenceThresholds,
			"fallback_strategy":     item.FallbackStrategy,
			"policy":                item.PolicyJSON,
			"version":               item.Version,
		}
	}
	return result
}

func buildActionPayload(items []model.SemanticAction) map[string]map[string]any {
	result := map[string]map[string]any{}
	for _, item := range items {
		result[item.ActionCode] = map[string]any{
			"label":                   item.Label,
			"source_scene_type":       item.SourceSceneType,
			"target_scene_type":       item.TargetSceneType,
			"source_constraints":      item.SourceConstraintsJSON,
			"target_payload_template": item.TargetPayloadTemplate,
			"priority":                item.Priority,
			"version":                 item.Version,
		}
	}
	return result
}

func buildTermPayload(terms []model.BusinessTerm) map[string]map[string]any {
	result := map[string]map[string]any{}
	for _, item := range terms {
		result[item.Term] = map[string]any{
			"metric_ids":      []int64(item.MetricIDs),
			"synonyms":        []string(item.Synonyms),
			"description":     item.Description,
			"dimension_field": item.DimensionField,
			"dimension_value": item.DimensionValue,
		}
	}
	return result
}

func buildMetricAliases(metrics []model.Metric, terms []model.BusinessTerm) map[string]string {
	result := map[string]string{}
	metricCodeByID := map[int64]string{}
	for _, metric := range metrics {
		if metric.ID != 0 && metric.MetricCode != "" {
			metricCodeByID[int64(metric.ID)] = metric.MetricCode
		}
		if metric.Name != "" && metric.MetricCode != "" {
			result[strings.ToLower(strings.TrimSpace(metric.Name))] = metric.MetricCode
		}
		if metric.NameEn != "" && metric.MetricCode != "" {
			result[strings.ToLower(strings.TrimSpace(metric.NameEn))] = metric.MetricCode
		}
	}

	for _, term := range terms {
		codes := uniqueMetricCodes(term.MetricIDs, metricCodeByID)
		if len(codes) != 1 {
			continue
		}
		code := codes[0]
		if term.Term != "" {
			result[strings.ToLower(strings.TrimSpace(term.Term))] = code
		}
		for _, synonym := range term.Synonyms {
			synonym = strings.TrimSpace(synonym)
			if synonym != "" {
				result[strings.ToLower(synonym)] = code
			}
		}
	}

	return result
}

func uniqueMetricCodes(metricIDs []int64, mapping map[int64]string) []string {
	seen := map[string]struct{}{}
	result := []string{}
	for _, metricID := range metricIDs {
		code := mapping[metricID]
		if code == "" {
			continue
		}
		if _, ok := seen[code]; ok {
			continue
		}
		seen[code] = struct{}{}
		result = append(result, code)
	}
	sort.Strings(result)
	return result
}

func upsertSemanticMetrics(db *gorm.DB, items []model.SemanticMetric) error {
	if len(items) == 0 {
		return nil
	}
	return db.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "metric_code"}},
		DoUpdates: clause.AssignmentColumns([]string{"display_name", "business_summary", "default_aggregation", "default_time_grain", "default_chart_type", "recommended_dimension_codes", "preferred_followups", "tags", "status", "version", "updated_by", "updated_at", "agg_expression", "metric_type"}),
	}).Create(&items).Error
}

func upsertSemanticDimensions(db *gorm.DB, items []model.SemanticDimension) error {
	if len(items) == 0 {
		return nil
	}
	return db.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "dimension_code"}},
		DoUpdates: clause.AssignmentColumns([]string{"display_name", "hierarchy_level", "parent_dimension_code", "supports_group_by", "supports_filter", "supports_drilldown", "drilldown_targets", "allowed_metric_codes", "default_sort_priority", "tags", "status", "version", "updated_by", "updated_at"}),
	}).Create(&items).Error
}

func upsertSemanticCapabilities(db *gorm.DB, items []model.SemanticAnalysisCapability) error {
	if len(items) == 0 {
		return nil
	}
	return db.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "subject_type"}, {Name: "subject_key"}},
		DoUpdates: clause.AssignmentColumns([]string{"supports_value", "supports_trend", "supports_comparison", "supports_yo_y", "supports_mo_m", "supports_ranking", "supports_ratio", "supports_attribution", "supports_drilldown", "allowed_modes", "constraints_json", "status", "version", "updated_by", "updated_at"}),
	}).Create(&items).Error
}

func upsertSemanticPolicies(db *gorm.DB, items []model.SemanticInteractionPolicy) error {
	if len(items) == 0 {
		return nil
	}
	return db.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "policy_key"}},
		DoUpdates: clause.AssignmentColumns([]string{"scene_type", "answer_mode", "clarify_priority", "max_suggestions", "confidence_thresholds", "fallback_strategy", "policy_json", "status", "version", "updated_by", "updated_at"}),
	}).Create(&items).Error
}

func upsertSemanticActions(db *gorm.DB, items []model.SemanticAction) error {
	if len(items) == 0 {
		return nil
	}
	return db.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "action_code"}},
		DoUpdates: clause.AssignmentColumns([]string{"label", "source_scene_type", "target_scene_type", "source_constraints_json", "target_payload_template", "priority", "status", "version", "updated_by", "updated_at"}),
	}).Create(&items).Error
}

func ensureDimensionSeed(index map[string]*dimSeed, code, displayName string) *dimSeed {
	if existing, ok := index[code]; ok {
		if existing.DisplayName == "" && displayName != "" {
			existing.DisplayName = displayName
		}
		return existing
	}
	seed := &dimSeed{
		DisplayName: firstNonEmpty(displayName, code),
		Tags:        map[string]struct{}{},
	}
	index[code] = seed
	return seed
}

type dimSeed struct {
	DisplayName string
	Level       int
	Tags        map[string]struct{}
}

func inferAggregation(metric model.Metric) string {
	sql := strings.ToUpper(metric.StarRocksSQL)
	switch {
	case strings.Contains(sql, "COUNT("):
		return "COUNT"
	case strings.Contains(sql, "AVG("):
		return "AVG"
	case strings.Contains(sql, "MAX("):
		return "MAX"
	case strings.Contains(sql, "MIN("):
		return "MIN"
	default:
		return "SUM"
	}
}

func inferTimeGrain(frequency string) string {
	freq := strings.ToLower(strings.TrimSpace(frequency))
	switch {
	case strings.Contains(freq, "week"):
		return "week"
	case strings.Contains(freq, "month"):
		return "month"
	case strings.Contains(freq, "quarter"):
		return "quarter"
	case strings.Contains(freq, "year"):
		return "year"
	default:
		return "day"
	}
}

func inferChartType(metricName string) string {
	if strings.Contains(metricName, "率") || strings.Contains(metricName, "占比") {
		return "line"
	}
	return "line"
}

func resolveRecommendedDimensions(commonDimensions string, dimensionLookup map[string]string) model.StringArray {
	result := model.StringArray{}
	seen := map[string]struct{}{}
	for _, item := range splitCSV(commonDimensions) {
		code := item
		if mapped, ok := dimensionLookup[item]; ok && mapped != "" {
			code = mapped
		}
		if code == "" {
			continue
		}
		if _, ok := seen[code]; ok {
			continue
		}
		seen[code] = struct{}{}
		result = append(result, code)
	}
	return result
}

func inferPreferredFollowups(metric model.Metric) model.StringArray {
	base := []string{
		fmt.Sprintf("查看%s趋势", metric.Name),
		fmt.Sprintf("查看%s环比", metric.Name),
	}
	if strings.TrimSpace(metric.CommonDimensions) != "" {
		for _, dim := range splitCSV(metric.CommonDimensions) {
			base = append(base, fmt.Sprintf("查看各%s%s变化", dim, metric.Name))
		}
	}
	return uniqueStrings(base)
}

func collectMetricTags(metric model.Metric) model.StringArray {
	values := []string{}
	for _, item := range []string{metric.Domain, metric.Category1, metric.Category2, metric.Category3, metric.MetricType, metric.Unit} {
		item = strings.TrimSpace(item)
		if item != "" {
			values = append(values, item)
		}
	}
	return uniqueStrings(values)
}

func normalizeStatus(status string) int16 {
	switch strings.TrimSpace(status) {
	case "", "启用", "在用", "active":
		return 1
	default:
		return 1
	}
}

func inferHierarchyLevel(name string) int {
	switch {
	case strings.Contains(name, "一级"):
		return 1
	case strings.Contains(name, "二级"):
		return 2
	case strings.Contains(name, "三级"):
		return 3
	case strings.Contains(name, "四级"):
		return 4
	default:
		return 0
	}
}

func inferDimensionSortPriority(name string, level int) int {
	switch {
	case strings.Contains(name, "站点"):
		return 100
	case strings.Contains(name, "平台"):
		return 90
	case strings.Contains(name, "品类"):
		return 80 - level
	default:
		return 50
	}
}

func inferAllowedModes(metric model.Metric, ratioMetric, hasTrigger, allowsDrilldown bool) model.StringArray {
	modes := []string{"direct", "clarify"}
	if ratioMetric {
		modes = append(modes, "comparison")
	} else {
		modes = append(modes, "trend", "comparison")
	}
	if hasTrigger {
		modes = append(modes, "analyze")
	}
	if allowsDrilldown {
		modes = append(modes, "drilldown")
	}
	return uniqueStrings(modes)
}

func splitCSV(raw string) []string {
	normalized := strings.NewReplacer("，", ",", "、", ",", ";", ",", "；", ",").Replace(raw)
	parts := strings.Split(normalized, ",")
	out := make([]string, 0, len(parts))
	for _, item := range parts {
		item = strings.TrimSpace(item)
		if item != "" {
			out = append(out, item)
		}
	}
	return out
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func uniqueStrings(values []string) model.StringArray {
	result := model.StringArray{}
	seen := map[string]struct{}{}
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		result = append(result, value)
	}
	return result
}

func mapKeys(values map[string]struct{}) model.StringArray {
	result := make([]string, 0, len(values))
	for key := range values {
		result = append(result, key)
	}
	sort.Strings(result)
	return result
}

func dedupeActions(items []model.SemanticAction) []model.SemanticAction {
	result := make([]model.SemanticAction, 0, len(items))
	seen := map[string]struct{}{}
	for _, item := range items {
		if _, ok := seen[item.ActionCode]; ok {
			continue
		}
		seen[item.ActionCode] = struct{}{}
		result = append(result, item)
	}
	return result
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
