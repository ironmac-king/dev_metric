"""V2 SQL Generator 单元测试"""
import pytest
from ai.engine.llm_v2.nodes.sql_generator import SQLGeneratorNode
from ai.engine.llm_v2.schema import (
    MQLSchema, MQLMetric, MQLDimension, MQLIntent, MQLFilter,
    TimeRange, TimeType, OperatorType, CalculationPattern
)


class TestSQLGeneratorSecurity:
    """SQL 生成器安全性测试"""

    @pytest.fixture
    def generator(self):
        """SQL 生成器 fixture"""
        return SQLGeneratorNode()

    def test_validate_field_name_accepts_valid(self, generator):
        """合法字段名应通过验证"""
        valid_fields = ["FDATE", "GROUP_1", "PAGEVIEWS_TOTAL", "col_123", "_private"]
        for field in valid_fields:
            result = generator._validate_field_name(field)
            assert result == field, f"字段 {field} 应该通过验证"

    def test_validate_field_name_rejects_sql_injection(self, generator):
        """SQL 注入攻击应被拒绝"""
        malicious_fields = [
            "FDATE; DROP TABLE users;--",
            "GROUP_1' OR '1'='1",
            "FDATE`; DELETE FROM metrics;--",
            "1; SELECT * FROM passwords",
            "a'b OR 'c'='c",
            "col; UPDATE metrics SET value=0;--",
        ]
        for field in malicious_fields:
            with pytest.raises(ValueError, match="非法字段名"):
                generator._validate_field_name(field)

    def test_sanitize_value_escapes_quotes(self, generator):
        """单引号应被正确转义"""
        # SQL 注入典型payload
        assert generator._sanitize_value("'; DROP TABLE users;--") == "''; DROP TABLE users;--"
        assert generator._sanitize_value("1' OR '1'='1") == "1'' OR ''1''=''1"
        assert generator._sanitize_value("admin'--") == "admin''--"

    def test_sanitize_value_handles_none(self, generator):
        """None 值应返回 NULL"""
        assert generator._sanitize_value(None) == "NULL"

    def test_sanitize_value_handles_numbers(self, generator):
        """数字应被转换为字符串"""
        assert generator._sanitize_value(123) == "123"
        assert generator._sanitize_value(45.67) == "45.67"


class TestSQLGeneratorBasic:
    """SQL 生成器基础功能测试"""

    @pytest.fixture
    def generator(self):
        return SQLGeneratorNode()

    @pytest.fixture
    def simple_mql(self):
        """简单指标查询 MQL"""
        mql = MQLSchema()
        mql.intent = MQLIntent.QUERY_VALUE
        mql.metric = MQLMetric(
            name="访客数",
            field="PAGEVIEWS_TOTAL",
            aggregation="SUM",
            starrocks_sql="SELECT SUM(PAGEVIEWS_TOTAL) AS PAGEVIEWS_TOTAL FROM IDS_AMZ_DI"
        )
        mql.time = TimeRange(
            type=TimeType.RELATIVE,
            original="本月"
        )
        return mql

    def test_build_simple_query(self, generator, simple_mql):
        """简单指标查询"""
        sql = generator._build_sql(simple_mql)
        assert "SELECT" in sql
        assert "SUM(PAGEVIEWS_TOTAL)" in sql
        assert "IDS_AMZ_COMPREHENSIVE_DI" in sql

    def test_build_query_with_dimension(self, generator, simple_mql):
        """带维度的查询"""
        simple_mql.dimensions = [
            MQLDimension(type="GROUP_1", value=None)
        ]
        sql = generator._build_sql(simple_mql)
        assert "SELECT" in sql
        assert "GROUP BY" in sql

    def test_build_query_with_time_filter(self, generator, simple_mql):
        """带时间条件的查询"""
        sql = generator._build_sql(simple_mql)
        assert "WHERE" in sql
        assert "FDATE >=" in sql


class TestSQLGeneratorMoM:
    """环比/同比查询测试"""

    @pytest.fixture
    def generator(self):
        return SQLGeneratorNode()

    @pytest.fixture
    def mom_mql(self):
        """环比查询 MQL"""
        mql = MQLSchema()
        mql.intent = MQLIntent.QUERY_TREND
        mql.metric = MQLMetric(
            name="销售额",
            field="ORDERED_PRODUCTSALES",
            aggregation="SUM",
            starrocks_sql="SELECT SUM(ORDERED_PRODUCTSALES) AS ORDERED_PRODUCTSALES FROM IDS_AMZ_DI"
        )
        mql.time = TimeRange(
            type=TimeType.DATE_RANGE,
            start="2026-04-01",
            end="2026-04-23"
        )
        mql.calculation_patterns = [CalculationPattern.MOM]
        return mql

    def test_build_mom_sql(self, generator, mom_mql):
        """环比查询 SQL 生成"""
        sql = generator._build_sql(mom_mql)
        assert '"当前值"' in sql
        assert '"环比值"' in sql
        assert '"环比变化"' in sql
        assert "CASE WHEN" in sql  # 条件聚合

    def test_mom_has_group_by_for_business_dimensions(self, generator, mom_mql):
        """带业务维度的环比查询应有 GROUP BY"""
        mom_mql.dimensions = [MQLDimension(type="GROUP_1", value=None)]
        sql = generator._build_sql(mom_mql)
        assert "GROUP BY" in sql


