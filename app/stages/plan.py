"""Produce a structured migration plan from the goal and optional pack."""

from app.llm import DemoLLM
from app.pack_loader import load_pack
from app.schemas import MigrationRun
from app.stages.base import StageContext


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    if migration.profile is None:
        raise ValueError("Cannot plan before repository profile exists")
    pack = load_pack(context.pack_path)
    adapter = context.services.get("llm") or DemoLLM()
    updated = migration.model_copy(deep=True)
    updated.plan = adapter.create_plan(goal=context.goal, pack=pack)
    return updated

