# Graph Schema

The first version uses a property-graph schema focused on gene-centric retrieval.

## Core node types

- `Guideline`: one node per source clinical guideline.
- `Section`: hierarchical section path inside a guideline.
- `Snippet`: text span extracted from the parsed JSON with provenance.
- `Gene`: gene symbol from upstream JSON or configured lexicons.
- `Condition`: disease, phenotype, or syndrome.
- `Biomarker`: biomarker or measured clinical quantity.
- `Drug`: drug, therapy, intervention, or care strategy.
- `Recommendation`: recommendation statement with evidence metadata when available.
- `EvidenceClass`: class of recommendation, such as `I` or `IIa`.
- `EvidenceLevel`: level of evidence, such as `A` or `B-R`.
- `Citation`: optional reference node for future expansion.

## Core edges

- `GENE_MENTIONED_IN`: `Gene -> Snippet`
- `ASSOCIATED_WITH_CONDITION`: `Gene -> Condition`
- `REFERENCED_IN_RECOMMENDATION`: `Gene -> Recommendation`
- `RECOMMENDS`: `Recommendation -> Drug`
- `CONTRAINDICATED_FOR`: `Recommendation -> Drug`
- `HAS_EVIDENCE_CLASS`: `Recommendation -> EvidenceClass`
- `HAS_EVIDENCE_LEVEL`: `Recommendation -> EvidenceLevel`
- `FROM_GUIDELINE`: `Snippet -> Guideline`
- `LOCATED_IN_SECTION`: `Snippet -> Section`
- `SUPPORTED_BY_SNIPPET`: `Recommendation -> Snippet`
- `CO_MENTIONED_WITH`: `Gene -> Biomarker`

## Provenance fields

Every snippet keeps:

- guideline id and title
- source JSON path
- source PDF path, if resolvable
- section path
- page, if available
- JSON pointer back into the parsed source object
- raw field name and extraction hints

Recommendation and association edges retain snippet identifiers so downstream services can render support spans.
