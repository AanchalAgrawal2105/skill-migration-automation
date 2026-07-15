from __future__ import annotations

from pathlib import Path

from app.schemas import MigrationRun


def ingest(run: MigrationRun, repo_path: Path | None = None) -> MigrationRun:
    root = (repo_path or run.repo_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {root}")
    run.repo_path = root
    return run

