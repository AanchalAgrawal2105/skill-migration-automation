from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.stages.scope import MAX_SOURCE_BYTES, ScopeError, scope
from tests.contract_fixtures import MigrationPlan, MigrationRun, RepoProfile


def make_run(root: Path, files: list[str], literals: list[str]) -> MigrationRun:
    return MigrationRun(
        goal="Migrate the repository",
        repo_path=str(root),
        profile=RepoProfile(repo_path=str(root), files=files),
        plan=MigrationPlan(
            steps=[{"description": "Update scoped files", "risk": "review"}],
            candidate_literals=literals,
        ),
    )


class ScopeTests(unittest.TestCase):
    def test_pack_and_plan_literals_are_stable_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b.py").write_text("old.call()\n", encoding="utf-8")
            (root / "a.py").write_text("first\nold.call()\n", encoding="utf-8")
            run = make_run(root, ["b.py", "a.py", "a.py"], ["old.call", "old.call"])

            result = scope(
                run,
                run.goal,
                {
                    "detect": {"markers": ["old.call"]},
                    "breaking_changes": [
                        {"pattern": "old.call", "risk": "auto", "fix": "new call"}
                    ],
                },
            )

        assert result.scope is not None
        self.assertEqual(result.scope.files_to_change, ["a.py", "b.py"])
        self.assertEqual(
            [(site.path, site.line, site.match, site.risk) for site in result.scope.sites],
            [("a.py", 2, "old.call", "auto"), ("b.py", 1, "old.call", "auto")],
        )

    def test_packless_scope_uses_plan_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("deprecated.value\n", encoding="utf-8")
            run = make_run(root, ["app.py"], ["deprecated.value"])
            result = scope(run, run.goal, None)

        assert result.scope is not None
        self.assertEqual(result.scope.files_to_change, ["app.py"])
        self.assertEqual(result.scope.sites[0].risk, "review")

    def test_binary_oversized_vendor_and_unmatched_files_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "binary.dat").write_bytes(b"old.call\0")
            (root / "large.py").write_bytes(b"old.call" + b"x" * MAX_SOURCE_BYTES)
            (root / "clean.py").write_text("nothing here\n", encoding="utf-8")
            vendor = root / "node_modules"
            vendor.mkdir()
            (vendor / "dep.py").write_text("old.call\n", encoding="utf-8")
            run = make_run(
                root,
                ["binary.dat", "large.py", "clean.py", "node_modules/dep.py"],
                ["old.call"],
            )
            result = scope(run, run.goal, None)

        assert result.scope is not None
        self.assertEqual(result.scope.files_to_change, [])
        self.assertEqual(result.scope.sites, [])

    def test_profile_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            outside = Path(directory) / "outside.py"
            outside.write_text("old.call\n", encoding="utf-8")
            run = make_run(root, ["../outside.py"], ["old.call"])
            with self.assertRaises(ScopeError):
                scope(run, run.goal, None)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_escaping_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            outside = Path(directory) / "outside.py"
            outside.write_text("old.call\n", encoding="utf-8")
            (root / "link.py").symlink_to(outside)
            run = make_run(root, ["link.py"], ["old.call"])
            with self.assertRaises(ScopeError):
                scope(run, run.goal, None)


if __name__ == "__main__":
    unittest.main()
