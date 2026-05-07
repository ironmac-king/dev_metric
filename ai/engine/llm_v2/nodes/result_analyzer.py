"""
步骤 10: 结果分析智能体

职责：
- 分析查询结果
- 生成自然语言回答
- 生成建议问题
"""
import json
import re
from typing import Dict, Any, List
from ai.config.logging_config import get_logger
from ai.engine.llm import get_llm_engine
from ..schema import MQLSchema, SQLResult, AnomalyAnnotation

logger = get_logger("ai.llm_v2.result_analyzer")

# 列名→中文映射（与 router.py 保持一致）
_DIM_COL_CHINESE = {
    "GROUP_3": "三级品类", "GROUP_2": "二级品类", "GROUP_1": "一级品类", "GROUP_4": "四级品类",
    "FSITE": "店铺", "FCOUNTRY": "国家", "FREGION": "区域", "FCHANNEL": "渠道",
    "PLATFORM": "平台", "FDATE": "日期", "MONTHS": "月份", "YEARS": "年份",
    "WEEKS": "周", "QUARTERS": "季度", "SKU": "SKU", "ASIN": "ASIN",
    "FBRANDS": "品牌", "FPRODUCTLINE": "产品线", "FADTYPE": "广告类型",
    "DT": "日期", "DATE": "日期", "STAT_DATE": "统计日期",
    "FSITECODE": "站点编码",
}
_METRIC_SUFFIX_CHINESE = {
    "_raw": "当前值", "current_val": "当前值", "mom_val": "环比", "yoy_val": "同比",
    "_yoy": "同比", "_mom": "环比", "_wow": "周环比", "_wow_val": "周环比",
    "_rank": "排名", "_running_sum": "累计值", "_ratio": "占比", "_pct": "占比", "_ma7": "7日均值",
}


