# Example Queries

These examples are intentionally written as pseudo-queries so they can be adapted to either the NetworkX backend, Neo4j/Cypher, or the HBP service layer.

## Guideline context for a gene

```cypher
MATCH (g:Gene {gene_symbol: "LDLR"})-[:GENE_MENTIONED_IN]->(s:Snippet)-[:FROM_GUIDELINE]->(doc:Guideline)
OPTIONAL MATCH (rec:Recommendation)-[:SUPPORTED_BY_SNIPPET]->(s)
RETURN g.gene_symbol, doc.guideline_id, s.snippet_id, s.page, s.text, rec.recommendation_id
LIMIT 25;
```

## Recommendations linked to a condition

```cypher
MATCH (gene:Gene)-[:ASSOCIATED_WITH_CONDITION]->(condition:Condition {condition_name: "familial hypercholesterolemia"})
OPTIONAL MATCH (gene)-[:REFERENCED_IN_RECOMMENDATION]->(rec:Recommendation)
OPTIONAL MATCH (rec)-[:HAS_EVIDENCE_CLASS]->(class:EvidenceClass)
OPTIONAL MATCH (rec)-[:HAS_EVIDENCE_LEVEL]->(level:EvidenceLevel)
RETURN gene.gene_symbol, condition.condition_name, rec.recommendation_id, class.code, level.code;
```

## Genes or variants mentioned in guideline snippets

```cypher
MATCH (s:Snippet)<-[:GENE_MENTIONED_IN]-(gene:Gene)
OPTIONAL MATCH (variant:Variant)-[*1..2]-(s)
RETURN s.guideline_id, s.section_path, s.page, gene.gene_symbol, variant.variant_id, s.text
LIMIT 50;
```

## Drug or intervention context

```cypher
MATCH (rec:Recommendation)-[rel:RECOMMENDS|CONTRAINDICATED_FOR]->(drug:Drug)
OPTIONAL MATCH (rec)-[:SUPPORTED_BY_SNIPPET]->(s:Snippet)-[:FROM_GUIDELINE]->(doc:Guideline)
RETURN drug.intervention_name, type(rel), rec.recommendation_id, doc.guideline_id, s.snippet_id, s.text
LIMIT 25;
```

## CLI examples

```bash
hcg-kg run-pipeline --profile local-dev --input-glob "data/sample/*.json"
hcg-kg query --profile local-dev --gene LDLR --pretty
hcg-kg inspect-gene --gene APOE
hcg-kg export-subgraph --gene LDLR --output /tmp/ldlr_subgraph.json
```
