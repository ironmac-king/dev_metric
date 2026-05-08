"""
同比环比周期逻辑测试
验证所有场景的 YoY/MoM 日期计算是否正确
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import calendar


def compute_period_comparison(start_dt: date, end_dt: date, supports_yoy=True, supports_mom=True):
    """
    模拟 _generate_period_comparison_sql 的核心周期计算逻辑
    返回 (yoy_start, yoy_end, mom_start, mom_end)
    """
    end_dt_adjusted = end_dt

    # ===== YoY =====
    if supports_yoy:
        yoy_start = start_dt - relativedelta(years=1)
        yoy_end = end_dt_adjusted - relativedelta(years=1)
    else:
        yoy_start = yoy_end = None

    # ===== MoM =====
    mom_start = mom_end = None
    if supports_mom:
        # 判断月份是否完成
        _, month_last_day = calendar.monthrange(end_dt_adjusted.year, end_dt_adjusted.month)
        month_complete = end_dt_adjusted.day >= month_last_day

        # 判断季度是否完成
        month = end_dt_adjusted.month
        if month <= 3:
            quarter_end_month = 3
        elif month <= 6:
            quarter_end_month = 6
        elif month <= 9:
            quarter_end_month = 9
        else:
            quarter_end_month = 12
        _, quarter_last_day = calendar.monthrange(end_dt_adjusted.year, quarter_end_month)
        quarter_complete = (end_dt_adjusted.month == quarter_end_month and end_dt_adjusted.day >= quarter_last_day)

        # 计算当前周期天数
        period_days = (end_dt_adjusted - start_dt).days + 1

        # 判断 YTD
        is_ytd = (start_dt.month == 1 and start_dt.day == 1 and end_dt_adjusted.month < 12)
        is_short_ytd = is_ytd and period_days < 90

        if month_complete:
            mom_start = start_dt - relativedelta(months=1)
            mom_end = end_dt_adjusted - relativedelta(months=1)
        elif quarter_complete:
            mom_start = start_dt - relativedelta(months=3)
            mom_end = end_dt_adjusted - relativedelta(months=3)
        elif is_short_ytd:
            # 短 YTD（1/1-2/2，33天）：比较 Q4 同期
            last_year_end = end_dt_adjusted.replace(year=end_dt_adjusted.year - 1, month=12, day=31)
            mom_start = last_year_end - timedelta(days=period_days - 1)
            mom_end = last_year_end
        elif is_ytd:
            # 跨季度 YTD（1/1-4/2，122天）：比较 Q4 完整范围
            last_year_start = end_dt_adjusted.replace(year=end_dt_adjusted.year - 1, month=10, day=1)
            last_year_end = end_dt_adjusted.replace(year=end_dt_adjusted.year - 1, month=12, day=31)
            mom_start = last_year_start
            mom_end = last_year_end
        else:
            # 未完成月份/季度：环比 = 上月同期
            mom_start = start_dt - relativedelta(months=1)
            mom_end = end_dt_adjusted - relativedelta(months=1)

    return yoy_start, yoy_end, mom_start, mom_end


def test_scenario(name, start_str, end_str, expected_yoy, expected_mom):
    start = date.fromisoformat(start_str)
    end = date.fromisoformat(end_str)
    yoy_s, yoy_e, mom_s, mom_e = compute_period_comparison(start, end)

    yoy_ok = (str(yoy_s) == expected_yoy[0] and str(yoy_e) == expected_yoy[1]) if expected_yoy else (yoy_s is None)
    mom_ok = (str(mom_s) == expected_mom[0] and str(mom_e) == expected_mom[1]) if expected_mom else (mom_s is None)

    status = "✓" if (yoy_ok and mom_ok) else "✗"
    print(f"\n{status} {name}")
    print(f"  当前期: {start_str} ~ {end_str}")
    if expected_yoy:
        print(f"  YoY 期望: {expected_yoy[0]} ~ {expected_yoy[1]}  实际: {yoy_s} ~ {yoy_e}  {'✓' if yoy_ok else '✗'}")
    if expected_mom:
        print(f"  MoM 期望: {expected_mom[0]} ~ {expected_mom[1]}  实际: {mom_s} ~ {mom_e}  {'✓' if mom_ok else '✗'}")

    if not yoy_ok or not mom_ok:
        print("  >>> 测试失败 <<<")
    return yoy_ok and mom_ok


# ===== 测试用例 =====
# 格式: (场景名, 开始日期, 结束日期, (期望YoY开始, 期望YoY结束), (期望MoM开始, 期望MoM结束))
# YoY = 上年同期，MoM = 上期（根据 spec 逻辑）

tests = [
    # === 月度场景 ===
    ("当月完整 (3月完整)", "2026-03-01", "2026-03-31",
     ("2025-03-01", "2025-03-31"), ("2026-02-01", "2026-02-28")),

    ("当月不完整 (5月2日)", "2026-05-01", "2026-05-02",
     ("2025-05-01", "2025-05-02"), ("2026-04-01", "2026-04-02")),

    ("上个月完整 (2月)", "2026-02-01", "2026-02-28",
     ("2025-02-01", "2025-02-28"), ("2026-01-01", "2026-01-31")),

    # === 季度场景 ===
    ("Q1 完整 (1-3月)", "2026-01-01", "2026-03-31",
     ("2025-01-01", "2025-03-31"), ("2025-10-01", "2025-12-31")),

    ("Q2 不完整 (4/1-5/2)", "2026-04-01", "2026-05-02",
     ("2025-04-01", "2025-05-02"), ("2026-01-01", "2026-02-02")),

    ("Q2 完整 (4-6月)", "2026-04-01", "2026-06-30",
     ("2025-04-01", "2025-06-30"), ("2026-01-01", "2026-03-31")),

    ("Q3 完整 (7-9月)", "2026-07-01", "2026-09-30",
     ("2025-07-01", "2025-09-30"), ("2026-04-01", "2026-06-30")),

    ("Q4 完整 (10-12月)", "2026-10-01", "2026-12-31",
     ("2025-10-01", "2025-12-31"), ("2026-07-01", "2026-09-30")),

    # === 年度 YTD 场景 ===
    ("Year YTD 早期 (1/1-2/2, 33天)", "2026-01-01", "2026-02-02",
     ("2025-01-01", "2025-02-02"), ("2025-12-01", "2025-12-31")),

    ("Year YTD 中期 (1/1-5/2, 122天)", "2026-01-01", "2026-05-02",
     ("2025-01-01", "2025-05-02"), ("2025-10-01", "2025-12-31")),

    ("Year YTD Q1 边界 (1/1-3/31)", "2026-01-01", "2026-03-31",
     ("2025-01-01", "2025-03-31"), ("2025-10-01", "2025-12-31")),

    # === 跨年场景 ===
    ("跨年 2025/12 + 2026/01", "2025-12-01", "2026-01-31",
     ("2024-12-01", "2025-01-31"), ("2025-11-01", "2025-12-31")),

    # === 纯同比（无环比）场景 ===
    ("纯YoY 月度不完整", "2026-05-01", "2026-05-02",
     ("2025-05-01", "2025-05-02"), None),
]

print("=" * 70)
print("同比环比周期逻辑测试")
print("=" * 70)

passed = 0
failed = 0
for t in tests:
    ok = test_scenario(*t)
    if ok:
        passed += 1
    else:
        failed += 1

print("\n" + "=" * 70)
print(f"结果: {passed} 通过, {failed} 失败")
print("=" * 70)
