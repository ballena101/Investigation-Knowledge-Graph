# Investigation Knowledge Graph

Evidence-grounded knowledge graph and review environment for heterogeneous investigation material.

## Purpose

This repository contains a standalone Proof of Concept (PoC) for representing investigation knowledge as an evidence-grounded graph.

The immediate PoC is intentionally limited to the **Commodore Clipper 2010** investigation. The longer-term objective is broader: analyse one document, multiple documents, or an entire investigation evidence set, including heterogeneous sources such as:

- accident investigation reports;
- interview transcripts;
- witness statements;
- VDR or communications transcripts;
- technical inspection notes;
- procedures and manuals;
- correspondence and emails;
- recommendations and actions taken;
- other documentary evidence.

The system is designed so that graph relationships remain traceable to source evidence and analytical mappings can be reviewed rather than silently accepted.

## Current PoC

The current PoC demonstrates:

- a reviewed Commodore Clipper case graph;
- 17 nodes;
- 12 relationships;
- 11 report-derived relationships with supporting evidence;
- EMCIP candidate / reviewed mappings;
- Neo4j AuraDB as graph projection and query layer;
- a Databricks Streamlit App for interactive graph exploration;
- preservation of unresolved concepts rather than forced classification.

The current app is a deterministic viewer of already-processed analytical outputs. It does **not** call an LLM at runtime.

## Long-term target

The future target is an investigation knowledge environment in which:

```text
heterogeneous source material
        ↓
evidence units / passages / utterances
        ↓
LLM-assisted analytical extraction
        ↓
candidate entities / events / factors / claims / findings
        ↓
candidate relationships
        ↓
evidence grounding and validation
        ↓
human review where required
        ↓
case graph + cross-case graph
        ↓
query / comparison / pattern discovery
```

The future unit of analysis is therefore not "one PDF". It is an **investigation evidence corpus** that may contain many source types.

## Relationship to MAIRA

This project is independent from MAIRA.

A later generic-ingestion stage may reuse MAIRA's existing capabilities for:

- report acquisition;
- PDF extraction;
- page and passage generation;
- document provenance;
- retrieval.

This avoids rebuilding mature document-processing components. The Investigation Knowledge Graph layer remains conceptually separate and adds evidence-grounded entities, relationships, graph structure, analytical mappings and review.

The current Commodore Clipper PoC reuses existing Delta tables that were created during the workshop under the `bdw_analysis_prod.maira` schema. This is an implementation convenience, not project ownership. A dedicated schema is recommended for future development.

## Repository structure

```text
app/
    app.py
    app.yaml
    requirements.txt

docs/
    00_project_charter.md
    01_current_poc_scope.md
    02_methodology.md
    03_architecture.md
    04_data_model.md
    05_review_and_governance.md
    06_source_types.md
    07_future_corpus_analysis.md
    08_roadmap.md
    09_commodore_clipper_case.md

notebooks/
    01_neo4j_connection_test.py
    02_publish_commodore_clipper_graph.py
    03_enrich_node_labels.py
    04_enrich_edge_evidence.py
    05_validate_neo4j_projection.py
    06_configure_databricks_app_resources.py

sql/
    01_future_human_review_tables.sql
```

## Core principle

> Evidence first. Analysis is reviewable. Graph relationships are not accepted solely because they are plausible.

Chronology, causality, contribution and effect are distinct concepts and must not be conflated.

## Current technology

- Databricks / Unity Catalog / Delta: governed analytical storage
- Neo4j AuraDB: property-graph projection, traversal and exploration
- Databricks Apps + Streamlit: investigator-facing interface
- streamlit-cytoscape: graph visualisation
- LLM: not currently called by the deployed app; future analytical extraction layer only

## Status

Current status: **Commodore Clipper PoC — interactive graph viewer working**.

Next recommended PoC step: add a human review workflow for relationships and EMCIP mappings without expanding the source scope yet.
