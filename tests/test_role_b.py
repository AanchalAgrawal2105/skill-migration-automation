from __future__ import annotations

import subprocess
from pathlib import Path

from app.schemas import ChangeKind, FileChange, MigrationRun
from app.stages.profile import profile
from app.stages.verify import verify


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True, text=True)


def test_profile_detects_python_repo_and_rollback_anchor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / "requirements.txt").write_text("pytest==8.0.0\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    _init_repo(repo)

    run = profile(MigrationRun(repo_path=repo))

    assert run.profile is not None
    assert run.profile.rollback_anchor
    assert "python" in run.profile.languages
    assert run.profile.dependencies["pytest"] == "8.0.0"
    assert "app.py" in run.profile.syntax_commands
    assert run.profile.test_commands
    assert ".git/HEAD" not in run.profile.files


def test_profile_initializes_git_when_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('ready')\n")

    run = profile(MigrationRun(repo_path=repo))

    assert run.profile is not None
    assert (repo / ".git").exists()
    assert run.profile.rollback_anchor


def test_verify_runs_syntax_and_tests(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    _init_repo(repo)

    run = profile(MigrationRun(repo_path=repo))
    run.changes.append(FileChange(path="app.py", kind=ChangeKind.auto, syntax_ok=True))
    run = verify(run)

    assert run.verify is not None
    assert run.verify.passed is True
    assert len(run.verify.commands) == 2
    assert all(command.passed for command in run.verify.commands)


def test_verify_reports_failure_truthfully(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    _init_repo(repo)

    run = profile(MigrationRun(repo_path=repo))
    run.changes.append(FileChange(path="app.py", kind=ChangeKind.auto, syntax_ok=True))
    run = verify(run)

    assert run.verify is not None
    assert run.verify.passed is False
    assert any(not command.passed for command in run.verify.commands)
