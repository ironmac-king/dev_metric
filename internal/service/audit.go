package service

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"strconv"
	"time"
)

// SQLAuditService SQL审计服务
type SQLAuditService struct{}

// NewSQLAuditService 创建SQL审计服务
func NewSQLAuditService() *SQLAuditService {
	return &SQLAuditService{}
}

// LogSQL 记录SQL执行日志
// 参数：
//   - userID: 用户ID（0表示系统或匿名）
//   - sqlText: SQL文本（脱敏后）
//   - metricID: 关联的指标ID（可选）
//   - status: 执行状态（0=成功 1=失败）
//   - errorMsg: 错误信息（成功时为空）
//   - ipAddress: 客户端IP地址
func (s *SQLAuditService) LogSQL(userID uint, sqlText string, metricID *uint, status int16, errorMsg string, ipAddress string) error {
	log := &model.SQLAuditLog{
		UserID:      userID,
		SQLText:     sqlText,
		MetricID:    metricID,
		ExecuteTime: time.Now(),
		Status:      status,
		ErrorMsg:    errorMsg,
		IPAddress:   ipAddress,
	}
	return postgres.Get().Create(log).Error
}

// LogMetricQuery 记录指标查询日志
func (s *SQLAuditService) LogMetricQuery(userID uint, metricID uint, sqlText string, success bool, ipAddress string) {
	status := int16(0)
	errorMsg := ""
	if !success {
		status = 1
	}
	s.LogSQL(userID, sqlText, &metricID, status, errorMsg, ipAddress)
}

// LogMetricCreate 记录指标创建日志
func (s *SQLAuditService) LogMetricCreate(userID uint, metricID uint, metricName string, ipAddress string) {
	sqlText := "CREATE metric: " + metricName
	s.LogSQL(userID, sqlText, &metricID, 0, "", ipAddress)
}

// LogMetricUpdate 记录指标更新日志
func (s *SQLAuditService) LogMetricUpdate(userID uint, metricID uint, changes string, ipAddress string) {
	sqlText := "UPDATE metric: " + changes
	s.LogSQL(userID, sqlText, &metricID, 0, "", ipAddress)
}

// LogMetricDelete 记录指标删除日志
func (s *SQLAuditService) LogMetricDelete(userID uint, metricID uint, ipAddress string) {
	sqlText := "DELETE metric"
	s.LogSQL(userID, sqlText, &metricID, 0, "", ipAddress)
}

// LogAlertConfig 记录告警配置变更日志
func (s *SQLAuditService) LogAlertConfig(userID uint, alertID uint, action string, ipAddress string) {
	sqlText := action + " alert_rule: " + strconv.FormatUint(uint64(alertID), 10)
	s.LogSQL(userID, sqlText, nil, 0, "", ipAddress)
}

// LogNLPConfig 记录NLP配置变更日志
func (s *SQLAuditService) LogNLPConfig(userID uint, configType string, action string, ipAddress string) {
	sqlText := action + " " + configType
	s.LogSQL(userID, sqlText, nil, 0, "", ipAddress)
}

// GetSQLAuditLogs 获取SQL审计日志列表
func (s *SQLAuditService) GetSQLAuditLogs(page, pageSize int, userID uint, metricID *uint) ([]model.SQLAuditLog, int64, error) {
	var logs []model.SQLAuditLog
	var total int64

	query := postgres.Get().Model(&model.SQLAuditLog{})

	if userID > 0 {
		query = query.Where("user_id = ?", userID)
	}
	if metricID != nil {
		query = query.Where("metric_id = ?", *metricID)
	}

	query.Count(&total)
	query.Offset((page - 1) * pageSize).Limit(pageSize).Order("execute_time DESC").Find(&logs)

	return logs, total, nil
}