class ResultAnalyzer:
    """
    结果分析智能体

    使用 LLM 分析查询结果，生成自然语言回答。
    """

    def __init__(self):
        self._llm_engine = get_llm_engine()
        self._semantic_service = None
        from ai.config.runtime import get_go_api_base
        self._go_api_base = get_go_api_base()

    def _get_semantic_service(self):
        """延迟加载语义快照服务（单例，从内存快照读取，不发 HTTP）"""
        if self._semantic_service is None:
            from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
            self._semantic_service = get_semantic_snapshot_service()
        return self._semantic_service

    def _col(self, mql: MQLSchema, suffix: str, fallback: str) -> str:
        """构建 CTE 新别名：{metric_name}_{suffix}，回退到旧 generic 列名"""
        name = mql.metric.name if mql.metric and mql.metric.name else ""
        return f"{name}{suffix}" if name else fallback

    def _generate_supplementary_info(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
    ) -> List[Dict[str, Any]]:
        """
        从语义快照的 capabilities 生成补充信息，用于类型 B 查询。

        Returns:
            [
                {"label": "同比", "value": "+12.3%", "trend": "+"},
                {"label": "环比", "value": "-5.2%", "trend": "-"},
                {"label": "昨日同期", "value": "100.00万", "trend": "+"},
                {"label": "本月累计", "value": "3,456.00万", "trend": None},
            ]
        """
        if not mql.metric or not sql_result.data:
            return []

        metric_code = mql.metric.code or ""
        if not metric_code:
            return []

        # ========== 优先使用语义层 enrich() 获取 ==========
        metric_cap = None
        try:
            from ai.services.semantic_layer import get_semantic_layer_service, EnrichStage
            from ai.services.semantic_layer.api import ParseResult

            semantic_layer = get_semantic_layer_service()
            parse_result = ParseResult(intent="", confidence=0.0, metric_code=metric_code)
            enrich_result = semantic_layer.enrich(parse_result, stage=EnrichStage.RESULT_ANALYSIS)
            if enrich_result.metric_capability:
                metric_cap = enrich_result.metric_capability
                logger.info(f"[ResultAnalyzer] 从语义层获取 metric_capability: {metric_code}")
        except Exception as e:
            logger.warning(f"[ResultAnalyzer] 语义层获取 metric_capability 失败: {e}")
        # ====================================================

        # 回退到直接调用语义快照
        if not metric_cap:
            semantic_svc = self._get_semantic_service()
            snapshot = semantic_svc.get_active_snapshot() if semantic_svc else None
            if not snapshot:
                logger.warning(f"[ResultAnalyzer] _generate_supplementary_info: no active snapshot, metric_code={metric_code}")
                return []
            capabilities = snapshot.get("capabilities", {}) or {}
            metric_cap = capabilities.get(f"metric:{metric_code}", {}) or {}

        # 获取当前指标值（从 sql_result）
        row = sql_result.data[0] if sql_result.data else {}
        logger.info(f"[ResultAnalyzer] _generate_supplementary_info: metric_code={metric_code}, supports_yoy={metric_cap.get('supports_yoy')}, supports_mom={metric_cap.get('supports_mom')}, row_keys={list(row.keys()) if row else []}")

        info: List[Dict[str, Any]] = []
        current_val = None
        for v in row.values():
            if isinstance(v, (int, float)):
                current_val = float(v)
                break

        # YoY 同比
        if metric_cap.get("supports_yoy"):
            yoy_val = row.get("yoy_val") or row.get("同比值")
            yoy_change = row.get("yoy_change") or row.get("同比变化")
            if yoy_val is not None or yoy_change is not None:
                try:
                    if yoy_change is not None:
                        change_val = float(str(yoy_change).replace("%", "").replace(",", ""))
                        trend = "+" if change_val > 0 else "-" if change_val < 0 else None
                        # yoy_change 可能已包含 +/- 前缀（如 "+12.3%"），或只有数值（如 "12.3%"）
                        # 如果已带符号直接用，否则根据趋势补前缀
                        if str(yoy_change).startswith(("+", "-")):
                            value_str = yoy_change
                        else:
                            value_str = f"{'+' if change_val > 0 else ''}{yoy_change}"
                        info.append({
                            "label": "同比",
                            "value": value_str,
                            "trend": trend,
                        })
                except (ValueError, TypeError):
                    pass

        # MoM 环比
        if metric_cap.get("supports_mom"):
            mom_val = row.get("mom_val") or row.get("环比值")
            mom_change = row.get("mom_change") or row.get("环比变化")
            if mom_val is not None or mom_change is not None:
                try:
                    if mom_change is not None:
                        change_val = float(str(mom_change).replace("%", "").replace(",", ""))
                        trend = "+" if change_val > 0 else "-" if change_val < 0 else None
                        info.append({
                            "label": "环比",
                            "value": f"{'+' if change_val > 0 else ''}{mom_change}",
                            "trend": trend,
                        })
                except (ValueError, TypeError):
                    pass

        # 昨日同期（如果时间粒度是天）
        if mql.time and sql_result.data:
            time_original = mql.time.original or ""
            # 只有天粒度才显示"昨日"
            if any(k in time_original for k in ["今日", "昨天", "日"]):
                yesterday_val = row.get("yesterday_val") or row.get("昨日值")
                if yesterday_val is not None:
                    info.append({
                        "label": "昨日同期",
                        "value": self._format_value(yesterday_val),
                        "trend": None,
                    })

        # 本月累计（根据指标配置判断是否显示）
        if metric_cap.get("supports_trend") and current_val is not None:
            month_total = row.get("month_total") or row.get("本月累计")
            if month_total is not None:
                info.append({
                    "label": "本月累计",
                    "value": self._format_value(month_total),
                    "trend": None,
                })

        return info

    def _get_time_context(self, mql: MQLSchema) -> str:
        """从 MQL 获取时间上下文，用于建议问题拼接"""
        if mql.time and mql.time.original:
            return mql.time.original
        return "本月"

    def _get_dim_label_from_service(self) -> Dict[str, str]:
        """从 DimensionService 获取用户友好的维度名称映射"""
        try:
            from ai.services.dimension_service import DimensionService
            svc = DimensionService()
            options = svc.get_ranking_options()
            result = {}
            for opt in options:
                col = opt.get("value", "")
                label = opt.get("label", "")
                if label.startswith("按"):
                    label = label[1:]
                if col and label:
                    result[col.upper()] = label
            return result
        except Exception:
            return {}

    def _get_alternative_dimensions(self, current_dim_type: str = None) -> tuple:
        """
        获取与当前维度不同的替代维度，用于建议问题生成。

        优先级：站点 > 三级品类 > 二级品类 > 一级品类
        即：如果当前是站点 → 推荐三级品类
            如果当前是三级品类 → 推荐站点
            ...
        """
        dim_priority = ["FSITE", "GROUP_3", "GROUP_2", "GROUP_1"]
        # 中文类型名 → 英文字段名 映射
        dim_type_to_col = {
            "站点": "FSITE", "FSITE": "FSITE",
            "三级品类": "GROUP_3", "GROUP_3": "GROUP_3",
            "二级品类": "GROUP_2", "GROUP_2": "GROUP_2",
            "一级品类": "GROUP_1", "GROUP_1": "GROUP_1",
            "四级品类": "GROUP_4", "GROUP_4": "GROUP_4",
            "ASIN": "ASIN", "SKU": "SKU",
            "平台": "PLATFORM", "PLATFORM": "PLATFORM",
        }
        label_map = self._get_dim_label_from_service()

        if not current_dim_type:
            dim_col = dim_priority[0]
        else:
            # 将中文/英文类型名统一转换为英文字段名
            current_col = dim_type_to_col.get(current_dim_type, current_dim_type.upper())
            candidates = [d for d in dim_priority if d != current_col]
            dim_col = candidates[0] if candidates else dim_priority[0]

        dim_label = label_map.get(dim_col, dim_col)
        return dim_col, dim_label

    async def analyze(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
        is_generic_result: bool = False,
        clarification_message: str = "",
        clarification_options: List[Dict[str, Any]] = None,
        analysis: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        分析结果

        Args:
            mql: MQL Schema
            sql_result: SQL 执行结果
            question: 原始问题
            is_generic_result: 是否为泛指默认结果
            clarification_message: 追问引导消息
            clarification_options: 追问选项列表
            analysis: 触发分析结果（可选）

        Returns:
            {
                "answer": str,
                "suggestions": List[str],
                "analysis": Dict (如果有触发分析),
                "mode": "triggered" or "direct",
            }
        """
        logger.info("[ResultAnalyzer] 分析结果")

        # 1. 处理空数据
        if not sql_result.data:
            result = await self._handle_empty_result(mql, question)
            # 附加泛指维度追问引导
            if is_generic_result and clarification_message:
                result["answer"] += f"\n\n{clarification_message}"
                if clarification_options:
                    options_text = " ".join([f"[{o['label']}]" for o in clarification_options])
                    result["answer"] += f" {options_text}"
            return result

        # 1.5 处理全空值数据（有行但指标值全为 None/0）
        all_empty = self._all_values_empty(sql_result.data)
        logger.info(f"[ResultAnalyzer] _all_values_empty={all_empty}, data_sample={sql_result.data[:2] if sql_result.data else 'empty'}")

        if all_empty:
            metric_name = mql.metric.name if mql.metric else "指标"
            time_desc = mql.time.original if mql.time and mql.time.original else "指定时间段"
            logger.info("[ResultAnalyzer] SQL有行但指标值全为空，返回一句话")
            return {
                "answer": f"{time_desc}{metric_name}暂无数据。",
                "suggestions": [
                    f"本月{metric_name}是多少",
                    f"各站点{metric_name}排名",
                ],
                "explanation": self._build_explanation(mql),
            }

        # 2. 根据意图生成回答
        intent = mql.intent.value if mql.intent else "query_value"

        if intent == "query_value":
            result = await self._handle_value_query(mql, sql_result, question)
            logger.info(f"[ResultAnalyzer] _handle_value_query returned: answer={result.get('answer', '')[:50]}, supplementary_info={result.get('supplementary_info')}, suggestions_count={len(result.get('suggestions', []))}")
        elif intent == "query_trend":
            result = await self._handle_trend_query(mql, sql_result, question)
        elif intent == "query_comparison":
            result = await self._handle_comparison_query(mql, sql_result, question)
        elif intent == "query_ranking":
            result = await self._handle_ranking_query(mql, sql_result, question)
        elif intent == "query_ratio":
            result = await self._handle_ratio_query(mql, sql_result, question)
        else:
            result = await self._handle_default(mql, sql_result, question)

        # 3. 检测异常（仅记录到 result，不追加到 answer 文本）
        # metric_name = mql.metric.name if mql.metric else "指标"
        # dim_types = [d.type for d in mql.dimensions] if mql.dimensions else []
        # anomalies = self.detect_anomalies(sql_result.data, metric_name, dim_types)
        # if anomalies:
        #     anomaly_messages = [a.message for a in anomalies]
        #     result["answer"] += f"\n\n⚠️ 异常提醒：{'；'.join(anomaly_messages)}"
        #     result["anomalies"] = [a.to_dict() for a in anomalies]

        # 3.5 构建解释信息
        result["explanation"] = self._build_explanation(mql)

        # 4. 附加泛指维度追问引导
        if is_generic_result and clarification_message:
            result["answer"] += f"\n\n{clarification_message}"
            if clarification_options:
                options_text = " ".join([f"[{o['label']}]" for o in clarification_options])
                result["answer"] += f" {options_text}"
                # 返回结构化的 clarification_options 供前端渲染按钮
                result["clarification_options"] = clarification_options
                result["clarification_message"] = clarification_message

        # 5. 固定骨架模板（所有查询统一）
        logger.info(f"[ResultAnalyzer] analysis is {'truthy' if analysis else 'falsy'}")

        if analysis:
            result["analysis"] = analysis
            result["mode"] = "triggered"
        else:
            result["mode"] = "direct"

        metric_name = mql.metric.name if mql.metric else "指标"

        # 三个开关
        data = sql_result.data if sql_result else []
        has_multi_dim = len(data) > 1
        if not has_multi_dim and len(data) == 1 and data[0]:
            # 单行但有维度列（如 GROUP_1, FSITE 等）也算多维度
            has_multi_dim = any(
                k for k in data[0].keys()
                if k in _DIM_COL_CHINESE or k.startswith("GROUP_")
            )
        has_fluctuation = bool(analysis and analysis.get("breakdown"))
        has_actionable = bool(analysis and analysis.get("action_items"))

        sections = []
        _CN = ["一", "二", "三", "四", "五", "六"]
        _si = 0  # section index

        # 小结（必有）— 只取第一段，不混数据表
        conclusion = ""
        if analysis and analysis.get("summary"):
            conclusion = analysis["summary"]
        else:
            conclusion = result.get("answer", "")
        # 统一截断：只保留第一段（双换行之前）
        if conclusion and "\n\n" in conclusion:
            conclusion = conclusion.split("\n\n")[0].strip()
        elif conclusion and "\n" in conclusion:
            conclusion = conclusion.split("\n")[0].strip()
        if conclusion:
            _si += 1
            sections.append(f"**{_CN[_si - 1]}、小结**\n{conclusion}")

        # 核心指标（必有）
        kpi_parts = []
        if analysis and analysis.get("kpi"):
            kpi = analysis["kpi"]
            current = kpi.get("current")
            if current is not None:
                kpi_parts.append(f"{metric_name}：{self._format_value(current)}")
            mom = kpi.get("mom")
            if mom is not None:
                mom_sign = "增长" if mom >= 0 else "下降"
                kpi_parts.append(f"环比{mom_sign} {abs(mom):.1f}%")
            yoy = kpi.get("yoy")
            if yoy is not None:
                yoy_sign = "增长" if yoy >= 0 else "下降"
                kpi_parts.append(f"同比{yoy_sign} {abs(yoy):.1f}%")
        elif result.get("supplementary_info"):
            for info in result["supplementary_info"]:
                if info.get("label") and info.get("value"):
                    kpi_parts.append(f"{info['label']} {info['value']}")
        # 兜底：从数据提取指标值（排除维度列），多行时汇总求和
        if not kpi_parts and data:
            row = data[0]
            dim_cols = set()
            if mql.dimensions:
                for d in mql.dimensions:
                    if d.column:
                        dim_cols.add(d.column.upper())
            for col, val in row.items():
                upper = col.upper()
                if upper in dim_cols or upper.startswith("GROUP_") or col in _DIM_COL_CHINESE:
                    continue
                skip_kw = ("环比变化", "环比上期", "同比变化", "同比上期", "MOM_CHANGE", "YOY_CHANGE",
                           "MOM_VAL", "YOY_VAL", "FSITECODE", "FDATE", "MONTHS")
                if any(kw in upper for kw in skip_kw):
                    continue
                col_clean = col.replace("_raw", "").replace("当前值", "").replace("_change", "").strip(" _")
                if not col_clean:
                    col_clean = metric_name
                # 多行数据时汇总求和
                if len(data) > 1:
                    total = 0
                    for r in data:
                        v = r.get(col)
                        if v is not None:
                            try:
                                total += float(str(v).replace(",", ""))
                            except (ValueError, TypeError):
                                pass
                    formatted = self._format_value(total)
                    kpi_parts.append(f"{col_clean}合计：{formatted}")
                else:
                    formatted = self._format_value(val)
                    kpi_parts.append(f"{col_clean}：{formatted}")
        # 最终兜底：至少显示指标名
        if not kpi_parts:
            kpi_parts.append(f"{metric_name}")
        _si += 1
        sections.append(f"**{_CN[_si - 1]}、核心指标**\n" + "，".join(kpi_parts))

        # 核心指标 tooltip 信息（业务定义 + 对比期间）
        tooltip_info = self._build_kpi_tooltip(mql, analysis, sql_result)
        if tooltip_info:
            result["kpi_tooltip"] = tooltip_info

        # 数据图表（有多维度/趋势/归因数据才出）
        if has_multi_dim or has_fluctuation:
            _si += 1
            sections.append(f"**{_CN[_si - 1]}、数据图表**\n（前端展示）")

        # 维度明细（有多维度才出，先构建内容再判断是否有效）
        dim_detail_has_contribution = False
        if has_multi_dim:
            dim_text = ""
            if analysis and analysis.get("breakdown"):
                dim_text = self._build_dim_value_text(analysis["breakdown"])
            elif data:
                # 数据 >= 3 行且有维度和时间范围时，尝试异步版本（涨跌幅+贡献度）
                if len(data) >= 3 and mql.time and mql.time.start and mql.time.end:
                    try:
                        dim_text, dim_mom = await self._build_dim_detail_text_async(mql, data)
                        if dim_text:
                            dim_detail_has_contribution = True
                        if dim_mom:
                            result["dim_mom_data"] = dim_mom
                    except Exception as e:
                        logger.warning(f"[ResultAnalyzer] 异步维度明细失败，回退: {e}")
                        dim_text = self._build_dim_detail_text(mql, data)
                else:
                    dim_text = self._build_dim_detail_text(mql, data)
            if dim_text and dim_text.strip("：\n "):
                _si += 1
                sections.append(f"**{_CN[_si - 1]}、维度明细**\n" + dim_text)

        # 归因分析（有涨跌波动才出，但如果维度明细已含贡献度则隐藏）
        if has_fluctuation and not dim_detail_has_contribution:
            attr_text = self._build_attribution_text(analysis["breakdown"])
            if attr_text and attr_text.strip("：\n "):
                _si += 1
                sections.append(f"**{_CN[_si - 1]}、归因分析**\n" + attr_text)

        # 建议结论（有分析就给，先构建内容再判断是否有效）
        if has_actionable:
            action_text = self._build_action_text(analysis["action_items"])
            if action_text and action_text.strip("：\n "):
                _si += 1
                sections.append(f"**{_CN[_si - 1]}、建议结论**\n" + action_text)

        if sections:
            result["answer"] = self._clean_raw_names("\n\n".join(sections))

        # 6. 优先从语义快照增强 suggestions（如果当前 suggestions 为空或过少）
        # ========== 优先使用语义层 recommend() 获取 ==========
        try:
            from ai.services.semantic_layer import get_semantic_layer_service
            from ai.services.semantic_layer.api import RecommendContext, ParseResult

            semantic_layer = get_semantic_layer_service()
            parse_result = ParseResult(intent=intent, confidence=0.0,
                                       metric_name=mql.metric.name if mql.metric else None,
                                       metric_code=mql.metric.code if mql.metric else None)
            recommend_context = RecommendContext(stage="result_analysis", parse_result=parse_result)
            recommend_result = semantic_layer.recommend(recommend_context)
            if recommend_result.next_questions:
                current = result.get("suggestions") or []
                seen = set(current)
                for s in recommend_result.next_questions:
                    if s not in seen:
                        seen.add(s)
                        current.append(s)
                result["suggestions"] = current[:6]
                logger.info(f"[ResultAnalyzer] 从语义层增强 suggestions: {recommend_result.next_questions}")
        except Exception as e:
            logger.warning(f"[ResultAnalyzer] 语义层 recommend 失败: {e}")
            # 回退到直接调用语义快照
            semantic_svc = self._get_semantic_service()
            if semantic_svc:
                scene_type_map = {
                    "query_value": "query_value",
                    "query_trend": "query_trend",
                    "query_comparison": "query_comparison",
                    "query_ranking": "query_ranking",
                    "query_ratio": "query_ratio",
                }
                scene_type = scene_type_map.get(intent, "query_value")
                snapshot_suggestions = semantic_svc.recommend_next_questions(mql, scene_type)
                if snapshot_suggestions:
                    current = result.get("suggestions") or []
                    seen = set(current)
                    for s in snapshot_suggestions:
                        if s not in seen:
                            seen.add(s)
                            current.append(s)
                    result["suggestions"] = current[:6]
                    logger.info(f"[ResultAnalyzer] 从语义快照增强 suggestions: {snapshot_suggestions}")

        return result

    def _build_dimension_empty_result(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """SQL 有行但指标值全为空：一句话小结"""
        metric_name = mql.metric.name if mql.metric else "指标"
        time_desc = mql.time.original if mql.time and mql.time.original else "指定时间段"

        return {
            "answer": f"{time_desc}{metric_name}暂无数据。",
            "suggestions": [
                f"本月{metric_name}是多少",
                f"各站点{metric_name}排名",
            ],
            "explanation": self._build_explanation(mql),
        }

    async def _handle_empty_result(self, mql: MQLSchema, question: str) -> Dict[str, Any]:
        """处理空结果"""
        # 从语义快照获取元数据，帮助 LLM 给出具体建议
        snapshot_hints = ""
        try:
            from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
            snap = get_semantic_snapshot_service()
            snapshot = snap.get_active_snapshot()
            if snapshot:
                payload = snapshot.get("payload", snapshot)
                metrics = payload.get("metrics", {})
                metric_code = mql.metric.code if mql.metric else ""
                metric_data = metrics.get(metric_code, {})
                if metric_data:
                    cap = metric_data.get("metric_capability", {})
                    earliest = cap.get("earliest_data_date", "")
                    time_grains = cap.get("supported_time_grains", [])
                    if earliest:
                        snapshot_hints += f"\n数据最早日期：{earliest}"
                    if time_grains:
                        snapshot_hints += f"\n支持的时间粒度：{', '.join(time_grains)}"
        except Exception:
            pass

        prompt = f"""用户问题：{question}
查询结果：暂无数据
{snapshot_hints}

请分析可能的原因，并给出 2-3 个具体的建议问题（包含明确的时间范围或维度）。

请以 JSON 格式返回：
{{"analysis": "原因分析", "suggestions": ["建议问题1", "建议问题2"]}}

只输出 JSON，不要有其他内容。"""

        try:
            response = self._llm_engine.call(prompt, temperature=0.5, max_tokens=500)
            result = json.loads(response)
            return {
                "answer": f"抱歉，暂未查询到数据。{result.get('analysis', '')}",
                "suggestions": result.get("suggestions", []),
            }
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            metric_name = mql.metric.name if mql.metric else "指标值"
            return {
                "answer": "抱歉，暂未查询到数据。请尝试调整时间范围或查询条件。",
                "suggestions": [
                    f"本月{metric_name}是多少",
                    f"查看其他{metric_name}数据",
                ],
            }

    async def _handle_value_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理数值查询"""
        data = sql_result.data
        time_context = self._get_time_context(mql)

        if len(data) == 1:
            # 单值查询
            row = data[0]
            metric_name = mql.metric.name if mql.metric else "指标值"

            # 检查是否有多指标（mql.metrics）
            has_multiple_metrics = mql.metrics and len(mql.metrics) > 0

            if has_multiple_metrics and len(row) > 1:
                # 多指标查询：显示所有指标值
                parts = []
                for col_name, value in row.items():
                    # 维度列（如SKU、日期）不格式化，保持原样
                    if self._is_metric_column(col_name):
                        formatted_value = self._format_value(value)
                        parts.append(f"{col_name}: {formatted_value}")
                    else:
                        parts.append(f"{col_name}: {value}")
                answer = " | ".join(parts)
                # 收集所有指标名用于建议
                metric_names = [mql.metric.name] if mql.metric else []
                metric_names.extend([m.name for m in mql.metrics if m.name])
                _, alt_label = self._get_alternative_dimensions(None)
                # 生成补充信息
                supplementary_info = self._generate_supplementary_info(mql, sql_result)
                return {
                    "answer": answer,
                    "suggestions": [
                        f"查看{time_context}各{alt_label}{metric_names[0]}趋势变化" if metric_names else f"查看{time_context}各{alt_label}趋势变化",
                        f"按{alt_label}维度对比上月" if metric_names else f"按{alt_label}维度对比上月",
                    ],
                    "supplementary_info": supplementary_info,
                }
            else:
                # 单指标查询
                value = list(row.values())[0] if row else 0
                formatted_value = self._format_value(value)
                _, alt_label = self._get_alternative_dimensions(None)
                # 生成补充信息
                supplementary_info = self._generate_supplementary_info(mql, sql_result)
                return {
                    "answer": f"{metric_name}为 {formatted_value}",
                    "suggestions": [
                        f"查看{time_context}各{alt_label}{metric_name}趋势变化",
                        f"按{alt_label}维度对比上月",
                    ],
                    "supplementary_info": supplementary_info,
                }

        # 多行数据
        metric_name = mql.metric.name if mql.metric else "指标值"
        # 获取指标列名（用于判断哪些列需要格式化）
        metric_columns = set()
        if mql.metric and mql.metric.name:
            pass
        if mql.metrics:
            for m in mql.metrics:
                if m.name:
                    metric_columns.add(m.name)
        if mql.metric and mql.metric.name:
            metric_columns.add(mql.metric.name)

        col_map = self._build_col_map(mql)

        lines = []
        for row in data[:5]:
            parts = []
            for k, v in row.items():
                display_k = col_map.get(k, k)
                # 用原始列名判断是否需要格式化
                if k in metric_columns or self._is_metric_column(k):
                    parts.append(f"{display_k}: {self._format_value(v)}")
                else:
                    parts.append(f"{display_k}: {v}")
            lines.append(" | ".join(parts))

        answer = "查询结果：\n" + "\n".join(lines)
        if len(data) > 5:
            answer += f"\n... 还有 {len(data) - 5} 条数据"

        # 生成带维度上下文的建议（维度错开，时间一致）
        time_context = self._get_time_context(mql)
        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)

        return {
            "answer": answer,
            "suggestions": [
                f"查看{time_context}各{alt_label}{metric_name}排名前10",
                f"按{alt_label}维度分析{metric_name}",
            ],
        }

    async def _handle_trend_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理趋势查询"""
        data = sql_result.data
        metric_name = mql.metric.name if mql.metric else "指标值"

        # 检查是否是 MoM/YOY 格式的单行数据（包含 current_val 和 compare_val，或新的 mom_val/yoy_val）
        row = data[0] if data else {}
        is_mom_yoy_format = (
            len(data) == 1 and
            isinstance(row, dict) and
            'current_val' in row and
            ('compare_val' in row or 'mom_val' in row or 'yoy_val' in row)
        )

        if is_mom_yoy_format:
            # MoM/YOY 单行数据：current_val 和 compare_val 在同一行，或者新的 mom_val/yoy_val
            current_val = float(row.get('current_val', 0) or 0)

            # 优先使用新的 mom_val/yoy_val 格式，其次使用旧的 compare_val 格式
            mom_val = float(row.get('mom_val', 0) or 0) if 'mom_val' in row else None
            yoy_val = float(row.get('yoy_val', 0) or 0) if 'yoy_val' in row else None
            compare_val = float(row.get('compare_val', 0) or 0) if 'compare_val' in row else None

            mom_change = row.get('mom_change', '')
            yoy_change = row.get('yoy_change', '')
            change_rate = row.get('change_rate', '')
            trend = row.get('trend', '')

            # 生成描述
            unit = mql.metric.unit if mql.metric and mql.metric.unit else ""

            # 判断是 MoM 还是 YoY
            is_yoy = mql.has_yoy
            is_mom = mql.has_mom

            if is_yoy and yoy_val is not None and yoy_val != 0:
                # 同比数据
                if yoy_change:
                    change_desc = f"同比{'上升' if float(str(yoy_change).replace('%','')) > 0 else '下降'}了 {abs(float(str(yoy_change).replace('%','')))}%"
                else:
                    change_desc = ""
                if unit:
                    compare_str = f"{yoy_val:,.2f}{unit}"
                else:
                    compare_str = f"{yoy_val:,.2f}"
                answer = f"{metric_name}整体同比{'上升' if float(str(yoy_change).replace('%','')) > 0 else '下降' if yoy_change else '持平'}，{change_desc}（当前：{current_val:,.2f}{unit}，去年同期：{compare_str}）"
            elif is_mom and mom_val is not None and mom_val != 0:
                # 环比数据
                if mom_change:
                    change_desc = f"环比{'上升' if float(str(mom_change).replace('%','')) > 0 else '下降'}了 {abs(float(str(mom_change).replace('%','')))}%"
                else:
                    change_desc = ""
                if unit:
                    compare_str = f"{mom_val:,.2f}{unit}"
                else:
                    compare_str = f"{mom_val:,.2f}"
                answer = f"{metric_name}整体环比{'上升' if float(str(mom_change).replace('%','')) > 0 else '下降' if mom_change else '持平'}，{change_desc}（当前：{current_val:,.2f}{unit}，上期：{compare_str}）"
            else:
                # 旧格式 fallback
                if trend == '增长':
                    trend_desc = "增长"
                    change_desc = f"上升了 {change_rate}%" if change_rate else ""
                elif trend == '下降':
                    trend_desc = "下降"
                    change_desc = f"下降了 {change_rate}%" if change_rate else ""
                else:
                    trend_desc = "持平"
                    change_desc = ""

                if unit:
                    current_str = f"{current_val:,.2f}{unit}"
                    compare_str = f"{compare_val:,.2f}{unit}" if compare_val else "N/A"
                else:
                    current_str = f"{current_val:,.2f}"
                    compare_str = f"{compare_val:,.2f}" if compare_val else "N/A"

                answer = f"{metric_name}整体{trend_desc}，{change_desc}（当前：{current_str}，对比期：{compare_str}）"

            current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
            _, alt_label = self._get_alternative_dimensions(current_dim)

            # 获取多个替代维度（三级品类 + 二级品类 + 一级品类）
            dim_priority = ["FSITE", "GROUP_3", "GROUP_2", "GROUP_1"]
            label_map = self._get_dim_label_from_service()
            dim_type_to_col = {
                "站点": "FSITE", "FSITE": "FSITE",
                "三级品类": "GROUP_3", "GROUP_3": "GROUP_3",
                "二级品类": "GROUP_2", "GROUP_2": "GROUP_2",
                "一级品类": "GROUP_1", "GROUP_1": "GROUP_1",
            }
            current_col = dim_type_to_col.get(current_dim, current_dim.upper()) if current_dim else "FSITE"
            # 过滤掉当前维度，取后续所有维度
            alt_dims = [d for d in dim_priority if d != current_col]

            # 用户问环比 → 推荐同比+异维度；用户问同比 → 推荐环比+异维度
            if is_mom:
                alt_type = "同比"
                same_type = "环比"
            else:
                alt_type = "环比"
                same_type = "同比"

            # 第一建议：当前维度的另一种对比类型（如 同比 → 环比）
            # 第二、三建议：其他维度 + 当前对比类型（提供不同视角）
            suggestions = [
                f"查看各{alt_label}{metric_name}{alt_type}变化",
            ]
            for dim_col in alt_dims[:2]:  # 最多加两个异维度建议
                dim_lbl = label_map.get(dim_col, dim_col)
                suggestions.append(f"查看各{dim_lbl}{metric_name}{same_type}变化")

            return {
                "answer": answer,
                "suggestions": suggestions,
            }

        # 原始时间序列趋势分析（多行数据）
        if len(data) < 2:
            return {
                "answer": "数据点不足，无法分析趋势",
                "suggestions": [],
            }

        # 简单趋势分析：只收集数值类型的列，跳过字符串列（如"月份"）
        # 关键：跳过 primary metric 列为 null 的行（如当月数据未完成）
        metric_col = None
        for k in row.keys():
            if k not in ("月份", "MONTHS", "FDATE", "date", "时间", "time", "dummy"):
                metric_col = k
                break
        values = []
        for row in data:
            # 跳过 metric 值为 null 的行（如当月数据未完成）
            if metric_col and row.get(metric_col) is None:
                continue
            for k, v in row.items():
                if k in ("月份", "MONTHS", "FDATE", "date", "时间", "time"):
                    continue
                try:
                    values.append(float(str(v).replace(",", "")))
                except (ValueError, TypeError):
                    continue

        if len(values) < 2:
            return {
                "answer": "数据不足，无法分析趋势",
                "suggestions": [],
            }

        first = values[0]
        last = values[-1]
        change = (last - first) / first * 100 if first != 0 else 0

        trend = "上升" if change > 0 else "下降"
        answer = f"趋势{trend}，变化幅度 {abs(change):.1f}%"

        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)
        return {
            "answer": answer,
            "suggestions": [
                f"查看各{alt_label}{metric_name}同比变化",
                f"查看各{alt_label}{metric_name}环比变化",
            ],
        }

    async def _handle_comparison_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理对比查询"""
        data = sql_result.data
        metric_name = mql.metric.name if mql.metric else "指标值"
        time_context = self._get_time_context(mql)

        # 检查是否是 MoM/YOY 格式的单行数据（包含 current_val 和 compare_val，或新的 mom_val/yoy_val）
        # 注意：SQL 生成器使用中文列名（当前值/环比值/同比值），需要同时兼容英文和中文列名
        row = data[0] if data else {}
        is_mom_format = (
            len(data) == 1 and
            isinstance(row, dict) and
            ('current_val' in row or '当前值' in row) and
            ('compare_val' in row or 'mom_val' in row or 'yoy_val' in row or
             '环比值' in row or '同比值' in row)
        )

        if is_mom_format:
            # MoM/YOY 单行数据：current_val 和 compare_val 在同一行，或者新的 mom_val/yoy_val
            # 支持中英文列名
            current_val = float(row.get('current_val') or row.get('当前值') or 0)

            # 优先使用新的 mom_val/yoy_val 格式，其次使用旧的 compare_val 格式，最后尝试中文列名
            mom_val = float(row.get('mom_val') or row.get('环比值') or 0) if 'mom_val' in row or '环比值' in row else None
            yoy_val = float(row.get('yoy_val') or row.get('同比值') or 0) if 'yoy_val' in row or '同比值' in row else None
            compare_val = float(row.get('compare_val', 0) or 0) if 'compare_val' in row else None

            mom_change = row.get('mom_change', row.get('环比变化', ''))
            yoy_change = row.get('yoy_change', row.get('同比变化', ''))
            change_rate = row.get('change_rate', '')
            trend = row.get('trend', '')

            # 判断是环比(MoM)还是同比(YoY)
            is_yoy = mql.has_yoy
            is_mom = mql.has_mom
            period_label = "同比" if is_yoy else ("环比" if is_mom else "")

            # 从 MQL time 提取实际期间描述
            time_start = mql.time.start if mql.time else ""

            # 格式化期间名称（取开始时间的年月）
            def format_period(start_str):
                if not start_str:
                    return "上期"
                try:
                    import datetime
                    dt = datetime.datetime.strptime(start_str[:10], "%Y-%m-%d")
                    return f"{dt.year}年{dt.month}月"
                except:
                    return start_str[:7] if start_str else "上期"

            current_period = format_period(time_start)

            # 生成回答
            if is_yoy and yoy_val is not None and yoy_val != 0:
                # 同比数据
                compare_period = format_period(mql.comparison.compare_period_start) if mql.comparison and mql.comparison.compare_period_start else "去年同期"
                if yoy_change:
                    change_desc = f"{yoy_change}%"
                else:
                    change_desc = ""
                answer = f"{metric_name}同比{'上升' if float(str(yoy_change).replace('%','')) > 0 else '下降' if yoy_change else '持平'}{change_desc}。{current_period}为 {int(current_val):,}，{compare_period}为 {int(yoy_val):,}。"
            elif is_mom and mom_val is not None and mom_val != 0:
                # 环比数据
                compare_period = format_period(mql.comparison.compare_period_start) if mql.comparison and mql.comparison.compare_period_start else "上期"
                if mom_change:
                    change_desc = f"{mom_change}%"
                else:
                    change_desc = ""
                answer = f"{metric_name}环比{'上升' if float(str(mom_change).replace('%','')) > 0 else '下降' if mom_change else '持平'}{change_desc}。{current_period}为 {int(current_val):,}，{compare_period}为 {int(mom_val):,}。"
            else:
                # 旧格式 fallback
                if trend == '增长':
                    trend_desc = "增长"
                    change_desc = f"{change_rate}%" if change_rate else ""
                elif trend == '下降':
                    trend_desc = "下降"
                    change_desc = f"{change_rate}%" if change_rate else ""
                else:
                    trend_desc = "持平"
                    change_desc = ""
                compare_period = "对比期"
                answer = f"{metric_name}{period_label}{trend_desc}{change_desc}。{current_period}为 {int(current_val):,}，{compare_period}为 {int(compare_val or 0):,}。"

            current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
            _, alt_label = self._get_alternative_dimensions(current_dim)

            # 获取多个替代维度
            dim_priority = ["FSITE", "GROUP_3", "GROUP_2", "GROUP_1"]
            label_map = self._get_dim_label_from_service()
            dim_type_to_col = {
                "站点": "FSITE", "FSITE": "FSITE",
                "三级品类": "GROUP_3", "GROUP_3": "GROUP_3",
                "二级品类": "GROUP_2", "GROUP_2": "GROUP_2",
                "一级品类": "GROUP_1", "GROUP_1": "GROUP_1",
            }
            current_col = dim_type_to_col.get(current_dim, current_dim.upper()) if current_dim else "FSITE"
            alt_dims = [d for d in dim_priority if d != current_col]

            # 用户问环比 → 推荐同比+异维度；用户问同比 → 推荐环比+异维度
            if is_mom:
                alt_type = "同比"
                same_type = "环比"
            else:
                alt_type = "环比"
                same_type = "同比"

            suggestions = [
                f"查看{time_context}各{alt_label}{metric_name}{alt_type}变化",
            ]
            for dim_col in alt_dims[:2]:
                dim_lbl = label_map.get(dim_col, dim_col)
                suggestions.append(f"查看{time_context}各{dim_lbl}{metric_name}{same_type}变化")

            return {
                "answer": answer,
                "suggestions": suggestions,
            }

        # 传统对比查询（两行数据）
        if len(data) < 2:
            return {
                "answer": "数据不足，无法进行对比",
                "suggestions": [],
            }

        # 多行对比数据（按维度分组的同比/环比）：生成有意义的回答
        col_map = self._build_col_map(mql)
        is_yoy = mql.has_yoy
        is_mom = mql.has_mom
        dim_type = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else "维度"

        # 尝试从数据中提取汇总信息
        metric_alias = metric_name
        raw_key = f"{metric_alias}_raw"
        yoy_val_key = f"{metric_alias}_yoy_val"
        mom_val_key = f"{metric_alias}_mom_val"
        yoy_change_key = f"{metric_alias}_yoy_change"
        mom_change_key = f"{metric_alias}_mom_change"

        total_current = 0
        total_compare = 0
        valid_count = 0
        for row in data:
            try:
                val = float(str(row.get(raw_key, 0)).replace(',', ''))
                total_current += val
                comp_key = yoy_val_key if is_yoy else mom_val_key
                comp_val = float(str(row.get(comp_key, 0)).replace(',', ''))
                total_compare += comp_val
                if comp_val > 0:
                    valid_count += 1
            except (ValueError, TypeError):
                pass

        change_label = "同比" if is_yoy else "环比"
        if total_current > 0 and valid_count > 0:
            total_change_pct = ((total_current - total_compare) / total_compare * 100) if total_compare != 0 else 0
            trend = "上升" if total_change_pct > 0 else "下降"
            answer = f"{metric_name}按{dim_type}{change_label}{trend}，整体{change_label}{abs(total_change_pct):.1f}%。共{len(data)}个{dim_type}，{valid_count}个有对比数据。"
        else:
            answer = f"{metric_name}按{dim_type}{change_label}对比已生成，详见数据。"

        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)
        return {
            "answer": answer,
            "suggestions": [
                f"查看{time_context}各{alt_label}{metric_name}详细数据",
                f"查看{time_context}各{alt_label}{metric_name}趋势变化",
            ],
        }

    async def _handle_ranking_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理排名查询"""
        data = sql_result.data
        time_context = self._get_time_context(mql)
        col_map = self._build_col_map(mql)

        metric_name = mql.metric.name if mql.metric else "指标值"
        time_context = self._get_time_context(mql)

        # 构建 LLM 摘要用的精简数据（中文列名 + 格式化数值）
        summary_rows = []
        for i, row in enumerate(data[:10], 1):
            parts = [f"{col_map.get(k, k)}: {self._format_value(v) if self._is_metric_column(k) else v}" for k, v in row.items()]
            summary_rows.append(f"{i}. " + " | ".join(parts))
        data_text = "\n".join(summary_rows)

        dim_label = ""
        if mql.dimensions:
            for d in mql.dimensions:
                if d.column:
                    dim_label = col_map.get(d.column, d.column)
                    break

        prompt = f"""用户问题：{question}
