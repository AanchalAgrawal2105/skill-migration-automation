"""Create a migration branch, commit verified changes, and optionally open a PR."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Sequence

from app.schemas import MigrationRun, PRResult
from app.stages.base import StageContext
from app.verifiers import MAX_LOG_CHARS


class PRStageError(RuntimeError):
    """Raised when a verified migration cannot be prepared for review."""


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    if migration.profile is None:
        raise PRStageError("Cannot create PR before repository profile exists")
    if migration.verify is None or not migration.verify.passed:
        raise PRStageError("Refusing to create PR because verification did not pass")
    if not migration.changes:
        raise PRStageError("Refusing to create PR because no file changes were recorded")

    root = Path(migration.profile.root_path).resolve()
    if not (root / ".git").exists():
        raise PRStageError(f"Repository is not a Git repository: {root}")

    original_branch = _current_branch(root)
    branch = _unique_branch(root, _branch_slug(context.goal))
    _git(root, ["switch", "-c", branch])

    changed_files = _changed_files(root, migration)
    if not changed_files:
        updated = migration.model_copy(deep=True)
        updated.pr = PRResult(branch=branch, pr_url=None, committed=False)
        return updated

    _git(root, ["add", "--", *changed_files])
    if _git(root, ["diff", "--cached", "--quiet"], allow_failure=True).returncode == 0:
        updated = migration.model_copy(deep=True)
        updated.pr = PRResult(branch=branch, pr_url=None, committed=False)
        return updated

    _git(root, ["commit", "-m", _commit_message(context.goal)])

    pr_url = None
    if bool(context.services.get("create_pr")):
        remote = str(context.services.get("pr_remote") or "origin")
        base = str(context.services.get("pr_base") or original_branch)
        _git(root, ["push", "-u", remote, branch])
        pr_url = _create_github_pr(root, branch=branch, base=base, migration=migration, context=context)

    updated = migration.model_copy(deep=True)
    updated.pr = PRResult(branch=branch, pr_url=pr_url, committed=True)
    return updated


def _changed_files(root: Path, migration: MigrationRun) -> list[str]:
    files: list[str] = []
    for change in migration.changes:
        if change.kind == "manual" or not change.syntax_ok:
            raise PRStageError(
                f"Refusing to create PR because {change.file} requires manual review"
            )
        relative = _safe_relative(root, change.file)
        if relative not in files:
            files.append(relative)
    return files


def _safe_relative(root: Path, relative: str) -> str:
    supplied = Path(relative)
    if supplied.is_absolute():
        raise PRStageError(f"Changed file must be relative: {relative}")
    candidate = (root / supplied).resolve()
    if not candidate.is_relative_to(root):
        raise PRStageError(f"Changed file escapes repository: {relative}")
    return candidate.relative_to(root).as_posix()


def _current_branch(root: Path) -> str:
    result = _git(root, ["branch", "--show-current"])
    branch = result.stdout.strip()
    if branch:
        return branch
    return "main"


def _unique_branch(root: Path, base: str) -> str:
    candidate = base
    index = 2
    while _git(root, ["rev-parse", "--verify", candidate], allow_failure=True).returncode == 0:
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _branch_slug(goal: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")
    if not slug:
        slug = "migration"
    return f"migrate/{slug[:56].strip('-')}"


def _commit_message(goal: str) -> str:
    title = goal.strip() or "Apply migration"
    return f"Apply migration: {title[:60]}"


def _create_github_pr(
    root: Path,
    *,
    branch: str,
    base: str,
    migration: MigrationRun,
    context: StageContext,
) -> str:
    result = _command(
        root,
        [
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            _pr_title(context.goal),
            "--body",
            _pr_body(migration),
        ],
    )
    url = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if not url:
        raise PRStageError("GitHub CLI did not return a PR URL")
    return url


def _pr_title(goal: str) -> str:
    return f"Migration: {(goal.strip() or 'repository update')[:72]}"


def _pr_body(migration: MigrationRun) -> str:
    if migration.reports is not None:
        return migration.reports.migration_docs
    changed = "\n".join(f"- `{change.file}`: {change.rationale}" for change in migration.changes)
    return "Automated migration prepared by Refer.\n\n" + changed


def _git(
    root: Path,
    args: Sequence[str],
    *,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = _command(root, ["git", *args], allow_failure=allow_failure)
    return result


def _command(
    root: Path,
    argv: Sequence[str],
    *,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(argv),
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 and not allow_failure:
        detail = (completed.stderr.strip() or completed.stdout.strip())[:MAX_LOG_CHARS]
        raise PRStageError(f"{' '.join(argv)} failed: {detail}")
    return completed

