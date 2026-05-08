package handler

import (
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

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
		APIURL    string `json:"api_url" binding:"required"`
		APIKey    string `json:"api_key" binding:"required"`
		ModelName string `json:"model_name" binding:"required"`
		Provider  string `json:"provider"` // optional: tencent/openai/anthropic
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 实际测试连接 - 调用 /v1/models 验证凭证
	testURL := strings.TrimSuffix(req.APIURL, "/") + "/v1/models"

	client := &http.Client{Timeout: 10 * time.Second}
	reqHTTP, _ := http.NewRequest("GET", testURL, nil)
	reqHTTP.Header.Set("Authorization", "Bearer "+req.APIKey)
	reqHTTP.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(reqHTTP)
	if err != nil {
		response.Success(c, gin.H{
			"status":  "error",
			"message": "连接失败: " + err.Error(),
		})
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	// 检查是否有错误标记（腾讯云等可能返回 200 但 body 里是错误）
	if strings.Contains(string(body), `"error"`) || strings.Contains(string(body), `"Error"`) {
		response.Success(c, gin.H{
			"status":  "error",
			"message": fmt.Sprintf("认证失败: %s", string(body)),
		})
		return
	}

	if resp.StatusCode == 200 {
		response.Success(c, gin.H{
			"status":  "ok",
			"message": "连接测试成功",
		})
	} else {
		response.Success(c, gin.H{
			"status":  "error",
			"message": fmt.Sprintf("HTTP %d: %s", resp.StatusCode, string(body)),
		})
	}
}
