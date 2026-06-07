# hcg-kg

`hcg-kg` builds a local, queryable biomedical knowledge graph from parsed clinical guideline JSON files, with an initial focus on AHA guideline content for downstream use in HeartBioPortal.

For HBP 3.0, HCG-KG is the clinical guideline knowledge graph resource. HCG prepares and extracts structured guideline JSON, HCG-KG normalizes that content into graph nodes and edges, and HeartBioPortal uses the resulting guideline context in gene search dossiers through guideline summary/detail layers.

This repository is not about training an LLM on PDFs. The parsed guideline JSON files are treated as the source corpus for ingestion, normalization, structured extraction, graph construction, and source-grounded retrieval. The vendored PDFs are included only as source references for provenance attachment and downstream inspection. Optional local LLMs can assist extraction or summarization offline, but the runtime system is designed to answer from a graph plus provenance-bearing snippets.

## Current working path

The workflow that worked end-to-end for the AHA corpus was:

1. Build the graph on Big Red 200 from the parsed guideline JSON files in `data/raw/*.json`.
2. Use `hpc-networkx` for the deterministic heuristic graph when Neo4j is not reachable from the cluster.
3. Use `hpc-llm` through SLURM for LlamaIndex + Hugging Face extraction on a GPU node.
4. Treat the final build artifact as a file-backed graph snapshot at `data/processed/graph/networkx_graph.json`.
5. Copy that graph snapshot to AWS or a laptop for testing, then load or query it from the HeartBioPortal backend environment.

Known successful outputs:

- Heuristic `hpc-networkx` run over 37 AHA guideline JSONs produced a graph with about 21k nodes and 43k edges, plus a TF-IDF snippet index for 16k snippets.
- LLM `hpc-llm` runs produce the same artifact type, `networkx_graph.json`, but the nodes and edges come from the LlamaIndex/Hugging Face extractor.
- Gene queries such as `LDLR` now use a constrained gene-centric traversal. They return directly linked snippets, recommendations, related entities, evidence metadata, and guideline names instead of expanding through a whole guideline and pulling unrelated sections.

The most practical production shape is: build offline on HPC, copy the graph artifact to the serving environment, load it into Neo4j there, and let the HeartBioPortal backend query Neo4j. Neo4j does not need to run on the HPC cluster.

Important rebuild behavior: use `--force` when changing the input corpus. Current code treats `--force` as a clean rebuild for the manifest and the file-backed NetworkX graph snapshot. Older versions reused `data/processed/state/manifest.json` and loaded an existing `data/processed/graph/networkx_graph.json`, which could accidentally mix legacy guideline data into a new graph. If you are using an older checkout, delete `data/processed/state/manifest.json`, `data/processed/normalized/`, `data/processed/graph/networkx_graph.json`, and `data/processed/vector/tfidf_index.joblib` before rebuilding.

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
- Optional LlamaIndex / Hugging Face extraction backend for offline LLM-assisted graph construction

### Why this stack

The first version prioritizes robust, source-grounded extraction from heterogeneous parsed JSON. The deterministic extractor is useful for debugging and baseline graph construction. The LlamaIndex/Hugging Face extractor is used offline when richer semantic extraction is needed. In both cases, runtime querying is graph-first and does not depend on live LLM calls or finetuning.

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

The repository ships with these profiles:

- `local-dev`: smallest settings, defaults to `data/sample/*.json`
- `local-medium`: larger local run without assuming a graph server
- `hpc-large`: default profile, tuned for cluster-scale offline extraction and Neo4j persistence
- `hpc-networkx`: HPC-oriented extraction settings with a file-backed graph for clusters without Neo4j
- `hpc-llm`: HPC-oriented extraction settings that use a local Hugging Face model through LlamaIndex

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

If Neo4j is installed through Homebrew on macOS, the local Browser usually runs at:

```text
http://localhost:7474
```

Use `bolt://localhost:7687`, username `neo4j`, and your configured password. For a quick graph sanity check in Neo4j Browser:

