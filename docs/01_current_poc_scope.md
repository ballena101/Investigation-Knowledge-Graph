# Current PoC Scope

## In scope

The current PoC is limited to the **Commodore Clipper 2010** investigation.

It demonstrates:

- case graph nodes and relationships;
- evidence-supported relationship review;
- EMCIP analytical mapping;
- preservation of intentionally unresolved concepts;
- graph publication to Neo4j;
- interactive exploration in a Databricks App.

## Out of scope for the current phase

The following are explicitly deferred:

- processing arbitrary uploaded PDFs;
- processing batches of documents;
- automatic interview-transcript ingestion;
- generic LLM extraction from new documents;
- cross-case analysis;
- automated review queues;
- OCR and difficult scanned-document handling.

These are future stages.

## Current graph

The PoC contains:

- 17 nodes;
- 12 relationships;
- 11 report-derived evidence-supported relationships;
- 1 structural `HAS_VESSEL` relationship.

## Current app behaviour

The deployed app:

- connects to Neo4j AuraDB;
- retrieves the Commodore Clipper graph;
- renders it interactively;
- exposes node properties, EMCIP mappings and relationship evidence.

It does not currently run an LLM or regenerate the graph.
