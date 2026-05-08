package service

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"fmt"
	"io"
	"strconv"
	"sync"
	"time"

	"github.com/xuri/excelize/v2"
)

// headerMapping Excel 表头映射（与 cmd/importer/main.go 保持一致）
var headerMapping = map[string]string{
	"序号":         "seq_no",
	"指标编号":       "metric_code",
	"所属域":        "domain",
	"指标一级分类":     "category_1",
	"指标二级分类":     "category_2",
	"指标三级分类":     "category_3",
	"指标名称":        "name",
	"指标英文名称":      "name_en",
	"指标类型":        "metric_type",
	"业务定义":        "business_definition",
	"业务口径":        "business_rule",
	"适用范围":        "applicable_scope",
	"统计规则":        "statistics_rule",
	"度量单位":        "unit",
	"常用维度":        "common_dimensions",
	"机构层级":        "org_level",
	"统计频度":        "frequency",
	"技术口径":        "technical_rule",
	"统计格式":        "data_format",
	"指标精度":        "precision",
	"指标归属部门":      "owner_dept",
	"指标状态":        "status",
	"发布日期":        "publish_date",
	"失效日期":        "expire_date",
}

// ImportError 导入错误信息
type ImportError struct {
	Row     int    `json:"row"`
	Field   string `json:"field"`
	Message string `json:"message"`
}

// PreviewResult 预览结果
type PreviewResult struct {
	Total      int            `json:"total"`
	NewCount   int            `json:"new_count"`
	UpdateCount int           `json:"update_count"`
	Errors     []ImportError  `json:"errors"`
	Preview    []PreviewItem  `json:"preview"`
}

// PreviewItem 预览项
type PreviewItem struct {
	MetricCode string `json:"metric_code"`
	Name       string `json:"name"`
	Domain     string `json:"domain"`
	Status     string `json:"status"`
	IsNew      bool   `json:"is_new"`
}

// CommitResult 提交结果
type CommitResult struct {
	Imported    int `json:"imported"`
	NewCount    int `json:"new_count"`
	UpdateCount int `json:"update_count"`
	Failed      int `json:"failed"`
}

// ImportData 导入数据（存储用）
type ImportData struct {
	Metrics  []model.Metric
	IsNew   map[string]bool // metric_code -> is_new
	CreatedAt time.Time
}

// ImportService 导入服务
type ImportService struct {
	store map[string]*ImportData
	mu    sync.RWMutex
}

var importServiceInstance *ImportService

// GetImportService 获取导入服务单例
func GetImportService() *ImportService {
	if importServiceInstance == nil {
		importServiceInstance = &ImportService{
			store: make(map[string]*ImportData),
		}
	}
	return importServiceInstance
}

// parseDate 解析日期，支持多种格式
func parseDate(v string) *time.Time {
	if v == "" {
		return nil
	}
	formats := []string{"2006/1/2", "2006-01-02", "2006/01/02", "2006-1-2"}
	for _, f := range formats {
		if t, err := time.Parse(f, v); err == nil {
			return &t
		}
	}
	return nil
}

// ParseRow 解析一行数据
func ParseRow(row []string, colIndex map[string]int) model.Metric {
	metric := model.Metric{}

	getValue := func(field string) string {
		idx, ok := colIndex[field]
		if !ok || idx >= len(row) {
			return ""
		}
		return row[idx]
	}

	// 解析序号
	if v := getValue("seq_no"); v != "" {
		fmt.Sscanf(v, "%d", &metric.SeqNo)
	}

	metric.MetricCode = getValue("metric_code")
	metric.Domain = getValue("domain")
	metric.Category1 = getValue("category_1")
	metric.Category2 = getValue("category_2")
	metric.Category3 = getValue("category_3")
	metric.Name = getValue("name")
	metric.NameEn = getValue("name_en")
	metric.MetricType = getValue("metric_type")
	metric.BusinessDefinition = getValue("business_definition")
	metric.BusinessRule = getValue("business_rule")
	metric.ApplicableScope = getValue("applicable_scope")
	metric.StatisticsRule = getValue("statistics_rule")
	metric.Unit = getValue("unit")
	metric.CommonDimensions = getValue("common_dimensions")
	metric.OrgLevel = getValue("org_level")
	metric.Frequency = getValue("frequency")
	metric.TechnicalRule = getValue("technical_rule")
	metric.DataFormat = getValue("data_format")
	metric.Precision = getValue("precision")
	metric.OwnerDept = getValue("owner_dept")
	metric.Status = getValue("status")
	if metric.Status == "" {
		metric.Status = "在用"
	}

	metric.PublishDate = parseDate(getValue("publish_date"))
	metric.ExpireDate = parseDate(getValue("expire_date"))

	return metric
}

