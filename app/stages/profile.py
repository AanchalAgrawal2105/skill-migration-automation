from __future__ import annotations

import subprocess
from pathlib import Path

from app.schemas import CommandSpec, MigrationRun, RepoProfile
from app.verifiers import VENDORED_DIRS, is_probably_text, python_syntax_command, pytest_command


MAX_FILE_BYTES = 250_000


def profile(run: MigrationRun, repo_path: Path | None = None) -> MigrationRun:
    root = (repo_path or run.repo_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {root}")

    rollback_anchor = _ensure_git_anchor(root)
    files = _walk_repo(root)
    languages = _detect_languages(files)
    manifests = _read_manifests(root)
    dependencies = _python_dependencies(manifests)
    syntax_commands = _syntax_commands(files)
    test_commands = _test_commands(root, files)

    run.repo_path = root
    run.profile = RepoProfile(
        repo_path=str(root),
        rollback_anchor=rollback_anchor,
        languages=languages,
        files=files,
        manifests=manifests,
        dependencies=dependencies,
        syntax_commands=syntax_commands,
        test_commands=test_commands,
    )
    return run


def _ensure_git_anchor(root: Path) -> str:
    if not (root / ".git").exists():
        _git(root, ["init"])
        _ensure_git_identity(root)
        _git(root, ["add", "."])
        _git(root, ["commit", "-m", "Baseline before migration"])

    head = _git(root, ["rev-parse", "HEAD"], allow_failure=True)
    if head.returncode == 0:
        return head.stdout.strip()

    _ensure_git_identity(root)
    _git(root, ["add", "."])
    _git(root, ["commit", "-m", "Baseline before migration"])
    return _git(root, ["rev-parse", "HEAD"]).stdout.strip()


def _ensure_git_identity(root: Path) -> None:
    email = _git(root, ["config", "user.email"], allow_failure=True)
    name = _git(root, ["config", "user.name"], allow_failure=True)
    if email.returncode != 0 or not email.stdout.strip():
        _git(root, ["config", "user.email", "refer-demo@example.com"])
    if name.returncode != 0 or not name.stdout.strip():
        _git(root, ["config", "user.name", "Refer Demo"])


def _git(root: Path, args: list[str], allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 and not allow_failure:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return completed


def _walk_repo(root: Path) -> list[str]:
    files: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in VENDORED_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        if not is_probably_text(path):
            continue
        files.append(relative.as_posix())
    return sorted(files)


def _detect_languages(files: list[str]) -> list[str]:
    languages: set[str] = set()
    if any(path.endswith(".py") for path in files):
        languages.add("python")
    if any(path.endswith((".js", ".jsx", ".mjs", ".cjs")) for path in files):
        languages.add("javascript")
    if any(path.endswith((".ts", ".tsx")) for path in files):
        languages.add("typescript")
    return sorted(languages)


def _read_manifests(root: Path) -> dict[str, object]:
    manifests: dict[str, object] = {}
    requirements = root / "requirements.txt"
    if requirements.exists() and requirements.is_file():
        manifests["requirements.txt"] = requirements.read_text(errors="replace").splitlines()

    pyproject = root / "pyproject.toml"
    if pyproject.exists() and pyproject.is_file():
        manifests["pyproject.toml"] = pyproject.read_text(errors="replace")

    return manifests


def _python_dependencies(manifests: dict[str, object]) -> dict[str, str]:
    dependencies: dict[str, str] = {}
    for line in manifests.get("requirements.txt", []):
        if not isinstance(line, str):
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, sep, version = stripped.partition("==")
        dependencies[name.strip()] = version.strip() if sep else ""
    return dependencies


def _syntax_commands(files: list[str]) -> dict[str, CommandSpec]:
    return {path: python_syntax_command(path) for path in files if path.endswith(".py")}


def _test_commands(root: Path, files: list[str]) -> list[CommandSpec]:
    has_pytest_config = any(
        (root / name).exists()
        for name in ("pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml")
    )
    has_tests = any(path.startswith("tests/") and path.endswith(".py") for path in files)
    return [pytest_command()] if has_pytest_config or has_tests else []
