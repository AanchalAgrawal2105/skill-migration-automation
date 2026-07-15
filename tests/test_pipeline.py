from pathlib import Path

import pytest

from app.pipeline import (
    CallableStage,
    Pipeline,
    PipelineConfigurationError,
    PipelineExecutionError,
    StageStatus,
    build_fixture_pipeline,
    load_stage,
    run_migration,
)
from app.schemas import MigrationPlan
from app.stages.base import StageContext


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DEMO_REPO = ROOT / "demo" / "sample-repo"


def context():
    return StageContext(repo_path=DEMO_REPO, goal="A technology-neutral goal")


def test_fixture_pipeline_populates_every_contract():
    run = build_fixture_pipeline(FIXTURES).run(context())

    assert run.profile is not None
    assert run.plan is not None
    assert run.scope is not None
    assert run.changes
    assert run.verify is not None and run.verify.passed
    assert run.reports is not None
    assert run.pr is not None


def test_pipeline_emits_ordered_snapshots():
    def add_plan(run, stage_context):
        run.plan = MigrationPlan(
            goal=stage_context.goal,
            summary="A generic plan",
            steps=[],
        )
        return run

    events = []
    pipeline = Pipeline([CallableStage("plan", add_plan)])
    result = pipeline.run(context(), on_stage=events.append)

    assert [event.status for event in events] == [
        StageStatus.STARTED,
        StageStatus.COMPLETED,
    ]
    assert events[0].run.plan is None
    assert events[1].run.plan == result.plan

    result.plan.summary = "mutated later"
    assert events[1].run.plan.summary == "A generic plan"


def test_failure_preserves_last_successful_run():
    def succeed(run, stage_context):
        run.plan = MigrationPlan(goal=stage_context.goal, summary="Saved", steps=[])
        return run

    def fail(run, stage_context):
        del run, stage_context
        raise RuntimeError("verifier unavailable")

    events = []
    pipeline = Pipeline(
        [CallableStage("plan", succeed), CallableStage("verify", fail)]
    )

    with pytest.raises(PipelineExecutionError) as raised:
        pipeline.run(context(), on_stage=events.append)

    assert raised.value.stage == "verify"
    assert raised.value.run.plan.summary == "Saved"
    assert events[-1].status == StageStatus.FAILED
    assert events[-1].error == "verifier unavailable"


def test_pipeline_rejects_duplicate_stage_names():
    stage = CallableStage("same", lambda run, stage_context: run)

    with pytest.raises(PipelineConfigurationError, match="duplicates: same"):
        Pipeline([stage, stage])


def test_pipeline_rejects_non_run_return_value():
    pipeline = Pipeline([CallableStage("bad", lambda run, stage_context: None)])

    with pytest.raises(PipelineExecutionError, match="expected MigrationRun"):
        pipeline.run(context())


def test_runtime_stage_loader_uses_module_name_as_stage_name():
    stage = load_stage("app.stages.plan:run")

    assert stage.name == "plan"


def test_run_migration_validates_inputs(tmp_path):
    with pytest.raises(PipelineConfigurationError, match="not a directory"):
        run_migration(tmp_path / "missing", "goal", fixture_dir=FIXTURES)

    with pytest.raises(PipelineConfigurationError, match="cannot be empty"):
        run_migration(DEMO_REPO, "  ", fixture_dir=FIXTURES)


def test_run_migration_fixture_mode_is_end_to_end():
    run = run_migration(
        DEMO_REPO,
        "Upgrade any technology",
        fixture_dir=FIXTURES,
    )

    assert run.verify is not None and run.verify.passed is True
