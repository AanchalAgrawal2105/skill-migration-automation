"""Validate a local repository and establish the initial run profile."""

from app.schemas import MigrationRun, RepoProfile
from app.stages.base import StageContext


def run(migration: MigrationRun, context: StageContext) -> MigrationRun:
    root = context.repo_path.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Repository path is not a directory: {root}")
    updated = migration.model_copy(deep=True)
    updated.profile = RepoProfile(
        repo_id=root.name,
        root_path=str(root),
        rollback_anchor="pending-profile",
        languages=[],
        manifests={},
        dependencies={},
        build_cmd=None,
        test_cmd=None,
        syntax_cmd={},
        file_tree=[],
    )
    return updated

