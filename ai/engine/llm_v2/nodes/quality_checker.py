"""
步骤 9: 数据质量检查

职责：
- 检查查询结果是否为空
- 检查是否有异常值
- 检查数据量是否合理
"""
from typing import Dict, Any, List, Tuple
from ai.config.logging_config import get_logger
from ..schema import SQLResult

logger = get_logger("ai.llm_v2.quality_checker")


class DataQualityChecker:
    """
    数据质量检查器

    检查查询结果的质量。
    """

    # 异常值阈值
    NULL_THRESHOLD = 0.1  # 空值比例超过 10% 警告
    OUTLIER_THRESHOLD = 3  # 超过均值 3 倍标准差为异常

    def check(self, sql_result: SQLResult) -> Tuple[bool, List[str]]:
        """
        检查数据质量

        Args:
            sql_result: SQL 执行结果

        Returns:
            (is_valid, warnings)
        """
        warnings = []

        if not sql_result.is_success():
            return False, ["SQL 执行失败"]

        # 1. 检查是否为空
        if not sql_result.data:
            warnings.append("查询结果为空")

        # 2. 检查空值比例
        null_ratio = self._check_null_ratio(sql_result.data)
        if null_ratio > self.NULL_THRESHOLD:
            warnings.append(f"空值比例过高: {null_ratio*100:.1f}%")

        # 3. 检查异常值
        outliers = self._check_outliers(sql_result.data)
        if outliers:
            warnings.append(f"检测到 {len(outliers)} 个异常值")

        # 4. 检查数据量
        if len(sql_result.data) > 10000:
            warnings.append(f"数据量较大: {len(sql_result.data)} 条，可能影响性能")

        # 如果只有警告，返回 True（有警告不代表失败）
        # 只有 SQL 执行失败才返回 False
        return True, warnings

    def _check_null_ratio(self, data: List[Dict[str, Any]]) -> float:
        """检查空值比例"""
        if not data:
            return 1.0

        total_cells = 0
        null_cells = 0

        for row in data:
            for value in row.values():
                total_cells += 1
                if value is None or value == "" or value == "null":
                    null_cells += 1

        if total_cells == 0:
            return 0.0

        return null_cells / total_cells

    def _check_outliers(self, data: List[Dict[str, Any]]) -> List[Any]:
        """检查异常值（使用简单的方法：超过均值 3 倍标准差）"""
        if not data or len(data) < 3:
            return []

        # 找到数值列
        numeric_values = []
        numeric_key = None

        for row in data:
            for key, value in row.items():
                if key.lower() in ("销售额", "订单量", "访客数", "销售额", "金额"):
                    try:
                        numeric_values.append(float(str(value).replace(",", "")))
                        numeric_key = key
                        break
                    except (ValueError, TypeError):
                        continue

        if not numeric_values or len(numeric_values) < 3:
            return []

        # 计算均值和标准差
        mean = sum(numeric_values) / len(numeric_values)
        variance = sum((x - mean) ** 2 for x in numeric_values) / len(numeric_values)
        std = variance ** 0.5

        if std == 0:
            return []

        # 找出异常值
        outliers = []
        for i, value in enumerate(numeric_values):
            if abs(value - mean) > self.OUTLIER_THRESHOLD * std:
                outliers.append(value)

        return outliers
