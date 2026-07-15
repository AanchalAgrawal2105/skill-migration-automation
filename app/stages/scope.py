"""Deterministic, line-aware migration scoping."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.contracts import (
    ContractError,
    build_model,
    field_model,
    nested_list_model,
    profile_paths,
    repo_root,
    update_run,
)
from app.packs import KnowledgePack, coerce_pack


MAX_SOURCE_BYTES = 256 * 1024
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "dist", "build"}


class ScopeError(RuntimeError):
    """Raised when scoped repository paths are unsafe or unreadable."""


def scope(
    run: Any,
    goal: str,
    pack: KnowledgePack | Mapping[str, Any] | None,
) -> Any:
    """Populate ``MigrationRun.scope`` using literal patterns and profile files."""

    del goal  # The goal influences the typed plan, never filesystem branching.
    knowledge = coerce_pack(pack)
    patterns = _patterns(run, knowledge)
    root = repo_root(run)
    scope_model = field_model(run, "scope")
    site_model = nested_list_model(scope_model, ("sites", "usage_sites"))

    sites: list[Any] = []
    files_to_change: set[str] = set()
    seen: set[tuple[str, int, str]] = set()
    for relative in sorted(set(profile_paths(run))):
        path = _safe_profile_path(root, relative)
        if _excluded(path, root) or not path.is_file():
            continue
        text = _read_eligible_text(path)
        if text is None:
            continue
        normalized = path.relative_to(root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for literal, risk in patterns:
                if literal not in line:
                    continue
                identity = (normalized, line_number, literal)
                if identity in seen:
                    continue
                seen.add(identity)
                sites.append(
                    build_model(
                        site_model,
                        {
                            "path": normalized,
                            "line": line_number,
                            "match": literal,
                            "risk": risk,
                        },
                    )
                )
                files_to_change.add(normalized)

    result = build_model(
        scope_model,
        {
            "sites": sites,
            "files_to_change": sorted(files_to_change),
        },
    )
    return update_run(run, scope=result)


run = scope


def _patterns(run: Any, pack: KnowledgePack | None) -> list[tuple[str, str]]:
    ordered: dict[str, str] = {}
    if pack:
        for literal, risk in pack.literals_with_risk():
            ordered[literal] = risk

    plan = getattr(run, "plan", None)
    if plan is None:
        raise ContractError("MigrationRun.plan is required before scope")
    candidates = getattr(plan, "candidate_literals", None)
    if candidates is None and isinstance(plan, Mapping):
        candidates = plan.get("candidate_literals")
    if candidates is None:
        raise ContractError("MigrationPlan must expose candidate_literals")
    for value in candidates:
        literal = str(value).strip()
        if literal:
            ordered.setdefault(literal, "review")
    return list(ordered.items())


def _safe_profile_path(root: Path, relative: str) -> Path:
    supplied = Path(relative)
    if supplied.is_absolute():
        raise ScopeError(f"profile path must be relative: {relative}")
    candidate = (root / supplied).resolve()
    if not candidate.is_relative_to(root):
        raise ScopeError(f"profile path escapes repository: {relative}")
    return candidate


def _excluded(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(part in EXCLUDED_PARTS for part in relative.parts)


def _read_eligible_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return None
        data = path.read_bytes()
    except OSError as exc:
        raise ScopeError(f"could not inspect {path}: {exc}") from exc
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
