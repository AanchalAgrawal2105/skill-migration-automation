"""Deterministically profile repository languages, manifests, and commands."""

import json
from pathlib import Path
import subprocess
from typing import Dict, List, Optional

from app.schemas import MigrationRun, RepoProfile
from app.stages.base import StageContext
from app.verifiers import MAX_LOG_CHARS, VENDORED_DIRS, VERIFIERS, is_probably_text


MAX_FILE_BYTES = 250_000
MANIFEST_NAMES = ("requirements.txt", "pyproject.toml", "package.json", "pom.xml", "go.mod")


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    root = context.repo_path.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Repository path is not a directory: {root}")

    files = _walk_repo(root)
    languages = _detect_languages(files)
    manifests = _read_manifests(root)
    dependencies = _dependencies(manifests)
    build_cmd, test_cmd = _commands(root, files, languages, manifests)
    syntax_cmd = {
        language: VERIFIERS[language]["syntax"]
        for language in languages
        if language in VERIFIERS
    }

    updated = migration.model_copy(deep=True)
    updated.profile = RepoProfile(
        repo_id=root.name,
        root_path=str(root),
        rollback_anchor=_ensure_git_anchor(root),
        languages=languages,
        manifests=manifests,
        dependencies=dependencies,
        build_cmd=build_cmd,
        test_cmd=test_cmd,
        syntax_cmd=syntax_cmd,
        file_tree=files,
    )
    return updated


def _ensure_git_anchor(root: Path) -> str:
    if not (root / ".git").exists():
        _git(root, ["init"])
    head = _git(root, ["rev-parse", "HEAD"], allow_failure=True)
    if head.returncode == 0:
        return head.stdout.strip()
    _ensure_git_identity(root)
    _git(root, ["add", "."])
    _git(root, ["commit", "-m", "Baseline before migration"])
    return _git(root, ["rev-parse", "HEAD"]).stdout.strip()


def _ensure_git_identity(root: Path) -> None:
    if _git(root, ["config", "user.email"], allow_failure=True).returncode != 0:
        _git(root, ["config", "user.email", "refer-demo@example.invalid"])
    if _git(root, ["config", "user.name"], allow_failure=True).returncode != 0:
        _git(root, ["config", "user.name", "Refer Migration Agent"])


def _git(
    root: Path, args: List[str], *, allow_failure: bool = False
) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        ["git"] + args, cwd=root, text=True, capture_output=True, check=False
    )
    if completed.returncode != 0 and not allow_failure:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail[:MAX_LOG_CHARS]}")
    return completed


def _walk_repo(root: Path) -> List[str]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in VENDORED_DIRS for part in relative.parts):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        if is_probably_text(path):
            files.append(relative.as_posix())
    return sorted(files)


def _detect_languages(files: List[str]) -> List[str]:
    suffixes = {
        "python": (".py",),
        "javascript": (".js", ".jsx", ".mjs", ".cjs"),
        "typescript": (".ts", ".tsx"),
        "go": (".go",),
        "java": (".java",),
    }
    return sorted(
        language
        for language, endings in suffixes.items()
        if any(path.endswith(endings) for path in files)
    )


def _read_manifests(root: Path) -> Dict[str, str]:
    manifests = {}
    for name in MANIFEST_NAMES:
        path = root / name
        if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
            manifests[name] = path.read_text(encoding="utf-8", errors="replace")
    return manifests


def _dependencies(manifests: Dict[str, str]) -> Dict[str, str]:
    dependencies = {}
    for line in manifests.get("requirements.txt", "").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        name, separator, version = value.partition("==")
        dependencies[name.strip()] = version.strip() if separator else ""
    package_json = manifests.get("package.json")
    if package_json:
        try:
            parsed = json.loads(package_json)
            for section in ("dependencies", "devDependencies"):
                for name, version in parsed.get(section, {}).items():
                    dependencies[str(name)] = str(version)
        except (json.JSONDecodeError, AttributeError):
            pass
    return dependencies


def _commands(
    root: Path,
    files: List[str],
    languages: List[str],
    manifests: Dict[str, str],
) -> tuple:
    if "python" in languages:
        test_cmd = (
            VERIFIERS["python"]["test"]
            if any(path.startswith("tests/") and path.endswith(".py") for path in files)
            else None
        )
        return None, test_cmd
    if "typescript" in languages:
        return VERIFIERS["typescript"]["build"], VERIFIERS["typescript"]["test"]
    if "javascript" in languages:
        package = manifests.get("package.json", "")
        has_test = '"test"' in package
        return VERIFIERS["javascript"]["build"], VERIFIERS["javascript"]["test"] if has_test else None
    if "go" in languages:
        return VERIFIERS["go"]["build"], VERIFIERS["go"]["test"]
    if "java" in languages:
        return VERIFIERS["java"]["build"], VERIFIERS["java"]["test"]
    return None, None

