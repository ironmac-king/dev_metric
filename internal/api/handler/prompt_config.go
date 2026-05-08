package handler

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"time"

	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"

	"github.com/gin-gonic/gin"
)

// ListPromptConfigs 获取Prompt配置列表
func ListPromptConfigs(c *gin.Context) {
	category := c.Query("category")
	var configs []model.PromptConfig
	query := postgres.Get().Order("id ASC")
	if category != "" {
		query = query.Where("category = ?", category)
	}
	query.Find(&configs)
	response.Success(c, configs)
}

// GetPromptConfig 获取单个Prompt配置
func GetPromptConfig(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var config model.PromptConfig
	if err := postgres.Get().First(&config, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}
	response.Success(c, config)
}

// CreatePromptConfig 创建Prompt配置
func CreatePromptConfig(c *gin.Context) {
	var config model.PromptConfig
	if err := c.ShouldBindJSON(&config); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 创建版本记录
	version := model.PromptConfigVersion{
		ConfigID:     config.ID,
		Version:      1,
		PromptText:   config.PromptText,
		ChangeReason: "初始创建",
		CreatedBy:    "system",
	}

	tx := postgres.Get().Begin()
	if err := tx.Create(&config).Error; err != nil {
		tx.Rollback()
		log.Printf("CreatePromptConfig error: %v", err)
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}

	version.ConfigID = config.ID
	if err := tx.Create(&version).Error; err != nil {
		tx.Rollback()
		log.Printf("CreatePromptConfigVersion error: %v", err)
		response.Error(c, response.CodeInternalError, "创建版本记录失败")
		return
	}

	tx.Commit()
	response.Success(c, config)
}

// UpdatePromptConfig 更新Prompt配置
func UpdatePromptConfig(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var config model.PromptConfig
	if err := postgres.Get().First(&config, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 获取当前版本号
	newVersion := config.Version + 1

	// 记录版本历史
	version := model.PromptConfigVersion{
		ConfigID:     config.ID,
		Version:      newVersion,
		PromptText:   config.PromptText,
		ChangeReason: "手动更新",
		CreatedBy:    "admin",
	}

	tx := postgres.Get().Begin()

	// 更新配置
	updates["version"] = newVersion
	if err := tx.Model(&config).Updates(updates).Error; err != nil {
		tx.Rollback()
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}

	// 记录版本
	if err := tx.Create(&version).Error; err != nil {
		tx.Rollback()
		log.Printf("CreatePromptConfigVersion error: %v", err)
		response.Error(c, response.CodeInternalError, "创建版本记录失败")
		return
	}

	tx.Commit()
	response.Success(c, config)
}

// DeletePromptConfig 删除Prompt配置
func DeletePromptConfig(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))

	tx := postgres.Get().Begin()

	// 先删除关联的 embedding 记录（decision_analysis_template_embeddings 表）
	if err := tx.Exec("DELETE FROM decision_analysis_template_embeddings WHERE template_id = ?", id).Error; err != nil {
		tx.Rollback()
		log.Printf("[DeletePromptConfig] 删除 embedding 记录失败: %v", err)
		response.Error(c, response.CodeInternalError, "删除关联embedding失败")
		return
	}

	// 删除版本历史
	if err := tx.Where("config_id = ?", id).Delete(&model.PromptConfigVersion{}).Error; err != nil {
		tx.Rollback()
		log.Printf("[DeletePromptConfig] 删除版本历史失败: %v", err)
		response.Error(c, response.CodeInternalError, "删除版本历史失败")
		return
	}

	// 删除配置
	if err := tx.Delete(&model.PromptConfig{}, id).Error; err != nil {
		tx.Rollback()
		log.Printf("[DeletePromptConfig] 删除配置失败: %v", err)
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}

	tx.Commit()
	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetPromptConfigVersions 获取Prompt配置的版本历史
func GetPromptConfigVersions(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var versions []model.PromptConfigVersion
	postgres.Get().Where("config_id = ?", id).Order("version DESC").Find(&versions)
	response.Success(c, versions)
}

