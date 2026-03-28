package main

import (
	"dev_metric/config"
	"dev_metric/internal/api"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	// 加载配置
	cfg, err := config.Load("config.yaml")
	if err != nil {
		log.Fatalf("加载配置失败: %v", err)
	}

	// 设置路由
	router := api.SetupRouter(cfg)

	// 启动服务
	addr := fmt.Sprintf("%s:%d", cfg.App.Host, cfg.App.Port)
	log.Printf("服务启动: %s", addr)

	// 优雅关闭
	go func() {
		if err := router.Run(addr); err != nil {
			log.Fatalf("服务启动失败: %v", err)
		}
	}()

	// 等待中断信号
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("服务关闭中...")
}
