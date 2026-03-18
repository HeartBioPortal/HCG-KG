# Architecture Overview

`hcg-kg` is built around a strict separation between offline build-time extraction and online query-time retrieval.

## Offline build phase

1. Discover parsed guideline JSON files.
2. Normalize heterogeneous raw JSON into a stable internal document model.
3. Emit source-grounded snippets with section, page, JSON pointer, and file provenance.
4. Run extraction over snippets and raw gene hints to generate graph nodes and relations.
5. Persist the graph to a backend such as NetworkX or Neo4j.
6. Optionally build a vector index over snippets for hybrid retrieval.
7. Save checkpoints and manifests so failed batch runs can resume.

## Online query phase

1. Resolve a gene symbol by exact or fuzzy match.
2. Pull the local subgraph around that gene.
3. Attach supporting snippets and provenance metadata.
4. Return structured results suitable for a HeartBioPortal service layer.
5. Optionally render a short grounded summary from graph results.

## Why this shape

- Parsed guideline JSON is heterogeneous, so normalization is the hard boundary where schema drift is contained.
- Heavy extraction happens once, offline.
- Query-time logic stays lightweight and auditable.
- Provenance is first-class at every stage.
- The graph backend is replaceable, but the graph schema and query contract remain stable.
