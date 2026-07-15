import pytest
from pydantic import ValidationError

from app.schemas import MigrationRun, PlanStep, UsageSite


def test_changes_uses_independent_default_lists():
    first = MigrationRun()
    second = MigrationRun()

    first.changes.append(
        {
            "file": "example.py",
            "original": "old",
            "modified": "new",
            "diff": "diff",
            "rationale": "reason",
            "syntax_ok": True,
            "kind": "auto",
        }
    )

    assert second.changes == []


@pytest.mark.parametrize("risk", ["unknown", "critical", ""])
def test_plan_step_rejects_unknown_risks(risk):
    with pytest.raises(ValidationError):
        PlanStep(order=1, title="Test", description="Test", risk=risk)


def test_usage_site_rejects_unknown_change_kind():
    with pytest.raises(ValidationError):
        UsageSite(
            file="example.py",
            line=1,
            pattern="old",
            reason="deprecated",
            risk="low",
            kind="automatic",
        )


def test_migration_run_round_trips_as_json():
    run = MigrationRun()

    assert MigrationRun.model_validate_json(run.model_dump_json()) == run

