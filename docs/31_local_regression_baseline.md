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

## Next local extraction priorities

1. QuestionRun scope contract:
   - whole case / one document / selected documents;
   - answer passage IDs must remain inside the chosen scope;
   - reference context must remain separate from source evidence.

2. Relationship-review governance:
   - semantic vs structural relationship distinction;
   - append-only human review;
   - valid review/amendment states.

3. SHIELD two-gate rules:
   - Gate 1 requires human validation of the contributing factor;
   - Gate 2 is a separate human decision on the SHIELD proposal.

4. EMCIP mapping governance:
   - proposal restricted to the governed shortlist or `NO_MAPPING`;
   - human amendment restricted to a governed candidate.

5. Graph filtering/coverage rules:
   - document-scope filtering;
   - supporting structural passthrough nodes;
   - no conversion of chronological `FOLLOWED_BY` into causality.

6. Retention/deletion calculations.

## Migration rule

New modules must first encode existing governed behaviour; refactoring must not silently redefine product policy.

The Streamlit App should adopt the modules incrementally after local regression tests exist. Databricks redeployment is not required merely because a deterministic module/test has been added.
