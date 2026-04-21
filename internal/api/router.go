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
		// 指标管理（需要认证）
		metrics := v1.Group("/metrics")
		metrics.Use(middleware.AuthMiddleware())
		{
			metrics.GET("", handler.ListMetrics)
			metrics.POST("", handler.CreateMetric)
			metrics.POST("/import-preview", handler.ImportPreviewMetrics)
			metrics.POST("/import-commit", handler.ImportCommitMetrics)
			metrics.POST("/import", handler.ImportMetricsFile)
			metrics.GET("/export-template", handler.ExportTemplateMetrics)
			metrics.GET("/export-sample", handler.ExportSampleMetrics)
			metrics.GET("/stats", handler.GetMetricStats)
			metrics.GET("/:id/data", handler.GetMetricData)
			metrics.GET("/:id", handler.GetMetric)
			metrics.PUT("/:id", handler.UpdateMetric)
			metrics.DELETE("/:id", handler.DeleteMetric)
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
			dashboard.GET("/metric-cards", handler.GetMetricCards)
		}

		// 反馈看板
		feedback := v1.Group("/feedback")
		{
			feedback.GET("/stats", handler.GetFeedbackStats)
			feedback.GET("/trend", handler.GetFeedbackTrend)
			feedback.GET("/list", handler.GetFeedbackList)
			feedback.GET("/by-type", handler.GetFeedbackByType)
		}

		// 智能问数 API（需要认证）
		ask := v1.Group("/ask")
		ask.Use(middleware.AuthMiddleware())
		{
			ask.POST("", handler.AskQuestion)
			ask.GET("/history", handler.GetAskHistory)
			ask.POST("/clear", handler.ClearSession)
			ask.GET("/suggest", handler.GetAskSuggest)
			ask.POST("/feedback", handler.SubmitFeedback)
			ask.POST("/drill_down", handler.DrillDownQuestion)
			ask.POST("/messages", handler.SaveMessage)
			ask.GET("/messages", handler.GetMessages)
			ask.DELETE("/messages", handler.DeleteMessages)
			ask.GET("/last-result", handler.GetLastResult)

			// Dashboard 相关
			ask.GET("/dashboard/stats", handler.GetDashboardStats)
			ask.GET("/sessions", handler.GetSessions)
			ask.PUT("/sessions/:id/star", handler.StarSession)
			ask.GET("/favorites", handler.GetFavorites)
			ask.POST("/favorites", handler.AddFavorite)
			ask.DELETE("/favorites/:id", handler.DeleteFavorite)
			ask.GET("/preferences", handler.GetPreferences)
			ask.PUT("/preferences", handler.UpdatePreferences)
			ask.GET("/recent-questions", handler.GetRecentQuestions)

			// 快捷问题管理
			ask.GET("/shortcuts", handler.GetShortcuts)
			ask.POST("/shortcuts", handler.CreateShortcut)
			ask.PUT("/shortcuts/:id", handler.UpdateShortcut)
			ask.DELETE("/shortcuts/:id", handler.DeleteShortcut)
		}

		// 问数分析 API（需要认证）
		askAnalysis := v1.Group("/ask-analysis")
		askAnalysis.Use(middleware.AuthMiddleware())

		// 决策分析 API（需要认证）
		analysis := v1.Group("/analysis")
		analysis.Use(middleware.AuthMiddleware())
		{
			analysis.POST("/analyze", handler.AnalysisQuestion)
			analysis.POST("/stream", handler.AnalysisStream)
		}
		{
			askAnalysis.POST("/logs", handler.CreateAnalysisLog)
			askAnalysis.GET("/logs", handler.GetAnalysisLogs)
			askAnalysis.GET("/logs/:id", handler.GetAnalysisLog)
			askAnalysis.DELETE("/logs/:id", handler.DeleteAnalysisLog)
			askAnalysis.DELETE("/logs", handler.DeleteAnalysisLogsBySession)
		}

		// 内部问数分析 API（不需要认证，供 Python AI 服务调用）
		internalAskAnalysis := v1.Group("/internal/ask-analysis")
		{
			internalAskAnalysis.POST("/logs", handler.CreateAnalysisLog)
		}

		// 内部智能问数 API（不需要认证，供前端调用）
		internalAsk := v1.Group("/internal/ask")
		{
			internalAsk.POST("/clear", handler.ClearSessionInternal)
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

			// 公式语法配置
			nlp.GET("/formula-syntax", handler.ListFormulaSyntaxConfigs)
			nlp.GET("/formula-syntax/enabled", handler.GetEnabledFormulaSyntaxConfigs)
			nlp.GET("/formula-syntax/:id", handler.GetFormulaSyntaxConfig)
			nlp.POST("/formula-syntax", handler.CreateFormulaSyntaxConfig)
			nlp.PUT("/formula-syntax/:id", handler.UpdateFormulaSyntaxConfig)
			nlp.DELETE("/formula-syntax/:id", handler.DeleteFormulaSyntaxConfig)

			// 向量重建 API
			nlp.POST("/intents/rebuild-embeddings", handler.RebuildIntentEmbeddings)
			nlp.POST("/metrics/rebuild-embeddings", handler.RebuildMetricEmbeddings)

			// 向量获取 API（供 Python AI 服务调用）
			nlp.GET("/vectors/intents", handler.GetIntentVectors)
			nlp.GET("/vectors/metrics", handler.GetMetricVectors)

			// Embedding 生成 API（供 Python AI 服务调用）
			nlp.POST("/generate-embeddings", handler.GenerateEmbeddings)

			// 槽位配置 API（供 Python AI 服务调用）
			nlp.GET("/slot-configs", handler.GetAllSlotConfigs)
			nlp.GET("/slots", handler.ListSlotDefinitions)
			nlp.GET("/slots/:id", handler.GetSlotDefinition)
			nlp.POST("/slots", handler.CreateSlotDefinition)
			nlp.PUT("/slots/:id", handler.UpdateSlotDefinition)
			nlp.DELETE("/slots/:id", handler.DeleteSlotDefinition)
			nlp.GET("/slot-dependencies", handler.ListSlotDependencies)
			nlp.POST("/slot-dependencies", handler.CreateSlotDependency)
			nlp.DELETE("/slot-dependencies/:id", handler.DeleteSlotDependency)
			nlp.GET("/slot-relations", handler.ListSlotRelations)
			nlp.POST("/slot-relations", handler.CreateSlotRelation)
			nlp.DELETE("/slot-relations/:id", handler.DeleteSlotRelation)
		}

		// 意图反馈
		intentFeedback := v1.Group("/feedback")
		{
			intentFeedback.GET("/intent", handler.ListIntentFeedback)
			intentFeedback.POST("/intent", handler.RecordIntentFeedback)
			intentFeedback.PUT("/intent/:id/review", handler.ReviewIntentFeedback)
		}

		// StarRocks 配置
		starrocksRoutes := v1.Group("/starrocks")
		{
			starrocksRoutes.GET("/config", handler.GetStarRocksConfig)
			starrocksRoutes.PUT("/config", handler.UpdateStarRocksConfig)
			starrocksRoutes.POST("/config/test", handler.TestStarRocksConnection)
		}

		// 通用 SQL 查询（供 AI 服务调用）
		query := v1.Group("/query")
		{
			query.POST("/execute", handler.ExecuteQuery)
		}

		// 维度配置
		dimension := v1.Group("/dimension-configs")
		{
			dimension.GET("", handler.ListDimensionConfigs)
			dimension.GET("/tables", handler.GetDimensionTables)
			dimension.POST("", handler.CreateDimensionConfig)
			dimension.PUT("/:id", handler.UpdateDimensionConfig)
			dimension.DELETE("/:id", handler.DeleteDimensionConfig)
			dimension.DELETE("/tables/:table_name", handler.DeleteDimensionTable)
		}

		// 维度类型映射（全局）
		dimensionType := v1.Group("/dimension-type-mappings")
		{
			dimensionType.GET("", handler.ListDimensionTypeMappings)
			dimensionType.GET("/search", handler.GetDimensionTypeMappingsByType)
			dimensionType.POST("", handler.CreateDimensionTypeMapping)
			dimensionType.PUT("/:id", handler.UpdateDimensionTypeMapping)
			dimensionType.DELETE("/:id", handler.DeleteDimensionTypeMapping)
		}

		// Prompt配置
		prompt := v1.Group("/prompt-configs")
		{
			prompt.GET("", handler.ListPromptConfigs)
			prompt.GET("/active", handler.GetActivePromptConfig)
			prompt.GET("/:id", handler.GetPromptConfig)
			prompt.GET("/:id/versions", handler.GetPromptConfigVersions)
			prompt.POST("", handler.CreatePromptConfig)
			prompt.PUT("/:id", handler.UpdatePromptConfig)
			prompt.DELETE("/:id", handler.DeletePromptConfig)
			prompt.POST("/:id/rollback", handler.RollbackPromptConfig)
			prompt.DELETE("/:id/version", handler.DeletePromptConfigVersion)
			prompt.POST("/generate", handler.GeneratePromptConfig) // AI 生成 Prompt
		}

		// 维度值搜索（供 AI 服务调用）
		dimensionValues := v1.Group("/dimension-values")
		{
			dimensionValues.GET("/search", handler.SearchDimensionValues)
			dimensionValues.POST("/frequency", handler.IncrementFrequency)
		}

		// 认证
		auth := v1.Group("/auth")
		{
			auth.POST("/login", handler.Login)
			auth.POST("/refresh", handler.RefreshToken)
			auth.POST("/logout", handler.Logout)
		}

		// 用户管理（需要认证+管理员）
		users := v1.Group("/users")
		users.Use(middleware.AuthMiddleware(), middleware.RequireRole("admin"))
		{
			users.GET("", handler.ListUsers)
			users.GET("/:id", handler.GetUser)
			users.POST("", handler.CreateUser)
			users.PUT("/:id", handler.UpdateUser)
			users.DELETE("/:id", handler.DeleteUser)
		}

		// 角色权限管理（需要认证+管理员）
		roles := v1.Group("/roles")
		roles.Use(middleware.AuthMiddleware(), middleware.RequireRole("admin"))
		{
			roles.GET("", handler.ListRoles)
			roles.GET("/all-menus", handler.GetAllMenus)
			roles.GET("/:name/menus", handler.GetRoleMenus)
			roles.PUT("/:name/menus", handler.UpdateRoleMenus)
			roles.POST("", handler.CreateRole)
			roles.PUT("/role/:role_id", handler.UpdateRole)
			roles.DELETE("/role/:role_id", handler.DeleteRole)
		}

		// 当前用户菜单权限（需要认证）
		v1.GET("/my-menus", handler.GetCurrentUserMenus)
	}

	// 初始化数据库
	if err := postgres.InitWithSeed(&cfg.Database); err != nil {
		log.Printf("警告: 数据库连接失败: %v", err)
	}

	return r
}
