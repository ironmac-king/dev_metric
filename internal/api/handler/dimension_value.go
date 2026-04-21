package handler

import (
	"dev_metric/internal/repository/starrocks"
	"dev_metric/pkg/response"
	"fmt"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
)

// SearchDimensionValues 搜索维度值
// GET /api/v1/dimension-values/search?query=有线&dimension_field=GROUP_3&limit=5
// GET /api/v1/dimension-values/search?dimension_field=GROUP_3&limit=50 (query为空时返回该field下所有值)
func SearchDimensionValues(c *gin.Context) {
	query := c.Query("query")
	dimensionField := c.Query("dimension_field")
	limitStr := c.DefaultQuery("limit", "5")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 5
	}
	if limit > 100 {
		limit = 100 // 提高限制以便获取更多值
	}

	// 构建 SQL 查询
	var sql string
	if query == "" {
		// query为空时，返回指定dimension_field下所有值（按频次排序）
		sql = fmt.Sprintf(
			`SELECT dimension_field, dimension_value, dimension_value_pinyin, frequency, 'exact' as match_type
			FROM ids.dim_value_mapping
			WHERE dimension_field = '%s'
			ORDER BY frequency DESC
			LIMIT %d`,
			dimensionField, limit)
	} else {
		sql = buildDimValueSearchSQL(query, dimensionField, limit)
	}

	// 执行查询
	results, err := starrocks.QueryRaw(sql)
	if err != nil {
		response.Error(c, response.CodeInternalError, fmt.Sprintf("查询失败: %v", err))
		return
	}

	// 转换结果格式
	data := make([]map[string]interface{}, 0, len(results))
	for _, row := range results {
		item := map[string]interface{}{
			"dimension_field":  row["dimension_field"],
			"dimension_value":  row["dimension_value"],
			"match_type":      row["match_type"],
		}
		// 可选字段
		if v, ok := row["dimension_value_pinyin"]; ok {
			item["dimension_value_pinyin"] = v
		}
		if v, ok := row["frequency"]; ok {
			item["frequency"] = v
		}
		data = append(data, item)
	}

	response.Success(c, data)
}

// IncrementFrequency 增加维度值频次
// POST /api/v1/dimension-values/frequency
func IncrementFrequency(c *gin.Context) {
	var req struct {
		DimensionField string `json:"dimension_field" binding:"required"`
		DimensionValue string `json:"dimension_value" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误：dimension_field 和 dimension_value 不能为空")
		return
	}

	// 构建更新 SQL
	sql := fmt.Sprintf(
		`UPDATE ids.dim_value_mapping
		SET frequency = frequency + 1, last_used = NOW()
		WHERE dimension_field = '%s' AND dimension_value = '%s'`,
		req.DimensionField, req.DimensionValue,
	)

	_, err := starrocks.QueryRaw(sql)
	if err != nil {
		// 忽略更新失败，不影响主流程
		c.JSON(http.StatusOK, gin.H{
			"code":    0,
			"message": "success",
			"data":    nil,
		})
		return
	}

	response.Success(c, nil)
}

// buildDimValueSearchSQL 构建维度值搜索 SQL
// 分层匹配：精确匹配 > 前缀匹配 > 模糊匹配
// 如果有精确匹配，只返回精确匹配（避免 SKU=10116 时出现 10116JP 等候选）
func buildDimValueSearchSQL(query, dimensionField string, limit int) string {
	// 转义 query 中的特殊字符
	escapedQuery := query

	// 构建 WHERE 条件
	whereClause := ""
	if dimensionField != "" {
		whereClause = fmt.Sprintf(" AND dimension_field = '%s'", dimensionField)
	}

	// 精确匹配
	exactSQL := fmt.Sprintf(
		`SELECT dimension_field, dimension_value, dimension_value_pinyin, frequency, 'exact' as match_type
		FROM ids.dim_value_mapping
		WHERE dimension_value = '%s'%s`,
		escapedQuery, whereClause)

	// 前缀匹配
	prefixSQL := fmt.Sprintf(
		`SELECT dimension_field, dimension_value, dimension_value_pinyin, frequency, 'prefix' as match_type
		FROM ids.dim_value_mapping
		WHERE dimension_value LIKE '%s%%' AND dimension_value != '%s'%s`,
		escapedQuery, escapedQuery, whereClause)

	// 模糊匹配
	fuzzySQL := fmt.Sprintf(
		`SELECT dimension_field, dimension_value, dimension_value_pinyin, frequency, 'fuzzy' as match_type
		FROM ids.dim_value_mapping
		WHERE dimension_value LIKE '%%%s%%' AND dimension_value NOT LIKE '%s%%' AND dimension_value != '%s'%s`,
		escapedQuery, escapedQuery, escapedQuery, whereClause)

	// 拼音匹配
	pinyinSQL := fmt.Sprintf(
		`SELECT dimension_field, dimension_value, dimension_value_pinyin, frequency, 'fuzzy' as match_type
		FROM ids.dim_value_mapping
		WHERE dimension_value_pinyin LIKE '%%%s%%'%s`,
		escapedQuery, whereClause)

	// 策略：如果有精确匹配结果，只返回精确匹配；否则返回其他匹配
	// 使用子查询：如果精确匹配数 > 0，只返回精确匹配；否则返回所有匹配
	sql := fmt.Sprintf(`
		SELECT dimension_field, dimension_value, dimension_value_pinyin, frequency, match_type FROM (
			SELECT dimension_field, dimension_value, dimension_value_pinyin, frequency, match_type,
				CASE WHEN match_type = 'exact' THEN 0 ELSE 1 END as priority
			FROM (
				%s
				UNION ALL %s
				UNION ALL %s
				UNION ALL %s
			) t
		) combined
		ORDER BY priority, frequency DESC
		LIMIT %d`,
		exactSQL, prefixSQL, fuzzySQL, pinyinSQL, limit)

	return sql
}
