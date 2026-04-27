package handler

import (
    "dev_metric/internal/model"
    "dev_metric/internal/repository/postgres"
    "dev_metric/pkg/response"
    "log"
    "strconv"

    "github.com/gin-gonic/gin"
)

// ListTriggerConfigs 获取触发规则列表
func ListTriggerConfigs(c *gin.Context) {
    var configs []model.AnalysisTriggerConfig
    query := postgres.Get()

    if triggerType := c.Query("trigger_type"); triggerType != "" {
        query = query.Where("trigger_type = ?", triggerType)
    }
    if enabled := c.Query("enabled"); enabled != "" {
        query = query.Where("enabled = ?", enabled == "true")
    }

    query.Order("priority DESC, id ASC").Find(&configs)
    response.Success(c, configs)
}

// GetTriggerConfig 获取单条触发规则
func GetTriggerConfig(c *gin.Context) {
    id, _ := strconv.Atoi(c.Param("id"))
    var cfg model.AnalysisTriggerConfig
    if err := postgres.Get().First(&cfg, id).Error; err != nil {
        response.Error(c, response.CodeNotFound, "配置不存在")
        return
    }
    response.Success(c, cfg)
}

// CreateTriggerConfig 创建触发规则
func CreateTriggerConfig(c *gin.Context) {
    var cfg model.AnalysisTriggerConfig
    if err := c.ShouldBindJSON(&cfg); err != nil {
        response.Error(c, response.CodeBadRequest, "参数错误")
        return
    }
    if err := postgres.Get().Create(&cfg).Error; err != nil {
        log.Printf("CreateTriggerConfig error: %v", err)
        response.Error(c, response.CodeInternalError, "创建失败")
        return
    }
    response.Success(c, cfg)
}

// UpdateTriggerConfig 更新触发规则
func UpdateTriggerConfig(c *gin.Context) {
    id, _ := strconv.Atoi(c.Param("id"))
    var cfg model.AnalysisTriggerConfig
    if err := postgres.Get().First(&cfg, id).Error; err != nil {
        response.Error(c, response.CodeNotFound, "配置不存在")
        return
    }

    var updates map[string]interface{}
    if err := c.ShouldBindJSON(&updates); err != nil {
        response.Error(c, response.CodeBadRequest, "参数错误")
        return
    }

    if err := postgres.Get().Model(&cfg).Updates(updates).Error; err != nil {
        log.Printf("UpdateTriggerConfig error: %v", err)
        response.Error(c, response.CodeInternalError, "更新失败")
        return
    }
    response.Success(c, cfg)
}

// DeleteTriggerConfig 删除触发规则
func DeleteTriggerConfig(c *gin.Context) {
    id, _ := strconv.Atoi(c.Param("id"))
    if err := postgres.Get().Delete(&model.AnalysisTriggerConfig{}, id).Error; err != nil {
        log.Printf("DeleteTriggerConfig error: %v", err)
        response.Error(c, response.CodeInternalError, "删除失败")
        return
    }
    response.SuccessWithMessage(c, "删除成功", nil)
}
