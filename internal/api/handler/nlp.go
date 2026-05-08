package handler

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/service"
	"dev_metric/pkg/response"

	"github.com/gin-gonic/gin"
)

// nlpAuditService 审计服务实例
var nlpAuditService = service.NewSQLAuditService()

// IntentTemplate CRUD

func ListIntentTemplates(c *gin.Context) {
	var templates []model.IntentTemplate
	postgres.Get().Select("*").Find(&templates)
	response.Success(c, templates)
}

func GetIntentTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.IntentTemplate
	if err := postgres.Get().Select("*").First(&tpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}
	response.Success(c, tpl)
}

func CreateIntentTemplate(c *gin.Context) {
	var tpl model.IntentTemplate
	if err := c.ShouldBindJSON(&tpl); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&tpl).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "intent_template", "CREATE", c.ClientIP())
	response.Success(c, tpl)
}

func UpdateIntentTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.IntentTemplate
	if err := postgres.Get().First(&tpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&tpl).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "intent_template", "UPDATE", c.ClientIP())
	response.Success(c, tpl)
}

func DeleteIntentTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.IntentTemplate
	if err := postgres.Get().First(&tpl, id).Error; err == nil {
		// 审计日志
		nlpAuditService.LogNLPConfig(getUserID(c), "intent_template", "DELETE", c.ClientIP())
	}
	postgres.Get().Delete(&model.IntentTemplate{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// SQLTemplate CRUD

func ListSQLTemplates(c *gin.Context) {
	var templates []model.SQLTemplate
	query := postgres.Get()

	templateType := c.Query("type")
	drilldownCategory := c.Query("drilldown_category")

	if templateType != "" {
		query = query.Where("template_type = ?", templateType)
	}
	if drilldownCategory != "" {
		query = query.Where("drilldown_category = ?", drilldownCategory)
	}

	// 按 template_order 排序，支持 drilldown_category 下多模板按顺序执行
	query = query.Order("drilldown_category, template_order, id")

	query.Find(&templates)
	response.Success(c, templates)
}

func GetSQLTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.SQLTemplate
	if err := postgres.Get().First(&tpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}
	response.Success(c, tpl)
}

func CreateSQLTemplate(c *gin.Context) {
	var tpl model.SQLTemplate
	if err := c.ShouldBindJSON(&tpl); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&tpl).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "sql_template", "CREATE", c.ClientIP())
	response.Success(c, tpl)
}

func UpdateSQLTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.SQLTemplate
	if err := postgres.Get().First(&tpl, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "模板不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 手动处理 metric_names 类型转换（JSON 数组 -> StringArray）
	if mn, ok := updates["metric_names"]; ok {
		if arr, ok := mn.([]interface{}); ok {
			sa := make(model.StringArray, len(arr))
			for i, v := range arr {
				if s, ok := v.(string); ok {
					sa[i] = s
				}
			}
			updates["metric_names"] = sa
		}
	}

	if err := postgres.Get().Model(&tpl).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	// 审计日志
	nlpAuditService.LogNLPConfig(getUserID(c), "sql_template", "UPDATE", c.ClientIP())
	response.Success(c, tpl)
}

func DeleteSQLTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.SQLTemplate
	if err := postgres.Get().First(&tpl, id).Error; err == nil {
		// 审计日志
		nlpAuditService.LogNLPConfig(getUserID(c), "sql_template", "DELETE", c.ClientIP())
	}
	postgres.Get().Delete(&model.SQLTemplate{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetAllNLPTemplates 获取所有 NLP 模板（供 AI 服务调用）
// Query params:
//   - type: 过滤 sql_templates 类型 (legacy | drilldown)，不传则返回所有
//   - drilldown_category: 过滤下钻类别 (sales/ad/inventory/cost)
func GetAllNLPTemplates(c *gin.Context) {
	var intentTemplates []model.IntentTemplate
	var sqlTemplates []model.SQLTemplate

	postgres.Get().Select("*").Where("status = ?", 1).Find(&intentTemplates)

	// 按 template_type 和 drilldown_category 过滤 SQL 模板
	query := postgres.Get().Where("status = ?", 1)
	templateType := c.Query("type")
	if templateType != "" {
		query = query.Where("template_type = ?", templateType)
	}
	drilldownCategory := c.Query("drilldown_category")
	if drilldownCategory != "" {
		query = query.Where("drilldown_category = ?", drilldownCategory)
	}
	// drilldown 类型按 order 排序
	query = query.Order("drilldown_category, template_order, id")
	query.Find(&sqlTemplates)

	response.Success(c, gin.H{
		"intent_templates": intentTemplates,
		"sql_templates":    sqlTemplates,
	})
}

// RebuildIntentEmbeddings 重新生成所有意图向量
func RebuildIntentEmbeddings(c *gin.Context) {
	// 获取所有启用的意图模板
	var templates []model.IntentTemplate
	postgres.Get().Where("status = ?", 1).Find(&templates)

	// 第一步：收集所有文本及其意图信息
	type textIntent struct {
		text      string
		intentID  uint
		intentType string
	}
	var allTexts []string
	textIntentMap := make(map[string]textIntent) // text -> intent info

	for _, tpl := range templates {
		patterns := strings.Split(tpl.Patterns, ",")
		for _, text := range patterns {
			text = strings.TrimSpace(text)
			if text == "" {
				continue
			}
			allTexts = append(allTexts, text)
			textIntentMap[text] = textIntent{
				intentID:   tpl.ID,
				intentType: tpl.Intent,
			}
		}
	}

	if len(allTexts) == 0 {
		response.Success(c, gin.H{"success": true, "count": 0})
		return
	}

	// 第二步：调用 Python AI 服务批量生成向量
	vectors, err := generateEmbeddingsBatch(allTexts)
	if err != nil {
		response.Error(c, response.CodeInternalError, fmt.Sprintf("调用向量生成服务失败: %v", err))
		return
	}

	// 第三步：存储向量到 PostgreSQL
	count := 0
	for text, info := range textIntentMap {
		embedding, ok := vectors[text]
		if !ok {
			continue
		}
		embeddingJSON, _ := json.Marshal(embedding)
		emb := model.IntentEmbedding{
			IntentID:   info.intentID,
			IntentType: info.intentType,
			Text:       text,
			Embedding:  string(embeddingJSON),
		}

		// 使用 upsert
		postgres.Get().Where("intent_id = ? AND text = ?", info.intentID, text).
			Assign(emb).
			FirstOrCreate(&model.IntentEmbedding{})
		count++
	}

	response.Success(c, gin.H{"success": true, "count": count})
}

// RebuildMetricEmbeddings 重新生成所有指标向量
func RebuildMetricEmbeddings(c *gin.Context) {
	// 获取所有指标
	var metrics []model.Metric
	postgres.Get().Find(&metrics)

	count := 0
	batchSize := 20 // 每批处理的指标数量

	// 辅助函数：构建指标的向量化文本
	buildText := func(m model.Metric) string {
		parts := []string{m.Name}
		if m.NameEn != "" {
			parts = append(parts, m.NameEn)
		}
		if m.BusinessDefinition != "" {
			parts = append(parts, m.BusinessDefinition)
		}
		return strings.Join(parts, " ")
	}

	// 分批处理
	for i := 0; i < len(metrics); i += batchSize {
		end := i + batchSize
		if end > len(metrics) {
			end = len(metrics)
		}
		batch := metrics[i:end]

		// 准备批量文本和指标映射
		texts := make([]string, 0, len(batch))
		textToMetric := make(map[string]model.Metric, len(batch))
		for _, m := range batch {
			combinedText := buildText(m)
			texts = append(texts, combinedText)
			textToMetric[combinedText] = m
		}

		// 调用 Python AI 服务批量生成向量（使用阿里 embedding）
		vectors, err := generateEmbeddingsBatch(texts)
		if err != nil {
			log.Printf("批量生成向量失败: %v", err)
			continue
		}

		// 存储每条向量
		for combinedText, emb := range vectors {
			m := textToMetric[combinedText]
			embeddingJSON, _ := json.Marshal(emb)
			metricEmb := model.MetricEmbedding{
				MetricID:   m.ID,
				MetricCode: m.MetricCode,
				Text:       combinedText,
				Embedding:  string(embeddingJSON),
			}
			postgres.Get().Where("metric_id = ?", m.ID).
				Assign(metricEmb).
				FirstOrCreate(&model.MetricEmbedding{})
			count++
		}
	}

	response.Success(c, gin.H{"success": true, "count": count})
}

// GetIntentVectors 获取所有意图向量（供 Python AI 服务调用）
func GetIntentVectors(c *gin.Context) {
	var embeddings []model.IntentEmbedding
	postgres.Get().Find(&embeddings)

	// 转换为响应格式
	result := make([]map[string]interface{}, 0, len(embeddings))
	for _, emb := range embeddings {
		// 解析 JSON 字符串为浮点数组
		var embedding []float64
		if err := json.Unmarshal([]byte(emb.Embedding), &embedding); err != nil {
			continue
		}
		result = append(result, map[string]interface{}{
			"text":        emb.Text,
			"intent_type": emb.IntentType,
			"embedding":   embedding,
		})
	}

	response.Success(c, result)
}

// GetMetricVectors 获取所有指标向量（供 Python AI 服务调用）
func GetMetricVectors(c *gin.Context) {
	var embeddings []model.MetricEmbedding
	postgres.Get().Find(&embeddings)

	// 转换为响应格式
	result := make([]map[string]interface{}, 0, len(embeddings))
	for _, emb := range embeddings {
		// 解析 JSON 字符串为浮点数组
		var embedding []float64
		if err := json.Unmarshal([]byte(emb.Embedding), &embedding); err != nil {
			continue
		}
		result = append(result, map[string]interface{}{
			"metric_code": emb.MetricCode,
			"text":        emb.Text,
			"embedding":   embedding,
			"info": map[string]interface{}{
				"metric_id": emb.MetricID,
			},
		})
	}

	response.Success(c, result)
}

// generateEmbedding 调用 AI 服务生成向量
func generateEmbedding(text string) ([]float64, error) {
	apiURL := "https://api.deepseek.com/embeddings"
	apiKey := os.Getenv("DEEPSEEK_API_KEY")

	reqBody := map[string]interface{}{
		"model": "deepseek-embedding",
		"input": text,
	}
	bodyBytes, _ := json.Marshal(reqBody)

	req, _ := http.NewRequest("POST", apiURL, bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("embedding API error: %d", resp.StatusCode)
	}

	data := result["data"].([]interface{})
	embedding := data[0].(map[string]interface{})["embedding"].([]interface{})
	resultVec := make([]float64, len(embedding))
	for i, v := range embedding {
		resultVec[i] = v.(float64)
	}

	return resultVec, nil
}

// generateEmbeddingsBatch 调用 Python AI 服务批量生成向量
// 返回 map[text]embedding
func generateEmbeddingsBatch(texts []string) (map[string][]float64, error) {
	aiHost := "http://localhost:8081"
	url := aiHost + "/internal/generate-embeddings"

	reqBody := map[string]interface{}{
		"texts": texts,
	}
	bodyBytes, _ := json.Marshal(reqBody)

	req, _ := http.NewRequest("POST", url, bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("请求 Python 服务失败: %v", err)
	}
	defer resp.Body.Close()

	var result struct {
		Code int `json:"code"`
		Data []struct {
			Text      string    `json:"text"`
			Embedding []float64 `json:"embedding"`
		} `json:"data"`
		Message string `json:"message"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("解析响应失败: %v", err)
	}

	if result.Code != 0 {
		return nil, fmt.Errorf("Python 服务错误: %s", result.Message)
	}

	vectors := make(map[string][]float64)
	for _, item := range result.Data {
		vectors[item.Text] = item.Embedding
	}

	return vectors, nil
}

// GenerateEmbeddings 对外提供的embedding生成接口（供Python AI服务调用）
func GenerateEmbeddings(c *gin.Context) {
	var req struct {
		Texts []string `json:"texts"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if len(req.Texts) == 0 {
		response.Success(c, []map[string]interface{}{})
		return
	}

	vectors, err := generateEmbeddingsBatch(req.Texts)
	if err != nil {
		response.Error(c, response.CodeInternalError, fmt.Sprintf("生成embedding失败: %v", err))
		return
	}

	// 转换为响应格式
	result := make([]map[string]interface{}, 0, len(req.Texts))
	for _, text := range req.Texts {
		if vec, ok := vectors[text]; ok {
			result = append(result, map[string]interface{}{
				"text":      text,
				"embedding": vec,
			})
		}
	}

	response.Success(c, result)
}

// ========== SlotDefinition CRUD ==========

// ListSlotDefinitions 获取所有槽位定义
func ListSlotDefinitions(c *gin.Context) {
	var slots []model.SlotDefinition
	query := postgres.Get().Select("*")

	// 按 priority 降序排序
	query.Order("priority DESC").Find(&slots)
	response.Success(c, slots)
}

// GetSlotDefinition 获取单个槽位定义
func GetSlotDefinition(c *gin.Context) {
	id := c.Param("id")
	var slot model.SlotDefinition
	if err := postgres.Get().Select("*").First(&slot, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "槽位不存在")
		return
	}
	response.Success(c, slot)
}

// CreateSlotDefinition 创建槽位定义
func CreateSlotDefinition(c *gin.Context) {
	var slot model.SlotDefinition
	if err := c.ShouldBindJSON(&slot); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&slot).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, slot)
}

