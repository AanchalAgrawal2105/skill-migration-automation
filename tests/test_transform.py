from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.llm import TransformOutput
from app.stages.transform import SyntaxOutcome, TransformError, transform
from tests.contract_fixtures import (
    MigrationPlan,
    MigrationRun,
    RepoProfile,
    ScopeResult,
    UsageSite,
)


class FakeLLM:
    def __init__(self, modified: str, repair: str | None = None) -> None:
        self.modified = modified
        self.repair = repair
        self.transform_calls = 0
        self.repair_calls = 0
        self.last_pack = None

    def create_plan(self, **kwargs: object) -> MigrationPlan:
        raise AssertionError("not used")

    def transform_file(self, **kwargs: object) -> TransformOutput:
        self.transform_calls += 1
        self.last_pack = kwargs["pack"]
        return TransformOutput(modified=self.modified, rationale="Initial migration")

    def repair_file(self, **kwargs: object) -> TransformOutput:
        self.repair_calls += 1
        if self.repair is None:
            raise RuntimeError("no repair fixture")
        return TransformOutput(modified=self.repair, rationale="Fixed syntax")


def make_run(root: Path, files: list[str], sites: list[UsageSite]) -> MigrationRun:
    return MigrationRun(
        goal="Migrate the call",
        repo_path=str(root),
        profile=RepoProfile(repo_path=str(root), files=files),
        plan=MigrationPlan(
            steps=[{"description": "Update", "risk": "review"}],
            candidate_literals=["old.call"],
        ),
        scope=ScopeResult(sites=sites, files_to_change=files),
    )


class TransformTests(unittest.TestCase):
    def test_success_changes_only_scoped_file_and_preserves_crlf_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "app.py"
            target.write_bytes(b"old.call()\r\n")
            target.chmod(0o744)
            unrelated = root / "other.py"
            unrelated.write_text("leave me\n", encoding="utf-8")
            site = UsageSite(path="app.py", line=1, match="old.call", risk="auto")
            run = make_run(root, ["app.py"], [site])
            llm = FakeLLM("new.call()\n")

            with patch("app.stages.transform.check_file_syntax", return_value=True):
                result = transform(
                    run,
                    {
                        "breaking_changes": [
                            {"pattern": "old.call", "risk": "auto", "fix": "new.call"}
                        ]
                    },
                    llm,
                )

            self.assertEqual(target.read_bytes(), b"new.call()\r\n")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o744)
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "leave me\n")

        self.assertEqual(len(result.changes), 1)
        self.assertTrue(result.changes[0].syntax_ok)
        self.assertEqual(result.changes[0].kind, "auto")
        self.assertIn("-old.call()", result.changes[0].diff)
        self.assertIn("+new.call()", result.changes[0].diff)
        self.assertEqual(llm.last_pack["breaking_changes"][0]["pattern"], "old.call")

    def test_unchanged_output_is_manual_without_syntax_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "app.py"
            target.write_text("old.call()\n", encoding="utf-8")
            run = make_run(
                root,
                ["app.py"],
                [UsageSite(path="app.py", line=1, match="old.call", risk="review")],
            )
            checker = unittest.mock.Mock(return_value=True)
            with patch("app.stages.transform.check_file_syntax", checker):
                result = transform(run, None, FakeLLM("old.call()\n"))

        checker.assert_not_called()
        self.assertEqual(result.changes[0].kind, "manual")
        self.assertFalse(result.changes[0].syntax_ok)
        self.assertEqual(result.changes[0].diff, "")

    def test_one_repair_can_recover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "app.py"
            target.write_text("old.call()\n", encoding="utf-8")
            run = make_run(
                root,
                ["app.py"],
                [UsageSite(path="app.py", line=1, match="old.call", risk="review")],
            )
            llm = FakeLLM("new.call(\n", repair="new.call()\n")
            outcomes = [SyntaxOutcome(False, "invalid syntax"), SyntaxOutcome(True, "")]
            with patch("app.stages.transform.check_file_syntax", side_effect=outcomes):
                result = transform(run, None, llm)

            self.assertEqual(target.read_text(encoding="utf-8"), "new.call()\n")

        self.assertEqual(llm.repair_calls, 1)
        self.assertTrue(result.changes[0].syntax_ok)
        self.assertIn("Repair:", result.changes[0].rationale)

    def test_failed_repair_restores_original_and_keeps_attempted_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "app.py"
            original = "old.call()\n"
            target.write_text(original, encoding="utf-8")
            run = make_run(
                root,
                ["app.py"],
                [UsageSite(path="app.py", line=1, match="old.call", risk="review")],
            )
            llm = FakeLLM("new.call(\n", repair="new.call))\n")
            outcomes = [SyntaxOutcome(False, "first failure"), SyntaxOutcome(False, "second failure")]
            with patch("app.stages.transform.check_file_syntax", side_effect=outcomes):
                result = transform(run, None, llm)

            self.assertEqual(target.read_text(encoding="utf-8"), original)

        self.assertEqual(llm.repair_calls, 1)
        change = result.changes[0]
        self.assertFalse(change.syntax_ok)
        self.assertEqual(change.kind, "manual")
        self.assertIn("+new.call))", change.diff)
        self.assertEqual(change.syntax_error, "second failure")

    def test_model_failure_restores_candidate_and_records_manual(self) -> None:
        class FailingLLM(FakeLLM):
            def transform_file(self, **kwargs: object) -> TransformOutput:
                raise RuntimeError("provider unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "app.py"
            target.write_text("old.call()\n", encoding="utf-8")
            run = make_run(root, ["app.py"], [])
            result = transform(run, None, FailingLLM("unused"))
            self.assertEqual(target.read_text(encoding="utf-8"), "old.call()\n")

        self.assertEqual(result.changes[0].kind, "manual")
        self.assertIn("provider unavailable", result.changes[0].syntax_error)

    def test_target_escape_is_rejected_before_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            outside = Path(directory) / "outside.py"
            outside.write_text("old.call()\n", encoding="utf-8")
            run = make_run(root, ["../outside.py"], [])
            llm = FakeLLM("new.call()\n")
            with self.assertRaises(TransformError):
                transform(run, None, llm)
            self.assertEqual(llm.transform_calls, 0)


if __name__ == "__main__":
    unittest.main()
