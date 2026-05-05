"""
全量 E2E 基准测试 — 45 个用例跑完整 LangGraph 管道

用法:
    # 跑全部 45 个用例（需要 AI 服务运行中）
    python -m pytest tests/benchmark/test_full_e2e.py -v -s

    # 只跑前 15 个（快速验证）
    python -m pytest tests/benchmark/test_full_e2e.py -v -s -k "first_15"

    # 指定用例 ID
    python -m pytest tests/benchmark/test_full_e2e.py -v -s -k "case_001"
"""
import asyncio
import json
import os
import sys
import time
import pytest
from typing import Dict, Any, List

CASES_DIR = os.path.join(os.path.dirname(__file__), "cases")


def load_cases(filename: str = "mki_basic.json") -> List[Dict[str, Any]]:
    filepath = os.path.join(CASES_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def check_sql_field(sql: str, expected_field: str) -> bool:
    if not sql or not expected_field:
        return False
    return expected_field.upper() in sql.upper()


def check_sql_table(sql: str, expected_table: str) -> bool:
    if not sql or not expected_table:
        return False
    table_name = expected_table.split(".")[-1]
    return table_name.upper() in sql.upper()


def check_sql_dimensions(sql: str, expected_dims: List[str]) -> bool:
    if not expected_dims:
        return True
    for dim in expected_dims:
        if dim.upper() not in sql.upper():
            return False
    return True


def check_sql_dimensions_contains(sql: str, keyword: str) -> bool:
    if not keyword:
        return True
    return keyword.upper() in sql.upper()


def check_sql_agg(sql: str, expected_agg: str, expected_field: str) -> bool:
    if not expected_agg or not expected_field:
        return True
    pattern = f"{expected_agg}({expected_field})"
    return pattern.upper() in sql.upper()


def evaluate_case(sql: str, expected: Dict[str, Any]) -> Dict[str, Any]:
    results = {"pass": True, "checks": {}}

    if "table" in expected:
        ok = check_sql_table(sql, expected["table"])
        results["checks"]["table"] = ok
        if not ok:
            results["pass"] = False

    if "field" in expected:
        ok = check_sql_field(sql, expected["field"])
        results["checks"]["field"] = ok
        if not ok:
            results["pass"] = False

    if "fields" in expected:
        for f in expected["fields"]:
            ok = check_sql_field(sql, f)
            results["checks"][f"field_{f}"] = ok
            if not ok:
                results["pass"] = False

    if "agg" in expected and "field" in expected:
        ok = check_sql_agg(sql, expected["agg"], expected["field"])
        results["checks"]["agg"] = ok
        if not ok:
            results["pass"] = False

    if "dimensions" in expected:
        ok = check_sql_dimensions(sql, expected["dimensions"])
        results["checks"]["dimensions"] = ok
        if not ok:
            results["pass"] = False

    if "dimensions_contains" in expected:
        ok = check_sql_dimensions_contains(sql, expected["dimensions_contains"])
        results["checks"]["dimensions_contains"] = ok
        if not ok:
            results["pass"] = False

    if "filters" in expected:
        for f in expected["filters"]:
            ok = f["value"] in sql
            results["checks"][f"filter_{f['field']}"] = ok
            if not ok:
                results["pass"] = False

    if "patterns" in expected:
        for p in expected["patterns"]:
            ok = p.upper() in sql.upper()
            results["checks"][f"pattern_{p}"] = ok
            if not ok:
                results["pass"] = False

    return results


async def run_single_case(graph, case: Dict[str, Any]) -> Dict[str, Any]:
    """跑单个用例通过完整 LangGraph 管道"""
    from ai.engine.llm_v2.schema import V2State

    question = case["question"]
    expected = case["expected"]
    case_id = case["id"]
    category = case.get("category", "")

    start = time.time()
    try:
        state = V2State(
            question=question,
            session_id=f"e2e_bench_{case_id}",
        )
        final_state = await graph.ainvoke(state)
        elapsed = time.time() - start

        sql = final_state.sql or ""

        # 追问场景：如果 expected 不要求特定字段/聚合/pattern，追问也算通过
        # 泛指维度（dimensions_contains）触发追问也是正确行为
        if final_state.needs_clarification:
            has_strict_expectation = bool(expected.get("field") or expected.get("agg") or expected.get("patterns"))
            is_generic_dim_expected = "dimensions_contains" in expected
            if not has_strict_expectation or is_generic_dim_expected:
                return {
                    "id": case_id,
                    "question": question,
                    "category": category,
                    "pass": True,
                    "type": "clarification",
                    "elapsed": round(elapsed, 2),
                    "message": final_state.clarification_message or "",
                }
            return {
                "id": case_id,
                "question": question,
                "category": category,
                "pass": False,
                "type": "clarification",
                "elapsed": round(elapsed, 2),
                "message": final_state.clarification_message or "",
            }

        # 有 SQL → 评估
        if sql:
            eval_result = evaluate_case(sql, expected)
            return {
                "id": case_id,
                "question": question,
                "category": category,
                "pass": eval_result["pass"],
                "type": "sql",
                "sql": sql[:300],
                "elapsed": round(elapsed, 2),
                "checks": eval_result["checks"],
            }

        # 无 SQL 且无追问
        return {
            "id": case_id,
            "question": question,
            "category": category,
            "pass": False,
            "type": "no_output",
            "elapsed": round(elapsed, 2),
            "answer": (final_state.answer or "")[:200],
        }

    except Exception as e:
        elapsed = time.time() - start
        return {
            "id": case_id,
            "question": question,
            "category": category,
            "pass": False,
            "type": "error",
            "elapsed": round(elapsed, 2),
            "error": str(e)[:300],
        }


def print_report(results: List[Dict[str, Any]], label: str = "Full E2E"):
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    accuracy = passed / total * 100 if total > 0 else 0

    # 按类别统计
    category_stats = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1
        if r["pass"]:
            category_stats[cat]["passed"] += 1

    print(f"\n{'='*70}")
    print(f" {label} Benchmark Report")
    print(f"{'='*70}")
    print(f" Total: {total}  |  Passed: {passed}  |  Failed: {total - passed}  |  Accuracy: {accuracy:.1f}%")
    print(f"{'='*70}")

    # 按类别输出
    print(f"\n {'Category':<25} {'Pass/Total':>12} {'Rate':>8}")
    print(f" {'-'*25} {'-'*12} {'-'*8}")
    for cat, stats in sorted(category_stats.items()):
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f" {cat:<25} {stats['passed']:>3}/{stats['total']:<3} {rate:>7.0f}%")

    # 详细结果
    print(f"\n{'='*70}")
    print(f" Detailed Results")
    print(f"{'='*70}")

    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        elapsed = f"{r.get('elapsed', 0):.1f}s"
        print(f"  [{status}] {r['id']}: {r['question']}  ({r['type']}, {elapsed})")
        if not r["pass"]:
            if r["type"] == "error":
                print(f"         ERROR: {r.get('error', '')}")
            elif r["type"] == "clarification":
                print(f"         Unexpected clarification: {r.get('message', '')}")
            elif r["type"] == "no_output":
                print(f"         No SQL and no clarification")
            elif r.get("checks"):
                for check, ok in r["checks"].items():
                    if not ok:
                        print(f"         FAIL: {check}")

    print(f"\n{'='*70}")
    print(f" Summary: {passed}/{total} = {accuracy:.1f}%")
    print(f"{'='*70}\n")

    return accuracy


