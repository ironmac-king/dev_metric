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
from datetime import datetime, timedelta


class TimeParser:
    """时间表达式解析器 - 行业标准 TimeML 规范"""

    # 中文数字映射
    CHINESE_DIGITS = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '零': 0, '两': 2, '半': 0.5,
    }

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

        # 类型检查：防止传入 dict 等非字符串类型
        if not isinstance(text, str):
            return None

        text = text.strip()

        # 0. 财务术语 YTD/MTD/WTD（需优先检查）
        result = self._parse_financial_term(text)
        if result:
            return result

        # 1. 带年份的绝对月份: "2024年7月" 或 "23年7月"
        result = self._parse_year_month(text)
        if result:
            return result

        # 2. 日期范围: "7月1日-7月15日" (优先检查，避免被月份匹配)
        result = self._parse_date_range(text)
        if result:
            return result

        # 3. 具体日期: "4月2日"、"7月15日" (在月份之前检查，避免被"4月"匹配)
        result = self._parse_specific_date(text)
        if result:
            return result

        # 4. 绝对月份: "7月"、"12月" (但不是日期范围的一部分)
        result = self._parse_month_only(text)
        if result:
            return result

        # 4. 季度: "Q1"、"一季度"、"Q2"
        result = self._parse_quarter(text)
        if result:
            return result

        # 5. 半年: "上半年"、"下半年"
        result = self._parse_half_year(text)
        if result:
            return result

        # 6. 相对时间（调用原有逻辑）
        result = self._parse_relative(text)
        if result:
            return result

        return None

    def _parse_financial_term(self, text: str) -> Optional[Dict[str, Any]]:
        """解析财务术语: YTD/MTD/WTD"""
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        # YTD: Year to Date，年初至今
        if re.search(r"YTD|年初至今", text, re.IGNORECASE):
            return {
                "type": "financial_term",
                "start": f"{today.year}-01-01",
                "end": yesterday.strftime("%Y-%m-%d"),
                "original": text,
                "has_explicit_year": True,
                "time_key": f"YTD_{today.year}"
            }

        # MTD: Month to Date，月初至今
        if re.search(r"MTD|月初至今", text, re.IGNORECASE):
            return {
                "type": "financial_term",
                "start": f"{today.year}-{today.month:02d}-01",
                "end": yesterday.strftime("%Y-%m-%d"),
                "original": text,
                "has_explicit_year": True,
                "time_key": f"MTD_{today.year}_{today.month:02d}"
            }

        # WTD: Week to Date，周初至今
        if re.search(r"WTD|周初至今", text, re.IGNORECASE):
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday)
            return {
                "type": "financial_term",
                "start": week_start.strftime("%Y-%m-%d"),
                "end": yesterday.strftime("%Y-%m-%d"),
                "original": text,
                "has_explicit_year": True,
                "time_key": f"WTD_{today.year}_{today.month:02d}_{today.day}"
            }

        return None

    def _parse_year_month(self, text: str) -> Optional[Dict[str, Any]]:
        """解析带年份的月份: 2024年7月、23年7月"""
        # 四位数年份: 2024年7月
        match = re.search(r"(\d{4})年(\d{1,2})月", text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            if 1 <= month <= 12:
                return self._build_month_result(year, month, match.group(0), has_explicit_year=True)

        # 两位数年份: 23年7月、24年
        match = re.search(r"(\d{2})年(\d{1,2})?月?", text)
        if match:
            year_short = int(match.group(1))
            # 补全为四位数: 23 -> 2023, 24 -> 2024
            year = 2000 + year_short if year_short < 100 else year_short
            month_str = match.group(2)
            if month_str:
                month = int(month_str)
                if 1 <= month <= 12:
                    return self._build_month_result(year, month, match.group(0), has_explicit_year=True)
            else:
                # 只有年份没有月份: 23年 -> 2023年全年
                return {
                    "type": "year_short",
                    "start": f"{year}-01-01",
                    "end": f"{year}-12-31",
                    "original": match.group(0),
                    "has_explicit_year": True,
                    "time_key": f"{year}",
                    "year": year
                }
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
                return self._build_month_result(year, month, match.group(0), has_explicit_year=has_explicit_year)
        return None

    def _parse_quarter(self, text: str) -> Optional[Dict[str, Any]]:
        """解析季度: Q1、一季度"""
        quarter_map = {
            "Q1": (1, 3, 1), "Q2": (4, 6, 2), "Q3": (7, 9, 3), "Q4": (10, 12, 4),
            "一季度": (1, 3, 1), "二季度": (4, 6, 2), "三季度": (7, 9, 3), "四季度": (10, 12, 4)
        }

        for q, (start_month, end_month, q_num) in quarter_map.items():
            if q in text:
                # _infer_year 已经处理了"去年"/"今年"/"明年"的年份推断，无需重复调整
                year = self._infer_year(text)

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

    def _parse_half_year(self, text: str) -> Optional[Dict[str, Any]]:
        """解析半年: 上半年、下半年"""
        if "上半年" not in text and "下半年" not in text:
            return None

        year = self._infer_year(text)

        # 注意：_infer_year 已经处理了"去年"/"今年"等修饰词的年份计算
        # 这里不需要再调整 year，直接使用 _infer_year 的返回值即可

        if "上半年" in text:
            from calendar import monthrange
            _, last_day = monthrange(year, 6)
            return {
                "type": "half_year",
                "start": f"{year}-01-01",
                "end": f"{year}-06-{last_day}",
                "original": text,
                "has_explicit_year": "去年" in text or "今年" in text or "明年" in text or "本年" in text or "上年" in text,
                "time_key": f"first_half_{year}",
                "half_year": 1,
                "year": year
            }
        elif "下半年" in text:
            from calendar import monthrange
            _, last_day = monthrange(year, 12)
            return {
                "type": "half_year",
                "start": f"{year}-07-01",
                "end": f"{year}-12-{last_day}",
                "original": text,
                "has_explicit_year": "去年" in text or "今年" in text or "明年" in text or "本年" in text or "上年" in text,
                "time_key": f"second_half_{year}",
                "half_year": 2,
                "year": year
            }
        return None

    def _parse_date_range(self, text: str) -> Optional[Dict[str, Any]]:
        """解析日期范围: 7月1日-7月15日 或 7月至9月"""
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
                "original": match.group(0),
                "has_explicit_year": False,
                "time_key": f"{year}-{start_month:02d}-{start_day:02d}_{year}-{end_month:02d}-{end_day:02d}"
            }

        # 匹配月份范围: "7月至9月" 或 "7月到9月"
        match = re.search(r"(\d{1,2})月[-到](\d{1,2})月", text)
        if match:
            start_month, end_month = int(match.group(1)), int(match.group(2))
            if 1 <= start_month <= 12 and 1 <= end_month <= 12:
                year = self._infer_year(text)
                from calendar import monthrange
                _, start_last = monthrange(year, start_month)
                _, end_last = monthrange(year, end_month)

                return {
                    "type": "date_range",
                    "start": f"{year}-{start_month:02d}-01",
                    "end": f"{year}-{end_month:02d}-{end_last}",
                    "original": match.group(0),
                    "has_explicit_year": False,
                    "time_key": f"{year}-{start_month:02d}_{year}-{end_month:02d}"
                }
        return None

    def _parse_specific_date(self, text: str) -> Optional[Dict[str, Any]]:
        """解析具体日期: 4月2日、7月15日（不是日期范围）"""
        # 匹配 "4月2日" 格式，但不匹配范围（如 "7月1日-7月15日"）
        # 负向前瞻：确保后面没有 "日-" 或 "日到"
        match = re.search(r"(\d{1,2})月(\d{1,2})日(?![-到])", text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                year = self._infer_year(text)
                from calendar import monthrange
                _, last_day = monthrange(year, month)
                day = min(day, last_day)  # 避免 2 月 30 号等问题
                return {
                    "type": "date_range",  # 用 date_range 类型表示具体日期
                    "start": f"{year}-{month:02d}-{day:02d}",
                    "end": f"{year}-{month:02d}-{day:02d}",
                    "original": match.group(0),
                    "has_explicit_year": False,
                    "time_key": f"{year}-{month:02d}-{day:02d}"
                }
        return None

    def _chinese_to_int(self, s: str) -> Optional[float]:
        """将中文数字转换为整数或浮点数"""
        if not s:
            return None
        if s in ('零', '两'):
            return self.CHINESE_DIGITS.get(s, 0)

        # 预处理：数字转为阿拉伯数字，量词保留
        chars = []
        for c in s:
            if c in '十百千万':
                # 量词（十/百/千/万）直接保留作为标记
                chars.append(c)
            elif c in self.CHINESE_DIGITS:
                digit = self.CHINESE_DIGITS[c]
                if digit < 1:
                    # 特殊处理：半(0.5)等小于1的值，直接返回
                    return digit
                elif digit < 10:  # 0-9 的数字才转为字符
                    chars.append(str(digit))
                # 十(10) 等不转为字符串（已由上面处理）
            elif c == '零':
                pass  # 忽略
            else:
                return None

        if not chars:
            return None

        # 解析：遇到十/百/千时，前面的数字乘以对应值
        result = 0
        current = 0
        for i, c in enumerate(chars):
            if c.isdigit():
                current = current * 10 + int(c)
            elif c == '十':
                result += current * 10
                current = 0
            elif c == '百':
                result += current * 100
                current = 0
            elif c == '千':
                result += current * 1000
                current = 0
        result += current
        return result if result > 0 else None

    def _parse_relative(self, text: str) -> Optional[Dict[str, Any]]:
        """解析相对时间（保留原有逻辑）"""
        from calendar import monthrange

        # 特殊时间词处理（需优先于 fixed_time_map 检查，避免子串匹配问题）
        special_time_map = {
            r"上上月|上上个月|上上个月份": ("last_month", -2, 0),  # 上上月 = 上上个月
        }

        for pattern, (time_key, year_offset, month_offset) in special_time_map.items():
            match = re.search(pattern, text)
            if match:
                current_month_index = (self.current_year * 12 + datetime.now().month) - 1
                target_month_index = current_month_index + year_offset + month_offset
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
                    "original": match.group(0),
                    "has_explicit_year": True,
                    "time_key": time_key
                }

        # ===== 日级特殊处理（必须用 timedelta，不能用 year_offset）=====
        today = datetime.now()
        if re.search(r"昨天|昨日", text):
            day = today - timedelta(days=1)
            return {"type": "relative", "start": day.strftime("%Y-%m-%d"), "end": day.strftime("%Y-%m-%d"), "original": text, "has_explicit_year": True, "time_key": "yesterday"}
        if re.search(r"今天|今日|本日|今儿", text):
            return {"type": "relative", "start": today.strftime("%Y-%m-%d"), "end": today.strftime("%Y-%m-%d"), "original": text, "has_explicit_year": True, "time_key": "today"}
        if re.search(r"明天|明日|明儿", text):
            day = today + timedelta(days=1)
            return {"type": "relative", "start": day.strftime("%Y-%m-%d"), "end": day.strftime("%Y-%m-%d"), "original": text, "has_explicit_year": True, "time_key": "tomorrow"}
        if re.search(r"前日|前天|昨儿", text):
            day = today - timedelta(days=2)
            return {"type": "relative", "start": day.strftime("%Y-%m-%d"), "end": day.strftime("%Y-%m-%d"), "original": text, "has_explicit_year": True, "time_key": "day_before_yesterday"}
        if re.search(r"后天|后日", text):
            day = today + timedelta(days=2)
            return {"type": "relative", "start": day.strftime("%Y-%m-%d"), "end": day.strftime("%Y-%m-%d"), "original": text, "has_explicit_year": True, "time_key": "day_after_tomorrow"}
        if re.search(r"大前天|大前日", text):
            day = today - timedelta(days=3)
            return {"type": "relative", "start": day.strftime("%Y-%m-%d"), "end": day.strftime("%Y-%m-%d"), "original": text, "has_explicit_year": True, "time_key": "three_days_ago"}
        if re.search(r"大后天|大后日", text):
            day = today + timedelta(days=3)
            return {"type": "relative", "start": day.strftime("%Y-%m-%d"), "end": day.strftime("%Y-%m-%d"), "original": text, "has_explicit_year": True, "time_key": "three_days_later"}

        # 星期几处理: 周一、周五（表示本周的星期几）
        weekday_map = {
            r"周一|星期一": 0,  # Monday
            r"周二|星期二": 1,
            r"周三|星期三": 2,
            r"周四|星期四": 3,
            r"周五|星期五": 4,
            r"周六|星期六": 5,
            r"周日|星期日|周末": 6,  # Python 中 Sunday = 6
        }
        for pattern, target_weekday in weekday_map.items():
            if re.search(pattern, text):
                today = datetime.now()
                days_since_target = (today.weekday() - target_weekday) % 7
                target_date = today - timedelta(days=days_since_target)
                return {
                    "type": "relative",
                    "start": target_date.strftime("%Y-%m-%d"),
                    "end": target_date.strftime("%Y-%m-%d"),
                    "original": text,
                    "has_explicit_year": True,
                    "time_key": f"this_week_{pattern.split('|')[0]}"
                }

        # 季度特殊处理（不能用 month_offset，会算错）
        today = datetime.now()
        current_quarter = (today.month - 1) // 3 + 1

        if "本季度" in text or "本季" in text:
            q_start_month = (current_quarter - 1) * 3 + 1
            _, q_end_day = monthrange(today.year, q_start_month + 2)
            start = f"{today.year}-{q_start_month:02d}-01"
            end = f"{today.year}-{q_start_month+2:02d}-{q_end_day}"
            return {"type": "relative", "start": start, "end": end, "original": text, "has_explicit_year": True, "time_key": "this_quarter"}

        if "上季度" in text:
            if current_quarter == 1:
                # Q1的上季度是去年Q4
                start = f"{today.year-1}-10-01"
                end = f"{today.year-1}-12-31"
            else:
                q_start_month = (current_quarter - 2) * 3 + 1
                _, q_end_day = monthrange(today.year, q_start_month + 2)
                start = f"{today.year}-{q_start_month:02d}-01"
                end = f"{today.year}-{q_start_month+2:02d}-{q_end_day}"
            return {"type": "relative", "start": start, "end": end, "original": text, "has_explicit_year": True, "time_key": "last_quarter"}

        if "下季度" in text:
            if current_quarter == 4:
                # Q4的下季度是明年Q1
                start = f"{today.year+1}-01-01"
                end = f"{today.year+1}-03-31"
            else:
                q_start_month = current_quarter * 3 + 1
                _, q_end_day = monthrange(today.year, q_start_month + 2)
                start = f"{today.year}-{q_start_month:02d}-01"
                end = f"{today.year}-{q_start_month+2:02d}-{q_end_day}"
            return {"type": "relative", "start": start, "end": end, "original": text, "has_explicit_year": True, "time_key": "next_quarter"}

        # 固定时间词
        fixed_time_map = {
            # 周
            r"本周|这周|这个礼拜": ("this_week", 0, 0),
            r"上周|上一周|上个礼拜": ("last_week", -1, 0),
            r"上上周": ("week_before_last", -2, 0),
            r"下周|下个礼拜": ("next_week", 1, 0),
            r"下下周": ("week_after_next", 2, 0),
            # 月
            r"本月|当月|这月": ("this_month", 0, 0),
            r"上月|上一月|上个月|上个月份": ("last_month", -1, 0),
            r"下月": ("next_month", 1, 0),
            r"下下月": ("month_after_next", 2, 0),
            # 年（季度已在上方单独处理）
            r"去年|上年": ("last_year", -1, 0),
            r"本年|今年": ("this_year", 0, 0),
            r"明年": ("next_year", 1, 0),
            r"前年": ("year_before_last", -2, 0),
            r"后年": ("year_after_next", 2, 0),
        }

        for pattern, (time_key, year_offset, month_offset) in fixed_time_map.items():
            match = re.search(pattern, text)
            if match:
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
                    "original": match.group(0),
                    "has_explicit_year": True,
                    "time_key": time_key
                }

        # 动态时间: 最近N天/周/月/年（支持阿拉伯数字和中文数字）
        # 中文数字匹配: 一|二|三|四|五|六|七|八|九|十|零|两|半
        chinese_num = r"[零一二三四五六七八九十两半]"

        # 组合中文数字 (十一, 二十三, 半年等)
        chinese_num_compound = rf"{chinese_num}{chinese_num}*"

        # 特殊处理"半年"：因为"半年"在语义上=6个月，而不是0.5年
        # "近半年" = "近" + "半年" + "年"，其中"半年"表示6个月，不是1年
        # 如果直接让正则匹配"年"模式，会错误地把"半年"解析为1年
        match = re.search(r"近(半|半年)年|过去(半|半年)年", text)
        if match:
            today = datetime.now()
            start = (today - timedelta(days=180)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return {
                "type": "relative",
                "start": start,
                "end": end,
                "original": match.group(0),
                "has_explicit_year": True,
                "time_key": "last_6_months"
            }

        # 注意: 天/周/月/年 前可能有"个"字（如"一个月"）
        # template 用普通字符串配合 .format() 使用 {}
        patterns = [
            (rf"最近(\d+|{chinese_num_compound})个?天", r"last_{}_days", "days"),
            (rf"最近(\d+|{chinese_num_compound})个?周", r"last_{}_weeks", "weeks"),
            (rf"最近(\d+|{chinese_num_compound})个?月", r"last_{}_months", "months"),
            (rf"最近(\d+|{chinese_num_compound})个?年", r"last_{}_years", "years"),
            (rf"过去(\d+|{chinese_num_compound})个?天", r"past_{}_days", "days"),
            (rf"过去(\d+|{chinese_num_compound})个?周", r"past_{}_weeks", "weeks"),
            (rf"过去(\d+|{chinese_num_compound})个?月", r"past_{}_months", "months"),
            (rf"过去(\d+|{chinese_num_compound})个?年", r"past_{}_years", "years"),
            (rf"近(\d+|{chinese_num_compound})个?天", r"last_{}_days", "days"),
            (rf"近(\d+|{chinese_num_compound})个?日", r"last_{}_days", "days"),
            (rf"近(\d+|{chinese_num_compound})个?周", r"last_{}_weeks", "weeks"),
            (rf"近(\d+|{chinese_num_compound})个?月", r"last_{}_months", "months"),
            (rf"近(\d+|{chinese_num_compound})个?年", r"last_{}_years", "years"),
        ]

        for pattern, template, unit in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1)
                # 尝试阿拉伯数字，失败则转中文数字
                try:
                    num = int(num_str)
                except ValueError:
                    num = self._chinese_to_int(num_str)
                # 处理"半年"等情况：0.5 -> 6个月
                if num == 0.5:
                    num = 6
                time_key = template.format(int(num))

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
                    "original": match.group(0),
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
            yesterday = datetime.now() - timedelta(days=1)
            return (yesterday.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))
        elif time_key == "today":
            today = datetime.now()
            return (today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        elif time_key == "this_week":
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            start = today - timedelta(days=today.weekday())
            return (start.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))
        elif time_key == "this_month":
            yesterday = datetime.now() - timedelta(days=1)
            _, last_day = monthrange(year, month)
            month_start = datetime(year, month, 1)
            month_end = datetime(year, month, last_day)
            # T+1 数据逻辑：结束日期不能超过昨天
            # 但如果昨天在上月（月初第一天），则 end_date 不能小于 month_start
            if yesterday < month_start:
                end_date = yesterday
            else:
                end_date = min(month_end, yesterday)
            return (f"{year}-{month:02d}-01", end_date.strftime("%Y-%m-%d"))
        elif time_key == "last_week":
            today = datetime.now()
            start = today - timedelta(days=7)
            return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        elif time_key == "last_month":
            if month == 1:
                return (f"{year-1}-12-01", f"{year-1}-12-31")
            else:
                _, last_day = monthrange(year, month)
                return (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day}")
        elif time_key == "last_year":
            return (f"{year-1}-01-01", f"{year-1}-12-31")
        elif time_key == "this_year":
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            return (f"{today.year}-01-01", yesterday.strftime("%Y-%m-%d"))
        # ===== 新增：其他相对日期 =====
        elif time_key == "day_before_yesterday":
            day = datetime.now() - timedelta(days=2)
            return (day.strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d"))
        elif time_key == "day_after_tomorrow":
            day = datetime.now() + timedelta(days=2)
            return (day.strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d"))
        elif time_key == "three_days_ago":
            day = datetime.now() - timedelta(days=3)
            return (day.strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d"))
        elif time_key == "three_days_later":
            day = datetime.now() + timedelta(days=3)
            return (day.strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d"))
        # ===== 新增：周级别 =====
        elif time_key == "week_before_last":
            today = datetime.now()
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            last_monday = this_monday - timedelta(days=14)
            last_sunday = last_monday + timedelta(days=6)
            return (last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d"))
        elif time_key == "next_week":
            today = datetime.now()
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            next_monday = this_monday + timedelta(days=7)
            next_sunday = next_monday + timedelta(days=6)
            return (next_monday.strftime("%Y-%m-%d"), next_sunday.strftime("%Y-%m-%d"))
        elif time_key == "week_after_next":
            today = datetime.now()
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            next_monday = this_monday + timedelta(days=14)
            next_sunday = next_monday + timedelta(days=6)
            return (next_monday.strftime("%Y-%m-%d"), next_sunday.strftime("%Y-%m-%d"))
        # ===== 新增：月级别 =====
        elif time_key == "next_month":
            if month == 12:
                return (f"{year+1}-01-01", f"{year+1}-01-31")
            else:
                _, last_day = monthrange(year, month + 1)
                return (f"{year}-{month+1:02d}-01", f"{year}-{month+1:02d}-{last_day}")
        elif time_key == "month_after_next":
            if month == 11:
                return (f"{year+1}-01-01", f"{year+1}-01-31")
            elif month == 12:
                return (f"{year+1}-02-01", f"{year+1}-02-28")
            else:
                _, last_day = monthrange(year, month + 2)
                return (f"{year}-{month+2:02d}-01", f"{year}-{month+2:02d}-{last_day}")
        # ===== 新增：季度级别 =====
        elif time_key == "this_quarter":
            current_quarter = (datetime.now().month - 1) // 3 + 1
            start_month = (current_quarter - 1) * 3 + 1
            from calendar import monthrange
            _, last_day = monthrange(year, start_month + 2)
            return (f"{year}-{start_month:02d}-01", f"{year}-{start_month+2:02d}-{last_day}")
        elif time_key == "last_quarter":
            current_quarter = (datetime.now().month - 1) // 3 + 1
            if current_quarter == 1:
                return (f"{year-1}-10-01", f"{year-1}-12-31")
            else:
                start_month = (current_quarter - 2) * 3 + 1
                from calendar import monthrange
                _, last_day = monthrange(year, start_month + 2)
                return (f"{year}-{start_month:02d}-01", f"{year}-{start_month+2:02d}-{last_day}")
        elif time_key == "next_quarter":
            current_quarter = (datetime.now().month - 1) // 3 + 1
            if current_quarter == 4:
                return (f"{year+1}-01-01", f"{year+1}-03-31")
            else:
                start_month = current_quarter * 3 + 1
                from calendar import monthrange
                _, last_day = monthrange(year, start_month + 2)
                return (f"{year}-{start_month:02d}-01", f"{year}-{start_month+2:02d}-{last_day}")
        # ===== 新增：年级别 =====
        elif time_key == "next_year":
            return (f"{year+1}-01-01", f"{year+1}-12-31")
        elif time_key == "year_before_last":
            return (f"{year-2}-01-01", f"{year-2}-12-31")
        elif time_key == "year_after_next":
            return (f"{year+2}-01-01", f"{year+2}-12-31")

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

    def get_comparison_period(self, comparison_type: str = "环比") -> Dict[str, Any]:
        """
        计算对比周期（T+1数据逻辑）

        参数:
            comparison_type: "环比" 或 "同比"

        返回:
            {
                "current_date": "2026-04-01",      # 实际可查的最新日期
                "comparison_date": "2025-04-01",    # 对比日期
                "comparison_start": "2025-04-01",   # 对比日期起点
                "comparison_end": "2025-04-01",     # 对比日期终点（用于SQL查询）
            }
        """
        # T+1数据：今天只能查到昨天
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        current_date = yesterday.strftime("%Y-%m-%d")

        if comparison_type == "环比":
            # 环比上月：取上月1号
            if yesterday.month == 1:
                # 去年12月1号
                last_year = yesterday.year - 1
                last_month = 12
            else:
                last_year = yesterday.year
                last_month = yesterday.month - 1
            comparison_date = f"{last_year}-{last_month:02d}-01"
        else:
            # 同比去年：取去年同月1号
            last_year = yesterday.year - 1
            comparison_date = f"{last_year}-{yesterday.month:02d}-01"

        return {
            "current_date": current_date,
            "comparison_date": comparison_date,
            "comparison_start": comparison_date,
            "comparison_end": comparison_date,
        }


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
