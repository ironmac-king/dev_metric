"""Mock Go 后端 API"""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional


class MockGoAPIClient:
    """Mock Go 后端 API 客户端"""

    def __init__(self):
        self.metrics = {
            "MKI-02-0001": {
                "id": 1,
                "metric_code": "MKI-02-0001",
                "name": "访客数",
                "name_en": "visitors",
                "unit": "人",
                "domain": "营销域",
                "starrocks_sql": "SELECT date, SUM(sessions_total) as value FROM metric_data WHERE metric_id = 1 GROUP BY date",
                "business_rule": "统计所有渠道的独立访客数",
                "technical_rule": "COUNT(DISTINCT visitor_id)",
            },
            "MKI-01-0001": {
                "id": 2,
                "metric_code": "MKI-01-0001",
                "name": "销售额",
                "name_en": "sales",
                "unit": "元",
                "domain": "营销域",
                "starrocks_sql": "SELECT date, SUM(sales_amount) as value FROM metric_data WHERE metric_id = 2 GROUP BY date",
                "business_rule": "包含退款的全站销售额",
                "technical_rule": "SUM(order_amount)",
            },
        }
        self.intent_templates = []
        self.sql_templates = {}
        self.dimensions = {}

    def get_metric(self, metric_code: str) -> Optional[Dict]:
        return self.metrics.get(metric_code)

    def get_all_metrics(self) -> list:
        return list(self.metrics.values())

    def get_intent_templates(self) -> list:
        return self.intent_templates

    def get_sql_templates(self) -> Dict:
        return self.sql_templates


@pytest.fixture
def mock_go_api():
    """Mock Go API fixture"""
    mock_client = MockGoAPIClient()
    with patch('ai.client.metric_client.MetricClient') as mock:
        instance = mock.return_value
        instance.get_metric = Mock(side_effect=mock_client.get_metric)
        instance.get_all_metrics = Mock(return_value=mock_client.get_all_metrics())
        instance.get_intent_templates = Mock(return_value=mock_client.get_intent_templates())
        instance.get_sql_templates = Mock(return_value=mock_client.get_sql_templates())
        yield instance
