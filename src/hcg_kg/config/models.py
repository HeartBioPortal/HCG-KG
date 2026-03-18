from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PathSettings(BaseModel):
    raw_input_glob: str = "data/raw/*.json"
    source_pdf_dir: str | None = None
    processed_dir: str = "data/processed"
    normalized_dir: str = "data/processed/normalized"
    graph_dir: str = "data/processed/graph"
    vector_dir: str = "data/processed/vector"
    cache_dir: str = ".cache/hcg_kg"
    state_dir: str = "data/processed/state"
    log_dir: str = "logs"


class ModelSettings(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: Literal["heuristic", "ollama", "huggingface", "llamaindex"] = "heuristic"
    model_name: str = "heuristic-v1"
    embedding_model: str = "tfidf"
    tokenizer_name: str | None = None
    context_window: int = 4096
    max_new_tokens: int = 768
    temperature: float = 0.0
    device_map: str = "auto"
    model_kwargs: dict[str, Any] = Field(default_factory=dict)
    generate_kwargs: dict[str, Any] = Field(default_factory=dict)


class ExtractionSettings(BaseModel):
    chunk_size: int = 1600
    chunk_overlap: int = 200
    batch_size: int = 24
    num_workers: int = 8
    use_gpu: bool = False
    run_relation_extraction: bool = True
    build_embeddings: bool = True
    generate_summaries: bool = False
    gene_lexicon_path: str | None = None
    condition_terms: list[str] = Field(default_factory=list)
    biomarker_terms: list[str] = Field(default_factory=list)
    drug_terms: list[str] = Field(default_factory=list)


class GraphSettings(BaseModel):
    backend: Literal["networkx", "neo4j"] = "networkx"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password_env: str = "NEO4J_PASSWORD"
    neo4j_database: str = "neo4j"


class RetrievalSettings(BaseModel):
    vector_backend: Literal["tfidf"] = "tfidf"
    top_k: int = 5


class RuntimeSettings(BaseModel):
    log_level: str = "INFO"
    persist_graph_snapshot: bool = True
    default_query_depth: int = 3


class ProjectSettings(BaseModel):
    project_name: str = "hcg-kg"
    profile_name: str = "hpc-large"
    guideline_family: str = "aha"
    project_root: Path
    paths: PathSettings = Field(default_factory=PathSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    extraction: ExtractionSettings = Field(default_factory=ExtractionSettings)
    graph: GraphSettings = Field(default_factory=GraphSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)

    def resolve_path(self, value: str | None) -> Path | None:
        if value is None:
            return None
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    def resolve_glob(self, pattern: str) -> str:
        path = Path(pattern)
        return str(path if path.is_absolute() else self.project_root / path)

    @property
    def normalized_dir(self) -> Path:
        path = self.resolve_path(self.paths.normalized_dir)
        assert path is not None
        return path

    @property
    def graph_dir(self) -> Path:
        path = self.resolve_path(self.paths.graph_dir)
        assert path is not None
        return path

    @property
    def vector_dir(self) -> Path:
        path = self.resolve_path(self.paths.vector_dir)
        assert path is not None
        return path

    @property
    def state_dir(self) -> Path:
        path = self.resolve_path(self.paths.state_dir)
        assert path is not None
        return path

    @property
    def manifest_path(self) -> Path:
        return self.state_dir / "manifest.json"

    @property
    def graph_snapshot_path(self) -> Path:
        return self.graph_dir / "networkx_graph.json"

    @property
    def tfidf_index_path(self) -> Path:
        return self.vector_dir / "tfidf_index.joblib"
