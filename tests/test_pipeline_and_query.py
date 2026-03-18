from __future__ import annotations

from hcg_kg.pipelines.runner import PipelineRunner
from hcg_kg.query.service import QueryService


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
