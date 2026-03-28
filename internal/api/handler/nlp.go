package handler

import (
	"bytes"
	"encoding/json"
	"fmt"
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
	postgres.Get().Find(&templates)
	response.Success(c, templates)
}

func GetIntentTemplate(c *gin.Context) {
	id := c.Param("id")
	var tpl model.IntentTemplate
	if err := postgres.Get().First(&tpl, id).Error; err != nil {
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
	postgres.Get().Find(&templates)
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
func GetAllNLPTemplates(c *gin.Context) {
	var intentTemplates []model.IntentTemplate
	var sqlTemplates []model.SQLTemplate

	postgres.Get().Where("status = ?", 1).Find(&intentTemplates)
	postgres.Get().Where("status = ?", 1).Find(&sqlTemplates)

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

	count := 0
	for _, tpl := range templates {
		// 构建待向量化的文本：pattern + intent
		texts := strings.Split(tpl.Patterns, ",")
		for _, text := range texts {
			text = strings.TrimSpace(text)
			if text == "" {
				continue
			}
			// 调用 AI 服务生成向量
			embedding, err := generateEmbedding(text)
			if err != nil {
				continue
			}

			// 存储向量
			embeddingJSON, _ := json.Marshal(embedding)
			emb := model.IntentEmbedding{
				IntentID:   tpl.ID,
				IntentType: tpl.Intent,
				Text:       text,
				Embedding:  string(embeddingJSON),
			}

			// 使用 upsert
			postgres.Get().Where("intent_id = ? AND text = ?", tpl.ID, text).
				Assign(emb).
				FirstOrCreate(&model.IntentEmbedding{})
			count++
		}
	}

	response.Success(c, gin.H{"success": true, "count": count})
}

// RebuildMetricEmbeddings 重新生成所有指标向量
func RebuildMetricEmbeddings(c *gin.Context) {
	// 获取所有指标
	var metrics []model.Metric
	postgres.Get().Find(&metrics)

	count := 0
	for _, m := range metrics {
		// 构建待向量化的文本：名称 + 英文名 + 业务定义
		texts := []string{m.Name}
		if m.NameEn != "" {
			texts = append(texts, m.NameEn)
		}
		if m.BusinessDefinition != "" {
			texts = append(texts, m.BusinessDefinition)
		}
		combinedText := strings.Join(texts, " ")

		// 调用 AI 服务生成向量
		embedding, err := generateEmbedding(combinedText)
		if err != nil {
			continue
		}

		// 存储向量
		embeddingJSON, _ := json.Marshal(embedding)
		emb := model.MetricEmbedding{
			MetricID:   m.ID,
			MetricCode: m.MetricCode,
			Text:       combinedText,
			Embedding:  string(embeddingJSON),
		}

		// 使用 upsert
		postgres.Get().Where("metric_id = ?", m.ID).
			Assign(emb).
			FirstOrCreate(&model.MetricEmbedding{})
		count++
	}

	response.Success(c, gin.H{"success": true, "count": count})
}

// generateEmbedding 调用 AI 服务生成向量
func generateEmbedding(text string) ([]float64, error) {
	apiURL := "https://dashscope.aliyuncs.com/compatible-mode/text-embedding/text-embedding-v2"
	apiKey := os.Getenv("DASHSCOPE_API_KEY") // 需要在环境变量中配置阿里云百炼 API Key

	reqBody := map[string]interface{}{
		"model": "text-embedding-v2",
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

	output := result["output"].(map[string]interface{})
	embedding := output["embedding"].([]interface{})
	resultVec := make([]float64, len(embedding))
	for i, v := range embedding {
		resultVec[i] = v.(float64)
	}

	return resultVec, nil
}
