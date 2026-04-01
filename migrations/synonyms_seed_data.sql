-- 业务术语同义词种子数据
-- 基于电商/零售行业沉淀话术生成
-- 2026-04-02

-- =============================================
-- 流量类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('页面访问量', ARRAY['PV', '访问量', '浏览量', '页面浏览', '页面pv', '网页浏览量'], 'Page Views'),
('访客数', ARRAY['UV', '独立访客', '去重访客', '独立访问人数', '访客'], 'Unique Visitors'),
('曝光量', ARRAY['Impressions', '展现量', '展示量', '曝光'], 'Impressions'),
('点击量', ARRAY['Clicks', '点击次数', '点击'], 'Clicks'),
('会话量', ARRAY['Sessions', '会话数', '访问次数'], 'Sessions')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

INSERT INTO business_terms (term, synonyms, description) VALUES
('会话量-网页端', ARRAY['Web会话', '网页会话', '网站会话', '网页端会话'], 'Web Sessions'),
('会话量-APP端', ARRAY['APP会话', '移动端会话', 'APP端会话'], 'APP Sessions'),
('会话量-B2B', ARRAY['B2B会话', '企业会话'], 'B2B Sessions'),
('会话量-APP-B2B', ARRAY['B2B APP会话', '企业APP会话'], 'B2B APP Sessions')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 页面访问类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('页面访问量-网页端', ARRAY['Web PV', '网页PV', '网站访问量', '网页访问'], 'Web Page Views'),
('页面访问量-APP端', ARRAY['APP PV', '移动端PV', 'APP访问量', 'APP浏览量'], 'APP Page Views'),
('页面访问量-网页端-B2B', ARRAY['B2B Web', 'B2B网页', '企业网页访问'], 'B2B Web Page Views'),
('页面访问量-APP端-B2B', ARRAY['B2B APP', '企业APP访问'], 'B2B APP Page Views')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 销售类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('总销售额', ARRAY['GMV', '总成交', '总成交额', '平台销售额', '销售额', '营收'], 'Total Sales'),
('广告销售额', ARRAY['广告营收', '广告收益', '付费广告销售'], 'Ad Sales'),
('自然订单', ARRAY['有机订单', '自然流量订单', '自然订单数'], 'Organic Orders'),
('广告订单', ARRAY['付费订单', '推广订单', '广告订单数'], 'Ad Orders'),
('销量', ARRAY['Sales', '销售量', '商品销量', '订单量', '订单数量'], 'Sales Volume'),
('含税收入', ARRAY['Revenue', '收入', '营收', '销售收入'], 'Revenue'),
('未税收入', ARRAY['Net Revenue', '净收入', '不含税收入'], 'Net Revenue'),
('广告花费', ARRAY['Spend', '广告支出', '推广花费', '付费推广', '广告费用'], 'Ad Spend'),
('广告花费-含vcpm', ARRAY['VCPM', '可见千次曝光成本'], 'Ad Spend with VCPM')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 转化率类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('转化率', ARRAY['CR', '转化', '转化比例', '订单转化', '转化比'], 'Conversion Rate'),
('点击转化率', ARRAY['CTR', '点展比', '点击率', '点击曝光比', '点展'], 'Click Conversion Rate'),
('广告转化率', ARRAY['广告CR', '广告转化', '付费转化', '广告CR'], 'Ad Conversion Rate'),
('可见曝光转化率', ARRAY['CVR', '转化', '转化比', '可见转化'], 'Visible Impressions CVR')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 广告效果类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('广告销售成本比', ARRAY['ACOS', '广告成本比', '广告支出比', 'acos'], 'Advertising Cost of Sales'),
('广告产出比', ARRAY['ROAS', '广告回报', '产出比', '广告ROI'], 'Return on Ad Spend'),
('广告客单价', ARRAY['客单价', '平均订单金额', 'AOV'], 'Ad Average Order Value'),
('单次点击成本', ARRAY['CPC', '单点成本', '每次点击成本', 'cpc'], 'Cost Per Click'),
('单次转化成本', ARRAY['CPA', '单次获客成本', '每次转化成本', 'cpa'], 'Cost Per Acquisition'),
('千次曝光成本', ARRAY['CPM', '千次展现成本', '千次展示费用', 'cpm'], 'Cost Per Mille')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 广告花费分类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('SP广告花费', ARRAY['SP广告', 'Sponsored Products', '搜索广告', 'SP投放'], 'SP Ad Spend'),
('SB广告花费', ARRAY['SB广告', 'Sponsored Brands', '品牌广告', 'SB投放'], 'SB Ad Spend'),
('SD广告花费', ARRAY['SD广告', 'Sponsored Display', '展示广告', 'SD投放'], 'SD Ad Spend'),
('DSP广告花费', ARRAY['DSP投放', '程序化广告', 'DSP投放额'], 'DSP Ad Spend')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 站内推广费
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('站内推广费费率', ARRAY['站内推广费', '站内推广', '平台推广费'], '站内推广费率'),
('DSP费率', ARRAY['DSP费用', '需求方平台费', '程序化广告费'], 'DSP费率')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 库存类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('库存金额', ARRAY['库存', '仓储', '仓库存货', '库存总值'], 'Inventory Amount'),
('库存数量', ARRAY['SKU数', '商品数', '货品数量', '库存'], 'Inventory Quantity'),
('库存周转天数', ARRAY['ITO', '库存周转', '周转天数', '周转'], 'Inventory Turnover Days'),
('库存周转率', ARRAY['周转率', '库存周转'], 'Inventory Turnover Rate'),
('动销SKU数', ARRAY['动销', '有销库存', '动销商品', '有销'], 'Active SKU Count'),
('不动销SKU数', ARRAY['滞销', '滞销商品', '滞销库存', '不动销'], 'Inactive SKU Count'),
('滞销库存金额', ARRAY['滞销额', '滞销货值'], 'Slow Moving Inventory'),
('滞销占比', ARRAY['滞销率'], 'Slow Moving Ratio'),
('缺货SKU数', ARRAY['缺货', '缺货商品', '无库存', '缺货产品'], 'Out of Stock SKU'),
('缺货率', ARRAY['缺货比例'], 'Out of Stock Rate')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 退款类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('退款金额', ARRAY['退款', '退货', '售后退款', '退款额'], 'Refund Amount'),
('退款数量', ARRAY['退货量', '退货数', '退单量', '退款单数'], 'Refund Quantity')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 平台费用类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('平台服务费率', ARRAY['平台费', '服务费', '佣金', '平台佣金'], 'Platform Service Fee Rate'),
('平台服务费', ARRAY['FBA费', '履约费', '配送费', 'FBA'], 'Platform Service Fee'),
('佣金费率', ARRAY['佣金费', '抽佣', '平台佣金'], 'Commission Rate'),
('仓储成本占比', ARRAY['仓储成本', '仓租', '仓储费'], 'Storage Cost Ratio'),
('仓储成本', ARRAY['仓储费', '仓库成本'], 'Storage Cost')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 可见性类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('可见曝光', ARRAY['可视曝光', '可见展示', '可见曝光量'], 'Visible Impressions'),
('可见率', ARRAY['可见曝光率', '可视率', '视屏见曝光率'], 'Visible Rate'),
('黄金购物车占比', ARRAY['黄金购物车', 'Buy Box', '购物车', 'BuyBox'], 'Buy Box Share')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 供应商类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('A级供应商数量', ARRAY['A级供应商', '优质供应商', '核心供应商', 'A供应商'], 'Grade A Suppliers'),
('B级供应商数量', ARRAY['B级供应商', '良好供应商', 'B供应商'], 'Grade B Suppliers'),
('C级供应商数量', ARRAY['C级供应商', '一般供应商', 'C供应商'], 'Grade C Suppliers'),
('D级供应商数量', ARRAY['D级供应商', '待改进供应商', 'D供应商'], 'Grade D Suppliers')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 采购类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('采购到货金额', ARRAY['采购额', '采购金额', '进货额'], 'Purchase Amount'),
('采购订单数量', ARRAY['采购单', '采购订单数'], 'Purchase Orders'),
('采购及时到货率', ARRAY['到货率', '交货率', '到货及时率', '准时到货率'], 'On-time Delivery Rate'),
('采购退货率', ARRAY['退货率', '采购退货'], 'Purchase Return Rate'),
('补货满足率', ARRAY['满足率', '补货率'], 'Replenishment Fill Rate')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 利润类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('税前利润', ARRAY['利润', '盈利', '税前盈利', '利润额'], 'Pre-tax Profit'),
('税前利润率', ARRAY['利润率'], 'Pre-tax Profit Margin'),
('平台边际贡献额', ARRAY['边际贡献', '边际利润', '贡献额', '边际'], 'Platform Contribution Margin'),
('平台边际贡献额率', ARRAY['边际率', '贡献率', '边际贡献率'], 'Contribution Margin Rate')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 税务类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('关税率', ARRAY['关税', '进口税'], 'Tariff Rate'),
('所得税率', ARRAY['所得税', '企业所得税'], 'Income Tax Rate'),
('地方消费税率', ARRAY['消费税', '消费附加税', '地方消费税'], 'Local Consumption Tax Rate'),
('售后服务费率', ARRAY['售后费', '售后服务费'], 'After-sales Service Fee'),
('咨询服务费率', ARRAY['咨询费', '咨询服务费'], 'Consulting Fee Rate'),
('包装费率', ARRAY['包装费', '包装费用'], 'Packaging Fee Rate')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 物流配送类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('运输费', ARRAY['运费', '运输费用'], 'Shipping Fee'),
('快递费', ARRAY['快递费用', '配送费'], 'Express Fee'),
('关税', ARRAY['进口关税'], 'Tariff'),
('佣金', ARRAY['平台佣金', '抽成'], 'Commission'),
('站内推广费', ARRAY['站内费', '推广费'], '站内推广费用'),
('售后服务费', ARRAY['售后费'], 'After-sales Fee'),
('DSP金额', ARRAY['DSP费', '程序化广告费'], 'DSP Amount'),
('包装物成本', ARRAY['包装成本'], 'Packaging Cost'),
('咨询服务费', ARRAY['咨询费'], 'Consulting Fee'),
('地方消费税', ARRAY['地方税'], 'Local Consumption Tax'),
('媒体推广费', ARRAY['媒体费', '推广费'], 'Media Promotion Fee')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 入库出库类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('入库数量', ARRAY['入库量'], 'Inbound Quantity'),
('出库数量', ARRAY['出库量'], 'Outbound Quantity'),
('日均入库量', ARRAY['日均入库'], 'Daily Average Inbound'),
('日均出库量', ARRAY['日均出库'], 'Daily Average Outbound'),
('24H出库及时率', ARRAY['24小时发货', '24H发货率', '发货及时率'], '24H Outbound Rate'),
('订单发货错误率', ARRAY['错发率', '发货错误率'], 'Order Error Rate')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 供应商绩效类
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('交付合格率', ARRAY['合格率和', '交货质量'], 'Delivery Qualification Rate'),
('交付及时率', ARRAY['准时交货率', '及时交付率'], 'On-time Delivery Rate'),
('降本达成率', ARRAY['降本率', '成本降低率'], 'Cost Reduction Rate'),
('成本目标达成率', ARRAY['成本达成', '目标成本率'], 'Cost Target Achievement'),
('供应商开发完成率', ARRAY['开发完成率'], 'Supplier Development Completion')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 库存准确率
-- =============================================
INSERT INTO business_terms (term, synonyms, description) VALUES
('库存准确率', ARRAY['库存准确', '盘点准确率'], 'Inventory Accuracy')
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;

-- =============================================
-- 验证结果
-- =============================================
SELECT '同义词配置完成！总条数：' || COUNT(*) || '，有同义词的：' || COUNT(*) FILTER (WHERE synonyms <> '{}') FROM business_terms;
