package middleware

import (
	"time"

	"github.com/gin-gonic/gin"

	"dev_metric/pkg/logger"
)

// SecurityMiddleware 安全中间件
func SecurityMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 安全响应头
		c.Header("X-Frame-Options", "DENY")
		c.Header("X-Content-Type-Options", "nosniff")
		c.Header("Strict-Transport-Security", "max-age=31536000")
		c.Header("X-XSS-Protection", "1; mode=block")

		c.Next()
	}
}

// TraceMiddleware 链路追踪中间件
func TraceMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		traceID := c.GetHeader("X-Trace-ID")
		if traceID == "" {
			traceID = generateTraceID()
		}
		c.Set("trace_id", traceID)
		c.Header("X-Trace-ID", traceID)

		start := time.Now()
		c.Next()
		duration := time.Since(start)

		// 获取用户信息（如果已登录）
		var userID interface{}
		if uid, exists := c.Get("user_id"); exists {
			userID = uid
		}

		// 记录请求日志（使用 zerolog）
		logger.Log.Info().
			Str("trace_id", traceID).
			Str("method", c.Request.Method).
			Str("path", c.Request.URL.Path).
			Int64("duration_ms", duration.Milliseconds()).
			Int("status", c.Writer.Status()).
			Str("ip", c.ClientIP()).
			Interface("user_id", userID).
			Msg("http_request")
	}
}

func generateTraceID() string {
	return time.Now().Format("20060102150405") + "-" + randomString(8)
}

func randomString(n int) string {
	const letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, n)
	for i := range b {
		b[i] = letters[time.Now().UnixNano()%int64(len(letters))]
	}
	return string(b)
}
