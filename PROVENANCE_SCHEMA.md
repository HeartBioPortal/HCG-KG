# HCG-KG Provenance Schema

HCG-KG nodes and edges should preserve enough provenance to trace each graph statement back to a guideline source document, parsed JSON input, snippet, extraction method, and release build.

## Node provenance

| Field | Description |
| --- | --- |
| `guideline_id` | Stable guideline identifier. |
| `source_document` | Source PDF, source URL/DOI, or document title. |
| `source_organization` | AHA, ACC, ESC, or collaborating organization. |
| `publication_year` | Guideline publication year. |
| `source_json_path` | Parsed source JSON file. |
| `source_pdf_path` | Source PDF path when available. |
| `section_path` | Guideline section hierarchy. |
| `page` | Page number when available. |
| `snippet_id` | Source snippet identifier. |
| `snippet_text_if_allowed` | Snippet text only when source terms allow redistribution. |
| `extraction_method` | Heuristic, LLM-assisted, parser, or curator method. |
| `curator_or_pipeline_version` | Pipeline, prompt, model, or curator version. |
| `source_license` | Source-document license or terms. |
| `hbp_build_version` | HBP release/build version. |

## Edge provenance

| Field | Description |
| --- | --- |
| `relationship_type` | Edge type, such as `GENE_MENTIONED_IN` or `SUPPORTED_BY_SNIPPET`. |
| `source_node_id` | Source node identifier. |
| `target_node_id` | Target node identifier. |
| `evidence_snippet_id` | Snippet supporting the relationship. |
| `confidence` | Extraction confidence when available. |
| `extraction_method` | Method used to create the edge. |
| `normalization_steps` | Entity or relation normalization applied. |
| `source_license` | Source terms inherited by the relationship. |

## Guideline-specific fields

Graph exports should preserve guideline source, snippet, relationship type, extraction pipeline version, and licensing. Recommendation nodes should preserve evidence class and evidence level relationships where available. Drug/intervention, biomarker, condition, gene, and variant nodes should preserve their original mention text and normalized identifier when available.

Guideline graph evidence is context only and should not be presented as medical advice or an automated recommendation.
