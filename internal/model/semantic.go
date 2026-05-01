package model

import (
	"database/sql/driver"
	"encoding/json"
	"errors"
	"time"
)

// JSONBlob 用于存储任意 JSON 文档并在运行时反序列化。
type JSONBlob []byte

func (j *JSONBlob) Scan(value interface{}) error {
	if value == nil {
		*j = nil
		return nil
	}
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	*j = append((*j)[:0], bytes...)
	return nil
}

func (j JSONBlob) Value() (driver.Value, error) {
	if len(j) == 0 {
		return nil, nil
	}
	return []byte(j), nil
}

func (j JSONBlob) MarshalJSON() ([]byte, error) {
	if len(j) == 0 {
		return []byte("null"), nil
	}
	return j, nil
}

func (j *JSONBlob) UnmarshalJSON(data []byte) error {
	if len(data) == 0 || string(data) == "null" {
		*j = nil
		return nil
	}
	*j = append((*j)[:0], data...)
	return nil
}

func (j JSONBlob) Unmarshal(target interface{}) error {
	if len(j) == 0 {
		return nil
	}
	return json.Unmarshal(j, target)
}

// SemanticMetric 语义指标主表。
type SemanticMetric struct {
	ID                        uint        `json:"id" gorm:"primaryKey"`
	MetricCode                string      `json:"metric_code" gorm:"size:64;uniqueIndex"`
	DisplayName               string      `json:"display_name" gorm:"size:128"`
	BusinessSummary           string      `json:"business_summary" gorm:"type:text"`
	DefaultAggregation        string      `json:"default_aggregation" gorm:"size:32"`
	DefaultTimeGrain          string      `json:"default_time_grain" gorm:"size:32"`
	DefaultChartType          string      `json:"default_chart_type" gorm:"size:32"`
	RecommendedDimensionCodes StringArray `json:"recommended_dimension_codes" gorm:"type:jsonb"`
	PreferredFollowups        StringArray `json:"preferred_followups" gorm:"type:jsonb"`
	Tags                      StringArray `json:"tags" gorm:"type:jsonb"`
	Status                    int16       `json:"status" gorm:"default:1"`
	Version                   int         `json:"version" gorm:"default:1"`
	UpdatedBy                 string      `json:"updated_by" gorm:"size:64"`
	CreatedAt                 time.Time   `json:"created_at"`
	UpdatedAt                 time.Time   `json:"updated_at"`
}

func (SemanticMetric) TableName() string {
	return "semantic_metrics"
}

// SemanticDimension 语义维度主表。
type SemanticDimension struct {
	ID                  uint        `json:"id" gorm:"primaryKey"`
	DimensionCode       string      `json:"dimension_code" gorm:"size:64;uniqueIndex"`
	DisplayName         string      `json:"display_name" gorm:"size:128"`
	HierarchyLevel      int         `json:"hierarchy_level" gorm:"default:0"`
	ParentDimensionCode string      `json:"parent_dimension_code" gorm:"size:64"`
	SupportsGroupBy     bool        `json:"supports_group_by" gorm:"default:true"`
	SupportsFilter      bool        `json:"supports_filter" gorm:"default:true"`
	SupportsDrilldown   bool        `json:"supports_drilldown" gorm:"default:false"`
	DrilldownTargets    StringArray `json:"drilldown_targets" gorm:"type:jsonb"`
	AllowedMetricCodes  StringArray `json:"allowed_metric_codes" gorm:"type:jsonb"`
	DefaultSortPriority int         `json:"default_sort_priority" gorm:"default:0"`
	Tags                StringArray `json:"tags" gorm:"type:jsonb"`
	Status              int16       `json:"status" gorm:"default:1"`
	Version             int         `json:"version" gorm:"default:1"`
	UpdatedBy           string      `json:"updated_by" gorm:"size:64"`
	CreatedAt           time.Time   `json:"created_at"`
	UpdatedAt           time.Time   `json:"updated_at"`
}

func (SemanticDimension) TableName() string {
	return "semantic_dimensions"
}

// SemanticAnalysisCapability 分析能力矩阵。
type SemanticAnalysisCapability struct {
	ID                  uint        `json:"id" gorm:"primaryKey"`
	SubjectType         string      `json:"subject_type" gorm:"size:32;index:idx_semantic_capability_subject,unique"`
	SubjectKey          string      `json:"subject_key" gorm:"size:64;index:idx_semantic_capability_subject,unique"`
	SupportsValue       bool        `json:"supports_value" gorm:"default:true"`
	SupportsTrend       bool        `json:"supports_trend" gorm:"default:false"`
	SupportsComparison  bool        `json:"supports_comparison" gorm:"default:false"`
	SupportsYoY         bool        `json:"supports_yoy" gorm:"default:false"`
	SupportsMoM         bool        `json:"supports_mom" gorm:"default:false"`
	SupportsRanking     bool        `json:"supports_ranking" gorm:"default:false"`
	SupportsRatio       bool        `json:"supports_ratio" gorm:"default:false"`
	SupportsAttribution bool        `json:"supports_attribution" gorm:"default:false"`
	SupportsDrilldown   bool        `json:"supports_drilldown" gorm:"default:false"`
	AllowedModes        StringArray `json:"allowed_modes" gorm:"type:jsonb"`
	ConstraintsJSON     JSONMap     `json:"constraints_json" gorm:"type:jsonb"`
	Status              int16       `json:"status" gorm:"default:1"`
	Version             int         `json:"version" gorm:"default:1"`
	UpdatedBy           string      `json:"updated_by" gorm:"size:64"`
	CreatedAt           time.Time   `json:"created_at"`
	UpdatedAt           time.Time   `json:"updated_at"`
}

