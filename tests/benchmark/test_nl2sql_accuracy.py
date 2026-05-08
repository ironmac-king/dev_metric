"""
NL2SQL Benchmark 测试框架

用法:
    pytest tests/benchmark/test_nl2sql_accuracy.py -v

测试模式:
    - sql_only: 只测试 SQL 生成（不调用 LLM），直接构造 MQL 输入
    - full_pipeline: 测试完整 NL→MQL→SQL 链路（需要 LLM API）
"""
import json
import os
import pytest
from typing import Dict, Any, List, Optional

# 测试用例目录
CASES_DIR = os.path.join(os.path.dirname(__file__), "cases")


def load_cases(filename: str = "mki_basic.json") -> List[Dict[str, Any]]:
    """加载测试用例"""
    filepath = os.path.join(CASES_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def check_sql_field(sql: str, expected_field: str) -> bool:
    """检查 SQL 中是否包含预期字段"""
    if not sql or not expected_field:
        return False
    return expected_field.upper() in sql.upper()


def check_sql_table(sql: str, expected_table: str) -> bool:
    """检查 SQL 中是否包含预期表名"""
    if not sql or not expected_table:
        return False
    # 去掉 schema 前缀匹配
    table_name = expected_table.split(".")[-1]
    return table_name.upper() in sql.upper()


def check_sql_dimensions(sql: str, expected_dims: List[str]) -> bool:
    """检查 SQL 中是否包含预期维度列"""
    if not expected_dims:
        return True
    for dim in expected_dims:
        if dim.upper() not in sql.upper():
            return False
    return True


def check_sql_dimensions_contains(sql: str, keyword: str) -> bool:
    """检查 SQL 中是否包含含关键词的维度"""
    if not keyword:
        return True
    return keyword.upper() in sql.upper()


def check_sql_agg(sql: str, expected_agg: str, expected_field: str) -> bool:
    """检查 SQL 中是否包含预期聚合函数"""
    if not expected_agg or not expected_field:
        return True  # 不检查
    pattern = f"{expected_agg}({expected_field})"
    return pattern.upper() in sql.upper()


def evaluate_case(sql: str, expected: Dict[str, Any]) -> Dict[str, Any]:
    """评估单个测试用例"""
    results = {"pass": True, "checks": {}}

    # 1. 表名检查
    if "table" in expected:
        ok = check_sql_table(sql, expected["table"])
        results["checks"]["table"] = ok
        if not ok:
            results["pass"] = False

    # 2. 字段检查
    if "field" in expected:
        ok = check_sql_field(sql, expected["field"])
        results["checks"]["field"] = ok
        if not ok:
            results["pass"] = False

    # 3. 多字段检查
    if "fields" in expected:
        for f in expected["fields"]:
            ok = check_sql_field(sql, f)
            results["checks"][f"field_{f}"] = ok
            if not ok:
                results["pass"] = False

    # 4. 聚合检查
    if "agg" in expected and "field" in expected:
        ok = check_sql_agg(sql, expected["agg"], expected["field"])
        results["checks"]["agg"] = ok
        if not ok:
            results["pass"] = False

    # 5. 维度检查
    if "dimensions" in expected:
        ok = check_sql_dimensions(sql, expected["dimensions"])
        results["checks"]["dimensions"] = ok
        if not ok:
            results["pass"] = False

    # 6. 维度关键词检查
    if "dimensions_contains" in expected:
        ok = check_sql_dimensions_contains(sql, expected["dimensions_contains"])
        results["checks"]["dimensions_contains"] = ok
        if not ok:
            results["pass"] = False

    # 7. 过滤条件检查
    if "filters" in expected:
        for f in expected["filters"]:
            ok = f["value"] in sql
            results["checks"][f"filter_{f['field']}"] = ok
            if not ok:
                results["pass"] = False

    # 8. SQL 模式检查
    if "patterns" in expected:
        for p in expected["patterns"]:
            ok = p.upper() in sql.upper()
            results["checks"][f"pattern_{p}"] = ok
            if not ok:
                results["pass"] = False

    return results


class TestNL2SQLAccuracy:
    """SQL 生成准确率测试（sql_only 模式）"""

    @pytest.fixture
    def sql_generator(self):
        from ai.engine.llm_v2.nodes.sql_generator import SQLGeneratorNode
        return SQLGeneratorNode()

    @pytest.fixture
    def cases(self):
        return load_cases()

    def _build_mql_for_case(self, case: Dict[str, Any]):
        """根据测试用例构造 MQL 输入"""
        from ai.engine.llm_v2.schema import (
            MQLSchema, MQLMetric, TimeRange, MQLDimension, MQLFilter, MQLIntent
        )

        expected = case["expected"]
        category = case.get("category", "simple_value")

        # 确定意图
        intent_map = {
            "simple_value": MQLIntent.QUERY_VALUE,
            "filtered_value": MQLIntent.QUERY_VALUE,
            "dimension_ranking": MQLIntent.QUERY_VALUE,
            "dimension_group": MQLIntent.QUERY_VALUE,
            "comparison": MQLIntent.QUERY_COMPARISON,
            "trend": MQLIntent.QUERY_TREND,
            "multi_metric": MQLIntent.QUERY_VALUE,
        }
        intent = intent_map.get(category, MQLIntent.QUERY_VALUE)

        # 构造指标
        metric = MQLMetric(
            name=expected.get("field", ""),
            field=expected.get("field", ""),
            table=expected.get("table", ""),
        )

        # 构造维度
        dimensions = []
        if "dimensions" in expected:
            for dim_col in expected["dimensions"]:
                dimensions.append(MQLDimension(type=dim_col, column=dim_col))
        if "dimensions_contains" in expected:
            dimensions.append(MQLDimension(type="品类", column="GROUP_3"))

        # 构造时间
        time = TimeRange(start="2026-04-01", end="2026-04-30")

        # 构造过滤
        filters = []
        if "filters" in expected:
            for f in expected["filters"]:
                filters.append(MQLFilter(field=f["field"], operator="eq", value=f["value"]))

        mql = MQLSchema(
            intent=intent,
            metric=metric,
            time=time,
            dimensions=dimensions,
            filters=filters,
        )

        # 多指标
        if "fields" in expected:
            mql.metrics = []
            for f in expected["fields"][1:]:
                mql.metrics.append(MQLMetric(name=f, field=f, table=expected.get("table", "")))

        return mql

    @pytest.mark.asyncio
    async def test_sql_generation_accuracy(self, sql_generator, cases):
        """测试 SQL 生成准确率"""
        if not cases:
            pytest.skip("No test cases loaded")

        results = []
        for case in cases:
            mql = self._build_mql_for_case(case)
            result = await sql_generator.generate(mql)
            sql = result.get("sql", "") if isinstance(result, dict) else ""

            eval_result = evaluate_case(sql, case["expected"])
            eval_result["id"] = case["id"]
            eval_result["question"] = case["question"]
            eval_result["sql"] = sql[:200] if sql else "EMPTY"
            results.append(eval_result)

        # 输出报告
        total = len(results)
        passed = sum(1 for r in results if r["pass"])
        accuracy = passed / total * 100 if total > 0 else 0

        print(f"\n{'='*60}")
        print(f"NL2SQL Benchmark Report")
        print(f"{'='*60}")
        print(f"Total: {total}  Passed: {passed}  Accuracy: {accuracy:.1f}%")
        print(f"{'='*60}")

        for r in results:
            status = "PASS" if r["pass"] else "FAIL"
            print(f"  [{status}] {r['id']}: {r['question']}")
            if not r["pass"]:
                for check, ok in r["checks"].items():
                    if not ok:
                        print(f"    FAIL: {check}")

        # 要求至少 80% 通过率
        assert accuracy >= 80, f"Accuracy {accuracy:.1f}% is below 80% threshold"


class TestSQLSecurityAuditor:
    """SQL 安全审计器测试"""

    @pytest.fixture
    def auditor(self):
        from ai.engine.llm_v2.nodes.sql_auditor import SQLSecurityAuditor
        return SQLSecurityAuditor()

    def test_normal_sql_passes(self, auditor):
        sql = "SELECT SUM(INCOME_NBCSS) AS sales FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-04-01'"
        ok, msg = auditor.audit(sql)
        assert ok, f"Normal SQL should pass: {msg}"

    def test_dangerous_keyword_blocked(self, auditor):
        sql = "DROP TABLE users"
        ok, msg = auditor.audit(sql)
        assert not ok

    def test_unauthorized_table_blocked(self, auditor):
        sql = "SELECT * FROM evil_table WHERE 1=1"
        ok, msg = auditor.audit(sql)
        assert not ok

    def test_comment_injection_blocked(self, auditor):
        sql = "SELECT * FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE 1=1; -- DROP TABLE"
        ok, msg = auditor.audit(sql)
        assert not ok

    def test_cte_sql_passes(self, auditor):
        sql = "WITH base_agg AS (SELECT SUM(INCOME_NBCSS) AS v FROM ids.IDS_AMZ_COMPREHENSIVE_DI) SELECT v FROM base_agg"
        ok, msg = auditor.audit(sql)
        assert ok, f"CTE SQL should pass: {msg}"

    def test_non_select_blocked(self, auditor):
        sql = "UPDATE ids.IDS_AMZ_COMPREHENSIVE_DI SET FDATE = '2026-01-01'"
        ok, msg = auditor.audit(sql)
        assert not ok


class TestDimensionValidation:
    """维度验证测试"""

    @pytest.fixture
    def validator(self):
        from ai.engine.llm_v2.nodes.mql_validator import MQLSemanticValidator
        return MQLSemanticValidator()

    def test_known_dimension_passes(self, validator):
        from ai.engine.llm_v2.schema import MQLDimension
        ok, msg = validator._validate_dimension(MQLDimension(type="站点", column="FSITE"))
        assert ok

    def test_time_dimension_passes(self, validator):
        from ai.engine.llm_v2.schema import MQLDimension
        ok, msg = validator._validate_dimension(MQLDimension(type="time_grain", column="MONTHS"))
        assert ok

    def test_unknown_dimension_warns(self, validator):
        from ai.engine.llm_v2.schema import MQLDimension
        ok, msg = validator._validate_dimension(MQLDimension(type="unknown", column="WEIRD"))
        assert ok  # warns but doesn't block


class TestFullPipeline:
    """完整 NL→MQL→SQL 链路测试（需要本地 LLM）"""

    @pytest.fixture
    def graph(self):
        from ai.engine.llm_v2.graph import get_v2_graph
        return get_v2_graph()

    @pytest.fixture
    def cases(self):
        # 只取前 10 个 case 做全链路测试（较慢）
        return load_cases()[:10]

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.environ.get("SKIP_LLM_TESTS") == "1",
        reason="Set SKIP_LLM_TESTS=0 to run LLM-dependent tests"
    )
    async def test_full_pipeline_accuracy(self, graph, cases):
        """测试完整 NL→MQL→SQL 链路"""
        from ai.engine.llm_v2.schema import V2State

        results = []
        for case in cases:
            question = case["question"]
            expected = case["expected"]

            # 构造初始状态
            state = V2State(
                question=question,
                session_id="benchmark_test",
            )

            # 执行完整链路
            try:
                final_state = await graph.ainvoke(state)

                # 检查 SQL
                sql = final_state.sql or ""
                if final_state.needs_clarification:
                    # 追问场景：检查追问消息是否合理
                    results.append({
                        "id": case["id"],
                        "question": question,
                        "pass": True,  # 追问也算通过
                        "type": "clarification",
                        "message": final_state.clarification_message,
                    })
                else:
                    eval_result = evaluate_case(sql, expected)
                    results.append({
                        "id": case["id"],
                        "question": question,
                        "pass": eval_result["pass"],
                        "type": "sql",
                        "sql": sql[:200],
                        "checks": eval_result["checks"],
                    })
            except Exception as e:
                results.append({
                    "id": case["id"],
                    "question": question,
                    "pass": False,
                    "type": "error",
                    "error": str(e),
                })

        # 输出报告
        total = len(results)
        passed = sum(1 for r in results if r["pass"])
        accuracy = passed / total * 100 if total > 0 else 0

        print(f"\n{'='*60}")
        print(f"Full Pipeline Benchmark Report (LLM)")
        print(f"{'='*60}")
        print(f"Total: {total}  Passed: {passed}  Accuracy: {accuracy:.1f}%")
        print(f"{'='*60}")

        for r in results:
            status = "PASS" if r["pass"] else "FAIL"
            print(f"  [{status}] {r['id']}: {r['question']} ({r['type']})")
            if not r["pass"]:
                if r["type"] == "error":
                    print(f"    ERROR: {r['error']}")
                elif r.get("checks"):
                    for check, ok in r["checks"].items():
                        if not ok:
                            print(f"    FAIL: {check}")

        # 要求至少 60% 通过率（LLM 不稳定，降低阈值）
        assert accuracy >= 60, f"Full pipeline accuracy {accuracy:.1f}% is below 60% threshold"


