package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/service"
	"dev_metric/pkg/response"

	"github.com/gin-gonic/gin"
)

// nlpAuditService 审计服务实例
var nlpAuditService = service.NewSQLAuditService()

// IntentTemplate CRUD

func ListIntentTemplates(c *gin.Context) {
	var templates []model.IntentTemplate
	postgres.Get().Find(&templates)
	response.Success(c, templates)
}

func GetIntentTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.IntentTemplate
	if err := postgres.Get().First(&tpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}
	response.Success(c, tpl)
}

func CreateIntentTemplate(c *gin.Context) {
	var tpl model.IntentTemplate
	if err := c.ShouldBindJSON(&tpl); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&tpl).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "intent_template", "CREATE", c.ClientIP())
	response.Success(c, tpl)
}

func UpdateIntentTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.IntentTemplate
	if err := postgres.Get().First(&tpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&tpl).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "intent_template", "UPDATE", c.ClientIP())
	response.Success(c, tpl)
}

func DeleteIntentTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.IntentTemplate
	if err := postgres.Get().First(&tpl, id).Error; err == nil {
		// 审计日志
		nlpAuditService.LogNLPConfig(getUserID(c), "intent_template", "DELETE", c.ClientIP())
	}
	postgres.Get().Delete(&model.IntentTemplate{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// SQLTemplate CRUD

func ListSQLTemplates(c *gin.Context) {
	var templates []model.SQLTemplate
	postgres.Get().Find(&templates)
	response.Success(c, templates)
}

func GetSQLTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.SQLTemplate
	if err := postgres.Get().First(&tpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}
	response.Success(c, tpl)
}

func CreateSQLTemplate(c *gin.Context) {
	var tpl model.SQLTemplate
	if err := c.ShouldBindJSON(&tpl); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&tpl).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "sql_template", "CREATE", c.ClientIP())
	response.Success(c, tpl)
}

func UpdateSQLTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.SQLTemplate
	if err := postgres.Get().First(&tpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&tpl).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "sql_template", "UPDATE", c.ClientIP())
	response.Success(c, tpl)
}

func DeleteSQLTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.SQLTemplate
	if err := postgres.Get().First(&tpl, id).Error; err == nil {
		// 审计日志
		nlpAuditService.LogNLPConfig(getUserID(c), "sql_template", "DELETE", c.ClientIP())
	}
	postgres.Get().Delete(&model.SQLTemplate{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetAllNLPTemplates 获取所有 NLP 模板（供 AI 服务调用）
func GetAllNLPTemplates(c *gin.Context) {
	var intentTemplates []model.IntentTemplate
	var sqlTemplates []model.SQLTemplate

	postgres.Get().Where("status = ?", 1).Find(&intentTemplates)
	postgres.Get().Where("status = ?", 1).Find(&sqlTemplates)

	response.Success(c, gin.H{
		"intent_templates": intentTemplates,
		"sql_templates":    sqlTemplates,
	})
}
