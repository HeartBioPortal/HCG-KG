from __future__ import annotations

from pydantic import BaseModel, Field


class GeneMatch(BaseModel):
    gene_symbol: str
    score: float
    match_type: str


class GuidelineReference(BaseModel):
    guideline_id: str
    title: str


class RelatedEntity(BaseModel):
    name: str
    node_id: str
    snippet_ids: list[str] = Field(default_factory=list)


class SupportingSnippet(BaseModel):
    snippet_id: str
    text: str
    guideline_title: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page: str | None = None
    source_json_path: str
    source_pdf_path: str | None = None


class RecommendationResult(BaseModel):
    recommendation_id: str
    text: str
    evidence_class: str | None = None
    evidence_level: str | None = None
    drugs: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    biomarkers: list[str] = Field(default_factory=list)
    supporting_snippet_ids: list[str] = Field(default_factory=list)


class GeneQueryResponse(BaseModel):
    query: str
    resolved_gene: str | None = None
    match_type: str | None = None
    matches: list[GeneMatch] = Field(default_factory=list)
    guidelines: list[GuidelineReference] = Field(default_factory=list)
    conditions: list[RelatedEntity] = Field(default_factory=list)
    biomarkers: list[RelatedEntity] = Field(default_factory=list)
    drugs: list[RelatedEntity] = Field(default_factory=list)
    recommendations: list[RecommendationResult] = Field(default_factory=list)
    supporting_snippets: list[SupportingSnippet] = Field(default_factory=list)
    summary: str | None = None
