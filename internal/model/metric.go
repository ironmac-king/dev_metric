package model

import (
	"encoding/json"
	"time"
)

// Metric 指标定义表（完整对齐 Excel 的 24 个字段）
type Metric struct {
	ID                 uint           `json:"id" gorm:"primaryKey"`
	SeqNo              int            `json:"seq_no" gorm:"index"`                     // 序号
	MetricCode         string         `json:"metric_code" gorm:"uniqueIndex;size:64"`   // 指标编号（如 MKI-02-0001）
	Domain             string         `json:"domain" gorm:"size:64"`                   // 所属域（如 营销域）
	Category1          string         `json:"category_1" gorm:"column:category_1;size:64"`               // 指标一级分类
	Category2          string         `json:"category_2" gorm:"column:category_2;size:64"`               // 指标二级分类
	Category3          string         `json:"category_3" gorm:"column:category_3;size:64"`               // 指标三级分类
	Name               string         `json:"name" gorm:"column:name;size:128"`                           // 指标名称
	NameEn             string         `json:"name_en" gorm:"column:name_en;size:128"`                    // 指标英文名称
	MetricType         string         `json:"metric_type" gorm:"column:metric_type;size:32"`             // 指标类型
	BusinessDefinition string         `json:"business_definition" gorm:"column:business_definition;type:text"` // 业务定义
	BusinessRule       string         `json:"business_rule" gorm:"column:business_rule;type:text"`         // 业务口径
	ApplicableScope    string         `json:"applicable_scope" gorm:"column:applicable_scope;size:256"`   // 适用范围
	StatisticsRule     string         `json:"statistics_rule" gorm:"column:statistics_rule;type:text"`   // 统计规则
	Unit               string         `json:"unit" gorm:"column:unit;size:32"`                          // 度量单位
	CommonDimensions   string         `json:"common_dimensions" gorm:"column:common_dimensions;size:256"` // 常用维度
	OrgLevel           string         `json:"org_level" gorm:"column:org_level;size:64"`               // 机构层级
	Frequency          string         `json:"frequency" gorm:"column:frequency;size:32"`               // 统计频度
	TechnicalRule      string         `json:"technical_rule" gorm:"column:technical_rule;type:text"`     // 技术口径
	DataFormat         string         `json:"data_format" gorm:"column:data_format;size:32"`           // 统计格式
	Precision          string         `json:"precision" gorm:"column:precision;size:32"`               // 指标精度
	OwnerDept          string         `json:"owner_dept" gorm:"column:owner_dept;size:128"`             // 指标归属部门
	Status             string         `json:"status" gorm:"column:status;size:32"`                     // 指标状态
	PublishDate        *time.Time     `json:"publish_date"`                           // 发布日期
	ExpireDate         *time.Time     `json:"expire_date"`                           // 失效日期
	StarRocksSQL       string         `json:"starrocks_sql" gorm:"column:starrocks_sql;type:text"` // 查询 SQL
	QueryParams        json.RawMessage `json:"query_params" gorm:"type:jsonb"`         // 查询参数配置
	CreatedAt          time.Time      `json:"created_at"`
	UpdatedAt          time.Time      `json:"updated_at"`
}

func (Metric) TableName() string {
	return "metrics"
}

// AlertRule 阈值配置表
type AlertRule struct {
	ID              uint      `json:"id" gorm:"primaryKey"`
	MetricID        uint      `json:"metric_id" gorm:"index"`
	Name            string    `json:"name" gorm:"size:128"`
	ConditionType   string    `json:"condition_type" gorm:"size:32"`    // gt/lt/gte/lte/eq
	ThresholdValue  float64   `json:"threshold_value" gorm:"type:decimal(20,4)"`
	Duration        int       `json:"duration"`                         // 持续时间(分钟)
	DingtalkWebhook string    `json:"dingtalk_webhook" gorm:"size:512"`
	DingtalkSecret  string    `json:"dingtalk_secret" gorm:"size:128"`
	NotifyStatus    int16     `json:"notify_status" gorm:"default:1"`  // 0=禁用 1=启用
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

func (AlertRule) TableName() string {
	return "alert_rules"
}

// AlertRecord 告警记录表
type AlertRecord struct {
	ID            uint       `json:"id" gorm:"primaryKey"`
	RuleID        uint       `json:"rule_id" gorm:"index"`
	MetricID      uint       `json:"metric_id" gorm:"index"`
	TriggerValue  float64    `json:"trigger_value" gorm:"type:decimal(20,4)"`
	ThresholdValue float64   `json:"threshold_value" gorm:"type:decimal(20,4)"`
	Status        int16      `json:"status" gorm:"default:0"`       // 0=触发 1=已通知 2=已恢复
	Message       string     `json:"message" gorm:"type:text"`
	TriggeredAt   time.Time  `json:"triggered_at"`
	NotifiedAt    *time.Time `json:"notified_at"`
	ResolvedAt    *time.Time `json:"resolved_at"`
}

func (AlertRecord) TableName() string {
	return "alert_records"
}

// LLMConfig 大模型配置表
type LLMConfig struct {
	ID         uint            `json:"id" gorm:"primaryKey"`
	Name       string          `json:"name" gorm:"size:64"`
	Provider   string          `json:"provider" gorm:"size:32"`      // tencent/openai/anthropic
	APIURL     string          `json:"api_url" gorm:"size:512"`
	APIKey     string          `json:"api_key" gorm:"size:256"`
	ModelName  string          `json:"model_name" gorm:"size:128"`
	IsDefault  int16          `json:"is_default" gorm:"default:0"` // 0=否 1=是
	ExtraConfig json.RawMessage `json:"extra_config" gorm:"type:jsonb"`
	Status     int16           `json:"status" gorm:"default:1"`     // 0=禁用 1=启用
	CreatedAt  time.Time      `json:"created_at"`
	UpdatedAt  time.Time      `json:"updated_at"`
}

func (LLMConfig) TableName() string {
	return "llm_configs"
}

// Dimension 维度表
type Dimension struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	Code        string    `json:"code" gorm:"size:64;uniqueIndex"`
	Name        string    `json:"name" gorm:"size:128"`
	Description string    `json:"description" gorm:"type:text"`
	Values      json.RawMessage `json:"values" gorm:"type:jsonb"`  // 可选值列表
	CreatedAt   time.Time `json:"created_at"`
}

