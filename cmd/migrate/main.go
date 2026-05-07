package main

import (
	"dev_metric/config"
	"dev_metric/internal/api/handler"
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"log"

	"gorm.io/gorm"
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

	// ========== 013: 统一 dim_value_mapping 表 ==========
	migrateDimValueMapping()

	// ========== 014: 触发分析相关表 ==========
	migrateTriggerAnalysisTables()

	// ========== 015: sql_templates 表扩展（支持下钻分析）==========
	migrateSQLTemplates()

	// ========== 018: semantic_metrics 表清理（移除 calculated_config 列）==========
	migrateSemanticMetricsCleanup()
}

func migrateDimValueMapping() {
	db := postgres.Get()

	// 1. 删除旧的新表（如存在）
	db.Exec(`DROP TABLE IF EXISTS dim_value_mapping_new;`)
	log.Println("[013] 删除旧 dim_value_mapping_new（如存在）")

	// 2. 创建新表
	// UNIQUE 约束: (table_name, column_name) — 一个列在同一表只能出现一次
	// dimension_value 为空时代表类型映射，为非空时代表具体维度值
	createTableSQL := `
	CREATE TABLE IF NOT EXISTS dim_value_mapping_new (
		id SERIAL PRIMARY KEY,
		table_name VARCHAR(128) NOT NULL DEFAULT 'ids.IDS_AMZ_COMPREHENSIVE_DI',
		column_name VARCHAR(64) NOT NULL,
		dimension_type VARCHAR(64),
		dimension_value VARCHAR(256) NOT NULL DEFAULT '',
		frequency BIGINT DEFAULT 0,
		status SMALLINT DEFAULT 1,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);
	`
	if err := db.Exec(createTableSQL).Error; err != nil {
		log.Printf("[013] 创建 dim_value_mapping_new 表失败: %v", err)
	} else {
		log.Println("[013] dim_value_mapping_new 表创建成功")
	}

	// 2. 创建索引
	indexes := []string{
		`CREATE INDEX IF NOT EXISTS idx_dvm_column ON dim_value_mapping_new(column_name);`,
		`CREATE INDEX IF NOT EXISTS idx_dvm_type ON dim_value_mapping_new(dimension_type);`,
		`CREATE INDEX IF NOT EXISTS idx_dvm_table ON dim_value_mapping_new(table_name);`,
	}
	for _, idx := range indexes {
		if err := db.Exec(idx).Error; err != nil {
			log.Printf("[013] 创建索引失败: %v", err)
		}
	}
	log.Println("[013] 索引创建完成")

	// 3. 从 dimension_type_mappings 迁移数据（dimension_value 为空）
	// 每个 column 可以对应多个 dimension_type（如 FDATE → 日期/日/时间/时间粒度）
	migrateSQL := `
	INSERT INTO dim_value_mapping_new (table_name, column_name, dimension_type, dimension_value, status)
	SELECT
		'ids.IDS_AMZ_COMPREHENSIVE_DI' AS table_name,
		dtm.column_name,
		dtm.dimension_type,
		'' AS dimension_value,
		dtm.status
	FROM dimension_type_mappings dtm
	WHERE dtm.status = 1;
	`
	if err := db.Exec(migrateSQL).Error; err != nil {
		log.Printf("[013] 迁移 dimension_type_mappings 数据失败: %v", err)
	} else {
		log.Println("[013] dimension_type_mappings 数据迁移成功")
	}

	// 4. 检查结果
	var count int
	db.Raw("SELECT COUNT(*) FROM dim_value_mapping_new").Scan(&count)
	log.Printf("[013] dim_value_mapping_new 当前行数: %d", count)

	// 5. 表切换：dim_value_mapping_new → dim_value_mapping（幂等，只执行一次）
	switchToNewTable()
}

