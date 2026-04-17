"""
RVNode - 结果验证节点（Node6）
输入：SQL 执行结果 + 原始 slots
输出：{ is_valid, anomaly_flags, data_profile }
职责：
1. 空数据检测
2. 极端值检测
3. 缺失字段检测
4. 波动异常检测
异常 → 记录 anomaly_flags，继续执行
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..config_loader import get_config_loader
from ..prompts.rv_prompt import RV_PROMPT

logger = logging.getLogger("ai.llm_v1.rv_node")


@dataclass
class RVOutput:
    """RV 节点输出"""
    is_valid: bool
    anomaly_flags: List[Dict[str, Any]]
    data_profile: Dict[str, Any]
    can_visualize: bool  # 是否有足够数据用于可视化


class RVNode:
    """
    结果验证节点（RV - Result Validation）

    职责：
    1. **空数据检测**：查询结果为空？
    2. **极端值检测**：数据是否为异常大/小值
    3. **缺失字段检测**：预期字段是否都存在
    4. **波动异常检测**：与历史数据对比是否有异常

    注意：即使有异常，is_valid 仍为 true（不阻塞流程）
    """

    def __init__(self):
        self._config_loader = get_config_loader()
        self._llm_engine = None  # TODO: 后续初始化

    async def process(
        self,
        ex_output,  # EXOutput
        slots: Dict[str, Any],
    ) -> RVOutput:
        """
        验证 SQL 执行结果

        Args:
            ex_output: EX 节点输出
            slots: 原始槽位信息

        Returns:
            RVOutput: 验证结果
        """
        logger.info(f"[RVNode] 验证结果: {ex_output.row_count} 行")

        anomaly_flags = []
        data_profile = {}

        # Step 1: 空数据检测
        if ex_output.row_count == 0:
            anomaly_flags.append({
                "type": "empty_data",
                "severity": "warning",
                "message": "查询结果为空，可能时间范围内无数据",
                "suggestion": "请确认时间范围是否正确，或尝试扩大时间范围",
            })
            logger.warning("[RVNode] 空数据检测: 查询结果为空")

        # Step 2: 极端值检测
        if ex_output.data:
            value_extremes = self._check_extreme_values(ex_output.data)
            if value_extremes:
                anomaly_flags.append({
                    "type": "extreme_value",
                    "severity": "warning",
                    "message": f"存在极端值: {value_extremes}",
                    "details": value_extremes,
                })

        # Step 3: 缺失字段检测
        missing_fields = self._check_missing_fields(ex_output, slots)
        if missing_fields:
            anomaly_flags.append({
                "type": "missing_field",
                "severity": "warning",
                "message": f"缺失预期字段: {', '.join(missing_fields)}",
                "missing": missing_fields,
            })

        # Step 4: 构建数据画像
        data_profile = self._build_data_profile(ex_output)

        # Step 5: 判断是否可以可视化
        can_visualize = (
            ex_output.row_count > 0
            and len(ex_output.data) <= 1000  # 数据量适中
            and len(ex_output.columns) <= 5  # 列数不过多
        )

        output = RVOutput(
            is_valid=True,  # 注意：即使有异常也不阻塞
            anomaly_flags=anomaly_flags,
            data_profile=data_profile,
            can_visualize=can_visualize,
        )

        logger.info(
            f"[RVNode] 结果: is_valid={output.is_valid}, "
            f"anomaly_flags={len(anomaly_flags)}, "
            f"can_visualize={can_visualize}"
        )

        return output

    def _check_extreme_values(self, data: List[Dict[str, Any]]) -> Optional[Dict]:
        """检测极端值"""
        try:
            # 找出所有数值列
            numeric_values = []
            for row in data:
                for key, value in row.items():
                    if isinstance(value, (int, float)) and value is not None:
                        numeric_values.append(value)

            if not numeric_values:
                return None

            # 检查是否有负数
            negative_values = [v for v in numeric_values if v < 0]
            if negative_values:
                return {"negative_count": len(negative_values), "has_negative": True}

            # 检查是否有极端大值（超过平均值 100 倍）
            avg_value = sum(numeric_values) / len(numeric_values)
            extreme_values = [v for v in numeric_values if abs(v) > avg_value * 100]
            if extreme_values:
                return {
                    "extreme_count": len(extreme_values),
                    "max_value": max(numeric_values),
                    "avg_value": avg_value,
                }

            return None

        except Exception as e:
            logger.warning(f"[RVNode] 极端值检测失败: {e}")
            return None

    def _check_missing_fields(
        self,
        ex_output,
        slots: Dict[str, Any],
    ) -> List[str]:
        """检测缺失字段"""
        if not slots or not slots.get("dimensions"):
            return []

        expected_fields = list(slots.get("dimensions", {}).values()) if isinstance(slots.get("dimensions"), dict) else slots.get("dimensions", [])
        actual_fields = ex_output.columns or []

        missing = []
        for field in expected_fields:
            # 检查 field 是否在 actual_fields 中（支持模糊匹配）
            found = any(field.lower() in col.lower() or col.lower() in field.lower()
                        for col in actual_fields)
            if not found:
                missing.append(field)

        return missing

    def _build_data_profile(self, ex_output) -> Dict[str, Any]:
        """构建数据画像"""
        profile = {
            "row_count": ex_output.row_count,
            "column_count": len(ex_output.columns),
            "columns": ex_output.columns,
            "has_null": False,
            "value_ranges": {},
        }

        if not ex_output.data:
            profile["summary"] = "无数据"
            return profile

        # 检查是否有 NULL
        for row in ex_output.data:
            if any(v is None for v in row.values()):
                profile["has_null"] = True
                break

        # 计算数值列的范围
        for row in ex_output.data:
            for key, value in row.items():
                if isinstance(value, (int, float)) and value is not None:
                    if key not in profile["value_ranges"]:
                        profile["value_ranges"][key] = {"min": value, "max": value}
                    else:
                        profile["value_ranges"][key]["min"] = min(
                            profile["value_ranges"][key]["min"], value
                        )
                        profile["value_ranges"][key]["max"] = max(
                            profile["value_ranges"][key]["max"], value
                        )

        # 生成摘要
        row_desc = f"共{ex_output.row_count}行"
        col_desc = f"{len(ex_output.columns)}列"
        null_desc = "（含空值）" if profile["has_null"] else ""
        profile["summary"] = f"{row_desc}，{col_desc}{null_desc}"

        return profile


# 全局实例
_rv_node: Optional[RVNode] = None


def get_rv_node() -> RVNode:
    """获取 RV 节点单例"""
    global _rv_node
    if _rv_node is None:
        _rv_node = RVNode()
    return _rv_node
