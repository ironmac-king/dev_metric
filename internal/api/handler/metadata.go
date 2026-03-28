package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"

	"github.com/gin-gonic/gin"
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

	response.Success(c, gin.H{
		"metric":     metric,
		"dimensions": dimensions,
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
