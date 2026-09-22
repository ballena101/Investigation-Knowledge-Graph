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
- the same governed `query_id`, initially `Q001`;
- the exact `query_spec_id` only if more than one governed specification exists;
- the approved GPT-OSS 20B and Llama 3.3 70B model-service identifiers.

Notebook 27 exposes a notebook-local temporary view. Because serverless compute
does not support global temporary views, notebook 28 uses that local view when
available; otherwise it deterministically reconstructs the governed retrieval
from the source tables and fails unless the computed snapshot ID exactly matches
the requested frozen snapshot.

Notebook 28:

- is compatible with Databricks serverless compute;
- verifies or deterministically reproduces the snapshot identity;
- verifies passage uniqueness and text hashes;
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


## Operational MAIRA-first document routing — 2026-09-22

Notebook 15 now applies the canonical ownership boundary during normal App
document analyses.

For each selected document:

1. resolve the full source SHA-256 against `bdw_analysis_prod.maira.documents`;
2. when there is exactly one MAIRA match, load
   `bdw_analysis_prod.maira.passages`;
3. validate every passage through the installed
   `MAIRA_IKF_PASSAGE_V0.1` executable contract;
4. preserve the MAIRA `passage_id`, exact passage text, text SHA-256, page
   bounds and passage order when materialising the analysis-scoped evidence;
5. record the MAIRA document/package identifiers on the Neo4j SourceDocument;
6. if no MAIRA SHA match exists, temporarily use the existing IKF local
   extraction path;
7. if more than one MAIRA document matches the same SHA, fail closed;
8. if a document already exists in MAIRA but the MAIRA contract package cannot
   be imported, fail rather than create a second passage identity.

The AnalysisGroup records `evidence_source_mode` as one of:

- `MAIRA_CANONICAL`;
- `MAIRA_FIRST_MIXED`;
- `IKF_LOCAL_FALLBACK`;
- `IKF_DIRECT_TEXT`.

The App exposes this value under Technical details. Direct text remains an
IKF-specific ingress at this stage.


## Canonical source-document viewer provenance — 2026-09-22

For a MAIRA-matched App document, notebook 15 now persists the MAIRA
`documents.file_path`, source filename and repository marker on the linked
IKF `SourceDocument` as viewer metadata.

This keeps two identities distinct:

- the IKF analysis/document link used to scope the App analysis;
- the MAIRA canonical source file used to display evidence for MAIRA-owned
  passages.

The viewer therefore opens the same MAIRA source artifact from which the
canonical passages were constructed, rather than relying on an IKF copy.


## MAIRA catalogue exposure in the App

MAIRA canonical evidence is now exposed upstream in the App document selector,
not only consumed after an IKF document has already been selected.

Notebook `33_sync_maira_investigation_catalogue.py` mirrors MAIRA registry
metadata into Neo4j `SourceDocument` catalogue nodes while preserving MAIRA
ownership and source paths. This is metadata synchronisation only; source PDFs
remain in the MAIRA Unity Catalog volume.

The normal App selector therefore supports both MAIRA investigation documents
and IKF input documents. Duplicate files are resolved by SHA-256 in favour of
the MAIRA canonical catalogue entry.
