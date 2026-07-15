"""Typed migration planning with adapters for the frozen public contracts."""

from __future__ import annotations

import os
from typing import Any, Mapping

from app.contracts import update_run
from app.llm import AgentPlan, LLM, PackLLM, build_llm
from app.packs import KnowledgePack, coerce_pack, load_pack
from app.schemas import MigrationPlan, MigrationRun, PlanStep
from app.stages.base import StageContext


def plan(
    migration: Any,
    goal: str,
    pack: KnowledgePack | Mapping[str, Any] | None,
    llm: LLM,
) -> Any:
    """Role C core: populate a run using a typed LLM adapter."""

    if not goal.strip():
        raise ValueError("migration goal must not be empty")
    migration_plan = llm.create_plan(
        goal=goal,
        profile=getattr(migration, "profile", None),
        pack=coerce_pack(pack),
    )
    return update_run(migration, plan=migration_plan)


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    if migration.profile is None:
        raise ValueError("Cannot plan before repository profile exists")
    knowledge = load_pack(context.pack_path)
    adapter = context.services.get("llm") or _build_adapter(context, knowledge)
    output = adapter.create_plan(
        goal=context.goal,
        profile=migration.profile,
        pack=knowledge,
    )
    public_plan, candidates = _public_plan(output, context.goal)
    state = context.services.get("state")
    if isinstance(state, dict):
        state["candidate_literals"] = candidates
        state["llm"] = adapter
        state["pack"] = knowledge
    updated = migration.model_copy(deep=True)
    updated.plan = public_plan
    return updated


def _build_adapter(context: StageContext, pack: KnowledgePack | None) -> LLM:
    if context.demo_mode:
        fixtures_root = context.services.get("fixtures_root", "tests/fixtures/llm")
        return build_llm(
            demo_mode=True,
            plan_model=AgentPlan,
            pack=pack,
            fixtures_root=fixtures_root,
        )
    if os.getenv("REFER_MODEL", "").strip():
        return build_llm(
            demo_mode=False,
            plan_model=AgentPlan,
            pack=pack,
            client=context.services.get("openai_client"),
        )
    return PackLLM()


def _public_plan(output: Any, goal: str) -> tuple:
    if isinstance(output, MigrationPlan):
        candidates = list(getattr(output, "candidate_literals", []) or [])
        return output, candidates
    raw_steps = list(getattr(output, "steps", []) or [])
    steps = []
    for order, item in enumerate(raw_steps, start=1):
        description = str(
            getattr(item, "description", None)
            or getattr(item, "details", None)
            or "Apply the migration specification."
        )
        raw_risk = str(getattr(item, "risk", "review"))
        steps.append(
            PlanStep(
                order=order,
                title=f"Migration step {order}",
                description=description,
                risk=_risk_level(raw_risk),
            )
        )
    if not steps:
        steps.append(
            PlanStep(
                order=1,
                title="Apply migration",
                description=goal,
                risk="medium",
            )
        )
    summary = str(getattr(output, "summary", "") or goal)
    candidates = [
        str(value)
        for value in (getattr(output, "candidate_literals", []) or [])
        if str(value).strip()
    ]
    return MigrationPlan(goal=goal, summary=summary, steps=steps), candidates


def _risk_level(value: str) -> str:
    value = value.lower()
    if value in {"low", "medium", "high"}:
        return value
    return {"auto": "low", "review": "medium", "manual": "high"}.get(
        value, "medium"
    )
