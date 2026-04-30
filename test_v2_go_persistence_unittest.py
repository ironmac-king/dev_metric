import unittest
from unittest.mock import AsyncMock, patch

from ai.engine.llm_v2.router import _save_v2_session_to_go
from ai.engine.llm_v2.schema import MQLIntent, MQLMetric, MQLSchema, SQLResult, TimeRange, TimeType, V2State, create_v2_state


class V2GoPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_v2_session_to_go_calls_internal_go_endpoint(self):
        state = create_v2_state(session_id="persist-1", user_id="u1", question="销售额")
        state.answer = "销售额为 100"
        state.sql = 'SELECT 100 AS "销售额"'
        state.mql = MQLSchema(
            intent=MQLIntent.QUERY_VALUE,
            metric=MQLMetric(code="M1", name="销售额"),
            time=TimeRange(type=TimeType.RELATIVE, original="本月"),
        )
        state.sql_result = SQLResult(sql=state.sql, data=[{"销售额": 100}], columns=["销售额"], total=1)

        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("ai.engine.llm_v2.router.httpx.AsyncClient", return_value=mock_client):
            await _save_v2_session_to_go(
                session_id="persist-1",
                user_id="u1",
                question="销售额",
                result_state=state,
            )

        mock_client.post.assert_awaited_once()
        called_url = mock_client.post.await_args.args[0]
        payload = mock_client.post.await_args.kwargs["json"]
        self.assertTrue(called_url.endswith("/api/v1/internal/ask/v2-session"))
        self.assertEqual(payload["session_id"], "persist-1")
        self.assertEqual(payload["user_id"], "u1")
        self.assertEqual(payload["question"], "销售额")
        self.assertEqual(payload["answer"], "销售额为 100")


if __name__ == "__main__":
    unittest.main()
