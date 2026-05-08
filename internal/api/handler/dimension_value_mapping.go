package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/repository/starrocks"
	"dev_metric/pkg/response"
	"fmt"
	"log"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
)

// SyncDimensionValuesBySQL 执行自定义 SQL 从 StarRocks 批量同步维度值
// POST /api/v1/dimension-values/sync/sql
// Body: { "sql": "SELECT 'ids.IDS_AMZ_COMPREHENSIVE_DI' as table_name, 'FSITECODE' as column_name, '站点编码' as dimension_type, FSITECODE as dimension_value FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE LENGTH(FSITECODE) > 0" }
func SyncDimensionValuesBySQL(c *gin.Context) {
	var req struct {
		SQL string `json:"sql" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误：sql 不能为空")
		return
	}

	// 执行 SQL
	rows, err := starrocks.QueryRaw(req.SQL)
	if err != nil {
		log.Printf("[SyncDimensionValuesBySQL] StarRocks 查询失败: %v", err)
		response.Error(c, response.CodeInternalError, fmt.Sprintf("StarRocks 查询失败: %v", err))
		return
	}

	db := postgres.Get()
	synced := 0
	skipped := 0

	for _, row := range rows {
		// 提取各列值
		tableName := getString(row, "table_name")
		columnName := getString(row, "column_name")
		dimensionType := getString(row, "dimension_type")
		dimensionValue := getString(row, "dimension_value")

		if tableName == "" || columnName == "" || dimensionValue == "" {
			skipped++
			continue
		}

		// Upsert
		var existing model.DimensionValueMapping
		err := db.Where("table_name = ? AND column_name = ? AND dimension_value = ?",
			tableName, columnName, dimensionValue).First(&existing).Error
		if err == nil {
			// 已存在，更新 frequency
			db.Model(&existing).Updates(map[string]interface{}{
				"frequency": existing.Frequency + 1,
			})
		} else {
			item := model.DimensionValueMapping{
				StarRocksTable: tableName,
				ColumnName:    columnName,
				DimensionType: dimensionType,
				DimensionValue: dimensionValue,
				Frequency:     1,
				Status:        1,
			}
			if err := db.Create(&item).Error; err != nil {
				log.Printf("[SyncDimensionValuesBySQL] 创建记录失败: %v", err)
				skipped++
				continue
			}
		}
		synced++
	}

	log.Printf("[SyncDimensionValuesBySQL] 同步完成: 新增=%d, 跳过=%d, 总行数=%d", synced, skipped, len(rows))
	response.Success(c, gin.H{
		"synced":  synced,
		"skipped": skipped,
		"total":   len(rows),
	})
}

// getString 安全获取 map 中的字符串值
func getString(row map[string]interface{}, key string) string {
	if v, ok := row[key].(string); ok {
		return strings.TrimSpace(v)
	}
	// 处理可能的字节数组
	if v, ok := row[key].([]byte); ok {
		return strings.TrimSpace(string(v))
	}
	return ""
}

// SyncDimensionValues 从 StarRocks 同步维度值到 PostgreSQL
// POST /api/v1/dimension-values/sync
// Body: { "column_name": "GROUP_2", "table_name": "ids.IDS_AMZ_COMPREHENSIVE_DI" }
func SyncDimensionValues(c *gin.Context) {
	var req struct {
		ColumnName string `json:"column_name" binding:"required"`
		TableName  string `json:"table_name"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误：column_name 不能为空")
		return
	}
	if req.TableName == "" {
		req.TableName = "ids.IDS_AMZ_COMPREHENSIVE_DI"
	}

	// 1. 从 StarRocks 查询该列的所有非空维度值
	sql := fmt.Sprintf(
		`SELECT DISTINCT %s AS dimension_value
		FROM %s
		WHERE %s IS NOT NULL AND %s != ''
		LIMIT 5000`,
		req.ColumnName, req.TableName, req.ColumnName, req.ColumnName)

	rows, err := starrocks.QueryRaw(sql)
	if err != nil {
		log.Printf("[SyncDimensionValues] StarRocks 查询失败: %v", err)
		response.Error(c, response.CodeInternalError, fmt.Sprintf("StarRocks 查询失败: %v", err))
		return
	}

	db := postgres.Get()
	synced := 0
	skipped := 0

	for _, row := range rows {
		val, ok := row["dimension_value"].(string)
		if !ok || val == "" {
			skipped++
			continue
		}

		// 查找该 column_name 对应的 dimension_type
		var mapping model.DimensionValueMapping
		err := db.Where("column_name = ? AND dimension_value = ''", req.ColumnName).
			Order("id ASC").First(&mapping).Error
		if err != nil {
			log.Printf("[SyncDimensionValues] 查找 dimension_type 失败 column=%s: %v", req.ColumnName, err)
			skipped++
			continue
		}

		// Upsert: 插入或更新（按 table_name + column_name + dimension_value）
		var existing model.DimensionValueMapping
		err = db.Where("star_rocks_table = ? AND column_name = ? AND dimension_value = ?",
			req.TableName, req.ColumnName, val).First(&existing).Error
		if err == nil {
			// 已存在，更新 frequency
			db.Model(&existing).Updates(map[string]interface{}{
				"frequency": existing.Frequency + 1,
			})
		} else {
			// 新增
			item := model.DimensionValueMapping{
				StarRocksTable: req.TableName,
				ColumnName:     req.ColumnName,
				DimensionType:  mapping.DimensionType,
				DimensionValue: val,
				Frequency:      1,
				Status:         1,
			}
			if err := db.Create(&item).Error; err != nil {
				log.Printf("[SyncDimensionValues] 创建记录失败: %v", err)
				skipped++
				continue
			}
		}
		synced++
	}

	log.Printf("[SyncDimensionValues] 同步完成: column=%s, 新增=%d, 跳过=%d", req.ColumnName, synced, skipped)
	response.Success(c, gin.H{
		"column_name": req.ColumnName,
		"synced":      synced,
		"skipped":     skipped,
		"total":       len(rows),
	})
}

