from __future__ import annotations

from pathlib import Path

from app.schemas import CommandResult, CommandSpec, MigrationRun, VerifyResult
from app.verifiers import CommandRunner


def verify(run: MigrationRun, runner: CommandRunner | None = None) -> MigrationRun:
    if run.profile is None:
        raise ValueError("Cannot verify before repository profile exists")

    repo_root = Path(run.profile.repo_path)
    command_runner = runner or CommandRunner(repo_root=repo_root)
    commands = _commands_for_run(run)
    results: list[CommandResult] = []
    notes: list[str] = []

    if not commands:
        notes.append("No deterministic verification commands were detected.")

    for command in commands:
        results.append(command_runner.run(command))

    run.verify = VerifyResult(
        passed=bool(results) and all(result.passed for result in results),
        commands=results,
        coverage_notes=notes,
    )
    return run


def _commands_for_run(run: MigrationRun) -> list[CommandSpec]:
    assert run.profile is not None

    commands: list[CommandSpec] = []
    changed_paths = [change.path for change in run.changes if change.kind != "skipped"]
    for path in changed_paths:
        command = run.profile.syntax_commands.get(path)
        if command:
            commands.append(command)

    commands.extend(run.profile.test_commands)
    return _dedupe_commands(commands)


def _dedupe_commands(commands: list[CommandSpec]) -> list[CommandSpec]:
    seen: set[tuple[tuple[str, ...], str | None]] = set()
    deduped: list[CommandSpec] = []
    for command in commands:
        key = (tuple(command.argv), command.cwd)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(command)
    return deduped