指标：{metric_name}
维度：{dim_label}
排名数据：
{data_text}

请用一句话总结排名数据的核心特征（如榜首是谁及数值、前几名差距、整体分布等），不要重复罗列数据。
例如："日本亚马逊以2.68万推广订单位居第一，前三名差距不大，前五站点贡献超70%。"
只输出总结，不要有其他内容。"""

        try:
            llm_summary = self._llm_engine.call(prompt, temperature=0.3, max_tokens=200)
            if llm_summary and len(llm_summary.strip()) > 10:
                logger.info(f"[ResultAnalyzer] LLM 排名总结: {llm_summary[:80]}")
                # 生成维度错开的建议
                current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
                _, alt_label = self._get_alternative_dimensions(current_dim)
                return {
                    "answer": llm_summary.strip(),
                    "suggestions": [
                        f"查看更多{time_context}各{alt_label}{metric_name}排名",
                        f"查看{time_context}各{alt_label}{metric_name}占比分布",
                    ],
                }
        except Exception as e:
            logger.warning(f"[ResultAnalyzer] LLM 排名总结失败，回退纯文本: {e}")

        # LLM 失败回退：简短摘要
        lines = ["排名结果："]
        for i, row in enumerate(data[:10], 1):
            parts = [f"{col_map.get(k, k)}: {self._format_value(v) if self._is_metric_column(k) else v}" for k, v in row.items()]
            lines.append(f"{i}. " + " | ".join(parts))

        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)

        return {
            "answer": "\n".join(lines),
            "suggestions": [
                f"查看更多{time_context}各{alt_label}{metric_name}排名",
                f"查看{time_context}各{alt_label}{metric_name}占比分布",
            ],
        }

    async def _handle_ratio_query(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理占比查询"""
        data = sql_result.data
        metric_name = mql.metric.name if mql.metric else "指标值"
        time_context = self._get_time_context(mql)

        # 计算总体的各部分占比
        if not data:
            return {
                "answer": "暂无数据",
                "suggestions": [],
            }

        lines = ["占比分布："]

        # 计算 total（安全转换数字）
        try:
            first_values = list(data[0].values())
            total = 0
            for v in first_values:
                try:
                    total += float(str(v).replace(",", ""))
                except (ValueError, TypeError):
                    continue
        except (ValueError, TypeError, IndexError):
            total = 0

        for row in data[:5]:
            for k, v in row.items():
                try:
                    val = float(str(v).replace(",", ""))
                    if total > 0:
                        ratio = val / total * 100
                        lines.append(f"{k}: {ratio:.1f}%")
                except (ValueError, TypeError):
                    continue

        # 生成维度错开的建议
        current_dim = mql.dimensions[0].type if mql.dimensions and mql.dimensions[0] else None
        _, alt_label = self._get_alternative_dimensions(current_dim)

        return {
            "answer": "\n".join(lines),
            "suggestions": [
                f"查看{time_context}各{alt_label}{metric_name}详细数据",
                f"查看{time_context}各{alt_label}{metric_name}趋势变化",
            ],
        }

    def _build_col_map(self, mql) -> Dict[str, str]:
        """构建列名映射（原始列名 → 中文展示名）"""
        col_map = dict(_DIM_COL_CHINESE)
        if mql and mql.metric:
            mname = getattr(mql.metric, 'name', '') or ''
            if mname:
                for suffix, label in _METRIC_SUFFIX_CHINESE.items():
                    col_map[f"{mname}{suffix}"] = f"{mname}{label}"
        return col_map

    async def _handle_default(
        self,
        mql: MQLSchema,
        sql_result: SQLResult,
        question: str,
    ) -> Dict[str, Any]:
        """处理默认查询"""
        data = sql_result.data
        col_map = self._build_col_map(mql)

        # 多行维度数据：用 LLM 生成一句话结论
        if len(data) > 1:
            metric_name = mql.metric.name if mql.metric else "指标值"
            dim_label = ""
            if mql.dimensions:
                for d in mql.dimensions:
                    if d.column:
                        dim_label = col_map.get(d.column, d.column)
                        break

            # 构建精简数据摘要供 LLM 分析（中文列名 + 格式化数值）
            summary_rows = []
            for row in data[:10]:
                parts = []
                for k, v in row.items():
                    display_k = col_map.get(k, k)
                    parts.append(f"{display_k}: {self._format_value(v)}")
                summary_rows.append(" | ".join(parts))
            data_text = "\n".join(summary_rows)

            prompt = f"""用户问题：{question}
指标：{metric_name}
维度：{dim_label}
数据：
{data_text}

请用一句话总结数据特征（如最大值、整体分布、显著差异等），不要重复罗列数据。
例如："美国亚马逊推广订单最高达669万，占总量近30%，前5站点贡献超80%。"
只输出总结，不要有其他内容。"""

            try:
                llm_summary = self._llm_engine.call(prompt, temperature=0.3, max_tokens=200)
                if llm_summary and len(llm_summary.strip()) > 10:
                    logger.info(f"[ResultAnalyzer] LLM 维度总结: {llm_summary[:80]}")
                    return {
                        "answer": llm_summary.strip(),
                        "suggestions": [],
                    }
            except Exception as e:
                logger.warning(f"[ResultAnalyzer] LLM 维度总结失败，回退表格: {e}")

        # 单行或 LLM 失败：回退表格
        lines = ["查询结果："]
        for row in data[:5]:
            parts = [f"{col_map.get(k, k)}: {self._format_value(v) if self._is_metric_column(k) else v}" for k, v in row.items()]
            lines.append(" | ".join(parts))

        return {
            "answer": "\n".join(lines),
            "suggestions": [],
        }

    def _all_values_empty(self, data: list) -> bool:
        """检测所有数值列是否全为 None/0/空字符串（维度列有值但指标值全空）"""
        if not data:
            return False

        found_nonzero = False
        for row in data:
            for v in row.values():
                if v is None:
                    continue
                try:
                    if float(str(v).replace(",", "")) != 0:
                        found_nonzero = True
                        break
                except (ValueError, TypeError):
                    continue
            if found_nonzero:
                break
        return not found_nonzero

    def _has_dimension_rows(self, data: list) -> bool:
        """检测数据中是否有维度列（字符串列有值但指标值全为空）"""
        if not data:
            return False
        dim_names = []
        for row in data[:20]:
            for k, v in row.items():
                if k in _DIM_COL_CHINESE or k.startswith("GROUP_"):
                    if v and isinstance(v, str):
                        dim_names.append(v)
                        break
        if not dim_names:
            return False
        # 只要有维度行就算有数据（即使指标值全 NULL）
        logger.info(f"[ResultAnalyzer] _has_dimension_rows: found {len(dim_names)} dimension values")
        return True

    def _build_dim_value_text(self, breakdown: list) -> str:
        """维度明细：只展示维度名+环比变化，不含归因影响"""
        lines = []
        for item in breakdown:
            dim = item.get("dimension", "")
            change = item.get("change", "")
            raw_value = item.get("raw_value", "")
            parts = [f"{dim}："]
            if raw_value is not None and raw_value != "":
                parts.append(f"{self._format_value(raw_value)}，")
            if change:
                parts.append(f"环比 {change}")
            lines.append("".join(parts))
        return "\n".join(lines)

    def _build_attribution_text(self, breakdown: list) -> str:
        """归因分析：展示影响程度+优先级"""
        lines = []
        for item in breakdown:
            dim = item.get("dimension", "")
            impact = item.get("impact", "")
            priority = item.get("priority", "")
            role = item.get("role", "")
            role_label = "拖累" if "drag" in role else ("贡献" if "boost" in role or "positive" in role else "")
            parts = [f"{dim}："]
            if impact:
                parts.append(f"{impact}")
            elif role_label:
                contribution = item.get("contribution_rate", "")
                if contribution:
                    parts.append(f"{role_label}整体 {contribution}")
            if priority:
                parts.append(f"（{priority}）")
            lines.append("".join(parts))
        return "\n".join(lines)

    def _build_dim_detail_text(self, mql: MQLSchema, data: list) -> str:
        """从 sql_result 提取维度明细文本"""
        col_map = self._build_col_map(mql)
        # 已知维度列（不做数值格式化）
        dim_keys = {'SKU', 'ASIN', 'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4',
                    'FSITE', 'FSITECODE', 'PLATFORM', 'BRAND', 'MONTHS', 'FDATE',
                    'FDATE_START', 'FDATE_END', 'FCOUNTRY', 'REGION', 'FCHANNEL',
                    '一级品类', '二级品类', '三级品类', '四级品类', '站点', '亚马逊站点',
                    '店铺', '平台', '品牌', '日期', '月份'}
        # 百分比类指标关键词
        pct_keywords = ["毛利率", "净利率", "转化率", "比率", "占比", "百分比"]

        lines = []
        for row in data[:10]:
            parts = []
            for k, v in row.items():
                display_k = col_map.get(k, k)
                # 清洗列名：去掉 _raw、当前值后缀
                display_k = re.sub(r'_raw$', '', display_k)
                display_k = display_k.replace("当前值", "")
                # 维度列直接显示原值
                if k in dim_keys:
                    parts.append(f"{display_k}：{v}")
                    continue
                # 数值列：格式化
                try:
                    num = float(str(v).replace(",", "")) if v is not None else None
                    if num is None:
                        parts.append(f"{display_k}：N/A")
                        continue
                    # 百分比指标：值 <= 1 时视为比率
                    is_pct = any(kw in display_k or kw in k for kw in pct_keywords)
                    if is_pct and abs(num) <= 1.0:
                        parts.append(f"{display_k}：{num * 100:.2f}%")
                    else:
                        parts.append(f"{display_k}：{self._format_value(num)}")
                except (ValueError, TypeError):
                    parts.append(f"{display_k}：{v}")
            lines.append("，".join(parts))
        if len(data) > 10:
            lines.append(f"... 还有 {len(data) - 10} 条")
        return "\n".join(lines)

    async def _query_prev_period_data(
        self,
        table_name: str,
        metric_field: str,
        dim_col: str,
        mom_start_str: str,
        mom_end_str: str,
    ) -> Dict[str, float]:
        """查询上期各维度的汇总值，返回 {维度值: 数值}"""
        sql = (
            f"SELECT {dim_col}, SUM({metric_field}) AS val "
            f"FROM {table_name} "
            f"WHERE FDATE >= '{mom_start_str}' AND FDATE <= '{mom_end_str}' "
            f"GROUP BY {dim_col}"
        )
        logger.info(f"[ResultAnalyzer] 查询上期数据: {sql}")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._go_api_base}/api/v1/query/execute",
                    json={"sql": sql, "timeout": 30},
                )
                data = resp.json()
                rows = None
                if data.get("code") == 0 and data.get("data"):
                    inner = data["data"]
                    rows = inner.get("data") if isinstance(inner, dict) else inner
                elif "columns" in data:
                    rows = data.get("data")
                if not rows or not isinstance(rows, list):
                    logger.warning(f"[ResultAnalyzer] 上期数据查询无结果: {sql[:80]}")
                    return {}
                result = {}
                for row in rows:
                    key = row.get(dim_col) or row.get(list(row.keys())[0]) if row else None
                    val = row.get("val") or row.get(list(row.keys())[1]) if row else None
                    if key is not None and val is not None:
                        result[str(key)] = float(val)
                return result
        except Exception as e:
            logger.warning(f"[ResultAnalyzer] 上期数据查询失败: {e}")
            return {}

    @staticmethod
    def _get_change_label(change_pct: float) -> str:
        """根据涨跌幅返回变化标签"""
        if change_pct >= 30:
            return "大幅增长"
        elif change_pct >= 5:
            return "小幅增长"
        elif change_pct >= -5:
            return "持平"
        elif change_pct >= -30:
            return "小幅下滑"
        else:
            return "大幅下滑"

    async def _build_dim_detail_text_async(self, mql: MQLSchema, data: list) -> tuple:
        """维度明细：涨跌幅表 + 贡献度 TOP3（需要查上期数据）

        Returns:
            (text, dim_mom_data) tuple:
                text: 贡献度TOP3文本
                dim_mom_data: {sku: {环比变化, 变化标签}} 供前端注入
        """
        import datetime
        from dateutil.relativedelta import relativedelta

        # 1. 识别维度列和指标列
        dim_keys = {'SKU', 'ASIN', 'GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4',
                    'FSITE', 'FSITECODE', 'PLATFORM', 'FBRANDS', 'FCOUNTRY',
                    'FREGION', 'FCHANNEL', 'FPRODUCTLINE', 'FADTYPE'}

        dim_col = None
        metric_col = None
        if not data:
            return "", {}
        first_row = data[0]
        for k in first_row.keys():
            upper_k = k.upper().rstrip("_RAW")
            if upper_k in dim_keys or k in dim_keys:
                dim_col = k
                break
        if not dim_col:
            return self._build_dim_detail_text(mql, data), {}

        # 找指标列（非维度列、非时间列、非 _change/_val 后缀的数值列）
        skip_suffixes = ("_MOM_VAL", "_YOY_VAL", "_MOM_CHANGE", "_YOY_CHANGE",
                         "MOM_VAL", "YOY_VAL", "MOM_CHANGE", "YOY_CHANGE")
        time_cols = {"FDATE", "MONTHS", "YEARS", "WEEKS", "QUARTERS", "DT", "DATE", "STAT_DATE"}
        for k, v in first_row.items():
            if k == dim_col:
                continue
            upper_k = k.upper()
            if upper_k in time_cols or k in time_cols:
                continue
            if any(upper_k.endswith(s) for s in skip_suffixes):
                continue
            # StarRocks 返回的数值可能是字符串，尝试转换
            try:
                float(str(v).replace(",", ""))
                metric_col = k
                break
            except (ValueError, TypeError):
                continue

        if not metric_col:
            return self._build_dim_detail_text(mql, data), {}

        # 2. 从 MQL 提取时间范围
        if not mql.time or not mql.time.start or not mql.time.end:
            return self._build_dim_detail_text(mql, data), {}

        try:
            start_dt = datetime.datetime.strptime(mql.time.start[:10], "%Y-%m-%d")
            end_dt = datetime.datetime.strptime(mql.time.end[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return self._build_dim_detail_text(mql, data), {}

        # 3. 计算环比期间
        try:
            from .sql_generator import SQLGeneratorNode
            mom_start, mom_end = SQLGeneratorNode.compute_mom_period(start_dt, end_dt)
        except Exception as e:
            logger.warning(f"[ResultAnalyzer] compute_mom_period 失败: {e}")
            return self._build_dim_detail_text(mql, data), {}

        mom_start_str = mom_start.strftime("%Y-%m-%d")
        mom_end_str = mom_end.strftime("%Y-%m-%d")

        # 4. 获取表名和指标字段
        table_name = ""
        metric_field = ""
        if mql.metric:
            table_name = mql.metric.table or ""
            metric_field = mql.metric.field or ""
            # 从 starrocks_sql 解析
            if not table_name or not metric_field:
                import re
                sql_str = mql.metric.starrocks_sql or ""
                if not table_name:
                    m = re.search(r"FROM\s+([a-zA-Z0-9_\.]+)", sql_str, re.IGNORECASE)
                    table_name = m.group(1) if m else ""
                if not metric_field:
                    m = re.search(r"SUM\s*\(\s*([A-Z_]+)\s*\)", sql_str, re.IGNORECASE)
                    metric_field = m.group(1) if m else ""

        if not table_name or not metric_field:
            logger.warning(f"[ResultAnalyzer] 无法获取表名/字段: table={table_name}, field={metric_field}")
            return self._build_dim_detail_text(mql, data), {}

        # 5. 查上期数据
        prev_data = await self._query_prev_period_data(
            table_name, metric_field, dim_col, mom_start_str, mom_end_str
        )

        if not prev_data:
            logger.info("[ResultAnalyzer] 上期数据为空，回退简单文本")
            return self._build_dim_detail_text(mql, data), {}

        # 6. 计算涨跌幅 + 贡献度
        results = []
        total_current = 0.0
        total_prev = 0.0
        for row in data:
            dim_val = str(row.get(dim_col, ""))
            try:
                current_val = float(str(row.get(metric_col, 0)).replace(",", ""))
            except (ValueError, TypeError):
                continue
            prev_val = prev_data.get(dim_val, 0)
            total_current += current_val
            total_prev += prev_val
            results.append({
                "dim": dim_val,
                "current": current_val,
                "prev": prev_val,
            })

        total_change = total_current - total_prev

        # 为每行计算变化率和贡献度
        for r in results:
            prev_v = r["prev"]
            curr_v = r["current"]
            r["change"] = curr_v - prev_v
            r["change_pct"] = ((curr_v - prev_v) / prev_v * 100) if prev_v != 0 else None
            r["contribution"] = (r["change"] / total_change * 100) if total_change != 0 else 0

        # 隐藏规则：所有变化率在 ±5% 以内
        significant_changes = [r for r in results if r["change_pct"] is not None and abs(r["change_pct"]) > 5]
        if not significant_changes:
            logger.info("[ResultAnalyzer] 所有变化率在±5%以内，维度明细隐藏")
            return "", {}

        # 7. 构建环比注入数据（由前端 ChartCard 合并到表格）
        dim_mom_data = {}
        for r in results:
            pct = r["change_pct"]
            if pct is not None:
                sign = "+" if pct >= 0 else ""
                contrib = r["contribution"]
                contrib_str = f"+{contrib:.1f}%" if contrib >= 0 else f"{contrib:.1f}%"
                dim_mom_data[r["dim"]] = {
                    "环比变化": f"{sign}{pct:.1f}%",
                    "变化标签": self._get_change_label(pct),
                    "贡献度": contrib_str,
                }
            else:
                dim_mom_data[r["dim"]] = {
                    "环比变化": "N/A",
                    "变化标签": "新增",
                    "贡献度": "N/A",
                }

        # 8. 第四段不输出文本，所有数据已注入表格
        return "", dim_mom_data

    def _build_action_text(self, action_items: list) -> str:
        """格式化运营建议为纯文本"""
        lines = []
        for item in action_items:
            text = item.get("text", "")
            item_type = item.get("type", "normal")
            if item_type == "urgent":
                priority = "P0"
            elif item_type == "warning":
                priority = "P1"
            else:
                priority = "P2"
            lines.append(f"{priority} {text}")
        return "\n".join(lines)

    @staticmethod
    def _clean_raw_names(text: str) -> str:
        """清洗回答文本中的 _raw、当前值等 SQL 列名残留"""
        if not text:
            return text
        # 去掉 _raw 后缀（带前面可能的中文字符）
        text = re.sub(r'(\S+)_raw', r'\1', text)
        # 去掉 "当前值" 后缀
        text = text.replace("当前值", "")
        # 去掉 _mom_val / _yoy_val / _mom_change / _yoy_change
        text = re.sub(r'_(?:mom|yoy)_(?:val|change)', '', text)
        return text

    def _build_kpi_tooltip(self, mql: MQLSchema, analysis: Dict = None, sql_result=None) -> Dict[str, str]:
        """构建核心指标 tooltip 信息：业务定义 + 对比期间"""
        tooltip = {}
        # 业务定义（收集指标定义，自动查缺失的定义）
        definitions = []
        seen_names = set()
        # 收集所有需要展示的指标名（主指标 + mql.metrics 中的非子串指标）
        metric_names_to_show = []
        if mql.metric:
            metric_names_to_show.append(mql.metric)
        if mql.metrics:
            for m in mql.metrics:
                if not m or m.name in seen_names:
                    continue
                # 跳过是其他更长相标名子串的拆分产物
                skip = False
                for other in mql.metrics:
                    if other and other != m and other.name != m.name and m.name in other.name and len(m.name) < len(other.name):
                        skip = True
                        break
                if not skip and mql.metric and m.name in mql.metric.name and len(m.name) < len(mql.metric.name):
                    skip = True
                if skip:
                    continue
                metric_names_to_show.append(m)
                seen_names.add(m.name)
        # 查找每个指标的定义（优先用 MQLMetric 自带的，缺失则查 metric client）
        for m in metric_names_to_show:
            meaning = m.business_meaning or m.business_summary or ""
            if not meaning and m.name:
                try:
                    from ai.client.metric_client import MetricClient
                    client = MetricClient()
                    info = client.get_metric_by_name(m.name)
                    if info:
                        meaning = info.get("business_definition", "")
                except Exception:
                    pass
            if meaning:
                definitions.append(f"{m.name}：{meaning}")
        if definitions:
            tooltip["metric_definition"] = "\n".join(definitions)
        # 当前查询期间
        if mql.time and mql.time.start:
            tooltip["current_period"] = f"{mql.time.start} ~ {mql.time.end}"
        # 对比期间（环比/同比）
        if mql.comparison and mql.comparison.compare_period_start:
            tooltip["compare_period"] = f"{mql.comparison.compare_period_start} ~ {mql.comparison.compare_period_end}"

        # 检测指标是否支持环比/同比（用语义层能力，不依赖当前查询是否有对比列）
        has_mom = False
        has_yoy = False
        metric_code = mql.metric.code if mql.metric else ""
        logger.info(f"[_build_kpi_tooltip] metric_code={metric_code}")
        if metric_code:
            try:
                from ai.services.semantic_layer import get_semantic_layer_service, EnrichStage
                from ai.services.semantic_layer.api import ParseResult
                semantic_layer = get_semantic_layer_service()
                parse_result = ParseResult(intent="", confidence=0.0, metric_code=metric_code)
                enrich_result = semantic_layer.enrich(parse_result, stage=EnrichStage.RESULT_ANALYSIS)
                logger.info(f"[_build_kpi_tooltip] semantic_layer enrich cap={enrich_result.metric_capability}")
                if enrich_result.metric_capability:
                    has_mom = bool(enrich_result.metric_capability.get("supports_mom"))
                    has_yoy = bool(enrich_result.metric_capability.get("supports_yoy"))
            except Exception as e:
                logger.warning(f"[_build_kpi_tooltip] semantic_layer failed: {e}")
        if not has_mom or not has_yoy:
            semantic_svc = self._get_semantic_service()
            snapshot = semantic_svc.get_active_snapshot() if semantic_svc else None
            if snapshot:
                capabilities = snapshot.get("capabilities", {}) or {}
                metric_cap = capabilities.get(f"metric:{metric_code}", {}) or {}
                logger.info(f"[_build_kpi_tooltip] snapshot cap for metric:{metric_code} = {metric_cap}")
                if not has_mom:
                    has_mom = bool(metric_cap.get("supports_mom"))
                if not has_yoy:
                    has_yoy = bool(metric_cap.get("supports_yoy"))
        logger.info(f"[_build_kpi_tooltip] final has_mom={has_mom}, has_yoy={has_yoy}")

        # 计算环比/同比期间
        if has_mom or has_yoy:
            try:
                import datetime
                from dateutil.relativedelta import relativedelta
                start = mql.time.start if mql.time else ""
                end = mql.time.end if mql.time else ""
                logger.info(f"[_build_kpi_tooltip] mql.time: start={start}, end={end}")
                if start:
                    dt = datetime.datetime.strptime(start[:10], "%Y-%m-%d")
                    end_dt = datetime.datetime.strptime((end or start)[:10], "%Y-%m-%d")
                    if has_mom:
                        from .sql_generator import SQLGeneratorNode
                        mom_start, mom_end = SQLGeneratorNode.compute_mom_period(dt, end_dt)
                        tooltip["mom_period"] = f"{mom_start.strftime('%Y-%m-%d')} ~ {mom_end.strftime('%Y-%m-%d')}"
                    if has_yoy:
                        period_days = (end_dt - dt).days + 1
                        yoy_start = dt - relativedelta(years=1)
                        yoy_end = yoy_start + datetime.timedelta(days=period_days - 1)
                        tooltip["yoy_period"] = f"{yoy_start.strftime('%Y-%m-%d')} ~ {yoy_end.strftime('%Y-%m-%d')}"
            except Exception as e:
                logger.warning(f"[_build_kpi_tooltip] period calc failed: {e}")

        logger.info(f"[_build_kpi_tooltip] final tooltip={tooltip}")
        return tooltip if len(tooltip) > 1 else {}

    def _format_value(self, value: Any) -> str:
        """格式化数值"""
        if value is None:
            return "N/A"

        try:
            num = float(str(value).replace(",", ""))
            if abs(num) >= 10000:
                return f"{num/10000:.2f}万"
            elif abs(num) >= 1000:
                return f"{num/1000:.2f}千"
            else:
                return f"{num:.2f}"
        except (ValueError, TypeError):
            return str(value)

    def _is_metric_column(self, column_name: str) -> bool:
        """判断是否为指标列（需要格式化的数值列）"""
        # 常见的指标列名后缀/模式
        metric_patterns = [
            "SALES", "AMOUNT", "COUNT", "NUM", "QTY", "ORDER",
            "REVENUE", "PROFIT", "GMV", "UV", "PV", "CLICK",
            "RATE", "RATIO", "PERCENT", "PCT",
        ]
        # 常见维度列名前缀（不应该格式化的）
        dimension_prefixes = [
            "SKU", "DATE", "TIME", "DT", "FSITE", "CHANNEL",
            "STORE", "SHOP", "CITY", "REGION", "COUNTRY",
            "PRODUCT", "CATEGORY", "BRAND", "CAMPAIGN",
        ]

        upper_name = column_name.upper()

        # 维度列不格式化
        for prefix in dimension_prefixes:
            if upper_name.startswith(prefix):
                return False

        # 指标列模式匹配
        for pattern in metric_patterns:
            if pattern in upper_name:
                return True

        # 默认：如果列名全是大写且像代码，不格式化
        if column_name.isdigit() or (len(column_name) <= 10 and not any(c.isalpha() for c in column_name)):
            return False

        return False

    def _build_explanation(self, mql: MQLSchema) -> Dict[str, Any]:
        """构建解释信息：指标含义 + 维度说明 + 数据来源"""
        parts = {}

        # 指标含义
        if mql.metric:
            meaning = mql.metric.business_meaning or mql.metric.business_summary
            if meaning:
                parts["metric_meaning"] = f"{mql.metric.name}：{meaning}"

        # 数据来源
        if mql.metric and mql.metric.table:
            parts["data_source"] = f"数据来源：{mql.metric.table}"

        # 时间范围
        if mql.time and mql.time.original:
            parts["time_range"] = f"查询时间：{mql.time.original}"

        # 维度说明
        if mql.dimensions:
            dim_labels = []
            for d in mql.dimensions:
                label = _DIM_COL_CHINESE.get(d.column, d.type) if d.column else d.type
                dim_labels.append(label)
            parts["dimensions"] = f"按 {'、'.join(dim_labels)} 维度查看"

        return parts

    def detect_anomalies(
        self,
        data: List[Dict[str, Any]],
        metric_name: str,
        dimensions: List[str] = None,
    ) -> List[AnomalyAnnotation]:
        """检测数据异常

        Args:
            data: 查询结果数据
            metric_name: 指标名称
            dimensions: 维度列表（用于定位异常来源）

        Returns:
            异常标注列表
        """
        anomalies = []
        dimensions = dimensions or []

        # 从 VolatilityTrigger.DEFAULT_RULES 获取动态阈值
        try:
            from .trigger_analyzer import VolatilityTrigger
            rules = VolatilityTrigger.DEFAULT_RULES.get(metric_name, {})
            mom_threshold = rules.get("mom", -15)  # 默认 -15%
            yoy_threshold = rules.get("yoy", -20)  # 默认 -20%
        except Exception:
            mom_threshold = -15
            yoy_threshold = -20

        for row in data:
            # 1. 环比异常检测
            mom_change = row.get("mom_change") or row.get("环比变化") or row.get("环比")
            if mom_change is not None:
                try:
                    mom_val = float(str(mom_change).replace("%", "").replace(",", ""))
                    # 阈值为百分比形式，mom_val 需要转换为百分比
                    mom_pct = mom_val * 100 if mom_val < 1 else mom_val
                    if mom_threshold < 0 and mom_pct < mom_threshold:  # 下降超过阈值
                        dim_value = ""
                        for dim in dimensions:
                            if dim in row:
                                dim_value = row[dim]
                                break
                        anomalies.append(AnomalyAnnotation(
                            type="significant_mom_drop",
                            metric=metric_name,
                            value=mom_val,
                            threshold=mom_threshold / 100,  # 转换为小数形式
                            message=f"{metric_name}环比下降{abs(mom_pct):.1f}%",
                            dimension=dimensions[0] if dimensions else "",
                            dimension_value=dim_value,
                            suggestion=f"关注{(dim_value + '的' if dim_value else '')}{metric_name}变化",
                        ))
                except (ValueError, TypeError):
                    pass

            # 2. 同比异常检测
            yoy_change = row.get("yoy_change") or row.get("同比变化") or row.get("同比")
            if yoy_change is not None and yoy_threshold is not None:
                try:
                    yoy_val = float(str(yoy_change).replace("%", "").replace(",", ""))
                    yoy_pct = yoy_val * 100 if yoy_val < 1 else yoy_val
                    if yoy_threshold < 0 and yoy_pct < yoy_threshold:
                        dim_value = ""
                        for dim in dimensions:
                            if dim in row:
                                dim_value = row[dim]
                                break
                        anomalies.append(AnomalyAnnotation(
                            type="significant_yoy_drop",
                            metric=metric_name,
                            value=yoy_val,
                            threshold=yoy_threshold / 100,
                            message=f"{metric_name}同比下降{abs(yoy_pct):.1f}%",
                            dimension=dimensions[0] if dimensions else "",
                            dimension_value=dim_value,
                            suggestion=f"关注{(dim_value + '的' if dim_value else '')}{metric_name}同比变化",
                        ))
                except (ValueError, TypeError):
                    pass

            # 3. 零值/空值检测
            value = row.get("value") or row.get("数值") or row.get("销售额") or row.get("订单量")
            if value is not None:
                try:
                    val = float(str(value).replace(",", ""))
                    if val == 0:
                        anomalies.append(AnomalyAnnotation(
                            type="zero_value",
                            metric=metric_name,
                            value=0,
                            threshold=0,
                            message=f"{metric_name}数据为零",
                            dimension=dimensions[0] if dimensions else "",
                            suggestion="检查数据是否正常或时间范围是否正确",
                        ))
                except (ValueError, TypeError):
                    pass

            # 4. 异常高值检测（增长 > 50%，可能是异常）
            if mom_change is not None:
                try:
                    mom_val = float(str(mom_change).replace("%", "").replace(",", ""))
                    if mom_val > 0.5:  # 增长超过50%
                        anomalies.append(AnomalyAnnotation(
                            type="significant_spike",
                            metric=metric_name,
                            value=mom_val,
                            threshold=0.5,
                            message=f"{metric_name}环比增长{abs(mom_val):.1f}%，注意确认异常原因",
                            dimension=dimensions[0] if dimensions else "",
                            suggestion="确认是否活动促销或数据口径变化",
                        ))
                except (ValueError, TypeError):
                    pass

        return anomalies
