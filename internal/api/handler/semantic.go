package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/internal/semantic"
	"dev_metric/pkg/response"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func ListSemanticMetrics(c *gin.Context) {
	var items []model.SemanticMetric
	query := postgres.Get().Model(&model.SemanticMetric{})
	if metricCode := c.Query("metric_code"); metricCode != "" {
		query = query.Where("metric_code ILIKE ?", "%"+metricCode+"%")
	}
	if status := c.Query("status"); status != "" {
		query = query.Where("status = ?", status)
	}
	query.Order("metric_code ASC").Find(&items)
	response.Success(c, items)
}

func CreateSemanticMetric(c *gin.Context) {
	var item model.SemanticMetric
	if err := c.ShouldBindJSON(&item); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if item.Version == 0 {
		item.Version = 1
	}
	if item.Status == 0 {
		item.Status = 1
	}
	if err := postgres.Get().Create(&item).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, item)
}

func UpdateSemanticMetric(c *gin.Context) {
	updateSemanticRecord[model.SemanticMetric](c)
}

func DeleteSemanticMetric(c *gin.Context) {
	deleteSemanticRecord[model.SemanticMetric](c)
}

func ListSemanticDimensions(c *gin.Context) {
	var items []model.SemanticDimension
	query := postgres.Get().Model(&model.SemanticDimension{})
	if dimensionCode := c.Query("dimension_code"); dimensionCode != "" {
		query = query.Where("dimension_code ILIKE ?", "%"+dimensionCode+"%")
	}
	if status := c.Query("status"); status != "" {
		query = query.Where("status = ?", status)
	}
	query.Order("default_sort_priority DESC, dimension_code ASC").Find(&items)
	response.Success(c, items)
}

func CreateSemanticDimension(c *gin.Context) {
	var item model.SemanticDimension
	if err := c.ShouldBindJSON(&item); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if item.Version == 0 {
		item.Version = 1
	}
	if item.Status == 0 {
		item.Status = 1
	}
	if err := postgres.Get().Create(&item).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, item)
}

func UpdateSemanticDimension(c *gin.Context) {
	updateSemanticRecord[model.SemanticDimension](c)
}

func DeleteSemanticDimension(c *gin.Context) {
	deleteSemanticRecord[model.SemanticDimension](c)
}

func ListSemanticCapabilities(c *gin.Context) {
	var items []model.SemanticAnalysisCapability
	query := postgres.Get().Model(&model.SemanticAnalysisCapability{})
	if subjectType := c.Query("subject_type"); subjectType != "" {
		query = query.Where("subject_type = ?", subjectType)
	}
	if subjectKey := c.Query("subject_key"); subjectKey != "" {
		query = query.Where("subject_key ILIKE ?", "%"+subjectKey+"%")
	}
	query.Order("subject_type ASC, subject_key ASC").Find(&items)
	response.Success(c, items)
}

func CreateSemanticCapability(c *gin.Context) {
	var item model.SemanticAnalysisCapability
	if err := c.ShouldBindJSON(&item); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if item.Version == 0 {
		item.Version = 1
	}
	if item.Status == 0 {
		item.Status = 1
	}
	if err := postgres.Get().Create(&item).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, item)
}

func UpdateSemanticCapability(c *gin.Context) {
	updateSemanticRecord[model.SemanticAnalysisCapability](c)
}

func DeleteSemanticCapability(c *gin.Context) {
	deleteSemanticRecord[model.SemanticAnalysisCapability](c)
}

func ListSemanticPolicies(c *gin.Context) {
	var items []model.SemanticInteractionPolicy
	query := postgres.Get().Model(&model.SemanticInteractionPolicy{})
	if sceneType := c.Query("scene_type"); sceneType != "" {
		query = query.Where("scene_type = ?", sceneType)
	}
	query.Order("clarify_priority DESC, policy_key ASC").Find(&items)
	response.Success(c, items)
}

func CreateSemanticPolicy(c *gin.Context) {
	var item model.SemanticInteractionPolicy
	if err := c.ShouldBindJSON(&item); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if item.Version == 0 {
		item.Version = 1
	}
	if item.Status == 0 {
		item.Status = 1
	}
	if err := postgres.Get().Create(&item).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, item)
}

func UpdateSemanticPolicy(c *gin.Context) {
	updateSemanticRecord[model.SemanticInteractionPolicy](c)
}

func DeleteSemanticPolicy(c *gin.Context) {
	deleteSemanticRecord[model.SemanticInteractionPolicy](c)
}

