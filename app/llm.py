"""Small structured fallback adapter for pack-driven integration runs.

Role C can replace or extend this adapter with a live structured-output model
without changing the pipeline or public stage contracts.
"""

from typing import Any, Dict, Optional

from app.schemas import MigrationPlan, PlanStep


class DemoLLM:
    def create_plan(
        self, goal: str, pack: Optional[Dict[str, Any]]
    ) -> MigrationPlan:
        pack = pack or {}
        raw_steps = pack.get("steps") or []
        steps = []
        for order, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                continue
            risk = str(raw.get("risk", "medium"))
            if risk not in {"low", "medium", "high"}:
                risk = "medium"
            steps.append(
                PlanStep(
                    order=order,
                    title=str(raw.get("title") or "Migration step"),
                    description=str(raw.get("details") or raw.get("description") or goal),
                    risk=risk,
                )
            )
        if not steps:
            steps.append(
                PlanStep(
                    order=1,
                    title="Apply scoped migration",
                    description="Update only usages identified by the migration specification.",
                    risk="medium",
                )
            )
        name = str(pack.get("name") or "Specification-driven migration")
        return MigrationPlan(goal=goal, summary=f"{name}: {goal}", steps=steps)
