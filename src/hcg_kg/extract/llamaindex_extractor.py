from __future__ import annotations

import logging
import re
from typing import Callable, Literal

from pydantic import BaseModel, Field

from hcg_kg.config.models import ProjectSettings
from hcg_kg.extract.chunker import chunk_snippets
from hcg_kg.extract.heuristic import HeuristicBiomedicalExtractor
from hcg_kg.models.documents import GuidelineDocument, SourceSnippet
from hcg_kg.models.graph import ExtractionResult, GraphEdge, GraphNode
from hcg_kg.utils import make_id, stable_hash

try:  # pragma: no cover - optional dependency
    from llama_index.core.prompts import PromptTemplate
    from llama_index.llms.huggingface import HuggingFaceLLM
except ImportError:  # pragma: no cover - optional dependency
    PromptTemplate = None  # type: ignore[assignment]
    HuggingFaceLLM = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


class SnippetLLMExtraction(BaseModel):
    genes: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    biomarkers: list[str] = Field(default_factory=list)
    drugs: list[str] = Field(default_factory=list)
    recommendation_text: str | None = None
    recommendation_relation: Literal["RECOMMENDS", "CONTRAINDICATED_FOR", "NONE"] = "NONE"
    evidence_class: str | None = None
    evidence_level: str | None = None
    confidence: float = 0.0


