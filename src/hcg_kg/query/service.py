from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher, get_close_matches

from hcg_kg.config.models import ProjectSettings
from hcg_kg.graph.backends import create_backend
from hcg_kg.models.graph import GraphEdge, GraphNode
from hcg_kg.models.query import (
    GeneMatch,
    GeneQueryResponse,
    GuidelineReference,
    RecommendationResult,
    RelatedEntity,
    SupportingSnippet,
)
from hcg_kg.vector.tfidf import TfidfSnippetIndex


class QueryService:
    def __init__(self, settings: ProjectSettings) -> None:
        self.settings = settings
        self.backend = create_backend(settings)
        self.backend.initialize()
        self.vector_index = TfidfSnippetIndex(settings)

    def close(self) -> None:
        self.backend.close()

    def query_gene(self, gene: str, question: str | None = None) -> GeneQueryResponse:
        gene_nodes = self.backend.list_nodes(label="Gene")
        if not gene_nodes:
            return GeneQueryResponse(query=gene, summary="No graph has been built yet.")

        resolved_node, matches, match_type = self._resolve_gene(gene, gene_nodes)
        if resolved_node is None:
            response = GeneQueryResponse(query=gene, matches=matches, summary="No matching gene found in the graph.")
            if question:
                response.supporting_snippets = self.vector_index.search(question, self.settings.retrieval.top_k)
            return response

        subgraph = self.backend.export_subgraph(
            resolved_node.node_id,
            depth=self.settings.runtime.default_query_depth,
        )
        node_map = {node.node_id: node for node in subgraph.nodes}
        edges = subgraph.edges

        supporting_snippets = self._supporting_snippets(node_map)
        guidelines = self._guidelines(node_map)
        conditions = self._related_entities(node_map, edges, label="Condition")
        biomarkers = self._related_entities(node_map, edges, label="Biomarker")
        drugs = self._related_entities(node_map, edges, label="Drug")
        recommendations = self._recommendations(node_map, edges)

        if question:
            vector_hits = self.vector_index.search(question, self.settings.retrieval.top_k)
            supporting_lookup = {snippet.snippet_id: snippet for snippet in supporting_snippets}
            for snippet in vector_hits:
                supporting_lookup.setdefault(snippet.snippet_id, snippet)
            supporting_snippets = list(supporting_lookup.values())

        summary = self._summarize(
            resolved_gene=resolved_node.name,
            guidelines=guidelines,
            conditions=conditions,
            recommendations=recommendations,
        )

        return GeneQueryResponse(
            query=gene,
            resolved_gene=resolved_node.name,
            match_type=match_type,
            matches=matches,
            guidelines=guidelines,
            conditions=conditions,
            biomarkers=biomarkers,
            drugs=drugs,
            recommendations=recommendations,
            supporting_snippets=supporting_snippets,
            summary=summary,
        )

    def export_subgraph(self, gene: str) -> dict[str, object]:
        gene_nodes = self.backend.list_nodes(label="Gene")
        resolved_node, _, _ = self._resolve_gene(gene, gene_nodes)
        if resolved_node is None:
            return {"nodes": [], "edges": []}
        subgraph = self.backend.export_subgraph(
            resolved_node.node_id,
            depth=self.settings.runtime.default_query_depth,
        )
        return subgraph.model_dump(mode="json")

    def _resolve_gene(
        self,
        query: str,
        gene_nodes: list[GraphNode],
    ) -> tuple[GraphNode | None, list[GeneMatch], str | None]:
        query_upper = query.strip().upper()
        exact = next((node for node in gene_nodes if node.name.upper() == query_upper), None)
        if exact is not None:
            return exact, [GeneMatch(gene_symbol=exact.name, score=1.0, match_type="exact")], "exact"

        candidate_names = [node.name for node in gene_nodes]
        close = get_close_matches(query_upper, candidate_names, n=5, cutoff=0.6)
        scored = sorted(
            [
                (
                    node,
                    SequenceMatcher(a=query_upper, b=node.name.upper()).ratio(),
                )
                for node in gene_nodes
                if node.name in close
            ],
            key=lambda item: item[1],
            reverse=True,
        )
        matches = [
            GeneMatch(gene_symbol=node.name, score=score, match_type="fuzzy")
            for node, score in scored
        ]
        if scored:
            return scored[0][0], matches, "fuzzy"
        return None, matches, None

    def _supporting_snippets(self, node_map: dict[str, GraphNode]) -> list[SupportingSnippet]:
        snippets: list[SupportingSnippet] = []
        for node in node_map.values():
            if node.label != "Snippet":
                continue
            snippets.append(
                SupportingSnippet(
                    snippet_id=node.node_id,
                    text=str(node.properties.get("text", "")),
                    guideline_title=node.properties.get("guideline_title"),
                    section_path=list(node.properties.get("section_path", [])),
                    page=node.properties.get("page"),
                    source_json_path=str(node.properties.get("source_json_path", "")),
                    source_pdf_path=node.properties.get("source_pdf_path"),
                )
            )
        snippets.sort(key=lambda item: (item.guideline_title or "", item.page or "", item.snippet_id))
        return snippets

    def _guidelines(self, node_map: dict[str, GraphNode]) -> list[GuidelineReference]:
        return sorted(
            [
                GuidelineReference(guideline_id=node.properties.get("guideline_id", node.node_id), title=node.name)
                for node in node_map.values()
                if node.label == "Guideline"
            ],
            key=lambda item: item.title,
        )

    def _related_entities(
        self,
        node_map: dict[str, GraphNode],
        edges: list[GraphEdge],
        label: str,
    ) -> list[RelatedEntity]:
        snippet_map: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            snippet_id = edge.properties.get("snippet_id")
            if isinstance(snippet_id, str):
                snippet_map[edge.target_id].add(snippet_id)
                snippet_map[edge.source_id].add(snippet_id)
        entities = []
        for node in node_map.values():
            if node.label != label:
                continue
            entities.append(
                RelatedEntity(
                    name=node.name,
                    node_id=node.node_id,
                    snippet_ids=sorted(snippet_map.get(node.node_id, set())),
                )
            )
        return sorted(entities, key=lambda item: item.name)

    def _recommendations(
        self,
        node_map: dict[str, GraphNode],
        edges: list[GraphEdge],
    ) -> list[RecommendationResult]:
        snippets_by_recommendation: dict[str, set[str]] = defaultdict(set)
        drugs_by_recommendation: dict[str, set[str]] = defaultdict(set)
        conditions_by_recommendation: dict[str, set[str]] = defaultdict(set)
        biomarkers_by_recommendation: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            if edge.relation == "SUPPORTED_BY_SNIPPET":
                snippets_by_recommendation[edge.source_id].add(edge.target_id)
            if edge.relation in {"RECOMMENDS", "CONTRAINDICATED_FOR"} and edge.target_id in node_map:
                drugs_by_recommendation[edge.source_id].add(node_map[edge.target_id].name)
            if edge.target_id in node_map and node_map[edge.target_id].label == "Condition":
                conditions_by_recommendation[edge.source_id].add(node_map[edge.target_id].name)
            if edge.target_id in node_map and node_map[edge.target_id].label == "Biomarker":
                biomarkers_by_recommendation[edge.source_id].add(node_map[edge.target_id].name)
        results = []
        for node in node_map.values():
            if node.label != "Recommendation":
                continue
            results.append(
                RecommendationResult(
                    recommendation_id=node.node_id,
                    text=str(node.properties.get("text", node.name)),
                    evidence_class=node.properties.get("evidence_class"),
                    evidence_level=node.properties.get("evidence_level"),
                    drugs=sorted(drugs_by_recommendation.get(node.node_id, set())),
                    conditions=sorted(conditions_by_recommendation.get(node.node_id, set())),
                    biomarkers=sorted(biomarkers_by_recommendation.get(node.node_id, set())),
                    supporting_snippet_ids=sorted(snippets_by_recommendation.get(node.node_id, set())),
                )
            )
        return sorted(results, key=lambda item: item.recommendation_id)

    def _summarize(
        self,
        resolved_gene: str,
        guidelines: list[GuidelineReference],
        conditions: list[RelatedEntity],
        recommendations: list[RecommendationResult],
    ) -> str:
        guideline_count = len(guidelines)
        condition_text = ", ".join(item.name for item in conditions[:5]) or "no linked conditions yet"
        evidence = [item.evidence_class for item in recommendations if item.evidence_class]
        evidence_text = ", ".join(sorted(set(evidence))) if evidence else "no explicit evidence classes extracted"
        return (
            f"{resolved_gene} appears in {guideline_count} guideline(s). "
            f"Top linked conditions: {condition_text}. "
            f"Extracted recommendation evidence classes: {evidence_text}."
        )
