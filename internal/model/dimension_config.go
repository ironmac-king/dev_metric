package model

import (
    "time"
)

// DimensionConfig StarRocks 表的维度配置
type DimensionConfig struct {
    ID              uint      `json:"id" gorm:"primaryKey"`
    StarrocksTable  string    `json:"table_name" gorm:"column:table_name;size:128;index:idx_table_dimension,unique"`
    DimensionName   string    `json:"dimension_name" gorm:"size:64;index:idx_table_dimension,unique"`
    ColumnName      string    `json:"column_name" gorm:"size:64"`
    DimensionValues string    `json:"dimension_values" gorm:"type:text"` // JSON array: ["北京","上海"]
    Status          int16     `json:"status" gorm:"default:1"`          // 1=启用 0=停用
    CreatedAt       time.Time `json:"created_at"`
    UpdatedAt       time.Time `json:"updated_at"`
}

func (DimensionConfig) TableName() string {
    return "dimension_configs"
}
