package model

import (
	"time"
)

// FormulaSyntaxConfig 公式语法配置
// 用于配置排名、排序、占比、累计等分析型查询的SQL片段模板
type FormulaSyntaxConfig struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	Name        string    `json:"name" gorm:"size:64;not null"`           // 规则名称，如"排名TOPN"
	Category    string    `json:"category" gorm:"size:32;not null;index"` // 分类，如"时间序列"、"排名分析"、"占比分析"
	IntentType  string    `json:"intent_type" gorm:"size:32;not null;index"` // 意图类型，如 query_ranking
	Keywords    string    `json:"keywords" gorm:"type:text"`             // 触发关键词（逗号分隔），如"排名前,前几名,Top"
	SQLPattern  string    `json:"sql_pattern" gorm:"type:text;not null"`   // SQL片段模板，如 "ORDER BY {metric} DESC LIMIT {n}"
	Description string    `json:"description" gorm:"type:text"`            // 说明
	Priority    int       `json:"priority" gorm:"default:0"`              // 优先级
	Status      int16     `json:"status" gorm:"default:1"`               // 状态 0=停用 1=启用
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

func (FormulaSyntaxConfig) TableName() string {
	return "formula_syntax_configs"
}
