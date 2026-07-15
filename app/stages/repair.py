"""One-attempt repair helper kept separate for explicit retry accounting."""

from __future__ import annotations

from typing import Any, Mapping

from app.llm import LLM, TransformOutput
from app.packs import KnowledgePack


def repair_once(
    *,
    llm: LLM,
    goal: str,
    path: str,
    candidate: str,
    sites: list[Any],
    pack: KnowledgePack | Mapping[str, Any] | None,
    syntax_error: str,
) -> TransformOutput:
    """Perform exactly one repair call; callers must not loop this helper."""

    return llm.repair_file(
        goal=goal,
        path=path,
        candidate=candidate,
        sites=sites,
        pack=pack,
        syntax_error=syntax_error,
    )
