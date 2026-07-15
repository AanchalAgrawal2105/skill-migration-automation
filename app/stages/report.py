"""Generate deterministic migration, risk, and rollback reports."""

from app.schemas import MigrationRun, Reports
from app.stages.base import StageContext


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    anchor = migration.profile.rollback_anchor if migration.profile else "unknown"
    change_lines = [
        f"- `{change.file}`: {change.rationale}" for change in migration.changes
    ] or ["- No files changed."]
    risk_rows = ["| File | Kind | Syntax |", "|---|---|---|"]
    risk_rows.extend(
        f"| `{change.file}` | {change.kind} | {change.syntax_ok} |"
        for change in migration.changes
    )
    docs = "\n".join(
        [
            "# Migration documentation",
            "",
            f"Goal: {context.goal}",
            "",
            "## Changes",
            "",
            *change_lines,
            "",
            f"Verification passed: {bool(migration.verify and migration.verify.passed)}",
        ]
    )
    rollback = (
        "# Rollback plan\n\n"
        f"Original commit: `{anchor}`.\n\n"
        "Review the diff, then restore the original branch or revert the migration commit."
    )
    updated = migration.model_copy(deep=True)
    updated.reports = Reports(
        migration_docs=docs,
        risk_report="\n".join(risk_rows),
        rollback_plan=rollback,
    )
    return updated