// ListDimensionValueMappings 获取维度值映射列表（新版，统一表）
// GET /api/v1/dimension-values?column_name=GROUP_2&dimension_type=二级品类&dimension_value=智能云存储&page=1&page_size=20
func ListDimensionValueMappings(c *gin.Context) {
	columnName := c.Query("column_name")
	dimensionType := c.Query("dimension_type")
	dimensionValue := c.Query("dimension_value")
	tableName := c.Query("table_name")
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 200 {
		pageSize = 20
	}
	offset := (page - 1) * pageSize

	db := postgres.Get().Model(&model.DimensionValueMapping{})
	if columnName != "" {
		db = db.Where("column_name = ?", columnName)
	}
	if dimensionType != "" {
		db = db.Where("dimension_type = ?", dimensionType)
	}
	if dimensionValue != "" {
		db = db.Where("dimension_value LIKE ?", "%"+dimensionValue+"%")
	}
	if tableName != "" {
		db = db.Where("table_name = ?", tableName)
	}

	var total int64
	db.Count(&total)

	var list []model.DimensionValueMapping
	db.Order("id ASC").Offset(offset).Limit(pageSize).Find(&list)

	response.Success(c, gin.H{
		"list": list,
		"pagination": gin.H{
			"page":        page,
			"page_size":   pageSize,
			"total":       total,
			"total_pages": (total + int64(pageSize) - 1) / int64(pageSize),
		},
	})
}

// GetDimensionValueMapping 获取单个
func GetDimensionValueMapping(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var item model.DimensionValueMapping
	if err := postgres.Get().First(&item, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "记录不存在")
		return
	}
	response.Success(c, item)
}

// UpdateDimensionValueMapping 更新记录
func UpdateDimensionValueMapping(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var item model.DimensionValueMapping
	if err := postgres.Get().First(&item, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "记录不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 禁止修改 id、table_name、column_name、dimension_value（核心字段）
	for _, blocked := range []string{"id", "table_name", "column_name", "dimension_value"} {
		delete(updates, blocked)
	}

	if err := postgres.Get().Model(&item).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	response.Success(c, item)
}

// DeleteDimensionValueMapping 删除记录
func DeleteDimensionValueMapping(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	if err := postgres.Get().Delete(&model.DimensionValueMapping{}, id).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}
	response.SuccessWithMessage(c, "删除成功", nil)
}

