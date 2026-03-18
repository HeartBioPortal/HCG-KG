from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from hcg_kg.config.models import ProjectSettings
from hcg_kg.utils import load_json, slugify


class RawDocumentLoader:
    def __init__(self, settings: ProjectSettings) -> None:
        self.settings = settings

    def discover(self, input_glob: str | None = None, limit: int | None = None) -> list[Path]:
        pattern = self.settings.resolve_glob(input_glob or self.settings.paths.raw_input_glob)
        files = [Path(item) for item in sorted(glob.glob(pattern))]
        return files if limit is None else files[:limit]

    def load(self, path: Path) -> dict[str, Any]:
        data = load_json(path)
        if not isinstance(data, dict):
            raise ValueError(f"Expected top-level object in {path}")
        return data

    def derive_doc_id(self, path: Path) -> str:
        return slugify(path.stem.removesuffix("_aggregated"))

    def resolve_pdf_path(self, json_path: Path) -> Path | None:
        source_pdf_dir = self.settings.resolve_path(self.settings.paths.source_pdf_dir)
        if source_pdf_dir is None or not source_pdf_dir.exists():
            return None
        doc_stem = json_path.stem.removesuffix("_aggregated")
        exact = list(source_pdf_dir.rglob(f"{doc_stem}.pdf"))
        if exact:
            return exact[0]
        folder_match = list(source_pdf_dir.rglob(f"{doc_stem}/{doc_stem}.pdf"))
        return folder_match[0] if folder_match else None
