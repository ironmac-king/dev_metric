package model

import (
	"time"
)

// PromptConfig Prompt配置
type PromptConfig struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	Name        string    `json:"name" gorm:"size:64;uniqueIndex"` // 如 "nl2structure", "sql_generation"
	Description string    `json:"description" gorm:"type:text"`
	PromptText  string    `json:"prompt_text" gorm:"type:text"`
	Variables   string    `json:"variables" gorm:"type:jsonb"` // JSON array: ["intent", "metric_name"]
	Category    string    `json:"category" gorm:"size:32;default:general"` // nl2structure/sql_generation/decision_analysis/general
	Version     int       `json:"version" gorm:"default:1"`
	Status      int16     `json:"status" gorm:"default:1"` // 1=启用 0=停用
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

func (PromptConfig) TableName() string {
	return "prompt_configs"
}

// PromptConfigVersion Prompt配置版本历史
type PromptConfigVersion struct {
	ID           uint      `json:"id" gorm:"primaryKey"`
	ConfigID     uint      `json:"config_id" gorm:"index"`
	Version      int       `json:"version"`
	PromptText   string    `json:"prompt_text" gorm:"type:text"`
	ChangeReason string    `json:"change_reason" gorm:"type:text"`
	CreatedBy    string    `json:"created_by" gorm:"size:64"`
	CreatedAt    time.Time `json:"created_at"`
}

func (PromptConfigVersion) TableName() string {
	return "prompt_config_versions"
}
