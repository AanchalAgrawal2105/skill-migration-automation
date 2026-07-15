"""Run deterministic syntax, build, and test verification."""

from pathlib import Path
from typing import List

from app.schemas import MigrationRun, VerifyResult
from app.stages.base import StageContext
from app.verifiers import CommandResult, CommandRunner


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    if migration.profile is None:
        raise ValueError("Cannot verify before repository profile exists")
    runner = context.services.get("command_runner") or CommandRunner(
        Path(migration.profile.root_path)
    )
    build_results = []
    test_results = []
    failed_files = []

    for change in migration.changes:
        language = _language_for(change.file)
        template = migration.profile.syntax_cmd.get(language) if language else None
        if not template:
            continue
        result = runner.run(template.format(file=change.file), timeout_seconds=30)
        test_results.append((f"syntax:{change.file}", result))
        if not result.passed:
            failed_files.append(change.file)

    if migration.profile.build_cmd:
        build_results.append(
            ("build", runner.run(migration.profile.build_cmd, timeout_seconds=120))
        )
    if migration.profile.test_cmd:
        test_results.append(
            ("test", runner.run(migration.profile.test_cmd, timeout_seconds=120))
        )

    all_results = [result for _, result in build_results + test_results]
    passed = bool(all_results) and all(result.passed for result in all_results)
    updated = migration.model_copy(deep=True)
    updated.verify = VerifyResult(
        passed=passed,
        build_log=_format_logs(build_results) or "No build command detected.",
        test_log=_format_logs(test_results) or "No syntax or test command detected.",
        failed_files=sorted(set(failed_files)),
    )
    return updated


def _language_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
    }.get(suffix, "")


def _format_logs(results: List[tuple]) -> str:
    blocks = []
    for label, result in results:
        status = "passed" if result.passed else "failed"
        command = " ".join(result.command)
        output = "\n".join(value for value in (result.stdout, result.stderr) if value).strip()
        blocks.append(f"$ {command}\n[{label}: {status}]" + (f"\n{output}" if output else ""))
    return "\n\n".join(blocks)

