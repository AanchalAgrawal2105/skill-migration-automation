import subprocess
from pathlib import Path

from app.schemas import FileChange, MigrationRun
from app.stages.base import StageContext
from app.stages.profile import run as profile
from app.stages.verify import run as verify
from app.verifiers import check_file_syntax


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _context(repo: Path) -> StageContext:
    return StageContext(repo_path=repo, goal="Test migration")


def _changed_file(path: str) -> FileChange:
    return FileChange(
        file=path,
        original="",
        modified="",
        diff="",
        rationale="Test verification",
        syntax_ok=True,
        kind="auto",
    )


def test_profile_detects_python_repo_and_rollback_anchor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / "requirements.txt").write_text("pytest==8.0.0\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text(
        "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    _init_repo(repo)

    result = profile(MigrationRun(), _context(repo))

    assert result.profile is not None
    assert result.profile.rollback_anchor
    assert "python" in result.profile.languages
    assert result.profile.dependencies["pytest"] == "8.0.0"
    assert result.profile.syntax_cmd["python"]
    assert result.profile.test_cmd
    assert ".git/HEAD" not in result.profile.file_tree


def test_profile_initializes_git_when_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('ready')\n")

    result = profile(MigrationRun(), _context(repo))

    assert result.profile is not None
    assert (repo / ".git").exists()
    assert result.profile.rollback_anchor


def test_verify_runs_syntax_and_tests(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text(
        "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    _init_repo(repo)

    result = profile(MigrationRun(), _context(repo))
    result.changes.append(_changed_file("app.py"))
    result = verify(result, _context(repo))

    assert result.verify is not None
    assert result.verify.passed is True
    assert "syntax:app.py: passed" in result.verify.test_log
    assert "test: passed" in result.verify.test_log


def test_verify_reports_failure_truthfully(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text(
        "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    _init_repo(repo)

    result = profile(MigrationRun(), _context(repo))
    result.changes.append(_changed_file("app.py"))
    result = verify(result, _context(repo))

    assert result.verify is not None
    assert result.verify.passed is False
    assert "test: failed" in result.verify.test_log


def test_config_syntax_verifier_accepts_toml_and_yaml(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    workflow = repo / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "test.yml").write_text("name: Test\njobs: {}\n")
    _init_repo(repo)
    run = profile(MigrationRun(), _context(repo))

    assert check_file_syntax(run, "pyproject.toml").passed
    assert check_file_syntax(run, ".github/workflows/test.yml").passed


def test_config_syntax_verifier_rejects_invalid_toml_and_yaml(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "broken.toml").write_text("name = [\n")
    (repo / "broken.yaml").write_text("name: [\n")
    _init_repo(repo)
    run = profile(MigrationRun(), _context(repo))

    assert not check_file_syntax(run, "broken.toml").passed
    assert not check_file_syntax(run, "broken.yaml").passed
