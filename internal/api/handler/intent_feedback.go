package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

// ListIntentFeedback 获取意图反馈列表（分页）
func ListIntentFeedback(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	status := c.Query("status")

	var feedbacks []model.IntentFeedback
	query := postgres.Get().Model(&model.IntentFeedback{})

	if status != "" {
		query = query.Where("status = ?", status)
	}

	var total int64
	query.Count(&total)

	query.Order("id DESC").
		Offset((page - 1) * pageSize).
		Limit(pageSize).
		Find(&feedbacks)

	response.Success(c, gin.H{
		"list":      feedbacks,
		"total":     total,
		"page":      page,
		"page_size": pageSize,
	})
}

// ReviewIntentFeedback 审核意图反馈
func ReviewIntentFeedback(c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var feedback model.IntentFeedback
	if err := postgres.Get().First(&feedback, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "反馈记录不存在")
		return
	}

	var input struct {
		Status     int16  `json:"status"`
		ReviewedBy string `json:"reviewed_by"`
	}
	if err := c.ShouldBindJSON(&input); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	feedback.Status = input.Status
	feedback.ReviewedBy = input.ReviewedBy
	now := time.Now()
	feedback.ReviewedAt = &now

	postgres.Get().Save(&feedback)
	response.Success(c, feedback)
}

// RecordIntentFeedback 记录意图反馈（AI 服务调用）
func RecordIntentFeedback(c *gin.Context) {
	var input struct {
		UserInput       string `json:"user_input" binding:"required"`
		PredictedIntent string `json:"predicted_intent" binding:"required"`
		CorrectIntent   string `json:"correct_intent" binding:"required"`
		SessionID       string `json:"session_id"`
	}
	if err := c.ShouldBindJSON(&input); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	feedback := model.IntentFeedback{
		UserInput:       input.UserInput,
		PredictedIntent: input.PredictedIntent,
		CorrectIntent:   input.CorrectIntent,
		SessionID:       input.SessionID,
		Status:          0,
	}

	if err := postgres.Get().Create(&feedback).Error; err != nil {
		response.Error(c, response.CodeInternalError, "记录失败")
		return
	}
	response.Success(c, feedback)
}
