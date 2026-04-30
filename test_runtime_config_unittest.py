import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


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


if __name__ == "__main__":
    unittest.main()
