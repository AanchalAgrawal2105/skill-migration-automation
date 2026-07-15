from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GenericityTests(unittest.TestCase):
    def test_demo_migration_literals_are_not_hardcoded_in_engine(self) -> None:
        forbidden = ("legacy_client(", "supported_client(", 'mode = "legacy"', 'mode = "current"')
        app_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "app").rglob("*.py"))
        )
        for literal in forbidden:
            self.assertNotIn(literal, app_text)


if __name__ == "__main__":
    unittest.main()
