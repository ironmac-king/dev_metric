"""
多轮追问 E2E 基准测试 — 30 个追问场景

验证追问流程：第一轮查 SQL → 第二轮追问 → 验证 MQL 合并结果

用法:
    python -m pytest tests/benchmark/test_multi_turn.py -v -s
    python tests/benchmark/test_multi_turn.py
"""
import asyncio
import json
import os
import sys
import time
import pytest
from typing import Dict, Any, List, Optional

CASES_DIR = os.path.join(os.path.dirname(__file__), "cases")


def load_multi_turn_cases() -> List[Dict[str, Any]]:
    filepath = os.path.join(CASES_DIR, "multi_turn_followup.json")
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _to_str(val) -> str:
    """Safely convert to string for case-insensitive comparison"""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if hasattr(val, "value"):
        return val.value
    return str(val)


def _list_contains_any(lst, candidates) -> bool:
    """Check if list contains any of the candidates (case-insensitive)"""
    lst_upper = [_to_str(x).upper() for x in (lst or [])]
    for c in candidates:
        if _to_str(c).upper() in lst_upper:
            return True
    return False


def _list_not_contains_any(lst, candidates) -> bool:
    """Check if list does NOT contain any of the candidates"""
    return not _list_contains_any(lst, candidates)


def evaluate_followup_mql(mql, expected: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate followup MQL against expected results"""
    results = {"pass": True, "checks": {}}
    mql_dict = mql.to_dict() if hasattr(mql, "to_dict") else {}
    mql_str = json.dumps(mql_dict, ensure_ascii=False).upper()

    # metric_name_in — 主指标名应该在列表中
    if "metric_name_in" in expected:
        metric_name = _to_str(getattr(mql, "metric", None) and mql.metric.name).upper()
        found = any(c.upper() in metric_name for c in expected["metric_name_in"])
        if not found:
            # 也检查 SQL 中是否包含
            found = any(c.upper() in mql_str for c in expected["metric_name_in"])
        results["checks"]["metric_name_in"] = found
        if not found:
            results["pass"] = False

    # metric_name_not_in — 主指标名不应在列表中
    if "metric_name_not_in" in expected:
        metric_name = _to_str(getattr(mql, "metric", None) and mql.metric.name).upper()
        found = any(c.upper() in metric_name for c in expected["metric_name_not_in"])
        results["checks"]["metric_name_not_in"] = not found
        if found:
            results["pass"] = False

    # dimensions_in — 维度应包含指定值（检查 type 和 column）
    if "dimensions_in" in expected:
        dims = []
        for d in (mql.dimensions or []):
            dims.append(_to_str(d.type).upper())
            if hasattr(d, "column") and d.column:
                dims.append(_to_str(d.column).upper())
        found = any(c.upper() in dims for c in expected["dimensions_in"])
        results["checks"]["dimensions_in"] = found
        if not found:
            results["pass"] = False

    # intent
    if "intent" in expected:
        intent_val = _to_str(getattr(mql, "intent", ""))
        ok = expected["intent"].upper() in intent_val.upper()
        results["checks"]["intent"] = ok
        if not ok:
            results["pass"] = False

    # comparison_types_in
    if "comparison_types_in" in expected:
        comp = getattr(mql, "comparison", None)
        types = [_to_str(t).upper() for t in (comp.types or [])] if comp else []
        found = any(c.upper() in types for c in expected["comparison_types_in"])
        results["checks"]["comparison_types_in"] = found
        if not found:
            results["pass"] = False

    # needs_clarification
    if "needs_clarification" in expected:
        # This is checked at the state level, not MQL level
        # Will be handled in run_single_case
        pass

    # metrics_count_gte — 多指标数量
    if "metrics_count_gte" in expected:
        count = len(mql.metrics or [])
        ok = count >= expected["metrics_count_gte"]
        results["checks"]["metrics_count_gte"] = ok
        if not ok:
            results["pass"] = False

    # time_original — 精确匹配时间表达式
    if "time_original" in expected:
        time_obj = getattr(mql, "time", None)
        actual = _to_str(getattr(time_obj, "original", ""))
        ok = expected["time_original"] == actual
        results["checks"]["time_original"] = ok
        if not ok:
            results["pass"] = False

    # time_original_in — 时间表达式包含在列表中
    if "time_original_in" in expected:
        time_obj = getattr(mql, "time", None)
        actual = _to_str(getattr(time_obj, "original", ""))
        found = any(c in actual for c in expected["time_original_in"])
        results["checks"]["time_original_in"] = found
        if not found:
            results["pass"] = False

    return results


async def run_multi_turn_case(graph, case: Dict[str, Any]) -> Dict[str, Any]:
    """跑一个多轮追问场景：第一轮 → 获取 MQL → 第二轮追问 → 验证"""
    from ai.engine.llm_v2.schema import V2State

    case_id = case["id"]
    first_turn = case["first_turn"]
    followup = case["followup"]
    expected = case["expected_followup"]
    category = case.get("category", "")

    # === 第一轮：执行查询，获取 MQL ===
    start = time.time()
    try:
        state1 = V2State(question=first_turn, session_id=f"mt_{case_id}_t1")
        final_state1 = await graph.ainvoke(state1)

        # 第一轮必须成功（产生 SQL 或追问）
        mql1 = final_state1.mql
        if not mql1:
            elapsed = time.time() - start
            return {
                "id": case_id, "category": category, "pass": False,
                "type": "first_turn_no_mql", "elapsed": round(elapsed, 2),
                "error": f"第一轮无 MQL: {first_turn}",
            }

        # 构造第二轮的 inherited_mql
        from ai.engine.llm_v2.session_store import V2SessionStore, get_session_store
        session_store = get_session_store()
        session_store.set_state(final_state1)

    except Exception as e:
        elapsed = time.time() - start
        return {
            "id": case_id, "category": category, "pass": False,
            "type": "first_turn_error", "elapsed": round(elapsed, 2),
            "error": str(e)[:300],
        }

    # === 第二轮：追问 ===
    try:
        # 直接构造 state2，手动传入 inherited_mql（绕过 router.py 的 session 恢复）
        state2 = V2State(question=followup, session_id=f"mt_{case_id}_t2")
        state2.inherited_mql = mql1
        final_state2 = await graph.ainvoke(state2)

        elapsed = time.time() - start

        # 检查是否需要追问
        if expected.get("needs_clarification"):
            ok = bool(final_state2.needs_clarification)
            return {
                "id": case_id, "category": category, "pass": ok,
                "type": "clarification", "elapsed": round(elapsed, 2),
                "checks": {"needs_clarification": ok},
                "message": final_state2.clarification_message or "",
            }

        # 如果追问触发了追问但预期不需要
        if final_state2.needs_clarification and not expected.get("needs_clarification"):
            return {
                "id": case_id, "category": category, "pass": False,
                "type": "unexpected_clarification", "elapsed": round(elapsed, 2),
                "checks": {"unexpected_clarification": False},
                "message": final_state2.clarification_message or "",
            }

        # 验证 MQL
        mql2 = final_state2.mql
        if not mql2:
            return {
                "id": case_id, "category": category, "pass": False,
                "type": "no_mql", "elapsed": round(elapsed, 2),
                "error": "追问后无 MQL",
            }

        eval_result = evaluate_followup_mql(mql2, expected)
        return {
            "id": case_id, "category": category, "pass": eval_result["pass"],
            "type": "followup_mql", "elapsed": round(elapsed, 2),
            "checks": eval_result["checks"],
            "metric": _to_str(mql2.metric.name if mql2.metric else None),
            "dims": [_to_str(d.type) for d in (mql2.dimensions or [])],
        }

    except Exception as e:
        elapsed = time.time() - start
        return {
            "id": case_id, "category": category, "pass": False,
            "type": "followup_error", "elapsed": round(elapsed, 2),
            "error": str(e)[:300],
        }


def print_report(results: List[Dict[str, Any]]):
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    accuracy = passed / total * 100 if total > 0 else 0

    category_stats = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1
        if r["pass"]:
            category_stats[cat]["passed"] += 1

    print(f"\n{'='*70}")
    print(f" Multi-Turn Followup Benchmark Report")
    print(f"{'='*70}")
    print(f" Total: {total}  |  Passed: {passed}  |  Failed: {total - passed}  |  Accuracy: {accuracy:.1f}%")
    print(f"{'='*70}")

    print(f"\n {'Category':<30} {'Pass/Total':>12} {'Rate':>8}")
    print(f" {'-'*30} {'-'*12} {'-'*8}")
    for cat, stats in sorted(category_stats.items()):
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f" {cat:<30} {stats['passed']:>3}/{stats['total']:<3} {rate:>7.0f}%")

    print(f"\n{'='*70}")
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        elapsed = f"{r.get('elapsed', 0):.1f}s"
        extra = ""
        if r.get("metric"):
            extra += f" metric={r['metric']}"
        if r.get("dims"):
            extra += f" dims={r['dims']}"
        if not r["pass"]:
            if r.get("error"):
                extra += f" ERROR: {r['error']}"
            elif r.get("message"):
                extra += f" MSG: {r['message']}"
            elif r.get("checks"):
                failed = [f"{k}" for k, v in r["checks"].items() if not v]
                if failed:
                    extra += f" FAIL: {', '.join(failed)}"

        print(f"  [{status}] {r['id']}: {elapsed}{extra}")

    print(f"\n{'='*70}")
    print(f" Summary: {passed}/{total} = {accuracy:.1f}%")
    print(f"{'='*70}\n")

    return accuracy


@pytest.fixture
def graph():
    from ai.engine.llm_v2.graph import get_v2_graph
    return get_v2_graph()


@pytest.fixture
def multi_turn_cases():
    return load_multi_turn_cases()


class TestMultiTurn:
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.environ.get("SKIP_LLM_TESTS") == "1",
        reason="Set SKIP_LLM_TESTS=0 to run"
    )
    async def test_all_multi_turn_cases(self, graph, multi_turn_cases):
        if not multi_turn_cases:
            pytest.skip("No multi-turn test cases loaded")

        results = []
        for case in multi_turn_cases:
            result = await run_multi_turn_case(graph, case)
            results.append(result)
            status = "PASS" if result["pass"] else "FAIL"
            print(f"  [{status}] {result['id']}: ({result.get('elapsed', 0):.1f}s)")

        accuracy = print_report(results)
        assert accuracy >= 70, f"Multi-turn accuracy {accuracy:.1f}% below 70%"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Turn Followup Benchmark")
    parser.add_argument("--ids", type=str, default="", help="Comma-separated case IDs (e.g. A1,A6,H1)")
    parser.add_argument("--category", type=str, default="", help="Filter by category")
    args = parser.parse_args()

    cases = load_multi_turn_cases()

    if args.ids:
        target_ids = set(args.ids.split(","))
        cases = [c for c in cases if c["id"] in target_ids]
    if args.category:
        cases = [c for c in cases if c.get("category", "") == args.category]

    if not cases:
        print("No matching cases found")
        sys.exit(1)

    print(f"Running {len(cases)} multi-turn cases...")

    from ai.engine.llm_v2.graph import get_v2_graph
    graph = get_v2_graph()

    async def _run_all():
        return [await run_multi_turn_case(graph, c) for c in cases]

    results = asyncio.run(_run_all())
    accuracy = print_report(results)

    if accuracy >= 90:
        print("EXCELLENT: >= 90%")
    elif accuracy >= 75:
        print("GOOD: >= 75%")
    else:
        print(f"NEEDS IMPROVEMENT: {accuracy:.1f}%")
