from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    guideline_id: str
    guideline_title: str | None = None
    source_json_path: str
    source_pdf_path: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page: str | None = None
    json_pointer: str | None = None
    field_name: str | None = None
    content_index: int | None = None


class SourceSnippet(BaseModel):
    snippet_id: str
    text: str
    snippet_type: str = "text"
    provenance: Provenance
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class GeneMention(BaseModel):
    gene_symbol: str
    associated_conditions: list[str] = Field(default_factory=list)
    occurrences: int | None = None
    context: str | None = None
    provenance: Provenance | None = None


class GuidelineMetadata(BaseModel):
    guideline_id: str
    family: str = "aha"
    title: str
    organization: str | None = None
    publication_date: str | None = None
    journal: str | None = None
    pages: str | None = None
    source_json_path: str
    source_pdf_path: str | None = None
    schema_hints: list[str] = Field(default_factory=list)


class GuidelineDocument(BaseModel):
    metadata: GuidelineMetadata
    snippets: list[SourceSnippet] = Field(default_factory=list)
    gene_mentions: list[GeneMention] = Field(default_factory=list)
    raw_summary: dict[str, Any] = Field(default_factory=dict)
