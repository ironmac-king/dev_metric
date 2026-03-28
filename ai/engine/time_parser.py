"""
时间表达式解析器 - 支持行业标准时间语义
- 绝对月份："7月"、"12月"
- 带年份："2024年7月"
- 季度："Q1"、"一季度"
- 日期范围："7月1日-7月15日"
- 相对时间：保留现有逻辑
"""
import re
from typing import Optional, Dict, Any
from datetime import datetime


class TimeParser:
    """时间表达式解析器 - 行业标准 TimeML 规范"""

    def __init__(self, current_year: int = None):
        # 默认使用当前年份
        self.current_year = current_year or datetime.now().year

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        """
        解析时间表达式
        返回: {
            "type": "absolute_month",  # absolute_month, quarter, range, relative
            "start": "2026-07-01",
            "end": "2026-07-31",
            "original": "7月",
            "has_explicit_year": False,
            "time_key": "2026-07"  # 用于 SQL 替换
        }
        """
        if not text:
            return None

        text = text.strip()

        # 1. 带年份的绝对月份: "2024年7月"
        result = self._parse_year_month(text)
        if result:
            return result

        # 2. 日期范围: "7月1日-7月15日" (优先检查，避免被月份匹配)
        result = self._parse_date_range(text)
        if result:
            return result

        # 3. 绝对月份: "7月"、"12月" (但不是日期范围的一部分)
        result = self._parse_month_only(text)
        if result:
            return result

        # 4. 季度: "Q1"、"一季度"、"Q2"
        result = self._parse_quarter(text)
        if result:
            return result

        # 5. 相对时间（调用原有逻辑）
        result = self._parse_relative(text)
        if result:
            return result

        return None

    def _parse_year_month(self, text: str) -> Optional[Dict[str, Any]]:
        """解析带年份的月份: 2024年7月"""
        match = re.search(r"(\d{4})年(\d{1,2})月", text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            if 1 <= month <= 12:
                return self._build_month_result(year, month, text, has_explicit_year=True)
        return None

    def _parse_month_only(self, text: str) -> Optional[Dict[str, Any]]:
        """解析绝对月份: 7月"""
        # 如果文本包含相对时间前缀，不应该匹配绝对月份
        relative_prefixes = ["最近", "近", "过去", "上前", "往前"]
        for prefix in relative_prefixes:
            if prefix in text:
                return None

        match = re.search(r"(\d{1,2})月", text)
        if match:
            month = int(match.group(1))
            if 1 <= month <= 12:
                # 推断年份
                year = self._infer_year(text)
                has_explicit_year = any(w in text for w in ["去年", "今年", "明年", "本年", "上年"])
                return self._build_month_result(year, month, text, has_explicit_year=has_explicit_year)
        return None

    def _parse_quarter(self, text: str) -> Optional[Dict[str, Any]]:
        """解析季度: Q1、一季度"""
        quarter_map = {
            "Q1": (1, 3, 1), "Q2": (4, 6, 2), "Q3": (7, 9, 3), "Q4": (10, 12, 4),
            "一季度": (1, 3, 1), "二季度": (4, 6, 2), "三季度": (7, 9, 3), "四季度": (10, 12, 4)
        }

        for q, (start_month, end_month, q_num) in quarter_map.items():
            if q in text:
                year = self._infer_year(text)
                # 检查是否有"去年"、"今年"等修饰
                if "去年" in text or "上年" in text:
                    year -= 1
                elif "明年" in text:
                    year += 1

                start_date = f"{year}-{start_month:02d}-01"
                # 计算季度最后一天
                if end_month == 12:
                    end_date = f"{year}-12-31"
                else:
                    end_date = f"{year}-{end_month + 1:02d}-01"

                # 修正 end_date 为季度最后一天
                from calendar import monthrange
                _, last_day = monthrange(year, end_month)
                end_date = f"{year}-{end_month:02d}-{last_day}"

                return {
                    "type": "quarter",
                    "start": start_date,
                    "end": end_date,
                    "original": text,
                    "has_explicit_year": "去年" in text or "今年" in text or "明年" in text or "本年" in text,
                    "time_key": f"Q{q_num}_{year}",
                    "quarter": q_num,
                    "year": year
                }
        return None

    def _parse_date_range(self, text: str) -> Optional[Dict[str, Any]]:
        """解析日期范围: 7月1日-7月15日"""
        # 匹配 "7月1日-7月15日" 或 "7月1-15日"
        # 正则: 第一个日期(月、日) - 第二个日期(月、日)
        match = re.search(r"(\d{1,2})月(\d{1,2})日?[-到](\d{1,2})月(\d{1,2})日?", text)
        if match:
            start_month, start_day, end_month, end_day = match.groups()
            start_month, start_day, end_month, end_day = int(start_month), int(start_day), int(end_month), int(end_day)
            year = self._infer_year(text)

            from calendar import monthrange
            _, start_last = monthrange(year, start_month)
            _, end_last = monthrange(year, end_month)

            start_day = min(start_day, start_last)
            end_day = min(end_day, end_last)

            return {
                "type": "date_range",
                "start": f"{year}-{start_month:02d}-{start_day:02d}",
                "end": f"{year}-{end_month:02d}-{end_day:02d}",
                "original": text,
                "has_explicit_year": False,
                "time_key": f"{year}-{start_month:02d}-{start_day:02d}_{year}-{end_month:02d}-{end_day:02d}"
            }
        return None

    def _parse_relative(self, text: str) -> Optional[Dict[str, Any]]:
        """解析相对时间（保留原有逻辑）"""
        # 固定时间词
        fixed_time_map = {
            r"昨天|昨日": ("yesterday", -1, 0),
            r"今天|今日|本日": ("today", 0, 0),
            r"明天|明日": ("tomorrow", 1, 0),
            r"本周|这周": ("this_week", 0, 0),
            r"本月|这月": ("this_month", 0, 0),
            r"上周|上一周": ("last_week", -1, 0),
            r"上月|上一月|上个月|上个月份": ("last_month", -1, 0),
            r"去年|上年": ("last_year", -1, 0),
            r"本年|今年": ("this_year", 0, 0),
        }

        for pattern, (time_key, year_offset, month_offset) in fixed_time_map.items():
            if re.search(pattern, text):
                # 计算目标月份
                # 使用 0-based 月份: 0=1月, 11=12月
                current_month_index = (self.current_year * 12 + datetime.now().month) - 1
                target_month_index = current_month_index + year_offset + month_offset

                # 转换回自然月份 (1-12) 和年份
                target_year = (target_month_index + 1) // 12
                actual_month = (target_month_index % 12) + 1
                if actual_month == 0:
                    actual_month = 12
                    target_year -= 1

                start, end = self._get_date_range(time_key, target_year, actual_month)
                return {
                    "type": "relative",
                    "start": start,
                    "end": end,
                    "original": text,
                    "has_explicit_year": True,
                    "time_key": time_key
                }

        # 动态时间: 最近N天/周/月/年
        patterns = [
            (r"最近(\d+)天", "last_{}_days", "days"),
            (r"最近(\d+)周", "last_{}_weeks", "weeks"),
            (r"最近(\d+)月", "last_{}_months", "months"),
            (r"最近(\d+)年", "last_{}_years", "years"),
            (r"过去(\d+)天", "past_{}_days", "days"),
            (r"过去(\d+)周", "past_{}_weeks", "weeks"),
            (r"过去(\d+)月", "past_{}_months", "months"),
            (r"过去(\d+)年", "past_{}_years", "years"),
            (r"近(\d+)天", "last_{}_days", "days"),
            (r"近(\d+)周", "last_{}_weeks", "weeks"),
            (r"近(\d+)月", "last_{}_months", "months"),
            (r"近(\d+)年", "last_{}_years", "years"),
        ]

        for pattern, template, unit in patterns:
            match = re.search(pattern, text)
            if match:
                num = int(match.group(1))
                time_key = template.format(num)

                from datetime import timedelta
                today = datetime.now()
                if unit == "days":
                    start = (today - timedelta(days=num)).strftime("%Y-%m-%d")
                    end = today.strftime("%Y-%m-%d")
                elif unit == "weeks":
                    start = (today - timedelta(weeks=num)).strftime("%Y-%m-%d")
                    end = today.strftime("%Y-%m-%d")
                elif unit == "months":
                    # 简化处理
                    start = (today - timedelta(days=num * 30)).strftime("%Y-%m-%d")
                    end = today.strftime("%Y-%m-%d")
                elif unit == "years":
                    start = (today - timedelta(days=num * 365)).strftime("%Y-%m-%d")
                    end = today.strftime("%Y-%m-%d")

                return {
                    "type": "relative",
                    "start": start,
                    "end": end,
                    "original": text,
                    "has_explicit_year": True,
                    "time_key": time_key
                }

        # 近几/前几
        if re.search(r"近几?(天|周|月|年)", text):
            if "天" in text:
                return {"type": "relative", "start": None, "end": None, "original": text, "has_explicit_year": True, "time_key": "last_3_days"}
            elif "周" in text:
                return {"type": "relative", "start": None, "end": None, "original": text, "has_explicit_year": True, "time_key": "last_3_weeks"}
            elif "月" in text:
                return {"type": "relative", "start": None, "end": None, "original": text, "has_explicit_year": True, "time_key": "last_3_months"}
            elif "年" in text:
                return {"type": "relative", "start": None, "end": None, "original": text, "has_explicit_year": True, "time_key": "last_3_years"}

        return None

    def _infer_year(self, text: str) -> int:
        """推断年份"""
        if "去年" in text or "上年" in text:
            return self.current_year - 1
        if "明年" in text:
            return self.current_year + 1
        if "今年" in text or "本年" in text:
            return self.current_year
        return self.current_year  # 默认今年

    def _build_month_result(self, year: int, month: int, original: str, has_explicit_year: bool) -> Dict[str, Any]:
        """构建月份解析结果"""
        from calendar import monthrange
        _, last_day = monthrange(year, month)

        return {
            "type": "absolute_month",
            "start": f"{year}-{month:02d}-01",
            "end": f"{year}-{month:02d}-{last_day}",
            "original": original,
            "has_explicit_year": has_explicit_year,
            "time_key": f"{year}-{month:02d}",
            "year": year,
            "month": month
        }

    def _get_date_range(self, time_key: str, year: int, month: int) -> tuple:
        """获取日期范围"""
        from calendar import monthrange

        if time_key == "yesterday":
            from datetime import timedelta
            yesterday = datetime.now() - timedelta(days=1)
            return (yesterday.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))
        elif time_key == "today":
            today = datetime.now()
            return (today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        elif time_key == "this_week":
            from datetime import timedelta
            today = datetime.now()
            start = today - timedelta(days=today.weekday())
            return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        elif time_key == "this_month":
            from calendar import monthrange
            _, last_day = monthrange(year, month)
            return (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day}")
        elif time_key == "last_week":
            from datetime import timedelta
            today = datetime.now()
            start = today - timedelta(days=7)
            return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        elif time_key == "last_month":
            if month == 1:
                return (f"{year-1}-12-01", f"{year-1}-12-31")
            else:
                _, last_day = monthrange(year, month - 1)
                return (f"{year}-{month-1:02d}-01", f"{year}-{month-1:02d}-{last_day}")
        elif time_key == "last_year":
            return (f"{year-1}-01-01", f"{year-1}-12-31")
        elif time_key == "this_year":
            today = datetime.now()
            return (f"{today.year}-01-01", today.strftime("%Y-%m-%d"))

        return (None, None)

    def needs_year_clarification(self, time_info: Dict[str, Any]) -> bool:
        """判断是否需要追问年份"""
        if not time_info:
            return False

        # 绝对月份但没有明确年份修饰词时，需要追问
        if time_info.get("type") == "absolute_month":
            if not time_info.get("has_explicit_year"):
                # "7月" 这种没有"去年"、"今年"修饰的，需要追问
                return True
        return False

    def build_year_clarification(self, time_info: Dict[str, Any]) -> str:
        """构建年份追问问题"""
        month = time_info.get("original", "").replace("月", "").replace("日", "")
        current_year = self.current_year
        last_year = self.current_year - 1

        if time_info.get("type") == "absolute_month":
            return f"请问您说的是{current_year}年{month}月还是{last_year}年{month}月？"

        return "请问您想查询哪个时间段？"


# 单元测试
if __name__ == "__main__":
    parser = TimeParser(current_year=2026)

    test_cases = [
        "7月",
        "12月",
        "2024年7月",
        "去年7月",
        "今年7月",
        "Q1",
        "一季度",
        "Q2",
        "近7天",
        "最近30天",
        "过去3月",  # 测试相对时间-过去N月
        "7月1日-7月15日",
        "上月",
        "本周",
    ]

    print("=== 时间表达式解析测试 ===\n")
    for text in test_cases:
        result = parser.parse(text)
        print(f"输入: {text}")
        print(f"结果: {result}")
        if parser.needs_year_clarification(result):
            print(f"追问: {parser.build_year_clarification(result)}")
        print("-" * 50)