```cypher
MATCH ()-[r]->()
RETURN type(r) AS relation, count(*) AS count
ORDER BY count DESC;
```

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

If Neo4j is not available on the cluster, use:

```bash
export HCG_KG_PROFILE=hpc-networkx
```

If you want LLM-based extraction with a local Hugging Face model through LlamaIndex:

```bash
pip install -e ".[llm]"
pip install llama-index-llms-huggingface
export HCG_KG_PROFILE=hpc-llm
```

The default `hpc-llm` profile uses `Qwen/Qwen2.5-7B-Instruct`. If you have already cached a different local model on the cluster, override it with `models.model_name` in a profile or by editing `configs/profiles/hpc-llm.yaml`.
Do not run `hpc-llm` on the login node for the full corpus. Submit it through SLURM instead, for example:

```bash
sbatch -A <RT_PROJECT> slurm/run_pipeline_llm.slurm
```

The script targets the Big Red 200 `gpu` partition by default.

On Big Red 200, include the RT Project account when submitting. For the allocation used during development:

```bash
sbatch -A r01806 slurm/run_pipeline_llm.slurm
```

If the job is pending, check scheduler state with:

```bash
squeue -j <jobid>
scontrol show job <jobid>
tail -f logs/slurm-llm-pipeline-<jobid>.out
tail -f logs/llm_pipeline_<jobid>.log
```

Do not run the full LLM pipeline on a login node. Big Red 200 terminates long interactive jobs.

### Final graph artifacts

Both `hpc-networkx` and `hpc-llm` write the graph to:

```text
data/processed/graph/networkx_graph.json
```

Additional useful artifacts are:

```text
data/processed/vector/tfidf_index.joblib
data/processed/state/manifest.json
```

The graph JSON is the primary artifact. It is a NetworkX node-link JSON file containing graph nodes, edge relations, and provenance properties. The TF-IDF file is optional and supports snippet search for question-style retrieval.

To protect an LLM-built graph from being overwritten by another run:

```bash
cp data/processed/graph/networkx_graph.json data/processed/graph/networkx_graph_llm.json
```

### Copying artifacts

From Big Red 200 to AWS:

```bash
ssh -i ~/.ssh/hbp.pem ubuntu@3.130.100.250 'mkdir -p ~/HCG-KG/data/processed/graph ~/HCG-KG/data/processed/vector ~/HCG-KG/data/processed/state'
scp -i ~/.ssh/hbp.pem ~/HCG-KG/data/processed/graph/networkx_graph.json ubuntu@3.130.100.250:~/HCG-KG/data/processed/graph/
scp -i ~/.ssh/hbp.pem ~/HCG-KG/data/processed/vector/tfidf_index.joblib ubuntu@3.130.100.250:~/HCG-KG/data/processed/vector/
scp -i ~/.ssh/hbp.pem ~/HCG-KG/data/processed/state/manifest.json ubuntu@3.130.100.250:~/HCG-KG/data/processed/state/
```

From AWS to a laptop:

```bash
mkdir -p ~/Downloads/hcgkg_llm/graph ~/Downloads/hcgkg_llm/vector ~/Downloads/hcgkg_llm/state
scp -i ~/.ssh/hbp.pem ubuntu@3.130.100.250:~/HCG-KG/data/processed/graph/networkx_graph.json ~/Downloads/hcgkg_llm/graph/
scp -i ~/.ssh/hbp.pem ubuntu@3.130.100.250:~/HCG-KG/data/processed/vector/tfidf_index.joblib ~/Downloads/hcgkg_llm/vector/
scp -i ~/.ssh/hbp.pem ubuntu@3.130.100.250:~/HCG-KG/data/processed/state/manifest.json ~/Downloads/hcgkg_llm/state/
```

### Loading a graph snapshot into Neo4j

The repository can query a file-backed NetworkX graph directly, but HeartBioPortal serving should use Neo4j. Until a dedicated `sync-neo4j` command is added, load a copied snapshot with this script from the repo root:

