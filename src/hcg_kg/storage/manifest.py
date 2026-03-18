from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from hcg_kg.utils import dump_json, load_json


class ManifestEntry(BaseModel):
    doc_id: str
    source_json_path: str
    source_pdf_path: str | None = None
    family: str = "aha"
    normalized_path: str | None = None
    stages: dict[str, str] = Field(
        default_factory=lambda: {
            "ingest": "pending",
            "normalize": "pending",
            "build_graph": "pending",
            "build_embeddings": "pending",
        }
    )
    notes: list[str] = Field(default_factory=list)


class ManifestStore:
    def __init__(self, path: Any) -> None:
        self.path = path

    def load(self) -> dict[str, ManifestEntry]:
        if not self.path.exists():
            return {}
        raw = load_json(self.path)
        return {
            item["doc_id"]: ManifestEntry.model_validate(item)
            for item in raw
        }

    def save(self, entries: dict[str, ManifestEntry]) -> None:
        ordered = sorted(entries.values(), key=lambda item: item.doc_id)
        dump_json([entry.model_dump(mode="json") for entry in ordered], self.path)

    def upsert(self, entry: ManifestEntry) -> ManifestEntry:
        entries = self.load()
        entries[entry.doc_id] = entry
        self.save(entries)
        return entry

    def update(self, doc_id: str, **fields: Any) -> ManifestEntry:
        entries = self.load()
        entry = entries[doc_id]
        updated = entry.model_copy(update=fields)
        entries[doc_id] = updated
        self.save(entries)
        return updated
