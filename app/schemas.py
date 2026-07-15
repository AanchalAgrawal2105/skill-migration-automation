from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChangeKind(StrEnum):
    auto = "auto"
    manual = "manual"
    skipped = "skipped"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    review = "review"


class CommandSpec(BaseModel):
    argv: list[str]
    cwd: str | None = None
    timeout_seconds: int = 60
    description: str


class CommandResult(BaseModel):
    command: list[str]
    cwd: str
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    passed: bool = False


class RepoProfile(BaseModel):
    repo_path: str
    rollback_anchor: str
    languages: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    manifests: dict[str, Any] = Field(default_factory=dict)
    dependencies: dict[str, str] = Field(default_factory=dict)
    syntax_commands: dict[str, CommandSpec] = Field(default_factory=dict)
    test_commands: list[CommandSpec] = Field(default_factory=list)


class PlanStep(BaseModel):
    title: str
    details: str
    risk: RiskLevel = RiskLevel.review


class MigrationPlan(BaseModel):
    summary: str
    steps: list[PlanStep] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class UsageSite(BaseModel):
    path: str
    line: int
    snippet: str
    risk: RiskLevel = RiskLevel.review


class ScopeResult(BaseModel):
    files_to_change: list[str] = Field(default_factory=list)
    usage_sites: list[UsageSite] = Field(default_factory=list)


class FileChange(BaseModel):
    path: str
    kind: ChangeKind
    rationale: str = ""
    diff: str = ""
    syntax_ok: bool | None = None


class VerifyResult(BaseModel):
    passed: bool
    commands: list[CommandResult] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)


class MigrationRun(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    repo_path: Path
    goal: str = ""
    profile: RepoProfile | None = None
    plan: MigrationPlan | None = None
    scope: ScopeResult | None = None
    changes: list[FileChange] = Field(default_factory=list)
    verify: VerifyResult | None = None
    reports: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
