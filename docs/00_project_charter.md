# Project Charter

## Working name

**Investigation Knowledge Graph (IKG)**

## Mission

Develop an evidence-grounded knowledge environment for investigation material that helps investigators and reviewers understand, validate, compare and reuse analytical knowledge without losing traceability to source evidence.

## Immediate objective

Complete a bounded Proof of Concept using the Commodore Clipper 2010 investigation.

The current PoC is not intended to process arbitrary source material automatically. It demonstrates the downstream analytical representation, evidence links, graph projection and interactive review interface.

## Long-term objective

Support analysis of heterogeneous investigation evidence, including individual documents and groups of documents, and enable both within-case and cross-case analysis.

## Design principles

1. Evidence precedes interpretation.
2. Source evidence, case graph and analytical taxonomy mappings remain separate.
3. Causality is never inferred merely from chronology or textual proximity.
4. Unsupported mappings remain unresolved.
5. Automated or LLM-assisted outputs remain reviewable.
6. Human review must preserve provenance.
7. Storage and visualisation technologies are replaceable; the evidence model is not.
8. A case may contain many source documents and source types.
