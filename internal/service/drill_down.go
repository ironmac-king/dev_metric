package service

import (
	"fmt"
	"regexp"
	"strings"

	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
)

// DrillDownService 下钻服务
type DrillDownService struct{}

// NewDrillDownService 创建下钻服务
func NewDrillDownService() *DrillDownService {
	return &DrillDownService{}
}

// TransformSQLForDrillDown 将 SQL 改造成下钻维度
// 原始: SELECT SUM(sales) FROM table GROUP BY shop
// 单选: SELECT city_id, SUM(sales) FROM table GROUP BY city_id
// 多选: SELECT city_id, region, SUM(sales) FROM table GROUP BY city_id, region
func (s *DrillDownService) TransformSQLForDrillDown(sql string, tableName string, dimensionNames []string) (string, error) {
	if len(dimensionNames) == 0 {
		return sql, nil
	}

	// 1. 获取维度配置
	var configs []model.DimensionConfig
	err := postgres.Get().Where("starrocks_table = ? AND dimension_name IN ?", tableName, dimensionNames).Find(&configs).Error
	if err != nil {
		return "", fmt.Errorf("查询维度配置失败: %w", err)
	}

	// 构建 column_name 列表
	var columnNames []string
	for _, cfg := range configs {
		columnNames = append(columnNames, cfg.ColumnName)
	}

	// 2. 提取当前 GROUP BY 字段
	currentGroupBy := s.extractGroupBy(sql)

	// 3. 改造 SQL
	return s.buildDrillDownSQL(sql, columnNames, currentGroupBy)
}

// extractGroupBy 提取 SQL 中的 GROUP BY 字段
func (s *DrillDownService) extractGroupBy(sql string) string {
	// 匹配 GROUP BY xxx
	re := regexp.MustCompile(`(?i)GROUP\s+BY\s+([^\s;]+)`)
	matches := re.FindStringSubmatch(sql)
	if len(matches) > 1 {
		return matches[1]
	}
	return ""
}

// buildDrillDownSQL 构建下钻后的 SQL
func (s *DrillDownService) buildDrillDownSQL(originalSQL string, newColumns []string, currentGroupBy string) (string, error) {
	// 1. 移除现有的 GROUP BY 子句
	sql := s.removeGroupBy(originalSQL)

	// 2. 在 SELECT 中插入维度列
	// 找到 SELECT 和 FROM 之间的位置
	selectPattern := regexp.MustCompile(`(?i)(SELECT\s+)(.+?)(\s+FROM\s+)`)
	match := selectPattern.FindStringSubmatch(sql)
	if len(match) < 3 {
		return "", fmt.Errorf("无法解析 SQL 结构")
	}

	columnsPart := match[2]
	newColumnsStr := strings.Join(newColumns, ", ")

	// 如果原来 SELECT 中没有聚合函数，直接在开头添加维度列
	// 否则在聚合函数后面添加维度列
	newSelectPart := fmt.Sprintf("SELECT %s, %s FROM", newColumnsStr, columnsPart)
	sql = selectPattern.ReplaceAllString(sql, newSelectPart)

	// 3. 添加新的 GROUP BY
	if currentGroupBy != "" {
		// 如果有旧的 GROUP BY，替换掉
		sql = sql + " GROUP BY " + strings.Join(newColumns, ", ")
	} else {
		// 如果没有旧的 GROUP BY，追加
		hasGroupBy := regexp.MustCompile(`(?i)GROUP\s+BY`)
		if !hasGroupBy.MatchString(sql) {
			sql = sql + " GROUP BY " + strings.Join(newColumns, ", ")
		}
	}

	return sql, nil
}

// removeGroupBy 移除 SQL 中的 GROUP BY 子句
func (s *DrillDownService) removeGroupBy(sql string) string {
	// 移除 GROUP BY xxx
	re := regexp.MustCompile(`(?i)\s+GROUP\s+BY\s+[^\s;]+`)
	return re.ReplaceAllString(sql, "")
}

// GetTableNameFromSQL 从 SQL 中提取表名
func (s *DrillDownService) GetTableNameFromSQL(sql string) string {
	// 匹配 FROM table 或 FROM schema.table
	re := regexp.MustCompile(`(?i)FROM\s+([^\s;]+)`)
	matches := re.FindStringSubmatch(sql)
	if len(matches) > 1 {
		return matches[1]
	}
	return ""
}
