package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"

	"github.com/gin-gonic/gin"
	"github.com/lib/pq"
)

// GetAllMetrics 获取所有指标（供 AI 服务调用）
func GetAllMetrics(c *gin.Context) {
	var metrics []model.Metric
	postgres.Get().Where("status = ?", "在用").Find(&metrics)

	// 转换为简化格式供 AI 使用
	var result []map[string]interface{}
	for _, m := range metrics {
		result = append(result, map[string]interface{}{
			"id":                  m.ID,
			"metric_code":         m.MetricCode,
			"name":                m.Name,
			"name_en":             m.NameEn,
			"domain":              m.Domain,
			"category_1":          m.Category1,
			"category_2":          m.Category2,
			"category_3":          m.Category3,
			"metric_type":         m.MetricType,
			"business_definition": m.BusinessDefinition,
			"business_rule":       m.BusinessRule,
			"unit":                m.Unit,
			"common_dimensions":   m.CommonDimensions,
			"frequency":           m.Frequency,
			"technical_rule":      m.TechnicalRule,
			"starrocks_sql":       m.StarRocksSQL,
		})
	}

	response.Success(c, result)
}

// GetMetricMetadata 获取指标详情（供 AI 服务调用）
func GetMetricMetadata(c *gin.Context) {
	id := c.Param("id")
	var metric model.Metric

	if err := postgres.Get().First(&metric, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指标不存在")
		return
	}

	// 获取关联维度
	var dimensions []model.Dimension
	postgres.Get().Table("dimensions").
		Joins("JOIN metric_dimensions ON dimensions.id = metric_dimensions.dimension_id").
		Where("metric_dimensions.metric_id = ?", id).
		Find(&dimensions)

	// 返回扁平结构，与 GetAllMetrics 保持一致
	response.Success(c, gin.H{
		"id":                  metric.ID,
		"metric_code":         metric.MetricCode,
		"name":                metric.Name,
		"name_en":             metric.NameEn,
		"domain":              metric.Domain,
		"category_1":          metric.Category1,
		"category_2":          metric.Category2,
		"category_3":          metric.Category3,
		"metric_type":         metric.MetricType,
		"business_definition":   metric.BusinessDefinition,
		"business_rule":        metric.BusinessRule,
		"unit":                metric.Unit,
		"common_dimensions":    metric.CommonDimensions,
		"frequency":           metric.Frequency,
		"technical_rule":      metric.TechnicalRule,
		"starrocks_sql":       metric.StarRocksSQL,
		"dimensions":          dimensions,
	})
}

// GetAllDimensions 获取所有维度
func GetAllDimensions(c *gin.Context) {
	var dimensions []model.Dimension
	postgres.Get().Find(&dimensions)
	response.Success(c, dimensions)
}

// GetAllTerms 获取所有业务术语映射
func GetAllTerms(c *gin.Context) {
	var terms []model.BusinessTerm
	postgres.Get().Find(&terms)
	response.Success(c, terms)
}

// CreateTerm 创建业务术语
func CreateTerm(c *gin.Context) {
	var term model.BusinessTerm
	if err := c.ShouldBindJSON(&term); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Create(&term).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}

	response.Success(c, term)
}

// UpdateTerm 更新业务术语
func UpdateTerm(c *gin.Context) {
	id := c.Param("id")
	var term model.BusinessTerm

	if err := postgres.Get().First(&term, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "术语不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 处理 pq.StringArray 类型的更新（GORM 需要特殊处理）
	if syns, ok := updates["synonyms"]; ok {
		switch v := syns.(type) {
		case []interface{}:
			// JSON array -> pq.StringArray
			strArr := make(pq.StringArray, len(v))
			for i, item := range v {
				if s, ok := item.(string); ok {
					strArr[i] = s
				}
			}
			updates["synonyms"] = strArr
		case []string:
			updates["synonyms"] = pq.StringArray(v)
		}
	}

	if err := postgres.Get().Model(&term).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}

	response.Success(c, term)
}

// DeleteTerm 删除业务术语
func DeleteTerm(c *gin.Context) {
	id := c.Param("id")
	postgres.Get().Delete(&model.BusinessTerm{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}
