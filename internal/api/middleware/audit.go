package middleware

import (
	"bytes"
	"dev_metric/internal/service"
	"encoding/json"
	"io"
	"regexp"
	"strings"
	"time"

	"github.com/gin-gonic/gin"

	"dev_metric/pkg/logger"
)

// AuditMiddleware 审计日志中间件
// 记录所有API请求的SQL操作，支持：
// - 敏感数据脱敏（密码、密钥等）
// - SQL执行日志记录
// - 请求响应时间追踪
func AuditMiddleware() gin.HandlerFunc {
	auditService := service.NewSQLAuditService()

	return func(c *gin.Context) {
		// 记录开始时间
		startTime := time.Now()

		// 获取客户端IP
		clientIP := c.ClientIP()

		// 获取用户ID（从context中，认证后会有）
		userID := getUserID(c)

		// 记录请求体（如果是POST/PUT）
		var requestBody string
		if c.Request.Method == "POST" || c.Request.Method == "PUT" || c.Request.Method == "PATCH" {
			bodyBytes, _ := io.ReadAll(c.Request.Body)
			c.Request.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))
			requestBody = sanitizeSensitiveData(string(bodyBytes))
		}

		// 处理请求
		c.Next()

		// 计算耗时
		duration := time.Since(startTime)

		// 根据路径和方法判断操作类型
		operation := c.Request.Method + " " + c.FullPath()
		if c.FullPath() == "" {
			operation = c.Request.Method + " " + c.Request.URL.Path
		}

		// 构建审计日志
		auditLog := map[string]interface{}{
			"user_id":      userID,
			"operation":    operation,
			"ip_address":   clientIP,
			"user_agent":  c.Request.UserAgent(),
			"status_code": c.Writer.Status(),
			"duration_ms":  duration.Milliseconds(),
			"request_body": requestBody,
			"trace_id":     c.GetHeader("X-Trace-ID"),
		}

		// 异步记录日志（不阻塞响应）
		go func() {
			// 根据不同操作类型调用不同的审计方法
			switch {
			case isMetricQuery(c):
				// 指标查询
				metricID := getMetricIDFromContext(c)
				statusCode := c.Writer.Status()
				auditStatus := int16(0)
				if statusCode/100 != 2 {
					auditStatus = int16(1)
				}
				auditService.LogSQL(userID, operation, metricID, auditStatus, "", clientIP)

			case isMetricWrite(c):
				// 指标写操作
				metricID := getMetricIDFromContext(c)
				auditService.LogSQL(userID, operation, metricID, 0, "", clientIP)

			case isAlertConfig(c):
				// 告警配置
				auditService.LogAlertConfig(userID, getAlertIDFromContext(c), c.Request.Method, clientIP)

			case isNLPConfig(c):
				// NLP配置
				auditService.LogNLPConfig(userID, "nlp_template", c.Request.Method, clientIP)

			default:
				// 其他操作 - 只记录操作本身
				statusCode := c.Writer.Status()
				auditStatus := int16(0)
				if statusCode/100 != 2 {
					auditStatus = int16(1)
				}
				auditService.LogSQL(userID, operation, nil, auditStatus, "", clientIP)
			}
		}()

		// 记录访问日志
		logAudit(auditLog)
	}
}

// getUserID 从context获取用户ID
func getUserID(c *gin.Context) uint {
	if userID, exists := c.Get("user_id"); exists {
		if id, ok := userID.(uint); ok {
			return id
		}
	}
	return 0 // 匿名用户
}

// sanitizeSensitiveData 脱敏敏感数据
func sanitizeSensitiveData(data string) string {
	// 脱敏密码
	passwordPatterns := []string{
		`"password"\s*:\s*"[^"]*"`,
		`"password"\s*:\s*'[^']*'`,
		`password=([^&\s]+)`,
	}
	for _, pattern := range passwordPatterns {
		re := regexp.MustCompile(pattern)
		data = re.ReplaceAllStringFunc(data, func(match string) string {
			if strings.Contains(match, "password") {
				return `"password": "***"`
			}
			return "password=***"
		})
	}

	// 脱敏API Key
	apiKeyPatterns := []string{
		`"api_key"\s*:\s*"[^"]*"`,
		`"apiKey"\s*:\s*"[^"]*"`,
		`"secret"\s*:\s*"[^"]*"`,
	}
	for _, pattern := range apiKeyPatterns {
		re := regexp.MustCompile(pattern)
		data = re.ReplaceAllString(data, `"***": "***"`)
	}

	// 脱敏token
	tokenPatterns := []string{
		`"token"\s*:\s*"[^"]*"`,
		`"access_token"\s*:\s*"[^"]*"`,
		`"refresh_token"\s*:\s*"[^"]*"`,
	}
	for _, pattern := range tokenPatterns {
		re := regexp.MustCompile(pattern)
		data = re.ReplaceAllString(data, `"***": "***"`)
	}

	return data
}

// isMetricQuery 判断是否为指标查询操作
func isMetricQuery(c *gin.Context) bool {
	return (c.Request.Method == "GET" && strings.HasPrefix(c.FullPath(), "/api/v1/metrics"))
}

// isMetricWrite 判断是否为指标写操作
func isMetricWrite(c *gin.Context) bool {
	method := c.Request.Method
	path := c.FullPath()
	return (method == "POST" || method == "PUT" || method == "DELETE") &&
		strings.HasPrefix(path, "/api/v1/metrics")
}

// isAlertConfig 判断是否为告警配置操作
func isAlertConfig(c *gin.Context) bool {
	path := c.FullPath()
	return strings.HasPrefix(path, "/api/v1/alerts")
}

// isNLPConfig 判断是否为NLP配置操作
func isNLPConfig(c *gin.Context) bool {
	path := c.FullPath()
	return strings.HasPrefix(path, "/api/v1/nlp")
}

// getMetricIDFromContext 从context获取指标ID
func getMetricIDFromContext(c *gin.Context) *uint {
	if idStr := c.Param("id"); idStr != "" {
		var id uint
		if _, err := json.Marshal(idStr); err == nil {
			// 简单转换
			for _, ch := range idStr {
				if ch >= '0' && ch <= '9' {
					id = id*10 + uint(ch-'0')
				}
			}
			return &id
		}
	}
	return nil
}

// getAlertIDFromContext 从context获取告警ID
func getAlertIDFromContext(c *gin.Context) uint {
	if idStr := c.Param("id"); idStr != "" {
		var id uint
		for _, ch := range idStr {
			if ch >= '0' && ch <= '9' {
				id = id*10 + uint(ch-'0')
			}
		}
		return id
	}
	return 0
}

// logAudit 记录审计日志到结构化日志
func logAudit(log map[string]interface{}) {
	// 使用 zerolog 记录审计日志
	event := logger.Info()

	if userID, ok := log["user_id"]; ok {
		event = event.Interface("user_id", userID)
	}
	if operation, ok := log["operation"]; ok {
		event = event.Interface("operation", operation)
	}
	if traceID, ok := log["trace_id"]; ok {
		event = event.Interface("trace_id", traceID)
	}
	if statusCode, ok := log["status_code"]; ok {
		event = event.Interface("status_code", statusCode)
	}
	if duration, ok := log["duration_ms"]; ok {
		event = event.Interface("duration_ms", duration)
	}

	event.Bool("audit", true).Msg("audit_log")
}
