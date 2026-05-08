package model

// BusinessDimensionLabel 业务维度标签翻译
type BusinessDimensionLabel struct {
	ID            uint   `json:"id" gorm:"primaryKey"`
	DimensionType string `json:"dimension_type" gorm:"size:64;not null"`
	RawValue     string `json:"raw_value" gorm:"size:128;not null"`
	DisplayName  string `json:"display_name" gorm:"size:128;not null"`
	Emoji        string `json:"emoji" gorm:"size:16"`
	PriorityTag  string `json:"priority_tag" gorm:"size:16"`
}

func (BusinessDimensionLabel) TableName() string {
	return "business_dimension_labels"
}
