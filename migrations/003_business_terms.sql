-- 业务术语补充
-- ASIN、SKU 等常见电商术语

-- 插入 ASIN 术语
INSERT INTO business_terms (term, metric_ids, description) VALUES
('ASIN', NULL, 'Amazon Standard Identification Number，亚马逊标准识别号。亚马逊平台上每个商品的唯一标识符，类似于其他平台的SKU。由10个字母和数字组成，用于在亚马逊上唯一标识和搜索商品。'),
('SKU', ARRAY[(
    SELECT id FROM metrics WHERE metric_code = 'SPI-05-009'
)], 'Stock Keeping Unit，库存量单位。是电商系统中用于标识商品的内部编码，亚马逊的SKU是商家自己设置的商品编号，用于库存管理和订单处理。ASIN是亚马逊给的，SKU是商家自己设置的。'),
('FBA', NULL, 'Fulfillment by Amazon，亚马逊物流。由亚马逊提供仓储、包装、配送服务的物流模式。商家将商品发送到亚马逊仓库，订单生成后由亚马逊完成打包发货。'),
('ACOS', NULL, 'Advertising Cost of Sales，广告销售成本比。计算公式：ACOS = 广告花费 / 广告带来的销售额。是衡量亚马逊广告投放效率的关键指标，ACOS越低说明广告效率越高。'),
('ROAS', NULL, 'Return on Advertising Spend，广告支出回报率。计算公式：ROAS = 广告带来的销售额 / 广告花费。与ACOS类似，但表达方式不同，ROAS越高说明广告效果越好。'),
('CTR', NULL, 'Click Through Rate，点击率。计算公式：CTR = 点击次数 / 展示次数。衡量广告或搜索结果吸引力的指标。'),
('CVR', NULL, 'Conversion Rate，转化率。计算公式：CVR = 订单数 / 点击次数。衡量流量转化为订单的效率。')
ON CONFLICT (term) DO UPDATE SET
    description = EXCLUDED.description;
