package handler

import (
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"strconv"

	"github.com/gin-gonic/gin"
)

// ListUsers 获取用户列表
func ListUsers(c *gin.Context) {
	var users []model.User
	if err := postgres.Get().Find(&users).Error; err != nil {
		response.Error(c, response.CodeInternalError, "获取用户列表失败")
		return
	}

	// 脱敏处理，不返回密码哈希
	var result []model.User
	for _, u := range users {
		u.PasswordHash = ""
		result = append(result, u)
	}

	response.Success(c, result)
}

// GetUser 获取单个用户
func GetUser(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	var user model.User
	if err := postgres.Get().First(&user, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "用户不存在")
		return
	}

	user.PasswordHash = ""
	response.Success(c, user)
}

// CreateUser 创建用户
func CreateUser(c *gin.Context) {
	var req struct {
		Username string `json:"username" binding:"required"`
		Password string `json:"password" binding:"required"`
		Dept     string `json:"dept"`
		DeptID   int    `json:"dept_id"`
		Role     string `json:"role" binding:"required"`
		DataFilter string `json:"data_filter"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 检查用户名是否已存在
	var count int64
	postgres.Get().Model(&model.User{}).Where("username = ?", req.Username).Count(&count)
	if count > 0 {
		response.Error(c, response.CodeBadRequest, "用户名已存在")
		return
	}

	// 密码哈希
	hash, err := HashPassword(req.Password)
	if err != nil {
		response.Error(c, response.CodeInternalError, "密码加密失败")
		return
	}

	user := &model.User{
		Username:     req.Username,
		PasswordHash: hash,
		Dept:         req.Dept,
		DeptID:       req.DeptID,
		Role:         req.Role,
		DataFilter:   req.DataFilter,
		Status:       1,
	}

	if err := postgres.Get().Create(user).Error; err != nil {
		response.Error(c, response.CodeInternalError, "创建用户失败")
		return
	}

	user.PasswordHash = ""
	response.Success(c, user)
}

// UpdateUser 更新用户
func UpdateUser(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	var user model.User
	if err := postgres.Get().First(&user, id).Error; err != nil {
		response.Error(c, response.CodeNotFound, "用户不存在")
		return
	}

	var req struct {
		Username   string `json:"username"`
		Password   string `json:"password"`
		Dept       string `json:"dept"`
		DeptID     int    `json:"dept_id"`
		Role       string `json:"role"`
		DataFilter string `json:"data_filter"`
		Status     int16  `json:"status"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 更新字段
	if req.Username != "" {
		// 检查用户名是否被其他用户占用
		var count int64
		postgres.Get().Model(&model.User{}).Where("username = ? AND id != ?", req.Username, id).Count(&count)
		if count > 0 {
			response.Error(c, response.CodeBadRequest, "用户名已存在")
			return
		}
		user.Username = req.Username
	}

	if req.Password != "" {
		hash, err := HashPassword(req.Password)
		if err != nil {
			response.Error(c, response.CodeInternalError, "密码加密失败")
			return
		}
		user.PasswordHash = hash
	}

	if req.Dept != "" {
		user.Dept = req.Dept
	}
	if req.DeptID != 0 {
		user.DeptID = req.DeptID
	}
	if req.Role != "" {
		user.Role = req.Role
	}
	if req.DataFilter != "" || req.DataFilter == "" {
		user.DataFilter = req.DataFilter
	}
	if req.Status != 0 {
		user.Status = req.Status
	}

	if err := postgres.Get().Save(&user).Error; err != nil {
		response.Error(c, response.CodeInternalError, "更新用户失败")
		return
	}

	user.PasswordHash = ""
	response.Success(c, user)
}

// DeleteUser 删除用户
func DeleteUser(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	// 不能删除自己
	currentUserID := GetUserIDFromContext(c)
	if uint(id) == currentUserID {
		response.Error(c, response.CodeBadRequest, "不能删除当前登录用户")
		return
	}

	if err := postgres.Get().Delete(&model.User{}, id).Error; err != nil {
		response.Error(c, response.CodeInternalError, "删除用户失败")
		return
	}

	response.SuccessWithMessage(c, "删除成功", nil)
}
