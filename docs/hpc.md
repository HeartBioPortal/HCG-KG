# HPC Execution

The repository is designed for batch execution on shared compute infrastructure.

## Default profile

`hpc-large` is the default profile. It assumes:

- many workers
- larger batch sizes
- GPU availability for optional local-model extraction
- a durable graph backend, typically Neo4j
- headless execution

If your cluster job does not have access to a Neo4j server, use `hpc-networkx` instead. It keeps the larger extraction settings but persists the graph to local files under `data/processed/graph/`.

## Recommended workflow

1. The repo defaults already point at `data/raw/*.json` and `data/source_pdfs/`.
2. Override `HCG_KG_INPUT_GLOB` or `HCG_KG_SOURCE_PDF_DIR` only if you want to use a different corpus.
3. Set `HCG_KG_PROFILE=hpc-large` when Neo4j is available, or `HCG_KG_PROFILE=hpc-networkx` when it is not.
4. Provision the environment once outside the job if possible.
5. Run `normalize`, `build-graph`, and `build-embeddings` as separate jobs for easier retry.
6. Use the manifest in `data/processed/state/manifest.json` for resumability.

## Checkpointing

- `ingest` records discovered documents.
- `normalize` writes one normalized JSON per document.
- `build-graph` can skip already-normalized inputs and re-use the manifest.
- `resume` continues from the saved manifest and processed outputs.

## Logging

Use `--log-file` or set `runtime.log_level` in the profile. SLURM examples in `/Users/kvand/HeartBioPortal/HCG-KG/slurm` write both scheduler logs and application logs.
