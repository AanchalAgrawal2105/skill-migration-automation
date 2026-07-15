from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas import MigrationRun, RiskLevel, ScopeResult, UsageSite
from app.verifiers import is_probably_text


def scope(run: MigrationRun, goal: str, pack: dict[str, Any] | None) -> MigrationRun:
    if run.profile is None:
        raise ValueError("Cannot scope before repository profile exists")

    markers = _patterns_from_pack(pack)
    if not markers:
        run.scope = ScopeResult()
        return run

    repo_root = Path(run.profile.repo_path)
    usage_sites: list[UsageSite] = []
    files_to_change: list[str] = []

    for relative_path in run.profile.files:
        path = repo_root / relative_path
        if not path.is_file() or not is_probably_text(path):
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if any(marker in line for marker in markers):
                usage_sites.append(
                    UsageSite(
                        path=relative_path,
                        line=line_number,
                        snippet=line.strip(),
                        risk=_pack_risk(pack),
                    )
                )
                if relative_path not in files_to_change:
                    files_to_change.append(relative_path)

    run.scope = ScopeResult(files_to_change=files_to_change, usage_sites=usage_sites)
    return run


def _patterns_from_pack(pack: dict[str, Any] | None) -> list[str]:
    if not pack:
        return []

    patterns: list[str] = []
    detect = pack.get("detect")
    if isinstance(detect, dict):
        patterns.extend(str(item) for item in detect.get("markers", []) if str(item))

    for item in pack.get("breaking_changes", []):
        if isinstance(item, dict) and item.get("pattern"):
            patterns.append(str(item["pattern"]))

    transform = pack.get("transform")
    if isinstance(transform, dict):
        for replacement in transform.get("replacements", []):
            if isinstance(replacement, dict) and replacement.get("old"):
                patterns.append(str(replacement["old"]))

    return sorted(set(patterns))


def _pack_risk(pack: dict[str, Any] | None) -> RiskLevel:
    if not pack:
        return RiskLevel.review
    value = pack.get("risk", "review")
    try:
        return RiskLevel(str(value))
    except ValueError:
        return RiskLevel.review

