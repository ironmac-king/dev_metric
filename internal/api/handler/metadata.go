package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/lib/pq"
	"github.com/xuri/excelize/v2"
)

// GetAllMetrics 获取所有指标（供 AI 服务调用）
func GetAllMetrics(c *gin.Context) {
	var metrics []model.Metric
	postgres.Get().Where("status = ?", "在用").Find(&metrics)

	// 转换为简化格式供 AI 使用
	var result []map[string]interface{}
	for _, m := range metrics {
		result = append(result, map[string]interface{}{
			"id":                  m.ID,
			"metric_code":         m.MetricCode,
			"name":                m.Name,
			"name_en":             m.NameEn,
			"domain":              m.Domain,
			"category_1":          m.Category1,
			"category_2":          m.Category2,
			"category_3":          m.Category3,
			"metric_type":         m.MetricType,
			"business_definition": m.BusinessDefinition,
			"business_rule":       m.BusinessRule,
			"unit":                m.Unit,
			"common_dimensions":   m.CommonDimensions,
			"frequency":           m.Frequency,
			"technical_rule":      m.TechnicalRule,
			"starrocks_sql":       m.StarRocksSQL,
		})
	}

	response.Success(c, result)
}

// GetMetricMetadata 获取指标详情（供 AI 服务调用）
func GetMetricMetadata(c *gin.Context) {
	id := c.Param("id")
	var metric model.Metric

	if err := postgres.Get().First(&metric, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "指标不存在")
		return
	}

	// 获取关联维度
	var dimensions []model.Dimension
	postgres.Get().Table("dimensions").
		Joins("JOIN metric_dimensions ON dimensions.id = metric_dimensions.dimension_id").
		Where("metric_dimensions.metric_id = ?", id).
		Find(&dimensions)

	// 返回扁平结构，与 GetAllMetrics 保持一致
	response.Success(c, gin.H{
		"id":                  metric.ID,
		"metric_code":         metric.MetricCode,
		"name":                metric.Name,
		"name_en":             metric.NameEn,
		"domain":              metric.Domain,
		"category_1":          metric.Category1,
		"category_2":          metric.Category2,
		"category_3":          metric.Category3,
		"metric_type":         metric.MetricType,
		"business_definition":   metric.BusinessDefinition,
		"business_rule":        metric.BusinessRule,
		"unit":                metric.Unit,
		"common_dimensions":    metric.CommonDimensions,
		"frequency":           metric.Frequency,
		"technical_rule":      metric.TechnicalRule,
		"starrocks_sql":       metric.StarRocksSQL,
		"dimensions":          dimensions,
	})
}

// GetAllDimensions 获取所有维度
func GetAllDimensions(c *gin.Context) {
	var dimensions []model.Dimension
	postgres.Get().Find(&dimensions)
	response.Success(c, dimensions)
}

// GetAllTerms 获取所有业务术语映射
func GetAllTerms(c *gin.Context) {
	var terms []model.BusinessTerm
	postgres.Get().Find(&terms)
	response.Success(c, terms)
}

// CreateTerm 创建业务术语
func CreateTerm(c *gin.Context) {
	var term model.BusinessTerm
	if err := c.ShouldBindJSON(&term); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Create(&term).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}

	response.Success(c, term)
}

// UpdateTerm 更新业务术语
func UpdateTerm(c *gin.Context) {
	id := c.Param("id")
	var term model.BusinessTerm

	if err := postgres.Get().First(&term, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "术语不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 处理 pq.StringArray 类型的更新（GORM 需要特殊处理）
	if syns, ok := updates["synonyms"]; ok {
		switch v := syns.(type) {
		case []interface{}:
			// JSON array -> pq.StringArray
			strArr := make(pq.StringArray, len(v))
			for i, item := range v {
				if s, ok := item.(string); ok {
					strArr[i] = s
				}
			}
			updates["synonyms"] = strArr
		case []string:
			updates["synonyms"] = pq.StringArray(v)
		}
	}

	// 处理 pq.Int64Array 类型的更新（GORM 需要特殊处理）
	if metricIDs, ok := updates["metric_ids"]; ok {
		switch v := metricIDs.(type) {
		case []interface{}:
			// JSON array -> pq.Int64Array
			intArr := make(pq.Int64Array, 0, len(v))
			for _, item := range v {
				if f, ok := item.(float64); ok { // JSON number is float64
					intArr = append(intArr, int64(f))
				} else if i, ok := item.(int); ok {
					intArr = append(intArr, int64(i))
				}
			}
			updates["metric_ids"] = intArr
		case []int:
			intArr := make(pq.Int64Array, len(v))
			for i, item := range v {
				intArr[i] = int64(item)
			}
			updates["metric_ids"] = intArr
		case []int64:
			updates["metric_ids"] = pq.Int64Array(v)
		}
	}

	if err := postgres.Get().Model(&term).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}

	response.Success(c, term)
}

