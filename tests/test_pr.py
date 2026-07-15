from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from app.schemas import FileChange, MigrationRun, PRResult, RepoProfile, Reports, VerifyResult
from app.stages.base import StageContext
from app.stages.pr import PRStageError, run as pr_stage


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "app.py").write_text("def old():\n    return 1\n", encoding="utf-8")
    _git(root, "add", "app.py")
    _git(root, "commit", "-m", "initial")


def _migration(root: Path, *, passed: bool = True) -> MigrationRun:
    return MigrationRun(
        profile=RepoProfile(
            repo_id=root.name,
            root_path=str(root),
            rollback_anchor="0" * 40,
            languages=["python"],
            manifests={},
            dependencies={},
            build_cmd=None,
            test_cmd="python3 -m pytest -q",
            syntax_cmd={"python": "python3 -m py_compile {file}"},
            file_tree=["app.py"],
        ),
        changes=[
            FileChange(
                file="app.py",
                original="def old():\n    return 1\n",
                modified="def new():\n    return 1\n",
                diff="diff",
                rationale="Rename helper",
                syntax_ok=True,
                kind="auto",
            )
        ],
        verify=VerifyResult(
            passed=passed,
            build_log="No build command detected.",
            test_log="tests passed" if passed else "tests failed",
            failed_files=[] if passed else ["app.py"],
        ),
        reports=Reports(
            migration_docs="# Migration\n\nRename helper.",
            risk_report="| File | Kind | Syntax |\n|---|---|---|",
            rollback_plan="# Rollback",
        ),
    )


def _context(root: Path, **services: object) -> StageContext:
    return StageContext(
        repo_path=root,
        goal="Rename old helper to new helper",
        services=services,
    )


def test_pr_stage_creates_local_branch_and_commit_without_push(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "app.py").write_text("def new():\n    return 1\n", encoding="utf-8")

    result = pr_stage(_migration(repo), _context(repo))

    assert isinstance(result.pr, PRResult)
    assert result.pr.branch.startswith("migrate/rename-old-helper")
    assert result.pr.pr_url is None
    assert result.pr.committed is True
    assert _git(repo, "branch", "--show-current").stdout.strip() == result.pr.branch
    assert _git(repo, "log", "-1", "--pretty=%s").stdout.strip().startswith("Apply migration:")
    assert _git(repo, "status", "--short").stdout == ""


def test_pr_stage_refuses_failed_verification(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "app.py").write_text("def new():\n    return 1\n", encoding="utf-8")

    with pytest.raises(PRStageError, match="verification did not pass"):
        pr_stage(_migration(repo, passed=False), _context(repo))


def test_pr_stage_pushes_and_creates_github_pr_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", remote], check=True, capture_output=True, text=True)

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-u", "origin", "main")
    (repo / "app.py").write_text("def new():\n    return 1\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_log = tmp_path / "gh-args.txt"
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" > {gh_log}\n"
        "printf '%s\\n' 'https://github.com/example/repo/pull/1'\n",
        encoding="utf-8",
    )
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    result = pr_stage(_migration(repo), _context(repo, create_pr=True, pr_base="main"))

    assert result.pr is not None
    assert result.pr.pr_url == "https://github.com/example/repo/pull/1"
    assert result.pr.committed is True
    assert result.pr.branch in _git(remote, "branch", "--list").stdout
    assert "pr create --base main --head" in gh_log.read_text(encoding="utf-8")

