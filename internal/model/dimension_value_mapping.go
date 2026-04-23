package model

import (
	"time"
)

// DimensionValueMapping 统一维度值映射表
// 由原来的 dimension_configs + dimension_type_mappings 合并而来
// 一行记录代表：一个 column_name 对应一个 dimension_type（dimension_value 为空时）
// 或者：一个 column_name 的具体 dimension_value（dimension_value 非空时，从 StarRocks 同步）
type DimensionValueMapping struct {
	ID             uint      `json:"id" gorm:"primaryKey"`
	StarRocksTable string    `json:"table_name" gorm:"column:table_name;size:128;not null;default:'ids.IDS_AMZ_COMPREHENSIVE_DI';index"`
	ColumnName     string    `json:"column_name" gorm:"size:64;not null;index"`
	DimensionType  string    `json:"dimension_type" gorm:"size:64;index"`
	DimensionValue string    `json:"dimension_value" gorm:"size:256;not null;default:''"`
	Frequency      int64     `json:"frequency" gorm:"default:0"`
	Status         int16     `json:"status" gorm:"default:1"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

func (DimensionValueMapping) TableName() string {
	return "dim_value_mapping"
}
