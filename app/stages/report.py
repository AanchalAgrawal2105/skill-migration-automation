from __future__ import annotations

from app.schemas import MigrationRun


def report(run: MigrationRun) -> MigrationRun:
    run.reports["summary.md"] = _summary(run)
    run.reports["rollback.md"] = _rollback(run)
    return run


def _summary(run: MigrationRun) -> str:
    lines = [f"# Migration Summary", "", f"Goal: {run.goal}", ""]
    if run.plan:
        lines.extend(["## Plan", "", run.plan.summary, ""])
        for step in run.plan.steps:
            lines.append(f"- {step.title}: {step.details} ({step.risk})")
        lines.append("")
    if run.changes:
        lines.extend(["## Changes", ""])
        for change in run.changes:
            lines.append(f"- {change.path}: {change.kind}; syntax_ok={change.syntax_ok}")
        lines.append("")
    if run.verify:
        lines.extend(["## Verification", "", f"Passed: {run.verify.passed}", ""])
        for command in run.verify.commands:
            lines.append(f"- {' '.join(command.command)} -> {command.returncode}")
    return "\n".join(lines).strip() + "\n"


def _rollback(run: MigrationRun) -> str:
    anchor = run.profile.rollback_anchor if run.profile else "unknown"
    return (
        "# Rollback\n\n"
        f"Rollback anchor: `{anchor}`\n\n"
        "Review changes with `git diff`. To return manually, use the recorded SHA in your normal Git workflow.\n"
    )

