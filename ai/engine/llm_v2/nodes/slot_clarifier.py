"""
槽位消解引擎

职责：
- 检测 MQL 中缺失的必要槽位（指标、时间、维度）
- 生成追问消息和选项
- 在 mql_generator 之后、sql_generator 之前运行
"""
from typing import Optional, List, Dict, Any
from ai.config.logging_config import get_logger
from ..schema import MQLSchema, MQLIntent

logger = get_logger("ai.llm_v2.slot_clarifier")


class SlotClarifier:
    """统一槽位缺失/歧义检测"""

    # 各意图类型必须的槽位
    REQUIRED_SLOTS = {
        "query_value": ["metric", "time"],
        "query_trend": ["metric", "time"],
        "query_comparison": ["metric", "time"],
        "query_ranking": ["metric", "time", "dimension"],
    }

    # 槽位缺失时的追问消息
    SLOT_MESSAGES = {
        "metric": {
            "message": "请问您想查询哪个指标？",
            "options": [],
        },
        "time": {
            "message": "请问您想查询哪个时间范围？",
            "options": [
                {"label": "本月", "value": "本月"},
                {"label": "上月", "value": "上月"},
                {"label": "近7天", "value": "近7天"},
                {"label": "近30天", "value": "近30天"},
            ],
        },
        "dimension": {
            "message": "请问您想按哪个维度查看？",
            "options": [
                {"label": "按站点", "value": "站点"},
                {"label": "按品类", "value": "品类"},
                {"label": "按店铺", "value": "店铺"},
                {"label": "按渠道", "value": "渠道"},
            ],
        },
    }

    def check(self, mql: MQLSchema) -> Optional[Dict[str, Any]]:
        """
        检测槽位缺失/歧义

        Args:
            mql: MQLSchema 实例

        Returns:
            None 如果所有必要槽位都已填充
            {"needs_clarification": True, "message": str, "options": list, "missing_slots": list} 如果有缺失
        """
        if not mql:
            return None

        # 寒暄/致谢等意图不需要检查
        if mql.intent in [MQLIntent.GREETING, MQLIntent.THANKS, MQLIntent.BYE]:
            return None

        intent = mql.intent.value if hasattr(mql.intent, 'value') else str(mql.intent)
        required = self.REQUIRED_SLOTS.get(intent, [])
        if not required:
            return None

        missing = []
        for slot in required:
            if slot == "metric" and not self._has_metric(mql):
                missing.append(slot)
            elif slot == "time" and not self._has_time(mql):
                missing.append(slot)
            elif slot == "dimension" and not self._has_dimension(mql):
                missing.append(slot)

        if not missing:
            return None

        # 构建追问消息
        primary_slot = missing[0]
        slot_info = self.SLOT_MESSAGES.get(primary_slot, {})
        message = slot_info.get("message", f"请提供: {primary_slot}")

        # 动态填充指标选项
        if primary_slot == "metric":
            slot_info["options"] = self._get_metric_options()

        result = {
            "needs_clarification": True,
            "message": message,
            "options": slot_info.get("options", []),
            "missing_slots": missing,
        }

        logger.info(f"[SlotClarifier] 槽位缺失: {missing}, intent={intent}")
        return result

    def _has_metric(self, mql: MQLSchema) -> bool:
        """检查是否有有效指标"""
        if mql.metric and mql.metric.name:
            return True
        if mql.metrics and any(m.name for m in mql.metrics):
            return True
        return False

    def _has_time(self, mql: MQLSchema) -> bool:
        """检查是否有时间范围"""
        if mql.time and (mql.time.start or mql.time.end):
            return True
        return False

    def _has_dimension(self, mql: MQLSchema) -> bool:
        """检查是否有维度"""
        if mql.dimensions and any(d.type or d.column for d in mql.dimensions):
            return True
        return False

    def _get_metric_options(self) -> List[Dict[str, str]]:
        """从快照获取在用指标列表（前端分批展示 + 换一批）"""
        options = []
        try:
            from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
            snap = get_semantic_snapshot_service()
            snapshot = snap.get_active_snapshot()
            if snapshot:
                payload = snapshot.get("payload", snapshot)
                metrics = payload.get("metrics", {})
                for code, m in metrics.items():
                    if code.startswith("MKI") and m.get("display_name"):
                        # 过滤停用指标：status=0 或 原始 status="停用"
                        if m.get("status") == 0 or m.get("status") == "停用":
                            continue
                        options.append({
                            "label": m["display_name"],
                            "value": m["display_name"],
                        })
        except Exception as e:
            logger.warning(f"[SlotClarifier] 获取指标选项失败: {e}")
        return options