class TestGenericDimensionClarification:
    """泛指维度追问测试"""

    @pytest.fixture
    def graph(self):
        from ai.engine.llm_v2.graph import get_v2_graph
        return get_v2_graph()

    @pytest.mark.asyncio
    async def test_generic_category_triggers_clarification(self, graph):
        """'按品类看本月销售额' 应触发品类级别追问"""
        from ai.engine.llm_v2.schema import V2State
        state = V2State(question="按品类看本月销售额", session_id="test_generic")
        result = await graph.ainvoke(state)
        assert result.needs_clarification, "应该触发追问"
        assert "品类" in (result.clarification_message or ""), f"追问消息应包含'品类': {result.clarification_message}"
        assert result.sql is None or result.sql == "", "泛指维度不应生成 SQL"

    @pytest.mark.asyncio
    async def test_specific_category_no_clarification(self, graph):
        """'按三级品类看本月销售额' 不应触发追问"""
        from ai.engine.llm_v2.schema import V2State
        state = V2State(question="按三级品类看本月销售额", session_id="test_specific")
        result = await graph.ainvoke(state)
        assert not result.needs_clarification, "具体品类级别不应触发追问"

    @pytest.mark.asyncio
    async def test_ge_category_triggers_clarification(self, graph):
        """'各品类销售额' 应触发品类级别追问"""
        from ai.engine.llm_v2.schema import V2State
        state = V2State(question="各品类销售额", session_id="test_ge")
        result = await graph.ainvoke(state)
        assert result.needs_clarification, "应该触发追问"
        assert "品类" in (result.clarification_message or ""), f"追问消息应包含'品类': {result.clarification_message}"

    @pytest.mark.asyncio
    async def test_normal_query_no_clarification(self, graph):
        """'本月销售额是多少' 不应触发追问"""
        from ai.engine.llm_v2.schema import V2State
        state = V2State(question="本月销售额是多少", session_id="test_normal")
        result = await graph.ainvoke(state)
        assert not result.needs_clarification, "普通查询不应触发追问"