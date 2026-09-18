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

Notebook 07 creates the governed relationship-review table and atomically attaches the SQL warehouse and UC table resources while preserving the three Neo4j secret resources.

The current app reads the published Neo4j graph and can write human relationship-review decisions to Unity Catalog.

Future generic ingestion and LLM-assisted extraction notebooks are intentionally not implemented here yet because the agreed current scope remains Commodore Clipper only.
