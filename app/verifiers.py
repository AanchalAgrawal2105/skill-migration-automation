"""Safe, technology-neutral verifier command registry and runner."""

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
from typing import Optional, Sequence


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

VERIFIERS = {
    "python": {
        "syntax": "python3 -m py_compile {file}",
        "build": "python3 -m pip install -r requirements.txt",
        "test": "python3 -m pytest -q",
    },
    "javascript": {
        "syntax": "node --check {file}",
        "build": "npm install",
        "test": "npm test",
    },
    "typescript": {
        "syntax": "npx tsc --noEmit",
        "build": "npm install",
        "test": "npm test",
    },
    "go": {
        "syntax": "gofmt -e {file}",
        "build": "go build ./...",
        "test": "go test ./...",
    },
    "java": {
        "syntax": "javac {file}",
        "build": "mvn -q compile",
        "test": "mvn -q test",
    },
}


@dataclass(frozen=True)
class CommandResult:
    command: Sequence[str]
    returncode: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool

    @property
    def passed(self) -> bool:
        return not self.timed_out and self.returncode == 0


def truncate_log(value: str, limit: int = MAX_LOG_CHARS) -> str:
    return value if len(value) <= limit else value[:limit] + "\n...[truncated]"


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
    return b"\0" not in data


@dataclass(frozen=True)
class CommandRunner:
    repo_root: Path
    default_timeout_seconds: int = 60

    def run(self, command: str, *, timeout_seconds: Optional[int] = None) -> CommandResult:
        """Execute a preselected command without invoking a shell."""

        argv = shlex.split(command)
        if not argv:
            raise ValueError("Verifier command cannot be empty")
        forbidden = {"&&", "||", ";", "|", ">", ">>", "<"}
        if any(token in forbidden for token in argv):
            raise ValueError("Shell control operators are not allowed in verifier commands")
        root = self.repo_root.resolve()
        try:
            completed = subprocess.run(
                argv,
                cwd=root,
                text=True,
                capture_output=True,
                timeout=timeout_seconds or self.default_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=argv,
                returncode=None,
                stdout=truncate_log(_to_text(exc.stdout)),
                stderr=truncate_log(_to_text(exc.stderr)),
                timed_out=True,
            )
        return CommandResult(
            command=argv,
            returncode=completed.returncode,
            stdout=truncate_log(completed.stdout),
            stderr=truncate_log(completed.stderr),
            timed_out=False,
        )


def _to_text(value: object) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else str(value)
