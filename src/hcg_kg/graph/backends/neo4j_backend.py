from __future__ import annotations

import os
import re

from hcg_kg.config.models import ProjectSettings
from hcg_kg.models.graph import GraphEdge, GraphNode, GraphSubgraph

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable
except ImportError:  # pragma: no cover - optional dependency
    GraphDatabase = None  # type: ignore[assignment]
    ServiceUnavailable = Exception  # type: ignore[assignment]


_SAFE_CYPHER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class Neo4jBackend:
    def __init__(self, settings: ProjectSettings) -> None:
        if GraphDatabase is None:  # pragma: no cover - optional dependency
            raise ImportError("Install hcg-kg with the neo4j extra to use the Neo4j backend.")
        password = os.getenv(settings.graph.neo4j_password_env)
        if not password:
            raise RuntimeError(
                f"Environment variable {settings.graph.neo4j_password_env} is required for Neo4j."
            )
        self.settings = settings
        self.driver = GraphDatabase.driver(
            settings.graph.neo4j_uri,
            auth=(settings.graph.neo4j_username, password),
        )

    def initialize(self) -> None:
        try:
            with self.driver.session(database=self.settings.graph.neo4j_database) as session:
                session.run(
                    "CREATE CONSTRAINT hcgkg_node_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.node_id IS UNIQUE"
                )
        except ServiceUnavailable as exc:
            raise RuntimeError(
                "Neo4j is not reachable at "
                f"{self.settings.graph.neo4j_uri}. "
                "If you do not have a Neo4j service running, use the "
                "'hpc-networkx' profile instead."
            ) from exc

    def upsert_nodes(self, nodes: list[GraphNode]) -> None:
        with self.driver.session(database=self.settings.graph.neo4j_database) as session:
            for node in nodes:
                label = self._sanitize_identifier(node.label)
                session.run(
                    f"MERGE (n:Entity:{label} {{node_id: $node_id}}) "
                    "SET n.name = $name, n.label = $label, n += $properties",
                    node_id=node.node_id,
                    name=node.name,
                    label=node.label,
                    properties=node.properties,
                )

    def upsert_edges(self, edges: list[GraphEdge]) -> None:
        with self.driver.session(database=self.settings.graph.neo4j_database) as session:
            for edge in edges:
                relation = self._sanitize_identifier(edge.relation)
                session.run(
                    f"MATCH (source {{node_id: $source_id}}) "
                    f"MATCH (target {{node_id: $target_id}}) "
                    f"MERGE (source)-[r:{relation} {{edge_id: $edge_id}}]->(target) "
                    "SET r += $properties, r.relation = $relation",
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    edge_id=edge.edge_id,
                    properties=edge.properties,
                    relation=edge.relation,
                )

    def list_nodes(self, label: str | None = None) -> list[GraphNode]:
        clause = ""
        params: dict[str, object] = {}
        if label is not None:
            safe_label = self._sanitize_identifier(label)
            clause = f":{safe_label}"
        with self.driver.session(database=self.settings.graph.neo4j_database) as session:
            records = session.run(f"MATCH (n:Entity{clause}) RETURN n")
            return [self._node_from_record(record["n"]) for record in records]

    def get_node(self, node_id: str) -> GraphNode | None:
        with self.driver.session(database=self.settings.graph.neo4j_database) as session:
            record = session.run("MATCH (n:Entity {node_id: $node_id}) RETURN n LIMIT 1", node_id=node_id).single()
            if record is None:
                return None
            return self._node_from_record(record["n"])

    def get_edges(
        self,
        node_id: str,
        relation: str | None = None,
        direction: str = "both",
    ) -> list[GraphEdge]:
        if direction not in {"in", "out", "both"}:
            raise ValueError(f"Unsupported direction: {direction}")
        relation_clause = ""
        if relation is not None:
            relation_clause = ":" + self._sanitize_identifier(relation)
        patterns: list[str] = []
        if direction in {"out", "both"}:
            patterns.append(f"MATCH (n {{node_id: $node_id}})-[r{relation_clause}]->(m) RETURN r, startNode(r) AS s, endNode(r) AS t")
        if direction in {"in", "both"}:
            patterns.append(f"MATCH (n {{node_id: $node_id}})<-[r{relation_clause}]-(m) RETURN r, startNode(r) AS s, endNode(r) AS t")
        edges: dict[str, GraphEdge] = {}
        with self.driver.session(database=self.settings.graph.neo4j_database) as session:
            for query in patterns:
                for record in session.run(query, node_id=node_id):
                    edge = self._edge_from_record(record["r"], record["s"], record["t"])
                    edges[edge.edge_id] = edge
        return list(edges.values())

    def export_subgraph(self, node_id: str, depth: int = 2) -> GraphSubgraph:
        safe_depth = max(1, min(depth, 5))
        node_query = (
            f"MATCH p=(n:Entity {{node_id: $node_id}})-[*1..{safe_depth}]-(m) "
            "UNWIND nodes(p) AS node RETURN DISTINCT node"
        )
        edge_query = (
            f"MATCH p=(n:Entity {{node_id: $node_id}})-[*1..{safe_depth}]-(m) "
            "UNWIND relationships(p) AS rel "
            "RETURN DISTINCT rel, startNode(rel) AS s, endNode(rel) AS t"
        )
        with self.driver.session(database=self.settings.graph.neo4j_database) as session:
            nodes = [self._node_from_record(record["node"]) for record in session.run(node_query, node_id=node_id)]
            edges = [
                self._edge_from_record(record["rel"], record["s"], record["t"])
                for record in session.run(edge_query, node_id=node_id)
            ]
        return GraphSubgraph(nodes=nodes, edges=edges)

    def persist(self) -> None:
        return None

    def close(self) -> None:
        self.driver.close()

    def _sanitize_identifier(self, value: str) -> str:
        if not _SAFE_CYPHER_PATTERN.match(value):
            raise ValueError(f"Unsafe Cypher identifier: {value}")
        return value

    def _node_from_record(self, node: object) -> GraphNode:
        data = dict(node)
        return GraphNode(
            node_id=str(data["node_id"]),
            label=str(data.get("label", "Entity")),
            name=str(data.get("name", data["node_id"])),
            properties={key: value for key, value in data.items() if key not in {"node_id", "label", "name"}},
        )

    def _edge_from_record(self, edge: object, source: object, target: object) -> GraphEdge:
        data = dict(edge)
        source_data = dict(source)
        target_data = dict(target)
        relation = data.get("relation")
        if not isinstance(relation, str) or not relation:
            relation = getattr(edge, "type", "")
            if callable(relation):  # pragma: no cover - driver-dependent
                relation = relation()
        return GraphEdge(
            edge_id=str(data["edge_id"]),
            source_id=str(source_data["node_id"]),
            target_id=str(target_data["node_id"]),
            relation=str(relation),
            properties={key: value for key, value in data.items() if key not in {"edge_id", "relation"}},
        )
