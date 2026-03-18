from __future__ import annotations

import re
from typing import Iterable

from hcg_kg.config.models import ProjectSettings
from hcg_kg.extract.chunker import chunk_snippets
from hcg_kg.models.documents import GuidelineDocument, SourceSnippet
from hcg_kg.models.graph import ExtractionResult, GraphEdge, GraphNode
from hcg_kg.utils import make_id, stable_hash

EVIDENCE_CLASS_PATTERN = re.compile(
    r"\bClass(?:\s+of\s+Recommendation)?\s+(I{1,3}|IV|1|2a|2b|3)\b",
    flags=re.IGNORECASE,
)
EVIDENCE_LEVEL_PATTERN = re.compile(
    r"\b(?:Level\s+of\s+Evidence|LOE)\s+([A-C](?:-[A-Z]+)?)\b",
    flags=re.IGNORECASE,
)
RECOMMENDATION_HINT_PATTERN = re.compile(
    r"\b(is recommended|should|should not|is reasonable|may be considered|contraindicated|no benefit|harm)\b",
    flags=re.IGNORECASE,
)


class HeuristicBiomedicalExtractor:
    """Heuristic extraction with strong provenance guarantees."""

    def __init__(self, settings: ProjectSettings) -> None:
        self.settings = settings
        self._configured_genes = self._load_gene_lexicon(settings.extraction.gene_lexicon_path)

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
            if edge.edge_id not in edges:
                edges[edge.edge_id] = edge

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

        genes_from_mentions = sorted({mention.gene_symbol for mention in document.gene_mentions})
        genes_from_config = self._configured_genes
        genes = sorted({*genes_from_mentions, *genes_from_config})
        conditions = sorted(
            {
                *self.settings.extraction.condition_terms,
                *[condition for mention in document.gene_mentions for condition in mention.associated_conditions],
            }
        )
        biomarkers = sorted(self.settings.extraction.biomarker_terms)
        drugs = sorted(self.settings.extraction.drug_terms)

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

            section_id = self._section_node_id(guideline.guideline_id, snippet.provenance.section_path)
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

        for mention in document.gene_mentions:
            gene_node = self._gene_node(mention.gene_symbol)
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
                condition_node = self._entity_node("Condition", condition)
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
                        properties={"context": mention.context},
                    )
                )

        for snippet in chunked_snippets:
            matched_genes = self._match_terms(snippet.text, genes)
            matched_conditions = self._match_terms(snippet.text, conditions)
            matched_biomarkers = self._match_terms(snippet.text, biomarkers)
            matched_drugs = self._match_terms(snippet.text, drugs)

            for gene_symbol in matched_genes:
                gene_node = self._gene_node(gene_symbol)
                add_node(gene_node)
                add_edge(
                    GraphEdge(
                        edge_id=make_id("edge", gene_node.node_id, "GENE_MENTIONED_IN", snippet.snippet_id),
                        source_id=gene_node.node_id,
                        target_id=snippet.snippet_id,
                        relation="GENE_MENTIONED_IN",
                        properties={"source": "snippet_match"},
                    )
                )
                for condition in matched_conditions:
                    condition_node = self._entity_node("Condition", condition)
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
                            properties={"snippet_id": snippet.snippet_id},
                        )
                    )
                for biomarker in matched_biomarkers:
                    biomarker_node = self._entity_node("Biomarker", biomarker)
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
                            properties={"snippet_id": snippet.snippet_id},
                        )
                    )

            recommendation_node = self._recommendation_node(snippet)
            if recommendation_node is None:
                continue
            add_node(recommendation_node)
            add_edge(
                GraphEdge(
                    edge_id=make_id("edge", recommendation_node.node_id, "SUPPORTED_BY_SNIPPET", snippet.snippet_id),
                    source_id=recommendation_node.node_id,
                    target_id=snippet.snippet_id,
                    relation="SUPPORTED_BY_SNIPPET",
                    properties={"snippet_id": snippet.snippet_id},
                )
            )

            evidence_class = recommendation_node.properties.get("evidence_class")
            if isinstance(evidence_class, str):
                class_node = self._entity_node("EvidenceClass", evidence_class)
                add_node(class_node)
                add_edge(
                    GraphEdge(
                        edge_id=make_id("edge", recommendation_node.node_id, "HAS_EVIDENCE_CLASS", class_node.node_id),
                        source_id=recommendation_node.node_id,
                        target_id=class_node.node_id,
                        relation="HAS_EVIDENCE_CLASS",
                        properties={},
                    )
                )
            evidence_level = recommendation_node.properties.get("evidence_level")
            if isinstance(evidence_level, str):
                level_node = self._entity_node("EvidenceLevel", evidence_level)
                add_node(level_node)
                add_edge(
                    GraphEdge(
                        edge_id=make_id("edge", recommendation_node.node_id, "HAS_EVIDENCE_LEVEL", level_node.node_id),
                        source_id=recommendation_node.node_id,
                        target_id=level_node.node_id,
                        relation="HAS_EVIDENCE_LEVEL",
                        properties={},
                    )
                )

            for gene_symbol in matched_genes:
                gene_node = self._gene_node(gene_symbol)
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
                        properties={"snippet_id": snippet.snippet_id},
                    )
                )

            recommendation_relation = (
                "CONTRAINDICATED_FOR" if self._is_contraindicated(snippet.text) else "RECOMMENDS"
            )
            for drug in matched_drugs:
                drug_node = self._entity_node("Drug", drug)
                add_node(drug_node)
                add_edge(
                    GraphEdge(
                        edge_id=make_id(
                            "edge",
                            recommendation_node.node_id,
                            recommendation_relation,
                            drug_node.node_id,
                        ),
                        source_id=recommendation_node.node_id,
                        target_id=drug_node.node_id,
                        relation=recommendation_relation,
                        properties={"snippet_id": snippet.snippet_id},
                    )
                )

        return ExtractionResult(nodes=list(nodes.values()), edges=list(edges.values()))

    def _load_gene_lexicon(self, path_value: str | None) -> list[str]:
        if path_value is None:
            return []
        path = self.settings.resolve_path(path_value)
        if path is None or not path.exists():
            return []
        return [
            line.strip().upper()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]

    def _match_terms(self, text: str, terms: Iterable[str]) -> list[str]:
        matches: list[str] = []
        for term in terms:
            if not term:
                continue
            pattern = self._term_pattern(term)
            if pattern.search(text):
                matches.append(term.upper() if term.isupper() else term)
        return sorted(set(matches))

    def _term_pattern(self, term: str) -> re.Pattern[str]:
        escaped = re.escape(term)
        if re.fullmatch(r"[A-Za-z0-9_-]+", term):
            return re.compile(rf"\b{escaped}\b", flags=re.IGNORECASE)
        return re.compile(escaped, flags=re.IGNORECASE)

    def _section_node_id(self, guideline_id: str, section_path: list[str]) -> str:
        payload = " > ".join(section_path) if section_path else "Document"
        return f"section:{guideline_id}:{stable_hash(payload)}"

    def _gene_node(self, symbol: str) -> GraphNode:
        canonical = symbol.upper()
        return GraphNode(
            node_id=f"gene:{canonical}",
            label="Gene",
            name=canonical,
            properties={"gene_symbol": canonical},
        )

    def _entity_node(self, label: str, name: str) -> GraphNode:
        canonical = name.strip()
        return GraphNode(
            node_id=f"{label.lower()}:{stable_hash(label, canonical)}",
            label=label,
            name=canonical,
            properties={"canonical_name": canonical},
        )

    def _recommendation_node(self, snippet: SourceSnippet) -> GraphNode | None:
        evidence_class = self._extract_evidence_class(snippet)
        evidence_level = self._extract_evidence_level(snippet)
        is_recommendation = snippet.snippet_type == "recommendation" or RECOMMENDATION_HINT_PATTERN.search(snippet.text)
        if not is_recommendation:
            return None
        return GraphNode(
            node_id=f"recommendation:{stable_hash(snippet.provenance.guideline_id, snippet.text[:200])}",
            label="Recommendation",
            name=snippet.text[:80],
            properties={
                "text": snippet.text,
                "guideline_id": snippet.provenance.guideline_id,
                "section_path": snippet.provenance.section_path,
                "page": snippet.provenance.page,
                "evidence_class": evidence_class,
                "evidence_level": evidence_level,
            },
        )

    def _extract_evidence_class(self, snippet: SourceSnippet) -> str | None:
        for candidate in (
            snippet.raw_fields.get("Class of Recommendation"),
            snippet.text,
        ):
            if isinstance(candidate, str):
                match = EVIDENCE_CLASS_PATTERN.search(candidate)
                if match:
                    return match.group(1)
        return None

    def _extract_evidence_level(self, snippet: SourceSnippet) -> str | None:
        for candidate in (
            snippet.raw_fields.get("Level of Evidence"),
            snippet.text,
        ):
            if isinstance(candidate, str):
                match = EVIDENCE_LEVEL_PATTERN.search(candidate)
                if match:
                    return match.group(1).upper()
        return None

    def _is_contraindicated(self, text: str) -> bool:
        lowered = text.lower()
        return any(token in lowered for token in ("contraindicated", "should not", "harm", "no benefit"))
