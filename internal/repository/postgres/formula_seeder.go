package postgres

import (
	"dev_metric/internal/model"
	"fmt"

	"gorm.io/gorm"
)

// SeedFormulaSyntaxConfigs 填充公式语法预置数据
func SeedFormulaSyntaxConfigs(db *gorm.DB) error {
	configs := getFormulaSyntaxConfigs()

	for _, cfg := range configs {
		// 使用 Name 作为唯一键，存在则跳过
		err := db.Where(model.FormulaSyntaxConfig{Name: cfg.Name}).FirstOrCreate(&cfg).Error
		if err != nil {
			return fmt.Errorf("插入公式语法配置[%s]失败: %w", cfg.Name, err)
		}
	}

	return nil
}

func getFormulaSyntaxConfigs() []model.FormulaSyntaxConfig {
	return []model.FormulaSyntaxConfig{
		// ==================== 时间序列 (7+8=15条) ====================
		// 基础时间序列
		{Name: "每日累计", Category: "时间序列", IntentType: "query_value", Keywords: "每日累计,日累计,累计,累加,加起来,总和", SQLPattern: "SUM({metric}) OVER(ORDER BY dt ROWS UNBOUNDED PRECEDING) AS cum_value", Priority: 10},
		{Name: "月初至今累计", Category: "时间序列", IntentType: "query_value", Keywords: "月初至今,MTD,月初到现在,本月累计", SQLPattern: "SUM({metric}) OVER(PARTITION BY YEAR(dt), MONTH(dt) ORDER BY dt)", Priority: 10},
		{Name: "7日均值", Category: "时间序列", IntentType: "query_value", Keywords: "7日均值,近7天平均,周均,最近7天,7天平均,周平均,近7天均值,7天平均值,最近一周平均,这7天平均,过去7天均值,7日平均,周均值,最近一周是多少", SQLPattern: "AVG({metric}) OVER(ORDER BY dt ROWS 6 PRECEDING)", Priority: 10},
		{Name: "30日均值", Category: "时间序列", IntentType: "query_value", Keywords: "30日均值,近30天平均,月均,最近1个月,月平均", SQLPattern: "AVG({metric}) OVER(ORDER BY dt ROWS 29 PRECEDING)", Priority: 10},
		{Name: "环比增长值", Category: "时间序列", IntentType: "query_value", Keywords: "环比增长,比上期,跟上个周期比,和上期比,跟上个月比,跟上期比,比上个月增长,比上周增长,和上个月比怎么样,跟上个周期比增长,近期对比,环比增加,环比上涨,比上一期", SQLPattern: "{metric} - LAG({metric}, 1) OVER(ORDER BY dt)", Priority: 10},
		{Name: "同比增长值", Category: "时间序列", IntentType: "query_value", Keywords: "同比增长,比去年同期,跟去年同期比,去年同期的增长,比去年增长,和去年比,跟去年同期比增长,同比增长了多少,去年增长,年际增长", SQLPattern: "{metric} - LAG({metric}, 1) OVER(PARTITION BY QUARTER(dt))", Priority: 10},
		{Name: "上月同日", Category: "时间序列", IntentType: "query_value", Keywords: "上月同天,上月同期,上月同日,去年同期同天", SQLPattern: "LAG({metric}, 1) OVER(PARTITION BY DAY(dt))", Priority: 10},
		// 销售分析补充 - 时间序列
		{Name: "年同比增长", Category: "时间序列", IntentType: "query_value", Keywords: "年同比增长,比去年同期,跟去年比,年际增长,同比增长了多少,去年增长", SQLPattern: "{metric} / LAG({metric}, 1) OVER(PARTITION BY YEAR(dt)) - 1", Priority: 10},
		{Name: "年环比增长", Category: "时间序列", IntentType: "query_value", Keywords: "年环比,年际增长,年度增长", SQLPattern: "{metric} / LAG({metric}, 4) OVER(PARTITION BY WEEK(dt)) - 1", Priority: 10},
		{Name: "季度初至今", Category: "时间序列", IntentType: "query_value", Keywords: "QTD,季度初至今,本季度累计", SQLPattern: "SUM({metric}) OVER(PARTITION BY YEAR(dt), QUARTER(dt) ORDER BY dt)", Priority: 10},
		{Name: "同比增长率", Category: "时间序列", IntentType: "query_value", Keywords: "同比增长率,比去年同期增长,同比增长百分比", SQLPattern: "({metric} - LAG({metric}, 1) OVER(PARTITION BY YEAR(dt), QUARTER(dt))) / NULLIF(LAG({metric}, 1) OVER(PARTITION BY YEAR(dt), QUARTER(dt)), 0) * 100", Priority: 10},
		{Name: "环比增长率", Category: "时间序列", IntentType: "query_value", Keywords: "环比增长率,比上期增长,环比增长百分比", SQLPattern: "({metric} - LAG({metric}, 1) OVER(ORDER BY dt)) / NULLIF(LAG({metric}, 1) OVER(ORDER BY dt), 0) * 100", Priority: 10},
		{Name: "近7日合计", Category: "时间序列", IntentType: "query_value", Keywords: "近7日,最近7天,最近一周,7日合计,7天累加,近7天总计", SQLPattern: "SUM({metric}) OVER(ORDER BY dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)", Priority: 10},
		{Name: "近30日合计", Category: "时间序列", IntentType: "query_value", Keywords: "近30日,最近30天,最近一个月,30日合计", SQLPattern: "SUM({metric}) OVER(ORDER BY dt ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)", Priority: 10},
		{Name: "销售同比", Category: "时间序列", IntentType: "query_value", Keywords: "销售同比,销售额同比增长,比去年销售", SQLPattern: "SUM(sales) / LAG(SUM(sales), 1) OVER(PARTITION BY YEAR(dt)) - 1", Priority: 10},
		{Name: "销售环比", Category: "时间序列", IntentType: "query_value", Keywords: "销售环比,销售额环比,比上期销售", SQLPattern: "SUM(sales) / LAG(SUM(sales), 1) OVER(ORDER BY dt) - 1", Priority: 10},

		// ==================== 排名分析 (6+10=16条) ====================
		{Name: "排名前N", Category: "排名分析", IntentType: "query_ranking", Keywords: "排名前,前几名,Top,按XX排序,取前N个,第几名,前N名,前N个,排名前十,排第几,排名前十,前10名,前5名,前3名,第1名,第2名,第3名,Top10,Top5,Top3,top10,top5,top3,销量前10,销售前10,排名最前,最靠前,第一名,第二名,第三名,前几名是,谁是第一,谁是冠军", SQLPattern: "ORDER BY {metric} DESC LIMIT {n}", Priority: 10},
		{Name: "排名后N", Category: "排名分析", IntentType: "query_ranking", Keywords: "排名后,最低,倒数,最后几名,最少的,排名最后的,排名最低,倒数第一,倒数第二,倒数10名,最后一名,最差,最垫底,排名最差,销量最低,销售最低,表现最差,谁最差", SQLPattern: "ORDER BY {metric} ASC LIMIT {n}", Priority: 10},
		{Name: "分组前N", Category: "排名分析", IntentType: "query_ranking", Keywords: "每组前3,各品类前10,分组排名,每个XX的排名,按XX分组排名", SQLPattern: "ROW_NUMBER() OVER(PARTITION BY {dimension} ORDER BY {metric} DESC) AS rn", Priority: 10},
		{Name: "百分位排名", Category: "排名分析", IntentType: "query_ranking", Keywords: "百分比排名,前20%,前10%,后10%,属于百分之多少", SQLPattern: "PERCENT_RANK() OVER(ORDER BY {metric} DESC)", Priority: 10},
		{Name: "分位数", Category: "排名分析", IntentType: "query_ranking", Keywords: "P10,P90,P95,P75,P25,百分位数,四分位数", SQLPattern: "PERCENTILE_CONT({metric}, 0.1) OVER()", Priority: 10},
		{Name: "等级划分", Category: "排名分析", IntentType: "query_ranking", Keywords: "高/中/低,ABC分类,等级划分,分成几等", SQLPattern: "NTILE(3) OVER(ORDER BY {metric} DESC)", Priority: 10},
		// 库存分析补充 - 排名分析
		{Name: "滞销商品", Category: "排名分析", IntentType: "query_ranking", Keywords: "滞销,卖不动,积压商品,滞销品,滞销金额,积压金额,呆滞库存值,卖不动金额", SQLPattern: "ORDER BY {metric} ASC LIMIT {n}", Priority: 10},
		{Name: "畅销商品", Category: "排名分析", IntentType: "query_ranking", Keywords: "畅销,卖得好,热销,爆款", SQLPattern: "ORDER BY {metric} DESC LIMIT {n}", Priority: 10},
		// 渠道分析补充 - 排名分析
		{Name: "渠道对比", Category: "排名分析", IntentType: "query_ranking", Keywords: "渠道对比,哪个渠道好,渠道排名", SQLPattern: "ROW_NUMBER() OVER(PARTITION BY channel ORDER BY {metric} DESC)", Priority: 10},
		// 搜索分析补充 - 排名分析
		{Name: "搜索关键词排名", Category: "排名分析", IntentType: "query_ranking", Keywords: "热搜词,搜索排名,搜什么,热搜,热搜词,搜得最多,搜索热词", SQLPattern: "ROW_NUMBER() OVER(ORDER BY search_count DESC)", Priority: 10},
		{Name: "热门搜索词", Category: "排名分析", IntentType: "query_ranking", Keywords: "热搜,搜得最多,搜索热词,热搜排行,最热搜索", SQLPattern: "ORDER BY search_count DESC LIMIT {n}", Priority: 10},
		// 竞品分析补充 - 排名分析
		{Name: "竞品对比", Category: "排名分析", IntentType: "query_ranking", Keywords: "竞品对比,跟XX比,比竞品", SQLPattern: "ROW_NUMBER() OVER(ORDER BY {metric} DESC)", Priority: 10},
		// 销售新增
		{Name: "销售冠军", Category: "排名分析", IntentType: "query_ranking", Keywords: "销冠,卖得最好,最爆款,销量冠军,谁是销冠,销售第一名", SQLPattern: "ORDER BY sales DESC LIMIT 1", Priority: 10},
		{Name: "销售垫底", Category: "排名分析", IntentType: "query_ranking", Keywords: "卖得最差,最滞销,滞销王,销售倒数第一,谁卖得最少", SQLPattern: "ORDER BY sales ASC LIMIT 1", Priority: 10},

		// ==================== 占比分析 (6+10=16条) ====================
		{Name: "整体占比", Category: "占比分析", IntentType: "query_value", Keywords: "占整体多少,占比,占总体的,占全部的,占比多少,百分比,占总金额的多少,占总额比例,占总量多少,占总盘子多少,整体占比多少,总体占比,全部占比,所有占比", SQLPattern: "{metric} / SUM({metric}) OVER() * 100 AS pct", Priority: 10},
		{Name: "分类占比", Category: "占比分析", IntentType: "query_value", Keywords: "占XX多少,XX占比,品类占比,按XX分类的占比,占分类的,各类占比,各品类占比,各渠道占比,各区域占比,占XX的比例,XX占总体的多少,按XX分类的占比", SQLPattern: "{metric} / SUM({metric}) OVER(PARTITION BY {dimension}) * 100", Priority: 10},
		{Name: "累计占比", Category: "占比分析", IntentType: "query_value", Keywords: "累计占比,加到多少,加起来占多少,累计百分比", SQLPattern: "SUM({metric}) OVER(ORDER BY {metric} DESC) / SUM({metric}) OVER() * 100", Priority: 10},
		{Name: "贡献度", Category: "占比分析", IntentType: "query_value", Keywords: "贡献度,贡献了多少,占比贡献,占总贡献的", SQLPattern: "{metric} / SUM({metric}) OVER() * 100 AS contribution", Priority: 10},
		{Name: "帕累托", Category: "占比分析", IntentType: "query_value", Keywords: "帕累托,二八法则,头部占比,尾部占比", SQLPattern: "SUM({metric}) OVER(ORDER BY {metric} DESC) / SUM({metric}) OVER() * 100", Priority: 10},
		{Name: "排名占比", Category: "占比分析", IntentType: "query_value", Keywords: "排名在前百分之,排在前%,第N名占", SQLPattern: "ROW_NUMBER() OVER(ORDER BY {metric} DESC) / COUNT(*) OVER() * 100", Priority: 10},
		// 客户分析补充 - 占比分析
		{Name: "客群占比", Category: "占比分析", IntentType: "query_value", Keywords: "客群占比,高价值占比,新客占比", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE segment = '高价值') / COUNT(DISTINCT user_id) OVER() * 100", Priority: 10},
		// 渠道分析补充 - 占比分析
		{Name: "渠道贡献占比", Category: "占比分析", IntentType: "query_value", Keywords: "渠道贡献,各渠道占比,渠道占比,渠道价值,渠道贡献度", SQLPattern: "{metric} / SUM({metric}) OVER(PARTITION BY channel) * 100", Priority: 10},
		{Name: "自然流量占比", Category: "占比分析", IntentType: "query_value", Keywords: "自然流量,免费流量,Organic占比,自然搜索占比,organic占比,免费流量占比", SQLPattern: "SUM(visits) FILTER(WHERE channel = '自然') / NULLIF(SUM(visits), 0) * 100", Priority: 10},
		{Name: "付费流量占比", Category: "占比分析", IntentType: "query_value", Keywords: "付费流量,付费占比,投流占比,付费渠道占比,投流占比", SQLPattern: "SUM(visits) FILTER(WHERE channel = '付费') / NULLIF(SUM(visits), 0) * 100", Priority: 10},
		// 搜索分析补充 - 占比分析
		{Name: "长尾搜索占比", Category: "占比分析", IntentType: "query_value", Keywords: "长尾词,小众搜索,长尾占比,无结果率,搜不到比例,空结果占比", SQLPattern: "COUNT(*) FILTER(WHERE search_count < 10) / NULLIF(COUNT(*), 0) * 100", Priority: 10},
		// 竞品分析补充 - 占比分析
		{Name: "市场份额", Category: "占比分析", IntentType: "query_value", Keywords: "市场份额,占比,市场地位", SQLPattern: "{metric} / SUM({metric}) OVER(PARTITION BY market) * 100", Priority: 10},
		// 会员分析补充 - 占比分析
		{Name: "会员占比", Category: "占比分析", IntentType: "query_value", Keywords: "会员占比,会员渗透,付费会员占比", SQLPattern: "COUNT(DISTINCT member_id) / NULLIF(COUNT(DISTINCT total_user_id), 0) * 100", Priority: 10},
		// 销售新增
		{Name: "新品占比", Category: "占比分析", IntentType: "query_value", Keywords: "新品占比,新品销售占比,新产品比例", SQLPattern: "SUM(new_product_sales) / NULLIF(SUM(total_sales), 0) * 100", Priority: 10},
		{Name: "爆款占比", Category: "占比分析", IntentType: "query_value", Keywords: "爆款占比,热销款占比,头部产品占比", SQLPattern: "SUM(top_product_sales) / NULLIF(SUM(total_sales), 0) * 100", Priority: 10},
		// 客户新增
		{Name: "新客占比", Category: "占比分析", IntentType: "query_value", Keywords: "新客占比,新客户比例,首购占比,新用户占比", SQLPattern: "COUNT(DISTINCT new_customer_id) / NULLIF(COUNT(DISTINCT customer_id), 0) * 100", Priority: 10},
		{Name: "老客占比", Category: "占比分析", IntentType: "query_value", Keywords: "老客占比,复购客户比例,忠诚客户占比", SQLPattern: "COUNT(DISTINCT returning_customer_id) / NULLIF(COUNT(DISTINCT customer_id), 0) * 100", Priority: 10},

		// ==================== 留存分析 (5+4=9条) ====================
		{Name: "次日留存", Category: "留存分析", IntentType: "query_value", Keywords: "次日留存,次留,明天还来,今天明天都来", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE dt = 'T+1') / COUNT(DISTINCT user_id) * 100", Priority: 10},
		{Name: "7日留存", Category: "留存分析", IntentType: "query_value", Keywords: "7日留存,周留,一周后还来,7天后留存", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE dt BETWEEN 'T+1' AND 'T+7') / COUNT(DISTINCT user_id)", Priority: 10},
		{Name: "30日留存", Category: "留存分析", IntentType: "query_value", Keywords: "月留,30日留存,一个月后还来", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE dt BETWEEN 'T+1' AND 'T+30') / COUNT(DISTINCT user_id)", Priority: 10},
		{Name: "流失用户", Category: "留存分析", IntentType: "query_value", Keywords: "流失,没回来,流失率,离开,不再来,流失了多少,走了多少客户", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE return_count = 0) / COUNT(DISTINCT user_id)", Priority: 10},
		{Name: "回流用户", Category: "留存分析", IntentType: "query_value", Keywords: "回流,回来,重新活跃,唤醒,流失后回来", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE gap > 7 AND return_count > 0) / COUNT(DISTINCT user_id)", Priority: 10},
		// 客户分析补充 - 留存分析
		{Name: "客户流失率", Category: "留存分析", IntentType: "query_value", Keywords: "流失率,流失了多少,走了多少客户", SQLPattern: "COUNT(DISTINCT churned_customer_id) / NULLIF(COUNT(DISTINCT total_customer_id), 0) * 100", Priority: 10},
		// 会员分析补充 - 留存分析
		{Name: "会员留存率", Category: "留存分析", IntentType: "query_value", Keywords: "会员留存,会员续费,会员留存率", SQLPattern: "COUNT(DISTINCT renewed_member_id) / NULLIF(COUNT(DISTINCT expired_member_id), 0) * 100", Priority: 10},
		// 促销分析补充
		{Name: "促销期对比", Category: "留存分析", IntentType: "query_value", Keywords: "促销量,平时比,活动效果,大促对比,促销期间对比,促销效果对比", SQLPattern: "{metric} FILTER(WHERE promotion_id IS NOT NULL) / NULLIF({metric} FILTER(WHERE promotion_id IS NULL), 0)", Priority: 10},

		// ==================== 排序分析 (4条) ====================
		{Name: "从高到低", Category: "排序分析", IntentType: "query_value", Keywords: "从高到低,从大到小,降序排列,最高在前,按从大到小", SQLPattern: "ORDER BY {metric} DESC", Priority: 9},
		{Name: "从低到高", Category: "排序分析", IntentType: "query_value", Keywords: "从低到高,从小到大,升序排列,最低在前,按从小到大", SQLPattern: "ORDER BY {metric} ASC", Priority: 9},
		{Name: "多字段排序", Category: "排序分析", IntentType: "query_value", Keywords: "先按X再按Y,主要按XX次要按YY,多字段排序", SQLPattern: "ORDER BY {metric1} DESC, {metric2} ASC", Priority: 9},
		{Name: "自定义排序", Category: "排序分析", IntentType: "query_value", Keywords: "指定排序,按XX排,按YYY排,想要排序", SQLPattern: "ORDER BY {metric} {sort_order}", Priority: 9},

		// ==================== 移动窗口 (5条) ====================
		{Name: "7日滑动求和", Category: "移动窗口", IntentType: "query_value", Keywords: "7日合计,近7天总计,7天累加,最近7天加起来", SQLPattern: "SUM({metric}) OVER(ORDER BY dt ROWS 6 PRECEDING)", Priority: 10},
		{Name: "7日峰值", Category: "移动窗口", IntentType: "query_value", Keywords: "7日最高,近7天峰值,7天最高是多少,最近7天最高", SQLPattern: "MAX({metric}) OVER(ORDER BY dt ROWS 6 PRECEDING)", Priority: 10},
		{Name: "7日最低", Category: "移动窗口", IntentType: "query_value", Keywords: "7日最低,近7天最低,7天最小值,最近7天最低", SQLPattern: "MIN({metric}) OVER(ORDER BY dt ROWS 6 PRECEDING)", Priority: 10},
		{Name: "移动平均", Category: "移动窗口", IntentType: "query_value", Keywords: "滑动平均,移动均值,窗口平均", SQLPattern: "AVG({metric}) OVER(ORDER BY dt ROWS 6 PRECEDING)", Priority: 10},
		{Name: "滚动聚合", Category: "移动窗口", IntentType: "query_value", Keywords: "滚动求和,滚动平均,滑动聚合", SQLPattern: "SUM({metric}) OVER(ORDER BY dt ROWS N PRECEDING)", Priority: 10},

		// ==================== 业务指标 (10+20=30条) ====================
		{Name: "转化率", Category: "业务指标", IntentType: "query_value", Keywords: "转化率,转化,到达率,浏览到购买的转化,浏览到购买的比率,有多少人买了,转化效果,成交转化,进店转化,点击转化,广告转化,转化了多少,转化效果如何,成交率", SQLPattern: "visitors / NULLIF(page_views, 0) * 100", Priority: 10},
		{Name: "点击率", Category: "业务指标", IntentType: "query_value", Keywords: "CTR,点击率,点击率多少,点开率,搜索点击率,搜后点击,点击占比", SQLPattern: "clicks / NULLIF(impressions, 0) * 100", Priority: 10},
		{Name: "跳出率", Category: "业务指标", IntentType: "query_value", Keywords: "跳出率,跳走,跳出的比率,浏览一页就走,退出率,页面退出,多少人在这里走,跳出", SQLPattern: "single_page_sessions / NULLIF(total_sessions, 0) * 100", Priority: 10},
		{Name: "加购率", Category: "业务指标", IntentType: "query_value", Keywords: "加入购物车,加购率,加入购物车比率,加入购物车比率,加购比例,多少人加购,加购人数占比,加购转化,购物车转化,加了几件,有人加购吗,加购情况", SQLPattern: "add_cart_users / NULLIF(visitors, 0) * 100", Priority: 10},
		{Name: "支付率", Category: "业务指标", IntentType: "query_value", Keywords: "支付率,付款率,支付转化,成交率", SQLPattern: "paying_users / NULLIF(order_users, 0) * 100", Priority: 10},
		{Name: "客单价", Category: "业务指标", IntentType: "query_value", Keywords: "客单价,每单均价,平均订单金额,人均消费,平均每单多少钱,人均消费,单均价,客单价是多少,人均订单金额,每单平均,单均价,客单价多少,人均多少钱", SQLPattern: "SUM(order_amount) / NULLIF(COUNT(DISTINCT order_id), 0)", Priority: 10},
		{Name: "复购率", Category: "业务指标", IntentType: "query_value", Keywords: "复购率,复购,再次购买率,买多次", SQLPattern: "reorder_users / NULLIF(total_users, 0) * 100", Priority: 10},
		{Name: "好评率", Category: "业务指标", IntentType: "query_value", Keywords: "好评率,好评,满意度,好评占比,满意度,服务评价", SQLPattern: "good_reviews / NULLIF(total_reviews, 0) * 100", Priority: 10},
		{Name: "退货率", Category: "业务指标", IntentType: "query_value", Keywords: "退货率,退货,退款率", SQLPattern: "returned_orders / NULLIF(total_orders, 0) * 100", Priority: 10},
		{Name: "毛利率", Category: "业务指标", IntentType: "query_value", Keywords: "毛利,利润率,毛利率,赚了多少,毛利率分析,毛利占比,利润空间,赚了多少比例", SQLPattern: "(revenue - cost) / NULLIF(revenue, 0) * 100", Priority: 10},
		// 库存分析补充 - 业务指标
		{Name: "库销比", Category: "业务指标", IntentType: "query_value", Keywords: "库销比,库存销售比,库存周转", SQLPattern: "SUM({metric}) / NULLIF(SUM(sales), 0)", Priority: 10},
		{Name: "库存周转率", Category: "业务指标", IntentType: "query_value", Keywords: "周转率,周转速度,几次,周转几次,周转次数,库存周转", SQLPattern: "SUM(out_stock) / NULLIF(AVG(stock), 0)", Priority: 10},
		{Name: "预计库存可用天数", Category: "业务指标", IntentType: "query_value", Keywords: "可用天数,还能卖多久,库存能撑几天,预计库存天数", SQLPattern: "stock / NULLIF(AVG(daily_sales), 0)", Priority: 10},
		// 渠道分析补充 - 业务指标
		{Name: "渠道ROI", Category: "业务指标", IntentType: "query_value", Keywords: "渠道ROI,投入产出,渠道效果,ROI,投入产出,投资回报,产出比,回报率", SQLPattern: "SUM(revenue) FILTER(WHERE channel = '付费') / NULLIF(SUM(cost) FILTER(WHERE channel = '付费'), 0)", Priority: 10},
		{Name: "渠道转化率", Category: "业务指标", IntentType: "query_value", Keywords: "渠道转化,各渠道转化率,渠道效果,流量转化,流量价值,流量效率,来多少人买", SQLPattern: "SUM(conversions) FILTER(WHERE channel = '{channel}') / NULLIF(SUM(visits) FILTER(WHERE channel = '{channel}'), 0) * 100", Priority: 10},
		{Name: "获客成本", Category: "业务指标", IntentType: "query_value", Keywords: "CPA,获客成本,获客价格,拉新成本,每个客户成本", SQLPattern: "SUM(cost) / NULLIF(COUNT(DISTINCT new_customer_id), 0)", Priority: 10},
		// 促销分析补充 - 业务指标
		{Name: "活动效果", Category: "业务指标", IntentType: "query_value", Keywords: "活动效果,促销效果,活动贡献", SQLPattern: "{metric} / NULLIF(SUM({metric}) OVER(), 0) * 100", Priority: 10},
		{Name: "活动ROI", Category: "业务指标", IntentType: "query_value", Keywords: "活动ROI,促销ROI,投入产出比,活动效果,投入产出,活动回报", SQLPattern: "SUM(sales) FILTER(WHERE promotion_id IS NOT NULL) / NULLIF(SUM(cost), 0)", Priority: 10},
		{Name: "折扣率", Category: "业务指标", IntentType: "query_value", Keywords: "折扣率,打折,折扣力度,让利,促销力度,优惠程度,让利幅度,打了几折,优惠多少", SQLPattern: "AVG(discount_rate) FILTER(WHERE promotion_id IS NOT NULL)", Priority: 10},
		{Name: "优惠券核销率", Category: "业务指标", IntentType: "query_value", Keywords: "优惠券核销,领券率,用券率,优惠券使用率,领券用券,优惠券使用", SQLPattern: "SUM(used) FILTER(WHERE coupon_id IS NOT NULL) / NULLIF(SUM(issued), 0) * 100", Priority: 10},
		// 页面分析补充 - 业务指标
		{Name: "页面浏览量", Category: "业务指标", IntentType: "query_value", Keywords: "PV,浏览量,页面浏览,看了多少次", SQLPattern: "SUM(page_views)", Priority: 10},
		{Name: "人均浏览页数", Category: "业务指标", IntentType: "query_value", Keywords: "人均页数,平均浏览,人均PV,访问深度,看了几页,人均页数,浏览深度", SQLPattern: "SUM(page_views) / NULLIF(COUNT(DISTINCT visitor_id), 0)", Priority: 10},
		{Name: "页面停留时长", Category: "业务指标", IntentType: "query_value", Keywords: "停留时长,看了多久,页面时长,访问时长,看了多久,访问时长,呆了多久", SQLPattern: "AVG(stay_time)", Priority: 10},
		{Name: "退出率", Category: "业务指标", IntentType: "query_value", Keywords: "退出率,退出,离开页面", SQLPattern: "SUM(exit_count) / NULLIF(SUM(page_views), 0) * 100", Priority: 10},
		// 搜索分析补充 - 业务指标
		{Name: "搜索转化率", Category: "业务指标", IntentType: "query_value", Keywords: "搜后购买,搜索转化,搜了买,搜索成交率,搜后购买", SQLPattern: "SUM(conversion) FILTER(WHERE from_search = 1) / NULLIF(SUM(search_count), 0) * 100", Priority: 10},
		{Name: "无结果搜索", Category: "业务指标", IntentType: "query_value", Keywords: "无结果,搜不到,空结果", SQLPattern: "COUNT(*) FILTER(WHERE result_count = 0)", Priority: 10},
		{Name: "搜索人均次数", Category: "业务指标", IntentType: "query_value", Keywords: "搜索次数,人均搜索", SQLPattern: "SUM(search_count) / NULLIF(COUNT(DISTINCT user_id), 0)", Priority: 10},
		// 供应链分析补充 - 业务指标
		{Name: "订单履约率", Category: "业务指标", IntentType: "query_value", Keywords: "履约率,按时发货,发货及时率", SQLPattern: "SUM(fulfilled_on_time) / NULLIF(SUM(total_orders), 0) * 100", Priority: 10},
		{Name: "准时交货率", Category: "业务指标", IntentType: "query_value", Keywords: "准时交货,按时到达,交货及时", SQLPattern: "SUM(delivered_on_time) / NULLIF(SUM(delivered_total), 0) * 100", Priority: 10},
		{Name: "平均配送时长", Category: "业务指标", IntentType: "query_value", Keywords: "配送时长,多久到,配送时间", SQLPattern: "AVG(delivery_time)", Priority: 10},
		{Name: "库存满足率", Category: "业务指标", IntentType: "query_value", Keywords: "满足率,现货率,有货率", SQLPattern: "SUM(in_stock_orders) / NULLIF(SUM(total_orders), 0) * 100", Priority: 10},
		{Name: "缺货率", Category: "业务指标", IntentType: "query_value", Keywords: "缺货,缺货率,无货,卖断", SQLPattern: "SUM(stockout_count) / NULLIF(SUM(demand_count), 0) * 100", Priority: 10},
		{Name: "在途库存", Category: "业务指标", IntentType: "query_value", Keywords: "在途,在途库存,运输中", SQLPattern: "SUM(in_transit_quantity)", Priority: 10},
		// 客服分析补充 - 业务指标
		{Name: "客服响应率", Category: "业务指标", IntentType: "query_value", Keywords: "响应率,回复率,客服响应", SQLPattern: "SUM(responded_count) / NULLIF(SUM(total_inquiries), 0) * 100", Priority: 10},
		{Name: "平均响应时长", Category: "业务指标", IntentType: "query_value", Keywords: "响应时长,回复速度,多久回复,首次响应时长,多久回复,响应速度,首响时长", SQLPattern: "AVG(first_response_time)", Priority: 10},
		{Name: "满意度", Category: "业务指标", IntentType: "query_value", Keywords: "满意度,好评率,服务评价", SQLPattern: "SUM(satisfied_count) / NULLIF(SUM(total_ratings), 0) * 100", Priority: 10},
		{Name: "客服处理时长", Category: "业务指标", IntentType: "query_value", Keywords: "处理时长,解决时长,花了多久", SQLPattern: "AVG(resolution_time)", Priority: 10},
		{Name: "升级率", Category: "业务指标", IntentType: "query_value", Keywords: "升级,升级率,升级投诉,升级投诉,升级率,升级多少,被升级", SQLPattern: "SUM(escalated_count) / NULLIF(SUM(total_inquiries), 0) * 100", Priority: 10},
		// 财务分析补充 - 业务指标
		{Name: "净利率", Category: "业务指标", IntentType: "query_value", Keywords: "净利率,净利润率,纯利率", SQLPattern: "(revenue - cost - expense) / NULLIF(revenue, 0) * 100", Priority: 10},
		{Name: "坏账率", Category: "业务指标", IntentType: "query_value", Keywords: "坏账,坏账率,收不回来", SQLPattern: "SUM(bad_debt) / NULLIF(SUM(accounts_receivable), 0) * 100", Priority: 10},
		{Name: "资产周转率", Category: "业务指标", IntentType: "query_value", Keywords: "资产周转,周转效率", SQLPattern: "SUM(revenue) / NULLIF(AVG(total_assets), 0)", Priority: 10},
		{Name: "现金流", Category: "业务指标", IntentType: "query_value", Keywords: "现金流,现金流入流出,现金结余", SQLPattern: "SUM(cash_inflow) - SUM(cash_outflow)", Priority: 10},
		// 竞品分析补充 - 业务指标
		{Name: "竞争力指数", Category: "业务指标", IntentType: "query_value", Keywords: "竞争力,强弱,优劣势", SQLPattern: "{metric} / NULLIF(competitor_metric, 0)", Priority: 10},
		// 活动分析补充 - 业务指标
		{Name: "活动参与率", Category: "业务指标", IntentType: "query_value", Keywords: "参与率,活动参与,多少人参加", SQLPattern: "SUM(participants) / NULLIF(SUM(exposed), 0) * 100", Priority: 10},
		{Name: "活动转化率", Category: "业务指标", IntentType: "query_value", Keywords: "活动转化,活动购买,活动成交", SQLPattern: "SUM(conversions) / NULLIF(SUM(participants), 0) * 100", Priority: 10},
		{Name: "活动曝光", Category: "业务指标", IntentType: "query_value", Keywords: "曝光量,多少人看到,展示次数,内容曝光,看到,展示", SQLPattern: "SUM(impressions)", Priority: 10},
		{Name: "活动ROI", Category: "业务指标", IntentType: "query_value", Keywords: "活动效果,投入产出,活动回报,ROI,投入产出,投资回报", SQLPattern: "SUM(gmv) FILTER(WHERE campaign_id IS NOT NULL) / NULLIF(SUM(cost), 0)", Priority: 10},
		// 内容分析补充 - 业务指标
		{Name: "内容点击", Category: "业务指标", IntentType: "query_value", Keywords: "点击,点开,浏览,内容点击", SQLPattern: "SUM(clicks)", Priority: 10},
		{Name: "内容互动率", Category: "业务指标", IntentType: "query_value", Keywords: "互动率,评论,收藏,分享,内容互动率", SQLPattern: "(SUM(comments) + SUM(favorites) + SUM(shares)) / NULLIF(SUM(impressions), 0) * 100", Priority: 10},
		// 会员分析补充 - 业务指标
		{Name: "会员活跃度", Category: "业务指标", IntentType: "query_value", Keywords: "会员活跃,会员登录,活跃度,活跃度,会员登录,活跃比例", SQLPattern: "COUNT(DISTINCT active_member_id) / NULLIF(COUNT(DISTINCT total_member_id), 0) * 100", Priority: 10},
		{Name: "会员续费率", Category: "业务指标", IntentType: "query_value", Keywords: "续费率,续费,会员续期", SQLPattern: "SUM(renewed) / NULLIF(SUM(expired), 0) * 100", Priority: 10},
		// 客服新增
		{Name: "解决率", Category: "业务指标", IntentType: "query_value", Keywords: "解决率,解决了多少,解决比例,成功解决", SQLPattern: "SUM(resolved) / NULLIF(SUM(total_tickets), 0) * 100", Priority: 10},
		{Name: "客服工作量", Category: "业务指标", IntentType: "query_value", Keywords: "工作量,处理量,人均处理,客服负荷", SQLPattern: "SUM(total_tickets) / NULLIF(COUNT(DISTINCT agent_id), 0)", Priority: 10},
		// 财务新增
		{Name: "成本占比", Category: "业务指标", IntentType: "query_value", Keywords: "成本率,费用率,成本占比,花了多少", SQLPattern: "SUM(cost) / NULLIF(SUM(revenue), 0) * 100", Priority: 10},
		{Name: "费用率", Category: "业务指标", IntentType: "query_value", Keywords: "费用率,营销费用率,运营费用率,各项费用", SQLPattern: "SUM(expense) / NULLIF(SUM(revenue), 0) * 100", Priority: 10},
		// 销售新增
		{Name: "人均产出", Category: "业务指标", IntentType: "query_value", Keywords: "人均产能,人均产值,人均效益,人均销售,每人产出", SQLPattern: "SUM(sales) / NULLIF(COUNT(staff), 0)", Priority: 10},
		{Name: "销售完成率", Category: "业务指标", IntentType: "query_value", Keywords: "完成率,达标率,目标完成,完成进度,完成了多少,预算执行率,花了多少预算,预算消耗,执行率", SQLPattern: "SUM(achieved) / NULLIF(SUM(target), 0) * 100", Priority: 10},

		// ==================== 数值计算 (8条) ====================
		{Name: "四舍五入", Category: "数值计算", IntentType: "query_value", Keywords: "四舍五入,保留几位,保留两位,保留整数", SQLPattern: "ROUND({metric}, 2)", Priority: 8},
		{Name: "绝对值", Category: "数值计算", IntentType: "query_value", Keywords: "绝对值,正数,取绝对值,不论正负", SQLPattern: "ABS({metric})", Priority: 8},
		{Name: "填充零", Category: "数值计算", IntentType: "query_value", Keywords: "填补NULL,填充0,空值填充,没有的填0", SQLPattern: "COALESCE({metric}, 0)", Priority: 8},
		{Name: "向上取整", Category: "数值计算", IntentType: "query_value", Keywords: "向上取,至少,取上线,进一", SQLPattern: "CEIL({metric})", Priority: 8},
		{Name: "向下取整", Category: "数值计算", IntentType: "query_value", Keywords: "向下取,最多,取下线,舍去", SQLPattern: "FLOOR({metric})", Priority: 8},
		{Name: "均价", Category: "数值计算", IntentType: "query_value", Keywords: "平均价格,单价,每件多少钱", SQLPattern: "SUM(amount) / NULLIF(SUM(quantity), 0)", Priority: 8},
		{Name: "总价", Category: "数值计算", IntentType: "query_value", Keywords: "总价,汇总,一共多少钱,总额", SQLPattern: "SUM({metric} * quantity)", Priority: 8},
		{Name: "折扣价", Category: "数值计算", IntentType: "query_value", Keywords: "打几折,折后价,折扣价", SQLPattern: "{metric} * discount / 10", Priority: 8},

		// ==================== 条件逻辑 (5+4=9条) ====================
		{Name: "条件赋值", Category: "条件逻辑", IntentType: "query_value", Keywords: "如果大于,当大于,大于则,超过", SQLPattern: "CASE WHEN {metric} > 100 THEN '高' ELSE '低' END", Priority: 9},
		{Name: "区间划分", Category: "条件逻辑", IntentType: "query_value", Keywords: "0-50,50-100,分段,分档,划分区间", SQLPattern: "CASE WHEN {metric} < 50 THEN '低' WHEN {metric} < 100 THEN '中' ELSE '高' END", Priority: 9},
		{Name: "开关函数", Category: "条件逻辑", IntentType: "query_value", Keywords: "开关,正负,正数负数,属于哪边", SQLPattern: "IF({metric} > 0, '正', '负')", Priority: 9},
		{Name: "多条件", Category: "条件逻辑", IntentType: "query_value", Keywords: "且和,并且,同时满足,满足A和B", SQLPattern: "CASE WHEN cond1 AND cond2 THEN 'A' WHEN cond1 OR cond2 THEN 'B' END", Priority: 9},
		{Name: "空值判断", Category: "条件逻辑", IntentType: "query_value", Keywords: "是否为空,有没有值,NULL判断", SQLPattern: "CASE WHEN {metric} IS NULL THEN '无' ELSE '有' END", Priority: 9},
		// 库存分析补充 - 条件逻辑
		{Name: "安全库存预警", Category: "条件逻辑", IntentType: "query_value", Keywords: "安全库存,库存预警,低于安全库存,库存不足,库存不足,缺货预警,库存告急,低于安全库存,需要补货", SQLPattern: "CASE WHEN stock < safety_stock THEN '预警' ELSE '正常' END", Priority: 9},
		// 促销分析补充 - 条件逻辑
		{Name: "满减门槛", Category: "条件逻辑", IntentType: "query_value", Keywords: "满减,凑单,满多少,门槛,满减分析,凑单,满多少减,满额优惠", SQLPattern: "CASE WHEN order_amount >= threshold THEN '满减' ELSE '不满' END", Priority: 9},
		// 竞品分析补充 - 条件逻辑
		{Name: "差距分析", Category: "条件逻辑", IntentType: "query_value", Keywords: "差距,差多少,落后多少", SQLPattern: "CASE WHEN {metric} > competitor THEN '领先' ELSE '落后' END", Priority: 9},
		// 库存新增 - 条件逻辑
		{Name: "库龄分层", Category: "条件逻辑", IntentType: "query_value", Keywords: "库龄等级,积压等级,呆滞等级,库龄分析,积压多久", SQLPattern: "CASE WHEN days_on_hand > 90 THEN '呆滞' WHEN days_on_hand > 30 THEN '一般' ELSE '正常' END", Priority: 9},
		{Name: "临期库存", Category: "条件逻辑", IntentType: "query_value", Keywords: "临期,快过期,即将过期,效期预警,多久到期", SQLPattern: "CASE WHEN expiration_date < DATE_ADD(CURRENT_DATE, INTERVAL 30 DAY) THEN '临期' ELSE '正常' END", Priority: 9},

		// ==================== 用户分群 (6+8=14条) ====================
		{Name: "新增用户", Category: "用户分群", IntentType: "query_value", Keywords: "今日新增,新用户,新注册,新来的,新增客户,新客户,新注册,获客", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE first_dt = dt)", Priority: 10},
		{Name: "活跃用户", Category: "用户分群", IntentType: "query_value", Keywords: "活跃用户,DAU,日活,在线用户,活跃客户,活跃", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE dt = '指定日期')", Priority: 10},
		{Name: "沉睡用户", Category: "用户分群", IntentType: "query_value", Keywords: "沉睡,不活跃,很久没来,流失边缘", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE last_dt < DATE_SUB(dt, 30))", Priority: 10},
		{Name: "回流用户", Category: "用户分群", IntentType: "query_value", Keywords: "回流,回来,唤醒,流失后回来,沉睡唤醒,唤醒,即将流失,很久没来,多久没买", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE gap > 7 AND return_count > 0)", Priority: 10},
		{Name: "高价值用户", Category: "用户分群", IntentType: "query_value", Keywords: "VIP,高价值,RFM,重要用户", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE RFM_score > 100)", Priority: 10},
		{Name: "用户等级", Category: "用户分群", IntentType: "query_value", Keywords: "普通,高级,会员,等级,用户分层", SQLPattern: "CASE WHEN order_count >= 10 THEN '高' WHEN order_count >= 3 THEN '中' ELSE '低' END", Priority: 10},
		// 客户分析补充 - 用户分群
		{Name: "新增客户数", Category: "用户分群", IntentType: "query_value", Keywords: "新增客户,新客户,新注册,获客", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE first_purchase_date = dt)", Priority: 10},
		{Name: "流失客户数", Category: "用户分群", IntentType: "query_value", Keywords: "流失客户,流失,流失率,离开的客户", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE last_purchase_date < DATE_SUB(CURRENT_DATE, 90))", Priority: 10},
		{Name: "活跃客户数", Category: "用户分群", IntentType: "query_value", Keywords: "活跃客户,活跃,在线", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE activity_date = dt)", Priority: 10},
		{Name: "复购客户数", Category: "用户分群", IntentType: "query_value", Keywords: "复购,回头客,再次购买", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE purchase_count > 1)", Priority: 10},
		{Name: "客户等级分布", Category: "用户分群", IntentType: "query_value", Keywords: "客户等级,VIP,普通,高级会员,会员等级分布,普通会员,黄金会员,等级分布", SQLPattern: "CASE WHEN total_amount > 10000 THEN '高' WHEN total_amount > 1000 THEN '中' ELSE '低' END", Priority: 10},
		{Name: "RFM分析", Category: "用户分群", IntentType: "query_value", Keywords: "RFM,最近一次,消费频率,消费金额,RFM评分,RFM模型,最近频率货币,客户分层", SQLPattern: "ROW_NUMBER() OVER(PARTITION BY user_id ORDER BY recency, frequency, monetary DESC)", Priority: 10},
		{Name: "沉睡客户唤醒", Category: "用户分群", IntentType: "query_value", Keywords: "沉睡唤醒,唤醒,很久没来,即将流失", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE DATEDIFF(CURRENT_DATE, last_purchase_date) BETWEEN 30 AND 90)", Priority: 10},
		// 活动分析补充 - 用户分群
		{Name: "活动拉新", Category: "用户分群", IntentType: "query_value", Keywords: "活动拉新,活动获客,新客活动", SQLPattern: "COUNT(DISTINCT user_id) FILTER(WHERE first_purchase_campaign = campaign_id)", Priority: 10},
		// 会员新增 - 用户分群
		{Name: "高价值会员", Category: "用户分群", IntentType: "query_value", Keywords: "高价值会员,VIP会员,核心会员,贡献最大的会员", SQLPattern: "SUM(membership_value) FILTER(WHERE member_tier = '高价值') / NULLIF(SUM(membership_value), 0) * 100", Priority: 10},

		// ==================== 地理分析 (4条) ====================
		{Name: "各省汇总", Category: "地理分析", IntentType: "query_value", Keywords: "各省统计,按省份,哪个省,省级别", SQLPattern: "SUM({metric}) OVER(PARTITION BY province)", Priority: 9},
		{Name: "区域汇总", Category: "地理分析", IntentType: "query_value", Keywords: "华东华南,按区域,区域统计,大区", SQLPattern: "SUM({metric}) OVER(PARTITION BY region)", Priority: 9},
		{Name: "城市排名", Category: "地理分析", IntentType: "query_ranking", Keywords: "城市排名,哪个城市,城市统计", SQLPattern: "ROW_NUMBER() OVER(PARTITION BY city ORDER BY {metric} DESC)", Priority: 9},
		{Name: "城市占比", Category: "地理分析", IntentType: "query_value", Keywords: "城市占比,哪个城市多,城市分布", SQLPattern: "{metric} / SUM({metric}) OVER(PARTITION BY city)", Priority: 9},

		// ==================== 文本处理 (5条) ====================
		{Name: "字符长度", Category: "文本处理", IntentType: "query_value", Keywords: "多长,字数,长度,字符数", SQLPattern: "LENGTH({metric})", Priority: 7},
		{Name: "字符截取", Category: "文本处理", IntentType: "query_value", Keywords: "截取前N位,中间,前几个字符,后几位", SQLPattern: "SUBSTRING({metric}, 1, N)", Priority: 7},
		{Name: "字符替换", Category: "文本处理", IntentType: "query_value", Keywords: "替换成,改成,替换,把XX换成", SQLPattern: "REPLACE({metric}, 'old', 'new')", Priority: 7},
		{Name: "拼接", Category: "文本处理", IntentType: "query_value", Keywords: "拼接,连接,加一起,合并", SQLPattern: "CONCAT({metric}, '-', other_col)", Priority: 7},
		{Name: "去除空格", Category: "文本处理", IntentType: "query_value", Keywords: "去掉空格,去空格,空格去掉", SQLPattern: "TRIM({metric})", Priority: 7},

		// ==================== 预算预测 (4+2=6条) ====================
		{Name: "目标完成率", Category: "预算预测", IntentType: "query_value", Keywords: "完成率,达标,目标完成,预算完成", SQLPattern: "{actual} / NULLIF({target}, 0) * 100", Priority: 9},
		{Name: "预算剩余", Category: "预算预测", IntentType: "query_value", Keywords: "还剩多少,预算剩余,还差多少", SQLPattern: "{budget} - SUM({metric}) OVER()", Priority: 9},
		{Name: "预算消耗", Category: "预算预测", IntentType: "query_value", Keywords: "消耗率,花了多少,消耗进度", SQLPattern: "SUM({metric}) / NULLIF({total_budget}, 0) * 100", Priority: 9},
		{Name: "偏差", Category: "预算预测", IntentType: "query_value", Keywords: "实际减预期,差异,超出多少", SQLPattern: "{actual} - {expected}", Priority: 9},
		// 财务分析补充 - 时间序列
		{Name: "同比差异", Category: "预算预测", IntentType: "query_value", Keywords: "同比差异,比去年多,同比变化,差异多少", SQLPattern: "{metric} - LAG({metric}, 1) OVER(PARTITION BY YEAR(dt))", Priority: 9},

		// ==================== 高级分析 (4+1=5条) ====================
		{Name: "独立用户数", Category: "高级分析", IntentType: "query_value", Keywords: "独立用户,去重用户,UV,有多少人,独立访客,去重访客,有多少人", SQLPattern: "COUNT(DISTINCT user_id)", Priority: 10},
		{Name: "精确去重", Category: "高级分析", IntentType: "query_value", Keywords: "精确UV,精确去重,人数", SQLPattern: "COUNT(DISTINCT user_id)", Priority: 10},
		{Name: "近似去重", Category: "高级分析", IntentType: "query_value", Keywords: "近似去重,估算UV,HLL", SQLPattern: "APPROX_COUNT_DISTINCT(user_id)", Priority: 10},
		{Name: "唯一计数", Category: "高级分析", IntentType: "query_value", Keywords: "唯一计数,不重复的,有几种", SQLPattern: "COUNT(DISTINCT {metric})", Priority: 10},
		// 页面分析补充 - 高级分析
		{Name: "独立访客数", Category: "高级分析", IntentType: "query_value", Keywords: "UV,独立访客,去重访客,有多少人", SQLPattern: "COUNT(DISTINCT visitor_id)", Priority: 10},

		// ==================== 补充销售分析 (2条) ====================
		// 销售新增
		{Name: "促销期峰值", Category: "业务指标", IntentType: "query_value", Keywords: "大促峰值,活动高峰,秒杀高峰,活动最高,促销最高", SQLPattern: "MAX({metric}) FILTER(WHERE is_promotion = 1)", Priority: 10},

		// ==================== 补充客户分析 (3条) ====================
		{Name: "首单时间", Category: "用户分群", IntentType: "query_value", Keywords: "首单时间,首次购买,第一次买,客户首购,什么时候首购", SQLPattern: "MIN(first_purchase_date)", Priority: 10},
		{Name: "客户生命周期价值", Category: "用户分群", IntentType: "query_value", Keywords: "LTV,生命周期价值,客户总价值,总贡献,客户价值", SQLPattern: "SUM(lifetime_revenue)", Priority: 10},
		{Name: "转化周期", Category: "用户分群", IntentType: "query_value", Keywords: "多久转化,购买周期,决策周期,从访问到购买,转化时长", SQLPattern: "AVG(days_to_convert)", Priority: 10},

		// ==================== 补充会员分析 (1条) ====================
		{Name: "会员增长率", Category: "时间序列", IntentType: "query_value", Keywords: "会员增长,新增会员,会员增速", SQLPattern: "COUNT(DISTINCT new_member_id) / NULLIF(COUNT(DISTINCT total_member_id), 0) * 100", Priority: 10},

		// ==================== 补充财务分析 (1条) ====================
		{Name: "账期分析", Category: "业务指标", IntentType: "query_value", Keywords: "账期,回款周期,应收账款,多久回款,账龄", SQLPattern: "AVG(collection_period_days)", Priority: 10},
	}
}
