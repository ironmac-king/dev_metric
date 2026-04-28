package handler

import (
	"crypto/sha256"
	"database/sql"
	"dev_metric/config"
	"dev_metric/internal/cache"
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/repository/starrocks"
	"dev_metric/pkg/response"
	"encoding/hex"
	"fmt"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	_ "github.com/go-sql-driver/mysql"
	"gorm.io/gorm"
)

// GetStarRocksConfig 获取 StarRocks 配置
func GetStarRocksConfig(c *gin.Context) {
	var cfg model.StarRocksConfig
	result := postgres.Get().Where("is_active = ?", 1).First(&cfg)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			response.Error(c, response.CodeNotFound, "未配置 StarRocks 连接")
			return
		}
		response.Error(c, response.CodeInternalError, "查询配置失败")
		return
	}

	// 密码脱敏
	cfg.Password = ""

	response.Success(c, cfg)
}

// UpdateStarRocksConfig 更新 StarRocks 配置
func UpdateStarRocksConfig(c *gin.Context) {
	var req model.StarRocksConfigUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 查找现有配置
	var cfg model.StarRocksConfig
	result := postgres.Get().Where("is_active = ?", 1).First(&cfg)
	if result.Error != nil && result.Error != gorm.ErrRecordNotFound {
		response.Error(c, response.CodeInternalError, "查询配置失败")
		return
	}

	// 设置默认值
	if req.Timeout == 0 {
		req.Timeout = 10
	}
	if req.QueryTimeout == 0 {
		req.QueryTimeout = 30
	}

	if result.Error == gorm.ErrRecordNotFound {
		// 新增
		cfg = model.StarRocksConfig{
			Name:         req.Name,
			Host:         req.Host,
			Port:         req.Port,
			User:         req.User,
			Password:     req.Password,
			Database:     req.Database,
			Timeout:      req.Timeout,
			QueryTimeout: req.QueryTimeout,
			IsActive:     1,
		}
		if err := postgres.Get().Create(&cfg).Error; err != nil {
			response.Error(c, response.CodeInternalError, "创建配置失败")
			return
		}
	} else {
		// 更新
		cfg.Name = req.Name
		cfg.Host = req.Host
		cfg.Port = req.Port
		cfg.User = req.User
		cfg.Database = req.Database
		cfg.Timeout = req.Timeout
		cfg.QueryTimeout = req.QueryTimeout
		cfg.IsActive = req.IsActive
		if req.Password != "" {
			cfg.Password = req.Password
		}
		if err := postgres.Get().Save(&cfg).Error; err != nil {
			response.Error(c, response.CodeInternalError, "更新配置失败")
			return
		}
	}

	// 通知 StarRocks 客户端重连
	srCfg := &config.StarRocksConfig{
		Host:     cfg.Host,
		Port:     cfg.Port,
		User:     cfg.User,
		Password: cfg.Password,
		Database: cfg.Database,
	}
	if err := starrocks.Reconnect(srCfg); err != nil {
		response.Error(c, response.CodeInternalError, fmt.Sprintf("配置已保存，但重连失败: %v", err))
		return
	}

	// 密码脱敏返回
	cfg.Password = ""
	response.Success(c, cfg)
}

// TestStarRocksConnection 测试 StarRocks 连接
func TestStarRocksConnection(c *gin.Context) {
	var req model.StarRocksConfigTestRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if req.Timeout == 0 {
		req.Timeout = 10
	}

	// 尝试连接
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?timeout=%ds",
		req.User, req.Password, req.Host, req.Port, req.Database, req.Timeout)

	db, err := sql.Open("mysql", dsn)
	if err != nil {
		response.Error(c, response.CodeBadRequest, fmt.Sprintf("连接失败: %v", err))
		return
	}
	defer db.Close()

	// 设置超时
	db.SetConnMaxLifetime(time.Duration(req.Timeout) * time.Second)

	if err := db.Ping(); err != nil {
		response.Error(c, response.CodeBadRequest, fmt.Sprintf("连接失败: %v", err))
		return
	}

	response.SuccessWithMessage(c, "连接成功", nil)
}

// ExecuteQueryRequest 执行查询请求
type ExecuteQueryRequest struct {
	SQL    string                 `json:"sql" binding:"required"`
	Params map[string]interface{} `json:"params"`
}

// ExecuteQuery 执行 SQL 查询（供 AI 服务调用）
func ExecuteQuery(c *gin.Context) {
	var req ExecuteQueryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误：sql 不能为空")
		return
	}

	// 安全校验：只允许 SELECT 或 WITH (CTE) 查询
	sqlLower := strings.ToLower(strings.TrimSpace(req.SQL))
	if len(req.SQL) < 6 || (!strings.HasPrefix(sqlLower, "select") && !strings.HasPrefix(sqlLower, "with")) {
		response.Error(c, response.CodeBadRequest, "只允许 SELECT 查询")
		return
	}

	// 生成缓存 key（SQL 的 SHA256 哈希）
	hash := sha256.Sum256([]byte(req.SQL))
	cacheKey := fmt.Sprintf("query:cache:%s", hex.EncodeToString(hash[:]))

	// 尝试从缓存获取
	ctx := c.Request.Context()
	var cachedResult struct {
		Data    interface{} `json:"data"`
		Columns []string   `json:"columns"`
		Count   int        `json:"count"`
	}
	if err := cache.GetJSON(ctx, cacheKey, &cachedResult); err == nil {
		// 缓存命中
		response.Success(c, gin.H{
			"data":    cachedResult.Data,
			"columns": cachedResult.Columns,
			"count":   cachedResult.Count,
			"cached":  true,
		})
		return
	}

	// 执行查询（带列信息）
	queryResult, err := starrocks.QueryRawWithColumns(req.SQL)
	if err != nil {
		response.Error(c, response.CodeInternalError, fmt.Sprintf("查询失败: %v", err))
		return
	}

	// 写入缓存，TTL 5分钟
	cacheResult := gin.H{
		"data":    queryResult.Rows,
		"columns": queryResult.Columns,
		"count":   len(queryResult.Rows),
	}
	if err := cache.SetJSON(ctx, cacheKey, cacheResult, 5*time.Minute); err != nil {
		fmt.Printf("[ExecuteQuery] 缓存写入失败: %v\n", err)
	} else {
		fmt.Printf("[ExecuteQuery] 缓存写入成功, key: %s, count: %d\n", cacheKey, len(queryResult.Rows))
	}

	response.Success(c, gin.H{
		"data":    queryResult.Rows,
		"columns": queryResult.Columns,
		"count":   len(queryResult.Rows),
		"cached":  false,
	})
}

