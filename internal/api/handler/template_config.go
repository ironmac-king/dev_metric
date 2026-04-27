package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"log"
	"strconv"

	"github.com/gin-gonic/gin"
)

// ListOutputTemplates 获取输出模板列表
func ListOutputTemplates(c *gin.Context) {
	var templates []model.OutputTemplate
	query := postgres.Get()

	if templateType := c.Query("template_type"); templateType != "" {
		query = query.Where("template_type = ?", templateType)
	}
	if templateKey := c.Query("template_key"); templateKey != "" {
		query = query.Where("template_key LIKE ?", "%"+templateKey+"%")
	}
	if enabled := c.Query("enabled"); enabled != "" {
		query = query.Where("enabled = ?", enabled == "true")
	}

	query.Order("priority DESC, id ASC").Find(&templates)
	response.Success(c, templates)
}

// GetOutputTemplate 获取单个输出模板
func GetOutputTemplate(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var tmpl model.OutputTemplate
	if err := postgres.Get().First(&tmpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}
	response.Success(c, tmpl)
}

// GetOutputTemplateByKey 根据 key 获取模板
func GetOutputTemplateByKey(c *gin.Context) {
	key := c.Param("key")
	var tmpl model.OutputTemplate
	if err := postgres.Get().Where("template_key = ?", key).First(&tmpl).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}
	response.Success(c, tmpl)
}

// CreateOutputTemplate 创建输出模板
func CreateOutputTemplate(c *gin.Context) {
	var tmpl model.OutputTemplate
	if err := c.ShouldBindJSON(&tmpl); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&tmpl).Error; err != nil {
		log.Printf("CreateOutputTemplate error: %v", err)
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, tmpl)
}

// UpdateOutputTemplate 更新输出模板
func UpdateOutputTemplate(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var tmpl model.OutputTemplate
	if err := postgres.Get().First(&tmpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&tmpl).Updates(updates).Error; err != nil {
		log.Printf("UpdateOutputTemplate error: %v", err)
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	response.Success(c, tmpl)
}

// UpdateOutputTemplateByKey 根据 key 更新模板
func UpdateOutputTemplateByKey(c *gin.Context) {
	key := c.Param("key")
	var tmpl model.OutputTemplate
	if err := postgres.Get().Where("template_key = ?", key).First(&tmpl).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&tmpl).Updates(updates).Error; err != nil {
		log.Printf("UpdateOutputTemplateByKey error: %v", err)
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	response.Success(c, tmpl)
}

// DeleteOutputTemplate 删除输出模板
func DeleteOutputTemplate(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	if err := postgres.Get().Delete(&model.OutputTemplate{}, id).Error; err != nil {
		log.Printf("DeleteOutputTemplate error: %v", err)
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}
	response.SuccessWithMessage(c, "删除成功", nil)
}
