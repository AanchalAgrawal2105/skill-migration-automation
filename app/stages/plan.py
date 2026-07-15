from __future__ import annotations

from typing import Any

from app.llm import DemoLLM
from app.schemas import MigrationRun


def plan(run: MigrationRun, goal: str, pack: dict[str, Any] | None, llm: DemoLLM | None = None) -> MigrationRun:
    if run.profile is None:
        raise ValueError("Cannot plan before repository profile exists")

    adapter = llm or DemoLLM()
    run.goal = goal
    run.plan = adapter.create_plan(goal=goal, pack=pack)
    return run

