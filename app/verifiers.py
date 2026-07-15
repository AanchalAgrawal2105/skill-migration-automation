from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.schemas import CommandResult, CommandSpec


MAX_LOG_CHARS = 8_000
VENDORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
    "venv",
}


def truncate_log(value: str, limit: int = MAX_LOG_CHARS) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated]"


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def is_probably_text(path: Path, sample_size: int = 4096) -> bool:
    try:
        data = path.read_bytes()[:sample_size]
    except OSError:
        return False
    if b"\0" in data:
        return False
    return True


@dataclass(frozen=True)
class CommandRunner:
    repo_root: Path
    default_timeout_seconds: int = 60

    def run(self, spec: CommandSpec) -> CommandResult:
        cwd = (self.repo_root / spec.cwd).resolve() if spec.cwd else self.repo_root.resolve()
        if not is_relative_to(cwd, self.repo_root):
            raise ValueError(f"Command cwd escapes repository: {cwd}")

        timeout = spec.timeout_seconds or self.default_timeout_seconds
        try:
            completed = subprocess.run(
                spec.argv,
                cwd=cwd,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=spec.argv,
                cwd=str(cwd),
                returncode=None,
                stdout=truncate_log(exc.stdout or ""),
                stderr=truncate_log(exc.stderr or ""),
                timed_out=True,
                passed=False,
            )

        return CommandResult(
            command=spec.argv,
            cwd=str(cwd),
            returncode=completed.returncode,
            stdout=truncate_log(completed.stdout),
            stderr=truncate_log(completed.stderr),
            timed_out=False,
            passed=completed.returncode == 0,
        )


def python_syntax_command(relative_file: str) -> CommandSpec:
    return CommandSpec(
        argv=["python3", "-m", "py_compile", relative_file],
        timeout_seconds=30,
        description=f"Compile {relative_file}",
    )


def pytest_command() -> CommandSpec:
    return CommandSpec(
        argv=["python3", "-m", "pytest", "-q"],
        timeout_seconds=60,
        description="Run pytest suite",
    )

