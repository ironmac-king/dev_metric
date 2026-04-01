package handler

import (
	"bytes"
	"context"
	"dev_metric/config"
	"dev_metric/internal/cache"
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// AskQuestion 智能问数 - 调用 Python AI 服务
func AskQuestion(c *gin.Context) {
	var req struct {
		Question  string `json:"question" binding:"required"`
		SessionID string `json:"session_id"`
		Page      int    `json:"page"`
		PageSize  int    `json:"page_size"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 设置默认值
	if req.Page <= 0 {
		req.Page = 1
	}
	if req.PageSize <= 0 {
		req.PageSize = 10
	}

	// 调用 Python AI 服务
	aiURL := fmt.Sprintf("http://localhost:8081/api/v1/ask")

	payload := map[string]interface{}{
		"question":   req.Question,
		"session_id": req.SessionID,
		"page":      req.Page,
		"page_size": req.PageSize,
	}
	jsonData, _ := json.Marshal(payload)

	resp, err := http.Post(aiURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		response.Success(c, gin.H{
			"session_id": req.SessionID,
			"answer":     "AI 服务暂时不可用，请稍后再试",
			"suggest":    []string{},
		})
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var aiResp map[string]interface{}
	json.Unmarshal(body, &aiResp)

	// 从 Python 响应获取 session_id，同步到 Go 数据库
	if sessionID, ok := aiResp["session_id"].(string); ok && sessionID != "" {
		now := time.Now()
		summary := model.AskSessionSummary{
			SessionID:     sessionID,
			Title:        aiResp["answer"].(string),
			FirstQuestion: req.Question,
			MessageCount: 1,
			UpdatedAt:    now,
		}
		// Upsert: 存在则更新，不存在则创建
		postgres.Get().Where("session_id = ?", sessionID).Assign(summary).FirstOrCreate(&model.AskSessionSummary{})
	}

	response.Success(c, gin.H{
		"session_id":             aiResp["session_id"],
		"answer":                aiResp["answer"],
		"suggest":               aiResp["suggest"],
		"sql":                   aiResp["sql"],
		"thinking_steps":         aiResp["thinking_steps"],
		"drill_down_dims":        aiResp["drill_down_dims"],
		"breadcrumbs":           aiResp["breadcrumbs"],
		"result_data":           aiResp["result_data"],
		"total":                 aiResp["total"],
		"page":                  aiResp["page"],
		"page_size":             aiResp["page_size"],
		"needs_clarification":    aiResp["needs_clarification"],
		"clarification_message":  aiResp["clarification_message"],
		"clarification_type":     aiResp["clarification_type"],
		"matched_metrics":       aiResp["matched_metrics"],
	})
}

// GetAskHistory 获取对话历史
func GetAskHistory(c *gin.Context) {
	sessionID := c.Query("session_id")
	if sessionID == "" {
		response.Error(c, response.CodeBadRequest, "session_id 不能为空")
		return
	}

	// 调用 Python AI 服务
	resp, err := http.Get(fmt.Sprintf("http://localhost:8081/api/v1/ask/history?session_id=%s", sessionID))
	if err != nil {
		response.Success(c, gin.H{
			"session_id": sessionID,
			"history":    []interface{}{},
		})
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var aiResp map[string]interface{}
	json.Unmarshal(body, &aiResp)

	response.Success(c, aiResp)
}

// ClearSession 清除会话
func ClearSession(c *gin.Context) {
	var req struct {
		SessionID string `json:"session_id" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 调用 Python AI 服务（session_id 作为 query parameter）
	resp, err := http.Get(fmt.Sprintf("http://localhost:8081/api/v1/ask/clear?session_id=%s", req.SessionID))
	if err != nil {
		response.Error(c, response.CodeInternalError, "AI 服务调用失败")
		return
	}
	defer resp.Body.Close()

	// 同时删除 Go 后端的会话摘要记录
	postgres.Get().Delete(&model.AskSessionSummary{}, "session_id = ?", req.SessionID)

	response.SuccessWithMessage(c, "会话已清除", nil)
}

// SubmitFeedback 提交反馈（点赞/点踩）
func SubmitFeedback(c *gin.Context) {
	var req struct {
		SessionID  string `json:"session_id" binding:"required"`
		TurnIndex  int    `json:"turn_index"`
		Feedback   int    `json:"feedback" binding:"required"` // 1=positive, -1=negative
		MetricID   *int   `json:"metric_id"`
		ClarificationType  string `json:"clarification_type"`
		ClarificationQuestion string `json:"clarification_question"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 调用 Python AI 服务
	aiURL := "http://localhost:8081/api/v1/ask/feedback"
	payload := map[string]interface{}{
		"session_id":            req.SessionID,
		"turn_index":            req.TurnIndex,
		"feedback":              req.Feedback,
		"metric_id":             req.MetricID,
		"clarification_type":    req.ClarificationType,
		"clarification_question": req.ClarificationQuestion,
	}
	jsonData, _ := json.Marshal(payload)

	resp, err := http.Post(aiURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		response.Error(c, response.CodeInternalError, "AI 服务调用失败")
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var aiResp map[string]interface{}
	json.Unmarshal(body, &aiResp)

	if success, ok := aiResp["success"].(bool); ok && success {
		response.SuccessWithMessage(c, "反馈已提交", nil)
	} else {
		response.Error(c, response.CodeInternalError, "反馈提交失败")
	}
}

// GetAskSuggest 获取问题建议
func GetAskSuggest(c *gin.Context) {
	resp, err := http.Get("http://localhost:8081/api/v1/ask/suggest")
	if err != nil {
		response.Success(c, []string{
			"昨天的访客数是多少",
			"本周的订单量",
			"本月销售额趋势",
		})
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var aiResp map[string]interface{}
	json.Unmarshal(body, &aiResp)

	if suggests, ok := aiResp["suggests"].([]interface{}); ok {
		var result []string
		for _, s := range suggests {
			if str, ok := s.(string); ok {
				result = append(result, str)
			}
		}
		response.Success(c, result)
		return
	}
	response.Success(c, []string{})
}

// ensureConfigLoaded 确保配置已加载
func ensureConfigLoaded() {
	if config.Get() == nil {
		config.Load("config.yaml")
	}
}

// DrillDownQuestion 下钻维度查询
func DrillDownQuestion(c *gin.Context) {
	var req struct {
		SessionID      string   `json:"session_id" binding:"required"`
		DimensionNames []string `json:"dimension_names" binding:"required"`
		MetricCode     string   `json:"metric_code" binding:"required"`
		CurrentSQL     string   `json:"current_sql" binding:"required"`
		CurrentGroupBy string   `json:"current_group_by"`
		Page           int      `json:"page"`
		PageSize       int      `json:"page_size"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误: "+err.Error())
		return
	}

	// 设置默认值
	if req.Page <= 0 {
		req.Page = 1
	}
	if req.PageSize <= 0 {
		req.PageSize = 10
	}

	// 调用 Python AI 服务的下钻接口
	aiURL := "http://localhost:8081/api/v1/ask/drill_down"
	payload := map[string]interface{}{
		"session_id":       req.SessionID,
		"dimension_names":   req.DimensionNames,
		"metric_code":      req.MetricCode,
		"current_sql":      req.CurrentSQL,
		"current_group_by":  req.CurrentGroupBy,
		"page":            req.Page,
		"page_size":       req.PageSize,
	}
	jsonData, _ := json.Marshal(payload)

	resp, err := http.Post(aiURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		response.Error(c, response.CodeInternalError, "下钻服务调用失败: "+err.Error())
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var aiResp map[string]interface{}
	json.Unmarshal(body, &aiResp)

	response.Success(c, gin.H{
		"session_id":             aiResp["session_id"],
		"answer":                aiResp["answer"],
		"sql":                   aiResp["sql"],
		"drill_down_dims":        aiResp["drill_down_dims"],
		"breadcrumbs":           aiResp["breadcrumbs"],
		"result_data":           aiResp["result_data"],
		"total":                 aiResp["total"],
		"page":                  aiResp["page"],
		"page_size":             aiResp["page_size"],
		"needs_clarification":    aiResp["needs_clarification"],
		"clarification_message":  aiResp["clarification_message"],
		"clarification_type":     aiResp["clarification_type"],
		"matched_metrics":       aiResp["matched_metrics"],
	})
}

// SaveMessage 保存会话消息（Redis 缓存 + 异步落库 PostgreSQL）
func SaveMessage(c *gin.Context) {
	var req struct {
		SessionID string `json:"session_id" binding:"required"`
		Role     string `json:"role" binding:"required"` // user / assistant
		Content  string `json:"content" binding:"required"`
		SQL      string `json:"sql"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 构造消息
	msg := model.AskMessage{
		SessionID: req.SessionID,
		Role:     req.Role,
		Content:  req.Content,
		SQL:      req.SQL,
	}

	// 同步写 Redis（7天过期）
ctx := context.Background()
	cacheKey := fmt.Sprintf("ask:messages:%s", req.SessionID)
	var existing []model.AskMessage
	if err := cache.GetJSON(ctx, cacheKey, &existing); err != nil {
		existing = []model.AskMessage{}
	}
	existing = append(existing, msg)
	cache.SetJSON(ctx, cacheKey, existing, 7*24*time.Hour)

	// 异步写 PostgreSQL
	go func() {
		postgres.Get().Create(&msg)
	}()

	response.Success(c, gin.H{"saved": true})
}

// GetMessages 获取会话消息（优先 Redis，没有则读 PostgreSQL）
func GetMessages(c *gin.Context) {
	sessionID := c.Query("session_id")
	if sessionID == "" {
		response.Error(c, response.CodeBadRequest, "session_id 不能为空")
		return
	}

	// 优先从 Redis 读
	ctx := context.Background()
	cacheKey := fmt.Sprintf("ask:messages:%s", sessionID)
	var messages []model.AskMessage
	if err := cache.GetJSON(ctx, cacheKey, &messages); err == nil && len(messages) > 0 {
		response.Success(c, gin.H{"messages": messages, "source": "redis"})
		return
	}

	// Redis 没有，从 PostgreSQL 读
	postgres.Get().Where("session_id = ?", sessionID).Order("created_at ASC").Find(&messages)

	// 回填 Redis
	if len(messages) > 0 {
		go func() {
			cache.SetJSON(ctx, cacheKey, messages, 7*24*time.Hour)
		}()
	}

	response.Success(c, gin.H{"messages": messages, "source": "db"})
}

// DeleteMessages 删除会话消息（Redis + PostgreSQL）
func DeleteMessages(c *gin.Context) {
	sessionID := c.Query("session_id")
	if sessionID == "" {
		response.Error(c, response.CodeBadRequest, "session_id 不能为空")
		return
	}

	// 删除 Redis
	ctx := context.Background()
	cacheKey := fmt.Sprintf("ask:messages:%s", sessionID)
	cache.Delete(ctx, cacheKey)

	// 删除 PostgreSQL
	go func() {
		postgres.Get().Delete(&model.AskMessage{}, "session_id = ?", sessionID)
	}()

	response.SuccessWithMessage(c, "删除成功", nil)
}
