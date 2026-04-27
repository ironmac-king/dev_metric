package model

import (
    "time"
)

// OutputTemplate 输出模板配置
type OutputTemplate struct {
    ID              uint      `json:"id" gorm:"primaryKey"`
    TemplateKey     string    `json:"template_key" gorm:"size:64;not null;uniqueIndex"`
    TemplateType    string    `json:"template_type" gorm:"size:32;not null"`
    ContentTemplate string    `json:"content_template" gorm:"type:text;not null"`
    Params          JSONMap   `json:"params" gorm:"type:jsonb"`
    Enabled         *bool     `json:"enabled" gorm:"default:true"`
    Priority        int       `json:"priority" gorm:"default:0"`
    CreatedAt       time.Time `json:"created_at"`
    UpdatedAt       time.Time `json:"updated_at"`
}

func (OutputTemplate) TableName() string {
    return "output_templates"
}
