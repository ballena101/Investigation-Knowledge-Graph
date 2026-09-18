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


## End-to-end generic analysis pipeline

1. `14_index_volume_documents_to_neo4j.py`
   - scans the user-managed Unity Catalog document library;
   - publishes SourceDocument metadata to Neo4j.

2. App → **New analysis**
   - select 1–5 indexed documents;
   - create one AnalysisGroup;
   - status becomes PENDING_PROCESSING.

3. `15_extract_analysis_evidence.py`
   - reads the selected source files under the notebook user's identity;
   - supports PDF, DOCX and TXT;
   - extracts deterministic passages with document/page provenance;
   - detects language;
   - persists passages to Delta;
   - status becomes EVIDENCE_READY.

4. `16_analyse_evidence_and_build_graph.py`
   - performs evidence-grounded candidate extraction in batches;
   - resolves duplicate concepts across the selected document group;
   - consolidates only already-supported relationships;
   - publishes one generic Neo4j graph;
   - stores overview, key findings, uncertainties and source conflicts;
   - status becomes COMPLETED.

5. App → **Analyses**
   - shows extraction/analysis progress;
   - shows the completed summary and generic graph.

Causality is never inferred from chronology alone. Generated graph relationships remain assistant candidates until human review.
