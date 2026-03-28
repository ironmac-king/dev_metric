package model

import (
	"database/sql/driver"
	"encoding/json"
	"errors"
	"time"
)

// ClarificationFeedback 追问反馈表
type ClarificationFeedback struct {
	ID                 int64           `json:"id" gorm:"primaryKey;autoIncrement"`
	SessionID          string          `json:"session_id" gorm:"index;size:64"`
	TurnIndex          int             `json:"turn_index"`
	FeedbackSource     string          `json:"feedback_source" gorm:"size:32;default:user"` // auto/user/silent
	FailReason         string          `json:"fail_reason" gorm:"size:64"`                  // no_metric/no_data/sql_error等
	ContextSnapshot    JSONMap         `json:"context_snapshot" gorm:"type:jsonb"`         // 上下文快照
	RawLLMOutput       string          `json:"raw_llm_output" gorm:"type:text"`            // LLM原始输出
	UserActions        JSONMap         `json:"user_actions" gorm:"type:jsonb"`              // 用户行为
	ClarificationType  string          `json:"clarification_type" gorm:"size:32"`          // 追问类型
	ClarificationQ     string          `json:"clarification_question" gorm:"column:clarification_question"` // 追问内容
	UserResponse       string          `json:"user_response" gorm:"type:text"`             // 用户响应
	Feedback           int             `json:"feedback" gorm:"default:0"`                  // 1=👍 -1=👎 0=无反馈
	MissingFields      JSONMap         `json:"missing_fields" gorm:"type:jsonb"`           // 缺失字段
	MetricID           *int            `json:"metric_id"`
	IntentConfidence   *float64        `json:"intent_confidence" gorm:"type:decimal(3,2)"` // 意图置信度
	ResponseTimeMs     *int            `json:"response_time_ms"`                          // 响应耗时
	CreatedAt          time.Time       `json:"created_at" gorm:"autoCreateTime"`
}

// TableName 指定表名
func (ClarificationFeedback) TableName() string {
	return "clarification_feedback"
}

// JSONMap JSONB类型
type JSONMap map[string]interface{}

// Scan 实现 sql.Scanner 接口
func (j *JSONMap) Scan(value interface{}) error {
	if value == nil {
		*j = nil
		return nil
	}
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, j)
}

// Value 实现 driver.Valuer 接口
func (j JSONMap) Value() (driver.Value, error) {
	if j == nil {
		return nil, nil
	}
	return json.Marshal(j)
}
