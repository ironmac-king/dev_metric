package middleware

import (
	"time"

	"github.com/gin-gonic/gin"
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

		// 记录请求日志
		gin.DefaultWriter.Write([]byte(
			`{"time":"` + start.Format(time.RFC3339) + `","level":"INFO","trace_id":"` + traceID + `","method":"` + c.Request.Method + `","path":"` + c.Request.URL.Path + `","duration_ms":` + string(rune(int(duration.Milliseconds()))) + `}` + "\n",
		))
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
