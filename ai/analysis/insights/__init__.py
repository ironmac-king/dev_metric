"""
洞察函数注册表
"""
from typing import Dict, Callable, Optional, Any
import numpy as np


# 行业基准值（供洞察计算使用）
INDUSTRY_BENCHMARKS = {
    "roas": {"excellent": 4.0, "good": 3.0, "average": 2.0},
    "acos": {"excellent": 15.0, "good": 20.0, "average": 25.0},
    "cpc": {"excellent": 1.5, "good": 2.5, "average": 3.5},
    "ctr": {"excellent": 1.5, "good": 1.0, "average": 0.5},
}


def get_insight_function(name: str) -> Optional[Callable]:
    """获取洞察函数"""
    return INSIGHT_FUNCTIONS.get(name)


def assess_metric(value: float, metric_type: str) -> str:
    """根据行业基准评估指标好坏"""
    if metric_type not in INDUSTRY_BENCHMARKS:
        return "unknown"

    benchmarks = INDUSTRY_BENCHMARKS[metric_type]

    # ROAS 和 CTR 越高越好
    if metric_type in ["roas", "ctr"]:
        if value >= benchmarks["excellent"]:
            return "优秀"
        elif value >= benchmarks["good"]:
            return "良好"
        elif value >= benchmarks["average"]:
            return "一般"
        else:
            return "较差"
    # ACOS 和 CPC 越低越好
    else:
        if value <= benchmarks["excellent"]:
            return "优秀"
        elif value <= benchmarks["good"]:
            return "良好"
        elif value <= benchmarks["average"]:
            return "一般"
        else:
            return "较差"


# 洞察函数注册表
INSIGHT_FUNCTIONS: Dict[str, Callable] = {}


def register_insight(name: str):
    """装饰器：注册洞察函数"""
    def decorator(func: Callable):
        INSIGHT_FUNCTIONS[name] = func
        return func
    return decorator


# 导入并注册所有洞察函数
from .trend import compute_trend
from .anomaly import detect_anomaly
from .cycle import detect_cycle
from .forecast import compute_forecast

INSIGHT_FUNCTIONS = {
    "trend": compute_trend,
    "anomaly": detect_anomaly,
    "cycle": detect_cycle,
    "forecast": compute_forecast,
}