class TestSQLGeneratorYoY:
    """同比查询测试"""

    @pytest.fixture
    def generator(self):
        return SQLGeneratorNode()

    @pytest.fixture
    def yoy_mql(self):
        """同比查询 MQL"""
        mql = MQLSchema()
        mql.intent = MQLIntent.QUERY_TREND
        mql.metric = MQLMetric(
            name="销售额",
            field="ORDERED_PRODUCTSALES",
            aggregation="SUM",
            starrocks_sql="SELECT SUM(ORDERED_PRODUCTSALES) AS ORDERED_PRODUCTSALES FROM IDS_AMZ_DI"
        )
        mql.time = TimeRange(
            type=TimeType.DATE_RANGE,
            start="2026-04-01",
            end="2026-04-23"
        )
        mql.calculation_patterns = [CalculationPattern.YOY]
        return mql

    def test_build_yoy_sql(self, generator, yoy_mql):
        """同比查询 SQL 生成"""
        sql = generator._build_sql(yoy_mql)
        assert '"当前值"' in sql
        assert '"同比值"' in sql
        assert '"同比变化"' in sql


class TestSQLGeneratorDimensionFiltering:
    """维度过滤测试"""

    @pytest.fixture
    def generator(self):
        return SQLGeneratorNode()

    @pytest.fixture
    def filtered_mql(self):
        """带维度过滤的 MQL"""
        mql = MQLSchema()
        mql.intent = MQLIntent.QUERY_VALUE
        mql.metric = MQLMetric(
            name="销售额",
            field="ORDERED_PRODUCTSALES",
            aggregation="SUM",
            starrocks_sql="SELECT SUM(ORDERED_PRODUCTSALES) AS ORDERED_PRODUCTSALES FROM IDS_AMZ_DI"
        )
        mql.dimensions = [
            MQLDimension(type="GROUP_1", value="电子产品")
        ]
        mql.time = TimeRange(
            type=TimeType.RELATIVE,
            original="本月"
        )
        return mql

    def test_dimension_filter_in_where(self, generator, filtered_mql):
        """维度过滤应出现在 WHERE 子句"""
        sql = generator._build_sql(filtered_mql)
        assert "WHERE" in sql
        assert "GROUP_1" in sql
        assert "电子产品" in sql  # 值被正确引用


# ============================================================
# 新增测试：覆盖重构后的各模块
# ============================================================

class TestSQLSecurityModule:
    """ai.sql_gen.security 统一安全校验模块"""

    def test_validate_sql_blocks_drop(self):
        from ai.sql_gen.security import validate_sql
        assert not validate_sql("DROP TABLE users")

    def test_validate_sql_blocks_delete(self):
        from ai.sql_gen.security import validate_sql
        assert not validate_sql("DELETE FROM metrics WHERE id=1")

    def test_validate_sql_blocks_advanced_injection(self):
        from ai.sql_gen.security import validate_sql
        assert not validate_sql("SELECT 1; EXEC sp_executesql 'SELECT 1'")
        assert not validate_sql("SELECT * FROM t; xp_cmdshell 'whoami'")
        assert not validate_sql("SELECT OPENROWSET(...)")

    def test_validate_sql_allows_select(self):
        from ai.sql_gen.security import validate_sql
        assert validate_sql("SELECT SUM(SALES) FROM ids.TABLE WHERE FDATE >= '2026-01-01'")

    def test_validate_sql_strips_comments_before_check(self):
        from ai.sql_gen.security import validate_sql
        # 注释包裹不能绕过检测
        assert not validate_sql("SELECT 1 /* DROP TABLE x */")
        assert not validate_sql("SELECT 1 -- DELETE FROM x\n")

    def test_validate_sql_handles_quoted_strings(self):
        from ai.sql_gen.security import validate_sql
        # 字符串字面量中的关键字不应触发告警
        assert validate_sql("SELECT * FROM t WHERE name = 'drop shipment'")

    def test_validate_data_filter_delegates(self):
        from ai.sql_gen.security import validate_data_filter
        assert validate_data_filter("site = 'US'")
        assert not validate_data_filter("site = 'US'; DROP TABLE t;")


class TestSQLCacheTTL:
    """cache.py 基于 TTLCache 的有界缓存"""

    def test_set_and_get(self):
        from ai.sql_gen.cache import SQLCache
        c = SQLCache(max_size=100, ttl_seconds=60)
        c.set("SELECT 1", {"rows": []})
        assert c.get("SELECT 1") == {"rows": []}

    def test_miss_returns_none(self):
        from ai.sql_gen.cache import SQLCache
        c = SQLCache(max_size=100, ttl_seconds=60)
        assert c.get("SELECT 999") is None

    def test_size_bounded(self):
        from ai.sql_gen.cache import SQLCache
        c = SQLCache(max_size=3, ttl_seconds=60)
        for i in range(10):
            c.set(f"SELECT {i}", i)
        assert c.size() <= 3

    def test_clear(self):
        from ai.sql_gen.cache import SQLCache
        c = SQLCache(max_size=100, ttl_seconds=60)
        c.set("SELECT 1", 1)
        c.clear()
        assert c.size() == 0


