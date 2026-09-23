# IKF local regression baseline

_Last updated: 2026-09-23_

## Purpose

This document tracks the migration of deterministic IKF rules out of the large
Streamlit application / Databricks-only execution path and into locally testable
Python modules.

The objective is to catch routine defects without consuming Databricks compute
and to reserve cloud execution for integration proof only.

## Current baseline

### Classification and source routing

- `src/ikf/classification_prescreen.py`
  - deterministic Class-D-sensitive record detection;
  - no LLM dependency.
- `tests/test_classification_prescreen.py`.

- `src/ikf/source_routing.py`
  - Class B document ownership -> MAIRA;
  - Classes A/C/D document ownership -> IKF;
  - direct text -> IKF ingress;
  - fail-closed handling for unsupported information classes/input modes;
  - catalogue filtering by governed source owner.
- `tests/test_source_routing.py`.

### Evidence provenance

- `src/ikf/evidence_locations.py`
  - parsing/serialisation of `document_id|page_start|page_end`;
  - positive-page and ordered-range validation;
  - duplicate removal;
  - evidence-document scope enforcement.
- `tests/test_evidence_locations.py`.

### QuestionRun scope and retrieval boundaries

- `src/ikf/question_scope.py`
  - `WHOLE_CASE`, `ONE_DOCUMENT` and `SELECTED_DOCUMENTS` scope resolution;
  - selected documents must belong to the primary AnalysisGroup;
  - `ONE_DOCUMENT` must resolve to exactly one document;
  - primary retrieval snapshots cannot escape the effective document scope;
  - answer SOURCE_EVIDENCE IDs cannot escape the selected scope or retrieval snapshot;
  - REFERENCE_CONTEXT remains separate and requires explicit request plus its own retrieval snapshot;
  - source/reference passage IDs cannot be attributed to both layers;
  - combined passage IDs must equal the exact union of both evidence layers;
  - deterministic no-support results cannot coexist with model-generated answers.
- `tests/test_question_scope.py`.

### Relationship-review governance

- `src/ikf/review_governance.py`
  - distinguishes semantic relationships from graph plumbing;
  - excludes structural relationships such as `INVOLVED_IN` from semantic human review;
  - enforces VALIDATED / REJECTED / AMENDED human decisions and matching HUMAN_* statuses;
  - amendments must resolve to a semantic relationship;
  - effective relationship is derived without overwriting the original edge;
  - supports append-only latest-review interpretation.
- `tests/test_review_governance.py`.

### SHIELD two-gate governance

- `src/ikf/shield_governance.py`
  - Gate 1 passes only when the latest human relationship review confirms `CONTRIBUTED_TO`;
  - VALIDATED original `CONTRIBUTED_TO` and AMENDED-to-`CONTRIBUTED_TO` are eligible;
  - proposals become stale when their Gate-1 review is no longer current;
  - proposal evidence must remain inside the deterministic SHIELD retrieval set;
  - `NO_GROUNDED_PROPOSAL` cannot contain a classification value;
  - Gate 2 enforces independent human VALIDATED / REJECTED / AMENDED decisions;
  - only HUMAN_VALIDATED or HUMAN_AMENDED can yield an authoritative SHIELD label.
- `tests/test_shield_governance.py`.

### EMCIP mapping governance

- `src/ikf/emcip_governance.py`
  - assistant selection must be a governed shortlist candidate or `NO_MAPPING`;
  - assistant output cannot invent a taxonomy candidate;
  - human VALIDATED / REJECTED / AMENDED statuses are enforced;
  - an amendment must select another candidate from the original governed shortlist;
  - free-form/out-of-shortlist amendments fail closed.
- `tests/test_emcip_governance.py`.

### Graph scope and coverage invariants

- `src/ikf/graph_governance.py`
  - explicitly classifies `FOLLOWED_BY` as chronology, not causality;
  - separates chronology, causal/contributory, structural and other semantic relationships;
  - document-scoped graph selection starts from evidence-backed nodes;
  - structural passthrough is limited to one hop from the original evidence-backed nodes;
  - structural passthrough cannot recursively pull unrelated semantic content into scope;
  - displayed edges require both endpoints to be retained.
- `tests/test_graph_governance.py`.

### Retention calculations

- `src/ikf/retention.py`
  - Class D transient/derived content: 24 hours;
  - Classes A/B/C transient/derived content: 72 hours;
  - MAIRA, SHIELD and REFERENCE_CONTEXT governed source resources are exempt from IKF transient source expiry;
  - direct-text raw payload is marked for purge after successful extraction;
  - unsupported information classes fail closed.
- `tests/test_retention.py`.

### Local test infrastructure

- `pytest.ini`
  - local `src` import path and test discovery.
- `.github/workflows/local-regression.yml`
  - zero-Databricks pytest workflow for changes under `src/ikf/`, `tests/` or test configuration;
  - intentionally contains no Databricks credentials, model calls or cloud-runtime dependency.

## Cost control

- `sql/02_databricks_cost_audit.sql`
  - read-only `system.billing.usage` + `system.billing.list_prices` audit;
  - cost summary by billing origin/SKU;
  - Lakeflow job/run cost attribution where metadata is available;
  - daily usage trend.

- `docs/30_cost_efficient_validation_strategy.md`
  - cost audit is a mandatory Gate 0 before future IKF cloud validation;
  - cloud sessions must reuse persisted outputs and minimise model reruns;
  - App/continuous resources should be stopped when not required.

## Relationship to Databricks validators

The local modules now capture deterministic governance previously verifiable
mainly through deployed notebooks such as 38, 42, 48, 51 and related graph /
retention validators.

Those notebooks remain useful as **cloud integration validators**: they prove
that the persisted Neo4j/Delta state and deployed Jobs obey the already-tested
contracts. They should not be the routine place where deterministic bugs are
discovered.

The intended sequence is:

1. local pytest / GitHub regression checks;
2. frozen fixture replay where appropriate;
3. App/notebook code consumes the reusable module contracts;
4. cost audit Gate 0;
5. one batched Databricks release-candidate integration proof.

## Validation note

The repository now contains the local regression suite and GitHub Actions
workflow. The current assistant execution environment could not clone GitHub
directly because outbound DNS access is blocked, and connector-authored commits
did not automatically produce a workflow run. Therefore no claim of an
executed full-suite PASS is made here yet.

This does **not** require Databricks. The next ordinary local checkout/push or
eligible pull request should run the workflow; any failure should be corrected
locally before a Databricks release candidate is created.

## Next engineering step — adoption, not new policy

The deterministic baseline is now broad enough to begin reducing duplication in
`app/app.py` and Databricks notebooks.

Adoption order:

1. use `source_routing` and `evidence_locations` from the App;
2. use `question_scope` from Ask/Compare and graph-scoped questions;
3. use `review_governance` in Review & Validate;
4. use `shield_governance` and `emcip_governance` in their review surfaces;
5. use `graph_governance` in the Knowledge Graph workspace;
6. use `retention` from cleanup/provisioning logic where practical.

This adoption should be incremental. A refactor must preserve behaviour and
must not trigger a Databricks deployment merely to prove deterministic code.

## Migration rule

New modules encode existing governed behaviour; refactoring must not silently
redefine product policy.

GitHub remains the authoritative code/documentation source. Databricks remains
the integration-proof environment, not the routine development environment.
