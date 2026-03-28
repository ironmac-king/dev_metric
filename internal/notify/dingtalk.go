package notify

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// DingTalk 钉钉通知
type DingTalk struct {
	webhook string
	secret  string
}

func NewDingTalk(webhook, secret string) *DingTalk {
	return &DingTalk{
		webhook: webhook,
		secret:  secret,
	}
}

// SendMessage 发送钉钉消息
func (d *DingTalk) SendMessage(title, content string) error {
	// 获取签名
	timestamp, sign := d.generateSign()

	// 发送请求
	apiURL := fmt.Sprintf("%s&timestamp=%d&sign=%s", d.webhook, timestamp, url.QueryEscape(sign))

	payload := fmt.Sprintf(`{
		"msgtype": "markdown",
		"markdown": {
			"title": "%s",
			"text": "%s"
		}
	}`, title, strings.ReplaceAll(content, "\n", "\n\n"))

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Post(apiURL, "application/json", strings.NewReader(payload))
	if err != nil {
		return fmt.Errorf("发送钉钉消息失败: %w", err)
	}
	defer resp.Body.Close()

	return nil
}

// SendTextMessage 发送文本消息
func (d *DingTalk) SendTextMessage(content string) error {
	timestamp, sign := d.generateSign()
	apiURL := fmt.Sprintf("%s&timestamp=%d&sign=%s", d.webhook, timestamp, url.QueryEscape(sign))

	payload := fmt.Sprintf(`{
		"msgtype": "text",
		"text": {
			"content": "%s"
		}
	}`, content)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Post(apiURL, "application/json", strings.NewReader(payload))
	if err != nil {
		return fmt.Errorf("发送钉钉消息失败: %w", err)
	}
	defer resp.Body.Close()

	return nil
}

// generateSign 生成签名
func (d *DingTalk) generateSign() (int64, string) {
	timestamp := time.Now().UnixMilli()
	signStr := fmt.Sprintf("%d\n%s", timestamp, d.secret)

	h := hmac.New(sha256.New, []byte(d.secret))
	h.Write([]byte(fmt.Sprintf("%d\n%s", timestamp, d.secret)))

	sign := base64.StdEncoding.EncodeToString(h.Sum(nil))
	return timestamp, sign
}

// BuildAlertMessage 构建告警消息
func BuildAlertMessage(metricName, triggerValue, threshold, condition, duration string) string {
	return fmt.Sprintf(`### 指标告警

**指标名称**: %s
**触发条件**: %s %s
**触发值**: %s
**持续时间**: %s

> 请及时处理`, metricName, condition, threshold, triggerValue, duration)
}
