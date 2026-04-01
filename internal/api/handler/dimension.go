package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"log"
	"strconv"

	"github.com/gin-gonic/gin"
)

// ListDimensionConfigs 获取维度配置列表
func ListDimensionConfigs(c *gin.Context) {
	tableName := c.Query("table_name")

	var configs []model.DimensionConfig
	db := postgres.Get().Model(&model.DimensionConfig{})

	if tableName != "" {
		db = db.Where("table_name = ?", tableName)
	}

	db.Order("id ASC").Find(&configs)
	response.Success(c, configs)
}

// GetDimensionTables 获取所有已配置表名
func GetDimensionTables(c *gin.Context) {
	var results []string
	postgres.Get().Model(&model.DimensionConfig{}).
		Where("status = ?", 1).
		Distinct("table_name").
		Pluck("table_name", &results)
	response.Success(c, results)
}

// CreateDimensionConfig 创建维度配置
func CreateDimensionConfig(c *gin.Context) {
	var config model.DimensionConfig
	if err := c.ShouldBindJSON(&config); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Create(&config).Error; err != nil {
		log.Printf("CreateDimensionConfig error: %v", err)
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, config)
}

// UpdateDimensionConfig 更新维度配置
func UpdateDimensionConfig(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var config model.DimensionConfig
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

// DeleteDimensionConfig 删除维度配置
func DeleteDimensionConfig(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	if err := postgres.Get().Delete(&model.DimensionConfig{}, id).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}
	response.SuccessWithMessage(c, "删除成功", nil)
}

// DeleteDimensionTable 删除表及其所有维度配置
func DeleteDimensionTable(c *gin.Context) {
	tableName := c.Param("table_name")
	if err := postgres.Get().Where("table_name = ?", tableName).Delete(&model.DimensionConfig{}).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}
	response.SuccessWithMessage(c, "删除成功", nil)
}
