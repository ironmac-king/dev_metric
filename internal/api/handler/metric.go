package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/repository/starrocks"
	"dev_metric/internal/service"
	"dev_metric/pkg/response"
	"fmt"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/xuri/excelize/v2"
)

// auditService 审计服务实例
var auditService = service.NewSQLAuditService()

// ListMetrics 获取指标列表
func ListMetrics(c *gin.Context) {
	var metrics []model.Metric
	var total int64

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	// 分类筛选
	domain := c.Query("domain")
	category1 := c.Query("category_1")
	category2 := c.Query("category_2")
	status := c.Query("status")
	keyword := c.Query("keyword")

	db := postgres.Get().Model(&model.Metric{})

	if domain != "" {
		db = db.Where("domain = ?", domain)
	}
	if category1 != "" {
		db = db.Where("category_1 = ?", category1)
	}
	if category2 != "" {
		db = db.Where("category_2 = ?", category2)
	}
	if status != "" {
		db = db.Where("status = ?", status)
	}
	if keyword != "" {
		db = db.Where("name ILIKE ? OR metric_code ILIKE ? OR name_en ILIKE ?", "%"+keyword+"%", "%"+keyword+"%", "%"+keyword+"%")
	}

	db.Count(&total)
	db.Order("updated_at DESC").Offset((page - 1) * pageSize).Limit(pageSize).Find(&metrics)

	response.Page(c, metrics, total, page, pageSize)
}

// GetMetricStats 获取指标统计数据（总数、在用、停用）
func GetMetricStats(c *gin.Context) {
	var total int64
	var activeCount int64

	db := postgres.Get().Model(&model.Metric{})
	db.Count(&total)
	db.Where("status = ?", "在用").Count(&activeCount)

	response.Success(c, gin.H{
		"total":       total,
		"active":      activeCount,
		"inactive":    total - activeCount,
	})
}

// GetMetric 获取指标详情
func GetMetric(c *gin.Context) {
	id := c.Param("id")
	var metric model.Metric

	if err := postgres.Get().First(&metric, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指标不存在")
		return
	}

	response.Success(c, metric)
}

// CreateMetric 创建指标
func CreateMetric(c *gin.Context) {
	var metric model.Metric
	if err := c.ShouldBindJSON(&metric); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Create(&metric).Error; err != nil {
		// 审计日志：创建失败
		auditService.LogSQL(getUserID(c), "CREATE metric", nil, 1, err.Error(), c.ClientIP())
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}

	// 审计日志：创建成功
	auditService.LogMetricCreate(getUserID(c), metric.ID, metric.Name, c.ClientIP())
	response.Success(c, metric)
}