class LlamaIndexBiomedicalExtractor:
    """LLM-backed extractor using LlamaIndex with a local Hugging Face model."""

    def __init__(self, settings: ProjectSettings) -> None:
        if HuggingFaceLLM is None or PromptTemplate is None:  # pragma: no cover - optional dependency
            raise ImportError(
                "Install hcg-kg with llama-index-llms-huggingface to use the LlamaIndex extractor."
            )
        self.settings = settings
        self.helper = HeuristicBiomedicalExtractor(settings)
        model_name = settings.models.model_name
        tokenizer_name = settings.models.tokenizer_name or model_name
        generate_kwargs = dict(settings.models.generate_kwargs)
        if settings.models.temperature <= 0:
            generate_kwargs.setdefault("do_sample", False)
            generate_kwargs.pop("temperature", None)
        else:
            generate_kwargs.setdefault("do_sample", True)
            generate_kwargs.setdefault("temperature", settings.models.temperature)
        self.llm = HuggingFaceLLM(
            model_name=model_name,
            tokenizer_name=tokenizer_name,
            context_window=settings.models.context_window,
            max_new_tokens=settings.models.max_new_tokens,
            device_map=settings.models.device_map,
            model_kwargs=settings.models.model_kwargs,
            generate_kwargs=generate_kwargs,
        )
        self.prompt = PromptTemplate(
            "You extract biomedical guideline facts as strict JSON.\n"
            "Return only a JSON object matching the requested schema.\n"
            "If the snippet is not gene-relevant, return empty lists and null recommendation fields.\n\n"
            "Guideline title: {guideline_title}\n"
            "Section path: {section_path}\n"
            "Page: {page}\n"
            "Candidate genes: {candidate_genes}\n"
            "Candidate conditions: {candidate_conditions}\n"
            "Candidate biomarkers: {candidate_biomarkers}\n"
            "Candidate drugs/interventions: {candidate_drugs}\n\n"
            "Snippet:\n{snippet_text}\n"
        )

    def extract(self, document: GuidelineDocument) -> ExtractionResult:
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}

        def add_node(node: GraphNode) -> None:
            existing = nodes.get(node.node_id)
            if existing is None:
                nodes[node.node_id] = node
                return
            merged = {**existing.properties, **node.properties}
            nodes[node.node_id] = existing.model_copy(update={"properties": merged})

        def add_edge(edge: GraphEdge) -> None:
            edges.setdefault(edge.edge_id, edge)

        guideline = document.metadata
        guideline_node = GraphNode(
            node_id=f"guideline:{guideline.guideline_id}",
            label="Guideline",
            name=guideline.title,
            properties={
                "guideline_id": guideline.guideline_id,
                "family": guideline.family,
                "organization": guideline.organization,
                "publication_date": guideline.publication_date,
                "journal": guideline.journal,
                "pages": guideline.pages,
                "source_json_path": guideline.source_json_path,
                "source_pdf_path": guideline.source_pdf_path,
            },
        )
        add_node(guideline_node)

        chunked_snippets = chunk_snippets(
            document.snippets,
            chunk_size=self.settings.extraction.chunk_size,
            overlap=self.settings.extraction.chunk_overlap,
        )
        snippets_by_content_index: dict[int, list[SourceSnippet]] = {}
        for snippet in chunked_snippets:
            if snippet.provenance.content_index is not None:
                snippets_by_content_index.setdefault(snippet.provenance.content_index, []).append(snippet)

        candidate_genes = sorted({mention.gene_symbol for mention in document.gene_mentions})
        gene_linked_content_indices = {
            mention.provenance.content_index
            for mention in document.gene_mentions
            if mention.provenance and mention.provenance.content_index is not None
        }
        candidate_conditions = sorted(
            {
                *self.settings.extraction.condition_terms,
                *[condition for mention in document.gene_mentions for condition in mention.associated_conditions],
            }
        )
        candidate_biomarkers = sorted(self.settings.extraction.biomarker_terms)
        candidate_drugs = sorted(self.settings.extraction.drug_terms)

        for snippet in chunked_snippets:
            snippet_node = GraphNode(
                node_id=snippet.snippet_id,
                label="Snippet",
                name=snippet.text[:80],
                properties={
                    "text": snippet.text,
                    "snippet_type": snippet.snippet_type,
                    "guideline_id": guideline.guideline_id,
                    "guideline_title": guideline.title,
                    "section_path": snippet.provenance.section_path,
                    "page": snippet.provenance.page,
                    "source_json_path": snippet.provenance.source_json_path,
                    "source_pdf_path": snippet.provenance.source_pdf_path,
                    "json_pointer": snippet.provenance.json_pointer,
                },
            )
            add_node(snippet_node)
            add_edge(
                GraphEdge(
                    edge_id=make_id("edge", snippet.snippet_id, "FROM_GUIDELINE", guideline_node.node_id),
                    source_id=snippet.snippet_id,
                    target_id=guideline_node.node_id,
                    relation="FROM_GUIDELINE",
                    properties={"guideline_id": guideline.guideline_id},
                )
            )
            section_id = self.helper._section_node_id(guideline.guideline_id, snippet.provenance.section_path)
            section_name = " > ".join(snippet.provenance.section_path) if snippet.provenance.section_path else "Document"
            add_node(
                GraphNode(
                    node_id=section_id,
                    label="Section",
                    name=section_name,
                    properties={
                        "guideline_id": guideline.guideline_id,
                        "section_path": snippet.provenance.section_path,
                    },
                )
            )
            add_edge(
                GraphEdge(
                    edge_id=make_id("edge", snippet.snippet_id, "LOCATED_IN_SECTION", section_id),
                    source_id=snippet.snippet_id,
                    target_id=section_id,
                    relation="LOCATED_IN_SECTION",
                    properties={"page": snippet.provenance.page},
                )
            )

        # Keep upstream parsed gene mentions as a strong prior.
        for mention in document.gene_mentions:
            gene_node = self.helper._gene_node(mention.gene_symbol)
            add_node(gene_node)
            if mention.provenance and mention.provenance.content_index is not None:
                for snippet in snippets_by_content_index.get(mention.provenance.content_index, []):
                    add_edge(
                        GraphEdge(
                            edge_id=make_id("edge", gene_node.node_id, "GENE_MENTIONED_IN", snippet.snippet_id),
                            source_id=gene_node.node_id,
                            target_id=snippet.snippet_id,
                            relation="GENE_MENTIONED_IN",
                            properties={"source": "raw_gene_mentions"},
                        )
                    )
            for condition in mention.associated_conditions:
                condition_node = self.helper._entity_node("Condition", condition)
                add_node(condition_node)
                add_edge(
                    GraphEdge(
                        edge_id=make_id(
                            "edge",
                            gene_node.node_id,
                            "ASSOCIATED_WITH_CONDITION",
                            condition_node.node_id,
                            mention.context or "",
                        ),
                        source_id=gene_node.node_id,
                        target_id=condition_node.node_id,
                        relation="ASSOCIATED_WITH_CONDITION",
                        properties={"context": mention.context, "source": "raw_gene_mentions"},
                    )
                )

        processed_snippets = self._select_candidate_snippets(
            chunked_snippets,
            candidate_genes,
            gene_linked_content_indices,
        )
        for snippet in processed_snippets:
            extraction = self._extract_snippet(
                snippet=snippet,
                guideline_title=guideline.title,
                candidate_genes=candidate_genes,
                candidate_conditions=candidate_conditions,
                candidate_biomarkers=candidate_biomarkers,
                candidate_drugs=candidate_drugs,
            )
            self._apply_snippet_extraction(add_node, add_edge, snippet, extraction)

        return ExtractionResult(nodes=list(nodes.values()), edges=list(edges.values()))

    def _select_candidate_snippets(
        self,
        snippets: list[SourceSnippet],
        candidate_genes: list[str],
        gene_linked_content_indices: set[int],
    ) -> list[SourceSnippet]:
        selected: list[SourceSnippet] = []
        gene_patterns = [re.compile(rf"\b{re.escape(gene)}\b", flags=re.IGNORECASE) for gene in candidate_genes]
        for snippet in snippets:
            if snippet.snippet_type == "recommendation":
                selected.append(snippet)
                continue
            if any(pattern.search(snippet.text) for pattern in gene_patterns):
                selected.append(snippet)
                continue
            if (
                snippet.provenance.content_index is not None
                and snippet.provenance.content_index in gene_linked_content_indices
            ):
                selected.append(snippet)
        # Fallback to all snippets if the candidate filter becomes too restrictive.
        return selected or snippets

    def _extract_snippet(
        self,
        snippet: SourceSnippet,
        guideline_title: str,
        candidate_genes: list[str],
        candidate_conditions: list[str],
        candidate_biomarkers: list[str],
        candidate_drugs: list[str],
    ) -> SnippetLLMExtraction:
        try:
            return self.llm.structured_predict(
                SnippetLLMExtraction,
                self.prompt,
                guideline_title=guideline_title,
                section_path=" > ".join(snippet.provenance.section_path) or "Document",
                page=snippet.provenance.page or "unknown",
                candidate_genes=", ".join(candidate_genes) or "none",
                candidate_conditions=", ".join(candidate_conditions[:40]) or "none",
                candidate_biomarkers=", ".join(candidate_biomarkers[:40]) or "none",
                candidate_drugs=", ".join(candidate_drugs[:40]) or "none",
                snippet_text=snippet.text,
            )
        except Exception as exc:  # pragma: no cover - runtime dependent
            LOGGER.warning("LLM extraction failed for %s: %s", snippet.snippet_id, exc)
            return SnippetLLMExtraction()

    def _apply_snippet_extraction(
        self,
        add_node: Callable[[GraphNode], None],
        add_edge: Callable[[GraphEdge], None],
        snippet: SourceSnippet,
        extraction: SnippetLLMExtraction,
    ) -> None:
        genes = [gene.upper() for gene in extraction.genes if gene.strip()]
        conditions = [condition.strip() for condition in extraction.conditions if condition.strip()]
        biomarkers = [item.strip() for item in extraction.biomarkers if item.strip()]
        drugs = [item.strip() for item in extraction.drugs if item.strip()]

        for gene_symbol in genes:
            gene_node = self.helper._gene_node(gene_symbol)
            add_node(gene_node)
            add_edge(
                GraphEdge(
                    edge_id=make_id("edge", gene_node.node_id, "GENE_MENTIONED_IN", snippet.snippet_id),
                    source_id=gene_node.node_id,
                    target_id=snippet.snippet_id,
                    relation="GENE_MENTIONED_IN",
                    properties={"source": "llamaindex"},
                )
            )
            for condition in conditions:
                condition_node = self.helper._entity_node("Condition", condition)
                add_node(condition_node)
                add_edge(
                    GraphEdge(
                        edge_id=make_id(
                            "edge",
                            gene_node.node_id,
                            "ASSOCIATED_WITH_CONDITION",
                            condition_node.node_id,
                            snippet.snippet_id,
                        ),
                        source_id=gene_node.node_id,
                        target_id=condition_node.node_id,
                        relation="ASSOCIATED_WITH_CONDITION",
                        properties={"snippet_id": snippet.snippet_id, "source": "llamaindex"},
                    )
                )
            for biomarker in biomarkers:
                biomarker_node = self.helper._entity_node("Biomarker", biomarker)
                add_node(biomarker_node)
                add_edge(
                    GraphEdge(
                        edge_id=make_id(
                            "edge",
                            gene_node.node_id,
                            "CO_MENTIONED_WITH",
                            biomarker_node.node_id,
                            snippet.snippet_id,
                        ),
                        source_id=gene_node.node_id,
                        target_id=biomarker_node.node_id,
                        relation="CO_MENTIONED_WITH",
                        properties={"snippet_id": snippet.snippet_id, "source": "llamaindex"},
                    )
                )

        recommendation_text = (extraction.recommendation_text or "").strip()
        if not recommendation_text:
            return
        recommendation_node = GraphNode(
            node_id=f"recommendation:{stable_hash(snippet.provenance.guideline_id, recommendation_text[:200])}",
            label="Recommendation",
            name=recommendation_text[:80],
            properties={
                "text": recommendation_text,
                "guideline_id": snippet.provenance.guideline_id,
                "section_path": snippet.provenance.section_path,
                "page": snippet.provenance.page,
                "evidence_class": extraction.evidence_class,
                "evidence_level": extraction.evidence_level,
                "source": "llamaindex",
                "confidence": extraction.confidence,
            },
        )
        add_node(recommendation_node)
        add_edge(
            GraphEdge(
                edge_id=make_id("edge", recommendation_node.node_id, "SUPPORTED_BY_SNIPPET", snippet.snippet_id),
                source_id=recommendation_node.node_id,
                target_id=snippet.snippet_id,
                relation="SUPPORTED_BY_SNIPPET",
                properties={"snippet_id": snippet.snippet_id, "source": "llamaindex"},
            )
        )

        if extraction.evidence_class:
            class_node = self.helper._entity_node("EvidenceClass", extraction.evidence_class)
            add_node(class_node)
            add_edge(
                GraphEdge(
                    edge_id=make_id("edge", recommendation_node.node_id, "HAS_EVIDENCE_CLASS", class_node.node_id),
                    source_id=recommendation_node.node_id,
                    target_id=class_node.node_id,
                    relation="HAS_EVIDENCE_CLASS",
                    properties={"source": "llamaindex"},
                )
            )
        if extraction.evidence_level:
            level_node = self.helper._entity_node("EvidenceLevel", extraction.evidence_level)
            add_node(level_node)
            add_edge(
                GraphEdge(
                    edge_id=make_id("edge", recommendation_node.node_id, "HAS_EVIDENCE_LEVEL", level_node.node_id),
                    source_id=recommendation_node.node_id,
                    target_id=level_node.node_id,
                    relation="HAS_EVIDENCE_LEVEL",
                    properties={"source": "llamaindex"},
                )
            )

        relation = extraction.recommendation_relation
        if relation not in {"RECOMMENDS", "CONTRAINDICATED_FOR"}:
            relation = "CONTRAINDICATED_FOR" if self.helper._is_contraindicated(recommendation_text) else "RECOMMENDS"
        for gene_symbol in genes:
            gene_node = self.helper._gene_node(gene_symbol)
            add_edge(
                GraphEdge(
                    edge_id=make_id(
                        "edge",
                        gene_node.node_id,
                        "REFERENCED_IN_RECOMMENDATION",
                        recommendation_node.node_id,
                    ),
                    source_id=gene_node.node_id,
                    target_id=recommendation_node.node_id,
                    relation="REFERENCED_IN_RECOMMENDATION",
                    properties={"snippet_id": snippet.snippet_id, "source": "llamaindex"},
                )
            )
        for drug in drugs:
            drug_node = self.helper._entity_node("Drug", drug)
            add_node(drug_node)
            add_edge(
                GraphEdge(
                    edge_id=make_id("edge", recommendation_node.node_id, relation, drug_node.node_id),
                    source_id=recommendation_node.node_id,
                    target_id=drug_node.node_id,
                    relation=relation,
                    properties={"snippet_id": snippet.snippet_id, "source": "llamaindex"},
                )
            )
