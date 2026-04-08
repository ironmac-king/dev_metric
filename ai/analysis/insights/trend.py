"""
趋势分析洞察
"""
from typing import Dict, List, Any, Optional
import numpy as np
from . import assess_metric


def compute_trend(data: List[float], metric_type: str = "roas") -> Dict[str, Any]:
    """
    计算趋势分析

    Args:
        data: 时序数据列表，如 [3.2, 3.1, 3.5, 3.8, 3.5]
        metric_type: 指标类型（roas/acos/cpc/ctr）

    Returns:
        {
            "direction": "up"/"down"/"stable",
            "change_rate": "+12.5%",
            "current_value": 3.5,
            "previous_avg": 3.1,
            "assessment": "优秀"/"良好"/"一般"/"较差"
        }
    """
    if not data or len(data) < 2:
        return {
            "direction": "stable",
            "change_rate": "0%",
            "current_value": data[0] if data else 0,
            "previous_avg": 0,
            "assessment": "数据不足"
        }

    current_value = float(data[-1])

    # 计算前期平均值（排除最后几个点）
    lookback = min(3, len(data) - 1)
    previous_values = data[:-lookback] if lookback > 0 else data[:-1]
    previous_avg = np.mean(previous_values) if previous_values else current_value

    # 计算变化率
    if previous_avg > 0:
        change_rate = ((current_value - previous_avg) / previous_avg) * 100
    else:
        change_rate = 0

    # 判断方向
    if abs(change_rate) < 5:
        direction = "stable"
    elif change_rate > 0:
        direction = "up"
    else:
        direction = "down"

    return {
        "direction": direction,
        "change_rate": f"{change_rate:+.1f}%",
        "current_value": round(current_value, 2),
        "previous_avg": round(previous_avg, 2),
        "assessment": assess_metric(current_value, metric_type)
    }


def compute_trend_detail(data: List[float], metric_type: str = "roas") -> str:
    """生成趋势详情描述"""
    trend = compute_trend(data, metric_type)

    direction_desc = {
        "up": "呈上升趋势",
        "down": "呈下降趋势",
        "stable": "保持稳定"
    }

    desc = f"{direction_desc.get(trend['direction'], '趋势不明')}"
    desc += f"，当前值 {trend['current_value']}"
    desc += f"，较前期平均 {trend['change_rate']}"
    desc += f"，整体{trend['assessment']}"

    return desc
