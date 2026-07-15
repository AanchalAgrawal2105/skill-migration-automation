"""Frozen data contracts shared by every migration stage.

Changes to these public models are integration changes and must be coordinated
across all stage owners. Internal stage-specific models should live beside the
stage that owns them.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Risk = Literal["low", "medium", "high"]
ChangeKind = Literal["auto", "review", "manual"]


class RepoProfile(BaseModel):
    repo_id: str
    root_path: str
    rollback_anchor: str
    languages: List[str]
    manifests: Dict[str, str]
    dependencies: Dict[str, str]
    build_cmd: Optional[str]
    test_cmd: Optional[str]
    syntax_cmd: Dict[str, str]
    file_tree: List[str]


class PlanStep(BaseModel):
    order: int
    title: str
    description: str
    risk: Risk


class MigrationPlan(BaseModel):
    goal: str
    summary: str
    steps: List[PlanStep]


class UsageSite(BaseModel):
    file: str
    line: int
    pattern: str
    reason: str
    risk: Risk
    kind: ChangeKind


class ScopeResult(BaseModel):
    sites: List[UsageSite]
    files_to_change: List[str]


class FileChange(BaseModel):
    file: str
    original: str
    modified: str
    diff: str
    rationale: str
    syntax_ok: bool
    kind: ChangeKind


class VerifyResult(BaseModel):
    passed: bool
    build_log: str
    test_log: str
    failed_files: List[str]


class Reports(BaseModel):
    migration_docs: str
    risk_report: str
    rollback_plan: str


class PRResult(BaseModel):
    branch: str
    pr_url: Optional[str]
    committed: bool


class MigrationRun(BaseModel):
    profile: Optional[RepoProfile] = None
    plan: Optional[MigrationPlan] = None
    scope: Optional[ScopeResult] = None
    changes: List[FileChange] = Field(default_factory=list)
    verify: Optional[VerifyResult] = None
    reports: Optional[Reports] = None
    pr: Optional[PRResult] = None

