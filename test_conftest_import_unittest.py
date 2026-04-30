import subprocess
import sys
import unittest


class ConftestImportTests(unittest.TestCase):
    def test_conftest_import_does_not_require_optional_engines(self):
        result = subprocess.run(
            [sys.executable, "-c", "import tests.conftest; print('ok')"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