class TestParseRelativeTime:
    """_parse_relative_time() 使用 TimeParser 后的行为验证"""

    @pytest.fixture
    def generator(self):
        return SQLGeneratorNode()

    def test_returns_sql_condition(self, generator):
        result = generator._parse_relative_time("本月")
        assert "FDATE >=" in result
        assert "FDATE <=" in result

    def test_today(self, generator):
        result = generator._parse_relative_time("今天")
        assert "FDATE >=" in result
        assert "FDATE <=" in result
        # 今天的 start == end
        import re
        dates = re.findall(r"'\d{4}-\d{2}-\d{2}'", result)
        assert len(dates) == 2
        assert dates[0] == dates[1]

    def test_last_month(self, generator):
        result = generator._parse_relative_time("上月")
        assert "FDATE >=" in result
        assert "FDATE <=" in result

    def test_relative_n_days(self, generator):
        result = generator._parse_relative_time("近30天")
        assert "FDATE >=" in result

    def test_updates_mql_time(self, generator):
        mql = MQLSchema()
        mql.time = TimeRange(type=TimeType.RELATIVE, original="近7天")
        generator._parse_relative_time("近7天", mql=mql)
        assert mql.time.start is not None
        assert mql.time.end is not None

    def test_fallback_on_unknown_expr(self, generator):
        # 无法识别的表达式降级为本月，不抛异常
        result = generator._parse_relative_time("某个奇怪的时间表达式xyz")
        assert "FDATE >=" in result


class TestDeduplicateDimensions:
    """_deduplicate_dimensions() 静态方法"""

    def test_removes_exact_duplicates(self):
        dims = [
            MQLDimension(type="GROUP_1", value="A"),
            MQLDimension(type="GROUP_1", value="A"),
            MQLDimension(type="GROUP_2", value=None),
        ]
        result = SQLGeneratorNode._deduplicate_dimensions(dims)
        assert len(result) == 2

    def test_preserves_order(self):
        dims = [
            MQLDimension(type="GROUP_1", value=None),
            MQLDimension(type="GROUP_2", value=None),
        ]
        result = SQLGeneratorNode._deduplicate_dimensions(dims)
        assert result[0].type == "GROUP_1"
        assert result[1].type == "GROUP_2"

    def test_empty_list(self):
        assert SQLGeneratorNode._deduplicate_dimensions([]) == []


class TestBuildComparisonPeriodWhere:
    """_build_comparison_period_where() 独立测试"""

    @pytest.fixture
    def generator(self):
        return SQLGeneratorNode()

    def test_returns_time_cond_without_filters(self, generator):
        mql = MQLSchema()
        result = generator._build_comparison_period_where("2025-04-01", "2025-04-30", mql)
        assert "FDATE >= '2025-04-01'" in result
        assert "FDATE <= '2025-04-30'" in result

    def test_returns_empty_string_for_empty_dates(self, generator):
        mql = MQLSchema()
        assert generator._build_comparison_period_where("", "", mql) == ""
        assert generator._build_comparison_period_where(None, None, mql) == ""

    def test_includes_dimension_filter(self, generator):
        mql = MQLSchema()
        mql.dimensions = [MQLDimension(type="GROUP_1", value="电子产品")]
        result = generator._build_comparison_period_where("2025-04-01", "2025-04-30", mql)
        assert "GROUP_1" in result
        assert "电子产品" in result


class TestApplyDataFilter:
    """generator.py apply_data_filter() 修复后的行为"""

    @pytest.fixture
    def generator(self):
        from ai.sql_gen.generator import SQLGenerator
        return SQLGenerator.__new__(SQLGenerator)

    def test_adds_dept_id_to_existing_where(self, generator):
        sql = "SELECT * FROM t WHERE FDATE >= '2026-01-01'"
        result = generator.apply_data_filter(sql, dept_id=5)
        assert "dept_id = 5" in result
        assert result.count("WHERE") == 1  # 不产生双 WHERE

    def test_adds_dept_id_without_where(self, generator):
        sql = "SELECT * FROM t"
        result = generator.apply_data_filter(sql, dept_id=5)
        assert "WHERE dept_id = 5" in result
        assert result.count("WHERE") == 1

    def test_blocks_dangerous_data_filter(self, generator):
        sql = "SELECT * FROM t WHERE FDATE >= '2026-01-01'"
        result = generator.apply_data_filter(sql, data_filter="site = 'US'; DROP TABLE t")
        # 危险 filter 被忽略，SQL 原样返回
        assert result == sql

    def test_safe_data_filter_appended(self, generator):
        sql = "SELECT * FROM t WHERE FDATE >= '2026-01-01'"
        result = generator.apply_data_filter(sql, data_filter="site = 'US'")
        assert "(site = 'US')" in result
