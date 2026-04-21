package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"log"
	"strconv"

	"github.com/gin-gonic/gin"
)

// ListDimensionTypeMappings 获取所有维度类型映射
func ListDimensionTypeMappings(c *gin.Context) {
	var mappings []model.DimensionTypeMapping
	postgres.Get().Order("id ASC").Find(&mappings)
	response.Success(c, mappings)
}

// GetDimensionTypeMappingsByType 根据类型名获取映射
func GetDimensionTypeMappingsByType(c *gin.Context) {
	dimensionType := c.Query("dimension_type")
	var mappings []model.DimensionTypeMapping
	query := postgres.Get().Model(&model.DimensionTypeMapping{}).Where("status = ?", 1)
	if dimensionType != "" {
		query = query.Where("LOWER(dimension_type) LIKE LOWER(?)", "%"+dimensionType+"%")
	}
	query.Find(&mappings)
	response.Success(c, mappings)
}

// CreateDimensionTypeMapping 创建维度类型映射
func CreateDimensionTypeMapping(c *gin.Context) {
	var mapping model.DimensionTypeMapping
	if err := c.ShouldBindJSON(&mapping); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Create(&mapping).Error; err != nil {
		log.Printf("CreateDimensionTypeMapping error: %v", err)
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, mapping)
}

// UpdateDimensionTypeMapping 更新维度类型映射
func UpdateDimensionTypeMapping(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var mapping model.DimensionTypeMapping
	if err := postgres.Get().First(&mapping, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "映射不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&mapping).Updates(updates).Error; err != nil {
		log.Printf("UpdateDimensionTypeMapping error: %v", err)
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	response.Success(c, mapping)
}

// DeleteDimensionTypeMapping 删除维度类型映射
func DeleteDimensionTypeMapping(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	if err := postgres.Get().Delete(&model.DimensionTypeMapping{}, id).Error; err != nil {
		log.Printf("DeleteDimensionTypeMapping error: %v", err)
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}
	response.SuccessWithMessage(c, "删除成功", nil)
}
