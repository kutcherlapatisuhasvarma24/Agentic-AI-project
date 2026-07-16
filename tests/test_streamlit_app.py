import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class StreamlitAppTests(unittest.TestCase):
    def test_app_module_imports(self):
        module = importlib.import_module("app")
        self.assertTrue(hasattr(module, "render_app"))


if __name__ == "__main__":
    unittest.main()
