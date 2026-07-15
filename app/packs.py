"""Validated, migration-agnostic YAML knowledge packs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_PACK_BYTES = 256 * 1024
VALID_RISKS = {"low", "medium", "high", "auto", "review", "manual"}


class PackError(ValueError):
    """Raised when a knowledge pack is missing, unsafe, or malformed."""


class DetectConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    markers: list[str] = Field(default_factory=list)

    @field_validator("markers")
    @classmethod
    def nonempty_markers(cls, values: list[str]) -> list[str]:
        return _clean_literals(values, "detect.markers")


class BreakingChange(BaseModel):
    model_config = ConfigDict(extra="allow")

    pattern: str
    fix: Optional[str] = None
    risk: str = "review"

    @field_validator("pattern")
    @classmethod
    def nonempty_pattern(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("pattern must not be empty")
        return value

    @field_validator("risk")
    @classmethod
    def known_risk(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_RISKS:
            raise ValueError(f"risk must be one of {sorted(VALID_RISKS)}")
        return value


class DemoConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    fixture_id: Optional[str] = None


class KnowledgePack(BaseModel):
    """Known generic pack fields while preserving extension data."""

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    detect: DetectConfig = Field(default_factory=DetectConfig)
    breaking_changes: list[BreakingChange] = Field(default_factory=list)
    demo: DemoConfig = Field(default_factory=DemoConfig)

    def literals_with_risk(self) -> list[tuple[str, str]]:
        ordered: dict[str, str] = {}
        for marker in self.detect.markers:
            ordered.setdefault(marker, "review")
        for change in self.breaking_changes:
            ordered[change.pattern] = change.risk
        return list(ordered.items())

    def relevant_for(self, matched_literals: set[str]) -> dict[str, Any]:
        relevant = [
            change.model_dump(mode="json")
            for change in self.breaking_changes
            if change.pattern in matched_literals
        ]
        result = {
            "name": self.name,
            "detect": {
                "markers": [
                    marker for marker in self.detect.markers if marker in matched_literals
                ]
            },
            "breaking_changes": relevant,
        }
        if self.model_extra and "transform" in self.model_extra:
            result["transform"] = self.model_extra["transform"]
        return result


def load_pack(path: str | Path | None) -> KnowledgePack | None:
    if path is None:
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise PackError(f"knowledge pack does not exist: {candidate}")
    if candidate.stat().st_size > MAX_PACK_BYTES:
        raise PackError(f"knowledge pack exceeds {MAX_PACK_BYTES} bytes")
    try:
        raw = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise PackError(f"could not read knowledge pack: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise PackError("knowledge pack root must be a mapping")
    return coerce_pack(raw)


def coerce_pack(value: KnowledgePack | Mapping[str, Any] | None) -> KnowledgePack | None:
    if value is None or isinstance(value, KnowledgePack):
        return value
    if not isinstance(value, Mapping):
        raise PackError("knowledge pack root must be a mapping")
    try:
        return KnowledgePack.model_validate(dict(value))
    except Exception as exc:
        raise PackError(f"invalid knowledge pack: {exc}") from exc


def _clean_literals(values: list[str], field_name: str) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        if not value:
            raise ValueError(f"{field_name} values must not be empty")
        if value not in seen:
            cleaned.append(value)
            seen.add(value)
    return cleaned
