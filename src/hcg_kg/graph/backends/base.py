from __future__ import annotations

from typing import Protocol

from hcg_kg.models.graph import GraphEdge, GraphNode, GraphSubgraph


class GraphBackend(Protocol):
    def initialize(self) -> None: ...

    def upsert_nodes(self, nodes: list[GraphNode]) -> None: ...

    def upsert_edges(self, edges: list[GraphEdge]) -> None: ...

    def list_nodes(self, label: str | None = None) -> list[GraphNode]: ...

    def get_node(self, node_id: str) -> GraphNode | None: ...

    def get_edges(
        self,
        node_id: str,
        relation: str | None = None,
        direction: str = "both",
    ) -> list[GraphEdge]: ...

    def export_subgraph(self, node_id: str, depth: int = 2) -> GraphSubgraph: ...

    def persist(self) -> None: ...

    def close(self) -> None: ...
