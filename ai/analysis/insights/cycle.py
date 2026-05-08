"""
周期规律洞察
"""
from typing import Dict, List, Any
import numpy as np


def detect_cycle(data: List[float], expected_cycle: int = 7) -> Dict[str, Any]:
    """
    检测周期规律（如周末高峰、工作日低谷）

    Args:
        data: 时序数据列表
        expected_cycle: 预期周期长度（天），默认7天

    Returns:
        {
            "has_cycle": True/False,
            "cycle_length": 7,
            "pattern": "周末高峰型",
            "peak_positions": [5, 6, 12, 13],  # 周末位置
            "description": "周末两天数据普遍高于工作日20%"
        }
    """
    if not data or len(data) < expected_cycle * 2:
        return {
            "has_cycle": False,
            "cycle_length": expected_cycle,
            "pattern": "数据不足",
            "peak_positions": [],
            "description": "数据量不足，无法进行周期分析"
        }

    n = len(data)
    cycle_data = []

    # 按周期位置分组
    for pos in range(expected_cycle):
        group = [data[i] for i in range(pos, n, expected_cycle) if i < n]
        if group:
            cycle_data.append({
                "position": pos,
                "avg": np.mean(group),
                "values": group
            })

    if not cycle_data:
        return {
            "has_cycle": False,
            "cycle_length": expected_cycle,
            "pattern": "无法识别",
            "peak_positions": [],
            "description": "周期分析失败"
        }

    # 找出峰值位置
    avg_values = [c["avg"] for c in cycle_data]
    overall_avg = np.mean(avg_values)

    peak_positions = []
    for c in cycle_data:
        if c["avg"] > overall_avg * 1.1:  # 高于均值10%以上
            peak_positions.extend([c["position"]])

    # 判断周期类型
    if len(peak_positions) >= 2:
        if 5 in peak_positions or 6 in peak_positions:
            pattern = "周末高峰型"
            description = "周末数据普遍高于工作日"
        elif 0 in peak_positions or 1 in peak_positions:
            pattern = "月初高峰型"
            description = "月初数据普遍较高"
        else:
            pattern = "周期波动型"
            description = f"存在{expected_cycle}天周期波动"
    else:
        pattern = "无明显周期"
        description = "未发现明显周期规律"

    return {
        "has_cycle": len(peak_positions) > 0,
        "cycle_length": expected_cycle,
        "pattern": pattern,
        "peak_positions": peak_positions,
        "description": description,
        "cycle_data": [
            {"position": c["position"], "avg": round(c["avg"], 2)}
            for c in cycle_data
        ]
    }


def detect_cycle_detail(data: List[float]) -> str:
    """生成周期规律详情描述"""
    result = detect_cycle(data)

    if not result["has_cycle"]:
        return result["description"]

    return f"{result['pattern']}，{result['description']}"