// DeleteTerm 删除业务术语
func DeleteTerm(c *gin.Context) {
	id := c.Param("id")
	postgres.Get().Delete(&model.BusinessTerm{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// businessTermExcelHeaders Excel 表头与字段映射
var businessTermExcelHeaders = []struct {
	Header string
	Field  string
}{
	{"术语", "term"},
	{"同义词", "synonyms"},
	{"维度字段", "dimension_field"},
	{"维度值", "dimension_value"},
	{"关联指标ID", "metric_ids"},
	{"描述", "description"},
}

// ExportTerms 导出业务术语 Excel
func ExportTerms(c *gin.Context) {
	var terms []model.BusinessTerm
	postgres.Get().Find(&terms)

	f := excelize.NewFile()
	defer f.Close()

	sheet := "业务术语"
	index, _ := f.NewSheet(sheet)
	f.SetActiveSheet(index)
	f.DeleteSheet("Sheet1")

	// 写入表头
	for colIdx, h := range businessTermExcelHeaders {
		cell, _ := excelize.CoordinatesToCellName(colIdx+1, 1)
		f.SetCellValue(sheet, cell, h.Header)
	}

	// 写入数据
	for rowIdx, term := range terms {
		for colIdx, h := range businessTermExcelHeaders {
			cell, _ := excelize.CoordinatesToCellName(colIdx+1, rowIdx+2)
			switch h.Field {
			case "synonyms":
				synonyms := term.Synonyms
				f.SetCellValue(sheet, cell, strings.Join(synonyms, ","))
			case "metric_ids":
				var ids []string
				for _, id := range term.MetricIDs {
					ids = append(ids, strconv.FormatInt(id, 10))
				}
				f.SetCellValue(sheet, cell, strings.Join(ids, ","))
			default:
				value := getBusinessTermCellValue(&term, h.Field)
				f.SetCellValue(sheet, cell, value)
			}
		}
	}

	// 设置列宽
	for colIdx, h := range businessTermExcelHeaders {
		colName, _ := excelize.ColumnNumberToName(colIdx + 1)
		width := 15.0
		if h.Field == "description" {
			width = 30.0
		} else if h.Field == "synonyms" {
			width = 25.0
		}
		f.SetColWidth(sheet, colName, colName, width)
	}

	// 发送文件
	filename := fmt.Sprintf("business_terms_%s.xlsx", time.Now().Format("20060102"))
	c.Header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))

	if err := f.Write(c.Writer); err != nil {
		response.Error(c, response.CodeInternalError, "生成Excel失败")
		return
	}
}

func getBusinessTermCellValue(term *model.BusinessTerm, field string) interface{} {
	switch field {
	case "term":
		return term.Term
	case "dimension_field":
		return term.DimensionField
	case "dimension_value":
		return term.DimensionValue
	case "description":
		return term.Description
	default:
		return nil
	}
}

// ImportTerms 导入业务术语 Excel
func ImportTerms(c *gin.Context) {
	file, _, err := c.Request.FormFile("file")
	if err != nil {
		response.Error(c, response.CodeBadRequest, "请上传Excel文件")
		return
	}
	defer file.Close()

	// 打开上传的 Excel 文件
	f, err := excelize.OpenReader(file)
	if err != nil {
		response.Error(c, response.CodeBadRequest, "无法打开Excel文件，请确认文件格式正确")
		return
	}
	defer f.Close()

	sheet := f.GetSheetList()[0]
	rows, err := f.GetRows(sheet)
	if err != nil {
		response.Error(c, response.CodeBadRequest, "读取Excel失败")
		return
	}

	if len(rows) < 2 {
		response.Error(c, response.CodeBadRequest, "Excel文件为空或没有数据行")
		return
	}

	// 解析表头
	headers := rows[0]
	headerMap := make(map[string]int)
	for idx, h := range headers {
		headerMap[h] = idx
	}

	// 验证必需列
	requiredHeaders := []string{"术语"}
	for _, h := range requiredHeaders {
		if _, ok := headerMap[h]; !ok {
			response.Error(c, response.CodeBadRequest, fmt.Sprintf("缺少必需列: %s", h))
			return
		}
	}

	// 解析数据行
	var terms []model.BusinessTerm
	errors := []string{}
	for rowIdx, row := range rows[1:] {
		term := model.BusinessTerm{}

		// term (术语) - 必需
		if idx, ok := headerMap["术语"]; ok && idx < len(row) {
			term.Term = row[idx]
		}
		if term.Term == "" {
			errors = append(errors, fmt.Sprintf("第%d行: 术语不能为空", rowIdx+2))
			continue
		}

		// synonyms (同义词) - 逗号分隔
		if idx, ok := headerMap["同义词"]; ok && idx < len(row) && row[idx] != "" {
			syns := strings.Split(row[idx], ",")
			for i := range syns {
				syns[i] = strings.TrimSpace(syns[i])
			}
			term.Synonyms = syns
		}

		// dimension_field (维度字段)
		if idx, ok := headerMap["维度字段"]; ok && idx < len(row) {
			term.DimensionField = row[idx]
		}

		// dimension_value (维度值)
		if idx, ok := headerMap["维度值"]; ok && idx < len(row) {
			term.DimensionValue = row[idx]
		}

		// metric_ids (关联指标ID) - 逗号分隔的ID列表
		if idx, ok := headerMap["关联指标ID"]; ok && idx < len(row) && row[idx] != "" {
			idStrs := strings.Split(row[idx], ",")
			var ids pq.Int64Array
			for _, idStr := range idStrs {
				idStr = strings.TrimSpace(idStr)
				if idStr == "" {
					continue
				}
				if id, err := strconv.ParseInt(idStr, 10, 64); err == nil {
					ids = append(ids, id)
				} else {
					errors = append(errors, fmt.Sprintf("第%d行: 无效的指标ID '%s'", rowIdx+2, idStr))
				}
			}
			term.MetricIDs = ids
		}

		// description (描述)
		if idx, ok := headerMap["描述"]; ok && idx < len(row) {
			term.Description = row[idx]
		}

		terms = append(terms, term)
	}

	// 批量 upsert（存在则更新，不存在则插入）
	inserted := 0
	updated := 0
	if len(terms) > 0 {
		for _, term := range terms {
			// 先查询是否存在
			var existing model.BusinessTerm
			err := postgres.Get().Where("term = ?", term.Term).First(&existing).Error
			if err == nil {
				// 存在，更新
				updates := map[string]interface{}{
					"synonyms":        term.Synonyms,
					"dimension_field": term.DimensionField,
					"dimension_value": term.DimensionValue,
					"metric_ids":      term.MetricIDs,
					"description":     term.Description,
				}
				if err := postgres.Get().Model(&existing).Updates(updates).Error; err != nil {
					errors = append(errors, fmt.Sprintf("更新术语'%s'失败: %v", term.Term, err))
				} else {
					updated++
				}
			} else {
				// 不存在，插入
				if err := postgres.Get().Create(&term).Error; err != nil {
					errors = append(errors, fmt.Sprintf("插入术语'%s'失败: %v", term.Term, err))
				} else {
					inserted++
				}
			}
		}
	}

	result := gin.H{
		"inserted": inserted,
		"updated":  updated,
		"total":    len(rows) - 1,
		"errors":   errors,
	}

	if len(errors) > 0 {
		response.SuccessWithMessage(c, fmt.Sprintf("导入完成，新增%d条，更新%d条，失败%d条", inserted, updated, len(errors)), result)
	} else {
		response.Success(c, result)
	}
}

// ExportTermsTemplate 导出业务术语空模板 Excel
func ExportTermsTemplate(c *gin.Context) {
	f := excelize.NewFile()
	defer f.Close()

	sheet := "业务术语模板"
	index, _ := f.NewSheet(sheet)
	f.SetActiveSheet(index)
	f.DeleteSheet("Sheet1")

	// 写入表头
	for colIdx, h := range businessTermExcelHeaders {
		cell, _ := excelize.CoordinatesToCellName(colIdx+1, 1)
		f.SetCellValue(sheet, cell, h.Header)
	}

	// 设置列宽
	for colIdx, h := range businessTermExcelHeaders {
		colName, _ := excelize.ColumnNumberToName(colIdx + 1)
		width := 15.0
		if h.Field == "description" {
			width = 30.0
		} else if h.Field == "synonyms" {
			width = 25.0
		}
		f.SetColWidth(sheet, colName, colName, width)
	}

	// 添加示例说明
	f.SetCellValue(sheet, "H2", "同义词多个用逗号分隔，如：亚马逊,Amazon,AMZ")
	f.SetCellValue(sheet, "H3", "关联指标ID多个用逗号分隔，如：1,2,3")

	// 发送文件
	filename := fmt.Sprintf("business_terms_template_%s.xlsx", time.Now().Format("20060102"))
	c.Header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))

	if err := f.Write(c.Writer); err != nil {
		response.Error(c, response.CodeInternalError, "生成Excel失败")
		return
	}
}
