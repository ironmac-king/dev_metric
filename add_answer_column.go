package main

import (
	"dev_metric/internal/repository/postgres"
	"log"
)

func main() {
	// 添加 answer 列到 ask_analysis_logs 表
	sql := `ALTER TABLE ask_analysis_logs ADD COLUMN IF NOT EXISTS answer TEXT;`

	if err := postgres.Get().Exec(sql).Error; err != nil {
		log.Printf("添加列失败或列已存在: %v", err)
	} else {
		log.Println("answer 列添加成功")
	}
}
