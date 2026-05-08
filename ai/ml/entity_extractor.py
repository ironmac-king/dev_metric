"""
实体抽取器 - 从用户问题中提取指标、时间、维度等实体
使用规则+正则的混合方法
"""
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta


class EntityExtractor:
    """实体抽取器 - 提取指标名、时间、维度等实体"""

    def __init__(self):
        # 时间表达式映射
        self.time_patterns = {
            # 昨天/今日等绝对时间
            r"(昨天|昨日)": "yesterday",
            r"(今天|今日|本日)": "today",
            r"(明天|明日)": "tomorrow",
            r"(前天|前日)": "day_before_yesterday",
            r"(后天|后日)": "day_after_tomorrow",

            # 本周/上周等相对周期
            r"(本周|这周|本周内)": "this_week",
            r"(上周|上一周)": "last_week",
            r"(下周|下一周)": "next_week",
            r"(本月|这月|本月内)": "this_month",
            r"(上月|上一月)": "last_month",
            r"(下月|下一月)": "next_month",
            r"(本年|今年|今年内)": "this_year",
            r"(去年|上年)": "last_year",

            # 常用时间范围
            r"最近[天周月]?(\d+)[天周月]?": "recent_days",  # 最近7天
            r"近(\d+)天": "recent_days",
            r"近(\d+)周": "recent_weeks",
            r"近(\d+)月": "recent_months",
            r"过去(\d+)天": "past_days",

            # 季度
            r"(本季|这个季度|本期)": "this_quarter",
            r"(上季|上个季度|上期)": "last_quarter",

            # 时间点
            r"(\d{4})年(\d{1,2})月(\d{1,2})日?": "specific_date",
            r"(\d{4})-(\d{1,2})-(\d{1,2})": "specific_date",
            r"(\d{4})年(\d{1,2})月": "specific_month",
            r"(\d{4})年": "specific_year",
        }

        # 常用指标词
        self.metric_keywords = [
            "数", "量", "额", "率", "占比", "比例",
            "次数", "人数", "客数", "用户数", "访客数",
            "订单", "销售额", "收入", "营收", "利润",
            "转化", "点击", "曝光", "浏览", "访问",
            "新增", "活跃", "留存", "流失",
        ]

        # 维度关键词
        self.dimension_keywords = [
            # 平台维度
            "亚马逊", "天猫", "京东", "淘宝", "拼多多", "抖音", "快手",
            # 地域维度
            "国内", "海外", "国外", "华东", "华南", "华北",
            # 品类维度
            "美妆", "服装", "食品", "数码", "家电",
            # 设备维度
            "PC", "移动", "APP", "小程序", "H5",
        ]

        # 聚合函数
        self.aggregation_keywords = {
            "总计": "sum",
            "合计": "sum",
            "总和": "sum",
            "平均": "avg",
            "均值": "avg",
            "平均数": "avg",
            "最大": "max",
            "最小": "min",
            "最高": "max",
            "最低": "min",
            "数量": "count",
            "个数": "count",
            "条数": "count",
        }

    def extract(self, text: str) -> Dict[str, Any]:
        """
        从文本中提取所有实体

        返回:
            {
                "metric_name": "访客数",      # 指标名
                "time_range": "this_week",    # 时间范围
                "time_exact": "2024-01-01",  # 精确时间（如果有）
                "dimensions": ["华东"],        # 维度列表
                "aggregation": "sum",        # 聚合方式
                "filters": {},                 # 筛选条件
            }
        """
        result = {
            "metric_name": None,
            "time_range": None,
            "time_exact": None,
            "dimensions": [],
            "aggregation": None,
            "filters": {},
            "raw_time": None,  # 原始时间表达
        }

        # 提取时间
        time_info = self.extract_time(text)
        result.update(time_info)

        # 提取指标名
        metric_name = self.extract_metric_name(text)
        result["metric_name"] = metric_name

        # 提取维度
        dimensions = self.extract_dimensions(text)
        result["dimensions"] = dimensions

        # 提取聚合方式
        aggregation = self.extract_aggregation(text)
        result["aggregation"] = aggregation

        return result

    def extract_time(self, text: str) -> Dict[str, Any]:
        """提取时间实体"""
        result = {
            "time_range": None,
            "time_exact": None,
            "raw_time": None,
        }

        for pattern, time_type in self.time_patterns.items():
            match = re.search(pattern, text)
            if match:
                result["raw_time"] = match.group(0)

                if time_type == "specific_date":
                    # 提取具体日期
                    groups = match.groups()
                    if len(groups) >= 3:
                        year, month, day = groups[0], groups[1], groups[2]
                        result["time_exact"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        result["time_range"] = "specific_date"

                elif time_type == "specific_month":
                    groups = match.groups()
                    if len(groups) >= 2:
                        year, month = groups[0], groups[1]
                        result["time_exact"] = f"{year}-{month.zfill(2)}"
                        result["time_range"] = "specific_month"

                elif time_type == "specific_year":
                    result["time_exact"] = match.group(1)
                    result["time_range"] = "specific_year"

                elif time_type in ["recent_days", "recent_weeks", "recent_months"]:
                    # 最近N天/周/月
                    days_match = re.search(r'(\d+)', match.group(0))
                    if days_match:
                        n = int(days_match.group(1))
                        result["time_range"] = time_type
                        result["time_value"] = n  # 附加信息：N是多少

                else:
                    result["time_range"] = time_type

                break

        return result

    def extract_metric_name(self, text: str) -> Optional[str]:
        """提取指标名"""
        # 常见指标名模式
        metric_patterns = [
            # 完整指标名
            r"(访客数|用户数|订单量|销售额|转化率|广告转化率|净利润|毛利率)",
            # 指标名+后缀
            r"([\u4e00-\u9fa5]+(?:数|量|额|率|占比))",
            # 指标名+前缀
            r"((?:新|老)?(?:增|活跃)?(?:用户|访客|订单|客户)(?:数|量)?)",
        ]

        for pattern in metric_patterns:
            match = re.search(pattern, text)
            if match:
                metric = match.group(1) if match.lastindex else match.group(0)
                # 过滤太短的
                if len(metric) >= 2:
                    return metric

        return None

    def extract_dimensions(self, text: str) -> List[str]:
        """提取维度"""
        dimensions = []

        for keyword in self.dimension_keywords:
            if keyword in text:
                dimensions.append(keyword)

        # 去重
        dimensions = list(dict.fromkeys(dimensions))

        return dimensions

    def extract_aggregation(self, text: str) -> Optional[str]:
        """提取聚合方式"""
        for keyword, agg in self.aggregation_keywords.items():
            if keyword in text:
                return agg

        return None

    def extract_filter_conditions(self, text: str) -> Dict[str, str]:
        """提取筛选条件"""
        filters = {}

        # 平台筛选
        platforms = ["亚马逊", "天猫", "京东", "淘宝", "拼多多", "抖音", "快手"]
        for platform in platforms:
            if platform in text:
                filters["platform"] = platform
                break

        # 地域筛选
        regions = ["华东", "华南", "华北", "国内", "海外", "国外"]
        for region in regions:
            if region in text:
                filters["region"] = region
                break

        return filters

    def get_time_range(self, time_type: str, time_value: int = None) -> Tuple[datetime, datetime]:
        """
        根据时间类型获取时间范围

        返回:
            (开始时间, 结束时间)
        """
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if time_type == "yesterday":
            start = today - timedelta(days=1)
            end = start + timedelta(days=1)
        elif time_type == "today":
            start = today
            end = now
        elif time_type == "this_week":
            start = today - timedelta(days=today.weekday())
            end = now
        elif time_type == "last_week":
            start = today - timedelta(days=today.weekday() + 7)
            end = start + timedelta(days=7)
        elif time_type == "this_month":
            start = today.replace(day=1)
            end = now
        elif time_type == "last_month":
            first_day_this_month = today.replace(day=1)
            start = (first_day_this_month - timedelta(days=1)).replace(day=1)
            end = first_day_this_month
        elif time_type == "this_year":
            start = today.replace(month=1, day=1)
            end = now
        elif time_type == "recent_days" and time_value:
            start = today - timedelta(days=time_value)
            end = now
        elif time_type == "recent_weeks" and time_value:
            start = today - timedelta(weeks=time_value)
            end = now
        elif time_type == "recent_months" and time_value:
            start = today - timedelta(days=time_value * 30)
            end = now
        else:
            start = today - timedelta(days=7)
            end = now

        return start, end


# 全局单例
_entity_extractor: Optional[EntityExtractor] = None


def get_entity_extractor() -> EntityExtractor:
    """获取实体抽取器单例"""
    global _entity_extractor
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor()
    return _entity_extractor


def extract_entities(text: str) -> Dict[str, Any]:
    """快捷函数：提取实体"""
    extractor = get_entity_extractor()
    return extractor.extract(text)
