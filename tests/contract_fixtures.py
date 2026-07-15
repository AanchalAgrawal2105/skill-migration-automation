"""Contract-shaped test models used until Role A's schemas land."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Risk = Literal["auto", "review", "manual"]


class PlanStep(BaseModel):
    description: str
    risk: Risk


class MigrationPlan(BaseModel):
    steps: list[PlanStep]
    candidate_literals: list[str]


class RepoProfile(BaseModel):
    repo_path: str
    files: list[str]
    language: str = "python"


class UsageSite(BaseModel):
    path: str
    line: int
    match: str
    risk: Risk


class ScopeResult(BaseModel):
    sites: list[UsageSite]
    files_to_change: list[str]


class FileChange(BaseModel):
    path: str
    rationale: str
    diff: str
    syntax_ok: bool
    kind: Risk
    original: str = ""
    modified: str = ""
    syntax_error: str = ""


class MigrationRun(BaseModel):
    goal: str
    repo_path: str
    profile: RepoProfile
    plan: MigrationPlan | None = None
    scope: ScopeResult | None = None
    changes: list[FileChange] = Field(default_factory=list)
