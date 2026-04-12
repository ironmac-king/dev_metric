package model

import (
	"time"
)

type Role struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	Name        string    `json:"name" gorm:"size:32;uniqueIndex"`
	DisplayName string    `json:"display_name" gorm:"size:64"`
	Description string    `json:"description" gorm:"type:text"`
	CreatedAt  time.Time `json:"created_at"`
}

func (Role) TableName() string {
	return "roles"
}

type RoleMenu struct {
	ID         uint      `json:"id" gorm:"primaryKey"`
	RoleName   string    `json:"role_name" gorm:"size:32;index"`
	MenuPath   string    `json:"menu_path" gorm:"size:128"`
	MenuName   string    `json:"menu_name" gorm:"size:64"`
	ParentPath string    `json:"parent_path" gorm:"size:128"`
	SortOrder  int       `json:"sort_order" gorm:"default:0"`
}

func (RoleMenu) TableName() string {
	return "role_menus"
}
