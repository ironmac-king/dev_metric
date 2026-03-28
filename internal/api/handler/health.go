package handler

import (
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/repository/starrocks"
	"net/http"

	"github.com/gin-gonic/gin"
)

func HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "ok",
	})
}

func ReadyCheck(c *gin.Context) {
	// 检查数据库连接
	db := postgres.Get()
	if db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status": "not ready",
			"reason": "database not connected",
		})
		return
	}

	// 检查 StarRocks 连接
	sr := starrocks.Get()
	if sr == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status": "not ready",
			"reason": "starrocks not connected",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "ready",
	})
}

func LiveCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "live",
	})
}