func (Dimension) TableName() string {
	return "dimensions"
}

// BusinessTerm 业务术语映射表
type BusinessTerm struct {
	ID        uint      `json:"id" gorm:"primaryKey"`
	Term      string    `json:"term" gorm:"size:128;uniqueIndex"`
	MetricIDs []int     `json:"metric_ids" gorm:"type:integer[]"`
	Description string   `json:"description" gorm:"type:text"`
	CreatedAt time.Time `json:"created_at"`
}

func (BusinessTerm) TableName() string {
	return "business_terms"
}

// MetricDimension 指标-维度关联表
type MetricDimension struct {
	ID         uint `json:"id" gorm:"primaryKey"`
	MetricID   uint `json:"metric_id" gorm:"index"`
	DimensionID uint `json:"dimension_id" gorm:"index"`
}

func (MetricDimension) TableName() string {
	return "metric_dimensions"
}

// User 用户表
type User struct {
	ID           uint      `json:"id" gorm:"primaryKey"`
	Username     string    `json:"username" gorm:"size:64;uniqueIndex"`
	PasswordHash string    `json:"-" gorm:"size:256"`
	Dept         string    `json:"dept" gorm:"size:128"`
	DeptID       int       `json:"dept_id" gorm:"index"`
	Role         string    `json:"role" gorm:"size:32"`  // admin/user
	Status       int16     `json:"status" gorm:"default:1"`
	CreatedAt    time.Time `json:"created_at"`
}

func (User) TableName() string {
	return "users"
}

// RefreshTokenBlacklist Token 黑名单表
type RefreshTokenBlacklist struct {
	ID        uint      `json:"id" gorm:"primaryKey"`
	TokenJTI  string    `json:"token_jti" gorm:"size:64;uniqueIndex"`
	RevokedAt time.Time `json:"revoked_at"`
	ExpiresAt time.Time `json:"expires_at"`
}

func (RefreshTokenBlacklist) TableName() string {
	return "refresh_token_blacklist"
}

// SQLAuditLog SQL 审计日志表
type SQLAuditLog struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	UserID      uint      `json:"user_id" gorm:"index"`
	SQLText     string    `json:"sql_text" gorm:"type:text"`
	MetricID    *uint     `json:"metric_id" gorm:"index"`
	ExecuteTime time.Time `json:"execute_time"`
	Status      int16     `json:"status"`      // 0=成功 1=失败
	ErrorMsg    string    `json:"error_msg" gorm:"type:text"`
	IPAddress   string    `json:"ip_address" gorm:"size:45"`
}

func (SQLAuditLog) TableName() string {
	return "sql_audit_logs"
}

// IntentTemplate 意图模板表
type IntentTemplate struct {
	ID         uint      `json:"id" gorm:"primaryKey"`
	Name       string    `json:"name" gorm:"size:64"`                     // 模板名称
	Intent     string    `json:"intent" gorm:"size:32"`                  // 意图类型
	Patterns   string    `json:"patterns" gorm:"type:text"`                // 匹配模式（正则或关键词，逗号分隔）
	Priority   int       `json:"priority" gorm:"default:0"`                // 优先级
	Response   string    `json:"response" gorm:"type:text"`               // 默认回复模板
	Status     int16     `json:"status" gorm:"default:1"`                // 0=禁用 1=启用
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

func (IntentTemplate) TableName() string {
	return "intent_templates"
}

// SQLTemplate SQL模板表
type SQLTemplate struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	Name        string    `json:"name" gorm:"size:128"`                  // 模板名称
	MetricCode  string    `json:"metric_code" gorm:"size:64;index"`     // 指标编号
	Intent      string    `json:"intent" gorm:"size:32"`                 // 适用意图
	SQLTemplate string    `json:"sql_template" gorm:"type:text"`          // SQL模板（支持占位符）
	Description string    `json:"description" gorm:"type:text"`           // 说明
	Status      int16     `json:"status" gorm:"default:1"`               // 0=禁用 1=启用
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

func (SQLTemplate) TableName() string {
	return "sql_templates"
}
