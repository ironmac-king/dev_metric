import httpx
import threading
from typing import Any, Dict, List, Optional

from ai.config.logging_config import get_logger
from ai.config.runtime import get_go_api_base

logger = get_logger("ai.semantic_snapshot_service")

_http_client: Optional[httpx.Client] = None


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
    return _http_client


class SemanticSnapshotService:
    _instance: Optional["SemanticSnapshotService"] = None
    _lock = threading.Lock()

    def __new__(cls, base_url: Optional[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._base_url = base_url or get_go_api_base()
                    cls._instance._active_snapshot = None
        return cls._instance

    def __init__(self, base_url: Optional[str] = None):
        self._base_url = base_url or self._base_url

    def get_active_snapshot(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        if self._active_snapshot is not None and not force_refresh:
            return self._active_snapshot

        url = f"{self._base_url}/api/v1/semantic/snapshots/active"
        try:
            client = _get_http_client()
            response = client.get(url)
            response.raise_for_status()
            body = response.json()
            data = body.get("data")
            if not data:
                return None

            payload = data.get("payload")
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            if isinstance(payload, dict):
                self._active_snapshot = payload
            else:
                self._active_snapshot = None
            return self._active_snapshot
        except Exception as e:
            logger.warning(f"[SemanticSnapshotService] load active snapshot failed: {e}")
            return None

    def recommend_next_questions(self, mql, scene_type: str) -> List[str]:
        snapshot = self.get_active_snapshot()
        if not snapshot or not mql or not getattr(mql, "metric", None):
            return []

        metric_code = getattr(mql.metric, "code", "") or ""
        metric_name = getattr(mql.metric, "name", "") or ""
        if not metric_code:
            return []

        metrics = snapshot.get("metrics", {}) or {}
        dimensions = snapshot.get("dimensions", {}) or {}
        capabilities = snapshot.get("capabilities", {}) or {}
        policies = snapshot.get("interaction_policies", {}) or {}

        metric_entry = metrics.get(metric_code, {}) or {}
        capability = capabilities.get(f"metric:{metric_code}", {}) or {}
        policy = policies.get(scene_type) or policies.get("simple_query") or {}

        time_context = getattr(getattr(mql, "time", None), "original", "") or "本月"
        current_dim_code = self._resolve_current_dimension_code(mql, dimensions)

        suggestions: List[str] = []
        suggestions.extend(metric_entry.get("preferred_followups", []) or [])

        display_name = metric_entry.get("display_name") or metric_name or "指标"

        for dim_code in metric_entry.get("recommended_dimension_codes", []) or []:
            if not dim_code or dim_code == current_dim_code:
                continue
            dim_name = (dimensions.get(dim_code) or {}).get("display_name") or dim_code
            suggestions.append(f"查看{time_context}各{dim_name}{display_name}变化")

        if capability.get("supports_trend") and scene_type not in {"trend", "comparison"}:
            suggestions.append(f"查看{time_context}{display_name}趋势变化")
        if capability.get("supports_yoy"):
            suggestions.append(f"查看{time_context}{display_name}同比变化")
        if capability.get("supports_mom"):
            suggestions.append(f"查看{time_context}{display_name}环比变化")

        max_suggestions = policy.get("max_suggestions", 3) or 3
        return self._unique_ordered(suggestions)[:max_suggestions]

    def recommend_actions(self, scene_type: str, target_scene_type: str = "drilldown", limit: int = 4) -> List[Dict[str, Any]]:
        snapshot = self.get_active_snapshot()
        if not snapshot:
            return []

        actions = snapshot.get("actions", {}) or {}
        normalized_scene_types = self._normalize_scene_types(scene_type)
        candidates: List[Dict[str, Any]] = []

        for action in actions.values():
            source_scene = action.get("source_scene_type", "")
            target_scene = action.get("target_scene_type", "")
            if source_scene not in normalized_scene_types:
                continue
            if target_scene_type and target_scene != target_scene_type:
                continue
            candidates.append({
                "label": action.get("label", ""),
                "action": "drilldown",
                "params": action.get("target_payload_template", {}) or {},
                "priority": action.get("priority", 0) or 0,
            })

        candidates.sort(key=lambda item: item.get("priority", 0), reverse=True)
        result = []
        seen = set()
        for item in candidates:
            label = item.get("label", "").strip()
            if not label or label in seen:
                continue
            seen.add(label)
            result.append({
                "label": label,
                "action": item["action"],
                "params": item["params"],
            })
            if len(result) >= limit:
                break
        return result

    def resolve_action(
        self,
        check: str = "",
        question: str = "",
        scene_type: str = "analysis",
        target_scene_type: str = "drilldown",
    ) -> Optional[Dict[str, Any]]:
        candidates = self.recommend_actions(scene_type, target_scene_type=target_scene_type, limit=20)
        normalized_question = self._normalize_text(question)
        normalized_check = self._normalize_text(check)
        signal_question = f"__DRILLDOWN__:{normalized_check}__" if normalized_check else ""

        for item in candidates:
            params = item.get("params", {}) or {}
            candidate_question = self._normalize_text(params.get("question"))
            candidate_check = self._normalize_text(params.get("check"))

            if normalized_question and candidate_question == normalized_question:
                return item
            if signal_question and candidate_question == signal_question:
                return item
            if normalized_check and candidate_check == normalized_check:
                return item

        return None

    def resolve_metric(self, candidate: str) -> Optional[Dict[str, Any]]:
        snapshot = self.get_active_snapshot()
        if not snapshot or not candidate:
            return None

        normalized = str(candidate).strip()
        lowered = normalized.lower()
        metrics = snapshot.get("metrics", {}) or {}
        aliases = snapshot.get("metric_aliases", {}) or {}

        metric_code = aliases.get(lowered)
        if not metric_code:
            for code, entry in metrics.items():
                display_name = str(entry.get("display_name", "")).strip()
                if normalized == code or normalized == display_name or lowered == display_name.lower():
                    metric_code = code
                    break
                if display_name and display_name.endswith(normalized):
                    metric_code = code
                    break

        if not metric_code:
            return None

        metric_entry = metrics.get(metric_code, {}) or {}
        result = {
            "metric_code": metric_code,
            "code": metric_code,
            "name": metric_entry.get("display_name") or normalized,
        }
        if metric_entry.get("unit"):
            result["unit"] = metric_entry["unit"]
        if metric_entry.get("table"):
            result["starrocks_table"] = metric_entry["table"]
        if metric_entry.get("field"):
            result["starrocks_field"] = metric_entry["field"]
        if metric_entry.get("starrocks_sql"):
            result["starrocks_sql"] = metric_entry["starrocks_sql"]
        return result

    def list_dimension_options(self) -> List[Dict[str, str]]:
        snapshot = self.get_active_snapshot()
        if not snapshot:
            return []

        dimensions = snapshot.get("dimensions", {}) or {}
        items: List[Dict[str, str]] = []
        for code, entry in dimensions.items():
            display_name = entry.get("display_name") or code
            items.append(
                {
                    "label": f"按{display_name}",
                    "value": code,
                }
            )

        items.sort(key=lambda item: item["label"])
        return items

    def resolve_dimension_code(self, candidate: str) -> Optional[str]:
        snapshot = self.get_active_snapshot()
        if not snapshot or not candidate:
            return None

        dimensions = snapshot.get("dimensions", {}) or {}
        normalized = str(candidate).strip()
        stripped = normalized[1:] if normalized.startswith("按") else normalized

        if normalized in dimensions:
            return normalized
        if stripped in dimensions:
            return stripped

        for code, entry in dimensions.items():
            display_name = (entry.get("display_name") or "").strip()
            if normalized == display_name or stripped == display_name:
                return code
            if normalized == f"按{display_name}" or stripped == display_name:
                return code

        return None

    def list_generic_dimension_options(self, generic_type: str) -> List[Dict[str, str]]:
        snapshot = self.get_active_snapshot()
        if not snapshot:
            return []

        dimensions = snapshot.get("dimensions", {}) or {}
        items: List[tuple[int, str, str]] = []

        if generic_type == "category":
            for code, entry in dimensions.items():
                display_name = (entry.get("display_name") or "").strip()
                if "品类" not in display_name and "类目" not in display_name:
                    continue
                items.append((entry.get("hierarchy_level", 0) or 0, display_name, code))
        elif generic_type == "business_dimension":
            for code, entry in dimensions.items():
                display_name = (entry.get("display_name") or "").strip()
                if any(keyword in display_name for keyword in ["品牌", "店铺", "平台", "站点"]):
                    items.append((entry.get("default_sort_priority", 0) or 0, display_name, code))

        items.sort(key=lambda item: (item[0], item[1]))
        return [{"label": label, "value": value} for _, label, value in items]

    def _get_snapshot_dimension_values(self) -> Dict[str, List[Dict[str, Any]]]:
        snapshot = self.get_active_snapshot()
        value_map = (snapshot or {}).get("dimension_values", {}) or {}
        return value_map if isinstance(value_map, dict) else {}

    def get_all_types(self) -> List[Dict[str, str]]:
        snapshot = self.get_active_snapshot()
        dimensions = (snapshot or {}).get("dimensions", {}) or {}
        items: List[Dict[str, str]] = []
        for code, entry in dimensions.items():
            display_name = str(entry.get("display_name") or code).strip()
            if not code or not display_name:
                continue
            items.append(
                {
                    "column_name": code,
                    "dimension_type": display_name,
                }
            )
        return items

    def find_dimension_column_by_type(self, candidate: str) -> Optional[str]:
        if not candidate:
            return None

        dim_code = self.resolve_dimension_code(candidate)
        if dim_code:
            return dim_code

        for item in self.get_all_types():
            if self._normalize_text(item.get("dimension_type")) == self._normalize_text(candidate):
                return self._normalize_text(item.get("column_name"))
        return None

    def search_dimension_values(
        self,
        candidate: str,
        limit: int = 20,
        column_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        normalized = self._normalize_text(candidate)
        if not normalized:
            return []

        results: List[Dict[str, Any]] = []
        seen = set()
        term_match = self._resolve_dimension_from_term_index(normalized)
        if term_match and not term_match.get("is_generic"):
            dim_code = str(term_match.get("column_name") or "").strip()
            if not column_name or dim_code == column_name:
                key = (
                    dim_code,
                    str(term_match.get("dimension_value") or "").strip(),
                )
                if key not in seen:
                    seen.add(key)
                    results.append(
                        {
                            "column_name": dim_code,
                            "dimension_type": term_match.get("dimension_type", ""),
                            "dimension_value": term_match.get("dimension_value", ""),
                            "match_type": "semantic_term",
                        }
                    )

        lowered = normalized.lower()
        for dim_code, items in self._get_snapshot_dimension_values().items():
            if column_name and dim_code != column_name:
                continue
            for item in items or []:
                dim_value = self._normalize_text(item.get("dimension_value"))
                if not dim_value or lowered not in dim_value.lower():
                    continue
                key = (dim_code, dim_value)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    {
                        "column_name": dim_code,
                        "dimension_type": self._normalize_text(item.get("dimension_type")),
                        "dimension_value": dim_value,
                        "match_type": "snapshot_dimension_value",
                    }
                )
                if len(results) >= limit:
                    return results

        return results[:limit]

    def resolve_dimension(self, candidate: str) -> Optional[Dict[str, Any]]:
        normalized = self._normalize_text(candidate)
        if not normalized:
            return None

        term_match = self._resolve_dimension_from_term_index(normalized)
        if term_match:
            return term_match

        dim_code = self.resolve_dimension_code(normalized)
        if dim_code:
            return self._build_dimension_resolution(dim_code, None, True)

        matches = self.search_dimension_values(normalized, limit=1)
        if not matches:
            return None
        return self._normalize_dimension_result(matches[0])

    def get_dimension_keywords(self) -> List[str]:
        snapshot = self.get_active_snapshot()
        dimensions = (snapshot or {}).get("dimensions", {}) or {}
        keywords: List[str] = []

        for code, entry in dimensions.items():
            display_name = self._normalize_text(entry.get("display_name") or code)
            if display_name and len(display_name) < 20 and display_name not in keywords:
                keywords.append(display_name)

        term_index = (snapshot or {}).get("term_index", {}) or {}
        for entry in term_index.values():
            if not isinstance(entry, dict):
                continue
            synonyms = entry.get("synonyms") or []
            for synonym in synonyms:
                synonym_text = self._normalize_text(synonym)
                if synonym_text and len(synonym_text) < 10 and synonym_text not in keywords:
                    keywords.append(synonym_text)

        return keywords

    def get_dimension_values_context(self, dimension_fields: Optional[List[str]] = None) -> str:
        snapshot = self.get_active_snapshot()
        dimensions = (snapshot or {}).get("dimensions", {}) or {}
        dimension_values = self._get_snapshot_dimension_values()
        allowed_fields = {field.upper() for field in (dimension_fields or []) if field}

        grouped: Dict[str, List[str]] = {}
        for dim_code, items in dimension_values.items():
            if allowed_fields and dim_code.upper() not in allowed_fields:
                continue
            values = grouped.setdefault(dim_code, [])
            for item in items or []:
                dim_value = self._normalize_text(item.get("dimension_value"))
                if dim_value and dim_value not in values:
                    values.append(dim_value)

        lines: List[str] = []
        for dim_code in sorted(grouped.keys()):
            display_name = self._normalize_text((dimensions.get(dim_code) or {}).get("display_name"))
            label = f"{dim_code}({display_name})" if display_name else dim_code
            lines.append(f"  {label}: {', '.join(grouped[dim_code][:20])}")
        return "\n".join(lines)

    def get_dimension_synonym_context(self, limit: int = 20) -> str:
        snapshot = self.get_active_snapshot()
        term_index = (snapshot or {}).get("term_index", {}) or {}
        lines: List[str] = []

        for entry in term_index.values():
            if not isinstance(entry, dict):
                continue
            dim_code = self._normalize_text(entry.get("dimension_field"))
            canonical = self._normalize_text(entry.get("dimension_value"))
            synonyms = [self._normalize_text(item) for item in (entry.get("synonyms") or [])]
            synonyms = [item for item in synonyms if item]
            if not dim_code or not canonical or not synonyms:
                continue
            lines.append(
                f"  {'、'.join(synonyms[:5])} → filter={{\"field\": \"{dim_code}\", \"value\": \"{canonical}\"}}"
            )
            if len(lines) >= limit:
                break

        if lines:
            return "【重要】以下用户词对应具体的数据库维度值，遇到这些词必须生成 filter：\n" + "\n".join(lines)

        return ""

    def get_level_keywords(self) -> Dict[str, str]:
        snapshot = self.get_active_snapshot()
        dimensions = (snapshot or {}).get("dimensions", {}) or {}
        result: Dict[str, str] = {}

        for code, entry in dimensions.items():
            display_name = self._normalize_text(entry.get("display_name") or code)
            if display_name and entry.get("hierarchy_level", 0):
                result[display_name] = code

        return result

    def get_dimension_fallback_map(self) -> Dict[str, str]:
        snapshot = self.get_active_snapshot()
        dimensions = (snapshot or {}).get("dimensions", {}) or {}
        result: Dict[str, str] = {}

        for code, entry in dimensions.items():
            display_name = self._normalize_text(entry.get("display_name") or code)
            if display_name:
                result[display_name] = code
            result[code] = code

        return result

    def get_dimension_name_to_code_map(self) -> Dict[str, str]:
        snapshot = self.get_active_snapshot()
        dimensions = (snapshot or {}).get("dimensions", {}) or {}
        result: Dict[str, str] = {}

        for code, entry in dimensions.items():
            display_name = self._normalize_text(entry.get("display_name") or code)
            if display_name:
                result[display_name] = code

        return result

    def get_metric_names(self) -> List[str]:
        snapshot = self.get_active_snapshot()
        metrics = (snapshot or {}).get("metrics", {}) or {}
        names = []
        for entry in metrics.values():
            display_name = self._normalize_text(entry.get("display_name"))
            if display_name and display_name not in names:
                names.append(display_name)
        names.sort()
        return names

    def get_dimension_mapping_pairs(self) -> List[Dict[str, str]]:
        snapshot = self.get_active_snapshot()
        dimensions = (snapshot or {}).get("dimensions", {}) or {}
        pairs: List[Dict[str, str]] = []
        for code in sorted(dimensions.keys()):
            display_name = self._normalize_text((dimensions.get(code) or {}).get("display_name") or code)
            if display_name:
                pairs.append({"name": display_name, "code": code})
        return pairs

    def get_business_term_maps(self) -> tuple[Dict[str, str], set[str]]:
        snapshot = self.get_active_snapshot()
        term_index = (snapshot or {}).get("term_index", {}) or {}
        synonym_map: Dict[str, str] = {}
        valid_values: set[str] = set()

        for term, entry in term_index.items():
            if not isinstance(entry, dict):
                continue
            canonical = self._normalize_text(entry.get("dimension_value"))
            term_text = self._normalize_text(term)
            if canonical:
                valid_values.add(canonical)
            if term_text and canonical:
                synonym_map[term_text] = canonical
                valid_values.add(term_text)

            for synonym in entry.get("synonyms") or []:
                synonym_text = self._normalize_text(synonym)
                if not synonym_text or not canonical:
                    continue
                synonym_map[synonym_text] = canonical
                valid_values.add(synonym_text)

        return synonym_map, valid_values

    def build_default_comparison_spec(
        self,
        question: str,
        metric_code: str = "",
        metric_name: str = "",
        scene_type: str = "comparison",
    ) -> Optional[Dict[str, Any]]:
        types = self._recommend_comparison_types(question, metric_code=metric_code, metric_name=metric_name, scene_type=scene_type)
        if not types:
            return None
        return {
            "enabled": True,
            "types": types,
        }

    def get_scene_keywords(self, scene_type: str, fallback: Optional[List[str]] = None) -> List[str]:
        policy = self._get_scene_policy(scene_type)
        keywords = self._extract_policy_string_list(policy, "keywords")
        if keywords:
            return keywords
        return list(fallback or [])

    def get_scene_core_metrics(self, scene_type: str, fallback: Optional[List[str]] = None) -> List[str]:
        policy = self._get_scene_policy(scene_type)
        metrics = self._extract_policy_string_list(policy, "core_metrics")
        if metrics:
            return metrics
        return list(fallback or [])

    def get_scene_drilldown_categories(
        self,
        scene_type: str,
        fallback: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, List[str]]:
        policy = self._get_scene_policy(scene_type)
        categories = self._extract_policy_string_map(policy, "drilldown_categories")
        if categories:
            return categories
        return dict(fallback or {})

    def _resolve_current_dimension_code(self, mql, dimensions: Dict[str, Dict[str, Any]]) -> Optional[str]:
        current_dimensions = getattr(mql, "dimensions", None) or []
        for dim in current_dimensions:
            column = getattr(dim, "column", "") or getattr(dim, "field", "") or ""
            if column and column in dimensions:
                return column

            dim_type = getattr(dim, "type", "") or ""
            if dim_type in dimensions:
                return dim_type

            for code, entry in dimensions.items():
                if entry.get("display_name") == dim_type:
                    return code
        return None

    def _recommend_comparison_types(
        self,
        question: str,
        metric_code: str = "",
        metric_name: str = "",
        scene_type: str = "comparison",
    ) -> List[str]:
        text = self._normalize_text(question)
        if not text:
            return []

        if "同比" in text:
            return ["同比"]
        if "环比" in text:
            return ["环比"]
        if not any(keyword in text for keyword in ["对比", "比较"]):
            return []

        resolved_metric_code = self._resolve_metric_code(metric_code=metric_code, metric_name=metric_name)
        capability = self._get_metric_capability(resolved_metric_code)

        default_type = self._get_default_comparison_type(scene_type=scene_type)
        if default_type and self._is_supported_comparison_type(capability, default_type):
            return [default_type]

        for candidate in ["同比", "环比"]:
            if self._is_supported_comparison_type(capability, candidate):
                return [candidate]

        return [default_type] if default_type else ["同比"]

    def _resolve_metric_code(self, metric_code: str = "", metric_name: str = "") -> str:
        normalized_code = self._normalize_text(metric_code)
        if normalized_code:
            return normalized_code
        normalized_name = self._normalize_text(metric_name)
        if not normalized_name:
            return ""
        resolved_metric = self.resolve_metric(normalized_name)
        if not resolved_metric:
            return ""
        return self._normalize_text(resolved_metric.get("metric_code") or resolved_metric.get("code"))

    def _get_metric_capability(self, metric_code: str) -> Dict[str, Any]:
        snapshot = self.get_active_snapshot()
        capabilities = (snapshot or {}).get("capabilities", {}) or {}
        if not metric_code:
            return {}
        return capabilities.get(f"metric:{metric_code}", {}) or {}

    def _get_default_comparison_type(self, scene_type: str = "comparison") -> str:
        policy_candidates = [
            self._get_scene_policy(scene_type),
            self._get_scene_policy("comparison"),
            self._get_scene_policy("simple_query"),
            self._get_scene_policy("followup"),
        ]

        for entry in policy_candidates:
            if not isinstance(entry, dict):
                continue
            direct_value = self._normalize_text(entry.get("default_comparison_type"))
            if direct_value:
                return direct_value
            policy_json = entry.get("policy", {}) or {}
            if isinstance(policy_json, dict):
                nested_value = self._normalize_text(policy_json.get("default_comparison_type"))
                if nested_value:
                    return nested_value

        return "同比"

    def _is_supported_comparison_type(self, capability: Dict[str, Any], comparison_type: str) -> bool:
        if not capability:
            return True
        if comparison_type == "同比":
            return bool(capability.get("supports_yoy") or capability.get("supports_comparison"))
        if comparison_type == "环比":
            return bool(capability.get("supports_mom") or capability.get("supports_comparison"))
        return bool(capability.get("supports_comparison"))

    def _get_scene_policy(self, scene_type: str) -> Dict[str, Any]:
        snapshot = self.get_active_snapshot()
        policies = (snapshot or {}).get("interaction_policies", {}) or {}
        entry = policies.get(scene_type) or {}
        return entry if isinstance(entry, dict) else {}

    def _extract_policy_string_list(self, policy: Dict[str, Any], key: str) -> List[str]:
        if not isinstance(policy, dict):
            return []

        value = policy.get(key)
        if isinstance(value, list):
            return [self._normalize_text(item) for item in value if self._normalize_text(item)]

        policy_json = policy.get("policy", {}) or {}
        if isinstance(policy_json, dict):
            nested = policy_json.get(key)
            if isinstance(nested, list):
                return [self._normalize_text(item) for item in nested if self._normalize_text(item)]

        return []

    def _extract_policy_string_map(self, policy: Dict[str, Any], key: str) -> Dict[str, List[str]]:
        if not isinstance(policy, dict):
            return {}

        candidates = [policy.get(key)]
        policy_json = policy.get("policy", {}) or {}
        if isinstance(policy_json, dict):
            candidates.append(policy_json.get(key))

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            result: Dict[str, List[str]] = {}
            for map_key, map_value in candidate.items():
                normalized_key = self._normalize_text(map_key)
                if not normalized_key or not isinstance(map_value, list):
                    continue
                normalized_values = [
                    self._normalize_text(item)
                    for item in map_value
                    if self._normalize_text(item)
                ]
                if normalized_values:
                    result[normalized_key] = normalized_values
            if result:
                return result

        return {}

    def _get_dimension_service(self):
        dimension_service = getattr(self, "_dimension_service", None)
        if dimension_service is not None:
            return dimension_service

        try:
            from ai.services.dimension_service import DimensionService

            dimension_service = DimensionService(base_url=self._base_url)
        except Exception as e:
            logger.warning(f"[SemanticSnapshotService] failed to load dimension service: {e}")
            dimension_service = None

        self._dimension_service = dimension_service
        return dimension_service

    def _resolve_dimension_from_term_index(self, candidate: str) -> Optional[Dict[str, Any]]:
        snapshot = self.get_active_snapshot()
        if not snapshot:
            return None

        term_index = snapshot.get("term_index", {}) or {}
        dimensions = snapshot.get("dimensions", {}) or {}
        normalized = self._normalize_text(candidate)
        lowered = normalized.lower()

        for term, entry in term_index.items():
            if not isinstance(entry, dict):
                continue

            matched = False
            term_text = self._normalize_text(term)
            if term_text and (normalized == term_text or lowered == term_text.lower()):
                matched = True

            synonyms = entry.get("synonyms") or []
            if not matched:
                for synonym in synonyms:
                    synonym_text = self._normalize_text(synonym)
                    if synonym_text and (normalized == synonym_text or lowered == synonym_text.lower()):
                        matched = True
                        break

            canonical_value = self._normalize_text(entry.get("dimension_value"))
            if not matched and canonical_value and (
                normalized == canonical_value or lowered == canonical_value.lower()
            ):
                matched = True

            if not matched:
                continue

            dim_code = self._normalize_text(entry.get("dimension_field"))
            if not dim_code:
                continue

            resolved_code = self.resolve_dimension_code(dim_code) or dim_code
            display_name = str((dimensions.get(resolved_code) or {}).get("display_name") or resolved_code).strip()
            is_generic = not canonical_value or canonical_value in {resolved_code, display_name}
            return self._build_dimension_resolution(
                resolved_code,
                None if is_generic else canonical_value,
                is_generic,
            )

        return None

    def _normalize_dimension_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        dim_code = self._normalize_text(result.get("column_name"))
        if not dim_code:
            return None

        resolved_code = self.resolve_dimension_code(dim_code) or dim_code
        is_generic = bool(result.get("is_generic"))
        dimension_value = None if is_generic else self._normalize_text(result.get("dimension_value"))
        return self._build_dimension_resolution(resolved_code, dimension_value, is_generic)

    def _build_dimension_resolution(
        self,
        dim_code: str,
        dimension_value: Optional[str],
        is_generic: bool,
    ) -> Dict[str, Any]:
        snapshot = self.get_active_snapshot()
        dimensions = (snapshot or {}).get("dimensions", {}) or {}
        display_name = str((dimensions.get(dim_code) or {}).get("display_name") or dim_code).strip()
        return {
            "column_name": dim_code,
            "dimension_value": None if is_generic else dimension_value,
            "is_generic": is_generic,
            "dimension_type": display_name,
        }

    def _normalize_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _unique_ordered(self, items: List[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for item in items:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _normalize_scene_types(self, scene_type: str) -> List[str]:
        mapping = {
            "generic_query": ["generic_query", "analysis"],
            "volatility": ["volatility", "analysis"],
            "comparison": ["comparison", "analysis"],
            "ad_effect": ["ad_effect", "analysis"],
            "inventory_risk": ["inventory_risk", "analysis"],
            "context_followup": ["context_followup", "followup", "analysis"],
        }
        return mapping.get(scene_type, [scene_type, "analysis"] if scene_type else ["analysis"])


_semantic_snapshot_service: Optional[SemanticSnapshotService] = None


def get_semantic_snapshot_service(base_url: Optional[str] = None) -> SemanticSnapshotService:
    global _semantic_snapshot_service
    if _semantic_snapshot_service is None:
        _semantic_snapshot_service = SemanticSnapshotService(base_url=base_url)
    return _semantic_snapshot_service
