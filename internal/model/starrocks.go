package model

import (
	"time"
)

// StarRocksConfig StarRocks 连接配置
type StarRocksConfig struct {
	ID           uint      `json:"id" gorm:"primaryKey"`
	Name         string    `json:"name" gorm:"size:64;uniqueIndex"`
	Host         string    `json:"host" gorm:"size:128"`
	Port         int       `json:"port" gorm:"default:9030"`
	User         string    `json:"user" gorm:"size:64"`
	Password     string    `json:"password" gorm:"size:256"`
	Database     string    `json:"database" gorm:"size:64"`
	Timeout      int       `json:"timeout" gorm:"default:10"`       // 连接超时（秒）
	QueryTimeout int       `json:"query_timeout" gorm:"default:30"`  // 查询超时（秒）
	IsActive     int16     `json:"is_active" gorm:"default:1"`      // 0=禁用 1=启用
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

func (StarRocksConfig) TableName() string {
	return "starrocks_configs"
}

// StarRocksConfigTestRequest 测试连接请求
type StarRocksConfigTestRequest struct {
	Host     string `json:"host" binding:"required"`
	Port     int    `json:"port" binding:"required"`
	User     string `json:"user" binding:"required"`
	Password string `json:"password"`
	Database string `json:"database" binding:"required"`
	Timeout  int    `json:"timeout"`
}

// StarRocksConfigUpdateRequest 更新配置请求
type StarRocksConfigUpdateRequest struct {
	Name         string `json:"name" binding:"required"`
	Host         string `json:"host" binding:"required"`
	Port         int    `json:"port" binding:"required"`
	User         string `json:"user" binding:"required"`
	Password     string `json:"password"`
	Database     string `json:"database" binding:"required"`
	Timeout      int    `json:"timeout"`
	QueryTimeout int    `json:"query_timeout"`
	IsActive     int16  `json:"is_active"`
}
