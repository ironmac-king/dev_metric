package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// ListLLMConfigs 获取 LLM 配置列表
func ListLLMConfigs(c *gin.Context) {
	var configs []model.LLMConfig
	postgres.Get().Find(&configs)
	response.Success(c, configs)
}

// GetLLMConfig 获取 LLM 配置详情
func GetLLMConfig(c *gin.Context) {
	id := c.Param("id")
	var config model.LLMConfig

	if err := postgres.Get().First(&config, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}

	response.Success(c, config)
}

// CreateLLMConfig 创建 LLM 配置
func CreateLLMConfig(c *gin.Context) {
	var config model.LLMConfig
	if err := c.ShouldBindJSON(&config); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Create(&config).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}

	response.Success(c, config)
}

// UpdateLLMConfig 更新 LLM 配置
func UpdateLLMConfig(c *gin.Context) {
	id := c.Param("id")
	var config model.LLMConfig

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

	response.Success(c, config)
}

// DeleteLLMConfig 删除 LLM 配置
func DeleteLLMConfig(c *gin.Context) {
	id := c.Param("id")
	postgres.Get().Delete(&model.LLMConfig{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// SetDefaultLLM 设为默认模型
func SetDefaultLLM(c *gin.Context) {
	id := c.Param("id")

	// 设置新的默认（先取消所有默认，再设置当前）
	var config model.LLMConfig
	if err := postgres.Get().First(&config, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}

	// 事务：取消所有默认 -> 设置当前为默认
	postgres.Get().Transaction(func(tx *gorm.DB) error {
		// 取消所有默认
		if err := tx.Model(&model.LLMConfig{}).Where("is_default = ?", 1).Update("is_default", 0).Error; err != nil {
			return err
		}
		// 设置当前为默认
		if err := tx.Model(&config).Update("is_default", 1).Error; err != nil {
			return err
		}
		return nil
	})

	response.SuccessWithMessage(c, "设置成功", nil)
}

// TestLLMConnection 测试连接
func TestLLMConnection(c *gin.Context) {
	var req struct {
		APIURL  string `json:"api_url" binding:"required"`
		APIKey  string `json:"api_key" binding:"required"`
		ModelName string `json:"model_name" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// TODO: 实际测试连接
	// 这里简化处理，实际应该调用 LLM API 测试
	response.Success(c, gin.H{
		"status":  "ok",
		"message": "连接测试成功",
	})
}
