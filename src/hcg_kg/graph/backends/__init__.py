from __future__ import annotations

from hcg_kg.config.models import ProjectSettings
from hcg_kg.graph.backends.base import GraphBackend
from hcg_kg.graph.backends.neo4j_backend import Neo4jBackend
from hcg_kg.graph.backends.networkx_backend import NetworkXBackend


def create_backend(settings: ProjectSettings) -> GraphBackend:
    if settings.graph.backend == "neo4j":
        return Neo4jBackend(settings)
    return NetworkXBackend(settings)
