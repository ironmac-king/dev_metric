package handler

import (
	"dev_metric/internal/repository/starrocks"
	"dev_metric/pkg/response"
	"fmt"
	"strings"

	"github.com/gin-gonic/gin"
)

// GetProductDetails 通过 SKU 查询产品详情
func GetProductDetails(c *gin.Context) {
	var req struct {
		SKUs []string `json:"skus" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, response.CodeBadRequest, "参数错误：skus 不能为空")
		return
	}

	if len(req.SKUs) == 0 || len(req.SKUs) > 50 {
		response.Error(c, response.CodeBadRequest, "skus 数量需在 1-50 之间")
		return
	}

	// 构建 IN 子句参数
	placeholders := make([]string, len(req.SKUs))
	args := make([]interface{}, len(req.SKUs))
	for i, sku := range req.SKUs {
		placeholders[i] = "?"
		args[i] = sku
	}

	sqlStr := fmt.Sprintf(`SELECT
  sku,
  materialname,
  groupone,
  grouptwo,
  groupthere,
  model,
  picture_localurl
FROM ads.dim_kingdee_material
WHERE sku IN (%s)
  AND materialstatus = '产成品'
  AND orgnizationid = 12352676`, strings.Join(placeholders, ","))

	rows, err := starrocks.QueryRawWithArgs(sqlStr, args...)
	if err != nil {
		response.Error(c, response.CodeInternalError, fmt.Sprintf("查询失败: %v", err))
		return
	}

	// 转换结果，替换图片路径
	type ProductInfo struct {
		SKU         string `json:"sku"`
		ProductName string `json:"product_name"`
		CategoryL1  string `json:"category_l1"`
		CategoryL2  string `json:"category_l2"`
		CategoryL3  string `json:"category_l3"`
		BigCode     string `json:"big_code"`
		ImageURL    string `json:"image_url"`
	}

	products := make([]ProductInfo, 0, len(rows))
	for _, row := range rows {
		sku, _ := row["sku"].(string)
		name, _ := row["materialname"].(string)
		l1, _ := row["groupone"].(string)
		l2, _ := row["grouptwo"].(string)
		l3, _ := row["groupthere"].(string)
		model, _ := row["model"].(string)
		imgPath, _ := row["picture_localurl"].(string)

		imageURL := strings.Replace(imgPath,
			"/home/hadoop178/sku_pic",
			"http://bi.ugreengroup.com:48066/webroot/Picture/SKU_PICTURE", 1)

		products = append(products, ProductInfo{
			SKU:         sku,
			ProductName: name,
			CategoryL1:  l1,
			CategoryL2:  l2,
			CategoryL3:  l3,
			BigCode:     model,
			ImageURL:    imageURL,
		})
	}

	response.Success(c, products)
}
