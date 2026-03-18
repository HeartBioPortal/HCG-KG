from __future__ import annotations

import logging
from pathlib import Path

from hcg_kg.config.models import ProjectSettings
from hcg_kg.graph.builder import GraphBuildReport, GraphBuilder
from hcg_kg.ingest.loaders import RawDocumentLoader
from hcg_kg.ingest.normalizer import GuidelineJSONNormalizer
from hcg_kg.models.documents import GuidelineDocument
from hcg_kg.storage.manifest import ManifestEntry, ManifestStore
from hcg_kg.utils import dump_json, ensure_dir, load_json
from hcg_kg.vector.tfidf import TfidfSnippetIndex

LOGGER = logging.getLogger(__name__)


class PipelineRunner:
    def __init__(self, settings: ProjectSettings) -> None:
        self.settings = settings
        self.loader = RawDocumentLoader(settings)
        self.normalizer = GuidelineJSONNormalizer(settings)
        self.manifest = ManifestStore(settings.manifest_path)

    def ingest(
        self,
        input_glob: str | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> list[ManifestEntry]:
        entries = self.manifest.load()
        discovered = self.loader.discover(input_glob=input_glob, limit=limit)
        for path in discovered:
            doc_id = self.loader.derive_doc_id(path)
            if doc_id in entries and not force:
                continue
            pdf_path = self.loader.resolve_pdf_path(path)
            entry = ManifestEntry(
                doc_id=doc_id,
                source_json_path=str(path),
                source_pdf_path=str(pdf_path) if pdf_path is not None else None,
                family=self.settings.guideline_family,
                stages={
                    "ingest": "complete",
                    "normalize": "pending",
                    "build_graph": "pending",
                    "build_embeddings": "pending",
                },
            )
            entries[doc_id] = entry
        self.manifest.save(entries)
        LOGGER.info("Discovered %s documents", len(entries))
        return list(entries.values())

    def normalize(
        self,
        input_glob: str | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> list[GuidelineDocument]:
        entries = self.manifest.load()
        if not entries:
            self.ingest(input_glob=input_glob, limit=limit, force=force)
            entries = self.manifest.load()

        ensure_dir(self.settings.normalized_dir)
        normalized_docs: list[GuidelineDocument] = []
        for entry in entries.values():
            if entry.stages.get("normalize") == "complete" and entry.normalized_path and not force:
                normalized_docs.append(self._load_normalized(Path(entry.normalized_path)))
                continue
            raw = self.loader.load(Path(entry.source_json_path))
            document = self.normalizer.normalize(
                raw=raw,
                source_json_path=Path(entry.source_json_path),
                source_pdf_path=Path(entry.source_pdf_path) if entry.source_pdf_path else None,
                doc_id=entry.doc_id,
            )
            output_path = self.settings.normalized_dir / f"{entry.doc_id}.json"
            dump_json(document.model_dump(mode="json"), output_path)
            updated_entry = entry.model_copy(
                update={
                    "normalized_path": str(output_path),
                    "stages": {**entry.stages, "normalize": "complete"},
                }
            )
            entries[entry.doc_id] = updated_entry
            normalized_docs.append(document)
        self.manifest.save(entries)
        LOGGER.info("Normalized %s documents", len(normalized_docs))
        return normalized_docs

    def build_graph(self, force: bool = False) -> GraphBuildReport:
        documents = self._load_all_normalized(force=force)
        builder = GraphBuilder(self.settings)
        report = builder.build(documents)
        entries = self.manifest.load()
        for doc_id, entry in entries.items():
            entries[doc_id] = entry.model_copy(
                update={"stages": {**entry.stages, "build_graph": "complete"}}
            )
        self.manifest.save(entries)
        LOGGER.info("Built graph with %s nodes and %s edges", report.nodes, report.edges)
        return report

    def build_embeddings(self, force: bool = False) -> str:
        documents = self._load_all_normalized(force=force)
        index = TfidfSnippetIndex(self.settings)
        artifact = index.build(documents)
        entries = self.manifest.load()
        for doc_id, entry in entries.items():
            entries[doc_id] = entry.model_copy(
                update={"stages": {**entry.stages, "build_embeddings": "complete"}}
            )
        self.manifest.save(entries)
        LOGGER.info("Built TF-IDF index for %s snippets", len(artifact.snippets))
        return str(index.path)

    def run_pipeline(
        self,
        input_glob: str | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> dict[str, object]:
        self.ingest(input_glob=input_glob, limit=limit, force=force)
        normalized_docs = self.normalize(input_glob=input_glob, limit=limit, force=force)
        graph_report = self.build_graph(force=force)
        embeddings_path = None
        if self.settings.extraction.build_embeddings:
            embeddings_path = self.build_embeddings(force=force)
        return {
            "documents": len(normalized_docs),
            "graph_nodes": graph_report.nodes,
            "graph_edges": graph_report.edges,
            "embeddings_path": embeddings_path,
        }

    def resume(self, input_glob: str | None = None, limit: int | None = None) -> dict[str, object]:
        return self.run_pipeline(input_glob=input_glob, limit=limit, force=False)

    def validate(self, input_glob: str | None = None, limit: int = 2) -> dict[str, object]:
        files = self.loader.discover(input_glob=input_glob, limit=limit)
        if not files:
            return {"valid": False, "error": "No input files found"}
        summaries = []
        for path in files:
            raw = self.loader.load(path)
            doc_id = self.loader.derive_doc_id(path)
            document = self.normalizer.normalize(
                raw,
                source_json_path=path,
                source_pdf_path=self.loader.resolve_pdf_path(path),
                doc_id=doc_id,
            )
            summaries.append(
                {
                    "doc_id": doc_id,
                    "title": document.metadata.title,
                    "snippets": len(document.snippets),
                    "gene_mentions": len(document.gene_mentions),
                    "schema_hints": document.metadata.schema_hints[:10],
                }
            )
        return {"valid": True, "documents": summaries}

    def _load_all_normalized(self, force: bool = False) -> list[GuidelineDocument]:
        entries = self.manifest.load()
        if not entries or force:
            return self.normalize(force=force)
        documents: list[GuidelineDocument] = []
        for entry in entries.values():
            if entry.normalized_path is None:
                continue
            documents.append(self._load_normalized(Path(entry.normalized_path)))
        return documents

    def _load_normalized(self, path: Path) -> GuidelineDocument:
        return GuidelineDocument.model_validate(load_json(path))
