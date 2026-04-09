package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// GetDashboardStats 获取 Dashboard 统计数据
func GetDashboardStats(c *gin.Context) {
	db := postgres.Get()

	// 获取今日热门指标（Top 5）
	var hotMetrics []struct {
		MetricCode string `json:"metric_code"`
		MetricName string `json:"metric_name"`
		QueryCount int    `json:"query_count"`
	}

	today := time.Now().Format("2006-01-02")
	db.Raw(`
		SELECT metric_code, metric_name, SUM(query_count) as query_count
		FROM ask_query_stats
		WHERE query_date >= ?
		GROUP BY metric_code, metric_name
		ORDER BY query_count DESC
		LIMIT 5
	`, today+" 00:00:00").Scan(&hotMetrics)

	// 获取本周查询趋势（7天）
	var trendData []struct {
		Date       string `json:"date"`
		QueryCount int    `json:"query_count"`
	}

	weekAgo := time.Now().AddDate(0, 0, -7).Format("2006-01-02")
	db.Raw(`
		SELECT query_date::date as date, SUM(query_count) as query_count
		FROM ask_query_stats
		WHERE query_date >= ?
		GROUP BY query_date::date
		ORDER BY date ASC
	`, weekAgo+" 00:00:00").Scan(&trendData)

	// 获取今日总查询数
	var todayTotal int64
	db.Model(&model.AskQueryStat{}).Where("query_date >= ?", today+" 00:00:00").Count(&todayTotal)

	// 获取会话总数
	var sessionTotal int64
	db.Model(&model.AskSessionSummary{}).Count(&sessionTotal)

	response.Success(c, gin.H{
		"hot_metrics":   hotMetrics,
		"trend_data":    trendData,
		"today_total":  todayTotal,
		"session_total": sessionTotal,
	})
}

// GetSessions 获取会话列表（卡片式）
func GetSessions(c *gin.Context) {
	db := postgres.Get()
	userID := fmt.Sprintf("%d", GetUserIDFromContext(c))

	var sessions []model.AskSessionSummary
	db.Where("user_id = ?", userID).Order("updated_at DESC").Limit(50).Find(&sessions)

	response.Success(c, sessions)
}

// StarSession 会话加星标
func StarSession(c *gin.Context) {
	db := postgres.Get()
	sessionID := c.Param("id")
	userID := fmt.Sprintf("%d", GetUserIDFromContext(c))

	var session model.AskSessionSummary
	if err := db.Where("session_id = ? AND user_id = ?", sessionID, userID).First(&session).Error; err != nil {
		response.Error(c, http.StatusNotFound, "会话不存在或无权限")
		return
	}

	session.Starred = !session.Starred
	db.Save(&session)

	response.Success(c, session)
}

// GetFavorites 获取收藏列表
func GetFavorites(c *gin.Context) {
	db := postgres.Get()
	userID := fmt.Sprintf("%d", GetUserIDFromContext(c))

	var favorites []model.AskFavorite
	db.Where("user_id = ?", userID).Order("created_at DESC").Find(&favorites)

	response.Success(c, favorites)
}

// AddFavorite 添加收藏
func AddFavorite(c *gin.Context) {
	db := postgres.Get()
	userID := fmt.Sprintf("%d", GetUserIDFromContext(c))

	var req struct {
		SessionID   string `json:"session_id"`
		QuestionText string `json:"question_text"`
		AnswerText   string `json:"answer_text"`
		MetricCode   string `json:"metric_code"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, "参数错误")
		return
	}

	favorite := model.AskFavorite{
		UserID:      userID,
		SessionID:   req.SessionID,
		QuestionText: req.QuestionText,
		AnswerText:   req.AnswerText,
		MetricCode:   req.MetricCode,
	}

	db.Create(&favorite)
	response.Success(c, favorite)
}

// DeleteFavorite 删除收藏
func DeleteFavorite(c *gin.Context) {
	db := postgres.Get()
	id := c.Param("id")
	userID := fmt.Sprintf("%d", GetUserIDFromContext(c))

	// 验证收藏属于当前用户
	var favorite model.AskFavorite
	if err := db.Where("id = ? AND user_id = ?", id, userID).First(&favorite).Error; err != nil {
		response.Error(c, http.StatusNotFound, "收藏不存在或无权限")
		return
	}

	if err := db.Delete(&model.AskFavorite{}, id).Error; err != nil {
		response.Error(c, http.StatusInternalServerError, "删除失败")
		return
	}

	response.Success(c, nil)
}

// GetPreferences 获取用户偏好
func GetPreferences(c *gin.Context) {
	db := postgres.Get()
	userID := fmt.Sprintf("%d", GetUserIDFromContext(c))

	var pref model.AskUserPreference
	if err := db.Where("user_id = ?", userID).First(&pref).Error; err != nil {
		// 如果不存在，返回默认偏好
		pref = model.AskUserPreference{
			UserID:       userID,
			Theme:        "light",
			MessageStyle: "bubbles",
			FontSize:     "medium",
			ShowThinking: true,
			CompactMode:  false,
		}
	}

	response.Success(c, pref)
}

// UpdatePreferences 更新用户偏好
func UpdatePreferences(c *gin.Context) {
	db := postgres.Get()
	userID := fmt.Sprintf("%d", GetUserIDFromContext(c))

	var req struct {
		Theme        string `json:"theme"`
		MessageStyle string `json:"message_style"`
		FontSize     string `json:"font_size"`
		ShowThinking *bool  `json:"show_thinking"`
		CompactMode  *bool  `json:"compact_mode"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, "参数错误")
		return
	}

	var pref model.AskUserPreference
	if err := db.Where("user_id = ?", userID).First(&pref).Error; err != nil {
		// 创建新记录
		pref = model.AskUserPreference{
			UserID: userID,
		}
	}

	if req.Theme != "" {
		pref.Theme = req.Theme
	}
	if req.MessageStyle != "" {
		pref.MessageStyle = req.MessageStyle
	}
	if req.FontSize != "" {
		pref.FontSize = req.FontSize
	}
	if req.ShowThinking != nil {
		pref.ShowThinking = *req.ShowThinking
	}
	if req.CompactMode != nil {
		pref.CompactMode = *req.CompactMode
	}

	db.Save(&pref)
	response.Success(c, pref)
}

// GetRecentQuestions 获取最近提问
func GetRecentQuestions(c *gin.Context) {
	db := postgres.Get()
	userID := fmt.Sprintf("%d", GetUserIDFromContext(c))
	limit := c.DefaultQuery("limit", "10")

	var sessions []model.AskSessionSummary
	db.Where("user_id = ?", userID).
		Where("first_question != ''").
		Order("updated_at DESC").
		Limit(parseInt(limit)).
		Find(&sessions)

	// 提取问题列表
	var questions []string
	for _, s := range sessions {
		if s.FirstQuestion != "" {
			questions = append(questions, s.FirstQuestion)
		}
	}

	response.Success(c, questions)
}

func parseInt(s string) int {
	var n int
	for _, c := range s {
		if c >= '0' && c <= '9' {
			n = n*10 + int(c-'0')
		}
	}
	return n
}
