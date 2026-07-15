import shutil
from pathlib import Path

from app.pipeline import run_migration


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_runs_pack_driven_demo(tmp_path: Path) -> None:
    repo = tmp_path / "sample-repo"
    shutil.copytree(ROOT / "demo" / "sample-repo", repo)

    result = run_migration(
        repo_path=repo,
        goal="Rename the old greeting helper to the new helper name",
        pack_path=ROOT / "packs" / "rename-greeting.yaml",
    )

    assert result.profile is not None
    assert result.scope is not None
    assert sorted(result.scope.files_to_change) == [
        "greeting.py",
        "tests/test_greeting.py",
    ]
    assert len(result.changes) == 2
    assert result.verify is not None and result.verify.passed
    assert result.reports is not None
    assert "legacy_greet" not in (repo / "greeting.py").read_text()
    assert "modern_greet" in (repo / "greeting.py").read_text()
