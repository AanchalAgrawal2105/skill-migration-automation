"""Find pack-specified migration usage sites with deterministic search."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.pack_loader import load_pack
from app.schemas import MigrationRun, ScopeResult, UsageSite
from app.stages.base import StageContext
from app.verifiers import is_probably_text


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    if migration.profile is None:
        raise ValueError("Cannot scope before repository profile exists")
    pack = load_pack(context.pack_path)
    patterns = _patterns_from_pack(pack)
    if not patterns:
        raise ValueError(
            "No scope patterns were produced; provide a knowledge pack or an LLM scope service"
        )
    root = Path(migration.profile.root_path).resolve()
    sites = []
    files = []
    for relative in migration.profile.file_tree:
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file() or not is_probably_text(path):
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            for pattern in patterns:
                if pattern not in line:
                    continue
                sites.append(
                    UsageSite(
                        file=relative,
                        line=line_number,
                        pattern=pattern,
                        reason="Matched a pattern supplied by the migration specification.",
                        risk=_risk(pack),
                        kind="auto" if pack else "review",
                    )
                )
                if relative not in files:
                    files.append(relative)
                break
    if not files:
        raise ValueError("No repository usages matched the migration specification")
    updated = migration.model_copy(deep=True)
    updated.scope = ScopeResult(sites=sites, files_to_change=files)
    return updated


def _patterns_from_pack(pack: Optional[Dict[str, Any]]) -> List[str]:
    if not pack:
        return []
    patterns = []
    detect = pack.get("detect")
    if isinstance(detect, dict):
        patterns.extend(str(value) for value in detect.get("markers", []) if value)
    for change in pack.get("breaking_changes", []):
        if isinstance(change, dict) and change.get("pattern"):
            patterns.append(str(change["pattern"]))
    transform = pack.get("transform")
    if isinstance(transform, dict):
        for replacement in transform.get("replacements", []):
            if isinstance(replacement, dict) and replacement.get("old") is not None:
                patterns.append(str(replacement["old"]))
    return sorted(set(patterns))


def _risk(pack: Optional[Dict[str, Any]]) -> str:
    value = str((pack or {}).get("risk", "medium"))
    return value if value in {"low", "medium", "high"} else "medium"
