from typing import Any, Dict, List, Optional

from ai.engine.llm_v2.schema import MQLDimension, MQLMetric, MQLSchema, TimeRange, TimeType


class AnalysisTaskService:
    def build_active_analysis_task(
        self,
        mql: Optional[MQLSchema],
        mode: str = "direct",
        suggestions: Optional[List[str]] = None,
        analysis: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not mql or not mql.metric:
            return None

        focus_dimensions = []
        for dim in mql.dimensions or []:
            focus_dimensions.append(
                {
                    "code": dim.column or dim.field or dim.type,
                    "label": dim.type,
                    "value": dim.value,
                }
            )

        focus_time = None
        if mql.time:
            focus_time = {
                "type": mql.time.type.value if isinstance(mql.time.type, TimeType) else mql.time.type,
                "start": mql.time.start,
                "end": mql.time.end,
                "original": mql.time.original,
                "days": mql.time.days,
            }

        return {
            "focus_metric": {
                "code": mql.metric.code,
                "name": mql.metric.name,
                "table": mql.metric.table,
                "field": mql.metric.field,
                "unit": mql.metric.unit,
                "starrocks_sql": mql.metric.starrocks_sql,
            },
            "focus_dimensions": focus_dimensions,
            "focus_time": focus_time,
            "analysis_mode": mode,
            "comparison_types": list(mql.comparison.types) if mql.comparison and mql.comparison.types else [],
            "preferred_followups": list(suggestions or []),
            "drilldown_options": list((analysis or {}).get("drilldown_options", [])) if analysis else [],
        }

    def build_mql_from_task(self, active_task: Optional[Dict[str, Any]], question: str) -> Optional[MQLSchema]:
        if not active_task:
            return None

        metric = active_task.get("focus_metric") or {}
        if not metric.get("name"):
            return None

        mql = MQLSchema()
        mql.metric = MQLMetric(
            code=metric.get("code", ""),
            name=metric.get("name", ""),
            table=metric.get("table", ""),
            field=metric.get("field", ""),
            unit=metric.get("unit", ""),
            starrocks_sql=metric.get("starrocks_sql", ""),
        )

        time_info = active_task.get("focus_time") or {}
        if time_info:
            try:
                time_type = TimeType(time_info.get("type", "relative"))
            except ValueError:
                time_type = TimeType.RELATIVE
            mql.time = TimeRange(
                type=time_type,
                start=time_info.get("start", ""),
                end=time_info.get("end", ""),
                original=time_info.get("original", ""),
                days=time_info.get("days", 0) or 0,
            )

        for dim in active_task.get("focus_dimensions", []) or []:
            mql.dimensions.append(
                MQLDimension(
                    type=dim.get("code") or dim.get("label", ""),
                    column=dim.get("code", ""),
                    value=dim.get("value"),
                )
            )

        mql.original_question = question
        return mql


_analysis_task_service: Optional[AnalysisTaskService] = None


def get_analysis_task_service() -> AnalysisTaskService:
    global _analysis_task_service
    if _analysis_task_service is None:
        _analysis_task_service = AnalysisTaskService()
    return _analysis_task_service
