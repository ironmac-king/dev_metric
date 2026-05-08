"""
预测洞察 - 基于简单移动平均
"""
from typing import Dict, List, Any
import numpy as np


def compute_forecast(data: List[float], periods: int = 1, window: int = 3) -> Dict[str, Any]:
    """
    简单移动平均预测

    Args:
        data: 时序数据列表
        periods: 预测期数，默认1
        window: 移动平均窗口大小，默认3

    Returns:
        {
            "forecast": [3.6],  # 预测值列表
            "confidence": "medium",  # low/medium/high
            "trend": "stable",  # up/down/stable
            "description": "下期预测值 3.6，趋势平稳"
        }
    """
    if not data or len(data) < window:
        return {
            "forecast": [],
            "confidence": "low",
            "trend": "unknown",
            "description": "数据不足，无法进行预测"
        }

    values = np.array(data)

    # 计算移动平均
    last_values = values[-window:]
    forecast_value = np.mean(last_values)

    # 判断趋势（基于最近几期变化）
    if len(values) >= 3:
        recent_trend = np.polyfit(range(3), values[-3:], 1)[0]
        if recent_trend > 0.1:
            trend = "up"
        elif recent_trend < -0.1:
            trend = "down"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # 计算置信度（基于数据波动性）
    std = np.std(values[-window:])
    if std < np.mean(values) * 0.1:
        confidence = "high"
    elif std < np.mean(values) * 0.2:
        confidence = "medium"
    else:
        confidence = "low"

    forecast_list = []
    current = forecast_value
    for _ in range(periods):
        forecast_list.append(round(float(current), 2))

    trend_desc = {"up": "上升", "down": "下降", "stable": "平稳"}
    confidence_desc = {"high": "高", "medium": "中", "low": "低"}

    description = f"下期预测值 {forecast_list[0]}"
    description += f"，趋势{trend_desc.get(trend, '平稳')}"
    description += f"，预测置信度{trend_desc.get(confidence, '中')}"

    return {
        "forecast": forecast_list,
        "confidence": confidence,
        "trend": trend,
        "description": description
    }


def compute_forecast_detail(data: List[float]) -> str:
    """生成预测详情描述"""
    result = compute_forecast(data)

    if not result["forecast"]:
        return result["description"]

    return result["description"]