// DeletePromptConfigVersion 删除指定版本
func DeletePromptConfigVersion(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	version, _ := strconv.Atoi(c.Query("version"))

	// 不允许删除当前版本
	var config model.PromptConfig
	if err := postgres.Get().First(&config, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}
	if config.Version == version {
		response.Error(c, response.CodeBadRequest, "不能删除当前版本")
		return
	}

	// 删除版本记录
	if err := postgres.Get().Where("config_id = ? AND version = ?", id, version).Delete(&model.PromptConfigVersion{}).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除版本失败")
		return
	}

	response.SuccessWithMessage(c, "删除成功", nil)
}

// RollbackPromptConfig 回滚Prompt配置到指定版本
func RollbackPromptConfig(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var req struct {
		Version int `json:"version"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	var config model.PromptConfig
	if err := postgres.Get().First(&config, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}

	// 查找目标版本
	var targetVersion model.PromptConfigVersion
	if err := postgres.Get().Where("config_id = ? AND version = ?", id, req.Version).First(&targetVersion).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指定版本不存在")
		return
	}

	// 记录当前版本到历史
	currentVersion := model.PromptConfigVersion{
		ConfigID:     config.ID,
		Version:      config.Version + 1,
		PromptText:   config.PromptText,
		ChangeReason: "回滚到版本" + strconv.Itoa(req.Version),
		CreatedBy:    "admin",
	}

	tx := postgres.Get().Begin()

	// 更新配置
	if err := tx.Model(&config).Updates(map[string]interface{}{
		"prompt_text": targetVersion.PromptText,
		"version":     config.Version + 1,
	}).Error; err != nil {
		tx.Rollback()
		response.Error(c, response.CodeInternalError, "回滚失败")
		return
	}

	// 记录版本
	if err := tx.Create(&currentVersion).Error; err != nil {
		tx.Rollback()
		log.Printf("CreatePromptConfigVersion error: %v", err)
		response.Error(c, response.CodeInternalError, "创建版本记录失败")
		return
	}

	tx.Commit()
	response.Success(c, config)
}

// GetActivePromptConfig 获取启用的Prompt配置
func GetActivePromptConfig(c *gin.Context) {
	name := c.Query("name")
	var config model.PromptConfig
	if err := postgres.Get().Where("name = ? AND status = 1", name).First(&config).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在或已禁用")
		return
	}
	response.Success(c, config)
}

// GeneratePromptConfig 调用 AI 服务生成 Prompt
func GeneratePromptConfig(c *gin.Context) {
	var req struct {
		CurrentPrompt string `json:"current_prompt"`
		TaskName     string `json:"task_name"`
		Description  string `json:"description"`
		Mode         string `json:"mode"` // "improve" or "regenerate"
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 设置默认值
	if req.Mode == "" {
		req.Mode = "improve"
	}
	if req.TaskName == "" {
		req.TaskName = "nl2structure"
	}
	if req.Description == "" {
		req.Description = "自然语言转结构化实体"
	}

	// 构造请求体
	reqBody := map[string]string{
		"current_prompt":   req.CurrentPrompt,
		"task_name":        req.TaskName,
		"task_description":  req.Description,
		"mode":             req.Mode,
	}
	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		response.Error(c, response.CodeInternalError, "构造请求失败")
		return
	}

	// 调用 Python AI 服务（带 2 分钟超时）
	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Post("http://localhost:8081/api/v1/prompt/generate", "application/json", bytes.NewBuffer(jsonBody))

	if err != nil {
		response.Error(c, response.CodeInternalError, "AI 服务调用失败")
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		response.Error(c, response.CodeInternalError, "解析 AI 响应失败")
		return
	}

	code, _ := result["code"].(float64)
	if code == 0 {
		response.Success(c, result["data"])
	} else {
		response.Error(c, response.CodeInternalError, fmt.Sprintf("%v", result["message"]))
	}
}
