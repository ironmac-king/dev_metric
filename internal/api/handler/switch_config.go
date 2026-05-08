package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"log"

	"github.com/gin-gonic/gin"
)

// ListTriggerSwitches 获取触发器开关列表
func ListTriggerSwitches(c *gin.Context) {
	var switches []model.TriggerSwitch
	query := postgres.Get()

	if triggerType := c.Query("trigger_type"); triggerType != "" {
		query = query.Where("trigger_type = ?", triggerType)
	}
	if switchStatus := c.Query("switch_status"); switchStatus != "" {
		query = query.Where("switch_status = ?", switchStatus)
	}

	query.Order("id ASC").Find(&switches)
	response.Success(c, switches)
}

// GetTriggerSwitch 获取单个触发器开关
func GetTriggerSwitch(c *gin.Context) {
	triggerType := c.Param("type")
	var sw model.TriggerSwitch
	if err := postgres.Get().Where("trigger_type = ?", triggerType).First(&sw).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}
	response.Success(c, sw)
}

// UpdateTriggerSwitch 更新触发器开关
func UpdateTriggerSwitch(c *gin.Context) {
	triggerType := c.Param("type")
	var sw model.TriggerSwitch
	if err := postgres.Get().Where("trigger_type = ?", triggerType).First(&sw).Error; err != nil {
		response.Error(c, response.CodeNotFound, "配置不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&sw).Updates(updates).Error; err != nil {
		log.Printf("UpdateTriggerSwitch error: %v", err)
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	response.Success(c, sw)
}

// SetTriggerSwitch 设置触发器开关状态（含灰度）
func SetTriggerSwitch(c *gin.Context) {
	triggerType := c.Param("type")

	var input struct {
		SwitchStatus string `json:"switch_status" binding:"required"`
		GrayRatio    *int   `json:"gray_ratio"`
		SwitchReason string `json:"switch_reason"`
		Operator     string `json:"operator"`
	}
	if err := c.ShouldBindJSON(&input); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	updates := map[string]interface{}{
		"switch_status": input.SwitchStatus,
	}
	if input.GrayRatio != nil {
		updates["gray_ratio"] = *input.GrayRatio
	}
	if input.SwitchReason != "" {
		updates["switch_reason"] = input.SwitchReason
	}
	if input.Operator != "" {
		updates["operator"] = input.Operator
	}

	var sw model.TriggerSwitch
	err := postgres.Get().Where("trigger_type = ?", triggerType).First(&sw).Error
	if err != nil {
		// 不存在则创建
		sw = model.TriggerSwitch{
			TriggerType:  triggerType,
			SwitchStatus: input.SwitchStatus,
			GrayRatio:    input.GrayRatio,
			SwitchReason: input.SwitchReason,
			Operator:     input.Operator,
		}
		if err := postgres.Get().Create(&sw).Error; err != nil {
			log.Printf("SetTriggerSwitch create error: %v", err)
			response.Error(c, response.CodeInternalError, "创建失败")
			return
		}
	} else {
		if err := postgres.Get().Model(&sw).Updates(updates).Error; err != nil {
			log.Printf("SetTriggerSwitch update error: %v", err)
			response.Error(c, response.CodeInternalError, "更新失败")
			return
		}
	}

	response.Success(c, sw)
}

// DeleteTriggerSwitch 删除触发器开关
func DeleteTriggerSwitch(c *gin.Context) {
	triggerType := c.Param("type")
	if err := postgres.Get().Where("trigger_type = ?", triggerType).Delete(&model.TriggerSwitch{}).Error; err != nil {
		log.Printf("DeleteTriggerSwitch error: %v", err)
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}
	response.SuccessWithMessage(c, "删除成功", nil)
}
