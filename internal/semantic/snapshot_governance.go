package semantic

import (
	"encoding/json"
	"fmt"
	"sort"
	"time"

	"dev_metric/internal/model"

	"gorm.io/gorm"
)

type SnapshotDiffSection struct {
	Added   []string `json:"added"`
	Removed []string `json:"removed"`
	Changed []string `json:"changed"`
}

type SnapshotDiffReport struct {
	FromSnapshotID string                         `json:"from_snapshot_id"`
	ToSnapshotID   string                         `json:"to_snapshot_id"`
	Summary        map[string]int                 `json:"summary"`
	Sections       map[string]SnapshotDiffSection `json:"sections"`
}

func CompareSnapshots(from, to model.SemanticSnapshot) (SnapshotDiffReport, error) {
	var fromPayload map[string]any
	var toPayload map[string]any

	if err := unmarshalSnapshotPayload(from.Payload, &fromPayload); err != nil {
		return SnapshotDiffReport{}, err
	}
	if err := unmarshalSnapshotPayload(to.Payload, &toPayload); err != nil {
		return SnapshotDiffReport{}, err
	}

	sections := []string{
		"metrics",
		"dimensions",
		"capabilities",
		"interaction_policies",
		"actions",
		"term_index",
		"metric_aliases",
	}

	report := SnapshotDiffReport{
		FromSnapshotID: from.SnapshotID,
		ToSnapshotID:   to.SnapshotID,
		Summary: map[string]int{
			"added":   0,
			"removed": 0,
			"changed": 0,
		},
		Sections: map[string]SnapshotDiffSection{},
	}

	for _, section := range sections {
		diff := comparePayloadSection(
			asStringMap(fromPayload[section]),
			asStringMap(toPayload[section]),
		)
		report.Sections[section] = diff
		report.Summary["added"] += len(diff.Added)
		report.Summary["removed"] += len(diff.Removed)
		report.Summary["changed"] += len(diff.Changed)
	}

	return report, nil
}

func RecordSnapshotAudit(
	db *gorm.DB,
	snapshotID string,
	eventType string,
	beforeStatus string,
	afterStatus string,
	operator string,
	note string,
	detail model.JSONMap,
) error {
	if db == nil {
		return fmt.Errorf("db is nil")
	}
	audit := model.SemanticSnapshotAudit{
		SnapshotID:   snapshotID,
		EventType:    eventType,
		BeforeStatus: beforeStatus,
		AfterStatus:  afterStatus,
		Operator:     operator,
		Note:         note,
		DetailJSON:   detail,
		CreatedAt:    time.Now().UTC(),
	}
	return db.Create(&audit).Error
}

func unmarshalSnapshotPayload(payload model.JSONBlob, target *map[string]any) error {
	if len(payload) == 0 {
		*target = map[string]any{}
		return nil
	}
	if err := json.Unmarshal(payload, target); err != nil {
		return fmt.Errorf("unmarshal snapshot payload failed: %w", err)
	}
	return nil
}

func comparePayloadSection(from, to map[string]json.RawMessage) SnapshotDiffSection {
	diff := SnapshotDiffSection{
		Added:   []string{},
		Removed: []string{},
		Changed: []string{},
	}

	for key, toValue := range to {
		fromValue, ok := from[key]
		if !ok {
			diff.Added = append(diff.Added, key)
			continue
		}
		if string(fromValue) != string(toValue) {
			diff.Changed = append(diff.Changed, key)
		}
	}
	for key := range from {
		if _, ok := to[key]; !ok {
			diff.Removed = append(diff.Removed, key)
		}
	}

	sort.Strings(diff.Added)
	sort.Strings(diff.Removed)
	sort.Strings(diff.Changed)
	return diff
}

func asStringMap(value any) map[string]json.RawMessage {
	result := map[string]json.RawMessage{}
	if value == nil {
		return result
	}
	rawMap, ok := value.(map[string]any)
	if !ok {
		return result
	}
	for key, item := range rawMap {
		raw, err := json.Marshal(item)
		if err != nil {
			continue
		}
		result[key] = raw
	}
	return result
}
