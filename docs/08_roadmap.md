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
- end-to-end relationship validation persisted in Neo4j;
- append-only human-review provenance;
- reviewer identity captured from Databricks App headers;
- EMCIP mapping-review UI implemented in the App code.

Current implementation step:

- create the `EMCIPMappingReview` uniqueness constraint;
- redeploy the App;
- test one EMCIP mapping validation end to end.

Next after successful mapping-review validation:

- optionally add a controlled export of review records to Delta / Unity Catalog;
- freeze the controlled Commodore Clipper demonstrator before moving to generic ingestion.

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
