"""V2 SQL Generator 单元测试 — CTE Jinja2 重构版"""
import pytest
import asyncio
from ai.engine.llm_v2.nodes.sql_generator import SQLGeneratorNode
from ai.engine.llm_v2.schema import (
    MQLSchema, MQLMetric, MQLDimension, MQLIntent, MQLFilter,
    TimeRange, TimeType, OperatorType, CalculationPattern
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def generator():
    return SQLGeneratorNode()


@pytest.fixture
def simple_mql():
    """原子查询 MQL"""
    mql = MQLSchema()
    mql.intent = MQLIntent.QUERY_VALUE
    mql.metric = MQLMetric(
        name="访客数",
        field="PAGEVIEWS_TOTAL",
        aggregation="SUM",
        starrocks_sql="SUM(PAGEVIEWS_TOTAL)"
    )
    mql.time = TimeRange(type=TimeType.RELATIVE, days=30)
    mql.dimensions = [MQLDimension(type="CATEGORY", column="GROUP_3")]
    mql.filters = [MQLFilter(field="GROUP_3", operator=OperatorType.EQ, value="Electronics")]
    return mql


@pytest.fixture
def mom_mql():
    """环比查询 MQL"""
    mql = MQLSchema()
    mql.intent = MQLIntent.QUERY_TREND
    mql.metric = MQLMetric(
        name="销售额",
        field="ORDERED_PRODUCTSALES",
        aggregation="SUM",
        starrocks_sql="SUM(ORDERED_PRODUCTSALES)"
    )
    mql.time = TimeRange(type=TimeType.ABSOLUTE_MONTH, days=90)
    mql.dimensions = [
        MQLDimension(type="MONTH", column="MONTHS"),
        MQLDimension(type="YEAR", column="YEARS"),
    ]
    mql.filters = [MQLFilter(field="YEARS", operator=OperatorType.EQ, value="2026")]
    mql.calculation_patterns = [CalculationPattern.MOM]
    return mql


@pytest.fixture
def yoy_mql():
    """同比查询 MQL"""
    mql = MQLSchema()
    mql.intent = MQLIntent.QUERY_TREND
    mql.metric = MQLMetric(
        name="销售额",
        field="ORDERED_PRODUCTSALES",
        aggregation="SUM",
        starrocks_sql="SUM(ORDERED_PRODUCTSALES)"
    )
    mql.time = TimeRange(type=TimeType.ABSOLUTE_MONTH, days=365)
    mql.dimensions = [
        MQLDimension(type="MONTH", column="MONTHS"),
        MQLDimension(type="YEAR", column="YEARS"),
    ]
    mql.filters = [MQLFilter(field="YEARS", operator=OperatorType.EQ, value="2026")]
    mql.calculation_patterns = [CalculationPattern.YOY]
    return mql


@pytest.fixture
def ranking_mql():
    """排名查询 MQL"""
    mql = MQLSchema()
    mql.intent = MQLIntent.QUERY_RANKING
    mql.metric = MQLMetric(
        name="销售额",
        field="ORDERED_PRODUCTSALES",
        aggregation="SUM",
        starrocks_sql="SUM(ORDERED_PRODUCTSALES)"
    )
    mql.time = TimeRange(type=TimeType.RELATIVE, days=30)
    mql.dimensions = [MQLDimension(type="CATEGORY", column="GROUP_3")]
    mql.calculation_patterns = [CalculationPattern.RANKING]
    mql.top_n = 10
    return mql


# ============================================================
# 安全测试
# ============================================================

class TestSQLGeneratorSecurity:
    """SQL 生成器安全性测试"""

    def test_validate_field_name_accepts_valid(self, generator):
        valid_fields = ["FDATE", "GROUP_1", "PAGEVIEWS_TOTAL", "col_123", "_private"]
        for field in valid_fields:
            assert generator._validate_field_name(field) == field

    def test_validate_field_name_rejects_sql_injection(self, generator):
        malicious_fields = [
            "FDATE; DROP TABLE users;--",
            "GROUP_1' OR '1'='1",
            "1; SELECT * FROM passwords",
            "a'b OR 'c'='c",
            "col; UPDATE metrics SET value=0;--",
        ]
        for field in malicious_fields:
            with pytest.raises(ValueError, match="非法字段名"):
                generator._validate_field_name(field)

    def test_sanitize_value_escapes_quotes(self, generator):
        assert generator._sanitize_value("'; DROP TABLE users;--") == "''; DROP TABLE users;--"
        assert generator._sanitize_value("1' OR '1'='1") == "1'' OR ''1''=''1"
        assert generator._sanitize_value("admin'--") == "admin''--"

    def test_sanitize_value_handles_none(self, generator):
        assert generator._sanitize_value(None) == "NULL"

    def test_sanitize_value_handles_numbers(self, generator):
        assert generator._sanitize_value(123) == "123"
        assert generator._sanitize_value(45.67) == "45.67"


# ============================================================
# CTE 三层结构测试
# ============================================================

class TestCTEStructure:
    """验证 CTE 三层结构正确生成"""

    @pytest.mark.asyncio
    async def test_atomic_query_has_three_cte_layers(self, generator, simple_mql):
        """原子查询应生成 WITH...date_meta...base_agg...calc_layer 结构"""
        result = await generator.generate(simple_mql)
        sql = result["sql"]
        assert "WITH" in sql
        assert "date_meta AS" in sql
        assert "base_agg AS" in sql
        assert "calc_layer AS" in sql
        assert "SELECT * FROM calc_layer" in sql

    @pytest.mark.asyncio
    async def test_atomic_query_no_double_aggregation(self, generator, simple_mql):
        """原子查询 SUM 不应出现 double aggregation"""
        result = await generator.generate(simple_mql)
        sql = result["sql"]
        # 只应有一个 SUM 聚合表达式
        # double aggregation check: only one SUM( expected
        assert sql.upper().count("SUM(") == 1, f"Expected 1 SUM(, got {sql.upper().count(chr(83)+chr(40))}"

    @pytest.mark.asyncio
    async def test_atomic_query_uses_agg_expression(self, generator, simple_mql):
        """应使用 starrocks_sql 提取的 agg_expression"""
        result = await generator.generate(simple_mql)
        sql = result["sql"]
        assert "PAGEVIEWS_TOTAL" in sql
        assert "_raw" in sql  # base_agg 别名

    @pytest.mark.asyncio
    async def test_atomic_query_has_group_by(self, generator, simple_mql):
        """应包含 GROUP BY 子句"""
        result = await generator.generate(simple_mql)
        sql = result["sql"]
        assert "GROUP BY" in sql

    @pytest.mark.asyncio
    async def test_atomic_query_filter_escaped(self, generator, simple_mql):
        """WHERE 条件中的值应被正确转义"""
        result = await generator.generate(simple_mql)
        sql = result["sql"]
        # 单引号应被转义为 ''
        assert "Electronics" in sql

    @pytest.mark.asyncio
    async def test_atomic_query_has_limit(self, generator, simple_mql):
        """应包含 LIMIT 子句"""
        result = await generator.generate(simple_mql)
        sql = result["sql"]
        assert "LIMIT" in sql


class TestMoMCalculation:
    """环比计算测试"""

    @pytest.mark.asyncio
    async def test_mom_generates_lag_1(self, generator, mom_mql):
        """环比应使用 LAG offset=1"""
        result = await generator.generate(mom_mql)
        sql = result["sql"]
        assert "LAG" in sql
        assert ", 1)" in sql  # offset=1

    @pytest.mark.asyncio
    async def test_mom_has_case_when(self, generator, mom_mql):
        """环比应使用 CASE WHEN 处理 month_full"""
        result = await generator.generate(mom_mql)
        sql = result["sql"]
        # CASE WHEN for is_month_full is in date_meta CTE
        assert "is_month_full" in sql
        assert "is_month_full" in sql

    @pytest.mark.asyncio
    async def test_mom_uses_dt_column_in_window(self, generator, mom_mql):
        """窗口函数 ORDER BY 应使用 dt 列"""
        result = await generator.generate(mom_mql)
        sql = result["sql"]
        assert "ORDER BY" in sql
        # window function 中有 PARTITION BY 和 ORDER BY
        assert "PARTITION BY" in sql


class TestYoYCalculation:
    """同比计算测试"""

    @pytest.mark.asyncio
    async def test_yoy_generates_lag_12(self, generator, yoy_mql):
        """同比应使用 LAG offset=12"""
        result = await generator.generate(yoy_mql)
        sql = result["sql"]
        assert "LAG" in sql
        assert ", 12)" in sql  # offset=12 for YoY

    @pytest.mark.asyncio
    async def test_yoy_divides_by_last_year(self, generator, yoy_mql):
        """同比应包含去年日期计算"""
        result = await generator.generate(yoy_mql)
        sql = result["sql"]
        # date_meta 中应有 last_year_date / last_year_month_start
        assert "last_year_date" in sql or "INTERVAL -12 MONTH" in sql


class TestRankingCalculation:
    """排名计算测试"""

    @pytest.mark.asyncio
    async def test_ranking_generates_rank(self, generator, ranking_mql):
        """排名查询应使用 RANK()"""
        result = await generator.generate(ranking_mql)
        sql = result["sql"]
        assert "RANK()" in sql

    @pytest.mark.asyncio
    async def test_ranking_orders_desc(self, generator, ranking_mql):
        """RANK() 应按指标值降序"""
        result = await generator.generate(ranking_mql)
        sql = result["sql"]
        # 应有 DESC 排序
        assert "DESC" in sql

    @pytest.mark.asyncio
    async def test_ranking_limit_top_n(self, generator, ranking_mql):
        """应使用 top_n 作为 LIMIT"""
        result = await generator.generate(ranking_mql)
        sql = result["sql"]
        assert "LIMIT 10" in sql


# ============================================================
# 语义 JSON 测试
# ============================================================

class TestMQLToSemantic:
    """_mql_to_semantic() 转换逻辑测试"""

    def test_converts_atomic_metric(self, generator, simple_mql):
        semantic = generator._mql_to_semantic(simple_mql)
        assert "tables" in semantic
        assert "dimensions" in semantic
        assert "metrics" in semantic
        assert "filters" in semantic
        assert "calculated_metrics" in semantic
        assert semantic["tables"][0] == "ids.IDS_AMZ_COMPREHENSIVE_DI"

    def test_converts_filter_operator(self, generator, simple_mql):
        """Filter OperatorType 应转换为 SQL 操作符"""
        semantic = generator._mql_to_semantic(simple_mql)
        assert semantic["filters"][0]["op"] == "="
        assert semantic["filters"][0]["field"] == "GROUP_3"

    def test_adds_dt_column_for_window_functions(self, generator, mom_mql):
        """有计算模式时自动补充 dt 列"""
        semantic = generator._mql_to_semantic(mom_mql)
        assert "FDATE" in semantic["dimensions"]
        assert semantic["dt_column"] == "FDATE"

    def test_mom_calculated_metric_format(self, generator, mom_mql):
        """MoM 应生成正确的 calculated_metric 格式"""
        semantic = generator._mql_to_semantic(mom_mql)
        assert len(semantic["calculated_metrics"]) == 1
        cm = semantic["calculated_metrics"][0]
        assert cm["op"] == "mom"
        assert "args" in cm
        assert "name" in cm


# ============================================================
# 维度列映射测试
# ============================================================

class TestDimensionColumnMapping:
    """_get_dimension_column() 映射测试"""

    def test_english_keys(self, generator):
        assert generator._get_dimension_column("CATEGORY") == "GROUP_3"
        assert generator._get_dimension_column("SHOP") == "FSITE"
        assert generator._get_dimension_column("MONTH") == "MONTHS"
        assert generator._get_dimension_column("YEAR") == "YEARS"
        assert generator._get_dimension_column("DAY") == "FDATE"

    def test_chinese_keys(self, generator):
        assert generator._get_dimension_column("品类") == "GROUP_3"
        assert generator._get_dimension_column("店铺") == "FSITE"
        assert generator._get_dimension_column("月") == "MONTHS"
        assert generator._get_dimension_column("年") == "YEARS"

    def test_case_insensitive(self, generator):
        assert generator._get_dimension_column("category") == "GROUP_3"
        assert generator._get_dimension_column("MONTH") == "MONTHS"

    def test_raw_column_name(self, generator):
        """全大写的列名应直接返回"""
        assert generator._get_dimension_column("FPRODUCTLINE") == "FPRODUCTLINE"
        assert generator._get_dimension_column("FCOUNTRY") == "FCOUNTRY"

    def test_unknown_returns_empty(self, generator):
        assert generator._get_dimension_column("UNKNOWN_XYZ") == "UNKNOWN_XYZ"  # fallback for uppercase column names
        assert generator._get_dimension_column("") == ""
