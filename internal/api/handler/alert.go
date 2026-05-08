package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/service"
	"dev_metric/pkg/response"
	"strconv"

	"github.com/gin-gonic/gin"
)

// alertAuditService 审计服务实例
var alertAuditService = service.NewSQLAuditService()

// ListAlertRules 获取告警规则列表
func ListAlertRules(c *gin.Context) {
	var rules []model.AlertRule
	var total int64

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	db := postgres.Get().Model(&model.AlertRule{})

	if metricID := c.Query("metric_id"); metricID != "" {
		db = db.Where("metric_id = ?", metricID)
	}

	db.Count(&total)
	db.Offset((page - 1) * pageSize).Limit(pageSize).Find(&rules)

	response.Page(c, rules, total, page, pageSize)
}

// CreateAlertRule 创建告警规则
func CreateAlertRule(c *gin.Context) {
	var rule model.AlertRule
	if err := c.ShouldBindJSON(&rule); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Create(&rule).Error; err != nil {
		// 审计日志：创建失败
		alertAuditService.LogAlertConfig(getUserID(c), 0, "CREATE", c.ClientIP())
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}

	// 审计日志：创建成功
	alertAuditService.LogAlertConfig(getUserID(c), rule.ID, "CREATE", c.ClientIP())
	response.Success(c, rule)
}

// UpdateAlertRule 更新告警规则
func UpdateAlertRule(c *gin.Context) {
	id := c.Param("id")
	var rule model.AlertRule

	if err := postgres.Get().First(&rule, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "规则不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&rule).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}

	// 审计日志：更新成功
	alertAuditService.LogAlertConfig(getUserID(c), rule.ID, "UPDATE", c.ClientIP())
	response.Success(c, rule)
}

// DeleteAlertRule 删除告警规则
func DeleteAlertRule(c *gin.Context) {
	id := c.Param("id")

	// 先获取规则信息用于审计日志
	var rule model.AlertRule
	if err := postgres.Get().First(&rule, id).Error; err == nil {
		// 审计日志：删除成功
		alertAuditService.LogAlertConfig(getUserID(c), rule.ID, "DELETE", c.ClientIP())
	}

	if err := postgres.Get().Delete(&model.AlertRule{}, id).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}

	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetAlertHistory 获取告警历史
func GetAlertHistory(c *gin.Context) {
	id := c.Param("id")
	var records []model.AlertRecord

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	var total int64
	postgres.Get().Model(&model.AlertRecord{}).Where("rule_id = ?", id).Count(&total)
	postgres.Get().Where("rule_id = ?", id).Offset((page-1)*pageSize).Limit(pageSize).Find(&records)

	response.Page(c, records, total, page, pageSize)
}
