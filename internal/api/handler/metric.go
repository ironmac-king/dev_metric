package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/repository/starrocks"
	"dev_metric/internal/service"
	"dev_metric/pkg/response"
	"fmt"
	"strconv"

	"github.com/gin-gonic/gin"
)

// auditService 审计服务实例
var auditService = service.NewSQLAuditService()

// ListMetrics 获取指标列表
func ListMetrics(c *gin.Context) {
	var metrics []model.Metric
	var total int64

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	// 分类筛选
	domain := c.Query("domain")
	category1 := c.Query("category_1")
	category2 := c.Query("category_2")
	status := c.Query("status")

	db := postgres.Get().Model(&model.Metric{})

	if domain != "" {
		db = db.Where("domain = ?", domain)
	}
	if category1 != "" {
		db = db.Where("category_1 = ?", category1)
	}
	if category2 != "" {
		db = db.Where("category_2 = ?", category2)
	}
	if status != "" {
		db = db.Where("status = ?", status)
	}

	db.Count(&total)
	db.Offset((page - 1) * pageSize).Limit(pageSize).Find(&metrics)

	response.Page(c, metrics, total, page, pageSize)
}

// GetMetric 获取指标详情
func GetMetric(c *gin.Context) {
	id := c.Param("id")
	var metric model.Metric

	if err := postgres.Get().First(&metric, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指标不存在")
		return
	}

	response.Success(c, metric)
}

// CreateMetric 创建指标
func CreateMetric(c *gin.Context) {
	var metric model.Metric
	if err := c.ShouldBindJSON(&metric); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Create(&metric).Error; err != nil {
		// 审计日志：创建失败
		auditService.LogSQL(getUserID(c), "CREATE metric", nil, 1, err.Error(), c.ClientIP())
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}

	// 审计日志：创建成功
	auditService.LogMetricCreate(getUserID(c), metric.ID, metric.Name, c.ClientIP())
	response.Success(c, metric)
}

// UpdateMetric 更新指标
func UpdateMetric(c *gin.Context) {
	id := c.Param("id")
	var metric model.Metric

	if err := postgres.Get().First(&metric, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指标不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&metric).Updates(updates).Error; err != nil {
		// 审计日志：更新失败
		auditService.LogSQL(getUserID(c), "UPDATE metric", nil, 1, err.Error(), c.ClientIP())
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}

	// 审计日志：更新成功
	changes := ""
	for k, v := range updates {
		if changes != "" {
			changes += ", "
		}
		changes += k + "=" + fmt.Sprintf("%v", v)
	}
	auditService.LogMetricUpdate(getUserID(c), metric.ID, changes, c.ClientIP())
	response.Success(c, metric)
}

// DeleteMetric 删除指标
func DeleteMetric(c *gin.Context) {
	id := c.Param("id")

	// 先获取指标信息用于审计日志
	var metric model.Metric
	if err := postgres.Get().First(&metric, id).Error; err == nil {
		// 审计日志：删除成功
		auditService.LogMetricDelete(getUserID(c), metric.ID, c.ClientIP())
	}

	if err := postgres.Get().Delete(&model.Metric{}, id).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}

	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetMetricData 获取指标趋势数据
func GetMetricData(c *gin.Context) {
	id := c.Param("id")
	var metric model.Metric

	if err := postgres.Get().First(&metric, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指标不存在")
		return
	}

	// 从 StarRocks 查询数据
	if metric.StarRocksSQL == "" {
		response.Error(c, response.CodeBadRequest, "该指标未配置查询SQL")
		return
	}

	data, err := starrocks.Query(metric.StarRocksSQL)
	if err != nil {
		response.Error(c, response.CodeInternalError, "查询失败: "+err.Error())
		return
	}

	response.Success(c, gin.H{
		"metric": metric,
		"data":   data,
	})
}

// ImportMetrics 导入指标字典 Excel
func ImportMetrics(c *gin.Context) {
	// TODO: 实现 Excel 导入逻辑
	response.Error(c, response.CodeInternalError, "Excel 导入功能开发中")
}
