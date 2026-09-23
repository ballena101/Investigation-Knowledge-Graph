# IKF local regression baseline

_Last updated: 2026-09-23_

## Purpose

This document tracks the migration of deterministic IKF rules out of the large Streamlit application / Databricks-only execution path and into locally testable Python modules.

The objective is to catch routine defects without consuming Databricks compute and to reserve cloud execution for integration proof only.

## Current baseline

### Existing

- `src/ikf/classification_prescreen.py`
  - deterministic Class-D-sensitive record detection;
  - no LLM dependency;
  - corresponding tests in `tests/test_classification_prescreen.py`.

### Added in the local-first consolidation milestone

- `src/ikf/source_routing.py`
  - Class B document ownership -> MAIRA;
  - Classes A/C/D document ownership -> IKF;
  - direct text -> IKF ingress;
  - fail-closed handling for unsupported information classes/input modes;
  - catalogue filtering by governed source owner.

- `tests/test_source_routing.py`
  - regression coverage for all four information classes;
  - catalogue-boundary tests;
  - invalid-route fail-closed tests.

- `src/ikf/evidence_locations.py`
  - parsing/serialisation of `document_id|page_start|page_end`;
  - positive-page and ordered-range validation;
  - duplicate removal;
  - evidence-document scope enforcement.

- `tests/test_evidence_locations.py`
  - page/page-range round-trip tests;
  - malformed-location fail-closed cases;
  - cross-document citation leakage prevention.

- `src/ikf/question_scope.py`
  - deterministic QuestionRun scope resolution for `WHOLE_CASE`, `ONE_DOCUMENT` and `SELECTED_DOCUMENTS`;
  - selected documents must belong to the primary AnalysisGroup;
  - `ONE_DOCUMENT` must resolve to exactly one document;
  - retrieval snapshots cannot contain unknown passages or passages outside the effective document scope;
  - answer `SOURCE_EVIDENCE` passage IDs cannot escape the selected case scope or primary retrieval snapshot;
  - `REFERENCE_CONTEXT` remains a separate governed layer and requires an explicit request and its own retrieval snapshot;
  - source/reference passage IDs cannot be attributed to both layers;
  - combined passage IDs must equal the exact union of the two evidence layers;
  - deterministic no-support results cannot coexist with model-generated answers.

- `tests/test_question_scope.py`
  - whole-case resolution;
  - one-document cardinality enforcement;
  - selected-document AnalysisGroup membership checks;
  - retrieval-snapshot scope leakage detection;
  - unknown-passage rejection;
  - source/reference evidence-layer separation;
  - primary/reference retrieval-snapshot enforcement;
  - combined passage-union contract;
  - deterministic no-support/model-answer mutual exclusion.

- `pytest.ini`
  - local `src` import path and test discovery.

### Cost control

- `sql/02_databricks_cost_audit.sql`
  - read-only `system.billing.usage` + `system.billing.list_prices` audit;
  - cost summary by billing origin/SKU;
  - Lakeflow job/run cost attribution where metadata is available;
  - daily usage trend.

- `docs/30_cost_efficient_validation_strategy.md`
  - cost audit is now a mandatory gate before future IKF cloud validation;
  - cloud sessions must reuse persisted outputs and minimise model reruns;
  - App/continuous resources should be stopped when not required.

## Relationship to Databricks validator 38

The pure-Python QuestionRun scope module now captures the deterministic governance rules that were previously verifiable mainly through `notebooks/38_validate_scoped_ask_run.py`.

Notebook 38 remains valuable as a **cloud integration validator** because it proves that the persisted Neo4j/Delta state obeys those contracts in the deployed environment. It should not be used as the routine place to discover basic scope/provenance bugs.

The intended sequence is therefore:

1. local tests against `src/ikf/question_scope.py`;
2. frozen fixture replay where needed;
3. App/notebook code consumes the same contract;
4. notebook 38 runs only as part of a batched Databricks release-candidate integration proof.

## Next local extraction priorities

1. Relationship-review governance:
   - semantic vs structural relationship distinction;
   - append-only human review;
   - valid review/amendment states.

2. SHIELD two-gate rules:
   - Gate 1 requires human validation of the contributing factor;
   - Gate 2 is a separate human decision on the SHIELD proposal.

3. EMCIP mapping governance:
   - proposal restricted to the governed shortlist or `NO_MAPPING`;
   - human amendment restricted to a governed candidate.

4. Graph filtering/coverage rules:
   - document-scope filtering;
   - supporting structural passthrough nodes;
   - no conversion of chronological `FOLLOWED_BY` into causality.

5. Retention/deletion calculations.

## Migration rule

New modules must first encode existing governed behaviour; refactoring must not silently redefine product policy.

The Streamlit App should adopt the modules incrementally after local regression tests exist. Databricks redeployment is not required merely because a deterministic module/test has been added.
