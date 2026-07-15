"""Stable extension boundary for built-in and third-party stages."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from app.schemas import MigrationRun


@dataclass(frozen=True)
class StageContext:
    """Run inputs and injectable dependencies shared without global state."""

    repo_path: Path
    goal: str
    pack_path: Optional[Path] = None
    demo_mode: bool = False
    services: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Stage(Protocol):
    """A technology-neutral pipeline stage."""

    name: str

    def run(self, run: MigrationRun, context: StageContext) -> MigrationRun:
        """Return the updated migration run or raise on failure."""

