package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"

	"github.com/gin-gonic/gin"
)

// FormulaSyntaxConfig CRUD

// ListFormulaSyntaxConfigs 获取所有公式语法配置
func ListFormulaSyntaxConfigs(c *gin.Context) {
	var configs []model.FormulaSyntaxConfig
	postgres.Get().Find(&configs)
	response.Success(c, configs)
}

// GetFormulaSyntaxConfig 获取单个公式语法配置
func GetFormulaSyntaxConfig(c *gin.Context) {
	id := c.Param("id")
	var config model.FormulaSyntaxConfig
	if err := postgres.Get().First(&config, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}
	response.Success(c, config)
}

// CreateFormulaSyntaxConfig 创建公式语法配置
func CreateFormulaSyntaxConfig(c *gin.Context) {
	var config model.FormulaSyntaxConfig
	if err := c.ShouldBindJSON(&config); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&config).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "formula_syntax_config", "CREATE", c.ClientIP())
	response.Success(c, config)
}

// UpdateFormulaSyntaxConfig 更新公式语法配置
func UpdateFormulaSyntaxConfig(c *gin.Context) {
	id := c.Param("id")
	var config model.FormulaSyntaxConfig
	if err := postgres.Get().First(&config, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&config).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "formula_syntax_config", "UPDATE", c.ClientIP())
	response.Success(c, config)
}

// DeleteFormulaSyntaxConfig 删除公式语法配置
func DeleteFormulaSyntaxConfig(c *gin.Context) {
	id := c.Param("id")
	var config model.FormulaSyntaxConfig
	if err := postgres.Get().First(&config, id).Error; err == nil {
		// 审计日志
		nlpAuditService.LogNLPConfig(getUserID(c), "formula_syntax_config", "DELETE", c.ClientIP())
	}
	postgres.Get().Delete(&model.FormulaSyntaxConfig{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetEnabledFormulaSyntaxConfigs 获取所有启用的公式语法配置（供 AI 服务调用）
func GetEnabledFormulaSyntaxConfigs(c *gin.Context) {
	var configs []model.FormulaSyntaxConfig
	postgres.Get().Where("status = ?", 1).Order("priority DESC").Find(&configs)
	response.Success(c, configs)
}
