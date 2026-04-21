package handler

import (
	"bytes"
	"dev_metric/config"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
)

// AnalysisQuestion 决策分析 - 转发到 Python AI
func AnalysisQuestion(c *gin.Context) {
	var req struct {
		Query       string   `json:"query"`
		SessionID  string   `json:"session_id"`
		MetricCodes []string `json:"metric_codes"`
		TimeRange  string   `json:"time_range"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, gin.H{"code": 400, "message": "参数错误"})
		return
	}

	cfg := config.Get()
	aiURL := fmt.Sprintf("http://%s:%d/api/v1/analysis/analyze", cfg.AI.Host, cfg.AI.Port)

	// 确保 metric_codes 是空数组而不是 null
	if req.MetricCodes == nil {
		req.MetricCodes = []string{}
	}

	payload := map[string]interface{}{
		"query":        req.Query,
		"session_id":   req.SessionID,
		"metric_codes": req.MetricCodes,
		"time_range":   req.TimeRange,
	}
	jsonData, _ := json.Marshal(payload)

	// 创建 HTTP 请求
	httpReq, _ := http.NewRequest("POST", aiURL, bytes.NewBuffer(jsonData))
	httpReq.Header.Set("Content-Type", "application/json")
	if auth := c.GetHeader("Authorization"); auth != "" {
		httpReq.Header.Set("Authorization", auth)
	}

	client := &http.Client{}
	resp, err := client.Do(httpReq)
	if err != nil {
		c.JSON(500, gin.H{"code": 500, "message": "AI 服务暂时不可用"})
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	c.Data(resp.StatusCode, "application/json", body)
}

// AnalysisStream 决策分析流式 - 转发到 Python AI
func AnalysisStream(c *gin.Context) {
	var req struct {
		Query       string   `json:"query"`
		SessionID  string   `json:"session_id"`
		MetricCodes []string `json:"metric_codes"`
		TimeRange  string   `json:"time_range"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, gin.H{"code": 400, "message": "参数错误"})
		return
	}

	cfg := config.Get()
	aiURL := fmt.Sprintf("http://%s:%d/api/v1/analysis/stream", cfg.AI.Host, cfg.AI.Port)

	// 确保 metric_codes 是空数组而不是 null
	if req.MetricCodes == nil {
		req.MetricCodes = []string{}
	}

	payload := map[string]interface{}{
		"query":        req.Query,
		"session_id":   req.SessionID,
		"metric_codes": req.MetricCodes,
		"time_range":   req.TimeRange,
	}
	jsonData, _ := json.Marshal(payload)

	// 创建 HTTP 请求，带上 Authorization header
	httpReq, _ := http.NewRequest("POST", aiURL, bytes.NewBuffer(jsonData))
	httpReq.Header.Set("Content-Type", "application/json")
	if auth := c.GetHeader("Authorization"); auth != "" {
		httpReq.Header.Set("Authorization", auth)
	}

	client := &http.Client{}
	resp, err := client.Do(httpReq)
	if err != nil {
		c.JSON(500, gin.H{"code": 500, "message": "AI 服务暂时不可用"})
		return
	}
	defer resp.Body.Close()

	// 设置 SSE 相关响应头
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Accel-Buffering", "no")

	// 直接转发 Python AI 的响应流（使用 1KB 缓冲 + 手动 flush）
	c.Stream(func(w io.Writer) bool {
		buf := make([]byte, 1024)
		for {
			n, err := resp.Body.Read(buf)
			if n > 0 {
				if _, err := w.Write(buf[:n]); err != nil {
					// 写入错误，停止
					return false
				}
				// 手动 flush，让数据尽快发送
				if flusher, ok := w.(http.Flusher); ok {
					flusher.Flush()
				}
			}
			if err != nil {
				// 读取完毕（err != nil），停止 Stream
				return false
			}
			// n == 0 && err == nil 的情况：短暂等待后重试
			// 不做任何 sleep，避免 busy loop
		}
	})
}