// UpdateSlotDefinition 更新槽位定义
func UpdateSlotDefinition(c *gin.Context) {
	id := c.Param("id")
	var slot model.SlotDefinition
	if err := postgres.Get().First(&slot, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "槽位不存在")
		return
	}

	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if err := postgres.Get().Model(&slot).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	response.Success(c, slot)
}

// DeleteSlotDefinition 删除槽位定义
func DeleteSlotDefinition(c *gin.Context) {
	id := c.Param("id")
	postgres.Get().Delete(&model.SlotDefinition{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetAllSlotConfigs 获取所有槽位配置（供 Python AI 服务调用）
func GetAllSlotConfigs(c *gin.Context) {
	var slots []model.SlotDefinition
	postgres.Get().Select("*").Where("status = ?", 1).Order("priority DESC").Find(&slots)
	response.Success(c, gin.H{
		"slot_definitions":  slots,
	})
}

// ========== SlotDependency CRUD ==========

// ListSlotDependencies 获取所有槽位依赖
func ListSlotDependencies(c *gin.Context) {
	var deps []model.SlotDependency
	postgres.Get().Select("*").Find(&deps)
	response.Success(c, deps)
}

// CreateSlotDependency 创建槽位依赖
func CreateSlotDependency(c *gin.Context) {
	var dep model.SlotDependency
	if err := c.ShouldBindJSON(&dep); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&dep).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, dep)
}

// DeleteSlotDependency 删除槽位依赖
func DeleteSlotDependency(c *gin.Context) {
	id := c.Param("id")
	postgres.Get().Delete(&model.SlotDependency{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}

// ========== SlotRelation CRUD ==========

// ListSlotRelations 获取所有指标-槽位关联
func ListSlotRelations(c *gin.Context) {
	var relations []model.SlotRelation
	postgres.Get().Select("*").Find(&relations)
	response.Success(c, relations)
}

// CreateSlotRelation 创建指标-槽位关联
func CreateSlotRelation(c *gin.Context) {
	var relation model.SlotRelation
	if err := c.ShouldBindJSON(&relation); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if err := postgres.Get().Create(&relation).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, relation)
}

// DeleteSlotRelation 删除指标-槽位关联
func DeleteSlotRelation(c *gin.Context) {
	id := c.Param("id")
	postgres.Get().Delete(&model.SlotRelation{}, id)
	response.SuccessWithMessage(c, "删除成功", nil)
}