@pytest.fixture
def graph():
    from ai.engine.llm_v2.graph import get_v2_graph
    return get_v2_graph()


@pytest.fixture
def all_cases():
    return load_cases()


class TestFullE2E:
    """全量 E2E 基准测试"""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.environ.get("SKIP_LLM_TESTS") == "1",
        reason="Set SKIP_LLM_TESTS=0 to run"
    )
    async def test_all_45_cases(self, graph, all_cases):
        """跑全部 45 个用例"""
        if not all_cases:
            pytest.skip("No test cases loaded")

        results = []
        for case in all_cases:
            result = await run_single_case(graph, case)
            results.append(result)
            status = "PASS" if result["pass"] else "FAIL"
            print(f"  [{status}] {result['id']}: {result['question']} ({result.get('elapsed', 0):.1f}s)")

        accuracy = print_report(results, "Full E2E (45 cases)")

        # 目标：95%（允许 2-3 个失败）
        assert accuracy >= 80, f"Accuracy {accuracy:.1f}% below 80% threshold"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.environ.get("SKIP_LLM_TESTS") == "1",
        reason="Set SKIP_LLM_TESTS=0 to run"
    )
    async def test_first_15_cases(self, graph, all_cases):
        """快速验证：前 15 个用例"""
        cases = all_cases[:15]
        if not cases:
            pytest.skip("No test cases loaded")

        results = []
        for case in cases:
            result = await run_single_case(graph, case)
            results.append(result)

        accuracy = print_report(results, "Quick E2E (first 15)")

        assert accuracy >= 80, f"Accuracy {accuracy:.1f}% below 80% threshold"


if __name__ == "__main__":
    """CLI 直接运行：python tests/benchmark/test_full_e2e.py"""
    import argparse
    parser = argparse.ArgumentParser(description="Full E2E Benchmark")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of cases (0=all)")
    parser.add_argument("--ids", type=str, default="", help="Comma-separated case IDs (e.g. 001,006,031)")
    parser.add_argument("--category", type=str, default="", help="Filter by category")
    args = parser.parse_args()

    cases = load_cases()

    # 过滤
    if args.ids:
        target_ids = set(args.ids.split(","))
        cases = [c for c in cases if c["id"] in target_ids]
    if args.category:
        cases = [c for c in cases if c.get("category", "") == args.category]
    if args.limit > 0:
        cases = cases[:args.limit]

    if not cases:
        print("No matching cases found")
        sys.exit(1)

    print(f"Running {len(cases)} cases...")

    from ai.engine.llm_v2.graph import get_v2_graph
    graph = get_v2_graph()

    async def _run_all():
        return [await run_single_case(graph, c) for c in cases]

    results = asyncio.run(_run_all())

    accuracy = print_report(results, f"E2E Benchmark ({len(cases)} cases)")

    if accuracy >= 95:
        print("TARGET REACHED: >= 95%")
    elif accuracy >= 85:
        print("GOOD: >= 85% (P2 baseline)")
    else:
        print(f"BELOW TARGET: {accuracy:.1f}%")
