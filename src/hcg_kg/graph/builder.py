from __future__ import annotations

from dataclasses import dataclass

from hcg_kg.config.models import ProjectSettings
from hcg_kg.extract.factory import create_extractor
from hcg_kg.graph.backends import create_backend
from hcg_kg.graph.backends.base import GraphBackend
from hcg_kg.models.documents import GuidelineDocument


@dataclass
class GraphBuildReport:
    documents: int
    nodes: int
    edges: int


class GraphBuilder:
    def __init__(self, settings: ProjectSettings, backend: GraphBackend | None = None) -> None:
        self.settings = settings
        self.backend = backend or create_backend(settings)
        self.extractor = create_extractor(settings)

    def build(self, documents: list[GuidelineDocument]) -> GraphBuildReport:
        self.backend.initialize()
        total_nodes = 0
        total_edges = 0
        for document in documents:
            extraction = self.extractor.extract(document)
            self.backend.upsert_nodes(extraction.nodes)
            self.backend.upsert_edges(extraction.edges)
            total_nodes += len(extraction.nodes)
            total_edges += len(extraction.edges)
        self.backend.persist()
        return GraphBuildReport(documents=len(documents), nodes=total_nodes, edges=total_edges)
