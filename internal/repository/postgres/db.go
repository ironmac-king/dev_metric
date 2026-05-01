package postgres

import (
	"dev_metric/config"
	"dev_metric/internal/model"
	"fmt"
	"strconv"
	"strings"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var db *gorm.DB

// VectorDB 包装 gorm.DB 用于向量搜索
type VectorDB struct {
	*gorm.DB
}

func Init(cfg *config.DatabaseConfig) error {
	var err error
	dsn := cfg.DSN()
	db, err = gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		return fmt.Errorf("连接 PostgreSQL 失败: %w", err)
	}

	// 设置客户端编码为 UTF-8
	db.Exec("SET client_encoding TO 'UTF8'")

	// 自动迁移表结构
	if err := autoMigrate(); err != nil {
		return fmt.Errorf("自动迁移表结构失败: %w", err)
	}

	return nil
}

// InitWithSeed 初始化数据库并填充预置数据
func InitWithSeed(cfg *config.DatabaseConfig) error {
	if err := Init(cfg); err != nil {
		return err
	}
	// 填充公式语法预置数据
	if err := SeedFormulaSyntaxConfigs(db); err != nil {
		return fmt.Errorf("填充公式语法预置数据失败: %w", err)
	}
	return nil
}

func autoMigrate() error {
	return db.AutoMigrate(
		// NOTE: model.Metric 已包含 164 条生产数据，不再自动迁移，避免 ALTER TABLE 锁表
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
		&model.DimensionConfig{},
		&model.IntentFeedback{},
		// 智能问数 Dashboard 相关
		&model.AskShortcutQuestion{},
		&model.AskFavorite{},
		&model.AskSessionSummary{},
		&model.AskQueryStat{},
		&model.AskUserPreference{},
		&model.AskMessage{},
		// 公式语法配置
		&model.FormulaSyntaxConfig{},
		// 问数分析日志
		&model.AskAnalysisLog{},
		// 槽位追问配置
		&model.SlotDefinition{},
		&model.SlotDependency{},
		&model.SlotRelation{},
		// 独立语义层
		&model.SemanticMetric{},
		&model.SemanticDimension{},
		&model.SemanticAnalysisCapability{},
		&model.SemanticInteractionPolicy{},
		&model.SemanticAction{},
		&model.SemanticSnapshot{},
		&model.SemanticSnapshotAudit{},
	)
}

func Get() *gorm.DB {
	return db
}

// SetForTest temporarily overrides the global DB handle for tests.
func SetForTest(testDB *gorm.DB) func() {
	previous := db
	db = testDB
	return func() {
		db = previous
	}
}

// GetVectorDB 返回 VectorDB 实例用于向量搜索
func GetVectorDB() *VectorDB {
	return &VectorDB{db}
}

// Close 关闭数据库连接
func Close() error {
	sqlDB, err := db.DB()
	if err != nil {
		return err
	}
	return sqlDB.Close()
}

// SearchIntentEmbeddings 搜索相似意图向量（使用余弦距离）
func (db *VectorDB) SearchIntentEmbeddings(queryEmbedding []float64, topK int) ([]model.IntentEmbedding, error) {
	var results []model.IntentEmbedding

	// 将 []float64 转换为 pgvector 格式
	embeddingStr := formatVectorForPostgres(queryEmbedding)

	sql := `
        SELECT id, intent_id, intent_type, text, embedding, updated_at,
               1 - (embedding <=> ?::vector) AS similarity
        FROM intent_embeddings
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> ?::vector
        LIMIT ?
    `

	rows, err := db.Raw(sql, embeddingStr, embeddingStr, topK).Rows()
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var item model.IntentEmbedding
		var similarity float64
		if err := rows.Scan(&item.ID, &item.IntentID, &item.IntentType, &item.Text, &item.Embedding, &item.UpdatedAt, &similarity); err != nil {
			return nil, err
		}
		results = append(results, item)
	}

	return results, nil
}

// SearchMetricEmbeddings 搜索相似指标向量
func (db *VectorDB) SearchMetricEmbeddings(queryEmbedding []float64, topK int) ([]model.MetricEmbedding, error) {
	var results []model.MetricEmbedding

	embeddingStr := formatVectorForPostgres(queryEmbedding)

	sql := `
        SELECT id, metric_id, metric_code, text, embedding, updated_at,
               1 - (embedding <=> ?::vector) AS similarity
        FROM metric_embeddings
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> ?::vector
        LIMIT ?
    `

	rows, err := db.Raw(sql, embeddingStr, embeddingStr, topK).Rows()
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var item model.MetricEmbedding
		var similarity float64
		if err := rows.Scan(&item.ID, &item.MetricID, &item.MetricCode, &item.Text, &item.Embedding, &item.UpdatedAt, &similarity); err != nil {
			return nil, err
		}
		results = append(results, item)
	}

	return results, nil
}

// formatVectorForPostgres 将 []float64 转换为 pgvector 格式字符串 "[0.1,0.2,0.3]"
func formatVectorForPostgres(v []float64) string {
	if len(v) == 0 {
		return "[]"
	}
	parts := make([]string, len(v))
	for i, f := range v {
		parts[i] = strconv.FormatFloat(f, 'f', 6, 64)
	}
	return "[" + strings.Join(parts, ",") + "]"
}
