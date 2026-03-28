package api

import (
	"dev_metric/config"
	"dev_metric/internal/api/handler"
	"dev_metric/internal/api/middleware"
	"dev_metric/internal/repository/postgres"
	"log"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
)

func SetupRouter(cfg *config.Config) *gin.Engine {
	r := gin.Default()

	// CORS 配置
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Authorization"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
	}))

	// 中间件
	r.Use(middleware.SecurityMiddleware())
	r.Use(middleware.TraceMiddleware())
	r.Use(middleware.AuditMiddleware())

	// 健康检查
	r.GET("/health", handler.HealthCheck)
	r.GET("/health/ready", handler.ReadyCheck)
	r.GET("/health/live", handler.LiveCheck)

	// API v1
	v1 := r.Group("/api/v1")
	{
		// 指标管理
		metrics := v1.Group("/metrics")
		{
			metrics.GET("", handler.ListMetrics)
			metrics.GET("/:id", handler.GetMetric)
			metrics.POST("", handler.CreateMetric)
			metrics.PUT("/:id", handler.UpdateMetric)
			metrics.DELETE("/:id", handler.DeleteMetric)
			metrics.GET("/:id/data", handler.GetMetricData)
			metrics.POST("/import", handler.ImportMetrics)
		}

		// 告警规则
		alerts := v1.Group("/alerts")
		{
			alerts.GET("", handler.ListAlertRules)
			alerts.POST("", handler.CreateAlertRule)
			alerts.PUT("/:id", handler.UpdateAlertRule)
			alerts.DELETE("/:id", handler.DeleteAlertRule)
			alerts.GET("/:id/history", handler.GetAlertHistory)
		}

		// 仪表盘
		dashboard := v1.Group("/dashboard")
		{
			dashboard.GET("/summary", handler.GetDashboardSummary)
			dashboard.GET("/charts", handler.GetDashboardCharts)
		}

		// 反馈看板
		feedback := v1.Group("/feedback")
		{
			feedback.GET("/stats", handler.GetFeedbackStats)
			feedback.GET("/trend", handler.GetFeedbackTrend)
			feedback.GET("/list", handler.GetFeedbackList)
			feedback.GET("/by-type", handler.GetFeedbackByType)
		}

		// 智能问数 API
		ask := v1.Group("/ask")
		{
			ask.POST("", handler.AskQuestion)
			ask.GET("/history", handler.GetAskHistory)
			ask.POST("/clear", handler.ClearSession)
			ask.GET("/suggest", handler.GetAskSuggest)
			ask.POST("/feedback", handler.SubmitFeedback)
		}

		// 指标元数据 API（供 AI 服务调用）
		metadata := v1.Group("/metadata")
		{
			metadata.GET("/metrics", handler.GetAllMetrics)
			metadata.GET("/metrics/:id", handler.GetMetricMetadata)
			metadata.GET("/dimensions", handler.GetAllDimensions)
			metadata.GET("/terms", handler.GetAllTerms)
			metadata.POST("/terms", handler.CreateTerm)
			metadata.PUT("/terms/:id", handler.UpdateTerm)
			metadata.DELETE("/terms/:id", handler.DeleteTerm)
		}

		// LLM 配置管理
		llm := v1.Group("/llm")
		{
			llm.GET("/configs", handler.ListLLMConfigs)
			llm.GET("/configs/:id", handler.GetLLMConfig)
			llm.POST("/configs", handler.CreateLLMConfig)
			llm.PUT("/configs/:id", handler.UpdateLLMConfig)
			llm.DELETE("/configs/:id", handler.DeleteLLMConfig)
			llm.PUT("/configs/:id/default", handler.SetDefaultLLM)
			llm.POST("/configs/test", handler.TestLLMConnection)
		}

		// NLP 模板管理（意图、SQL模板）
		nlp := v1.Group("/nlp")
		{
			nlp.GET("/templates", handler.GetAllNLPTemplates)
			nlp.GET("/intents", handler.ListIntentTemplates)
			nlp.GET("/intents/:id", handler.GetIntentTemplate)
			nlp.POST("/intents", handler.CreateIntentTemplate)
			nlp.PUT("/intents/:id", handler.UpdateIntentTemplate)
			nlp.DELETE("/intents/:id", handler.DeleteIntentTemplate)
			nlp.GET("/sql-templates", handler.ListSQLTemplates)
			nlp.GET("/sql-templates/:id", handler.GetSQLTemplate)
			nlp.POST("/sql-templates", handler.CreateSQLTemplate)
			nlp.PUT("/sql-templates/:id", handler.UpdateSQLTemplate)
			nlp.DELETE("/sql-templates/:id", handler.DeleteSQLTemplate)

			// 向量重建 API
			nlp.POST("/intents/rebuild-embeddings", handler.RebuildIntentEmbeddings)
			nlp.POST("/metrics/rebuild-embeddings", handler.RebuildMetricEmbeddings)
		}

		// 认证
		auth := v1.Group("/auth")
		{
			auth.POST("/login", handler.Login)
			auth.POST("/refresh", handler.RefreshToken)
			auth.POST("/logout", handler.Logout)
		}
	}

	// 初始化数据库
	if err := postgres.Init(&cfg.Database); err != nil {
		log.Printf("警告: 数据库连接失败: %v", err)
	}

	return r
}
