from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.pack_loader import load_pack
from app.schemas import MigrationRun
from app.stages.ingest import ingest
from app.stages.plan import plan
from app.stages.profile import profile
from app.stages.report import report
from app.stages.scope import scope
from app.stages.transform import transform
from app.stages.verify import verify


StageCallback = Callable[[str, str, MigrationRun], None]


def run_migration(
    repo_path: Path,
    goal: str,
    pack_path: Path | None = None,
    on_stage: StageCallback | None = None,
) -> MigrationRun:
    pack = load_pack(pack_path)
    run = MigrationRun(repo_path=repo_path, goal=goal)

    for name, stage in (
        ("ingest", lambda current: ingest(current, repo_path)),
        ("profile", lambda current: profile(current, repo_path)),
        ("plan", lambda current: plan(current, goal, pack)),
        ("scope", lambda current: scope(current, goal, pack)),
        ("transform", lambda current: transform(current, pack)),
        ("verify", verify),
        ("report", report),
    ):
        _emit(on_stage, name, "started", run)
        try:
            run = stage(run)
        except Exception as exc:
            run.errors.append(f"{name}: {exc}")
            _emit(on_stage, name, "failed", run)
            return run
        _emit(on_stage, name, "completed", run)

        if name == "scope" and run.scope is not None and not run.scope.files_to_change:
            run.errors.append("scope: no files matched the supplied goal or pack")
            return report(run)

    return run


def _emit(callback: StageCallback | None, name: str, status: str, run: MigrationRun) -> None:
    if callback:
        callback(name, status, run)

