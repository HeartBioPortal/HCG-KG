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


def test_normalizer_preserves_new_hcg_recommendation_metadata(local_settings, tmp_path):
    raw_path = tmp_path / "new_hcg_doc_aggregated.json"
    raw = {
        "content": [
            {
                "content": {
                    "recommendation_tables": [
                        {
                            "title": "Recommendations",
                            "rows": [
                                {
                                    "recommendation": "PCSK9 inhibitor therapy may be considered.",
                                    "class_of_recommendation": "IIb",
                                    "level_of_evidence": "B-R",
                                    "supporting_text": "",
                                    "row_continues_from_previous_page": False,
                                    "row_continues_to_next_page": False,
                                }
                            ],
                        }
                    ]
                },
                "genes": [],
            }
        ],
        "genes": [{"Gene": "PCSK9", "Associated Conditions": [], "Occurrences": 1, "context": []}],
    }
    raw_path.write_text(__import__("json").dumps(raw), encoding="utf-8")

    document = GuidelineJSONNormalizer(local_settings).normalize(
        raw=raw,
        source_json_path=raw_path,
        source_pdf_path=None,
        doc_id="new_hcg_doc",
    )

    recommendation = next(snippet for snippet in document.snippets if snippet.snippet_type == "recommendation")
    assert recommendation.raw_fields["class_of_recommendation"] == "IIb"
    assert recommendation.raw_fields["level_of_evidence"] == "B-R"