// BatchDeleteDimensionValues 批量删除维度值
// DELETE /api/v1/dimension-values/batch
func BatchDeleteDimensionValues(c *gin.Context) {
	var req struct {
		IDs []uint `json:"ids" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误：ids 不能为空")
		return
	}

	if err := postgres.Get().Delete(&model.DimensionValueMapping{}, req.IDs).Error; err != nil {
		response.Error(c, response.CodeInternalError, "批量删除失败")
		return
	}
	response.SuccessWithMessage(c, fmt.Sprintf("成功删除 %d 条记录", len(req.IDs)), nil)
}

// GetDimensionColumns 获取所有维度列（按 column_name 分组）
// GET /api/v1/dimension-values/columns
func GetDimensionColumns(c *gin.Context) {
	tableName := c.Query("table_name")

	db := postgres.Get().Model(&model.DimensionValueMapping{})
	if tableName != "" {
		db = db.Where("table_name = ?", tableName)
	}

	var results []struct {
		ColumnName    string `json:"column_name"`
		DimensionType string `json:"dimension_type"`
		TableName    string `json:"table_name"`
		Count        int64  `json:"value_count"`
	}
	db.Select("column_name, dimension_type, table_name, COUNT(*) as count").
		Where("dimension_value != ''").
		Group("column_name, dimension_type, table_name").
		Order("column_name ASC").
		Scan(&results)

	response.Success(c, results)
}

// SearchDimensionValuesNew 基于 PostgreSQL 新表的维度值搜索
// GET /api/v1/dimension-values/search-new?query=智能&column_name=GROUP_2&limit=20
func SearchDimensionValuesNew(c *gin.Context) {
	query := c.Query("query")
	columnName := c.Query("column_name")
	dimensionType := c.Query("dimension_type")
	tableName := c.DefaultQuery("table_name", "ids.IDS_AMZ_COMPREHENSIVE_DI")
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	if limit <= 0 || limit > 100 {
		limit = 20
	}

	db := postgres.Get().Model(&model.DimensionValueMapping{}).
		Where("table_name = ?", tableName).
		Where("dimension_value != ''")

	if columnName != "" {
		db = db.Where("column_name = ?", columnName)
	}
	if dimensionType != "" {
		db = db.Where("dimension_type = ?", dimensionType)
	}
	if query != "" {
		db = db.Where("dimension_value LIKE ?", "%"+query+"%")
	}

	var results []model.DimensionValueMapping
	db.Order("frequency DESC, id ASC").Limit(limit).Find(&results)

	data := make([]map[string]interface{}, 0, len(results))
	for _, r := range results {
		data = append(data, map[string]interface{}{
			"id":             r.ID,
			"column_name":    r.ColumnName,
			"dimension_type": r.DimensionType,
			"dimension_value": r.DimensionValue,
			"table_name":    r.StarRocksTable,
			"frequency":     r.Frequency,
			"status":        r.Status,
		})
	}
	response.Success(c, data)
}

// IncrementFrequencyByID 通过 ID 增加频次
// POST /api/v1/dimension-values/frequency/id
func IncrementFrequencyByID(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var item model.DimensionValueMapping
	if err := postgres.Get().First(&item, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "记录不存在")
		return
	}
	postgres.Get().Model(&item).Update("frequency", item.Frequency+1)
	response.Success(c, nil)
}

// IncrementFrequency 增加维度值频次（兼容旧 API，改造为更新 PostgreSQL）
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

	var item model.DimensionValueMapping
	err := postgres.Get().Where("column_name = ? AND dimension_value = ?",
		req.DimensionField, req.DimensionValue).First(&item).Error
	if err != nil {
		response.Success(c, nil) // 找不到不报错，静默忽略
		return
	}
	postgres.Get().Model(&item).Update("frequency", item.Frequency+1)
	response.Success(c, nil)
}

// --- 兼容旧 API：SearchDimensionValues 改造为查 PostgreSQL ---
// SearchDimensionValues 搜索维度值（改造后查 PostgreSQL 新表，不查 StarRocks）
// GET /api/v1/dimension-values/search?query=智能&column_name=GROUP_2&limit=5
func SearchDimensionValues(c *gin.Context) {
	query := c.Query("query")
	columnName := c.Query("dimension_field") // 兼容旧参数名
	if columnName == "" {
		columnName = c.Query("column_name")
	}
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "5"))
	if limit <= 0 || limit > 100 {
		limit = 5
	}

	db := postgres.Get().Model(&model.DimensionValueMapping{}).
		Where("dimension_value != ''")

	if columnName != "" {
		db = db.Where("column_name = ?", columnName)
	}
	if query != "" {
		// 分层匹配：精确 > 前缀 > 模糊
		query = strings.TrimSpace(query)
		// 先找精确匹配
		var exact model.DimensionValueMapping
		err := db.Where("dimension_value = ?", query).First(&exact).Error
		if err == nil {
			// 有精确匹配，只返回精确匹配
			response.Success(c, []map[string]interface{}{
				{
					"column_name":     exact.ColumnName,
					"dimension_value": exact.DimensionValue,
					"match_type":     "exact",
					"frequency":      exact.Frequency,
				},
			})
			return
		}
		// 无精确匹配，走模糊
		db = db.Where("dimension_value LIKE ?", "%"+query+"%")
	}

	var results []model.DimensionValueMapping
	db.Order("frequency DESC, id ASC").Limit(limit).Find(&results)

	data := make([]map[string]interface{}, 0, len(results))
	for _, r := range results {
		matchType := "fuzzy"
		if strings.HasPrefix(r.DimensionValue, query) {
			matchType = "prefix"
		}
		data = append(data, map[string]interface{}{
			"column_name":     r.ColumnName,
			"dimension_value": r.DimensionValue,
			"match_type":     matchType,
			"frequency":      r.Frequency,
		})
	}
	response.Success(c, data)
}

// --- 兼容旧 API：ListDimensionTypeMappings 改造为从新表聚合 ---
// ListDimensionTypeMappings 获取所有维度类型映射（从 dim_value_mapping 聚合）
func ListDimensionTypeMappings(c *gin.Context) {
	var results []struct {
		ColumnName    string `json:"column_name" gorm:"column:column_name"`
		DimensionType string `json:"dimension_type" gorm:"column:dimension_type"`
		TableName    string `json:"table_name" gorm:"column:table_name"`
	}
	postgres.Get().Model(&model.DimensionValueMapping{}).
		Select("DISTINCT column_name, dimension_type, table_name").
		Order("column_name ASC").
		Scan(&results)
	response.Success(c, results)
}

// GetDimensionTypeMappingsByType 根据类型名获取映射（从新表）
func GetDimensionTypeMappingsByType(c *gin.Context) {
	dimensionType := c.Query("dimension_type")
	query := postgres.Get().Model(&model.DimensionValueMapping{}).
		Select("DISTINCT column_name, dimension_type, table_name")
	if dimensionType != "" {
		query = query.Where("LOWER(dimension_type) LIKE LOWER(?)", "%"+dimensionType+"%")
	}
	var results []struct {
		ColumnName    string `json:"column_name" gorm:"column:column_name"`
		DimensionType string `json:"dimension_type" gorm:"column:dimension_type"`
		TableName    string `json:"table_name" gorm:"column:table_name"`
	}
	query.Scan(&results)
	response.Success(c, results)
}

// --- 兼容旧 API：ListDimensionConfigs 改造为从新表聚合 ---
// ListDimensionConfigs 获取维度配置列表（从 dim_value_mapping 聚合）
func ListDimensionConfigs(c *gin.Context) {
	tableName := c.Query("table_name")

	db := postgres.Get().Model(&model.DimensionValueMapping{}).
		Select("DISTINCT table_name, column_name, dimension_type")
	if tableName != "" {
		db = db.Where("LOWER(table_name) = LOWER(?)", tableName)
	}

	var results []struct {
		TableName     string `json:"table_name" gorm:"column:table_name"`
		ColumnName    string `json:"column_name" gorm:"column:column_name"`
		DimensionType string `json:"dimension_type" gorm:"column:dimension_type"`
	}
	db.Order("column_name ASC").Scan(&results)
	response.Success(c, results)
}
