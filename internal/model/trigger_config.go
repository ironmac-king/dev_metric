package model

import (
	"time"
)

// AnalysisTriggerConfig 触发规则配置
type AnalysisTriggerConfig struct {
	ID               uint     `json:"id" gorm:"primaryKey"`
	TriggerType      string   `json:"trigger_type" gorm:"size:32;not null"`
	MetricCode       string   `json:"metric_code" gorm:"size:64"`
	Condition        JSONMap  `json:"condition" gorm:"type:jsonb;not null"`
	CampaignBuffers  JSONMap  `json:"campaign_buffers" gorm:"type:jsonb"`
	OutputTemplateID *int     `json:"output_template_id"`
	Enabled          *bool    `json:"enabled" gorm:"default:true"`
	Priority         int      `json:"priority" gorm:"default:0"`
	CreatedAt        time.Time `json:"created_at"`
	UpdatedAt        time.Time `json:"updated_at"`
}

func (AnalysisTriggerConfig) TableName() string {
	return "analysis_trigger_configs"
}
