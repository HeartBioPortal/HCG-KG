from __future__ import annotations

from hcg_kg.ingest.loaders import RawDocumentLoader
from hcg_kg.ingest.normalizer import GuidelineJSONNormalizer


def test_normalizer_extracts_metadata_and_provenance(local_settings, sample_json_path):
    loader = RawDocumentLoader(local_settings)
    raw = loader.load(sample_json_path)
    document = GuidelineJSONNormalizer(local_settings).normalize(
        raw=raw,
        source_json_path=sample_json_path,
        source_pdf_path=None,
        doc_id=loader.derive_doc_id(sample_json_path),
    )

    assert document.metadata.title == "2023 AHA/ACC Guideline for Chronic Coronary Disease"
    assert len(document.snippets) >= 4
    assert any(snippet.provenance.page == "145" for snippet in document.snippets)
    assert {"LDLR", "APOE", "PCSK9"} <= {mention.gene_symbol for mention in document.gene_mentions}
    assert any("Biomarkers and Genomics" in " > ".join(snippet.provenance.section_path) for snippet in document.snippets)
