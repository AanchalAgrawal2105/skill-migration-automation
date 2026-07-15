from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from app.schemas import ChangeKind, FileChange, MigrationRun
from app.verifiers import CommandRunner


def transform(run: MigrationRun, pack: dict[str, Any] | None, runner: CommandRunner | None = None) -> MigrationRun:
    if run.profile is None:
        raise ValueError("Cannot transform before repository profile exists")
    if run.scope is None:
        raise ValueError("Cannot transform before scope exists")

    replacements = _replacements_from_pack(pack)
    repo_root = Path(run.profile.repo_path)
    command_runner = runner or CommandRunner(repo_root=repo_root)

    for relative_path in run.scope.files_to_change:
        target = (repo_root / relative_path).resolve()
        if repo_root.resolve() not in target.parents and target != repo_root.resolve():
            raise ValueError(f"Scoped file escapes repository: {relative_path}")

        original = target.read_text(encoding="utf-8", errors="replace")
        modified = _apply_replacements(original, replacements)
        if modified == original:
            run.changes.append(
                FileChange(
                    path=relative_path,
                    kind=ChangeKind.skipped,
                    rationale="No pack replacement changed this file.",
                    diff="",
                    syntax_ok=None,
                )
            )
            continue

        target.write_text(modified, encoding="utf-8")
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            )
        )

        syntax_ok = None
        syntax_command = run.profile.syntax_commands.get(relative_path)
        if syntax_command is not None:
            syntax_result = command_runner.run(syntax_command)
            syntax_ok = syntax_result.passed
            if not syntax_result.passed:
                target.write_text(original, encoding="utf-8")
                run.changes.append(
                    FileChange(
                        path=relative_path,
                        kind=ChangeKind.manual,
                        rationale="Candidate transform failed syntax verification and was restored.",
                        diff=diff,
                        syntax_ok=False,
                    )
                )
                continue

        run.changes.append(
            FileChange(
                path=relative_path,
                kind=ChangeKind.auto,
                rationale="Applied pack-provided literal replacements.",
                diff=diff,
                syntax_ok=syntax_ok,
            )
        )

    return run


def _replacements_from_pack(pack: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not pack:
        return []
    transform_config = pack.get("transform")
    if not isinstance(transform_config, dict):
        return []

    replacements: list[tuple[str, str]] = []
    for item in transform_config.get("replacements", []):
        if not isinstance(item, dict):
            continue
        old = item.get("old")
        new = item.get("new")
        if old is None or new is None:
            continue
        replacements.append((str(old), str(new)))
    return replacements


def _apply_replacements(content: str, replacements: list[tuple[str, str]]) -> str:
    modified = content
    for old, new in replacements:
        modified = modified.replace(old, new)
    return modified

