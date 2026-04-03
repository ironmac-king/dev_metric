"""Mock StarRocks 查询"""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List


class MockStarRocksResult:
    """Mock StarRocks 查询结果"""

    def __init__(self, data: List[Dict], count: int = None):
        self.data = data
        self.count = count or len(data)

    def to_dict(self) -> Dict:
        return {
            "data": self.data,
            "count": self.count
        }


@pytest.fixture
def mock_starrocks_success():
    """Mock StarRocks 成功查询"""
    mock_result = MockStarRocksResult([
        {"date": "2026-04-02", "value": 12345},
        {"date": "2026-04-01", "value": 11234},
    ])
    with patch('ai.sql_gen.generator.SQLGenerator.execute') as mock_execute:
        mock_execute.return_value = mock_result.to_dict()
        yield mock_execute


@pytest.fixture
def mock_starrocks_empty():
    """Mock StarRocks 空结果"""
    mock_result = MockStarRocksResult([])
    with patch('ai.sql_gen.generator.SQLGenerator.execute') as mock_execute:
        mock_execute.return_value = mock_result.to_dict()
        yield mock_execute


@pytest.fixture
def mock_starrocks_error():
    """Mock StarRocks 查询错误"""
    with patch('ai.sql_gen.generator.SQLGenerator.execute') as mock_execute:
        mock_execute.side_effect = Exception("StarRocks connection timeout")
        yield mock_execute
