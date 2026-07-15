from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.llm import build_llm
from app.packs import load_pack
from app.stages.plan import plan
from app.stages.scope import scope
from app.stages.transform import transform
from tests.contract_fixtures import MigrationPlan, MigrationRun, RepoProfile


ROOT = Path(__file__).resolve().parents[1]


class RoleCIntegrationTests(unittest.TestCase):
    def test_two_data_only_migrations_use_the_same_engine(self) -> None:
        cases = [
            (
                "packs/client-call-upgrade.yaml",
                "Migrate client construction",
                "src/client.py",
                "def build_client():\n    return legacy_client()\n",
                "supported_client",
            ),
            (
                "packs/config-value-upgrade.yaml",
                "Migrate the configuration value",
                "settings.py",
                'mode = "legacy"\n',
                'mode = "current"',
            ),
        ]
        app_before = self._app_snapshot()

        for pack_name, goal, relative, original, expected in cases:
            with self.subTest(pack=pack_name), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory)
                target = repo / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(original, encoding="utf-8")
                run = MigrationRun(
                    goal=goal,
                    repo_path=str(repo),
                    profile=RepoProfile(repo_path=str(repo), files=[relative]),
                )
                knowledge = load_pack(ROOT / pack_name)
                llm = build_llm(
                    demo_mode=True,
                    plan_model=MigrationPlan,
                    pack=knowledge,
                    fixtures_root=ROOT / "tests/fixtures/llm",
                )

                run = plan(run, goal, knowledge, llm)
                run = scope(run, goal, knowledge)
                with patch("app.stages.transform.check_file_syntax", return_value=True):
                    run = transform(run, knowledge, llm)

                self.assertIn(expected, target.read_text(encoding="utf-8"))
                self.assertEqual(len(run.changes), 1)
                self.assertTrue(run.changes[0].syntax_ok)

        self.assertEqual(self._app_snapshot(), app_before)

    @staticmethod
    def _app_snapshot() -> dict[str, bytes]:
        return {
            path.relative_to(ROOT).as_posix(): path.read_bytes()
            for path in sorted((ROOT / "app").rglob("*.py"))
        }


if __name__ == "__main__":
    unittest.main()