func ListSemanticActions(c *gin.Context) {
	var items []model.SemanticAction
	query := postgres.Get().Model(&model.SemanticAction{})
	if sceneType := c.Query("source_scene_type"); sceneType != "" {
		query = query.Where("source_scene_type = ?", sceneType)
	}
	query.Order("priority DESC, action_code ASC").Find(&items)
	response.Success(c, items)
}

func CreateSemanticAction(c *gin.Context) {
	var item model.SemanticAction
	if err := c.ShouldBindJSON(&item); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	if item.Version == 0 {
		item.Version = 1
	}
	if item.Status == 0 {
		item.Status = 1
	}
	if err := postgres.Get().Create(&item).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建失败")
		return
	}
	response.Success(c, item)
}

func UpdateSemanticAction(c *gin.Context) {
	updateSemanticRecord[model.SemanticAction](c)
}

func DeleteSemanticAction(c *gin.Context) {
	deleteSemanticRecord[model.SemanticAction](c)
}

func ListSemanticSnapshots(c *gin.Context) {
	var items []model.SemanticSnapshot
	postgres.Get().Order("compiled_at DESC, id DESC").Find(&items)
	response.Success(c, items)
}

func ListSemanticSnapshotAudits(c *gin.Context) {
	var items []model.SemanticSnapshotAudit
	query := postgres.Get().Model(&model.SemanticSnapshotAudit{})
	if snapshotID := c.Query("snapshot_id"); snapshotID != "" {
		query = query.Where("snapshot_id = ?", snapshotID)
	}
	if eventType := c.Query("event_type"); eventType != "" {
		query = query.Where("event_type = ?", eventType)
	}
	query.Order("created_at DESC, id DESC").Find(&items)
	response.Success(c, items)
}

func GetActiveSemanticSnapshot(c *gin.Context) {
	var item model.SemanticSnapshot
	if err := postgres.Get().Where("status = ?", "active").Order("compiled_at DESC").First(&item).Error; err != nil {
		response.Error(c, response.CodeNotFound, "active snapshot 不存在")
		return
	}
	response.Success(c, item)
}

func CompileSemanticSnapshot(c *gin.Context) {
	var req struct {
		CompiledBy  string `json:"compiled_by"`
		ReleaseNote string `json:"release_note"`
	}
	_ = c.ShouldBindJSON(&req)

	db := postgres.Get()
	if db == nil {
		response.Error(c, response.CodeInternalError, "数据库未初始化")
		return
	}

	seeds, err := loadBootstrapSeedsFromDB(db)
	if err != nil {
		response.Error(c, response.CodeInternalError, "加载语义数据失败")
		return
	}
	snapshot, err := semantic.CompileSnapshot(seeds, firstNonEmpty(req.CompiledBy, "semantic-console"), firstNonEmpty(req.ReleaseNote, "manual compile"))
	if err != nil {
		response.Error(c, response.CodeInternalError, "编译快照失败")
		return
	}
	snapshot.Status = "draft"
	if err := db.Create(&snapshot).Error; err != nil {
		response.Error(c, response.CodeInternalError, "保存快照失败")
		return
	}
	_ = semantic.RecordSnapshotAudit(
		db,
		snapshot.SnapshotID,
		"compile",
		"",
		"draft",
		firstNonEmpty(req.CompiledBy, "semantic-console"),
		firstNonEmpty(req.ReleaseNote, "manual compile"),
		model.JSONMap{"version": snapshot.Version},
	)
	response.Success(c, snapshot)
}

func PublishSemanticSnapshot(c *gin.Context) {
	var req struct {
		Operator string `json:"operator"`
		Note     string `json:"note"`
	}
	_ = c.ShouldBindJSON(&req)

	snapshotID := c.Param("snapshot_id")
	if snapshotID == "" {
		response.Error(c, response.CodeBadRequest, "snapshot_id 不能为空")
		return
	}
	db := postgres.Get()
	if db == nil {
		response.Error(c, response.CodeInternalError, "数据库未初始化")
		return
	}
	if err := semantic.PublishSnapshot(db, snapshotID, firstNonEmpty(req.Operator, "semantic-console"), req.Note); err != nil {
		response.Error(c, response.CodeInternalError, "发布失败")
		return
	}
	response.SuccessWithMessage(c, "发布成功", gin.H{"snapshot_id": snapshotID})
}

