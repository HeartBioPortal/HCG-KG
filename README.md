# hcg-kg

`hcg-kg` builds a local, queryable biomedical knowledge graph from parsed clinical guideline JSON files, with an initial focus on AHA guideline content for downstream use in HeartBioPortal.

This repository is not about training an LLM on PDFs. The parsed guideline JSON files are treated as the source corpus for ingestion, normalization, structured extraction, graph construction, and source-grounded retrieval. The vendored PDFs are included only as source references for provenance attachment and downstream inspection. Optional local LLMs can assist extraction or summarization offline, but the runtime system is designed to answer from a graph plus provenance-bearing snippets.

## Proposed repository architecture and rationale

- `src/hcg_kg`: typed Python package for ingestion, normalization, extraction, graph persistence, and querying.
- `configs/`: YAML profiles for `local-dev`, `local-medium`, and default `hpc-large`.
- `data/`: vendored AHA parsed JSON inputs in `raw/`, vendored source PDFs in `source_pdfs/`, empty `processed/`, and a representative sample guideline JSON for tests and demo runs.
- `docs/`: schema, architecture, query contract, and HPC execution notes.
- `examples/`: short CLI examples.
- `slurm/`: batch scripts for HPC execution.
- `docker/`: container assets, including a local Neo4j compose file.
- `tests/`: normalization, extraction, graph, and CLI coverage over sample data.

This layout keeps the repository open-source friendly, reproducible, and ready for both laptop iteration and large offline runs on a cluster.

## Chosen stack

- Python 3.11+
- Typer CLI for a clean command surface
- Pydantic models for typed schemas and configuration validation
- YAML profiles for reproducible environment-specific configuration
- NetworkX backend for local development and tests
- Neo4j backend for larger graph persistence workloads
- Optional TF-IDF snippet index for lightweight hybrid retrieval
- Optional LlamaIndex / Hugging Face / Ollama extras for future local-model extraction

### Why this stack

The first version prioritizes robust, source-grounded extraction from heterogeneous parsed JSON. That makes a defensive normalization layer and explicit schema control more important than coupling the core pipeline to any single orchestration library. The repository still exposes clear extension points for LlamaIndex or local-model extractors, while keeping the default path fully open-source and runnable without a finetuning workflow.

## Repository tree

```text
hcg-kg/
├── .github/workflows/ci.yml
├── configs/
│   ├── profiles/
│   └── schema/kg_schema.yaml
├── data/
│   ├── processed/
│   ├── raw/
│   └── sample/
├── docker/
├── docs/
├── examples/
├── scripts/
├── slurm/
├── src/hcg_kg/
└── tests/
```

## What the project does

Given parsed guideline JSON files, the pipeline:

1. normalizes heterogeneous raw structures into a stable internal document model
2. preserves provenance for guideline title, section path, page, snippet text, and source paths
3. extracts gene-centric biomedical entities and relations
4. builds a local knowledge graph
5. optionally builds a snippet index for hybrid retrieval
6. exposes a query interface for gene-first lookup and grounded question answering

Example downstream questions:

- What does this guideline say about gene `LDLR`?
- What recommendations, evidence classes, conditions, biomarkers, drugs, or related entities are associated with `APOE`?
- Which exact snippets and page references support those statements?

## Why a graph is better than raw JSON search

Raw JSON search can recover text, but it does not resolve entity identity, relation structure, or cross-document traversal. A graph supports:

- gene-first lookup over heterogeneous guideline structure
- explicit relations between genes, recommendations, conditions, drugs, and biomarkers
- easier downstream API integration for HeartBioPortal
- provenance-preserving traversal from an answer back to the source snippet
- future extension across additional guideline families such as ESC

## Configuration profiles

The repository ships with three profiles:

- `local-dev`: smallest settings, defaults to `data/sample/*.json`
- `local-medium`: larger local run without assuming a graph server
- `hpc-large`: default profile, tuned for cluster-scale offline extraction and Neo4j persistence

`hpc-large` is the default unless you pass `--profile` or set `HCG_KG_PROFILE`.

