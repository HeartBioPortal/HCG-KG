from __future__ import annotations

from hcg_kg.extract.heuristic import HeuristicBiomedicalExtractor
from hcg_kg.ingest.loaders import RawDocumentLoader
from hcg_kg.ingest.normalizer import GuidelineJSONNormalizer


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
