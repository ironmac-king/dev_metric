package model

import (
	"encoding/json"
	"time"

	"github.com/lib/pq"
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
	WhereCondition  string    `json:"where_condition" gorm:"column:where_condition;type:text"` // WHERE 条件
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
	ModelName       string          `json:"model_name" gorm:"size:128"`
	EmbeddingApiKey string          `json:"embedding_api_key" gorm:"size:256"` // 阿里 dashscope 向量服务 API Key
	IsDefault      int16           `json:"is_default" gorm:"default:0"`          // 0=否 1=是
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
	ID             uint           `json:"id" gorm:"primaryKey"`
	Term           string         `json:"term" gorm:"size:128;uniqueIndex"`
	MetricIDs      pq.Int64Array  `json:"metric_ids" gorm:"type:integer[]"`
	Synonyms       pq.StringArray `json:"synonyms" gorm:"type:text[]"`  // 同义词列表，如 ["PV", "访问量"]
	Description    string         `json:"description" gorm:"type:text"`
	DimensionField string         `json:"dimension_field" gorm:"size:64"`      // 维度字段名，如 GROUP_3
	DimensionValue string         `json:"dimension_value" gorm:"size:256"`      // 维度值，如 有线网卡
	CreatedAt      time.Time      `json:"created_at"`
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
	Role         string    `json:"role" gorm:"size:32"`       // admin/user
	DataFilter   string    `json:"data_filter" gorm:"size:512"` // 自定义SQL WHERE条件，用于数据权限
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

// MetricRelation 指标关系表
type MetricRelation struct {
	ID              uint      `json:"id" gorm:"primaryKey"`
	SourceMetricCode string `json:"source_metric_code" gorm:"size:64;index"`
	TargetMetricCode string `json:"target_metric_code" gorm:"size:64;index"`
	RelationType    string `json:"relation_type" gorm:"size:32"`
	Weight          float64 `json:"weight" gorm:"type:decimal(3,2)"`
	Description     string `json:"description" gorm:"type:text"`
	Status          int16   `json:"status" gorm:"default:1"`
	CreatedAt       time.Time `json:"created_at"`
}

func (MetricRelation) TableName() string {
	return "metric_relations"
}

// IntentEmbedding 意图向量表
type IntentEmbedding struct {
	ID         uint      `json:"id" gorm:"primaryKey"`
	IntentID   uint      `json:"intent_id" gorm:"index"`
	IntentType string    `json:"intent_type" gorm:"size:32"`
	Text       string    `json:"text" gorm:"type:text"`
	Embedding  string    `json:"embedding" gorm:"type:text"` // 存储为 JSON 字符串
	UpdatedAt  time.Time `json:"updated_at"`
}

func (IntentEmbedding) TableName() string {
	return "intent_embeddings"
}

// IntentFeedback 意图反馈记录
type IntentFeedback struct {
	ID              uint       `json:"id" gorm:"primaryKey"`
	UserInput       string     `json:"user_input" gorm:"type:varchar(512)"`       // 用户原始输入
	PredictedIntent string     `json:"predicted_intent" gorm:"size:32"`          // 系统识别的意图
	CorrectIntent   string     `json:"correct_intent" gorm:"size:32"`           // 用户纠正的意图
	Status          int16      `json:"status" gorm:"default:0"`                // 0=待审核 1=已采纳 2=已忽略
	SessionID       string     `json:"session_id" gorm:"size:64"`
	CreatedAt       time.Time  `json:"created_at"`
	ReviewedAt      *time.Time `json:"reviewed_at"`
	ReviewedBy      string     `json:"reviewed_by" gorm:"size:64"`
}

func (IntentFeedback) TableName() string {
	return "intent_feedback"
}

// MetricEmbedding 指标向量表
type MetricEmbedding struct {
	ID         uint      `json:"id" gorm:"primaryKey"`
	MetricID   uint      `json:"metric_id" gorm:"index"`
	MetricCode string    `json:"metric_code" gorm:"size:64"`
	Text       string    `json:"text" gorm:"type:text"`
	Embedding  string    `json:"embedding" gorm:"type:text"` // 存储为 JSON 字符串
	UpdatedAt  time.Time `json:"updated_at"`
}

func (MetricEmbedding) TableName() string {
	return "metric_embeddings"
}

// AskShortcutQuestion 快捷问题配置表
type AskShortcutQuestion struct {
	ID           uint      `json:"id" gorm:"primaryKey"`
	QuestionText string    `json:"question_text" gorm:"size:256"` // 问题文本
	Icon         string    `json:"icon" gorm:"size:32"`          // 图标
	SortOrder    int       `json:"sort_order" gorm:"default:0"`  // 排序
	Status       int16     `json:"status" gorm:"default:1"`      // 0=禁用 1=启用
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

func (AskShortcutQuestion) TableName() string {
	return "ask_shortcut_questions"
}

// AskFavorite 收藏表
type AskFavorite struct {
	ID           uint      `json:"id" gorm:"primaryKey"`
	UserID      string    `json:"user_id" gorm:"size:64;default:'default'"` // 用户ID（预留）
	SessionID   string    `json:"session_id" gorm:"size:64;index"`          // 关联会话ID
	QuestionText string    `json:"question_text" gorm:"size:512"`           // 收藏的问题
	AnswerText   string    `json:"answer_text" gorm:"type:text"`           // 收藏的回答
	MetricCode   string    `json:"metric_code" gorm:"size:64"`             // 关联指标编号
	CreatedAt    time.Time `json:"created_at"`
}

func (AskFavorite) TableName() string {
	return "ask_favorites"
}

// AskSessionSummary 会话摘要表
type AskSessionSummary struct {
	ID            uint      `json:"id" gorm:"primaryKey"`
	SessionID     string    `json:"session_id" gorm:"size:64;uniqueIndex"` // 会话ID
	Title         string    `json:"title" gorm:"size:128"`                // 会话标题
	FirstQuestion string    `json:"first_question" gorm:"size:512"`        // 第一个问题
	MessageCount  int       `json:"message_count" gorm:"default:0"`       // 消息数量
	Starred       bool      `json:"starred" gorm:"default:false"`        // 是否加星标
	UserID        string    `json:"user_id" gorm:"size:64;default:'default'"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

func (AskSessionSummary) TableName() string {
	return "ask_session_summaries"
}

// AskMessage 会话消息表
type AskMessage struct {
	ID        uint      `json:"id" gorm:"primaryKey"`
	SessionID string    `json:"session_id" gorm:"size:64;index"`
	Role      string    `json:"role" gorm:"size:16"`    // user / assistant
	Content   string    `json:"content" gorm:"type:text"`
	SQL       string    `json:"sql" gorm:"type:text"`
	CreatedAt time.Time `json:"created_at"`
	// 响应数据（JSON 序列化存储）
	ResultData       string `json:"result_data" gorm:"type:text"`
	ComparisonResults string `json:"comparison_results" gorm:"column:comparison_results;type:text"`
	DrillDownDims    string `json:"drill_down_dims" gorm:"type:text"`
	Breadcrumbs      string `json:"breadcrumbs" gorm:"type:text"`
	MetricCode       string `json:"metric_code" gorm:"size:64"`
}

func (AskMessage) TableName() string {
	return "ask_messages"
}

// AskQueryStat 查询统计表
type AskQueryStat struct {
	ID         uint      `json:"id" gorm:"primaryKey"`
	QueryDate  time.Time `json:"query_date" gorm:"index"`                 // 查询日期
	MetricCode string    `json:"metric_code" gorm:"size:64;index"`        // 被查询的指标编号
	MetricName string    `json:"metric_name" gorm:"size:128"`             // 被查询的指标名称
	QueryCount int       `json:"query_count" gorm:"default:1"`            // 查询次数
	CreatedAt  time.Time `json:"created_at"`
}

func (AskQueryStat) TableName() string {
	return "ask_query_stats"
}

// AskUserPreference 用户偏好表
type AskUserPreference struct {
	ID           uint      `json:"id" gorm:"primaryKey"`
	UserID      string    `json:"user_id" gorm:"size:64;uniqueIndex;default:'default'"` // 用户ID
	Theme        string    `json:"theme" gorm:"size:16;default:'light'"`                 // light/dark
	MessageStyle string    `json:"message_style" gorm:"size:16;default:'bubbles'"`       // bubbles/cards
	FontSize     string    `json:"font_size" gorm:"size:16;default:'medium'"`           // small/medium/large
	ShowThinking bool      `json:"show_thinking" gorm:"default:true"`                    // 显示思考过程
	CompactMode  bool      `json:"compact_mode" gorm:"default:false"`                   // 紧凑模式
	UpdatedAt    time.Time `json:"updated_at"`
}

func (AskUserPreference) TableName() string {
	return "ask_user_preferences"
}

// AskAnalysisLog 问数分析日志表
type AskAnalysisLog struct {
	ID            uint      `json:"id" gorm:"primaryKey"`
	UserID       string    `json:"user_id" gorm:"size:64;index;default:'default'"` // 用户ID
	SessionID    string    `json:"session_id" gorm:"size:64;index"`                // 会话ID
	Question     string    `json:"question" gorm:"type:text"`                     // 用户问题
	Answer       string    `json:"answer" gorm:"type:text"`                       // 完整回答/报告
	Intent       string    `json:"intent" gorm:"size:32"`                        // 识别的意图
	Success      bool      `json:"success"`                                       // 是否成功
	FailStage    string    `json:"fail_stage" gorm:"size:32"`                  // 失败阶段: intent/entity/sql/execute
	FailReason   string    `json:"fail_reason" gorm:"type:text"`                // 失败原因
	Suggestion   string    `json:"suggestion" gorm:"type:text"`                 // 建议解决方案
	ThinkingSteps string    `json:"thinking_steps" gorm:"type:text"`             // JSON序列化的思考步骤
	CreatedAt    time.Time `json:"created_at"`
}

func (AskAnalysisLog) TableName() string {
	return "ask_analysis_logs"
}
