from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    """Create a stable ASCII slug for ids and filenames."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower())
    collapsed = re.sub(r"-{2,}", "-", cleaned)
    return collapsed.strip("-") or "unknown"


def stable_hash(*parts: str) -> str:
    payload = "::".join(part.strip() for part in parts if part.strip())
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def make_id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{stable_hash(prefix, *parts)}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data: Any, path: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def to_pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=json_default)
