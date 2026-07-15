"""Isolated per-file transformation with deterministic syntax gating."""

from __future__ import annotations

import difflib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.contracts import (
    ContractError,
    build_model,
    field_model,
    model_data,
    repo_root,
    update_run,
)
from app.llm import LLM
from app.packs import KnowledgePack, coerce_pack, load_pack
from app.schemas import MigrationRun
from app.stages.base import StageContext
from app.stages.repair import repair_once
from app.stages.scope import MAX_SOURCE_BYTES


@dataclass(frozen=True)
class SyntaxOutcome:
    passed: bool
    log: str = ""


class TransformError(RuntimeError):
    """Raised for unsafe paths or missing integration boundaries."""


def transform(
    run: Any,
    pack: KnowledgePack | Mapping[str, Any] | None,
    llm: LLM,
    goal: str | None = None,
) -> Any:
    """Transform scoped files and append truthful FileChange contracts."""

    scope_result = getattr(run, "scope", None)
    if scope_result is None:
        raise ContractError("MigrationRun.scope is required before transform")
    migration_goal = str(goal or getattr(run, "goal", "")).strip()
    if not migration_goal:
        raise ContractError("MigrationRun.goal is required before transform")

    knowledge = coerce_pack(pack)
    root = repo_root(run)
    file_change_model = field_model(run, "changes", list_item=True)
    files = _value(scope_result, "files_to_change", "files") or []
    all_sites = _value(scope_result, "sites", "usage_sites") or []
    created: list[Any] = []

    for relative in files:
        normalized, path = _safe_target(root, str(relative))
        sites = [site for site in all_sites if _site_path(site) == normalized]
        created.append(
            _transform_one(
                run=run,
                path=path,
                relative=normalized,
                goal=migration_goal,
                sites=sites,
                pack=knowledge,
                llm=llm,
                file_change_model=file_change_model,
            )
        )

    previous = list(getattr(run, "changes", None) or [])
    return update_run(run, changes=[*previous, *created])


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    knowledge = load_pack(context.pack_path)
    state = context.services.get("state")
    adapter = state.get("llm") if isinstance(state, dict) else None
    if adapter is None:
        adapter = context.services.get("llm")
    if adapter is None:
        raise ContractError("Plan stage did not provide an LLM adapter")
    return transform(migration, knowledge, adapter, goal=context.goal)


def check_file_syntax(run: Any, relative_path: str) -> Any:
    """Role B boundary: ``check_file_syntax(run, relative_path)``."""

    try:
        from app.verifiers import check_file_syntax as role_b_checker
    except ImportError as exc:
        raise ContractError(
            "Role B must provide app.verifiers.check_file_syntax(run, relative_path)"
        ) from exc
    return role_b_checker(run, relative_path)


def _transform_one(
    *,
    run: Any,
    path: Path,
    relative: str,
    goal: str,
    sites: list[Any],
    pack: KnowledgePack | None,
    llm: LLM,
    file_change_model: type[Any],
) -> Any:
    original, mode, newline = _read_original(path)
    matched = {_site_match(site) for site in sites if _site_match(site)}
    relevant_pack = pack.relevant_for(matched) if pack else None
    try:
        proposed = llm.transform_file(
            goal=goal,
            path=relative,
            original=original,
            sites=sites,
            pack=relevant_pack,
        )
        candidate = _preserve_newlines(proposed.modified, newline)
        if candidate == original:
            return _file_change(
                file_change_model,
                path=relative,
                original=original,
                modified=candidate,
                rationale="Model returned unchanged content; manual review required.",
                syntax_ok=False,
                kind="manual",
                syntax_error="unchanged transform output",
            )

        _atomic_write(path, candidate, mode)
        first = _syntax_outcome(check_file_syntax(run, relative))
        if first.passed:
            return _file_change(
                file_change_model,
                path=relative,
                original=original,
                modified=candidate,
                rationale=proposed.rationale,
                syntax_ok=True,
                kind=_successful_kind(sites),
                syntax_error="",
            )

        repaired = repair_once(
            llm=llm,
            goal=goal,
            path=relative,
            candidate=candidate,
            sites=sites,
            pack=relevant_pack,
            syntax_error=first.log[-4_000:],
        )
        repaired_content = _preserve_newlines(repaired.modified, newline)
        _atomic_write(path, repaired_content, mode)
        second = _syntax_outcome(check_file_syntax(run, relative))
        if second.passed:
            return _file_change(
                file_change_model,
                path=relative,
                original=original,
                modified=repaired_content,
                rationale=f"{proposed.rationale} Repair: {repaired.rationale}",
                syntax_ok=True,
                kind=_successful_kind(sites),
                syntax_error="",
            )

        _atomic_write(path, original, mode)
        return _file_change(
            file_change_model,
            path=relative,
            original=original,
            modified=repaired_content,
            rationale=(
                f"{proposed.rationale} Repair failed; original restored. "
                f"{repaired.rationale}"
            ),
            syntax_ok=False,
            kind="manual",
            syntax_error=second.log[-4_000:],
        )
    except (KeyboardInterrupt, SystemExit):
        if path.exists() and path.read_text(encoding="utf-8") != original:
            _atomic_write(path, original, mode)
        raise
    except Exception as exc:
        # A model/checker failure must not leave a candidate in the worktree.
        try:
            current = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            current = original
        attempted = current if current != original else original
        if current != original:
            _atomic_write(path, original, mode)
        return _file_change(
            file_change_model,
            path=relative,
            original=original,
            modified=attempted,
            rationale=f"Transformation failed; original restored: {exc}",
            syntax_ok=False,
            kind="manual",
            syntax_error=str(exc)[-4_000:],
        )


