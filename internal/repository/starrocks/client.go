package starrocks

import (
	"database/sql"
	"fmt"

	"dev_metric/config"

	_ "github.com/go-sql-driver/mysql"
)

var db *sql.DB

// Init 初始化 StarRocks 连接
func Init(cfg *config.StarRocksConfig) error {
	dsn := cfg.DSN()
	var err error
	db, err = sql.Open("mysql", dsn)
	if err != nil {
		return fmt.Errorf("连接 StarRocks 失败: %w", err)
	}

	if err := db.Ping(); err != nil {
		return fmt.Errorf("StarRocks Ping 失败: %w", err)
	}

	return nil
}

// Get 获取 StarRocks 数据库连接
func Get() *sql.DB {
	return db
}

// Close 关闭连接
func Close() error {
	if db != nil {
		return db.Close()
	}
	return nil
}

// Query 执行查询并返回结果
func Query(sqlStr string, args ...interface{}) ([]map[string]interface{}, error) {
	rows, err := db.Query(sqlStr, args...)
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
			row[col] = val
		}
		results = append(results, row)
	}

	return results, nil
}
