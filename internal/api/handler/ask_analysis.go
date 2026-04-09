package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

// CreateAnalysisLog 创建分析日志
func CreateAnalysisLog(c *gin.Context) {
	var req struct {
		UserID       string `json:"user_id"`
		SessionID    string `json:"session_id"`
		Question     string `json:"question"`
		Answer       string `json:"answer"`
		Intent       string `json:"intent"`
		Success      bool   `json:"success"`
		FailStage    string `json:"fail_stage"`
		FailReason   string `json:"fail_reason"`
		Suggestion   string `json:"suggestion"`
		ThinkingSteps string `json:"thinking_steps"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 伪代码：user_id 默认值
	if req.UserID == "" {
		req.UserID = "default"
	}

	log := model.AskAnalysisLog{
		UserID:        req.UserID,
		SessionID:     req.SessionID,
		Question:      req.Question,
		Answer:        req.Answer,
		Intent:        req.Intent,
		Success:       req.Success,
		FailStage:     req.FailStage,
		FailReason:   req.FailReason,
		Suggestion:    req.Suggestion,
		ThinkingSteps: req.ThinkingSteps,
		CreatedAt:    time.Now(),
	}

	if err := postgres.Get().Create(&log).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建日志失败")
		return
	}

	response.Success(c, log)
}

// GetAnalysisLogs 获取日志列表
func GetAnalysisLogs(c *gin.Context) {
	// 获取分页参数
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	if page <= 0 {
		page = 1
	}
	if pageSize <= 0 || pageSize > 100 {
		pageSize = 20
	}

	// 获取筛选参数
	successFilter := c.Query("success")
	userID := c.Query("user_id")
	if userID == "" {
		userID = "default"
	}

	// 构建查询
	db := postgres.Get().Model(&model.AskAnalysisLog{})
	db = db.Where("user_id = ?", userID)

	if successFilter != "" {
		if successFilter == "true" || successFilter == "1" {
			db = db.Where("success = ?", true)
		} else if successFilter == "false" || successFilter == "0" {
			db = db.Where("success = ?", false)
		}
	}

	// 统计总数
	var total int64
	db.Count(&total)

	// 分页查询
	offset := (page - 1) * pageSize
	var logs []model.AskAnalysisLog
	db = db.Order("created_at DESC").Offset(offset).Limit(pageSize)
	if err := db.Find(&logs).Error; err != nil {
		response.Error(c, response.CodeInternalError, "查询失败")
		return
	}

	response.Success(c, gin.H{
		"list": logs,
		"pagination": gin.H{
			"page":        page,
			"page_size":   pageSize,
			"total":       total,
			"total_pages": (total + int64(pageSize) - 1) / int64(pageSize),
		},
	})
}

// GetAnalysisLog 获取日志详情
func GetAnalysisLog(c *gin.Context) {
	id := c.Param("id")
	var log model.AskAnalysisLog

	if err := postgres.Get().First(&log, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "日志不存在")
		return
	}

	response.Success(c, log)
}

// DeleteAnalysisLog 删除日志
func DeleteAnalysisLog(c *gin.Context) {
	id := c.Param("id")
	var log model.AskAnalysisLog

	if err := postgres.Get().First(&log, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "日志不存在")
		return
	}

	if err := postgres.Get().Delete(&log).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}

	response.Success(c, gin.H{"deleted": true})
}
