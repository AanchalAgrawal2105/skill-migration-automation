"""Explicit placeholders used until a production stage is implemented."""

from typing import Callable

from app.schemas import MigrationRun
from app.stages.base import StageContext


class StageNotImplementedError(NotImplementedError):
    """Raised rather than simulating success for a missing production stage."""


def pending(stage_name: str) -> Callable[[MigrationRun, StageContext], MigrationRun]:
    def run(run: MigrationRun, context: StageContext) -> MigrationRun:
        del run, context
        raise StageNotImplementedError(
            f"Production stage '{stage_name}' is not implemented. "
            "Use --fixture-dir for backbone validation or implement the stage."
        )

    return run

