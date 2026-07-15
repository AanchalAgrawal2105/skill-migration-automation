from __future__ import annotations

from typing import Any

from app.schemas import MigrationPlan, PlanStep, RiskLevel


class DemoLLM:
    """Deterministic structured fallback used when live LLM mode is unavailable."""

    def create_plan(self, goal: str, pack: dict[str, Any] | None) -> MigrationPlan:
        pack = pack or {}
        title = str(pack.get("name") or "Pack-driven migration")
        risks = [str(item) for item in pack.get("risks", [])]
        raw_steps = pack.get("steps") or []
        steps: list[PlanStep] = []

        for raw in raw_steps:
            if not isinstance(raw, dict):
                continue
            steps.append(
                PlanStep(
                    title=str(raw.get("title") or "Migration step"),
                    details=str(raw.get("details") or goal),
                    risk=_risk(raw.get("risk")),
                )
            )

        if not steps:
            steps.append(
                PlanStep(
                    title="Apply scoped replacements",
                    details="Search for pack-provided patterns and update matching files.",
                    risk=RiskLevel.review,
                )
            )

        return MigrationPlan(summary=f"{title}: {goal}", steps=steps, risks=risks)


def _risk(value: object) -> RiskLevel:
    try:
        return RiskLevel(str(value))
    except ValueError:
        return RiskLevel.review

