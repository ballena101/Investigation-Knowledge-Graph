# Bosuil-informed coverage and retrieval improvements

## Purpose

This note records the IKF design decisions taken after comparing the current IKF pipeline with the public `Fenre1/Bosuil` investigation RAG implementation.

Bosuil is used only as a methodological comparison/reference. IKF governance, MAIRA canonical evidence identity, information-class routing, Neo4j provenance, EMCIP/SHIELD controls and human review remain authoritative.

## Problem observed in IKF

A normal Ask/Compare LLM answer identified more contributing-factor statements than were visible in Findings & Evidence and the Knowledge Graph for the same case.

This exposed a consistency gap between:

1. source evidence available to Ask/Compare;
2. structured analytical candidates produced during notebook 16;
3. consolidated/published Findings & Evidence;
4. the Knowledge Graph.

Ask/Compare must not silently become a second source of graph truth. The correct target is one evidence base feeding one comprehensive structured analysis, with Findings & Evidence and the Knowledge Graph acting as two views of the same structured result.

## Bosuil ideas retained

### 1. Document-wide ledger / final consolidation

Bosuil processes contiguous chunk batches and then performs a final document-wide consolidation that removes duplicates and combines compatible statements while retaining contributing chunk references.

IKF should adopt the principle, not the implementation:

`canonical evidence passages -> batch extraction -> category coverage review -> global consolidation -> structured findings -> graph publication`

The global consolidation must preserve all supporting passage/page references and must not invent unsupported facts or causal relationships.

### 2. Separate source passage from retrieval representation

Bosuil keeps the stored source passage distinct from embedding-only context such as headings, metadata and bounded overlap.

IKF should preserve MAIRA canonical passage text and identity unchanged while allowing a separate retrieval representation containing governed metadata such as document title, section heading and bounded neighbouring context.

This representation must never replace or mutate the canonical MAIRA passage.

### 3. Hybrid retrieval as an experiment, not an immediate replacement

Bosuil supports keyword, semantic, hybrid and HyDE retrieval.

IKF currently has deterministic lexical retrieval plus an all-passages path for small scopes. The next benchmark should compare:

- current all-passages path;
- current deterministic lexical retrieval;
- lexical + semantic hybrid retrieval.

HyDE is deferred until simpler hybrid retrieval is benchmarked and shown to improve recall without weakening provenance or governance.

### 4. Retrieval evaluation

Bosuil includes end-to-end RAG evaluation with stored questions, expected answers, generated answers, judge scores and run parameters.

IKF should extend its existing governed benchmark framework with retrieval-specific measures:

- recall@k against a human-reviewed relevant-passage set;
- citation precision;
- answer-support rate;
- unsupported-claim rate;
- retrieval stability;
- latency;
- prompt/completion token usage;
- human amendment/rejection effort.

Model quality and retrieval quality must be measured separately.

### 5. Graph readability

Bosuil dynamically sizes entity rectangles to rendered labels and wraps long/multiword names.

IKF should adopt equivalent usability principles:

- high-contrast dark text on light nodes;
- label wrapping without truncation;
- node dimensions that expand for rendered labels;
- consistent semantic shapes only where useful;
- readable minimum font size;
- clear selected-node state;
- warnings/limits for dense graphs.

## Immediate implementation sequence

### Step 1 — Coverage diagnostic

Notebook `56_validate_structured_analysis_coverage.py` is read-only and compares notebook-16 candidate concepts with concepts actually published as `KGNode` nodes.

It answers the first diagnostic question:

- If a missing concept is absent from `analysis_candidate`, extraction recall is the problem.
- If it exists in `analysis_candidate` but is absent from the published graph, consolidation/publication is the problem.

Exact normalized-label matching is intentionally conservative and is a review signal rather than proof of loss because legitimate canonicalisation can change wording.

### Step 2 — Category coverage pass

After the diagnostic is run on the current Class-B case, add a bounded evidence-grounded coverage pass for:

- Event;
- ContributingFactor;
- Finding;
- SafetyIssue;
- Recommendation.

The pass must search only the already-governed evidence passages, preserve provenance and return `NO_ADDITIONAL_SUPPORTED_ITEM` where evidence does not support another item.

### Step 3 — Global consolidation

Consolidate preliminary candidates across all batches. Merge only semantically compatible items and union their passage/page references. Do not merge distinct contributing factors merely because they share a target outcome.

### Step 4 — Findings/Graph consistency

Findings & Evidence should always expose all six analytical groups:

- Events;
- Contributing factors;
- Findings;
- Safety issues;
- Safety recommendations;
- Relationships.

Empty groups must remain visible with a `0 identified` state.

The Knowledge Graph must be generated from the same consolidated structured set.

### Step 5 — Ask/Compare consistency signal

Ask/Compare remains question-dependent and read-only with respect to the structured analysis. If an answer cites evidence supporting a concept not represented in the structured analysis, the UI may flag a coverage inconsistency for investigator review; it must not automatically mutate the graph.

### Step 6 — Faster Ask/Compare

Benchmark retrieval before changing defaults. The intended direction is to avoid sending very large all-passages scopes when a smaller evidence package can achieve equal or better grounded recall.

Stable Python dependencies should move from per-run notebook installation into the Databricks Job/serverless environment where practical.

### Step 7 — Graph Q&A

Graph questions should distinguish:

- what is currently represented in the graph; and
- what the underlying selected evidence may additionally support.

Graph Q&A must not silently mutate graph knowledge. A coverage discrepancy can be surfaced as a candidate review signal.

## Governance constraints

- MAIRA passage identity and exact source text remain canonical.
- Reference context is not occurrence evidence.
- EMCIP and SHIELD remain governed taxonomies/reference layers and are not silently converted into case facts.
- Assistant candidates remain distinct from human-validated knowledge.
- Chronology is never promoted automatically to causality.
- Every structured item and relationship must retain evidence provenance.
- Human validation remains append-only and authoritative where required.

## Status

- Bosuil comparison: reviewed and retained as methodological reference.
- Coverage diagnostic notebook: implemented.
- Extraction coverage pass: pending diagnostic result.
- Global consolidation refinement: pending diagnostic result.
- Hybrid retrieval benchmark: planned.
- App UI changes (reference-context checkbox simplification, answer-local refresh/status, graph readability, collapsible validation): bundled for the next App update/redeploy.
