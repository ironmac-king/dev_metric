import os
import asyncio
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class RuntimeConfigTests(unittest.TestCase):
    def test_get_postgres_settings_falls_back_to_config_yaml(self):
        config_text = textwrap.dedent(
            """
            database:
              host: 10.0.0.9
              port: 5433
              user: pguser
              password: pgpass
              name: pgdb
            """
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.yaml"
            cfg.write_text(config_text, encoding="utf-8")

            env = {
                "PG_HOST": "",
                "PG_PORT": "",
                "PG_USER": "",
                "PG_PASSWORD": "",
                "PG_DATABASE": "",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("ai.config.runtime._PROJECT_ROOT", Path(tmpdir)):
                    from ai.config.runtime import get_postgres_settings

                    self.assertEqual(
                        get_postgres_settings(),
                        ("10.0.0.9", 5433, "pguser", "pgpass", "pgdb"),
                    )

    def test_sql_executor_uses_runtime_go_api_base(self):
        from ai.engine.llm_v2.nodes.sql_executor import SQLExecutor

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0, "data": {"data": [], "columns": [], "count": 0}}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch.dict(os.environ, {"GO_API_BASE": "http://runtime-host:19999"}, clear=False):
            with patch("httpx.AsyncClient", return_value=mock_client):
                asyncio.run(SQLExecutor()._execute_via_go_api("SELECT 1"))

        called_url = mock_client.post.await_args.args[0]
        self.assertEqual(called_url, "http://runtime-host:19999/api/v1/query/execute")

    def test_volatility_analyzer_uses_runtime_go_api_base(self):
        with patch("ai.engine.llm_v2.nodes.volatility_analyzer.get_llm_engine", return_value=MagicMock()):
            from ai.engine.llm_v2.nodes.volatility_analyzer import VolatilityAnalyzer

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": 0,
                "data": {"data": [{"prev_val": "12.5"}], "columns": ["prev_val"], "count": 1},
            }
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            with patch.dict(os.environ, {"GO_API_BASE": "http://runtime-host:19999"}, clear=False):
                with patch("httpx.AsyncClient", return_value=mock_client):
                    asyncio.run(VolatilityAnalyzer()._query_starrocks_sum("SELECT 1"))

        called_url = mock_client.post.await_args.args[0]
        self.assertEqual(called_url, "http://runtime-host:19999/api/v1/query/execute")

    def test_report_generator_uses_runtime_go_api_base(self):
        with patch("ai.engine.llm_v2.nodes.report_generator.get_prompt_manager", return_value=MagicMock()):
            with patch("ai.engine.llm_v2.nodes.report_generator.get_llm_engine", return_value=MagicMock()):
                from ai.engine.llm_v2.nodes.report_generator import ReportGeneratorNode

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"data": []}
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                with patch.dict(os.environ, {"GO_API_BASE": "http://runtime-host:19999"}, clear=False):
                    with patch("httpx.AsyncClient", return_value=mock_client):
                        asyncio.run(ReportGeneratorNode()._load_drilldown_templates("sales"))

        called_url = mock_client.get.await_args.args[0]
        self.assertEqual(called_url, "http://runtime-host:19999/api/v1/nlp/sql-templates")

    def test_local_intent_model_uses_runtime_go_api_base(self):
        from ai.engine.llm_v2.nodes.local_intent_model import LocalJointIntentModel

        fake_dimension_service = MagicMock()
        fake_dimension_service.get_all_types.return_value = []
        fake_dimension_service.get_by_column_name.return_value = []

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}

        model = LocalJointIntentModel.__new__(LocalJointIntentModel)

        with patch.dict(os.environ, {"GO_API_BASE": "http://runtime-host:19999"}, clear=False):
            with patch("httpx.get", return_value=mock_response) as mock_get:
                with patch("ai.engine.llm_v2.nodes.local_intent_model.DimensionService", return_value=fake_dimension_service):
                    model._build_rule_dict()

        called_url = mock_get.call_args.args[0]
        self.assertEqual(called_url, "http://runtime-host:19999/api/v1/metadata/terms")


if __name__ == "__main__":
    unittest.main()
