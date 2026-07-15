from __future__ import annotations

import argparse
from pathlib import Path

from app.pipeline import run_migration
from app.schemas import MigrationRun


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local migration demo.")
    parser.add_argument("--repo", required=True, type=Path, help="Local repository path to migrate")
    parser.add_argument("--goal", required=True, help="Plain-English migration goal")
    parser.add_argument("--pack", type=Path, help="Optional YAML knowledge pack")
    args = parser.parse_args()

    run = run_migration(args.repo, args.goal, args.pack, on_stage=_stage_event)
    _print_run(run)
    return 0 if run.verify and run.verify.passed and not run.errors else 1


def _stage_event(name: str, status: str, run: MigrationRun) -> None:
    print(f"[{status}] {name}")


def _print_run(run: MigrationRun) -> None:
    print("\n== Result ==")
    if run.profile:
        print(f"Rollback anchor: {run.profile.rollback_anchor}")
        print(f"Languages: {', '.join(run.profile.languages) or 'none'}")
    if run.plan:
        print(f"Plan: {run.plan.summary}")
    if run.scope:
        print(f"Files scoped: {len(run.scope.files_to_change)}")
    for change in run.changes:
        print(f"\n-- {change.path} [{change.kind}] --")
        print(change.rationale)
        if change.diff:
            print(change.diff)
    if run.verify:
        print(f"\nVerification passed: {run.verify.passed}")
        for command in run.verify.commands:
            print(f"$ {' '.join(command.command)} -> {command.returncode}")
            if command.stdout:
                print(command.stdout.strip())
            if command.stderr:
                print(command.stderr.strip())
    if run.errors:
        print("\nErrors:")
        for error in run.errors:
            print(f"- {error}")


if __name__ == "__main__":
    raise SystemExit(main())

