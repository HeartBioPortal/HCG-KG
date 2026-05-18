# Repository Manifest

## Code

- `src/hcg_kg/`: Python package for ingestion, normalization, extraction, graph building, vector indexing, storage manifests, and query service.
- `configs/`: local, HPC, Neo4j, NetworkX, and LLM profile configuration plus the graph schema YAML.
- `examples/`: CLI examples.
- `slurm/`: BigRed/HPC batch scripts.
- `docker/`: local container and Neo4j support.
- `tests/`: unit and workflow tests for CLI, config, extraction, normalization, and pipeline/query behavior.

## Inputs and examples

- `data/raw/*.json`: parsed guideline JSON inputs vendored for graph ingestion.
- `data/source_pdfs/`: source PDFs used as provenance references; redistribution rights require review.
- `data/sample/`: small sample input for tests and demos.
- `data/processed/`: generated outputs; only `.gitkeep` is committed by default.

## Release metadata and documentation

- `README.md`: overview, setup, usage, HBP 3.0 role, and safety/privacy cautions.
- `KG_SCHEMA.md`: graph node and edge schema documentation.
- `GRAPH_MANIFEST.tsv`: graph release inventory and count placeholders.
- `EXAMPLES.md`: example graph query patterns.
- `PROVENANCE_SCHEMA.md`: provenance fields expected on nodes and edges.
- `RELEASE_NOTES.md`: HBP 3.0 manuscript release notes.
- `CITATION.cff` and `.zenodo.json`: citation and archive metadata.
- `scripts/generate_checksums.sh`: checksum helper for release-relevant static files.

## Do not include without review

- API keys, Neo4j passwords, or `.env`
- protected or controlled human data
- source PDFs or long snippets without redistribution permission
- generated graph dumps or vector indexes unless intended, permitted, and documented for archive
