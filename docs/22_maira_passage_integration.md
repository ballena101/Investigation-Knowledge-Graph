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

## Controlled test-analysis registration

If no existing IKF analysis document matches MAIRA, run
`notebooks/26_create_maira_bridge_test_analysis.py`. It selects one parsed MAIRA
investigation document with passages and, after explicit confirmation, registers
an idempotent Delta-only IKF bridge-test analysis. It does not copy source data,
create passages, invoke a model or modify Neo4j.

## First executable checkpoint

Run `notebooks/25_validate_maira_passage_bridge.py` with the `analysis_id`
printed by notebook 26, or with another analysis whose documents are present in
both repositories' Delta schemas.

The notebook:

- matches `kg_poc.analysis_document` to `maira.documents` by full SHA-256;
- requires exactly one MAIRA document match for every IKF analysis document;
- exposes MAIRA passages through `maira_ikf_passage_bridge`;
- preserves the MAIRA passage ID, text, hash, page bounds and chunking version;
- recomputes passage hashes and fails closed on integrity errors;
- performs no writes.

The validator accepts normal App IDs (`analysis_<32 hex>`) and explicitly
controlled IDs in the `ikf_maira_test_<three digits>` namespace.

The expected final output with the MAIRA package import available is:

```text
PASS — MAIRA_IKF_PASSAGE_V0.1
```

If the package import is temporarily unavailable, the same data-integrity
checks may run against the versioned compatibility field list, but the notebook
reports `PASS — DATA BRIDGE` and keeps the MAIRA package import as pending.

## Second read-only checkpoint: governed retrieval

Run `notebooks/27_validate_maira_governed_retrieval.py` with the validated
analysis ID and a governed MAIRA query ID, initially `Q001`.

The notebook:

- requires the installed MAIRA passage, governed-term and lexical-retrieval
  modules; there is no IKF compatibility fallback;
- reconstructs and revalidates the SHA-256 document bridge;
- loads the exact persisted query specification and concepts;
- derives terms only from governed `query_spec_concepts`;
- applies MAIRA's reusable lexical retrieval to the bridged passages;
- retains all matching passages only from packages satisfying every populated
  query role;
- calculates a deterministic retrieval snapshot ID from the query specification,
  passage IDs and passage hashes;
- exposes the result as temporary view `maira_ikf_retrieval_snapshot`;
- creates no table, invokes no model and modifies no graph.

Expected final output:

```text
PASS — MAIRA RETRIEVAL CHECKPOINT
```

This checkpoint validates the retrieval hand-off only. The temporary snapshot is
not yet a persisted benchmark result.

## What this checkpoint does not do

It does not replace notebook 15, persist a new table, invoke either LLM, modify
the graph, or classify SHIELD. Those changes follow only after passage parity
and one end-to-end reviewed case are confirmed.

## Third read-only checkpoint: dual-model execution

Run `notebooks/28_compare_maira_snapshot_dual_model.py` after notebook 27 with:

- the same `analysis_id`;
- the exact `retrieval_snapshot_id` printed by notebook 27;
- the approved GPT-OSS 20B and Llama 3.3 70B model-service identifiers.

Notebook 27 now exposes the snapshot both as a notebook-local view and as a
snapshot-specific, cluster-scoped temporary view. The snapshot-specific name
prevents one controlled run from silently reading a different snapshot.

Notebook 28:

- verifies the snapshot identity, passage uniqueness and text hashes;
- resolves the frozen governed question from its exact query specification;
- constructs one canonical prompt and records its SHA-256;
- sends that same prompt independently to both model services;
- handles the GPT-OSS Responses API and Llama Chat Completions API separately;
- validates returned passage IDs and verbatim evidence quotations;
- flags causal/contributory candidates for human review;
- exposes temporary run, candidate and exact-label comparison views;
- creates no table and modifies no Neo4j graph.

The final execution message is:

```text
PASS — MAIRA DUAL-MODEL EXECUTION CHECKPOINT
```

This PASS confirms controlled execution and provenance checks only. It is not a
model-accuracy decision. Exact-label agreement is descriptive and does not
replace semantic human review.

## Following checkpoint

Human-review each candidate as `VALIDATED`, `AMENDED` or `REJECTED`, record
failure types (especially causal overreach and incorrect evidence), and compare
both models on evidence grounding, relationship correctness, completeness,
privacy, stability and review effort. Only then should the document branch of
notebook 15 be replaced. Direct text remains a separate IKF ingress until its
chunking calls the reusable MAIRA component.

## Verified Databricks checkpoint

Date: 2026-09-21

The cross-schema bridge was executed with controlled analysis
`ikf_maira_test_001` using the MAIRA Wight Sky investigation document
(`doc_6f9e9b308bc074427763a014`).

Observed result:

```text
Documents validated: 1
Passages validated: 6
Temporary view: maira_ikf_passage_bridge
PASS — MAIRA_IKF_PASSAGE_V0.1
```

The unqualified `PASS` confirms that Databricks imported the actual MAIRA
contract package; the IKF compatibility fallback was not used. This validates
document matching by SHA-256, passage identity, exact text-hash integrity and
the read-only cross-project contract for this controlled case. It does not yet
validate retrieval quality or LLM interpretation performance.

## Verified governed-retrieval checkpoint

Date: 2026-09-21

Governed query `Q001` was executed for controlled analysis
`ikf_maira_test_001` against the validated Wight Sky passage bridge.

Observed result:

```text
Bridge passages inspected: 6
Passages matching at least one governed role: 6
All-role same-passage candidates: 2
Complete candidate packages: 1
Frozen retrieved passages: 6
Retrieval snapshot ID: snapshot_742f8e0adbccbbf8bf3610015e824415
Temporary view: maira_ikf_retrieval_snapshot
PASS — MAIRA RETRIEVAL CHECKPOINT
```

All six validated passages entered the governed candidate set, two passages
contained terms for every populated query role in the same passage, and one
report package satisfied the complete-package gate. The deterministic snapshot
ID binds the query specification to the selected passage IDs and text hashes.

This validates the governed retrieval hand-off for the controlled case. It does
not validate either model's interpretation accuracy. The snapshot remains a
temporary view and is not yet a persisted benchmark result.
