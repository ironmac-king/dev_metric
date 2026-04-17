"""
SFNode - 要素校验节点（Node2）
输入：LU 输出的 slots + 当前上下文
输出：{ metric_code, dimension, time_range, filters }
职责：
1. 维度映射：中文维度名 → 数据库列名
2. 槽位补全：从指标库推断缺省的时间/维度/聚合方式
3. 多轮上下文继承
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..config_loader import get_config_loader
from ..state.session_store import get_session_store

logger = logging.getLogger("ai.llm_v1.sf_node")


@dataclass
class SFOutput:
    """SF 节点输出"""
    metric_code: str
    metric_name: str
    starrocks_sql: str
    table: str = "ids.IDS_AMZ_COMPREHENSIVE_DI"  # 默认表名
    dimensions: Dict[str, str] = None  # {dimension_name: column_name}
    time_range: Dict[str, str] = None  # {start, end, original}
    filters: list = None
    aggregations: list = None
    operations: list = None
    raw_slots: Dict[str, Any] = None  # 原始 slots 用于追溯

    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = {}
        if self.time_range is None:
            self.time_range = {}
        if self.filters is None:
            self.filters = []
        if self.aggregations is None:
            self.aggregations = []
        # 确保 operations 是列表，并规范化格式
        if self.operations is None:
            self.operations = []
        elif not isinstance(self.operations, list):
            # 如果是字符串或其他非列表类型，转换为列表
            self.operations = [self.operations] if self.operations else []

        # 规范化 operations 格式：支持 LLM 返回的 {'order_by': 'DESC', 'limit': 10} 格式
        if isinstance(self.operations, list):
            normalized = []
            for op in self.operations:
                if isinstance(op, dict):
                    # 如果 dict 中包含 'order_by' 或 'limit' 键（不是 'type'），需要拆分
                    if "order_by" in op and "type" not in op:
                        normalized.append({"type": "order_by", "direction": op["order_by"]})
                    if "limit" in op and "type" not in op:
                        normalized.append({"type": "limit", "value": op["limit"]})
                    if "compare" in op and "type" not in op:
                        normalized.append({"type": "compare", "compare_type": op["compare"]})
                    if "percentage" in op and "type" not in op:
                        normalized.append({"type": "percentage"})
                    # 如果已经是标准格式或有其他键，直接保留
                    if not any(k in op for k in ["order_by", "limit", "compare", "percentage"]) or "type" in op:
                        normalized.append(op)
                else:
                    normalized.append(op)
            self.operations = normalized
        if self.raw_slots is None:
            self.raw_slots = {}


class SFNode:
    """
    要素校验节点（SF - Slot Filling）

    职责：
    1. **维度映射**（铁律一）：将中文维度名转换为数据库列名
    2. **槽位补全**：从指标库推断缺省值
    3. **时间解析**：将自然语言时间转换为具体日期
    4. **上下文继承**：复用上一轮的有效槽位
    """

    def __init__(self):
        self._config_loader = get_config_loader()
        self._session_store = get_session_store()
        self._metric_client = None  # TODO: 后续初始化 MetricClient

    async def process(
        self,
        lu_output,  # LUOutput
        session_id: Optional[str] = None,
    ) -> SFOutput:
        """
        处理 LU 节点输出，校验并补全槽位

        Args:
            lu_output: LU 节点输出
            session_id: 会话ID

        Returns:
            SFOutput: 补全后的槽位信息
        """
        logger.info(f"[SFNode] 处理 LU 输出: intent={lu_output.intent_type}")

        slots = lu_output.slots.copy() if lu_output.slots else {}

        # Step 1: 获取指标信息
        metric_info = await self._get_metric_info(slots.get("metric"), slots.get("metric_code"))
        if not metric_info:
            logger.warning(f"[SFNode] 未找到指标: {slots.get('metric')}")
            # TODO: 返回错误或触发澄清

        # Step 2: 维度映射（铁律一）
        dimensions = self._map_dimensions(slots.get("dimensions", []))

        # Step 3: 时间范围补全
        time_range = self._process_time_range(slots.get("time_range"))

        # Step 4: 上下文继承（继承上一轮有效的槽位）
        if session_id:
            context = self._session_store.get_context(session_id)
            if context:
                dimensions, time_range = self._apply_context_inheritance(
                    dimensions, time_range, context
                )

        # Step 5: 槽位补全（从指标库推断缺省值）
        dimensions, time_range = self._fill_missing_slots(
            dimensions, time_range, metric_info
        )

        # Step 6: 构建输出
        starrocks_sql = metric_info.get("starrocks_sql", "") if metric_info else ""
        # 从 starrocks_sql 提取表名
        table = "ids.IDS_AMZ_COMPREHENSIVE_DI"
        if starrocks_sql and "FROM" in starrocks_sql:
            try:
                table_part = starrocks_sql.split("FROM")[1].split("WHERE")[0].strip()
                if table_part:
                    table = table_part
            except:
                pass

        output = SFOutput(
            metric_code=metric_info.get("metric_code", "") if metric_info else slots.get("metric_code", ""),
            metric_name=metric_info.get("name", "") if metric_info else slots.get("metric", ""),
            starrocks_sql=starrocks_sql,
            table=table,
            dimensions=dimensions,
            time_range=time_range,
            filters=slots.get("filters", []),
            aggregations=slots.get("aggregations", ["SUM"]),
            operations=slots.get("operations", []),
            raw_slots=slots,
        )

        logger.info(
            f"[SFNode] 输出: metric={output.metric_name}, "
            f"dimensions={list(output.dimensions.values())}, "
            f"time_range={output.time_range.get('original')}"
        )

        return output

    async def _get_metric_info(self, metric_name: str, metric_code: str) -> Optional[Dict[str, Any]]:
        """获取指标信息"""
        from ..metric_client import get_metric_client

        metric_client = get_metric_client()

        # 优先用 metric_code 查询（但只有正确的格式如 MKI-02-0014 才能匹配）
        if metric_code and metric_code.startswith('MKI-'):
            info = metric_client.get_metric_by_code(metric_code)
            if info:
                return info

        # 用名称查询（包括模糊匹配）
        if metric_name:
            info = metric_client.get_metric_by_name(metric_name)
            if info:
                return info

        # 如果 metric_code 不是正确格式但有值，也尝试按名称查询
        if metric_code and not metric_code.startswith('MKI-'):
            info = metric_client.get_metric_by_name(metric_code)
            if info:
                return info

        return None

    def _map_dimensions(self, dimension_names: list) -> Dict[str, str]:
        """
        维度映射（铁律一）
        将中文维度名转换为数据库列名
        输出: {dimension_name: column_name}
        """
        if not dimension_names:
            return {}

        dimension_map = self._config_loader.get_dimension_map()
        result = {}

        # 时间维度特殊映射（用于趋势查询等场景）
        time_dimension_map = {
            "日期": "FDATE",
            "日": "FDATE",
            "每日": "FDATE",
            "每天": "FDATE",
            "天": "FDATE",
            "月份": "MONTHS",
            "月": "MONTHS",
            "年度": "YEARS",
            "年": "YEARS",
            "周": "WEEKS",
            "周次": "WEEKS",
        }

        for dim_name in dimension_names:
            if not dim_name:
                continue

            # 尝试直接匹配
            column_name = dimension_map.get(dim_name)
            if column_name:
                result[dim_name] = column_name
                logger.debug(f"[SFNode] 维度映射: {dim_name} → {column_name}")
                continue

            # 特殊处理时间维度
            if dim_name in time_dimension_map:
                result[dim_name] = time_dimension_map[dim_name]
                logger.info(f"[SFNode] 维度映射(时间): {dim_name} → {time_dimension_map[dim_name]}")
                continue

            # 处理复合维度名（如 "SKU/ASIN" → "ASIN"）
            if "/" in dim_name:
                # 尝试拆分并匹配每个部分
                for part in dim_name.split("/"):
                    part = part.strip()
                    column_name = dimension_map.get(part)
                    if column_name:
                        result[dim_name] = column_name
                        logger.info(f"[SFNode] 维度映射(复合): {dim_name} → {column_name} (via {part})")
                        break
                    # 也检查时间维度映射
                    if part in time_dimension_map:
                        result[dim_name] = time_dimension_map[part]
                        logger.info(f"[SFNode] 维度映射(复合时间): {dim_name} → {time_dimension_map[part]}")
                        break
                else:
                    logger.warning(f"[SFNode] 未找到维度映射: {dim_name}")

            # 处理带空格的维度名（如 "SKU / ASIN"）
            elif " " in dim_name:
                for part in dim_name.split():
                    part = part.strip()
                    if part and "/" in part:
                        for subpart in part.split("/"):
                            subpart = subpart.strip()
                            column_name = dimension_map.get(subpart)
                            if column_name:
                                result[dim_name] = column_name
                                logger.info(f"[SFNode] 维度映射(空格分隔): {dim_name} → {column_name}")
                                break
                            if subpart in time_dimension_map:
                                result[dim_name] = time_dimension_map[subpart]
                                logger.info(f"[SFNode] 维度映射(空格分隔时间): {dim_name} → {time_dimension_map[subpart]}")
                                break
                    if not column_name and part not in time_dimension_map:
                        column_name = dimension_map.get(part)
                        if column_name:
                            result[dim_name] = column_name
                            logger.info(f"[SFNode] 维度映射(空格): {dim_name} → {column_name}")
                            break
                    if part in time_dimension_map and dim_name not in result:
                        result[dim_name] = time_dimension_map[part]
                        logger.info(f"[SFNode] 维度映射(空格时间): {dim_name} → {time_dimension_map[part]}")
                        break
                else:
                    if dim_name not in result:
                        logger.warning(f"[SFNode] 未找到维度映射: {dim_name}")
            else:
                logger.warning(f"[SFNode] 未找到维度映射: {dim_name}")

        return result

    def _process_time_range(self, time_range) -> Dict[str, str]:
        """
        处理时间范围
        将 slots 中的 time_range 转换为标准格式
        """
        if not time_range:
            return {"start": "", "end": "", "original": ""}

        if isinstance(time_range, dict):
            return {
                "start": time_range.get("start", ""),
                "end": time_range.get("end", ""),
                "original": time_range.get("original", ""),
            }

        # 如果是字符串，手动解析
        return {"start": "", "end": "", "original": str(time_range)}

    def _apply_context_inheritance(
        self,
        dimensions: Dict[str, str],
        time_range: Dict[str, str],
        context,
    ) -> tuple:
        """
        应用上下文继承
        如果当前 slots 没有值，从上下文继承
        """
        # 维度继承
        if not dimensions and context.current_dimensions:
            dimension_map = self._config_loader.get_dimension_map()
            inherited = {}
            for dim_name in context.current_dimensions:
                col_name = dimension_map.get(dim_name)
                if col_name:
                    inherited[dim_name] = col_name
            if inherited:
                logger.info(f"[SFNode] 从上下文继承维度: {list(inherited.keys())}")
                dimensions = inherited

        # 时间继承
        if not time_range.get("original") and context.current_time:
            time_range = {
                "start": "",
                "end": "",
                "original": context.current_time,
            }
            logger.info(f"[SFNode] 从上下文继承时间: {context.current_time}")

        return dimensions, time_range

    def _fill_missing_slots(
        self,
        dimensions: Dict[str, str],
        time_range: Dict[str, str],
        metric_info: Optional[Dict],
    ) -> tuple:
        """
        补全缺失的槽位
        从指标信息推断缺省的时间范围和可用维度
        """
        # 如果没有 metric_info，无法推断
        if not metric_info:
            return dimensions, time_range

        # 补全时间范围（如果只有 original，没有具体日期）
        if not time_range.get("start") and time_range.get("original"):
            parsed_time = self._parse_time_expression(time_range["original"])
            if parsed_time:
                time_range.update(parsed_time)
                logger.info(f"[SFNode] 补全时间范围: {time_range}")

        # 补全维度（如果指标有 common_dimensions）
        if not dimensions and metric_info.get("common_dimensions"):
            dimension_map = self._config_loader.get_dimension_map()
            available_dims = metric_info["common_dimensions"].split(",")
            # 选择第一个维度作为默认
            for dim_name in available_dims:
                dim_name = dim_name.strip()
                col_name = dimension_map.get(dim_name)
                if col_name:
                    dimensions = {dim_name: col_name}
                    logger.info(f"[SFNode] 补全维度: {dim_name} → {col_name}")
                    break

        return dimensions, time_range

    def _parse_time_expression(self, time_expr: str) -> Optional[Dict[str, str]]:
        """
        解析时间表达式
        将"本月"、"近7天"等转换为具体日期
        """
        from datetime import datetime, timedelta

        # TODO: 后续实现 - 复用或重写 TimeParser
        # 参考: ai/engine/time_parser.py
        today = datetime.now()
        time_expr_lower = time_expr.lower()

        if "本月" in time_expr_lower:
            # 本月第1天
            start = today.replace(day=1).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        elif "上月" in time_expr_lower:
            # 上月
            first_day_this_month = today.replace(day=1)
            last_day_last_month = first_day_this_month - timedelta(days=1)
            start = last_day_last_month.replace(day=1).strftime("%Y-%m-%d")
            end = last_day_last_month.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        elif "近7天" in time_expr_lower:
            start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        elif "近30天" in time_expr_lower:
            start = (today - timedelta(days=29)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        elif "上周" in time_expr_lower:
            # 上周一到周日
            days_since_monday = today.weekday()
            last_monday = today - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)
            return {
                "start": last_monday.strftime("%Y-%m-%d"),
                "end": last_sunday.strftime("%Y-%m-%d"),
            }

        return None


# 全局实例
_sf_node: Optional[SFNode] = None


def get_sf_node() -> SFNode:
    """获取 SF 节点单例"""
    global _sf_node
    if _sf_node is None:
        _sf_node = SFNode()
    return _sf_node
