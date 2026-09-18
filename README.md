# Investigation Knowledge Graph

Evidence-grounded knowledge graph and review environment for heterogeneous investigation material.

This repository contains a standalone Proof of Concept (PoC) for representing investigation knowledge as an evidence-grounded graph. The immediate PoC is intentionally limited to the Commodore Clipper 2010 investigation, while the longer-term objective is to analyse one document, multiple documents, or an entire investigation evidence set, including reports, interview transcripts, witness statements, VDR/communications transcripts, technical notes, procedures, correspondence and other documentary evidence.

The current app is a deterministic viewer of already-processed analytical outputs. It does not call an LLM at runtime. Future phases will add LLM-assisted extraction, evidence grounding, review, heterogeneous-source analysis and cross-case knowledge discovery.

See the `docs/` folder for the project charter, methodology, architecture, governance, source model, corpus-analysis target and roadmap.
