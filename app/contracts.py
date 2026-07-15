"""Runtime helpers for consuming Role A's frozen Pydantic contracts.

Role C intentionally does not own ``app.schemas``.  These helpers inspect the
models carried by a MigrationRun so the stages can construct nested contract
objects without importing a second, competing schema definition.
"""

from __future__ import annotations

from dataclasses import is_dataclass, replace
from pathlib import Path
try:
    from types import UnionType
except ImportError:  # Python 3.9 compatibility
    UnionType = ()  # type: ignore[assignment,misc]
from typing import Any, Mapping, Union, get_args, get_origin


class ContractError(RuntimeError):
    """Raised when the frozen integration contract is missing required data."""


def update_run(run: Any, **updates: Any) -> Any:
    """Return a run with updates, supporting mutable and frozen contracts."""

    if hasattr(run, "model_copy"):
        return run.model_copy(update=updates)
    if is_dataclass(run):
        return replace(run, **updates)
    for name, value in updates.items():
        setattr(run, name, value)
    return run


def field_model(instance: Any, field_name: str, *, list_item: bool = False) -> type[Any]:
    """Resolve a nested Pydantic model type from a field annotation."""

    fields = getattr(type(instance), "model_fields", None)
    if not fields or field_name not in fields:
        raise ContractError(f"contract is missing field {field_name!r}")
    annotation = _strip_optional(fields[field_name].annotation)
    if list_item:
        origin = get_origin(annotation)
        if origin not in (list, tuple):
            raise ContractError(f"contract field {field_name!r} must be a list")
        args = get_args(annotation)
        if not args:
            raise ContractError(f"contract field {field_name!r} has no item type")
        annotation = _strip_optional(args[0])
    if not isinstance(annotation, type) or not hasattr(annotation, "model_validate"):
        raise ContractError(f"contract field {field_name!r} is not a Pydantic model")
    return annotation


def nested_list_model(parent_model: type[Any], field_names: tuple[str, ...]) -> type[Any]:
    """Resolve the item model for the first matching list field."""

    fields = getattr(parent_model, "model_fields", {})
    for name in field_names:
        if name not in fields:
            continue
        annotation = _strip_optional(fields[name].annotation)
        if get_origin(annotation) not in (list, tuple):
            continue
        args = get_args(annotation)
        if args:
            item = _strip_optional(args[0])
            if isinstance(item, type) and hasattr(item, "model_validate"):
                return item
    joined = ", ".join(field_names)
    raise ContractError(f"contract has no typed list field matching: {joined}")


def build_model(model: type[Any], values: Mapping[str, Any]) -> Any:
    """Validate values against a contract model, accepting documented aliases."""

    fields = getattr(model, "model_fields", {})
    payload: dict[str, Any] = {}
    aliases = {
        "path": ("path", "file", "file_path"),
        "line": ("line", "line_number"),
        "match": ("match", "pattern", "snippet"),
        "sites": ("sites", "usage_sites"),
        "files_to_change": ("files_to_change", "files"),
        "diff": ("diff", "unified_diff"),
        "syntax_ok": ("syntax_ok", "syntax_passed"),
        "kind": ("kind", "change_kind"),
    }
    for canonical, value in values.items():
        candidates = aliases.get(canonical, (canonical,))
        target = next((name for name in candidates if name in fields), None)
        if target is not None:
            payload[target] = value
    try:
        return model.model_validate(payload)
    except Exception as exc:  # Pydantic version belongs to Role A.
        raise ContractError(f"could not construct {model.__name__}: {exc}") from exc


def repo_root(run: Any) -> Path:
    """Read the repository root from the run or its profile."""

    for owner in (run, getattr(run, "profile", None)):
        if owner is None:
            continue
        for name in ("repo_path", "root_path", "root", "path"):
            value = _value(owner, name)
            if value:
                return Path(value).expanduser().resolve()
    raise ContractError("MigrationRun/RepoProfile does not expose a repository path")


def profile_paths(run: Any) -> list[str]:
    """Return normalized relative paths from the frozen RepoProfile."""

    profile = getattr(run, "profile", None)
    if profile is None:
        raise ContractError("MigrationRun.profile is required before scope")
    raw: Any = None
    for name in ("files", "file_tree", "paths"):
        raw = _value(profile, name)
        if raw is not None:
            break
    if raw is None:
        raise ContractError("RepoProfile does not expose files/file_tree/paths")

    paths: list[str] = []
    for item in raw:
        if isinstance(item, str):
            paths.append(item)
            continue
        if isinstance(item, Mapping):
            value = item.get("path") or item.get("file")
        else:
            value = getattr(item, "path", None) or getattr(item, "file", None)
        if value:
            paths.append(str(value))
    return paths


def model_data(value: Any) -> Any:
    """Convert Pydantic/dataclass-like objects into prompt-safe primitives."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): model_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [model_data(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _strip_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    union_types = (Union,) if UnionType == () else (Union, UnionType)
    if origin in union_types:
        args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
        if len(args) == 1:
            return args[0]
    return annotation


def _value(owner: Any, name: str) -> Any:
    if isinstance(owner, Mapping):
        return owner.get(name)
    return getattr(owner, name, None)
