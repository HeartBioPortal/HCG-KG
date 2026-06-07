from __future__ import annotations

from hcg_kg.graph.backends.networkx_backend import NetworkXBackend
from hcg_kg.pipelines.runner import PipelineRunner
from hcg_kg.query.service import QueryService
from hcg_kg.storage.manifest import ManifestEntry


def test_pipeline_builds_graph_and_answers_gene_query(local_settings):
    runner = PipelineRunner(local_settings)
    result = runner.run_pipeline()

    assert result["documents"] == 1
    assert result["graph_nodes"] > 0
    assert result["graph_edges"] > 0

    service = QueryService(local_settings)
    try:
        response = service.query_gene("LDLR")
    finally:
        service.close()

    assert response.resolved_gene == "LDLR"
    assert response.conditions
    assert response.recommendations
    assert any("statin" in drug.name.lower() for drug in response.drugs)
    assert any(snippet.page == "145" for snippet in response.supporting_snippets)
    assert not any("APOE carriers" in snippet.text for snippet in response.supporting_snippets)


def test_force_ingest_drops_manifest_entries_outside_current_corpus(local_settings):
    runner = PipelineRunner(local_settings)
    runner.run_pipeline()

    entries = runner.manifest.load()
    entries["legacy-guideline"] = ManifestEntry(
        doc_id="legacy-guideline",
        source_json_path="/tmp/legacy-guideline.json",
        source_pdf_path="/tmp/legacy-guideline.pdf",
    )
    runner.manifest.save(entries)

    runner.ingest(force=True)

    refreshed_entries = runner.manifest.load()
    assert "legacy-guideline" not in refreshed_entries
    assert len(refreshed_entries) == 1


def test_force_graph_build_starts_from_clean_networkx_snapshot(local_settings):
    runner = PipelineRunner(local_settings)
    runner.run_pipeline()

    backend = NetworkXBackend(local_settings)
    backend.initialize()
    backend.graph.add_node("guideline:legacy", label="Guideline", name="Legacy Guideline")
    backend.persist()

    runner.build_graph(force=True)

    refreshed_backend = NetworkXBackend(local_settings)
    refreshed_backend.initialize()
    assert refreshed_backend.get_node("guideline:legacy") is None
