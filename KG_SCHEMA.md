# HCG-KG Schema

This documentation follows the current graph schema in `configs/schema/kg_schema.yaml`.

## Node types

| Node | Key | Description |
| --- | --- | --- |
| `Guideline` | `guideline_id` | Canonical guideline document node. |
| `Section` | `section_id` | Hierarchical section or subsection inside a guideline. |
| `Snippet` | `snippet_id` | Source-grounded text span with document, section, and page provenance. |
| `Gene` | `gene_symbol` | HGNC-style gene symbol or curated gene mention. |
| `Variant` | `variant_id` | Sequence or pathogenicity-specific variant mention when available. |
| `Condition` | `condition_name` | Disease, phenotype, or syndrome. |
| `Biomarker` | `biomarker_name` | Measured biomarker or lab concept. |
| `Drug` | `intervention_name` | Drug, therapy, or intervention. |
| `Recommendation` | `recommendation_id` | Guideline recommendation statement extracted from source snippets. |
| `EvidenceClass` | `code` | Class of recommendation. |
| `EvidenceLevel` | `code` | Level of evidence. |
| `Citation` | `citation_id` | Reference or citation metadata when available. |

## Edge types

| Edge | Source | Target | Description |
| --- | --- | --- | --- |
| `GENE_MENTIONED_IN` | `Gene` | `Snippet` | Gene mention grounded in a source snippet. |
| `ASSOCIATED_WITH_CONDITION` | `Gene` | `Condition` | Gene linked to a disease, phenotype, or syndrome. |
| `REFERENCED_IN_RECOMMENDATION` | `Gene` | `Recommendation` | Gene mentioned in or linked to a recommendation. |
| `RECOMMENDS` | `Recommendation` | `Drug` | Recommendation supports a drug/intervention. |
| `CONTRAINDICATED_FOR` | `Recommendation` | `Drug` | Recommendation indicates a contraindicated drug/intervention context. |
| `HAS_EVIDENCE_CLASS` | `Recommendation` | `EvidenceClass` | Recommendation class/COR. |
| `HAS_EVIDENCE_LEVEL` | `Recommendation` | `EvidenceLevel` | Recommendation evidence level/LOE. |
| `FROM_GUIDELINE` | `Snippet` | `Guideline` | Snippet derives from a guideline. |
| `LOCATED_IN_SECTION` | `Snippet` | `Section` | Snippet section provenance. |
| `SUPPORTED_BY_SNIPPET` | `Recommendation` | `Snippet` | Recommendation is supported by a source snippet. |
| `CO_MENTIONED_WITH` | `Gene` | `Biomarker` | Gene and biomarker co-occur in source context. |

## HBP-facing interpretation

HCG-KG graph relationships are context links, not clinical directives. HBP should display source guideline, section, page/snippet provenance, evidence class/level when available, and extraction method/version with each graph-derived signal.
