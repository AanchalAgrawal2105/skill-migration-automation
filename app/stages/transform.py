"""Apply generic pack replacements per file and check syntax immediately."""

import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.pack_loader import load_pack
from app.schemas import FileChange, MigrationRun
from app.stages.base import StageContext
from app.verifiers import CommandRunner


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    if migration.profile is None or migration.scope is None:
        raise ValueError("Cannot transform before profile and scope")
    pack = load_pack(context.pack_path)
    replacements = _replacements(pack)
    root = Path(migration.profile.root_path).resolve()
    runner = context.services.get("command_runner") or CommandRunner(root)
    changes = list(migration.changes)

    for relative in migration.scope.files_to_change:
        target = (root / relative).resolve()
        if root not in target.parents or not target.is_file():
            raise ValueError(f"Scoped file escapes repository or is missing: {relative}")
        original = target.read_text(encoding="utf-8", errors="replace")
        modified = original
        for old, new in replacements:
            modified = modified.replace(old, new)
        if modified == original:
            changes.append(
                FileChange(
                    file=relative,
                    original=original,
                    modified=modified,
                    diff="",
                    rationale="No authoritative pack replacement changed this file.",
                    syntax_ok=False,
                    kind="manual",
                )
            )
            continue

        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            )
        )
        target.write_text(modified, encoding="utf-8")
        language = _language_for(relative)
        syntax_template = migration.profile.syntax_cmd.get(language)
        syntax_ok = True
        if syntax_template:
            syntax_ok = runner.run(
                syntax_template.format(file=relative), timeout_seconds=30
            ).passed
        kind = "auto" if syntax_ok else "manual"
        if not syntax_ok:
            target.write_text(original, encoding="utf-8")
        changes.append(
            FileChange(
                file=relative,
                original=original,
                modified=modified,
                diff=diff,
                rationale=(
                    "Applied migration-specification replacements."
                    if syntax_ok
                    else "Candidate failed syntax verification and the file was restored."
                ),
                syntax_ok=syntax_ok,
                kind=kind,
            )
        )

    updated = migration.model_copy(deep=True)
    updated.changes = changes
    return updated


def _replacements(pack: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    transform = (pack or {}).get("transform")
    if not isinstance(transform, dict):
        return []
    replacements = []
    for item in transform.get("replacements", []):
        if not isinstance(item, dict) or "old" not in item or "new" not in item:
            continue
        replacements.append((str(item["old"]), str(item["new"])))
    return replacements


def _language_for(path: str) -> str:
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
    }.get(Path(path).suffix.lower(), "")

