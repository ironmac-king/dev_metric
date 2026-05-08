package main

import (
	"dev_metric/config"
	"dev_metric/internal/api/handler"
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"fmt"
	"log"
)

func main() {
	cfg := &config.DatabaseConfig{
		Host:     "192.168.1.225",
		Port:     5432,
		User:     "postgres",
		Password: "admin123",
		Name:     "dev_metric",
	}

	if err := postgres.Init(cfg); err != nil {
		log.Fatalf("初始化数据库失败: %v", err)
	}
	defer postgres.Close()

	var user model.User
	if err := postgres.Get().Where("username = ?", "admin").First(&user).Error; err != nil {
		log.Fatalf("查找 admin 用户失败: %v", err)
	}

	fmt.Printf("Found admin user: ID=%d, Username=%s\n", user.ID, user.Username)
	fmt.Printf("Current hash: %s\n", user.PasswordHash)

	// 重置密码为 admin123
	hash, err := handler.HashPassword("admin123")
	if err != nil {
		log.Fatalf("生成密码哈希失败: %v", err)
	}

	user.PasswordHash = hash
	if err := postgres.Get().Save(&user).Error; err != nil {
		log.Fatalf("更新密码失败: %v", err)
	}

	fmt.Println("密码已重置为 admin123")
}
