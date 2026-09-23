# IKF implementation status and roadmap

_Last updated: 2026-09-23_

This is the operational implementation tracker for the current IKF Proof of Concept. Historical implementation detail remains in the numbered design and validation documents; this file records the current truth, immediate next step and remaining work.

## 1. Current operating principle

IKF is the orchestration, interaction, review and validated-knowledge layer.

MAIRA is the canonical published-investigation evidence layer for documents, passages, provenance, governed terminology and governed retrieval.

The App keeps four roles distinct:

- source evidence;
- reference context;
- controlled taxonomies/vocabularies;
- human-validated knowledge.

AI output remains candidate knowledge until the relevant human-validation workflow records a decision.

Engineering rule: **Databricks is the integration-proof environment, not the routine development/debugging environment.** Local/GitHub checks must be exhausted before cloud execution.

## 2. DONE — current local release candidate

### Product/App architecture

The current App separation is implemented for:

1. Analyse Documents;
2. Ask / Compare LLMs;
3. Findings & Evidence;
4. Knowledge Graph;
5. Review & Validate;
6. News & Alerts kept separate from validated investigation knowledge.

The shared Active analysis model and question-independent analysis workflow remain the intended operating model.

### Evidence and provenance

- MAIRA-first passage reuse by full SHA-256 for published investigation material.
- MAIRA passage identity, exact text/hash, page bounds and order preserved.
- Direct text remains an IKF-specific ingress.
- Evidence locations use `document_id|page_start|page_end`.
- Source viewer supports IKF and MAIRA source roots.
- Class-B catalogue routing is MAIRA-only; A/C/D document routing is IKF-only.
- QuestionRun scope, retrieval snapshot and citation boundaries are encoded in reusable deterministic policy.

### Governance

Reusable `src/ikf` modules and local regression tests now cover:

- information-class pre-screen;
- source routing;
- evidence-location parsing;
- QuestionRun scope/provenance;
- relationship-review governance;
- chronology-versus-causality semantics;
- SHIELD two-gate governance;
- EMCIP governed-shortlist restrictions;
- graph document-scope/structural passthrough rules;
- transient-content retention calculations.

### App adoption and packaging

- Repository is an installable Python package.
- The historical monolithic App is incrementally bound to canonical `src/ikf` policy through a strict fail-closed adoption layer.
- A deterministic bundle builder creates the exact Databricks App source under `build/databricks_app`.
- The bundle includes canonical `src/ikf`, a materialisation marker and a manifest with source/materialised hashes and policy-adoption metadata.
- CI compiles/checks the materialised App and performs undefined-name analysis.

### Cost-control / pre-cloud safeguards

- `sql/02_databricks_cost_audit.sql` is the mandatory Gate-0 cost audit.
- Static tests ensure the cost audit remains SELECT-only.
- `notebooks/60_validate_persisted_release_candidate_read_paths.py` is the cheapest first live read-path check and is guarded against Job triggers, model calls, writes and `%pip install`.
- `notebooks/55_validate_consolidated_release_preflight.py` now checks the complete current App `valueFrom` resource contract.
- A regression test compares the notebook-55 required-resource set directly with `app/app.yaml`.
- CI watches notebook 55, notebook 60 and the Gate-0 SQL.

### Current local validation baseline

Frozen branch:

`release/ikf-local-baseline-2026-09-23`

Validated code commit:

`f8aea8c2e59f98634222bd9e11d99d2b421e5224`

GitHub Actions run:

`35923614601`

Status:

- **87 deterministic tests PASS**;
- materialised App bundle build **PASS**;
- undefined-name check **PASS**;
- App environment/resource contract **PASS**;
- `app.yaml` ↔ notebook-55 resource parity **PASS**;
- notebook-60 no-inference/no-write guard **PASS**;
- cost-audit SELECT-only guard **PASS**.

No Databricks App, Job or model endpoint was invoked to reach this baseline.

## 3. Historical runtime evidence already available

Earlier Databricks work established useful runtime evidence, including:

- MAIRA/IKF passage bridge and governed retrieval snapshots;
- dual-model benchmark persistence and canonical-gold review;
- successful persisted QuestionRun `question_1af98ef693404bc69d5b24a26eff10fd` for analysis `analysis_6b330c0e0ce24b6caebb40e041038c55`;
- persisted MAIRA benchmark `maira_benchmark_9e059930506d33295105addcd06e821d`;
- prior consolidated preflight/runtime checks and corpus-indexing work.

