package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"strconv"

	"github.com/gin-gonic/gin"
)

// ListRoles 获取所有角色
func ListRoles(c *gin.Context) {
	var roles []model.Role
	if err := postgres.Get().Find(&roles).Error; err != nil {
		response.Error(c, response.CodeInternalError, "获取角色列表失败")
		return
	}
	response.Success(c, roles)
}

// GetRoleMenus 获取角色的菜单权限
func GetRoleMenus(c *gin.Context) {
	roleName := c.Param("name")
	if roleName == "" {
		response.Error(c, response.CodeBadRequest, "角色名称不能为空")
		return
	}

	var menus []model.RoleMenu
	if err := postgres.Get().Where("role_name = ?", roleName).Order("sort_order").Find(&menus).Error; err != nil {
		response.Error(c, response.CodeInternalError, "获取权限失败")
		return
	}

	// 如果没有权限记录，返回空数组而不是错误
	response.Success(c, menus)
}

// UpdateRoleMenus 更新角色的菜单权限
func UpdateRoleMenus(c *gin.Context) {
	roleName := c.Param("name")
	if roleName == "" {
		response.Error(c, response.CodeBadRequest, "角色名称不能为空")
		return
	}

	var req struct {
		Menus []struct {
			MenuPath  string `json:"menu_path"`
			MenuName  string `json:"menu_name"`
			ParentPath string `json:"parent_path"`
			SortOrder int    `json:"sort_order"`
		} `json:"menus"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 开启事务
	tx := postgres.Get().Begin()
	defer func() {
		if r := recover(); r != nil {
			tx.Rollback()
		}
	}()

	// 删除该角色的所有权限
	if err := tx.Where("role_name = ?", roleName).Delete(&model.RoleMenu{}).Error; err != nil {
		tx.Rollback()
		response.Error(c, response.CodeInternalError, "删除旧权限失败")
		return
	}

	// 添加新权限
	for _, m := range req.Menus {
		menu := &model.RoleMenu{
			RoleName:   roleName,
			MenuPath:   m.MenuPath,
			MenuName:   m.MenuName,
			ParentPath: m.ParentPath,
			SortOrder:  m.SortOrder,
		}
		if err := tx.Create(menu).Error; err != nil {
			tx.Rollback()
			response.Error(c, response.CodeInternalError, "保存权限失败")
			return
		}
	}

	tx.Commit()
	response.SuccessWithMessage(c, "权限更新成功", nil)
}

// CreateRole 创建角色
func CreateRole(c *gin.Context) {
	var req struct {
		Name        string `json:"name" binding:"required"`
		DisplayName string `json:"display_name"`
		Description string `json:"description"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 检查是否已存在
	var count int64
	postgres.Get().Model(&model.Role{}).Where("name = ?", req.Name).Count(&count)
	if count > 0 {
		response.Error(c, response.CodeBadRequest, "角色已存在")
		return
	}

	role := &model.Role{
		Name:        req.Name,
		DisplayName: req.DisplayName,
		Description: req.Description,
	}

	if err := postgres.Get().Create(role).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建角色失败")
		return
	}

	response.Success(c, role)
}

// UpdateRole 更新角色
func UpdateRole(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("role_id"))
	if err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	var role model.Role
	if err := postgres.Get().First(&role, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "角色不存在")
		return
	}

	var req struct {
		DisplayName string `json:"display_name"`
		Description string `json:"description"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	if req.DisplayName != "" {
		role.DisplayName = req.DisplayName
	}
	if req.Description != "" {
		role.Description = req.Description
	}

	if err := postgres.Get().Save(&role).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新角色失败")
		return
	}

	response.Success(c, role)
}

// DeleteRole 删除角色
func DeleteRole(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("role_id"))
	if err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 不能删除 admin
	var role model.Role
	if err := postgres.Get().First(&role, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "角色不存在")
		return
	}

	if role.Name == "admin" {
		response.Error(c, response.CodeBadRequest, "不能删除管理员角色")
		return
	}

	// 删除角色的权限
	postgres.Get().Where("role_name = ?", role.Name).Delete(&model.RoleMenu{})

	// 删除角色
	if err := postgres.Get().Delete(&role).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除角色失败")
		return
	}

	response.SuccessWithMessage(c, "删除成功", nil)
}

// GetAllMenus 获取所有可选菜单（用于权限配置）
func GetAllMenus(c *gin.Context) {
	// 返回所有可配置的菜单项
	menus := []map[string]interface{}{
		// 工作台
		{"path": "/dashboard", "name": "Dashboard", "group": "工作台"},
		{"path": "/metrics", "name": "指标管理", "group": "工作台"},
		{"path": "/alerts", "name": "告警配置", "group": "工作台"},
		// 智能分析
		{"path": "/ai-assistant", "name": "AI 问数", "group": "智能分析"},
		{"path": "/llm-ask", "name": "LLM.V1", "group": "智能分析"},
		{"path": "/ask-analysis", "name": "问数分析", "group": "智能分析"},
		{"path": "/analysis", "name": "决策分析", "group": "智能分析"},
		// 系统配置
		{"path": "/llm-config", "name": "LLM 配置", "group": "系统配置"},
		{"path": "/nlp-config", "name": "意图配置", "group": "系统配置"},
		{"path": "/starrocks-config", "name": "数据源配置", "group": "系统配置"},
		{"path": "/dimension-config", "name": "维度配置", "group": "系统配置"},
		{"path": "/prompt-config", "name": "Prompt配置", "group": "系统配置"},
		{"path": "/user-management", "name": "用户管理", "group": "系统配置"},
	}
	response.Success(c, menus)
}

// GetCurrentUserMenus 获取当前用户的菜单权限
func GetCurrentUserMenus(c *gin.Context) {
	role, _ := c.Get("role")
	roleName, _ := role.(string)

	if roleName == "" {
		roleName = "user"
	}

	var menus []model.RoleMenu
	if err := postgres.Get().Where("role_name = ?", roleName).Order("sort_order").Find(&menus).Error; err != nil {
		response.Error(c, response.CodeInternalError, "获取权限失败")
		return
	}

	// 如果没有配置，返回该角色的默认权限
	if len(menus) == 0 {
		// 根据角色名返回默认菜单
		defaultMenus := getDefaultMenusByRole(roleName)
		response.Success(c, defaultMenus)
		return
	}

	paths := make([]string, len(menus))
	for i, m := range menus {
		paths[i] = m.MenuPath
	}

	response.Success(c, paths)
}

func getDefaultMenusByRole(roleName string) []string {
	switch roleName {
	case "admin":
		return []string{
			"/dashboard", "/metrics", "/alerts",
			"/ai-assistant", "/llm-ask", "/ask-analysis", "/analysis",
			"/llm-config", "/nlp-config", "/starrocks-config", "/dimension-config", "/prompt-config", "/user-management",
		}
	case "analyst":
		return []string{
			"/dashboard", "/metrics", "/alerts",
			"/ai-assistant", "/llm-ask", "/ask-analysis", "/analysis",
		}
	case "user":
		return []string{
			"/dashboard", "/llm-ask", "/analysis",
		}
	default:
		return []string{"/dashboard"}
	}
}
