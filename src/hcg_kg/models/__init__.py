"""Typed models used across the pipeline."""

from hcg_kg.models.documents import GeneMention, GuidelineDocument, GuidelineMetadata, Provenance, SourceSnippet
from hcg_kg.models.graph import ExtractionResult, GraphEdge, GraphNode, GraphSubgraph
from hcg_kg.models.query import (
    GeneMatch,
    GeneQueryResponse,
    GuidelineReference,
    RecommendationResult,
    RelatedEntity,
    SupportingSnippet,
)

__all__ = [
    "ExtractionResult",
    "GeneMatch",
    "GeneMention",
    "GeneQueryResponse",
    "GraphEdge",
    "GraphNode",
    "GraphSubgraph",
    "GuidelineDocument",
    "GuidelineMetadata",
    "GuidelineReference",
    "Provenance",
    "RecommendationResult",
    "RelatedEntity",
    "SourceSnippet",
    "SupportingSnippet",
]
