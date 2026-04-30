import unittest
from unittest.mock import MagicMock, patch


class PromptManagerRedisTests(unittest.TestCase):
    def test_prompt_manager_initializes_redis_with_runtime_settings(self):
        fake_client = MagicMock()
        fake_client.ping.return_value = True

        with patch("ai.engine.prompt_manager.get_redis_settings", return_value=("127.0.0.1", 6380, 2)), \
             patch("ai.engine.prompt_manager.redis.Redis", return_value=fake_client):
            from ai.engine.prompt_manager import PromptManager

            PromptManager._redis_client = None
            manager = PromptManager(base_url="http://localhost:18080")

            self.assertIs(manager._redis_client, fake_client)
            fake_client.ping.assert_called_once()

    def test_l2_cache_initializes_redis_with_runtime_settings(self):
        fake_client = MagicMock()
        fake_client.ping.return_value = True

        with patch("ai.engine.llm_v2.cache.get_redis_settings", return_value=("127.0.0.1", 6381, 3)), \
             patch("redis.Redis", return_value=fake_client):
            from ai.engine.llm_v2.cache import L2RedisCache

            cache = L2RedisCache()

            self.assertIs(cache._redis, fake_client)
            fake_client.ping.assert_called_once()


if __name__ == "__main__":
    unittest.main()
