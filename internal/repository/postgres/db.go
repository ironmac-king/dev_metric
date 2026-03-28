package postgres

import (
	"dev_metric/config"
	"dev_metric/internal/model"
	"fmt"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var db *gorm.DB

func Init(cfg *config.DatabaseConfig) error {
	var err error
	dsn := cfg.DSN()
	db, err = gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		return fmt.Errorf("连接 PostgreSQL 失败: %w", err)
	}

	// 自动迁移表结构
	if err := autoMigrate(); err != nil {
		return fmt.Errorf("自动迁移表结构失败: %w", err)
	}

	return nil
}

func autoMigrate() error {
	return db.AutoMigrate(
		&model.Metric{},
		&model.AlertRule{},
		&model.AlertRecord{},
		&model.LLMConfig{},
		&model.Dimension{},
		&model.BusinessTerm{},
		&model.MetricDimension{},
		&model.User{},
		&model.RefreshTokenBlacklist{},
		&model.SQLAuditLog{},
		&model.IntentTemplate{},
		&model.SQLTemplate{},
	)
}

func Get() *gorm.DB {
	return db
}

// Close 关闭数据库连接
func Close() error {
	sqlDB, err := db.DB()
	if err != nil {
		return err
	}
	return sqlDB.Close()
}
