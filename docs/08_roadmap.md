# Roadmap

## Phase 0 — Current PoC

Status: active / substantially complete.

Scope: Commodore Clipper only.

Completed:

- reviewed graph;
- evidence-linked relationships;
- EMCIP mapping layer;
- Neo4j projection;
- Databricks interactive graph app;
- relationship-review UI;
- auditable human-review table design;
- Databricks App resource setup notebook for review persistence.

Current implementation step:

- create the governed relationship-review table;
- attach a SQL warehouse and the review table to the App;
- deploy and test Validate / Reject / Amend end to end.

Next after successful relationship-review validation:

- implement EMCIP mapping review using the same provenance pattern.

## Phase 1 — Generic controlled ingestion

Deferred until the controlled PoC review workflow is proven.

Goal: parameterise the existing workflow so new investigation material does not require case-specific code.

Reuse MAIRA document-processing components where practical for source acquisition, extraction, passaging and provenance, while keeping this project separate.

Estimated work for a usable multi-document controlled PoC: approximately **32–55 hours** based on the current prototype and existing MAIRA PDF infrastructure.

Main work items:

- remove case-specific constants;
- generic case/source IDs;
- connect to reusable extraction/passaging;
- generic node extraction;
- generic relationship extraction;
- evidence-linking;
- mapping workflow;
- generic Neo4j publication;
- app orchestration;
- test on heterogeneous sources.

## Phase 2 — Heterogeneous investigation evidence

Add:

- interview transcripts;
- witness statements;
- VDR / communications transcripts;
- procedures;
- correspondence;
- technical documentation.

## Phase 3 — Corpus and cross-case knowledge

Add:

- graph normalisation across cases;
- cross-case traversal;
- recurring-factor analysis;
- similarity search;
- corroboration / contradiction;
- recommendations / actions chain.

## Phase 4 — Production hardening

Potential requirements:

- OCR;
- access control;
- audit logging;
- retries;
- model/version governance;
- evaluation benchmarks;
- performance testing;
- data retention policy;
- review workload metrics.
