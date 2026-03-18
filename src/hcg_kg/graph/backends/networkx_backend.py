from __future__ import annotations

from collections import deque

import networkx as nx
from networkx.readwrite import json_graph

from hcg_kg.config.models import ProjectSettings
from hcg_kg.models.graph import GraphEdge, GraphNode, GraphSubgraph
from hcg_kg.utils import dump_json, ensure_dir, load_json


class NetworkXBackend:
    def __init__(self, settings: ProjectSettings) -> None:
        self.settings = settings
        self.snapshot_path = settings.graph_snapshot_path
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()

    def initialize(self) -> None:
        ensure_dir(self.snapshot_path.parent)
        if self.snapshot_path.exists():
            raw = load_json(self.snapshot_path)
            self.graph = json_graph.node_link_graph(raw, directed=True, multigraph=True, edges="edges")

    def upsert_nodes(self, nodes: list[GraphNode]) -> None:
        for node in nodes:
            properties = {key: value for key, value in node.properties.items() if key not in {"label", "name"}}
            if self.graph.has_node(node.node_id):
                current = dict(self.graph.nodes[node.node_id])
                current.update(properties)
                current["label"] = node.label
                current["name"] = node.name
                self.graph.nodes[node.node_id].update(current)
            else:
                self.graph.add_node(node.node_id, label=node.label, name=node.name, **properties)

    def upsert_edges(self, edges: list[GraphEdge]) -> None:
        for edge in edges:
            self.graph.add_edge(
                edge.source_id,
                edge.target_id,
                key=edge.edge_id,
                relation=edge.relation,
                edge_id=edge.edge_id,
                **edge.properties,
            )

    def list_nodes(self, label: str | None = None) -> list[GraphNode]:
        nodes: list[GraphNode] = []
        for node_id, attrs in self.graph.nodes(data=True):
            node_label = attrs.get("label")
            if label is not None and node_label != label:
                continue
            properties = {key: value for key, value in attrs.items() if key not in {"label", "name"}}
            nodes.append(
                GraphNode(
                    node_id=node_id,
                    label=str(node_label),
                    name=str(attrs.get("name", node_id)),
                    properties=properties,
                )
            )
        return nodes

    def get_node(self, node_id: str) -> GraphNode | None:
        if not self.graph.has_node(node_id):
            return None
        attrs = dict(self.graph.nodes[node_id])
        properties = {key: value for key, value in attrs.items() if key not in {"label", "name"}}
        return GraphNode(
            node_id=node_id,
            label=str(attrs.get("label")),
            name=str(attrs.get("name", node_id)),
            properties=properties,
        )

    def get_edges(
        self,
        node_id: str,
        relation: str | None = None,
        direction: str = "both",
    ) -> list[GraphEdge]:
        results: list[GraphEdge] = []
        if direction in {"out", "both"}:
            results.extend(self._edges_from_iter(self.graph.out_edges(node_id, data=True, keys=True)))
        if direction in {"in", "both"}:
            results.extend(self._edges_from_iter(self.graph.in_edges(node_id, data=True, keys=True)))
        if relation is not None:
            results = [edge for edge in results if edge.relation == relation]
        unique: dict[str, GraphEdge] = {edge.edge_id: edge for edge in results}
        return list(unique.values())

    def export_subgraph(self, node_id: str, depth: int = 2) -> GraphSubgraph:
        if not self.graph.has_node(node_id):
            return GraphSubgraph()
        seen = {node_id}
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            neighbors = set(self.graph.predecessors(current)) | set(self.graph.successors(current))
            for neighbor in neighbors:
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append((neighbor, current_depth + 1))
        subgraph = self.graph.subgraph(seen).copy()
        nodes = [
            GraphNode(
                node_id=node_id_,
                label=str(attrs.get("label")),
                name=str(attrs.get("name", node_id_)),
                properties={key: value for key, value in attrs.items() if key not in {"label", "name"}},
            )
            for node_id_, attrs in subgraph.nodes(data=True)
        ]
        edges = self._edges_from_iter(subgraph.edges(data=True, keys=True))
        return GraphSubgraph(nodes=nodes, edges=edges)

    def persist(self) -> None:
        ensure_dir(self.snapshot_path.parent)
        dump_json(json_graph.node_link_data(self.graph, edges="edges"), self.snapshot_path)

    def close(self) -> None:
        self.persist()

    def _edges_from_iter(
        self,
        iterator: object,
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        for source_id, target_id, edge_id, attrs in iterator:  # type: ignore[misc]
            properties = {key: value for key, value in attrs.items() if key not in {"relation", "edge_id"}}
            edges.append(
                GraphEdge(
                    edge_id=str(attrs.get("edge_id", edge_id)),
                    source_id=source_id,
                    target_id=target_id,
                    relation=str(attrs.get("relation")),
                    properties=properties,
                )
            )
        return edges
