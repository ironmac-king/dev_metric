package middleware

import (
	"dev_metric/config"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

// AuthMiddleware JWT 认证中间件
func AuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 从 Header 获取 Token
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"code":    401,
				"message": "未登录或登录已过期",
			})
			c.Abort()
			return
		}

		// Bearer token
		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"code":    401,
				"message": "Token 格式错误",
			})
			c.Abort()
			return
		}

		tokenString := parts[1]
		cfg := config.Get()

		// 解析 Token
		token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
			return []byte(cfg.App.JWTSecret), nil
		})

		if err != nil || !token.Valid {
			c.JSON(http.StatusUnauthorized, gin.H{
				"code":    401,
				"message": "Token 无效或已过期",
			})
			c.Abort()
			return
		}

		// 提取 claims
		claims, ok := token.Claims.(jwt.MapClaims)
		if !ok {
			c.JSON(http.StatusUnauthorized, gin.H{
				"code":    401,
				"message": "无法解析用户信息",
			})
			c.Abort()
			return
		}

		// 设置用户上下文
		if userID, ok := claims["user_id"].(float64); ok {
			c.Set("user_id", uint(userID))
		}
		if role, ok := claims["role"].(string); ok {
			c.Set("role", role)
		}
		if deptID, ok := claims["dept_id"].(float64); ok {
			c.Set("dept_id", uint(deptID))
		}

		c.Set("claims", claims)
		c.Next()
	}
}

// OptionalAuthMiddleware 可选的认证中间件（不强制登录）
func OptionalAuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.Next()
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.Next()
			return
		}

		tokenString := parts[1]
		cfg := config.Get()

		token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
			return []byte(cfg.App.JWTSecret), nil
		})

		if err != nil || !token.Valid {
			c.Next()
			return
		}

		claims, ok := token.Claims.(jwt.MapClaims)
		if !ok {
			c.Next()
			return
		}

		if userID, ok := claims["user_id"].(float64); ok {
			c.Set("user_id", uint(userID))
		}
		if role, ok := claims["role"].(string); ok {
			c.Set("role", role)
		}
		if deptID, ok := claims["dept_id"].(float64); ok {
			c.Set("dept_id", uint(deptID))
		}

		c.Set("claims", claims)
		c.Next()
	}
}

// RequireRole 角色权限中间件
func RequireRole(roles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		role, exists := c.Get("role")
		if !exists {
			c.JSON(http.StatusForbidden, gin.H{
				"code":    403,
				"message": "无权限访问",
			})
			c.Abort()
			return
		}

		roleStr, ok := role.(string)
		if !ok {
			c.JSON(http.StatusForbidden, gin.H{
				"code":    403,
				"message": "无权限访问",
			})
			c.Abort()
			return
		}

		// 检查角色是否匹配
		for _, r := range roles {
			if r == roleStr {
				c.Next()
				return
			}
		}

		c.JSON(http.StatusForbidden, gin.H{
			"code":    403,
			"message": "无权限访问此功能",
		})
		c.Abort()
	}
}

// GetUserID 获取当前用户ID
func GetUserID(c *gin.Context) uint {
	if userID, exists := c.Get("user_id"); exists {
		if id, ok := userID.(uint); ok {
			return id
		}
	}
	return 0
}

// GetUserRole 获取当前用户角色
func GetUserRole(c *gin.Context) string {
	if role, exists := c.Get("role"); exists {
		if r, ok := role.(string); ok {
			return r
		}
	}
	return ""
}