func switchToNewTable() {
	// 检查 dim_value_mapping 是否已存在（已切换过则跳过）
	var existingCount int
	postgres.Get().Raw("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'dim_value_mapping'").Scan(&existingCount)
	if existingCount > 0 {
		log.Println("[013] dim_value_mapping 已存在，跳过表切换")
		return
	}

	log.Println("[013] 执行表切换：dim_value_mapping_new → dim_value_mapping")

	// 先尝试删除旧表（如果存在）
	postgres.Get().Exec(`DROP TABLE IF EXISTS dim_value_mapping;`)

	// 将 dim_value_mapping_new 重命名为 dim_value_mapping
	if err := postgres.Get().Exec(`ALTER TABLE dim_value_mapping_new RENAME TO dim_value_mapping;`).Error; err != nil {
		log.Printf("[013] 表切换失败: %v", err)
		return
	}
	log.Println("[013] 表切换成功：dim_value_mapping_new → dim_value_mapping")
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

// ========== 014: 触发分析相关表 ==========
func migrateTriggerAnalysisTables() {
	db := postgres.Get()

	// 1. analysis_trigger_configs（触发规则配置）
	triggerConfigsSQL := `
	CREATE TABLE IF NOT EXISTS analysis_trigger_configs (
		id SERIAL PRIMARY KEY,
		trigger_type VARCHAR(32) NOT NULL,
		metric_code VARCHAR(64),
		condition JSONB NOT NULL,
		campaign_buffers JSONB,
		output_template_id INT,
		enabled BOOLEAN DEFAULT true,
		priority INT DEFAULT 0,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);
	`
	if err := db.Exec(triggerConfigsSQL).Error; err != nil {
		log.Printf("[014] 创建 analysis_trigger_configs 表失败: %v", err)
	} else {
		log.Println("[014] analysis_trigger_configs 表创建成功")
	}

	// 2. output_templates（输出模板配置）
	outputTemplatesSQL := `
	CREATE TABLE IF NOT EXISTS output_templates (
		id SERIAL PRIMARY KEY,
		template_key VARCHAR(64) NOT NULL UNIQUE,
		template_type VARCHAR(32) NOT NULL,
		content_template TEXT NOT NULL,
		params JSONB,
		enabled BOOLEAN DEFAULT true,
		priority INT DEFAULT 0,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);
	`
	if err := db.Exec(outputTemplatesSQL).Error; err != nil {
		log.Printf("[014] 创建 output_templates 表失败: %v", err)
	} else {
		log.Println("[014] output_templates 表创建成功")
	}

	// 3. business_dimension_labels（业务标签翻译）
	bizLabelsSQL := `
	CREATE TABLE IF NOT EXISTS business_dimension_labels (
		id SERIAL PRIMARY KEY,
		dimension_type VARCHAR(64) NOT NULL,
		raw_value VARCHAR(128) NOT NULL,
		display_name VARCHAR(128) NOT NULL,
		emoji VARCHAR(16),
		priority_tag VARCHAR(16),
		UNIQUE(dimension_type, raw_value)
	);
	`
	if err := db.Exec(bizLabelsSQL).Error; err != nil {
		log.Printf("[014] 创建 business_dimension_labels 表失败: %v", err)
	} else {
		log.Println("[014] business_dimension_labels 表创建成功")
	}

	// 4. trigger_switches（触发器开关）
	triggerSwitchesSQL := `
	CREATE TABLE IF NOT EXISTS trigger_switches (
		id SERIAL PRIMARY KEY,
		trigger_type VARCHAR(32) NOT NULL UNIQUE,
		switch_status VARCHAR(16) NOT NULL DEFAULT 'enabled',
		gray_ratio INT DEFAULT 100,
		switch_reason VARCHAR(256),
		operator VARCHAR(64),
		switched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);
	`
	if err := db.Exec(triggerSwitchesSQL).Error; err != nil {
		log.Printf("[014] 创建 trigger_switches 表失败: %v", err)
	} else {
		log.Println("[014] trigger_switches 表创建成功")
	}

	// 5. 扩展 ask_sessions 表（连续追问识别）
	askSessionsExtSQLs := []string{
		`ALTER TABLE ask_sessions ADD COLUMN IF NOT EXISTS last_query_type VARCHAR(32);`,
		`ALTER TABLE ask_sessions ADD COLUMN IF NOT EXISTS consecutive_followups INT DEFAULT 0;`,
		`ALTER TABLE ask_sessions ADD COLUMN IF NOT EXISTS last_topic VARCHAR(128);`,
		`ALTER TABLE ask_sessions ADD COLUMN IF NOT EXISTS followup_depth INT DEFAULT 0;`,
	}
	for _, sql := range askSessionsExtSQLs {
		if err := db.Exec(sql).Error; err != nil {
			log.Printf("[014] 扩展 ask_sessions 表失败: %v", err)
		}
	}
	log.Println("[014] ask_sessions 表扩展完成")

	// 插入默认触发规则
	insertDefaultTriggerConfigs(db)

	// 插入默认业务标签（预置通用标签）
	insertDefaultDimensionLabels(db)

	// 从 dim_value_mapping 同步实际维度值作为业务标签（会跳过已存在的）
	syncDimensionLabelsFromMapping(db)

	// 插入默认触发器开关
	insertDefaultTriggerSwitches(db)

	// 插入默认输出模板
	insertDefaultOutputTemplates(db)
}

func insertDefaultTriggerConfigs(db interface{}) {
	configs := []struct {
		triggerType string
		metricCode  string
		condition   string
		priority    int
	}{
		// 指标名称与 MQL.metric.name 一一对应
		{"volatility", "销售额", `{"mom": -10, "yoy": -15}`, 10},
		{"volatility", "广告花费", `{"mom": 20, "yoy": null}`, 10},   // 广告花费涨也是问题
		{"volatility", "ROAS", `{"mom": -15, "yoy": -20}`, 8},
		{"volatility", "广告产出比", `{"mom": -15, "yoy": -20}`, 8},
		{"volatility", "点击转化率", `{"mom": -5, "yoy": -8}`, 8},
		{"volatility", "转化率", `{"mom": -5, "yoy": -8}`, 8},
		{"volatility", "签收率", `{"mom": -3, "yoy": -5}`, 8},
		{"inventory_risk", "", `{"days_warning": 7, "days_urgent": 3}`, 9},
		{"generic_query", "", `{}`, 5},
		{"ad_effect", "", `{}`, 6},
	}

	// 清理旧的简化码记录（gmv/orders/cvr/sign_rate/ad_spend）
	db.(*gorm.DB).Exec(`DELETE FROM analysis_trigger_configs WHERE metric_code IN ('gmv','orders','cvr','sign_rate','ad_spend','roas')`)
	log.Println("[014] 清理旧 metric_code 记录完成")

	for _, c := range configs {
		var count int
		db.(*gorm.DB).Raw("SELECT COUNT(*) FROM analysis_trigger_configs WHERE trigger_type = ? AND COALESCE(metric_code, '') = ?", c.triggerType, c.metricCode).Scan(&count)
		if count == 0 {
			db.(*gorm.DB).Exec(`
				INSERT INTO analysis_trigger_configs (trigger_type, metric_code, condition, priority)
				VALUES (?, ?, ?::jsonb, ?)
			`, c.triggerType, c.metricCode, c.condition, c.priority)
			log.Printf("[014] 插入触发规则: %s.%s", c.triggerType, c.metricCode)
		}
	}
	log.Println("[014] 默认触发规则插入完成")
}

func insertDefaultDimensionLabels(db interface{}) {
	labels := []struct {
		dimType string
		rawVal  string
		display string
		emoji   string
	}{
		{"country", "US", "美国站", "🏪"},
		{"country", "EU", "欧洲站", "🏪"},
		{"country", "SEA", "东南亚站", "🏪"},
		{"platform", "AMAZON", "Amazon", "📦"},
		{"platform", "SHOPEE", "Shopee", "📦"},
		{"platform", "TEMU", "Temu", "📦"},
		{"ad_channel", "SPONSORED", "Sponsored", "📢"},
		{"ad_channel", "PPC", "PPC", "📢"},
		{"ad_channel", "SB", "Smart Bidding", "📢"},
	}

	for _, l := range labels {
		var count int
		db.(*gorm.DB).Raw("SELECT COUNT(*) FROM business_dimension_labels WHERE dimension_type = ? AND raw_value = ?", l.dimType, l.rawVal).Scan(&count)
		if count == 0 {
			db.(*gorm.DB).Exec(`
				INSERT INTO business_dimension_labels (dimension_type, raw_value, display_name, emoji)
				VALUES (?, ?, ?, ?)
			`, l.dimType, l.rawVal, l.display, l.emoji)
		}
	}
	log.Println("[014] 默认业务标签插入完成")
}

// syncDimensionLabelsFromMapping 从 dim_value_mapping 同步维度标签
// 根据实际的 dimension_type + dimension_value 自动生成业务标签
func syncDimensionLabelsFromMapping(db interface{}) {
	gdb := db.(*gorm.DB)

	// 先清理旧的预置类型（country/platform/ad_channel 与实际维度不匹配）
	gdb.Exec(`DELETE FROM business_dimension_labels WHERE dimension_type IN ('country','platform','ad_channel')`)
	log.Println("[014] 清理旧维度标签(country/platform/ad_channel)完成")

	// emoji 映射：根据 dimension_type 推断
	emojiMap := map[string]string{
		"站点":     "🏪",
		"站点编码":  "🏪",
		"平台":     "📦",
		"ASIN":    "🛍️",
		"SKU":     "📦",
		"一级品类": "📂",
		"二级品类": "📂",
		"三级品类": "📂",
		"四级品类": "📂",
	}

	// 从 dim_value_mapping 提取所有 dimension_type + dimension_value 组合
	rows, err := gdb.Raw(`
		SELECT DISTINCT dimension_type, dimension_value
		FROM dim_value_mapping
		WHERE dimension_value IS NOT NULL AND dimension_value != ''
		ORDER BY dimension_type, dimension_value
	`).Rows()
	if err != nil {
		log.Printf("[014] syncDimensionLabels 读取 dim_value_mapping 失败: %v", err)
		return
	}
	defer rows.Close()

	syncCount := 0
	skipCount := 0
	for rows.Next() {
		var dimType, dimValue string
		if err := rows.Scan(&dimType, &dimValue); err != nil {
			continue
		}

		// 检查是否已存在
		var exists int
		gdb.Raw("SELECT COUNT(*) FROM business_dimension_labels WHERE dimension_type = ? AND raw_value = ?", dimType, dimValue).Scan(&exists)
		if exists > 0 {
			skipCount++
			continue
		}

		// 获取 emoji（未知类型用 🔖）
		emoji := emojiMap[dimType]
		if emoji == "" {
			emoji = "🔖"
		}

		// 插入：display_name 暂用 raw_value，后续可人工校准
		gdb.Exec(`
			INSERT INTO business_dimension_labels (dimension_type, raw_value, display_name, emoji)
			VALUES (?, ?, ?, ?)
		`, dimType, dimValue, dimValue, emoji)
		syncCount++
	}

	log.Printf("[014] 维度标签同步完成: 新增 %d, 跳过已存在 %d", syncCount, skipCount)
}

func insertDefaultTriggerSwitches(db interface{}) {
	switches := []struct {
		triggerType string
		status      string
	}{
		{"volatility", "enabled"},
		{"generic_query", "enabled"},
		{"ad_effect", "enabled"},
		{"inventory_risk", "enabled"},
		{"all", "enabled"},
	}

	for _, s := range switches {
		var count int
		db.(*gorm.DB).Raw("SELECT COUNT(*) FROM trigger_switches WHERE trigger_type = ?", s.triggerType).Scan(&count)
		if count == 0 {
			db.(*gorm.DB).Exec(`
				INSERT INTO trigger_switches (trigger_type, switch_status)
				VALUES (?, ?)
			`, s.triggerType, s.status)
		}
	}
	log.Println("[014] 默认触发器开关插入完成")
}

func insertDefaultOutputTemplates(db interface{}) {
	templates := []struct {
		key       string
		tmplType  string
		content   string
		priority  int
	}{
		// 归因话术
		{"volatility_summary", "summary", "{{dimension}}{{emoji}}{{change}}，{{impact}}", 10},
		{"breakdown_reason_traffic", "reason", "流量下降{{value}}，广告曝光减少", 9},
		{"breakdown_reason_cvr", "reason", "转化率下降{{value}}，可能是页面或商品问题", 9},
		{"breakdown_reason_inventory", "reason", "库存可售天数仅{{days}}天，存在断货风险", 10},
		// 建议话术
		{"action_ad_check", "action", "检查广告投放策略", 10},
		{"action_inventory_replenish", "action", "立即补充库存", 10},
		{"action_cvr_optimize", "action", "优化商品详情页", 8},
		// 欢迎语
		{"greeting_morning", "greeting", "早！今日数据来了～", 5},
		{"greeting_afternoon", "greeting", "下午好！来看下最新数据", 5},
		{"greeting_weekend", "greeting", "周末数据已更新，看看本周表现", 5},
	}

	for _, t := range templates {
		var count int
		db.(*gorm.DB).Raw("SELECT COUNT(*) FROM output_templates WHERE template_key = ?", t.key).Scan(&count)
		if count == 0 {
			db.(*gorm.DB).Exec(`
				INSERT INTO output_templates (template_key, template_type, content_template, priority, enabled)
				VALUES (?, ?, ?, ?, true)
			`, t.key, t.tmplType, t.content, t.priority)
			log.Printf("[014] 插入输出模板: %s", t.key)
		}
	}
	log.Println("[014] 默认输出模板插入完成")
}

// ========== 015: sql_templates 表扩展（支持下钻分析）==========
func migrateSQLTemplates() {
	db := postgres.Get()

	// 扩展 sql_templates 表的新字段
	alterSQLs := []string{
		`ALTER TABLE sql_templates ADD COLUMN IF NOT EXISTS drilldown_category VARCHAR(32);`,
		`ALTER TABLE sql_templates ADD COLUMN IF NOT EXISTS metric_names JSONB;`,
		`ALTER TABLE sql_templates ADD COLUMN IF NOT EXISTS template_type VARCHAR(32) DEFAULT 'legacy';`,
		`ALTER TABLE sql_templates ADD COLUMN IF NOT EXISTS template_order INT DEFAULT 0;`,
		`ALTER TABLE sql_templates ADD COLUMN IF NOT EXISTS template_name VARCHAR(128);`,
	}

	for _, sql := range alterSQLs {
		if err := db.Exec(sql).Error; err != nil {
			log.Printf("[015] 扩展 sql_templates 表失败: %v", err)
		}
	}
	log.Println("[015] sql_templates 表扩展完成")

	// 为 drilldown_category 添加索引（如果还没有）
	db.Exec(`CREATE INDEX IF NOT EXISTS idx_sql_templates_drilldown ON sql_templates(drilldown_category);`)
	log.Println("[015] drilldown_category 索引创建完成")
}

// ========== 018: semantic_metrics 表清理（移除 calculated_config 列）==========
func migrateSemanticMetricsCleanup() {
	db := postgres.Get()
	sql := `ALTER TABLE semantic_metrics DROP COLUMN IF EXISTS calculated_config;`
	if err := db.Exec(sql).Error; err != nil {
		log.Printf("[018] 移除 calculated_config 列失败: %v", err)
	} else {
		log.Println("[018] calculated_config 列已移除或原本不存在")
	}
}
