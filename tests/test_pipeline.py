from __future__ import annotations

import shutil
from pathlib import Path

from app.pipeline import run_migration


def test_pipeline_runs_pack_driven_demo(tmp_path: Path) -> None:
    source = Path("demo/sample-repo")
    repo = tmp_path / "sample-repo"
    shutil.copytree(source, repo)

    run = run_migration(
        repo_path=repo,
        goal="Rename the old greeting helper to the new helper name",
        pack_path=Path("packs/rename-greeting.yaml"),
    )

    assert not run.errors
    assert run.profile is not None
    assert run.scope is not None
    assert sorted(run.scope.files_to_change) == ["greeting.py", "tests/test_greeting.py"]
    assert len(run.changes) == 2
    assert run.verify is not None
    assert run.verify.passed is True
    assert "legacy_greet" not in (repo / "greeting.py").read_text()
    assert "modern_greet" in (repo / "greeting.py").read_text()

