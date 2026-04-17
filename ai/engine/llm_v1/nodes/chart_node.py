"""
ChartNode - 可视化生成节点（Node7）
输入：SQL 执行结果 + 原始 slots
输出：{ chart_type, echarts_config }
职责：
1. 根据数据形状和查询意图推荐图表类型
2. 生成 ECharts 配置
3. 图表推荐规则从配置读取（不硬编码）
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..config_loader import get_config_loader

logger = logging.getLogger("ai.llm_v1.chart_node")


@dataclass
class ChartOutput:
    """Chart 节点输出"""
    chart_type: str  # bar / line / table / pie
    echarts_config: Dict[str, Any]
    suggestions: list  # 图表优化建议


class ChartNode:
    """
    可视化生成节点

    职责：
    1. 根据数据形状和查询意图推荐图表类型
    2. 生成 ECharts 配置
    3. 图表推荐规则从配置读取（不硬编码）
    """

    # 默认图表推荐规则
    DEFAULT_CHART_RULES = {
        ("query_value", "single"): "table",  # 单值指标 → 数字卡片
        ("query_value", "multiple"): "bar",   # 多行数据 → 柱状图
        ("query_ranking", "multiple"): "bar", # 排名 → 柱状图
        ("query_trend", "timeseries"): "line",  # 时间趋势 → 折线图
        ("compare", "multiple"): "bar",  # 对比 → 柱状图
    }

    def __init__(self):
        self._config_loader = get_config_loader()

    async def process(
        self,
        ex_output,  # EXOutput
        rv_output,  # RVOutput
        slots: Dict[str, Any],
    ) -> ChartOutput:
        """
        生成可视化配置

        Args:
            ex_output: EX 节点输出
            rv_output: RV 节点输出
            slots: 原始槽位信息

        Returns:
            ChartOutput: 可视化配置
        """
        logger.info(f"[ChartNode] 生成图表: columns={ex_output.columns}, rows={ex_output.row_count}")

        # 如果无法可视化，返回空配置
        if not rv_output.can_visualize:
            logger.info("[ChartNode] 数据不适合可视化，返回空配置")
            return ChartOutput(
                chart_type="none",
                echarts_config={},
                suggestions=["数据量过大或为空，无法生成图表"],
            )

        # Step 1: 推荐图表类型
        chart_type = self._recommend_chart_type(ex_output, rv_output, slots)

        # Step 2: 生成 ECharts 配置
        echarts_config = self._generate_echarts_config(
            chart_type, ex_output, rv_output, slots
        )

        # Step 3: 生成优化建议
        suggestions = self._generate_suggestions(chart_type, ex_output, rv_output)

        output = ChartOutput(
            chart_type=chart_type,
            echarts_config=echarts_config,
            suggestions=suggestions,
        )

        logger.info(f"[ChartNode] 生成图表类型: {chart_type}")
        return output

    def _recommend_chart_type(
        self,
        ex_output,
        rv_output,
        slots: Dict[str, Any],
    ) -> str:
        """
        推荐图表类型

        策略：
        1. 从配置读取图表规则
        2. 根据数据形状判断
        3. 根据意图类型判断
        """
        # 获取意图类型
        intent_type = slots.get("intent_type", "query_value")

        # 判断数据形状
        data_shape = self._determine_data_shape(ex_output, rv_output)

        # 尝试从配置读取规则
        chart_rules = self._config_loader.get_chart_rules()
        for rule in chart_rules:
            if rule.intent_type == intent_type and rule.data_shape == data_shape:
                logger.info(f"[ChartNode] 从配置读取图表规则: {rule.chart_type}")
                return rule.chart_type

        # 使用默认规则
        default_key = (intent_type, data_shape)
        chart_type = self.DEFAULT_CHART_RULES.get(default_key, "table")
        logger.info(f"[ChartNode] 使用默认图表规则: {chart_type}")
        return chart_type

    def _determine_data_shape(
        self,
        ex_output,
        rv_output,
    ) -> str:
        """判断数据形状"""
        row_count = ex_output.row_count
        column_count = len(ex_output.columns)

        # 单值（1行1列左右的数值）
        if row_count <= 1 and column_count <= 2:
            return "single"

        # 时间序列（包含日期列，且有多行）
        if row_count > 1 and any("DATE" in col.upper() or "FDATE" in col.upper()
                                 for col in ex_output.columns):
            return "timeseries"

        # 多行多列
        if row_count > 1:
            return "multiple"

        return "single"

    def _generate_echarts_config(
        self,
        chart_type: str,
        ex_output,
        rv_output,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """生成 ECharts 配置"""
        if chart_type == "none":
            return {}

        # 获取反向映射（数据库列名 → 中文名）
        config_loader = get_config_loader()
        reverse_map = config_loader.get_reverse_dimension_map()

        # 获取指标的中文名作为备用
        metric_name = slots.get("metric", "") if isinstance(slots, dict) else ""

        # 转换列名为中文
        display_columns = self._convert_columns_to_display(ex_output.columns, reverse_map, metric_name)

        # 转换数据行的 key 为中文
        display_data = self._convert_data_to_display(ex_output.data, reverse_map, metric_name)

        # 基础配置
        config = {
            "chart_type": chart_type,
            "data": display_data,
            "columns": display_columns,
        }

        if chart_type == "table":
            config["table"] = self._generate_table_config(ex_output, display_data, display_columns)
        elif chart_type == "bar":
            config["bar"] = self._generate_bar_config(ex_output, slots)
        elif chart_type == "line":
            config["line"] = self._generate_line_config(ex_output, slots)
        elif chart_type == "pie":
            config["pie"] = self._generate_pie_config(ex_output)

        return config

    def _convert_columns_to_display(self, columns, reverse_map, metric_name=""):
        """将数据库列名转换为中文显示名"""
        display_columns = []
        for col in columns:
            # 1. 先查维度映射（维度列名 → 中文维度名）
            display_name = reverse_map.get(col, None)
            if display_name:
                display_columns.append(display_name)
                continue

            # 2. 如果映射没有，使用指标中文名（用于指标值列）
            if metric_name:
                display_columns.append(metric_name)
                continue

            # 3. 兜底：特殊处理常见列名
            if "SALES" in col.upper():
                display_name = "销售额"
            elif "UNITS" in col.upper():
                display_name = "订单量"
            elif "AMOUNT" in col.upper():
                display_name = "金额"
            elif "QTY" in col.upper() or "QUANTITY" in col.upper():
                display_name = "数量"
            else:
                display_name = col
            display_columns.append(display_name)
        return display_columns

    def _convert_data_to_display(self, data, reverse_map, metric_name=""):
        """将数据行的 key 转换为中文"""
        display_data = []
        for row in data:
            new_row = {}
            for col, value in row.items():
                # 1. 先查维度映射
                display_name = reverse_map.get(col, None)
                if display_name:
                    new_row[display_name] = value
                    continue

                # 2. 使用指标中文名
                if metric_name:
                    new_row[metric_name] = value
                    continue

                # 3. 兜底：特殊处理
                if "SALES" in col.upper():
                    display_name = "销售额"
                elif "UNITS" in col.upper():
                    display_name = "订单量"
                elif "AMOUNT" in col.upper():
                    display_name = "金额"
                elif "QTY" in col.upper() or "QUANTITY" in col.upper():
                    display_name = "数量"
                else:
                    display_name = col
                new_row[display_name] = value
            display_data.append(new_row)
        return display_data

    def _generate_table_config(self, ex_output, display_data, display_columns) -> Dict[str, Any]:
        """生成表格配置"""
        return {
            "columns": display_columns,
            "data": display_data[:100],  # 最多显示100行
            "pagination": {
                "page": 1,
                "pageSize": 10,
            },
        }

    def _generate_bar_config(self, ex_output, slots) -> Dict[str, Any]:
        """生成柱状图配置"""
        # 找出维度列和数值列
        dimension_col = None
        value_col = None

        for col in ex_output.columns:
            if col in ["FSITE", "PLATFORM", "GROUP_1", "GROUP_2", "GROUP_3"]:
                dimension_col = col
            elif any(keyword in col.upper() for keyword in ["销售额", "订单量", "值", "AMOUNT", "UNITS"]):
                value_col = col

        if not dimension_col or not value_col:
            dimension_col = ex_output.columns[0]
            value_col = ex_output.columns[-1] if len(ex_output.columns) > 1 else "value"

        # 反向映射维度名为中文
        config = self._config_loader
        reverse_map = config.get_reverse_dimension_map()
        dimension_label = reverse_map.get(dimension_col, dimension_col)

        return {
            "xAxis": {
                "type": "category",
                "data": [row.get(dimension_col, "") for row in ex_output.data],
                "name": dimension_label,
            },
            "yAxis": {
                "type": "value",
                "name": value_col,
            },
            "series": [{
                "type": "bar",
                "data": [row.get(value_col, 0) for row in ex_output.data],
                "label": {
                    "show": True,
                    "position": "top",
                },
            }],
        }

    def _generate_line_config(self, ex_output, slots) -> Dict[str, Any]:
        """生成折线图配置"""
        return {
            "xAxis": {
                "type": "category",
                "data": [row.get("FDATE", row.get("date", i)) for i, row in enumerate(ex_output.data)],
                "name": "时间",
            },
            "yAxis": {
                "type": "value",
                "name": ex_output.columns[-1] if len(ex_output.columns) > 1 else "value",
            },
            "series": [{
                "type": "line",
                "data": [row.get(ex_output.columns[-1], 0) for row in ex_output.data],
                "smooth": True,
                "label": {
                    "show": True,
                },
            }],
        }

    def _generate_pie_config(self, ex_output) -> Dict[str, Any]:
        """生成饼图配置"""
        # 找出维度列和数值列
        dimension_col = ex_output.columns[0]
        value_col = ex_output.columns[-1] if len(ex_output.columns) > 1 else "value"

        return {
            "series": [{
                "type": "pie",
                "radius": ["40%", "70%"],
                "data": [
                    {"name": row.get(dimension_col, ""), "value": row.get(value_col, 0)}
                    for row in ex_output.data
                ],
                "label": {
                    "formatter": "{b}: {d}%",
                },
            }],
        }

    def _generate_suggestions(
        self,
        chart_type: str,
        ex_output,
        rv_output,
    ) -> list:
        """生成图表优化建议"""
        suggestions = []

        # 数据量建议
        if ex_output.row_count > 20:
            suggestions.append("数据量较大，建议筛选后查看TOP N")

        # 异常建议
        if rv_output.anomaly_flags:
            for flag in rv_output.anomaly_flags:
                if flag.get("type") == "extreme_value":
                    suggestions.append(f"检测到极端值: {flag.get('message')}，请关注")

        # 图表类型建议
        if chart_type == "table" and ex_output.row_count > 10:
            suggestions.append("表格数据较多，建议切换为图表视图查看")

        return suggestions


# 全局实例
_chart_node: Optional[ChartNode] = None


def get_chart_node() -> ChartNode:
    """获取 Chart 节点单例"""
    global _chart_node
    if _chart_node is None:
        _chart_node = ChartNode()
    return _chart_node
