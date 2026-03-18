# Query Contract

The query layer returns machine-readable responses intended for a future HeartBioPortal service.

## Gene query response

Fields:

- `query`: original user input
- `resolved_gene`: canonical resolved gene symbol
- `match_type`: exact or fuzzy
- `matches`: candidate gene matches with scores
- `guidelines`: referenced guideline summaries
- `conditions`: related condition summaries
- `biomarkers`: related biomarker summaries
- `drugs`: related drug summaries
- `recommendations`: recommendation objects with evidence and provenance
- `supporting_snippets`: source-grounded snippets
- `summary`: optional templated answer

## Design rules

- Every statement returned to the caller must be backed by one or more snippet records.
- Snippets are the atomic provenance object.
- Free-text summaries are optional and derived from structured results, not vice versa.
