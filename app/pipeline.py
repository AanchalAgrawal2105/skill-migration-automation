"""Technology-neutral migration orchestration.

This module sequences stages and reports state. It intentionally contains no
migration rules, file patterns, language checks, prompts, or verifier commands.
"""

from dataclasses import dataclass
from enum import Enum
from importlib import import_module
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, Optional, Sequence

from app.schemas import (
    FileChange,
    MigrationPlan,
    MigrationRun,
    PRResult,
    RepoProfile,
    Reports,
    ScopeResult,
    VerifyResult,
)
from app.stages.base import Stage, StageContext


DEFAULT_STAGE_SPECS = (
    "app.stages.ingest:run",
    "app.stages.profile:run",
    "app.stages.plan:run",
    "app.stages.scope:run",
    "app.stages.transform:run",
    "app.stages.verify:run",
    "app.stages.repair:run",
    "app.stages.report:run",
    "app.stages.pr:run",
)

FIXTURE_STAGE_NAMES = (
    "ingest",
    "profile",
    "plan",
    "scope",
    "transform",
    "verify",
    "repair",
    "report",
    "pr",
)


class StageStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class StageEvent:
    stage: str
    status: StageStatus
    run: MigrationRun
    error: Optional[str] = None


StageCallback = Callable[[StageEvent], None]


class PipelineConfigurationError(ValueError):
    """Raised before execution for an invalid pipeline definition."""


class PipelineExecutionError(RuntimeError):
    """A stage failure with the last valid partial run attached."""

    def __init__(self, stage: str, run: MigrationRun, cause: Exception):
        self.stage = stage
        self.run = run.model_copy(deep=True)
        self.cause = cause
        super().__init__(f"Stage '{stage}' failed: {cause}")


@dataclass(frozen=True)
class CallableStage:
    name: str
    function: Callable[[MigrationRun, StageContext], MigrationRun]

    def run(self, run: MigrationRun, context: StageContext) -> MigrationRun:
        return self.function(run, context)


def load_stage(spec: str) -> CallableStage:
    """Load `package.module:callable` without coupling the pipeline to a stack."""

    if ":" not in spec:
        raise PipelineConfigurationError(
            f"Invalid stage '{spec}'; expected package.module:callable"
        )
    module_name, attribute = spec.rsplit(":", 1)
    try:
        module: ModuleType = import_module(module_name)
        function = getattr(module, attribute)
    except (ImportError, AttributeError) as exc:
        raise PipelineConfigurationError(f"Cannot load stage '{spec}': {exc}") from exc
    if not callable(function):
        raise PipelineConfigurationError(f"Stage '{spec}' is not callable")
    name = module_name.rsplit(".", 1)[-1]
    return CallableStage(name=name, function=function)


class Pipeline:
    def __init__(self, stages: Sequence[Stage]):
        self.stages = tuple(stages)
        names = [stage.name for stage in self.stages]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise PipelineConfigurationError(
                f"Stage names must be unique; duplicates: {', '.join(duplicates)}"
            )

    def run(
        self,
        context: StageContext,
        *,
        initial: Optional[MigrationRun] = None,
        on_stage: Optional[StageCallback] = None,
    ) -> MigrationRun:
        current = (initial or MigrationRun()).model_copy(deep=True)
        for stage in self.stages:
            self._emit(on_stage, stage.name, StageStatus.STARTED, current)
            try:
                candidate = stage.run(current.model_copy(deep=True), context)
                if not isinstance(candidate, MigrationRun):
                    raise TypeError(
                        f"Stage returned {type(candidate).__name__}, expected MigrationRun"
                    )
                current = candidate.model_copy(deep=True)
            except Exception as exc:
                self._emit(
                    on_stage,
                    stage.name,
                    StageStatus.FAILED,
                    current,
                    error=str(exc),
                )
                raise PipelineExecutionError(stage.name, current, exc) from exc
            self._emit(on_stage, stage.name, StageStatus.COMPLETED, current)
        return current

    @staticmethod
    def _emit(
        callback: Optional[StageCallback],
        stage: str,
        status: StageStatus,
        run: MigrationRun,
        error: Optional[str] = None,
    ) -> None:
        if callback is not None:
            callback(
                StageEvent(
                    stage=stage,
                    status=status,
                    run=run.model_copy(deep=True),
                    error=error,
                )
            )


def build_pipeline(stage_specs: Optional[Sequence[str]] = None) -> Pipeline:
    return Pipeline([load_stage(spec) for spec in (stage_specs or DEFAULT_STAGE_SPECS)])


class FixtureStage:
    """Integration-only stage that applies a validated stage output fixture."""

    def __init__(self, name: str, fixture_dir: Path):
        self.name = name
        self.fixture_path = fixture_dir / f"{name}.json"

    def run(self, run: MigrationRun, context: StageContext) -> MigrationRun:
        del context
        if not self.fixture_path.is_file():
            raise FileNotFoundError(f"Missing fixture: {self.fixture_path}")
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        updated = run.model_copy(deep=True)
        if self.name in {"ingest", "profile"}:
            updated.profile = RepoProfile.model_validate(payload)
        elif self.name == "plan":
            updated.plan = MigrationPlan.model_validate(payload)
        elif self.name == "scope":
            updated.scope = ScopeResult.model_validate(payload)
        elif self.name in {"transform", "repair"}:
            updated.changes = [FileChange.model_validate(item) for item in payload]
        elif self.name == "verify":
            updated.verify = VerifyResult.model_validate(payload)
        elif self.name == "report":
            updated.reports = Reports.model_validate(payload)
        elif self.name == "pr":
            updated.pr = PRResult.model_validate(payload)
        else:
            raise PipelineConfigurationError(f"Unknown fixture stage: {self.name}")
        return updated


def build_fixture_pipeline(fixture_dir: Path) -> Pipeline:
    return Pipeline([FixtureStage(name, fixture_dir) for name in FIXTURE_STAGE_NAMES])


def run_migration(
    repo_path: Path,
    goal: str,
    *,
    pack_path: Optional[Path] = None,
    demo_mode: bool = False,
    stage_specs: Optional[Sequence[str]] = None,
    fixture_dir: Optional[Path] = None,
    services: Optional[Mapping[str, Any]] = None,
    on_stage: Optional[StageCallback] = None,
) -> MigrationRun:
    """Validate run-level input and execute the configured migration stages."""

    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise PipelineConfigurationError(f"Repository path is not a directory: {repo_path}")
    if not goal.strip():
        raise PipelineConfigurationError("Migration goal cannot be empty")
    resolved_pack = pack_path.expanduser().resolve() if pack_path else None
    if resolved_pack is not None and not resolved_pack.is_file():
        raise PipelineConfigurationError(f"Knowledge pack does not exist: {pack_path}")
    if fixture_dir is not None and stage_specs:
        raise PipelineConfigurationError(
            "Choose either --fixture-dir or custom --stage values, not both"
        )

    context = StageContext(
        repo_path=resolved_repo,
        goal=goal.strip(),
        pack_path=resolved_pack,
        demo_mode=demo_mode,
        services=dict(services or {}),
    )
    pipeline = (
        build_fixture_pipeline(fixture_dir.expanduser().resolve())
        if fixture_dir is not None
        else build_pipeline(stage_specs)
    )
    return pipeline.run(context, on_stage=on_stage)