## Setup

### Laptop setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Run the demo pipeline:

```bash
hcg-kg run-pipeline --profile local-dev --input-glob "data/sample/*.json"
hcg-kg query --profile local-dev --gene LDLR --pretty
```

### Neo4j setup

For a local property graph service:

```bash
cp .env.example .env
docker compose -f docker/docker-compose.neo4j.yml up -d
```

Set `NEO4J_PASSWORD` and, if needed, override `NEO4J_URI`.

### HPC setup

1. Clone the repository onto the cluster.
2. Create or activate a Python 3.11+ environment.
3. Export:

```bash
export HCG_KG_PROFILE=hpc-large
export NEO4J_PASSWORD="..."
```

4. Because the parsed AHA JSONs and source PDFs are vendored in `data/raw/*.json` and `data/source_pdfs/`, you can use the repo defaults and skip both `HCG_KG_INPUT_GLOB` and `HCG_KG_SOURCE_PDF_DIR` unless you want to override them.
5. Submit the stage-specific SLURM jobs from `/Users/kvand/HeartBioPortal/HCG-KG/slurm`, or run the CLI directly in batch jobs.

## CLI overview

```bash
hcg-kg ingest
hcg-kg normalize
hcg-kg build-graph
hcg-kg build-embeddings
hcg-kg query --gene LDLR
hcg-kg inspect-document --path data/sample/aha_sample_guideline.json
hcg-kg inspect-gene --gene APOE
hcg-kg export-subgraph --gene LDLR --output /tmp/ldlr_subgraph.json
hcg-kg validate
hcg-kg run-pipeline
hcg-kg resume
```

On a fresh clone, the shortest end-to-end path is:

```bash
hcg-kg run-pipeline --profile hpc-large
hcg-kg query --profile hpc-large --gene LDLR --pretty
```

## Source grounding and provenance

Every extracted statement should remain traceable to:

- source guideline
- section path
- page number, if available
- snippet text
- source JSON path
- source PDF path, when resolvable
- JSON pointer into the parsed source structure

This repository is explicitly designed to avoid a black-box chatbot workflow.

## Incremental and resumable processing

- `ingest` discovers inputs and writes a manifest
- `normalize` writes one normalized document file per input
- `build-graph` reads normalized files and persists graph state
- `build-embeddings` writes a reusable snippet index
- `resume` reuses the manifest and skips finished work unless `--force` is passed

This supports long-running cluster jobs where retries should not rebuild the world.

## Open-source license choice

The repository uses Apache 2.0. It is permissive, contributor-friendly, and includes a patent grant, which is useful for biomedical and translational informatics projects that may later integrate into larger research or production systems.

## Plug-in points for exact AHA JSON schema details

The normalization layer is intentionally defensive because the current AHA parsed JSON files are heterogeneous. The main places to tighten once the exact schema is fully characterized are:

- `src/hcg_kg/ingest/normalizer.py`: add explicit handlers for stable page, table, citation, and recommendation objects once known
- `src/hcg_kg/extract/heuristic.py`: replace or augment heuristics with schema-aware or local-model extraction
- `configs/profiles/*.yaml`: tune chunk sizes, worker counts, and retrieval settings for Big Red 200
- `docs/schema.md`: extend relation types as additional downstream requirements emerge

The vendored PDF copies do not change the ingestion model. They are used only for provenance path resolution.

## Limitations in v0.1

- Extraction is heuristic-first and intentionally conservative.
- Variant extraction is scaffolded but not deeply implemented yet.
- Citation graphing is minimal.
- Vector retrieval is TF-IDF based by default; neural embeddings are optional future work.
- The Neo4j backend is implemented as an optional runtime dependency.

## Future work

- stronger entity normalization against HGNC and biomedical ontologies
- richer recommendation and evidence parsing from known AHA section layouts
- better citation extraction and reference linking
- hybrid retrieval with local embedding models
- ESC and other guideline-family adapters
- HeartBioPortal-facing REST service layer
