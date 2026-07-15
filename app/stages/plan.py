"""Typed migration planning stage."""

from __future__ import annotations

from typing import Any, Mapping

from app.contracts import update_run
from app.llm import LLM
from app.packs import KnowledgePack, coerce_pack


def plan(
    run: Any,
    goal: str,
    pack: KnowledgePack | Mapping[str, Any] | None,
    llm: LLM,
) -> Any:
    """Populate ``MigrationRun.plan`` using a typed LLM adapter."""

    if not goal.strip():
        raise ValueError("migration goal must not be empty")
    migration_plan = llm.create_plan(
        goal=goal,
        profile=getattr(run, "profile", None),
        pack=coerce_pack(pack),
    )
    return update_run(run, plan=migration_plan)


# Pipeline implementations may prefer a conventional stage-level run symbol.
run = plan