These are reusable evidence assets. They do **not** by themselves make the new local release candidate runtime-validated after the latest refactor.

## 4. NEXT — exact execution order

### Gate 0A — cost audit

First live action:

`sql/02_databricks_cost_audit.sql`

Do not deploy the App or trigger a model/Job before reviewing the six billing views.

Decision rule:

- **STOP** if there is unexplained ongoing IKF cost, an unnecessary continuously running resource, unexpected recurrent Job activity or model-serving cost without a planned need.
- **GO** only when current cost exposure is understood and unnecessary resources are stopped.

### Gate 0B — cheapest persisted read-path proof

If Gate 0A is GO, run:

`notebooks/60_validate_persisted_release_candidate_read_paths.py`

This reuses persisted analysis/benchmark/MAIRA state and performs no inference or write.

### Gate 0C — broader prerequisite preflight only if needed

Run:

`notebooks/55_validate_consolidated_release_preflight.py`

only when broader App-resource, table, source-root, scope or Neo4j prerequisite checking is required.

### Gate 1 — build exact deployment source

Build from the frozen release branch:

```bash
python scripts/build_databricks_app_bundle.py
```

Deploy the generated `build/databricks_app` bundle, not the historical raw `app/` directory.

### Gate 2 — one App deployment and persisted-state validation

Validate, in order:

1. App startup;
2. resource/environment resolution;
3. landing/navigation;
4. existing analysis listing/read;
5. MAIRA Class-B routing;
6. IKF A/C/D routing;
7. source/page viewer on existing evidence;
8. existing Knowledge Graph rendering/filtering;
9. existing review states;
10. existing QuestionRun rendering/citations.

A failure here is investigated before fresh inference.

### Gate 3 — fresh execution only when strictly necessary

- one fresh Class-B analysis only if persisted artefacts cannot prove the changed source/viewer path;
- one new QuestionRun only if Ask Job wiring itself remains unproven;
- no SHIELD/EMCIP/relationship-correction regeneration for deterministic UI validation;
- no Class-D model execution unless Class-D runtime is the explicit unresolved test;
- no SHIELD or REFERENCE_CONTEXT rebuild unless indexing code/source corpus changed materially.

### Gate 4 — post-validation cost audit

Rerun `sql/02_databricks_cost_audit.sql` immediately after the minimal integration proof and record incremental cost/resource activity.

## 5. PENDING

### P1 — current release candidate runtime validation

- Gate-0 billing audit: **PENDING**;
- notebook-60 persisted read-path proof: **PENDING**;
- broader notebook-55 preflight: **CONDITIONAL / PENDING**;
- generated App bundle live deployment: **PENDING**;
- Files API/page viewer under deployed user token: **PENDING**;
- latest resource-binding validation in live App: **PENDING**;
- persisted QuestionRun/graph/review rendering on latest build: **PENDING**;
- post-validation measured incremental cost: **PENDING**.

### P2 — production/governance hardening

- final Class-D endpoint/security approval and explicit runtime validation;
- access-control/PII/retention/audit hardening;
- monitoring and operational alerting;
- rollback/deployment runbook refinement;
- remove transitional App source-transform layer as physical modularisation progresses;
- retire IKF local-parser fallback once MAIRA coverage is sufficient.

### P3 — capability expansion

- News & Alerts integration as separate external/unvalidated signal capability;
- heterogeneous evidence ingestion beyond PDFs/documents;
- richer cross-case validated-knowledge analysis;
- controlled human-feedback/evaluation loop without conflating validation with automatic model training.

## 6. Definition of completion for the current milestone

The current release-candidate milestone is complete when:

1. Gate-0 costs are understood and unnecessary resources are stopped;
2. persisted read paths pass;
3. the generated bundle deploys once successfully;
4. existing governed artefacts render with correct source/page provenance, graph scope and review state;
5. any truly necessary fresh inference is minimal and documented;
6. post-validation incremental cost is measured;
7. PASS/FAIL evidence and remaining defects are recorded in GitHub.

Until those conditions are met, the current state is **locally validated / cloud integration pending**, not production ready.
