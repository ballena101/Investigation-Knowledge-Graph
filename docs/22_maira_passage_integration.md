# MAIRA passage integration

Status: first read-only integration slice

## Purpose

IKF already records model runs, candidate graph output and human review. MAIRA
already records deterministic investigation passages and provenance. The first
integration slice connects those existing layers without changing the current
production tables or treating model output as knowledge.

```text
MAIRA document + passages
          ↓ read-only contract
IKF analysis association
          ↓ identical evidence
GPT-OSS 20B      Llama 3.3 70B
          ↓ independent candidates
human VALIDATE / AMEND / REJECT
          ↓
validated graph → SHIELD classification
```

## Current duplication

`notebooks/15_extract_analysis_evidence.py` currently parses files and creates
`bdw_analysis_prod.kg_poc.analysis_passage`. This duplicates part of MAIRA and
uses a different passage identity/chunking strategy. It remains operational
during parity validation; it is not the target long-term ownership boundary.

## First executable checkpoint

Run `notebooks/25_validate_maira_passage_bridge.py` with an `analysis_id` whose
documents are present in both repositories' Delta schemas.

The notebook:

- matches `kg_poc.analysis_document` to `maira.documents` by full SHA-256;
- requires exactly one MAIRA document match for every IKF analysis document;
- exposes MAIRA passages through `maira_ikf_passage_bridge`;
- preserves the MAIRA passage ID, text, hash, page bounds and chunking version;
- recomputes passage hashes and fails closed on integrity errors;
- performs no writes.

The expected final output is:

```text
PASS — MAIRA_IKF_PASSAGE_V0.1
```

## What this checkpoint does not do

It does not replace notebook 15, persist a new table, invoke either LLM, modify
the graph, or classify SHIELD. Those changes follow only after passage parity
and one end-to-end reviewed case are confirmed.

## Next checkpoint

Using the temporary bridge view, run both models on the same frozen MAIRA
passages and compare the results with the existing IKF passage run. Measure:

- evidence retrieval/coverage;
- evidence-reference accuracy;
- validated, amended and rejected relationships;
- causal-overreach failures;
- human review effort.

Only then should the document branch of notebook 15 be replaced. Direct text is
kept as a separate IKF ingress until its chunking calls the reusable MAIRA
component.