def _safe_target(root: Path, relative: str) -> tuple[str, Path]:
    supplied = Path(relative)
    if supplied.is_absolute():
        raise TransformError(f"target must be relative: {relative}")
    path = (root / supplied).resolve()
    if not path.is_relative_to(root):
        raise TransformError(f"target escapes repository: {relative}")
    if not path.is_file():
        raise TransformError(f"target is not a file: {relative}")
    return path.relative_to(root).as_posix(), path


def _read_original(path: Path) -> tuple[str, int, str]:
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise TransformError(f"target exceeds {MAX_SOURCE_BYTES} bytes: {path}")
    data = path.read_bytes()
    if b"\0" in data:
        raise TransformError(f"target is binary: {path}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TransformError(f"target is not UTF-8: {path}") from exc
    newline = "\r\n" if data.count(b"\r\n") > 0 else "\n"
    return text, path.stat().st_mode, newline


def _atomic_write(path: Path, content: str, mode: int) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _preserve_newlines(content: str, newline: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if newline == "\n" else normalized.replace("\n", "\r\n")


def _file_change(
    model: type[Any],
    *,
    path: str,
    original: str,
    modified: str,
    rationale: str,
    syntax_ok: bool,
    kind: str,
    syntax_error: str,
) -> Any:
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    return build_model(
        model,
        {
            "path": path,
            "original": original,
            "modified": modified,
            "rationale": rationale,
            "diff": diff,
            "syntax_ok": syntax_ok,
            "kind": kind,
            "syntax_error": syntax_error,
        },
    )


def _successful_kind(sites: list[Any]) -> str:
    kinds = {_value(site, "kind", "change_kind") for site in sites}
    kinds.discard(None)
    if "manual" in kinds:
        return "manual"
    if "review" in kinds:
        return "review"
    if "auto" in kinds:
        return "auto"
    risks = {_value(site, "risk") for site in sites}
    if "manual" in risks:
        return "manual"
    return "review" if "review" in risks else "auto"


def _syntax_outcome(value: Any) -> SyntaxOutcome:
    if isinstance(value, SyntaxOutcome):
        return value
    if isinstance(value, bool):
        return SyntaxOutcome(value)
    if isinstance(value, tuple) and value:
        return SyntaxOutcome(bool(value[0]), str(value[1]) if len(value) > 1 else "")
    passed = _value(value, "passed", "ok", "syntax_ok")
    if passed is None:
        raise ContractError("syntax checker result must expose passed/ok/syntax_ok")
    log = _value(value, "log", "stderr", "output") or ""
    return SyntaxOutcome(bool(passed), str(log))


def _site_path(site: Any) -> str:
    return str(_value(site, "path", "file", "file_path") or "")


def _site_match(site: Any) -> str:
    return str(_value(site, "match", "pattern", "snippet") or "")


def _value(owner: Any, *names: str) -> Any:
    data = model_data(owner)
    if isinstance(data, Mapping):
        for name in names:
            if name in data:
                return data[name]
    for name in names:
        value = getattr(owner, name, None)
        if value is not None:
            return value
    return None