func RollbackSemanticSnapshot(c *gin.Context) {
	var req struct {
		Operator string `json:"operator"`
		Note     string `json:"note"`
	}
	_ = c.ShouldBindJSON(&req)

	snapshotID := c.Param("snapshot_id")
	if snapshotID == "" {
		response.Error(c, response.CodeBadRequest, "snapshot_id 不能为空")
		return
	}
	db := postgres.Get()
	if db == nil {
		response.Error(c, response.CodeInternalError, "数据库未初始化")
		return
	}
	if err := semantic.RollbackSnapshot(db, snapshotID, firstNonEmpty(req.Operator, "semantic-console"), req.Note); err != nil {
		response.Error(c, response.CodeInternalError, "回滚失败")
		return
	}
	response.SuccessWithMessage(c, "回滚成功", gin.H{"snapshot_id": snapshotID})
}

func GetSemanticSnapshotDiff(c *gin.Context) {
	snapshotID := c.Param("snapshot_id")
	baseSnapshotID := c.Query("base_snapshot_id")
	if snapshotID == "" || baseSnapshotID == "" {
		response.Error(c, response.CodeBadRequest, "snapshot_id/base_snapshot_id 不能为空")
		return
	}

	var fromSnapshot model.SemanticSnapshot
	if err := postgres.Get().Where("snapshot_id = ?", baseSnapshotID).First(&fromSnapshot).Error; err != nil {
		response.Error(c, response.CodeNotFound, "base snapshot 不存在")
		return
	}

	var toSnapshot model.SemanticSnapshot
	if err := postgres.Get().Where("snapshot_id = ?", snapshotID).First(&toSnapshot).Error; err != nil {
		response.Error(c, response.CodeNotFound, "target snapshot 不存在")
		return
	}

	diff, err := semantic.CompareSnapshots(fromSnapshot, toSnapshot)
	if err != nil {
		response.Error(c, response.CodeInternalError, "快照对比失败")
		return
	}
	response.Success(c, diff)
}

func BootstrapSemanticData(c *gin.Context) {
	db := postgres.Get()
	if db == nil {
		response.Error(c, response.CodeInternalError, "数据库未初始化")
		return
	}
	if err := semantic.SeedSemanticBootstrap(db, "semantic-console"); err != nil {
		response.Error(c, response.CodeInternalError, "初始化失败")
		return
	}
	response.SuccessWithMessage(c, "初始化成功", gin.H{"bootstrapped_at": time.Now().UTC()})
}

func updateSemanticRecord[T any](c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	var entity T
	if err := postgres.Get().First(&entity, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "记录不存在")
		return
	}
	var updates map[string]any
	if err := c.ShouldBindJSON(&updates); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}
	updates["updated_at"] = time.Now().UTC()
	if err := postgres.Get().Model(&entity).Updates(updates).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新失败")
		return
	}
	response.Success(c, entity)
}

func deleteSemanticRecord[T any](c *gin.Context) {
	id, _ := strconv.Atoi(c.Param("id"))
	if err := postgres.Get().Delete(new(T), id).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除失败")
		return
	}
	response.SuccessWithMessage(c, "删除成功", nil)
}

func loadBootstrapSeedsFromDB(db *gorm.DB) (semantic.BootstrapSeeds, error) {
	var metrics []model.Metric
	if err := db.Find(&metrics).Error; err != nil {
		return semantic.BootstrapSeeds{}, err
	}
	var dimensionConfigs []model.DimensionConfig
	if err := db.Find(&dimensionConfigs).Error; err != nil {
		return semantic.BootstrapSeeds{}, err
	}
	var dimensionTypes []model.DimensionTypeMapping
	if err := db.Find(&dimensionTypes).Error; err != nil {
		return semantic.BootstrapSeeds{}, err
	}
	var labels []model.BusinessDimensionLabel
	if err := db.Find(&labels).Error; err != nil {
		return semantic.BootstrapSeeds{}, err
	}
	var terms []model.BusinessTerm
	if err := db.Find(&terms).Error; err != nil {
		return semantic.BootstrapSeeds{}, err
	}
	var dimensionValues []model.DimensionValueMapping
	if err := db.Where("status = ?", 1).Find(&dimensionValues).Error; err != nil {
		return semantic.BootstrapSeeds{}, err
	}
	var triggerConfigs []model.AnalysisTriggerConfig
	_ = db.Find(&triggerConfigs).Error
	var outputTemplates []model.OutputTemplate
	_ = db.Find(&outputTemplates).Error

	return semantic.BuildBootstrapSeeds(metrics, dimensionConfigs, dimensionTypes, labels, terms, triggerConfigs, outputTemplates, dimensionValues), nil
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}
