package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
)

// GetShortcuts 获取快捷问题列表
func GetShortcuts(c *gin.Context) {
	db := postgres.Get()

	var shortcuts []model.AskShortcutQuestion
	db.Where("status = ?", 1).Order("sort_order ASC").Find(&shortcuts)

	// 如果没有数据，返回默认快捷问题
	if len(shortcuts) == 0 {
		shortcuts = []model.AskShortcutQuestion{
			{ID: 1, QuestionText: "广告转化率是多少？", Icon: "📊", SortOrder: 1, Status: 1},
			{ID: 2, QuestionText: "今日 DAU 是多少？", Icon: "📊", SortOrder: 2, Status: 1},
			{ID: 3, QuestionText: "本周 GMV 趋势如何？", Icon: "📈", SortOrder: 3, Status: 1},
			{ID: 4, QuestionText: "业务口径是什么？", Icon: "📝", SortOrder: 4, Status: 1},
		}
	}

	response.Success(c, shortcuts)
}

// CreateShortcut 创建快捷问题
func CreateShortcut(c *gin.Context) {
	db := postgres.Get()

	var req struct {
		QuestionText string `json:"question_text" binding:"required"`
		Icon         string `json:"icon"`
		SortOrder    int    `json:"sort_order"`
		Status       int16  `json:"status"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, "参数错误: "+err.Error())
		return
	}

	if req.Icon == "" {
		req.Icon = "📊"
	}
	if req.SortOrder == 0 {
		req.SortOrder = 10
	}
	if req.Status == 0 {
		req.Status = 1
	}

	shortcut := model.AskShortcutQuestion{
		QuestionText: req.QuestionText,
		Icon:         req.Icon,
		SortOrder:    req.SortOrder,
		Status:       req.Status,
	}

	db.Create(&shortcut)
	response.Success(c, shortcut)
}

// UpdateShortcut 更新快捷问题
func UpdateShortcut(c *gin.Context) {
	db := postgres.Get()
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		response.Error(c, http.StatusBadRequest, "无效的ID")
		return
	}

	var req struct {
		QuestionText string `json:"question_text"`
		Icon         string `json:"icon"`
		SortOrder    *int   `json:"sort_order"`
		Status       *int16  `json:"status"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, "参数错误")
		return
	}

	var shortcut model.AskShortcutQuestion
	if err := db.First(&shortcut, id).Error; err != nil {
		response.Error(c, http.StatusNotFound, "快捷问题不存在")
		return
	}

	if req.QuestionText != "" {
		shortcut.QuestionText = req.QuestionText
	}
	if req.Icon != "" {
		shortcut.Icon = req.Icon
	}
	if req.SortOrder != nil {
		shortcut.SortOrder = *req.SortOrder
	}
	if req.Status != nil {
		shortcut.Status = *req.Status
	}

	db.Save(&shortcut)
	response.Success(c, shortcut)
}

// DeleteShortcut 删除快捷问题
func DeleteShortcut(c *gin.Context) {
	db := postgres.Get()
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		response.Error(c, http.StatusBadRequest, "无效的ID")
		return
	}

	if err := db.Delete(&model.AskShortcutQuestion{}, id).Error; err != nil {
		response.Error(c, http.StatusInternalServerError, "删除失败")
		return
	}

	response.Success(c, nil)
}
