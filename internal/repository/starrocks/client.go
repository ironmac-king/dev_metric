package starrocks

import (
	"context"
	"database/sql"
	"fmt"
	"sync"
	"time"

	"dev_metric/config"
	"dev_metric/internal/cache"

	_ "github.com/go-sql-driver/mysql"
)

var (
	db       *sql.DB
	mu       sync.RWMutex
	queryTTL = 5 * time.Minute // 查询缓存 TTL
)

// Init 初始化 StarRocks 连接
func Init(cfg *config.StarRocksConfig) error {
	mu.Lock()
	defer mu.Unlock()

	var err error
	db, err = newConnection(cfg)
	if err != nil {
		return err
	}

	return nil
}

// newConnection 创建新连接
func newConnection(cfg *config.StarRocksConfig) (*sql.DB, error) {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&timeout=10s&readTimeout=30s",
		cfg.User, cfg.Password, cfg.Host, cfg.Port, cfg.Database)

	newDB, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, fmt.Errorf("连接 StarRocks 失败: %w", err)
	}

	// 设置连接池参数
	newDB.SetMaxOpenConns(50)
	newDB.SetMaxIdleConns(10)
	newDB.SetConnMaxLifetime(5 * time.Minute)

	if err := newDB.Ping(); err != nil {
		newDB.Close()
		return nil, fmt.Errorf("StarRocks Ping 失败: %w", err)
	}

	return newDB, nil
}

// Get 获取 StarRocks 数据库连接
func Get() *sql.DB {
	mu.RLock()
	defer mu.RUnlock()
	return db
}

// Close 关闭连接
func Close() error {
	mu.Lock()
	defer mu.Unlock()
	if db != nil {
		return db.Close()
	}
	return nil
}

// Reconnect 重新连接（用于配置变更）
func Reconnect(cfg *config.StarRocksConfig) error {
	mu.Lock()
	defer mu.Unlock()

	oldDB := db
	newDB, err := newConnection(cfg)
	if err != nil {
		return err
	}

	if oldDB != nil {
		oldDB.Close()
	}
	db = newDB
	return nil
}

// QueryResult 查询结果（带缓存）
type QueryResult struct {
	Data      []map[string]interface{} `json:"data"`
	Timestamp time.Time                `json:"timestamp"`
	Cached    bool                     `json:"cached"`
}

// Query 执行查询并缓存结果
func Query(ctx context.Context, sqlStr string, metricID uint) (*QueryResult, error) {
	// 先尝试从缓存获取
	cacheKey := cache.MetricDataKey(metricID)
	var cachedResult QueryResult
	if err := cache.GetJSON(ctx, cacheKey, &cachedResult); err == nil {
		cachedResult.Cached = true
		return &cachedResult, nil
	}

	// 缓存不存在，查询 StarRocks
	mu.RLock()
	defer mu.RUnlock()

	if db == nil {
		return nil, fmt.Errorf("StarRocks 未连接")
	}

	rows, err := db.QueryContext(ctx, sqlStr)
	if err != nil {
		return nil, fmt.Errorf("StarRocks 查询失败: %w", err)
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return nil, fmt.Errorf("获取列名失败: %w", err)
	}

	var results []map[string]interface{}
	for rows.Next() {
		values := make([]interface{}, len(columns))
		valuePtrs := make([]interface{}, len(columns))
		for i := range values {
			valuePtrs[i] = &values[i]
		}

		if err := rows.Scan(valuePtrs...); err != nil {
			return nil, fmt.Errorf("扫描行失败: %w", err)
		}

		row := make(map[string]interface{})
		for i, col := range columns {
			val := values[i]
			// 转换字节数组为字符串
			if b, ok := val.([]byte); ok {
				row[col] = string(b)
			} else {
				row[col] = val
			}
		}
		results = append(results, row)
	}

	result := &QueryResult{
		Data:      results,
		Timestamp: time.Now(),
		Cached:    false,
	}

	// 写入缓存
	if err := cache.SetJSON(ctx, cacheKey, result, queryTTL); err != nil {
		// 缓存写入失败不影响返回
		fmt.Printf("缓存写入失败: %v\n", err)
	}

	return result, nil
}

// QueryAlertRule 执行查询并缓存结果（按告警规则 ID 缓存）
func QueryAlertRule(ctx context.Context, sqlStr string, ruleID uint) (*QueryResult, error) {
	// 先尝试从缓存获取
	cacheKey := cache.AlertRuleDataKey(ruleID)
	var cachedResult QueryResult
	if err := cache.GetJSON(ctx, cacheKey, &cachedResult); err == nil {
		cachedResult.Cached = true
		return &cachedResult, nil
	}

	// 缓存不存在，查询 StarRocks
	mu.RLock()
	defer mu.RUnlock()

	if db == nil {
		return nil, fmt.Errorf("StarRocks 未连接")
	}

	rows, err := db.QueryContext(ctx, sqlStr)
	if err != nil {
		return nil, fmt.Errorf("StarRocks 查询失败: %w", err)
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return nil, fmt.Errorf("获取列名失败: %w", err)
	}

	var results []map[string]interface{}
	for rows.Next() {
		values := make([]interface{}, len(columns))
		valuePtrs := make([]interface{}, len(columns))
		for i := range values {
			valuePtrs[i] = &values[i]
		}

		if err := rows.Scan(valuePtrs...); err != nil {
			return nil, fmt.Errorf("扫描行失败: %w", err)
		}

		row := make(map[string]interface{})
		for i, col := range columns {
			val := values[i]
			if b, ok := val.([]byte); ok {
				row[col] = string(b)
			} else {
				row[col] = val
			}
		}
		results = append(results, row)
	}

	result := &QueryResult{
		Data:      results,
		Timestamp: time.Now(),
		Cached:    false,
	}

	// 写入缓存
	if err := cache.SetJSON(ctx, cacheKey, result, queryTTL); err != nil {
		fmt.Printf("缓存写入失败: %v\n", err)
	}

	return result, nil
}

// QueryRaw 执行查询（不走缓存，用于测试连接等）
func QueryRaw(sqlStr string) ([]map[string]interface{}, error) {
	mu.RLock()
	defer mu.RUnlock()

	if db == nil {
		return nil, fmt.Errorf("StarRocks 未连接")
	}

	rows, err := db.Query(sqlStr)
	if err != nil {
		return nil, fmt.Errorf("StarRocks 查询失败: %w", err)
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return nil, fmt.Errorf("获取列名失败: %w", err)
	}

	var results []map[string]interface{}
	for rows.Next() {
		values := make([]interface{}, len(columns))
		valuePtrs := make([]interface{}, len(columns))
		for i := range values {
			valuePtrs[i] = &values[i]
		}

		if err := rows.Scan(valuePtrs...); err != nil {
			return nil, fmt.Errorf("扫描行失败: %w", err)
		}

		row := make(map[string]interface{})
		for i, col := range columns {
			val := values[i]
			if b, ok := val.([]byte); ok {
				row[col] = string(b)
			} else {
				row[col] = val
			}
		}
		results = append(results, row)
	}

	return results, nil
}

// InvalidateCache 删除指标缓存
func InvalidateCache(ctx context.Context, metricID uint) error {
	return cache.Delete(ctx, cache.MetricDataKey(metricID))
}
