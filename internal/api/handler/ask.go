package handler

import (
	"bytes"
	"dev_metric/config"
	"dev_metric/pkg/response"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
)

// AskQuestion 智能问数 - 调用 Python AI 服务
func AskQuestion(c *gin.Context) {
	var req struct {
		Question  string `json:"question" binding:"required"`
		SessionID string `json:"session_id"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 调用 Python AI 服务
	aiURL := fmt.Sprintf("http://localhost:8081/api/v1/ask")

	payload := map[string]string{
		"question":   req.Question,
		"session_id": req.SessionID,
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

	response.Success(c, gin.H{
		"session_id":     aiResp["session_id"],
		"answer":        aiResp["answer"],
		"suggest":       aiResp["suggest"],
		"sql":           aiResp["sql"],
		"thinking_steps": aiResp["thinking_steps"],
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

	// 调用 Python AI 服务
	payload := map[string]string{"session_id": req.SessionID}
	jsonData, _ := json.Marshal(payload)
	http.Post("http://localhost:8081/api/v1/ask/clear", "application/json", bytes.NewBuffer(jsonData))

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
