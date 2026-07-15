from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_pack(pack_path: Path | None) -> dict[str, Any] | None:
    if pack_path is None:
        return None

    path = pack_path.expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Knowledge pack does not exist or is not a file: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError("Knowledge pack must contain a YAML mapping at the top level")
    return data
