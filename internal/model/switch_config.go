package model

import (
    "time"
)

// TriggerSwitch 触发器开关配置
type TriggerSwitch struct {
    ID           uint      `json:"id" gorm:"primaryKey"`
    TriggerType  string    `json:"trigger_type" gorm:"size:32;not null;uniqueIndex"`
    SwitchStatus string    `json:"switch_status" gorm:"size:16;not null;default:'enabled'"`
    GrayRatio    *int      `json:"gray_ratio" gorm:"default:100"`
    SwitchReason string    `json:"switch_reason" gorm:"size:256"`
    Operator     string    `json:"operator" gorm:"size:64"`
    SwitchedAt   time.Time `json:"switched_at"`
    CreatedAt    time.Time `json:"created_at"`
}

func (TriggerSwitch) TableName() string {
    return "trigger_switches"
}
