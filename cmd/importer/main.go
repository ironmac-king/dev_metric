package main

import (
	"dev_metric/config"
	"dev_metric/internal/model"
	"flag"
	"fmt"
	"log"
	"time"

	"github.com/xuri/excelize/v2"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// headerMapping Excel 表头映射（根据实际 Excel 列名）
var headerMapping = map[string]string{
	"序号":             "seq_no",
	"指标编号":          "metric_code",
	"所属域":           "domain",
	"指标一级分类":       "category_1",
	"指标二级分类":       "category_2",
	"指标三级分类":       "category_3",
	"指标名称":          "name",
	"指标英文名称":        "name_en",
	"指标类型":          "metric_type",
	"业务定义":          "business_definition",
	"业务口径":          "business_rule",
	"适用范围":          "applicable_scope",
	"统计规则":          "statistics_rule",
	"度量单位":          "unit",
	"常用维度":          "common_dimensions",
	"机构层级":          "org_level",
	"统计频度":          "frequency",
	"技术口径":          "technical_rule",
	"统计格式":          "data_format",
	"指标精度":          "precision",
	"指标归属部门":        "owner_dept",
	"指标状态":          "status",
	"发布日期":          "publish_date",
	"失效日期":          "expire_date",
}

func main() {
	var configPath string
	var excelPath string

	flag.StringVar(&configPath, "config", "config.yaml", "配置文件路径")
	flag.StringVar(&excelPath, "file", "", "Excel文件路径")
	flag.Parse()

	if excelPath == "" {
		log.Fatal("请指定 Excel 文件路径 (--file)")
	}

	// 加载配置
	cfg, err := config.Load(configPath)
	if err != nil {
		log.Fatalf("加载配置失败: %v", err)
	}

	// 连接数据库
	db, err := gorm.Open(postgres.Open(cfg.Database.DSN()), &gorm.Config{})
	if err != nil {
		log.Fatalf("连接数据库失败: %v", err)
	}

	log.Printf("开始导入: %s", excelPath)

	// 使用 excelize 读取 Excel
	f, err := excelize.OpenFile(excelPath)
	if err != nil {
		log.Fatalf("打开 Excel 文件失败: %v", err)
	}
	defer f.Close()

	// 获取第一个 sheet
	sheets := f.GetSheetList()
	if len(sheets) == 0 {
		log.Fatal("Excel 文件中没有 Sheet")
	}
	sheetName := sheets[0]
	log.Printf("使用 Sheet: %s", sheetName)
	rows, err := f.GetRows(sheetName)
	if err != nil {
		log.Fatalf("读取 Sheet 失败: %v", err)
	}

	if len(rows) < 2 {
		log.Fatal("Excel 文件行数不足（需要表头+至少1行数据）")
	}

	// 解析表头
	headers := rows[0]
	colIndex := make(map[string]int)
	for i, h := range headers {
		if mapped, ok := headerMapping[h]; ok {
			colIndex[mapped] = i
		}
	}

	log.Printf("发现 %d 个指标字段", len(colIndex))

	// 导入数据
	var metrics []model.Metric
	for rowIdx, row := range rows[1:] {
		metric := parseRow(row, colIndex)
		if metric.MetricCode == "" {
			log.Printf("警告: 第 %d 行数据缺少指标编号，跳过", rowIdx+2)
			continue
		}
		metrics = append(metrics, metric)
	}

	log.Printf("解析到 %d 条指标记录", len(metrics))

	// 批量导入/更新
	importCount := 0
	updateCount := 0
	for _, m := range metrics {
		var existing model.Metric
		result := db.Where("metric_code = ?", m.MetricCode).First(&existing)

		if result.Error != nil {
			// 新增
			if err := db.Create(&m).Error; err != nil {
				log.Printf("插入失败 [%s]: %v", m.MetricCode, err)
				continue
			}
			importCount++
		} else {
			// 更新
			m.ID = existing.ID
			m.CreatedAt = existing.CreatedAt
			if err := db.Save(&m).Error; err != nil {
				log.Printf("更新失败 [%s]: %v", m.MetricCode, err)
				continue
			}
			updateCount++
		}
	}

	log.Printf("导入完成: 新增 %d 条，更新 %d 条", importCount, updateCount)
	log.Println("提示: 记得同步执行数据库迁移 SQL 创建表结构")
}

func parseRow(row []string, colIndex map[string]int) model.Metric {
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

	// 解析日期
	if v := getValue("publish_date"); v != "" {
		if t, err := time.Parse("2006/1/2", v); err == nil {
			metric.PublishDate = &t
		}
	}
	if v := getValue("expire_date"); v != "" {
		if t, err := time.Parse("2006/1/2", v); err == nil {
			metric.ExpireDate = &t
		}
	}

	return metric
}
