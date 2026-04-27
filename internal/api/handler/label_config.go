package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"log"
	"strconv"

	"github.com/gin-gonic/gin"
)

// ListDimensionLabels 获取维度标签列表
func ListDimensionLabels(c *gin.Context) {
	var labels []model.BusinessDimensionLabel
	query := postgres.Get()

	if dimensionType := c.Query("dimension_type"); dimensionType != "" {
		query = query.Where("dimension_type = ?", dimensionType)
	}
	if rawValue := c.Query("raw_value"); rawValue != "" {
		query = query.Where("raw_value LIKE ?", "%"+rawValue+"%")
	}
	if displayName := c.Query("display_name"); displayName != "" {
		query = query.Where("display_name LIKE ?", "%"+displayName+"%")
	}

	query.Order("dimension_type ASC, priority_tag DESC, id ASC").Find(&labels)
	response.Success(c, labels)
}

// GetDimensionLabel 获取单个维度标签
func GetDimensionLabel(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var label model.BusinessDimensionLabel
	if err := postgres.Get().First(&label, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "标签不存在")
		return
	}
	response.Success(c, label)
}

// CreateDimensionLabel 创建维度标签
func CreateDimensionLabel(c *gin.Context) {
	var label model.BusinessDimensionLabel
	if err := c.ShouldBindJSON(&label); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&label).Error; err != nil {
		log.Printf("CreateDimensionLabel error: %v", err)
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, label)
}

// UpdateDimensionLabel 更新维度标签
func UpdateDimensionLabel(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var label model.BusinessDimensionLabel
	if err := postgres.Get().First(&label, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "标签不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&label).Updates(updates).Error; err != nil {
		log.Printf("UpdateDimensionLabel error: %v", err)
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	response.Success(c, label)
}

// DeleteDimensionLabel 删除维度标签
func DeleteDimensionLabel(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	if err := postgres.Get().Delete(&model.BusinessDimensionLabel{}, id).Error; err != nil {
		log.Printf("DeleteDimensionLabel error: %v", err)
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}
	response.SuccessWithMessage(c, "删除成功", nil)
}
