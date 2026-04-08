"""
异常检测洞察
"""
from typing import Dict, List, Any, Optional, Tuple
import numpy as np


def detect_anomaly(data: List[float], threshold_multiplier: float = 2.0) -> Dict[str, Any]:
    """
    检测异常值（基于标准差）

    Args:
        data: 时序数据列表
        threshold_multiplier: 阈值倍数，默认2倍标准差

    Returns:
        {
            "detected": True/False,
            "anomalies": [
                {"date": "2024-03-15", "index": 5, "value": 18.5, "threshold": 15.0, "reason": "高于均值30%"}
            ],
            "stats": {"mean": 12.5, "std": 3.0, "min": 8.0, "max": 18.5}
        }
    """
    if not data or len(data) < 3:
        return {
            "detected": False,
            "anomalies": [],
            "stats": {"mean": 0, "std": 0, "min": 0, "max": 0},
            "message": "数据不足，无法进行异常检测"
        }

    values = np.array(data)
    mean = np.mean(values)
    std = np.std(values)

    # 计算阈值
    upper_threshold = mean + threshold_multiplier * std
    lower_threshold = mean - threshold_multiplier * std

    anomalies = []
    for i, value in enumerate(data):
        if value > upper_threshold:
            deviation = ((value - mean) / mean * 100) if mean > 0 else 0
            anomalies.append({
                "index": i,
                "value": round(float(value), 2),
                "threshold": round(float(upper_threshold), 2),
                "reason": f"高于均值 {deviation:.0f}%"
            })
        elif value < lower_threshold:
            deviation = ((mean - value) / mean * 100) if mean > 0 else 0
            anomalies.append({
                "index": i,
                "value": round(float(value), 2),
                "threshold": round(float(lower_threshold), 2),
                "reason": f"低于均值 {deviation:.0f}%"
            })

    return {
        "detected": len(anomalies) > 0,
        "anomalies": anomalies[:5],  # 最多返回5个异常
        "stats": {
            "mean": round(float(mean), 2),
            "std": round(float(std), 2),
            "min": round(float(np.min(values)), 2),
            "max": round(float(np.max(values)), 2)
        }
    }


def detect_anomaly_detail(data: List[float], metric_type: str = "roas") -> str:
    """生成异常检测详情描述"""
    result = detect_anomaly(data)

    if not result["detected"]:
        return "未检测到明显异常"

    stats = result["stats"]
    anomalies = result["anomalies"]

    desc = f"检测到 {len(anomalies)} 个异常点（均值 {stats['mean']}，标准差 {stats['std']}）："

    for a in anomalies[:3]:  # 最多描述3个
        desc += f"\n- 第{a['index']+1}期 {a['value']}，{a['reason']}"

    return desc
