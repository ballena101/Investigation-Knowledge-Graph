# Databricks Notebooks

These files use Databricks source format (`# Databricks notebook source`) so they remain readable in Git and can be imported into Databricks as notebooks.

Execution order for the current Commodore Clipper PoC:

1. `01_neo4j_connection_test.py`
2. `02_publish_commodore_clipper_graph.py`
3. `03_enrich_node_labels.py`
4. `04_enrich_edge_evidence.py`
5. `05_validate_neo4j_projection.py`
6. `06_configure_databricks_app_resources.py`
7. `07_configure_relationship_review.py`
8. `08_configure_emcip_mapping_review.py`

Notebook 07 verifies the Neo4j review write path and creates the uniqueness constraint for relationship reviews.

Notebook 08 creates the uniqueness constraint for EMCIP mapping reviews.

The current App reads the published Neo4j graph and writes append-only relationship and EMCIP mapping review records to Neo4j. It does not require an additional SQL warehouse resource for the controlled PoC.

Future generic ingestion and LLM-assisted extraction notebooks are intentionally not implemented here yet because the agreed current scope remains Commodore Clipper only.


## Generic document-library workflow

- `13_register_analysis_from_volume_folder.py` — fallback notebook-only route: one volume folder becomes one analysis.
- `14_index_volume_documents_to_neo4j.py` — preferred App-assisted route: scan a user-accessible UC volume and publish document metadata to Neo4j. The App can then select existing documents without direct volume access.

The preferred PoC pattern is:

```text
User-managed UC volume
  → notebook 14 metadata index
  → Neo4j SourceDocument catalogue
  → App document selection
  → Neo4j AnalysisGroup
  → processing notebook under user identity
```
