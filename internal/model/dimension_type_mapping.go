package model

import (
	"time"
)

// DimensionTypeMapping 全局维度类型到数据库列名的映射
// 例如：日期→FDATE，每天/每日/日→FDATE
type DimensionTypeMapping struct {
	ID           uint      `json:"id" gorm:"primaryKey"`
	DimensionType string   `json:"dimension_type" gorm:"size:64;uniqueIndex"` // 中文维度类型名，如"日期"
	ColumnName   string   `json:"column_name" gorm:"size:64"`               // 对应数据库列名，如"FDATE"
	Description  string   `json:"description" gorm:"size:256"`               // 描述
	Status       int16    `json:"status" gorm:"default:1"`                 // 1=启用 0=停用
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

func (DimensionTypeMapping) TableName() string {
	return "dimension_type_mappings"
}
