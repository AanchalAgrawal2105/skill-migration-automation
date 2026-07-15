"""Command-line entrypoint for the migration pipeline."""

import argparse
from pathlib import Path
import sys
from typing import Optional, Sequence

from app.pipeline import (
    PipelineConfigurationError,
    PipelineExecutionError,
    StageEvent,
    StageStatus,
    run_migration,
)
from app.schemas import MigrationRun


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="refer-migrate",
        description="Run a specification-driven technology migration pipeline.",
    )
    parser.add_argument("--repo", required=True, type=Path, help="Local repository path")
    parser.add_argument("--goal", required=True, help="Plain-English migration goal")
    parser.add_argument("--pack", type=Path, help="Optional YAML knowledge pack")
    parser.add_argument(
        "--stage",
        action="append",
        dest="stages",
        help="Stage package.module:callable; repeat to define execution order",
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        help="Run validated integration fixtures instead of production stages",
    )
    parser.add_argument("--demo-mode", action="store_true", help="Enable explicit demo fallback")
    parser.add_argument(
        "--create-pr",
        action="store_true",
        help="Push the migration branch and open a GitHub PR with gh after verification passes",
    )
    parser.add_argument(
        "--pr-base",
        help="Base branch for --create-pr; defaults to the branch active before migration branch creation",
    )
    parser.add_argument("--json", action="store_true", help="Print final run as JSON")
    return parser


def _render_event(event: StageEvent) -> None:
    marker = {
        StageStatus.STARTED: "→",
        StageStatus.COMPLETED: "✓",
        StageStatus.FAILED: "✗",
    }[event.status]
    message = f"{marker} {event.stage}: {event.status.value}"
    if event.error:
        message += f" — {event.error}"
    print(message, file=sys.stderr)


def _render_summary(run: MigrationRun) -> None:
    print("\nMigration result")
    print(f"  repository: {run.profile.repo_id if run.profile else 'unknown'}")
    print(f"  plan: {run.plan.summary if run.plan else 'not produced'}")
    print(f"  scoped files: {len(run.scope.files_to_change) if run.scope else 0}")
    print(f"  changed files: {len(run.changes)}")
    verified = run.verify.passed if run.verify is not None else False
    print(f"  verified: {'yes' if verified else 'no'}")
    if run.profile:
        print(f"  rollback anchor: {run.profile.rollback_anchor}")
    if run.pr:
        print(f"  branch: {run.pr.branch}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run = run_migration(
            args.repo,
            args.goal,
            pack_path=args.pack,
            demo_mode=args.demo_mode,
            stage_specs=args.stages,
            fixture_dir=args.fixture_dir,
            services={"create_pr": args.create_pr, "pr_base": args.pr_base},
            on_stage=_render_event,
        )
    except (PipelineConfigurationError, PipelineExecutionError) as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        if args.json and isinstance(exc, PipelineExecutionError):
            print(exc.run.model_dump_json(indent=2))
        return 1

    if args.json:
        print(run.model_dump_json(indent=2))
    else:
        _render_summary(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