func (SemanticAnalysisCapability) TableName() string {
	return "semantic_analysis_capabilities"
}

// SemanticInteractionPolicy 交互策略。
type SemanticInteractionPolicy struct {
	ID                   uint      `json:"id" gorm:"primaryKey"`
	PolicyKey            string    `json:"policy_key" gorm:"size:64;uniqueIndex"`
	SceneType            string    `json:"scene_type" gorm:"size:32;index"`
	AnswerMode           string    `json:"answer_mode" gorm:"size:32"`
	ClarifyPriority      int       `json:"clarify_priority" gorm:"default:0"`
	MaxSuggestions       int       `json:"max_suggestions" gorm:"default:3"`
	ConfidenceThresholds JSONMap   `json:"confidence_thresholds" gorm:"type:jsonb"`
	FallbackStrategy     string    `json:"fallback_strategy" gorm:"size:64"`
	PolicyJSON           JSONMap   `json:"policy_json" gorm:"type:jsonb"`
	Status               int16     `json:"status" gorm:"default:1"`
	Version              int       `json:"version" gorm:"default:1"`
	UpdatedBy            string    `json:"updated_by" gorm:"size:64"`
	CreatedAt            time.Time `json:"created_at"`
	UpdatedAt            time.Time `json:"updated_at"`
}

func (SemanticInteractionPolicy) TableName() string {
	return "semantic_interaction_policies"
}

// SemanticAction 下钻与动作配置。
type SemanticAction struct {
	ID                    uint      `json:"id" gorm:"primaryKey"`
	ActionCode            string    `json:"action_code" gorm:"size:64;uniqueIndex"`
	Label                 string    `json:"label" gorm:"size:128"`
	SourceSceneType       string    `json:"source_scene_type" gorm:"size:32;index"`
	TargetSceneType       string    `json:"target_scene_type" gorm:"size:32"`
	SourceConstraintsJSON JSONMap   `json:"source_constraints_json" gorm:"type:jsonb"`
	TargetPayloadTemplate JSONMap   `json:"target_payload_template" gorm:"type:jsonb"`
	Priority              int       `json:"priority" gorm:"default:0"`
	Status                int16     `json:"status" gorm:"default:1"`
	Version               int       `json:"version" gorm:"default:1"`
	UpdatedBy             string    `json:"updated_by" gorm:"size:64"`
	CreatedAt             time.Time `json:"created_at"`
	UpdatedAt             time.Time `json:"updated_at"`
}

func (SemanticAction) TableName() string {
	return "semantic_actions"
}

// SemanticSnapshot 运行时快照。
type SemanticSnapshot struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	SnapshotID  string    `json:"snapshot_id" gorm:"size:64;uniqueIndex"`
	Version     string    `json:"version" gorm:"size:64;index"`
	CompiledAt  time.Time `json:"compiled_at"`
	CompiledBy  string    `json:"compiled_by" gorm:"size:64"`
	Payload     JSONBlob  `json:"payload" gorm:"type:jsonb"`
	Status      string    `json:"status" gorm:"size:16;index"` // draft / active / archived
	ReleaseNote string    `json:"release_note" gorm:"type:text"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

func (SemanticSnapshot) TableName() string {
	return "semantic_snapshots"
}

// SemanticSnapshotAudit 快照治理审计事件。
type SemanticSnapshotAudit struct {
	ID           uint      `json:"id" gorm:"primaryKey"`
	SnapshotID   string    `json:"snapshot_id" gorm:"size:64;index"`
	EventType    string    `json:"event_type" gorm:"size:32;index"`
	BeforeStatus string    `json:"before_status" gorm:"size:16"`
	AfterStatus  string    `json:"after_status" gorm:"size:16"`
	Operator     string    `json:"operator" gorm:"size:64"`
	Note         string    `json:"note" gorm:"type:text"`
	DetailJSON   JSONMap   `json:"detail_json" gorm:"type:jsonb"`
	CreatedAt    time.Time `json:"created_at"`
}

func (SemanticSnapshotAudit) TableName() string {
	return "semantic_snapshot_audits"
}
