package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/repository/starrocks"
	"dev_metric/pkg/response"
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
)

// GetDashboardSummary 获取仪表盘汇总数据
func GetDashboardSummary(c *gin.Context) {
	var totalMetrics int64
	var activeMetrics int64
	var totalAlerts int64
	var activeAlerts int64

	db := postgres.Get()

	db.Model(&model.Metric{}).Count(&totalMetrics)
	db.Model(&model.Metric{}).Where("status = ?", "在用").Count(&activeMetrics)
	db.Model(&model.AlertRule{}).Count(&totalAlerts)
	db.Model(&model.AlertRule{}).Where("notify_status = ?", 1).Count(&activeAlerts)

	// 按域统计指标数量
	type DomainStat struct {
		Domain string `json:"domain"`
		Count  int64  `json:"count"`
	}
	var domainStats []DomainStat
	db.Model(&model.Metric{}).
		Select("domain, count(*) as count").
		Group("domain").
		Scan(&domainStats)

	response.Success(c, gin.H{
		"total_metrics":  totalMetrics,
		"active_metrics": activeMetrics,
		"total_alerts":  totalAlerts,
		"active_alerts": activeAlerts,
		"domain_stats":  domainStats,
	})
}

// GetDashboardCharts 获取仪表盘图表数据
func GetDashboardCharts(c *gin.Context) {
	// TODO: 返回图表数据
	response.Success(c, gin.H{
		"trend_data":   []interface{}{},
		"category_data": []interface{}{},
	})
}

// MetricCard 指标卡片数据结构
type MetricCard struct {
	RuleID          uint    `json:"rule_id"`
	MetricID        uint    `json:"metric_id"`
	MetricCode      string  `json:"metric_code"`
	MetricName      string  `json:"metric_name"`
	Unit            string  `json:"unit"`
	CurrentValue    float64 `json:"current_value"`
	Threshold       float64 `json:"threshold"`
	ConditionType   string  `json:"condition_type"`    // gt/lt/gte/lte/eq
	ConditionText   string  `json:"condition_text"`    // 显示用：>, <, >=, <=, =
	Status          string  `json:"status"`            // normal/warning/critical
	LastCheck       string  `json:"last_check"`
	Name            string  `json:"name"`              // 规则名称
	WhereCondition  string  `json:"where_condition"`  // WHERE 条件
	DingtalkWebhook string  `json:"dingtalk_webhook"` // 钉钉 Webhook
	SQL             string  `json:"sql"`              // 指标 SQL
}

// GetMetricCards 获取指标卡片数据（用于 Dashboard 告警监控）
func GetMetricCards(c *gin.Context) {
	db := postgres.Get()

	type AlertRuleWithMetric struct {
		model.AlertRule
		MetricCode string `json:"metric_code"`
		MetricName string `json:"metric_name"`
		Unit       string `json:"unit"`
		SQL        string `json:"sql"`
	}

	var rules []AlertRuleWithMetric

	// 查询启用的告警规则及其关联指标
	db.Table("alert_rules").
		Select("alert_rules.*, metrics.metric_code, metrics.name as metric_name, metrics.unit, metrics.starrocks_sql as sql").
		Joins("LEFT JOIN metrics ON alert_rules.metric_id = metrics.id").
		Where("alert_rules.notify_status = ?", 1).
		Where("metrics.id IS NOT NULL").
		Scan(&rules)

	cards := make([]MetricCard, 0, len(rules))

	for _, rule := range rules {
		var currentValue float64
		var status string

		// 尝试从 StarRocks 查询实际值（带缓存）
		if rule.SQL != "" {
			// 拼接完整的 SQL：基础 SQL + WHERE 条件
			fullSQL := rule.SQL
			if rule.WhereCondition != "" {
				fullSQL = rule.SQL + " " + rule.WhereCondition
			}
			result, err := starrocks.QueryAlertRule(c.Request.Context(), fullSQL, rule.ID)
			if err != nil || len(result.Data) == 0 {
				// 查询失败时设置为空
				currentValue = 0
				status = "warning"
			} else {
				// 假设 SQL 返回的第一行第一列就是指标值
				for _, row := range result.Data {
					for _, v := range row {
						if v != nil {
							switch val := v.(type) {
							case float64:
								currentValue = val
							case float32:
								currentValue = float64(val)
							case int64:
								currentValue = float64(val)
							case int:
								currentValue = float64(val)
							case string:
								// 尝试解析字符串为数字
								var parsed float64
								if _, err := fmt.Sscanf(val, "%f", &parsed); err == nil {
									currentValue = parsed
								}
							}
							break
						}
					}
					break
				}

				// 根据条件判断状态
				status = getAlertStatus(rule.ConditionType, currentValue, rule.ThresholdValue)
			}
		} else {
			// 没有 SQL 时设为默认值
			currentValue = 0
			status = "warning"
		}

		// 转换条件为显示文本
		conditionText := map[string]string{
			"gt":  ">",
			"lt":  "<",
			"gte": ">=",
			"lte": "<=",
			"eq":  "=",
		}[rule.ConditionType]

		cards = append(cards, MetricCard{
			RuleID:          rule.ID,
			MetricID:        rule.MetricID,
			MetricCode:      rule.MetricCode,
			MetricName:      rule.MetricName,
			Unit:            rule.Unit,
			CurrentValue:    currentValue,
			Threshold:       rule.ThresholdValue,
			ConditionType:   rule.ConditionType,
			ConditionText:   conditionText,
			Status:          status,
			LastCheck:       time.Now().Format("2006-01-02 15:04:05"),
			Name:            rule.Name,
			WhereCondition:  rule.WhereCondition,
			DingtalkWebhook: rule.DingtalkWebhook,
			SQL:             rule.SQL,
		})
	}

	response.Success(c, gin.H{
		"cards": cards,
	})
}

// getAlertStatus 根据条件和阈值判断告警状态
func getAlertStatus(conditionType string, currentValue, threshold float64) string {
	var isAlert bool
	switch conditionType {
	case "gt":
		isAlert = currentValue > threshold
	case "lt":
		isAlert = currentValue < threshold
	case "gte":
		isAlert = currentValue >= threshold
	case "lte":
		isAlert = currentValue <= threshold
	case "eq":
		isAlert = currentValue == threshold
	default:
		isAlert = false
	}

	if !isAlert {
		return "normal"
	}

	// 超过阈值 50% 以上为 critical，否则为 warning
	if currentValue > threshold*1.5 || currentValue < threshold*0.5 {
		return "critical"
	}
	return "warning"
}
