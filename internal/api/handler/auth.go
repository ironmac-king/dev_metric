package handler

import (
	"dev_metric/config"
	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"
	"dev_metric/pkg/response"
	"errors"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
)

type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

type LoginResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int    `json:"expires_in"`
	User         UserInfo `json:"user"`
}

type UserInfo struct {
	ID       uint   `json:"id"`
	Username string `json:"username"`
	Dept     string `json:"dept"`
	Role     string `json:"role"`
}

// Login 用户登录
func Login(c *gin.Context) {
	var req LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	cfg := config.Get()

	var user model.User
	if err := postgres.Get().Where("username = ?", req.Username).First(&user).Error; err != nil {
		response.Error(c, response.CodeUnauthorized, "用户名或密码错误")
		return
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
		response.Error(c, response.CodeUnauthorized, "用户名或密码错误")
		return
	}

	// 生成 JWT
	accessToken, err := generateAccessToken(&user, cfg.App.JWTExpire)
	if err != nil {
		response.Error(c, response.CodeInternalError, "生成令牌失败")
		return
	}

	refreshToken, err := generateRefreshToken(&user, cfg.App.RefreshExpire)
	if err != nil {
		response.Error(c, response.CodeInternalError, "生成令牌失败")
		return
	}

	response.Success(c, LoginResponse{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		ExpiresIn:    cfg.App.JWTExpire,
		User: UserInfo{
			ID:       user.ID,
			Username: user.Username,
			Dept:     user.Dept,
			Role:     user.Role,
		},
	})
}

// RefreshToken 刷新令牌
func RefreshToken(c *gin.Context) {
	var req struct {
		RefreshToken string `json:"refresh_token" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误")
		return
	}

	cfg := config.Get()

	// 解析 refresh token
	token, err := jwt.Parse(req.RefreshToken, func(token *jwt.Token) (interface{}, error) {
		return []byte(cfg.App.JWTSecret), nil
	})

	if err != nil || !token.Valid {
		response.Error(c, response.CodeUnauthorized, "令牌无效")
		return
	}

	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		response.Error(c, response.CodeUnauthorized, "令牌解析失败")
		return
	}

	// 检查是否在黑名单
	jti, ok := claims["jti"].(string)
	if !ok {
		response.Error(c, response.CodeUnauthorized, "令牌无效")
		return
	}
	var count int64
	postgres.Get().Model(&model.RefreshTokenBlacklist{}).Where("token_jti = ?", jti).Count(&count)
	if count > 0 {
		response.Error(c, response.CodeUnauthorized, "令牌已失效")
		return
	}

	// 获取用户
	var user model.User
	if err := postgres.Get().First(&user, claims["user_id"]).Error; err != nil {
		response.Error(c, response.CodeUnauthorized, "用户不存在")
		return
	}

	// 生成新令牌
	accessToken, err := generateAccessToken(&user, cfg.App.JWTExpire)
	if err != nil {
		response.Error(c, 500, "生成令牌失败")
		return
	}
	newRefreshToken, err := generateRefreshToken(&user, cfg.App.RefreshExpire)
	if err != nil {
		response.Error(c, 500, "生成令牌失败")
		return
	}

	// 将旧 token 加入黑名单
	expValue, ok := claims["exp"].(float64)
	if !ok {
		response.Error(c, response.CodeUnauthorized, "令牌无效")
		return
	}
	postgres.Get().Create(&model.RefreshTokenBlacklist{
		TokenJTI:  jti,
		RevokedAt: time.Now(),
		ExpiresAt: time.Unix(int64(expValue), 0),
	})

	response.Success(c, gin.H{
		"access_token":  accessToken,
		"refresh_token": newRefreshToken,
		"expires_in":    cfg.App.JWTExpire,
	})
}

// Logout 用户登出
func Logout(c *gin.Context) {
	// 将 refresh token 加入黑名单
	var req struct {
		RefreshToken string `json:"refresh_token"`
	}
	c.ShouldBindJSON(&req)

	if req.RefreshToken != "" {
		token, err := jwt.Parse(req.RefreshToken, nil)
		if err != nil || token == nil {
			// Token 解析失败，忽略
		} else if claims, ok := token.Claims.(jwt.MapClaims); ok {
			if jti, ok := claims["jti"].(string); ok {
				if exp, ok := claims["exp"].(float64); ok {
					postgres.Get().Create(&model.RefreshTokenBlacklist{
						TokenJTI:  jti,
						RevokedAt: time.Now(),
						ExpiresAt: time.Unix(int64(exp), 0),
					})
				}
			}
		}
	}

	response.SuccessWithMessage(c, "登出成功", nil)
}

func generateAccessToken(user *model.User, expire int) (string, error) {
	cfg := config.Get()
	return jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"user_id": user.ID,
		"dept_id": user.DeptID,
		"role":    user.Role,
		"exp":     time.Now().Add(time.Duration(expire) * time.Second).Unix(),
		"iat":     time.Now().Unix(),
	}).SignedString([]byte(cfg.App.JWTSecret))
}

func generateRefreshToken(user *model.User, expire int) (string, error) {
	cfg := config.Get()
	return jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"user_id": user.ID,
		"jti":     user.Username + "-" + time.Now().Format("20060102150405"),
		"exp":     time.Now().Add(time.Duration(expire) * time.Second).Unix(),
		"iat":     time.Now().Unix(),
	}).SignedString([]byte(cfg.App.JWTSecret))
}

// HashPassword 密码哈希（供创建用户使用）
func HashPassword(password string) (string, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return "", err
	}
	return string(hash), nil
}

// GetClaims 从 context 获取用户claims
func GetClaims(c *gin.Context) (jwt.MapClaims, error) {
	claims, exists := c.Get("claims")
	if !exists {
		return nil, errors.New("未获取到用户信息")
	}
	return claims.(jwt.MapClaims), nil
}

// getUserID 从 gin.Context 获取当前用户ID
// 如果用户未登录，返回 0
func getUserID(c *gin.Context) uint {
	if userID, exists := c.Get("user_id"); exists {
		if id, ok := userID.(uint); ok {
			return id
		}
	}
	return 0
}
