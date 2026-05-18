# Release Notes

## v3.0.0-nar

This release prepares HCG-KG as the clinical guideline knowledge graph resource for the HeartBioPortal 3.0 NAR Database Issue manuscript archive.

Included release-support material:

- `KG_SCHEMA.md` summarizing actual node and edge types from `configs/schema/kg_schema.yaml`
- `GRAPH_MANIFEST.tsv` for graph release metadata
- `EXAMPLES.md` with gene, condition, snippet, and drug/intervention query examples
- `PROVENANCE_SCHEMA.md` for node and edge provenance expectations
- `MANIFEST.md`, `CITATION.cff`, `.zenodo.json`, and checksum tooling
- README sections linking HCG-KG to HCG, DataHub, the HeartBioPortal organization, and the live site

The repository currently vendors 37 parsed guideline JSON inputs under `data/raw/`. Final graph node and edge counts require running the release pipeline and exporting the build manifest before GitHub/Zenodo release.

Third-party guideline documents and parsed snippets remain subject to source terms. Do not redistribute source PDFs, long snippets, or generated outputs unless rights are confirmed.
