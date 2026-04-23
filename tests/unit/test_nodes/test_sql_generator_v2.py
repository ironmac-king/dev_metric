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
        assert generator._sanitize_value("'; DROP TABLE users;--") == "'' OR ''1''=''1"
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
        assert "IDS_AMZ_DI" in sql

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
        assert "current_val" in sql
        assert "compare_val" in sql
        assert "change_rate" in sql
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
        assert "current_val" in sql
        assert "compare_val" in sql


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
