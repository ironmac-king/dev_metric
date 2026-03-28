package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"

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
