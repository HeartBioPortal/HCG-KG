from __future__ import annotations

from hcg_kg.extract.heuristic import HeuristicBiomedicalExtractor
from hcg_kg.ingest.loaders import RawDocumentLoader
from hcg_kg.ingest.normalizer import GuidelineJSONNormalizer
from hcg_kg.models.documents import Provenance, SourceSnippet


def test_extractor_creates_recommendations_and_relations(local_settings, sample_json_path):
    loader = RawDocumentLoader(local_settings)
    raw = loader.load(sample_json_path)
    document = GuidelineJSONNormalizer(local_settings).normalize(
        raw=raw,
        source_json_path=sample_json_path,
        source_pdf_path=None,
        doc_id=loader.derive_doc_id(sample_json_path),
    )
    extraction = HeuristicBiomedicalExtractor(local_settings).extract(document)

    labels = {node.label for node in extraction.nodes}
    relations = {edge.relation for edge in extraction.edges}

    assert "Gene" in labels
    assert "Recommendation" in labels
    assert "EvidenceClass" in labels
    assert "EvidenceLevel" in labels
    assert "REFERENCED_IN_RECOMMENDATION" in relations
    assert "SUPPORTED_BY_SNIPPET" in relations
    assert any(node.label == "Drug" and "statin" in node.name.lower() for node in extraction.nodes)


def test_extractor_reads_new_hcg_cor_and_loe_fields(local_settings):
    snippet = SourceSnippet(
        snippet_id="snippet:test",
        text="PCSK9 inhibitor therapy may be considered for selected patients.",
        snippet_type="recommendation",
        provenance=Provenance(guideline_id="doc", guideline_title="Doc", source_json_path="doc.json"),
        raw_fields={
            "class_of_recommendation": "IIb",
            "level_of_evidence": "B-R",
        },
    )

    extractor = HeuristicBiomedicalExtractor(local_settings)
    recommendation = extractor._recommendation_node(snippet)

    assert recommendation is not None
    assert recommendation.properties["evidence_class"] == "IIb"
    assert recommendation.properties["evidence_level"] == "B-R"
