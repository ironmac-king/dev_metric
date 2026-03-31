package main

import (
	"dev_metric/config"
	"dev_metric/internal/api"
	"dev_metric/internal/cache"
	"dev_metric/internal/repository/starrocks"
	"dev_metric/pkg/logger"
	"fmt"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	// 加载配置
	cfg, err := config.Load("config.yaml")
	if err != nil {
		fmt.Printf("加载配置失败: %v\n", err)
		os.Exit(1)
	}

	// 初始化日志
	logger.Init(&cfg.Logging)
	logger.Info().Str("addr", fmt.Sprintf("%s:%d", cfg.App.Host, cfg.App.Port)).Msg("日志系统初始化完成")

	// 初始化 Redis
	if err := cache.Init(&cfg.Redis); err != nil {
		logger.Warn().Err(err).Msg("Redis 连接失败，缓存功能将不可用")
	} else {
		logger.Info().Msg("Redis 连接成功")
	}

	// 初始化 StarRocks（如果配置了）
	if cfg.StarRocks.Host != "" {
		if err := starrocks.Init(&cfg.StarRocks); err != nil {
			logger.Warn().Err(err).Msg("StarRocks 连接失败")
		} else {
			logger.Info().Msg("StarRocks 连接成功")
		}
	}

	// 设置路由
	router := api.SetupRouter(cfg)

	// 启动服务
	addr := fmt.Sprintf("%s:%d", cfg.App.Host, cfg.App.Port)
	logger.Info().Str("addr", addr).Msg("服务启动")

	// 优雅关闭
	go func() {
		if err := router.Run(addr); err != nil {
			logger.Fatal().Err(err).Msg("服务启动失败")
		}
	}()

	// 等待中断信号
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info().Msg("服务关闭中...")
	cache.Close()
	starrocks.Close()
	logger.Info().Msg("服务已关闭")
}