// UpdateMetric 更新指标
func UpdateMetric(c *gin.Context) {
	id := c.Param("id")
	var metric model.Metric

	if err := postgres.Get().First(&metric, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指标不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	updates["updated_at"] = time.Now()

	// 设置更新人
	userID := getUserID(c)
	if userID > 0 {
		var user model.User
		if err := postgres.Get().First(&user, userID).Error; err == nil {
			updates["updated_by"] = user.Username
		}
	}

	if err := postgres.Get().Model(&metric).Updates(updates).Error; err != nil {
		// 审计日志：更新失败
		auditService.LogSQL(getUserID(c), "UPDATE metric", nil, 1, err.Error(), c.ClientIP())
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}

	// 审计日志：更新成功
	changes := ""
	for k, v := range updates {
		if changes != "" {
			changes += ", "
		}
		changes += k + "=" + fmt.Sprintf("%v", v)
	}
	auditService.LogMetricUpdate(getUserID(c), metric.ID, changes, c.ClientIP())
	response.Success(c, metric)
}

// DeleteMetric 删除指标
func DeleteMetric(c *gin.Context) {
	id := c.Param("id")

	// 先获取指标信息用于审计日志
	var metric model.Metric
	if err := postgres.Get().First(&metric, id).Error; err == nil {
		// 审计日志：删除成功
		auditService.LogMetricDelete(getUserID(c), metric.ID, c.ClientIP())
	}

	if err := postgres.Get().Delete(&model.Metric{}, id).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}

	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetMetricData 获取指标趋势数据
func GetMetricData(c *gin.Context) {
	id := c.Param("id")
	var metric model.Metric

	if err := postgres.Get().First(&metric, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指标不存在")
		return
	}

	// 从 StarRocks 查询数据
	if metric.StarRocksSQL == "" {
		response.Error(c, response.CodeBadRequest, "该指标未配置查询SQL")
		return
	}

	result, err := starrocks.Query(c.Request.Context(), metric.StarRocksSQL, metric.ID)
	if err != nil {
		response.Error(c, response.CodeInternalError, "查询失败: "+err.Error())
		return
	}

	response.Success(c, gin.H{
		"metric": metric,
		"data":   result.Data,
		"cached": result.Cached,
	})
}

// ImportMetrics 导入指标字典 Excel（已废弃，改用 Preview + Commit）
func ImportMetrics(c *gin.Context) {
	response.Error(c, response.CodeInternalError, "请使用预览接口 POST /import-preview")
}

// ImportPreviewMetrics 导入预览
func ImportPreviewMetrics(c *gin.Context) {
	file, _, err := c.Request.FormFile("file")
	if err != nil {
		response.Error(c, response.CodeBadRequest, "请上传Excel文件")
		return
	}
	defer file.Close()

	filename := c.Request.FormValue("filename")
	svc := service.GetImportService()
	result, token, err := svc.PreviewImport(file, filename)
	if err != nil {
		response.Error(c, response.CodeBadRequest, err.Error())
		return
	}

	response.Success(c, gin.H{
		"token":   token,
		"total":   result.Total,
		"new_count":    result.NewCount,
		"update_count": result.UpdateCount,
		"errors":  result.Errors,
		"preview": result.Preview,
	})
}

// ImportCommitMetrics 导入提交
func ImportCommitMetrics(c *gin.Context) {
	var req struct {
		Token string `json:"token" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "缺少token参数")
		return
	}

	svc := service.GetImportService()
	result, err := svc.CommitImport(req.Token)
	if err != nil {
		response.Error(c, response.CodeBadRequest, err.Error())
		return
	}

	response.Success(c, result)
}

// ImportMetricsFile 导入指标字典 Excel（单文件流方式，供前端上传）
func ImportMetricsFile(c *gin.Context) {
	file, _, err := c.Request.FormFile("file")
	if err != nil {
		response.Error(c, response.CodeBadRequest, "请上传Excel文件")
		return
	}
	defer file.Close()

	filename := c.Request.FormValue("filename")
	svc := service.GetImportService()
	result, token, err := svc.PreviewImport(file, filename)
	if err != nil {
		response.Error(c, response.CodeBadRequest, err.Error())
		return
	}

	response.Success(c, gin.H{
		"token":      token,
		"total":      result.Total,
		"new_count":  result.NewCount,
		"update_count": result.UpdateCount,
		"errors":     result.Errors,
		"preview":    result.Preview,
	})
}

// metricExcelHeaders Excel 表头与字段映射（与 cmd/importer/main.go 保持一致）
var metricExcelHeaders = []struct {
	Header string
	Field  string
}{
	{"序号", "seq_no"},
	{"指标编号", "metric_code"},
	{"所属域", "domain"},
	{"指标一级分类", "category_1"},
	{"指标二级分类", "category_2"},
	{"指标三级分类", "category_3"},
	{"指标名称", "name"},
	{"指标英文名称", "name_en"},
	{"指标类型", "metric_type"},
	{"业务定义", "business_definition"},
	{"业务口径", "business_rule"},
	{"适用范围", "applicable_scope"},
	{"统计规则", "statistics_rule"},
	{"度量单位", "unit"},
	{"常用维度", "common_dimensions"},
	{"机构层级", "org_level"},
	{"统计频度", "frequency"},
	{"技术口径", "technical_rule"},
	{"统计格式", "data_format"},
	{"指标精度", "precision"},
	{"指标归属部门", "owner_dept"},
	{"指标状态", "status"},
	{"发布日期", "publish_date"},
	{"失效日期", "expire_date"},
}

// getCellValue 根据字段名从 metric 中获取值
func getMetricCellValue(metric *model.Metric, field string) string {
	switch field {
	case "seq_no":
		return fmt.Sprintf("%d", metric.SeqNo)
	case "metric_code":
		return metric.MetricCode
	case "domain":
		return metric.Domain
	case "category_1":
		return metric.Category1
	case "category_2":
		return metric.Category2
	case "category_3":
		return metric.Category3
	case "name":
		return metric.Name
	case "name_en":
		return metric.NameEn
	case "metric_type":
		return metric.MetricType
	case "business_definition":
		return metric.BusinessDefinition
	case "business_rule":
		return metric.BusinessRule
	case "applicable_scope":
		return metric.ApplicableScope
	case "statistics_rule":
		return metric.StatisticsRule
	case "unit":
		return metric.Unit
	case "common_dimensions":
		return metric.CommonDimensions
	case "org_level":
		return metric.OrgLevel
	case "frequency":
		return metric.Frequency
	case "technical_rule":
		return metric.TechnicalRule
	case "data_format":
		return metric.DataFormat
	case "precision":
		return metric.Precision
	case "owner_dept":
		return metric.OwnerDept
	case "status":
		return metric.Status
	case "publish_date":
		if metric.PublishDate != nil {
			return metric.PublishDate.Format("2006-01-02")
		}
		return ""
	case "expire_date":
		if metric.ExpireDate != nil {
			return metric.ExpireDate.Format("2006-01-02")
		}
		return ""
	default:
		return ""
	}
}

// ExportTemplateMetrics 导出空模板 Excel
func ExportTemplateMetrics(c *gin.Context) {
	f := excelize.NewFile()
	defer f.Close()

	sheet := "指标模板"
	index, err := f.NewSheet(sheet)
	if err != nil {
		response.Error(c, response.CodeInternalError, "创建工作表失败")
		return
	}
	f.SetActiveSheet(index)
	f.DeleteSheet("Sheet1")

	// 写入表头
	for colIdx, h := range metricExcelHeaders {
		cell, _ := excelize.CoordinatesToCellName(colIdx+1, 1)
		f.SetCellValue(sheet, cell, h.Header)
	}

	// 设置列宽
	for colIdx := range metricExcelHeaders {
		colName, _ := excelize.ColumnNumberToName(colIdx + 1)
		f.SetColWidth(sheet, colName, colName, 18)
	}

	// 写出版本说明在第二行
	f.SetCellValue(sheet, "A2", "请在下方填写指标数据，表头行不可修改")
	f.SetCellValue(sheet, "B2", "导入时会根据表头自动匹配字段")

	// 发送文件
	filename := fmt.Sprintf("metrics_template_%s.xlsx", time.Now().Format("20060102"))
	c.Header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))

	if err := f.Write(c.Writer); err != nil {
		response.Error(c, response.CodeInternalError, "生成Excel失败")
		return
	}
}

// ExportSampleMetrics 导出指标样例 Excel
func ExportSampleMetrics(c *gin.Context) {
	domain := c.Query("domain")
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "500"))
	if pageSize > 500 {
		pageSize = 500
	}

	db := postgres.Get().Model(&model.Metric{})
	if domain != "" {
		db = db.Where("domain = ?", domain)
	}

	var metrics []model.Metric
	db.Offset((page - 1) * pageSize).Limit(pageSize).Find(&metrics)

	f := excelize.NewFile()
	defer f.Close()

	sheet := "指标数据"
	index, err := f.NewSheet(sheet)
	if err != nil {
		response.Error(c, response.CodeInternalError, "创建工作表失败")
		return
	}
	f.SetActiveSheet(index)
	f.DeleteSheet("Sheet1")

	// 写入表头
	for colIdx, h := range metricExcelHeaders {
		cell, _ := excelize.CoordinatesToCellName(colIdx+1, 1)
		f.SetCellValue(sheet, cell, h.Header)
	}

	// 写入数据
	for rowIdx, metric := range metrics {
		for colIdx, h := range metricExcelHeaders {
			cell, _ := excelize.CoordinatesToCellName(colIdx+1, rowIdx+2)
			f.SetCellValue(sheet, cell, getMetricCellValue(&metric, h.Field))
		}
	}

	// 设置列宽
	for colIdx := range metricExcelHeaders {
		colName, _ := excelize.ColumnNumberToName(colIdx + 1)
		f.SetColWidth(sheet, colName, colName, 18)
	}

	// 发送文件
	filename := fmt.Sprintf("metrics_sample_%s.xlsx", time.Now().Format("20060102"))
	c.Header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))

	if err := f.Write(c.Writer); err != nil {
		response.Error(c, response.CodeInternalError, "生成Excel失败")
		return
	}
}
