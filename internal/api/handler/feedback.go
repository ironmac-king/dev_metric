package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

// GetFeedbackStats 获取反馈统计（卡片数据）
func GetFeedbackStats(c *gin.Context) {
	db := postgres.Get()

	var totalFeedback int64
	var positiveCount int64
	var negativeCount int64
	var silentCount int64

	db.Model(&model.ClarificationFeedback{}).Count(&totalFeedback)
	db.Model(&model.ClarificationFeedback{}).Where("feedback = ?", 1).Count(&positiveCount)
	db.Model(&model.ClarificationFeedback{}).Where("feedback = ?", -1).Count(&negativeCount)
	db.Model(&model.ClarificationFeedback{}).Where("feedback_source = ?", "silent").Count(&silentCount)

	// 计算占比
	positiveRate := float64(0)
	negativeRate := float64(0)
	silentRate := float64(0)
	if totalFeedback > 0 {
		positiveRate = float64(positiveCount) / float64(totalFeedback) * 100
		negativeRate = float64(negativeCount) / float64(totalFeedback) * 100
		silentRate = float64(silentCount) / float64(totalFeedback) * 100
	}

	response.Success(c, gin.H{
		"total_feedback": totalFeedback,
		"positive": gin.H{
			"count": positiveCount,
			"rate":  positiveRate,
		},
		"negative": gin.H{
			"count": negativeCount,
			"rate":  negativeRate,
		},
		"silent": gin.H{
			"count": silentCount,
			"rate":  silentRate,
		},
	})
}

// GetFeedbackTrend 获取反馈趋势
func GetFeedbackTrend(c *gin.Context) {
	period := c.DefaultQuery("period", "day") // day/week/month

	var dateFormat string
	switch period {
	case "week":
		dateFormat = "YYYY-IW"
	case "month":
		dateFormat = "YYYY-MM"
	default:
		dateFormat = "YYYY-MM-DD"
	}

	type TrendItem struct {
		Date     string `json:"date"`
		Positive int64  `json:"positive"`
		Negative int64  `json:"negative"`
		Silent   int64  `json:"silent"`
		Total    int64  `json:"total"`
	}

	var trends []TrendItem
	db := postgres.Get()

	// 使用 fmt.Sprintf 直接嵌入 dateFormat（来自 switch 的固定值，安全）
	db.Model(&model.ClarificationFeedback{}).
		Select("TO_CHAR(created_at, '"+dateFormat+"') as date, "+
			"SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as positive, "+
			"SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as negative, "+
			"SUM(CASE WHEN feedback_source = 'silent' THEN 1 ELSE 0 END) as silent, "+
			"COUNT(*) as total").
		Group("TO_CHAR(created_at, '"+dateFormat+"')").
		Order("date ASC").
		Scan(&trends)

	response.Success(c, gin.H{
		"period": period,
		"trends": trends,
	})
}

// GetFeedbackByType 按追问类型统计
func GetFeedbackByType(c *gin.Context) {
	type TypeStat struct {
		ClarificationType string  `json:"clarification_type"`
		Total             int64   `json:"total"`
		Success           int64   `json:"success"`
		Fail              int64   `json:"fail"`
		Silent            int64   `json:"silent"`
		SuccessRate       float64 `json:"success_rate"`
	}

	var stats []TypeStat
	db := postgres.Get()

	db.Model(&model.ClarificationFeedback{}).
		Select("clarification_type, "+
			"COUNT(*) as total, "+
			"SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as success, "+
			"SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as fail, "+
			"SUM(CASE WHEN feedback = 0 AND feedback_source = 'silent' THEN 1 ELSE 0 END) as silent",
			"ROUND(SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as success_rate").
		Group("clarification_type").
		Order("success_rate ASC").
		Scan(&stats)

	response.Success(c, gin.H{
		"stats": stats,
	})
}

// GetFeedbackList 获取反馈列表（分页）
func GetFeedbackList(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	// 筛选参数
	feedbackType := c.Query("feedback_type") // positive/negative/silent
	clarType := c.Query("clarification_type")
	failReason := c.Query("fail_reason")
	startDate := c.Query("start_date")
	endDate := c.Query("end_date")

	db := postgres.Get()

	query := db.Model(&model.ClarificationFeedback{})

	// 筛选条件
	if feedbackType != "" {
		switch feedbackType {
		case "positive":
			query = query.Where("feedback = ?", 1)
		case "negative":
			query = query.Where("feedback = ?", -1)
		case "silent":
			query = query.Where("feedback_source = ?", "silent")
		}
	}
	if clarType != "" {
		query = query.Where("clarification_type = ?", clarType)
	}
	if failReason != "" {
		query = query.Where("fail_reason = ?", failReason)
	}
	if startDate != "" {
		t, _ := time.Parse("2006-01-02", startDate)
		query = query.Where("created_at >= ?", t)
	}
	if endDate != "" {
		t, _ := time.Parse("2006-01-02", endDate+" 23:59:59")
		query = query.Where("created_at <= ?", t)
	}

	// 总数
	var total int64
	query.Count(&total)

	// 分页查询
	var list []model.ClarificationFeedback
	offset := (page - 1) * pageSize
	query.Order("created_at DESC").Offset(offset).Limit(pageSize).Find(&list)

	// 处理数据，截取问题摘要
	type FeedbackItem struct {
		ID                 int64                   `json:"id"`
		SessionID          string                  `json:"session_id"`
		TurnIndex         int                     `json:"turn_index"`
		ClarificationType string                  `json:"clarification_type"`
		FailReason        string                  `json:"fail_reason"`
		QuestionPreview   string                  `json:"question_preview"`
		FeedbackDisplay    string                  `json:"feedback_display"`
		CreatedAt         time.Time              `json:"created_at"`
	}

	items := make([]FeedbackItem, len(list))
	for i, f := range list {
		questionPreview := f.ClarificationQ
		if len(questionPreview) > 30 {
			questionPreview = questionPreview[:30] + "..."
		}

		feedbackDisplay := "--"
		if f.Feedback == 1 {
			feedbackDisplay = "👍"
		} else if f.Feedback == -1 {
			feedbackDisplay = "👎"
		} else if f.FeedbackSource == "silent" {
			feedbackDisplay = "🔇"
		}

		items[i] = FeedbackItem{
			ID:                 f.ID,
			SessionID:          f.SessionID,
			TurnIndex:         f.TurnIndex,
			ClarificationType: f.ClarificationType,
			FailReason:        f.FailReason,
			QuestionPreview:   questionPreview,
			FeedbackDisplay:   feedbackDisplay,
			CreatedAt:         f.CreatedAt,
		}
	}

	response.Success(c, gin.H{
		"list": items,
		"pagination": gin.H{
			"page":       page,
			"page_size":  pageSize,
			"total":      total,
			"total_page": (total + int64(pageSize) - 1) / int64(pageSize),
		},
	})
}
