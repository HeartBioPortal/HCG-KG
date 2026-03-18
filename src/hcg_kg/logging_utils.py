from __future__ import annotations

import logging
from pathlib import Path

from hcg_kg.utils import ensure_dir

try:
    from rich.logging import RichHandler
except ImportError:  # pragma: no cover - optional runtime nicety
    RichHandler = None  # type: ignore[assignment]


def configure_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Configure console and optional file logging."""
    if RichHandler is not None:
        handlers: list[logging.Handler] = [RichHandler(rich_tracebacks=True)]
    else:
        handlers = [logging.StreamHandler()]
    if log_file is not None:
        ensure_dir(log_file.parent)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        handlers=handlers,
        force=True,
    )
