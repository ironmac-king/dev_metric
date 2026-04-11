package main

import (
	"dev_metric/config"
	"dev_metric/internal/api/handler"
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"log"
)

func main() {
	// 初始化配置
	cfg := &config.DatabaseConfig{
		Host:     "192.168.1.225",
		Port:     5432,
		User:     "postgres",
		Password: "admin123",
		Name:     "dev_metric",
	}

	// 初始化数据库
	if err := postgres.Init(cfg); err != nil {
		log.Fatalf("初始化数据库失败: %v", err)
	}
	defer postgres.Close()

	// 添加 answer 列
	sql := `ALTER TABLE ask_analysis_logs ADD COLUMN IF NOT EXISTS answer TEXT;`
	if err := postgres.Get().Exec(sql).Error; err != nil {
		log.Printf("执行 ALTER TABLE 失败: %v", err)
	} else {
		log.Println("answer 列添加成功或已存在")
	}

	// 添加 updated_by 列到 metrics 表
	metricColSQL := `ALTER TABLE metrics ADD COLUMN IF NOT EXISTS updated_by VARCHAR(64);`
	if err := postgres.Get().Exec(metricColSQL).Error; err != nil {
		log.Printf("添加 updated_by 列失败: %v", err)
	} else {
		log.Println("updated_by 列添加成功或已存在")
	}

	// 创建角色和权限表
	createRolesAndMenus()

	// 创建默认管理员用户
	createAdminUser()
}

func createRolesAndMenus() {
	// 创建角色表
	createTableSQL := `
	CREATE TABLE IF NOT EXISTS roles (
		id SERIAL PRIMARY KEY,
		name VARCHAR(32) NOT NULL UNIQUE,
		display_name VARCHAR(64),
		description TEXT,
		created_at TIMESTAMP DEFAULT NOW()
	);

	CREATE TABLE IF NOT EXISTS role_menus (
		id SERIAL PRIMARY KEY,
		role_name VARCHAR(32) NOT NULL,
		menu_path VARCHAR(128) NOT NULL,
		menu_name VARCHAR(64),
		parent_path VARCHAR(128),
		sort_order INT DEFAULT 0,
		UNIQUE(role_name, menu_path)
	);
	`
	if err := postgres.Get().Exec(createTableSQL).Error; err != nil {
		log.Printf("创建角色权限表失败: %v", err)
	} else {
		log.Println("角色权限表创建成功")
	}

	// 初始化默认角色
	defaultRoles := []struct {
		name        string
		displayName string
		description string
	}{
		{"admin", "管理员", "拥有全部权限"},
		{"analyst", "分析师", "可以查看和管理指标、告警、智能分析"},
		{"user", "普通用户", "只能使用智能问数和决策分析"},
	}

	for _, r := range defaultRoles {
		var count int64
		postgres.Get().Model(&model.Role{}).Where("name = ?", r.name).Count(&count)
		if count == 0 {
			role := &model.Role{
				Name:        r.name,
				DisplayName: r.displayName,
				Description: r.description,
			}
			if err := postgres.Get().Create(role).Error; err != nil {
				log.Printf("创建角色 %s 失败: %v", r.name, err)
			} else {
				log.Printf("角色 %s 创建成功", r.name)
			}
		}
	}

	// 初始化默认权限
	initDefaultMenus()
}

func initDefaultMenus() {
	// 默认菜单配置
	defaultMenus := []struct {
		roleName   string
		menuPath   string
		menuName   string
		parentPath string
		sortOrder  int
	}{
		// admin 拥有所有权限
		{"admin", "/dashboard", "Dashboard", "", 1},
		{"admin", "/metrics", "指标管理", "", 2},
		{"admin", "/alerts", "告警配置", "", 3},
		{"admin", "/ai-assistant", "AI 问数", "", 4},
		{"admin", "/ask", "智能问数", "", 5},
		{"admin", "/ask-analysis", "问数分析", "", 6},
		{"admin", "/analysis", "决策分析", "", 7},
		{"admin", "/llm-config", "LLM 配置", "", 8},
		{"admin", "/nlp-config", "意图配置", "", 9},
		{"admin", "/starrocks-config", "数据源配置", "", 10},
		{"admin", "/dimension-config", "维度配置", "", 11},
		{"admin", "/prompt-config", "Prompt配置", "", 12},
		{"admin", "/user-management", "用户管理", "", 13},

		// analyst 权限
		{"analyst", "/dashboard", "Dashboard", "", 1},
		{"analyst", "/metrics", "指标管理", "", 2},
		{"analyst", "/alerts", "告警配置", "", 3},
		{"analyst", "/ai-assistant", "AI 问数", "", 4},
		{"analyst", "/ask", "智能问数", "", 5},
		{"analyst", "/ask-analysis", "问数分析", "", 6},
		{"analyst", "/analysis", "决策分析", "", 7},

		// user 权限
		{"user", "/dashboard", "Dashboard", "", 1},
		{"user", "/ask", "智能问数", "", 2},
		{"user", "/analysis", "决策分析", "", 3},
	}

	for _, m := range defaultMenus {
		var count int64
		postgres.Get().Model(&model.RoleMenu{}).Where("role_name = ? AND menu_path = ?", m.roleName, m.menuPath).Count(&count)
		if count == 0 {
			menu := &model.RoleMenu{
				RoleName:   m.roleName,
				MenuPath:   m.menuPath,
				MenuName:   m.menuName,
				ParentPath: m.parentPath,
				SortOrder:  m.sortOrder,
			}
			if err := postgres.Get().Create(menu).Error; err != nil {
				log.Printf("创建权限 %s.%s 失败: %v", m.roleName, m.menuPath, err)
			}
		}
	}
	log.Println("默认菜单权限初始化完成")
}

func createAdminUser() {
	var count int64
	postgres.Get().Model(&model.User{}).Where("username = ?", "admin").Count(&count)
	if count > 0 {
		log.Println("admin 用户已存在")
		return
	}

	hash, err := handler.HashPassword("admin123")
	if err != nil {
		log.Fatalf("生成密码哈希失败: %v", err)
	}

	user := &model.User{
		Username:     "admin",
		PasswordHash: hash,
		Dept:         "技术部",
		DeptID:       1,
		Role:         "admin",
		Status:       1,
	}

	if err := postgres.Get().Create(user).Error; err != nil {
		log.Fatalf("创建 admin 用户失败: %v", err)
	}
	log.Println("admin 用户创建成功，密码: admin123")
}