```bash
pip install -e ".[neo4j]"

mkdir -p data/processed/graph
cp ~/Downloads/hcgkg_llm/graph/networkx_graph.json data/processed/graph/networkx_graph.json

export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD="your-password"
```

```bash
python - <<'PY'
from pathlib import Path
from hcg_kg.config import load_settings
from hcg_kg.graph.backends.networkx_backend import NetworkXBackend
from hcg_kg.graph.backends.neo4j_backend import Neo4jBackend

root = Path.cwd()
settings = load_settings(profile="hpc-networkx", project_root=root)

src = NetworkXBackend(settings)
src.initialize()

dst_settings = settings.model_copy(deep=True)
dst_settings.graph.backend = "neo4j"
dst_settings.graph.neo4j_uri = "bolt://localhost:7687"
dst_settings.graph.neo4j_username = "neo4j"

dst = Neo4jBackend(dst_settings)
dst.initialize()

nodes = src.list_nodes()
edges = {}
for node in nodes:
    for edge in src.get_edges(node.node_id, direction="out"):
        edges[edge.edge_id] = edge

dst.upsert_nodes(nodes)
dst.upsert_edges(list(edges.values()))
dst.close()
src.close()

print({"nodes": len(nodes), "edges": len(edges)})
PY
```

Import into an empty Neo4j database for clean tests. Otherwise old nodes from earlier graph versions may remain.

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

If you do not have a reachable Neo4j service, run:

```bash
hcg-kg run-pipeline --profile hpc-networkx
hcg-kg query --profile hpc-networkx --gene LDLR --pretty
```

For LLM-based extraction:

```bash
hcg-kg run-pipeline --profile hpc-llm
hcg-kg query --profile hpc-llm --gene LDLR --pretty
```

To summarize the local graph snapshot:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

data = json.loads(Path("data/processed/graph/networkx_graph.json").read_text())
nodes = data.get("nodes", [])
edges = data.get("edges") or data.get("links") or []
label_by_id = {node.get("id", node.get("node_id")): node.get("label", "Unknown") for node in nodes}

print(f"nodes={len(nodes)}")
print(f"edges={len(edges)}")

print("\nNode types")
for label, count in Counter(node.get("label", "Unknown") for node in nodes).most_common():
    print(f"{label}\t{count}")

print("\nRelation types")
for relation, count in Counter(edge.get("relation", "<missing>") for edge in edges).most_common():
    print(f"{relation}\t{count}")

print("\nTop source-[relation]->target patterns")
patterns = Counter(
    (
        label_by_id.get(edge.get("source"), "Unknown"),
        edge.get("relation", "<missing>"),
        label_by_id.get(edge.get("target"), "Unknown"),
    )
    for edge in edges
)
for (source_label, relation, target_label), count in patterns.most_common(40):
    print(f"{source_label} -[{relation}]-> {target_label}\t{count}")
PY
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

## How this repository supports HBP 3.0

HCG-KG connects cardiovascular guideline source evidence to genes, variants, conditions, biomarkers, recommendations, evidence classes, evidence levels, and drugs/interventions in a provenance-bearing graph. HBP can query this graph or exported graph artifacts to show guideline context alongside gene, variant, protein, association, and drug-discovery evidence.

Related HBP 3.0 repositories:

- HeartBioPortal organization: https://github.com/HeartBioPortal
- Live site: https://heartbioportal.org/
- HCG guideline extraction resource: https://github.com/HeartBioPortal/HCG
- DataHub: https://github.com/HeartBioPortal/DataHub

## Manuscript release

This repository supports the HeartBioPortal 3.0 NAR Database Issue manuscript release (`v3.0.0-nar`). Release-support files include graph schema documentation, graph/output manifests, examples, provenance documentation, citation metadata, Zenodo metadata, and checksum tooling.

Guideline graph outputs expose source-grounded context only. They are not medical advice, automated clinical recommendations, or direct clinical actionability.

## Security and privacy

No controlled individual-level human data should be committed. Do not commit API keys, credentials, protected data, tokens, or restricted source data. Guideline PDFs, snippets, and parsed source JSON remain subject to source-specific licensing and publisher/society terms.
