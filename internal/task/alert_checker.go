package task

import (
	"dev_metric/internal/model"
	"dev_metric/internal/notify"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/repository/starrocks"
	"fmt"
	"time"

	"dev_metric/pkg/logger"
)

// AlertChecker 告警检测任务
type AlertChecker struct {
	interval time.Duration
	stopCh   chan struct{}
}

func NewAlertChecker(interval time.Duration) *AlertChecker {
	return &AlertChecker{
		interval: interval,
		stopCh:   make(chan struct{}),
	}
}

func (ac *AlertChecker) Start() {
	logger.Info().Msg("告警检测任务启动")
	ticker := time.NewTicker(ac.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			ac.check()
		case <-ac.stopCh:
			logger.Info().Msg("告警检测任务停止")
			return
		}
	}
}

func (ac *AlertChecker) Stop() {
	close(ac.stopCh)
}

func (ac *AlertChecker) check() {
	var rules []model.AlertRule
	postgres.Get().Where("notify_status = ?", 1).Find(&rules)

	for _, rule := range rules {
		ac.checkRule(rule)
	}
}

func (ac *AlertChecker) checkRule(rule model.AlertRule) {
	var metric model.Metric
	if err := postgres.Get().First(&metric, rule.MetricID).Error; err != nil {
		logger.Error().Err(err).Uint("metric_id", rule.MetricID).Msg("获取指标失败")
		return
	}

	// 查询最新值
	data, err := starrocks.Query(metric.StarRocksSQL)
	if err != nil {
		logger.Error().Err(err).Uint("metric_id", rule.MetricID).Msg("查询指标数据失败")
		return
	}

	if len(data) == 0 {
		return
	}

	// 获取最新值
	var latestValue float64
	if v, ok := data[0]["value"].(float64); ok {
		latestValue = v
	}

	// 检查是否触发告警
	triggered := ac.isTriggered(latestValue, rule.ConditionType, rule.ThresholdValue)

	if triggered {
		ac.handleAlert(rule, metric, latestValue)
	}
}

func (ac *AlertChecker) isTriggered(value float64, conditionType string, threshold float64) bool {
	switch conditionType {
	case "gt":
		return value > threshold
	case "lt":
		return value < threshold
	case "gte":
		return value >= threshold
	case "lte":
		return value <= threshold
	case "eq":
		return value == threshold
	default:
		return false
	}
}

func (ac *AlertChecker) handleAlert(rule model.AlertRule, metric model.Metric, value float64) {
	// 检查是否已有未恢复的告警
	var existingAlert model.AlertRecord
	postgres.Get().Where("rule_id = ? AND status IN (0, 1)", rule.ID).
		Order("triggered_at DESC").First(&existingAlert)

	if existingAlert.ID != 0 {
		// 已有活跃告警，跳过
		return
	}

	// 创建告警记录
	record := model.AlertRecord{
		RuleID:         rule.ID,
		MetricID:       rule.MetricID,
		TriggerValue:   value,
		ThresholdValue: rule.ThresholdValue,
		Status:         0,
		Message:        notify.BuildAlertMessage(metric.Name, fmt.Sprintf("%.2f", value), fmt.Sprintf("%.2f", rule.ThresholdValue), rule.ConditionType, fmt.Sprintf("%d分钟", rule.Duration)),
		TriggeredAt:    time.Now(),
	}

	postgres.Get().Create(&record)

	// 发送钉钉通知
	if rule.DingtalkWebhook != "" {
		dt := notify.NewDingTalk(rule.DingtalkWebhook, rule.DingtalkSecret)
		if err := dt.SendMessage("指标告警", record.Message); err != nil {
			logger.Error().Err(err).Uint("rule_id", rule.ID).Msg("发送钉钉通知失败")
		} else {
			// 更新通知状态
			now := time.Now()
			record.Status = 1
			record.NotifiedAt = &now
			postgres.Get().Save(&record)
		}
	}
}
