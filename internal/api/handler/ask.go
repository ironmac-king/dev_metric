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
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// GetUserIDFromContext 从 gin.Context 获取当前用户ID
func GetUserIDFromContext(c *gin.Context) uint {
	if userID, exists := c.Get("user_id"); exists {
		if id, ok := userID.(uint); ok {
			return id
		}
	}
	return 0
}

// GetUserRoleFromContext 从 gin.Context 获取当前用户角色
func GetUserRoleFromContext(c *gin.Context) string {
	if role, exists := c.Get("role"); exists {
		if r, ok := role.(string); ok {
			return r
		}
	}
	return ""
}

// AskQuestion 智能问数 - 调用 Python AI 服务
func AskQuestion(c *gin.Context) {
	var req struct {
		Question   string `json:"question" binding:"required"`
		SessionID  string `json:"session_id"`
		Page       int    `json:"page"`
		PageSize   int    `json:"page_size"`
		EngineType string `json:"engine_type"`
		SqlMode    string `json:"sql_mode"` // SQL生成模式: "llm" | "template"
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

	// 获取当前用户ID
	userID := GetUserIDFromContext(c)

	// 获取用户的 dept_id 和 data_filter
	var user model.User
	var deptID int
	var dataFilter string
	if err := postgres.Get().First(&user, userID).Error; err == nil {
		deptID = user.DeptID
		dataFilter = user.DataFilter
	}

	// 调用 Python AI 服务
	aiURL := fmt.Sprintf("http://localhost:8081/api/v1/ask")

	payload := map[string]interface{}{
		"question":    req.Question,
		"session_id":  req.SessionID,
		"user_id":    strconv.FormatUint(uint64(userID), 10),
		"dept_id":    deptID,
		"data_filter": dataFilter,
		"page":       req.Page,
		"page_size":  req.PageSize,
		"engine_type": req.EngineType,
		"sql_mode":   req.SqlMode, // SQL生成模式: "llm" | "template"
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

	// 只解析需要存数据库的字段
	var pythonResp map[string]interface{}
	json.Unmarshal(body, &pythonResp)

	// 获取 session_id（供后续使用）
	sessionID := ""
	if sid, ok := pythonResp["session_id"].(string); ok {
		sessionID = sid
	}

	// 从 Python 响应获取 session_id，同步到 Go 数据库
	if sessionID != "" {
		now := time.Now()
		title := ""
		if answer, ok := pythonResp["answer"].(string); ok {
			title = answer
		}
		userIDStr := strconv.FormatUint(uint64(userID), 10)
		if userIDStr == "0" {
			userIDStr = "default"
		}
		summary := model.AskSessionSummary{
			SessionID:     sessionID,
			Title:        title,
			FirstQuestion: req.Question,
			MessageCount: 1,
			UserID:        userIDStr,
			UpdatedAt:    now,
		}
		postgres.Get().Where("session_id = ?", sessionID).Assign(summary).FirstOrCreate(&model.AskSessionSummary{})

		// 保存用户消息和助手消息到 AskMessage 表
		saveMessages := func() {
			ctx := context.Background()
			cacheKey := fmt.Sprintf("ask:messages:%s", sessionID)

			// 构造用户消息
			userMsg := model.AskMessage{
				SessionID:         sessionID,
				Role:              "user",
				Content:           req.Question,
				SQL:               "",
				ResultData:        "",
				ComparisonResults: "",
				DrillDownDims:    "",
				Breadcrumbs:       "",
				MetricCode:        "",
			}

			// 序列化 result_data
			var resultDataStr string
			if rd, ok := pythonResp["result_data"].(string); ok {
				resultDataStr = rd
			} else if rdMap, ok := pythonResp["result_data"]; ok && rdMap != nil {
				if rdBytes, err := json.Marshal(rdMap); err == nil {
					resultDataStr = string(rdBytes)
				}
			}

			// 序列化 comparison_results
			var comparisonResultsStr string
			if cr, ok := pythonResp["comparison_results"]; ok && cr != nil {
				if crBytes, err := json.Marshal(cr); err == nil {
					comparisonResultsStr = string(crBytes)
				}
			}

			// 序列化 drill_down_dims
			var drillDownDimsStr string
			if dd, ok := pythonResp["drill_down_dims"]; ok && dd != nil {
				if ddBytes, err := json.Marshal(dd); err == nil {
					drillDownDimsStr = string(ddBytes)
				}
			}

			// 序列化 breadcrumbs
			var breadcrumbsStr string
			if bc, ok := pythonResp["breadcrumbs"]; ok && bc != nil {
				if bcBytes, err := json.Marshal(bc); err == nil {
					breadcrumbsStr = string(bcBytes)
				}
			}

			// 获取 metric_code
			metricCode := ""
			if mc, ok := pythonResp["metric_code"].(string); ok {
				metricCode = mc
			}

			// 序列化 thinking_steps
			var thinkingStepsStr string
			if ts, ok := pythonResp["thinking_steps"]; ok && ts != nil {
				if tsBytes, err := json.Marshal(ts); err == nil {
					thinkingStepsStr = string(tsBytes)
				}
			}

			// 构造助手消息
			// 安全提取字符串字段，避免 nil 值导致 panic
			getString := func(key string) string {
				if v, ok := pythonResp[key].(string); ok {
					return v
				}
				return ""
			}

			assistantMsg := model.AskMessage{
				SessionID:         sessionID,
				Role:              "assistant",
				Content:           getString("answer"),
				SQL:               getString("sql"),
				ResultData:        resultDataStr,
				ComparisonResults: comparisonResultsStr,
				DrillDownDims:    drillDownDimsStr,
				Breadcrumbs:       breadcrumbsStr,
				MetricCode:        metricCode,
				ThinkingSteps:     thinkingStepsStr,
			}

			// 同步写 Redis（7天过期）
			var existing []model.AskMessage
			if err := cache.GetJSON(ctx, cacheKey, &existing); err != nil {
				existing = []model.AskMessage{}
			}
			existing = append(existing, userMsg)
			existing = append(existing, assistantMsg)
			cache.SetJSON(ctx, cacheKey, existing, 7*24*time.Hour)

			// 异步写 PostgreSQL
			go func() {
				postgres.Get().Create(&userMsg)
				postgres.Get().Create(&assistantMsg)
			}()
		}
		saveMessages()
	}

	// 写入问数分析日志
	userIDStr := strconv.FormatUint(uint64(userID), 10)
	if userIDStr == "0" {
		userIDStr = "default"
	}
	analysisLog := model.AskAnalysisLog{
		UserID:     userIDStr,
		SessionID:  sessionID,
		Question:   req.Question,
		Answer:     "",
		Intent:     "",
		Success:    true,
		FailStage:  "",
		FailReason: "",
		Suggestion: "",
	}
	if answer, ok := pythonResp["answer"].(string); ok {
		analysisLog.Answer = answer
	}
	if intent, ok := pythonResp["intent"].(string); ok {
		analysisLog.Intent = intent
	}
	if needsClarification, ok := pythonResp["needs_clarification"].(bool); ok && needsClarification {
		analysisLog.Success = false
		analysisLog.FailStage = "sql"
		if msg, ok := pythonResp["clarification_message"].(string); ok {
			analysisLog.FailReason = msg
		}
	}
	if failReason, ok := pythonResp["fail_reason"].(string); ok && failReason != "" {
		analysisLog.Success = false
		if analysisLog.FailStage == "" {
			analysisLog.FailStage = "unknown"
		}
		analysisLog.FailReason = failReason
	}
	if suggestion, ok := pythonResp["suggestion"].(string); ok {
		analysisLog.Suggestion = suggestion
	}
	if thinkingSteps, ok := pythonResp["thinking_steps"].([]interface{}); ok {
		if stepsJSON, err := json.Marshal(thinkingSteps); err == nil {
			analysisLog.ThinkingSteps = string(stepsJSON)
		}
	} else if thinkingStepsStr, ok := pythonResp["thinking_steps"].(string); ok {
		analysisLog.ThinkingSteps = thinkingStepsStr
	}
	postgres.Get().Create(&analysisLog)

	// 从原始 JSON 字节中直接提取 result_data（保持 Python 返回的原始列顺序）
	var resultDataJSON []byte
	bodyStr := string(body)
	if idx := strings.Index(bodyStr, `"result_data":`); idx >= 0 {
		start := idx + len(`"result_data":`)
		for start < len(bodyStr) && (bodyStr[start] == ' ' || bodyStr[start] == '\t' || bodyStr[start] == '\n' || bodyStr[start] == '\r') {
			start++
		}
		if start < len(bodyStr) {
			depth := 0
			inString := false
			escape := false
			dataStart := start
			if bodyStr[start] == '[' {
				for i := start; i < len(bodyStr); i++ {
					ch := bodyStr[i]
					if escape {
						escape = false
						continue
					}
					if ch == '\\' {
						escape = true
						continue
					}
					if ch == '"' {
						inString = !inString
						continue
					}
					if inString {
						continue
					}
					if ch == '[' {
						if depth == 0 {
							dataStart = i
						}
						depth++
					} else if ch == ']' {
						depth--
						if depth == 0 {
							resultDataJSON = []byte(bodyStr[dataStart : i+1])
							break
						}
					}
				}
			}
		}
	}

	// 手动拼接 JSON 响应字符串，保证 key 顺序固定
	// 顺序固定为: session_id, answer, suggest, sql, thinking_steps,
	//   drill_down_dims, breadcrumbs, result_data, total, page,
	//   page_size, needs_clarification, clarification_message, clarification_type,
	//   matched_metrics, comparison_results, metric_code,
	//   dimension_value_candidates, dimension_value_matched_text
	var sb strings.Builder
	sb.WriteString("{")
	first := true
	addField := func(key string, value interface{}) {
		if !first {
			sb.WriteString(",")
		}
		first = false
		sb.WriteString(`"`)
		sb.WriteString(key)
		sb.WriteString(`":`)
		if vb, err := json.Marshal(value); err == nil {
			sb.Write(vb)
		} else {
			sb.WriteString("null")
		}
	}
	// 逐字段添加（固定顺序）
	if v := pythonResp["session_id"]; v != nil {
		addField("session_id", v)
	} else {
		addField("session_id", "")
	}
	if v := pythonResp["answer"]; v != nil {
		addField("answer", v)
	} else {
		addField("answer", "")
	}
	if v := pythonResp["suggest"]; v != nil {
		addField("suggest", v)
	} else {
		addField("suggest", []string{})
	}
	if v := pythonResp["sql"]; v != nil {
		addField("sql", v)
	} else {
		addField("sql", "")
	}
	if v := pythonResp["thinking_steps"]; v != nil {
		addField("thinking_steps", v)
	} else {
		addField("thinking_steps", []interface{}{})
	}
	if v := pythonResp["drill_down_dims"]; v != nil {
		addField("drill_down_dims", v)
	} else {
		addField("drill_down_dims", []interface{}{})
	}
	if v := pythonResp["breadcrumbs"]; v != nil {
		addField("breadcrumbs", v)
	} else {
		addField("breadcrumbs", []interface{}{})
	}
	// result_data 使用原始 JSON（保持列顺序）
	sb.WriteString(",\"result_data\":")
	if len(resultDataJSON) > 0 {
		sb.Write(resultDataJSON)
	} else {
		sb.WriteString("null")
	}
	if v := pythonResp["total"]; v != nil {
		addField("total", v)
	} else {
		addField("total", 0)
	}
	if v := pythonResp["page"]; v != nil {
		addField("page", v)
	} else {
		addField("page", 1)
	}
	if v := pythonResp["page_size"]; v != nil {
		addField("page_size", v)
	} else {
		addField("page_size", 10)
	}
	if v := pythonResp["needs_clarification"]; v != nil {
		addField("needs_clarification", v)
	} else {
		addField("needs_clarification", false)
	}
	if v := pythonResp["clarification_message"]; v != nil {
		addField("clarification_message", v)
	} else {
		addField("clarification_message", nil)
	}
	if v := pythonResp["clarification_type"]; v != nil {
		addField("clarification_type", v)
	} else {
		addField("clarification_type", nil)
	}
	// 槽位追问相关字段
	if v := pythonResp["pending_slot_options"]; v != nil {
		addField("pending_slot_options", v)
	} else {
		addField("pending_slot_options", nil)
	}
	if v := pythonResp["pending_slot_name"]; v != nil {
		addField("pending_slot_name", v)
	} else {
		addField("pending_slot_name", nil)
	}
	if v := pythonResp["pending_slots"]; v != nil {
		addField("pending_slots", v)
	} else {
		addField("pending_slots", nil)
	}
	if v := pythonResp["slot_display_name"]; v != nil {
		addField("slot_display_name", v)
	} else {
		addField("slot_display_name", nil)
	}
	if v := pythonResp["matched_metrics"]; v != nil {
		addField("matched_metrics", v)
	} else {
		addField("matched_metrics", []interface{}{})
	}
	if v := pythonResp["comparison_results"]; v != nil {
		addField("comparison_results", v)
	} else {
		addField("comparison_results", nil)
	}
	if v := pythonResp["metric_code"]; v != nil {
		addField("metric_code", v)
	} else {
		addField("metric_code", "")
	}
	if v := pythonResp["dimension_value_candidates"]; v != nil {
		addField("dimension_value_candidates", v)
	} else {
		addField("dimension_value_candidates", nil)
	}
	if v := pythonResp["dimension_value_matched_text"]; v != nil {
		addField("dimension_value_matched_text", v)
	} else {
		addField("dimension_value_matched_text", "")
	}
	sb.WriteString("}")

	c.Header("Content-Type", "application/json")
	c.Status(http.StatusOK)
	c.Writer.Write([]byte(sb.String()))
}

// GetAskHistory 获取对话历史
func GetAskHistory(c *gin.Context) {
	sessionID := c.Query("session_id")
	if sessionID == "" {
		response.Error(c, response.CodeBadRequest, "session_id 不能为空")
		return
	}

	// 获取当前用户ID
	userID := GetUserIDFromContext(c)

	// 调用 Python AI 服务（传递 user_id 用于隔离）
	resp, err := http.Get(fmt.Sprintf("http://localhost:8081/api/v1/ask/history?session_id=%s&user_id=%d", sessionID, userID))
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
	pythonURL := fmt.Sprintf("http://localhost:8081/api/v1/ask/clear?session_id=%s", req.SessionID)
	resp, err := http.Post(pythonURL, "application/json", nil)
	if err != nil {
		response.Error(c, response.CodeInternalError, "AI 服务调用失败")
		return
	}
	defer resp.Body.Close()

	// 同时删除 Go 后端的会话摘要记录
	postgres.Get().Delete(&model.AskSessionSummary{}, "session_id = ?", req.SessionID)

	response.SuccessWithMessage(c, "会话已清除", nil)
}

// ClearSessionInternal 清除会话（内部版本，不需要认证，使用 query 参数）
func ClearSessionInternal(c *gin.Context) {
	sessionID := c.Query("session_id")
	if sessionID == "" {
		response.Error(c, response.CodeBadRequest, "session_id 不能为空")
		return
	}

	// 调用 Python AI 服务
	pythonURL := fmt.Sprintf("http://localhost:8081/api/v1/ask/clear?session_id=%s", sessionID)
	resp, err := http.Post(pythonURL, "application/json", nil)
	if err != nil {
		response.Error(c, response.CodeInternalError, "AI 服务调用失败")
		return
	}
	defer resp.Body.Close()

	// 同时删除 Go 后端的会话摘要记录
	postgres.Get().Delete(&model.AskSessionSummary{}, "session_id = ?", sessionID)

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
		SessionID       string   `json:"session_id" binding:"required"`
		DimensionNames  []string `json:"dimension_names" binding:"required"`
		MetricCode      string   `json:"metric_code"`
		CurrentSQL      string   `json:"current_sql" binding:"required"`
		CurrentGroupBy  string   `json:"current_group_by"`
		Page            int      `json:"page"`
		PageSize        int      `json:"page_size"`
		ComparisonTypes []string `json:"comparison_types"`
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
		"comparison_types": req.ComparisonTypes,
	}
	jsonData, _ := json.Marshal(payload)

	resp, err := http.Post(aiURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		response.Error(c, response.CodeInternalError, "下钻服务调用失败: "+err.Error())
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	// 直接返回 Python 服务的原始响应（与 AskQuestion 保持一致）
	c.Header("Content-Type", "application/json")
	c.Status(http.StatusOK)
	c.Writer.Write(body)
}

// SaveMessage 保存会话消息（Redis 缓存 + 异步落库 PostgreSQL）
func SaveMessage(c *gin.Context) {
	fmt.Printf("[DEBUG SaveMessage] 请求到达, session_id=%s\n", c.Query("session_id"))

	var req struct {
		SessionID        string `json:"session_id" binding:"required"`
		Role            string `json:"role" binding:"required"` // user / assistant
		Content         string `json:"content" binding:"required"`
		SQL             string `json:"sql"`
		ResultData      string `json:"result_data"`
		ComparisonResults string `json:"comparison_results"`
		DrillDownDims   string `json:"drill_down_dims"`
		Breadcrumbs     string `json:"breadcrumbs"`
		MetricCode      string `json:"metric_code"`
		ThinkingSteps   string `json:"thinking_steps"` // 思考过程
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		fmt.Printf("[DEBUG SaveMessage] BindJSON失败: %v\n", err)
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	fmt.Printf("[DEBUG SaveMessage] 解析成功, SessionID=%s, Role=%s, Content长度=%d\n", req.SessionID, req.Role, len(req.Content))

	// 构造消息
	msg := model.AskMessage{
		SessionID:        req.SessionID,
		Role:            req.Role,
		Content:         req.Content,
		SQL:             req.SQL,
		ResultData:      req.ResultData,
		ComparisonResults: req.ComparisonResults,
		DrillDownDims:   req.DrillDownDims,
		Breadcrumbs:     req.Breadcrumbs,
		MetricCode:      req.MetricCode,
		ThinkingSteps:   req.ThinkingSteps,
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
	fmt.Printf("[DEBUG GetMessages] 请求到达, session_id=%s\n", sessionID)
	if sessionID == "" {
		response.Error(c, response.CodeBadRequest, "session_id 不能为空")
		return
	}

	// 优先从 Redis 读
	ctx := context.Background()
	cacheKey := fmt.Sprintf("ask:messages:%s", sessionID)
	fmt.Printf("[DEBUG GetMessages] cacheKey=%s\n", cacheKey)
	var messages []model.AskMessage
	if err := cache.GetJSON(ctx, cacheKey, &messages); err == nil && len(messages) > 0 {
		fmt.Printf("[DEBUG GetMessages] Redis命中, 消息数=%d\n", len(messages))
		// 将 JSON 字符串反序列化为对象
		result := make([]map[string]interface{}, len(messages))
		for i, msg := range messages {
			result[i] = map[string]interface{}{
				"role":                msg.Role,
				"content":             msg.Content,
				"sql":                 msg.SQL,
				"created_at":          msg.CreatedAt,
				"result_data":         decodeJSON(msg.ResultData),
				"comparison_results":  decodeJSON(msg.ComparisonResults),
				"drill_down_dims":    decodeJSON(msg.DrillDownDims),
				"breadcrumbs":         decodeJSON(msg.Breadcrumbs),
				"metric_code":         msg.MetricCode,
				"thinking_steps":      decodeJSON(msg.ThinkingSteps),
			}
		}
		response.Success(c, gin.H{"messages": result, "source": "redis"})
		return
	}

	// Redis 没有，从 PostgreSQL 读
	fmt.Printf("[DEBUG GetMessages] Redis未命中, 查询PostgreSQL, session_id=%s\n", sessionID)
	postgres.Get().Where("session_id = ?", sessionID).Order("created_at ASC").Find(&messages)
	fmt.Printf("[DEBUG GetMessages] PostgreSQL查询结果, 消息数=%d\n", len(messages))

	// 回填 Redis
	if len(messages) > 0 {
		go func() {
			cache.SetJSON(ctx, cacheKey, messages, 7*24*time.Hour)
		}()
	}

	// 将 JSON 字符串反序列化为对象
	result := make([]map[string]interface{}, len(messages))
	for i, msg := range messages {
		result[i] = map[string]interface{}{
			"role":                msg.Role,
			"content":             msg.Content,
			"sql":                 msg.SQL,
			"created_at":          msg.CreatedAt,
			"result_data":         decodeJSON(msg.ResultData),
			"comparison_results":  decodeJSON(msg.ComparisonResults),
			"drill_down_dims":    decodeJSON(msg.DrillDownDims),
			"breadcrumbs":         decodeJSON(msg.Breadcrumbs),
			"metric_code":         msg.MetricCode,
			"thinking_steps":      decodeJSON(msg.ThinkingSteps),
		}
	}
	response.Success(c, gin.H{"messages": result, "source": "db"})
}

// decodeJSON 将 JSON 字符串解码为 interface{}
func decodeJSON(s string) interface{} {
	if s == "" {
		return nil
	}
	var result interface{}
	if err := json.Unmarshal([]byte(s), &result); err != nil {
		return nil
	}
	return result
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

// GetLastResult 获取最近一次问数结果（供决策分析模块调用）
func GetLastResult(c *gin.Context) {
	sessionID := c.Query("session_id")
	if sessionID == "" {
		response.Error(c, response.CodeBadRequest, "session_id 不能为空")
		return
	}

	ctx := context.Background()

	// 优先从 Redis 获取最近一条 assistant 消息
	cacheKey := fmt.Sprintf("ask:messages:%s", sessionID)
	var messages []model.AskMessage
	if err := cache.GetJSON(ctx, cacheKey, &messages); err != nil || len(messages) == 0 {
		// Redis 没有，从 PostgreSQL 读取
		var dbMessages []model.AskMessage
		postgres.Get().Where("session_id = ? AND role = ?", sessionID, "assistant").
			Order("created_at DESC").Limit(1).Find(&dbMessages)
		if len(dbMessages) == 0 {
			response.Error(c, 404, "未找到问数记录")
			return
		}
		messages = dbMessages
	} else {
		// 从 Redis 消息中筛选最后一条 assistant 消息
		var lastAssistant *model.AskMessage
		for i := len(messages) - 1; i >= 0; i-- {
			if messages[i].Role == "assistant" {
				lastAssistant = &messages[i]
				break
			}
		}
		if lastAssistant == nil {
			response.Error(c, 404, "未找到问数记录")
			return
		}
		messages = []model.AskMessage{*lastAssistant}
	}

	// 取最后一条 assistant 消息
	lastMsg := messages[len(messages)-1]

	// 提取指标 code（可能多个，用逗号分隔）
	metricCode := lastMsg.MetricCode

	// 解析 result_data
	var resultData interface{}
	if lastMsg.ResultData != "" {
		json.Unmarshal([]byte(lastMsg.ResultData), &resultData)
	}

	// 返回结果
	response.Success(c, gin.H{
		"metric_code":  metricCode,
		"result_data":  resultData,
		"sql":          lastMsg.SQL,
		"created_at":   lastMsg.CreatedAt,
	})
}