// PreviewImport 预览导入
func (s *ImportService) PreviewImport(file io.Reader, filename string) (*PreviewResult, string, error) {
	f, err := excelize.OpenReader(file)
	if err != nil {
		return nil, "", fmt.Errorf("打开Excel失败: %v", err)
	}
	defer f.Close()

	sheets := f.GetSheetList()
	if len(sheets) == 0 {
		return nil, "", fmt.Errorf("Excel文件中没有Sheet")
	}

	rows, err := f.GetRows(sheets[0])
	if err != nil {
		return nil, "", fmt.Errorf("读取Sheet失败: %v", err)
	}

	if len(rows) < 2 {
		return nil, "", fmt.Errorf("Excel文件行数不足（需要表头+至少1行数据）")
	}

	// 解析表头
	headers := rows[0]
	colIndex := make(map[string]int)
	for i, h := range headers {
		if mapped, ok := headerMapping[h]; ok {
			colIndex[mapped] = i
		}
	}

	// 检查必要字段
	if _, ok := colIndex["metric_code"]; !ok {
		return nil, "", fmt.Errorf("缺少指标编号列")
	}

	// 解析数据行
	var metrics []model.Metric
	var errors []ImportError
	var preview []PreviewItem
	isNew := make(map[string]bool)

	for rowIdx, row := range rows[1:] {
		rowNum := rowIdx + 2 // Excel行号从1开始，表头是1，数据从2开始
		metric := ParseRow(row, colIndex)

		// 校验必填字段
		if metric.MetricCode == "" {
			errors = append(errors, ImportError{Row: rowNum, Field: "metric_code", Message: "指标编号不能为空"})
			continue
		}
		if len(metric.MetricCode) > 64 {
			errors = append(errors, ImportError{Row: rowNum, Field: "metric_code", Message: "指标编号长度不能超过64"})
			continue
		}
		if metric.Name == "" {
			errors = append(errors, ImportError{Row: rowNum, Field: "name", Message: "指标名称不能为空"})
			continue
		}
		if len(metric.Name) > 128 {
			errors = append(errors, ImportError{Row: rowNum, Field: "name", Message: "指标名称长度不能超过128"})
			continue
		}
		if metric.Status != "" && metric.Status != "在用" && metric.Status != "停用" {
			errors = append(errors, ImportError{Row: rowNum, Field: "status", Message: "指标状态只能是'在用'或'停用'"})
			continue
		}

		// 检查是否已存在
		var existing model.Metric
		db := postgres.Get().Where("metric_code = ?", metric.MetricCode).First(&existing)
		if db.Error != nil {
			isNew[metric.MetricCode] = true
		} else {
			isNew[metric.MetricCode] = false
			metric.ID = existing.ID
			metric.CreatedAt = existing.CreatedAt
		}

		metrics = append(metrics, metric)

		// 预览项（截断过长字段）
		previewName := metric.Name
		if len(previewName) > 20 {
			previewName = previewName[:20] + "..."
		}
		preview = append(preview, PreviewItem{
			MetricCode: metric.MetricCode,
			Name:       previewName,
			Domain:     metric.Domain,
			Status:     metric.Status,
			IsNew:      isNew[metric.MetricCode],
		})
	}

	// 统计
	newCount := 0
	updateCount := 0
	for _, item := range preview {
		if item.IsNew {
			newCount++
		} else {
			updateCount++
		}
	}

	// 生成 token
	token := fmt.Sprintf("%d_%s", time.Now().UnixNano(), randomString(8))

	// 存储数据
	data := &ImportData{
		Metrics:   metrics,
		IsNew:     isNew,
		CreatedAt: time.Now(),
	}
	s.mu.Lock()
	s.store[token] = data
	s.mu.Unlock()

	result := &PreviewResult{
		Total:       len(metrics),
		NewCount:    newCount,
		UpdateCount: updateCount,
		Errors:      errors,
		Preview:     preview,
	}

	return result, token, nil
}

// CommitImport 提交导入
func (s *ImportService) CommitImport(token string) (*CommitResult, error) {
	s.mu.Lock()
	data, ok := s.store[token]
	delete(s.store, token)
	s.mu.Unlock()

	if !ok {
		return nil, fmt.Errorf("无效的导入token或已过期")
	}

	// 检查是否过期（30分钟）
	if time.Since(data.CreatedAt) > 30*time.Minute {
		return nil, fmt.Errorf("导入token已过期，请重新上传")
	}

	db := postgres.Get()
	imported := 0
	newCount := 0
	updateCount := 0
	failed := 0

	for _, m := range data.Metrics {
		if data.IsNew[m.MetricCode] {
			// 新增
			if err := db.Create(&m).Error; err != nil {
				failed++
				continue
			}
			newCount++
		} else {
			// 更新
			if err := db.Save(&m).Error; err != nil {
				failed++
				continue
			}
			updateCount++
		}
		imported++
	}

	return &CommitResult{
		Imported:    imported,
		NewCount:    newCount,
		UpdateCount: updateCount,
		Failed:      failed,
	}, nil
}

// randomString 生成随机字符串
func randomString(length int) string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, length)
	for i := range b {
		b[i] = charset[time.Now().UnixNano()%int64(len(charset))]
		time.Sleep(time.Nanosecond)
	}
	return string(b)
}

// ParseRowInt 解析整数字段（供外部调用）
func ParseRowInt(value string) int {
	if value == "" {
		return 0
	}
	v, _ := strconv.Atoi(value)
	return v
}
