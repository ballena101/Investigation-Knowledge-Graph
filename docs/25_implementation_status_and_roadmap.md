# IKF implementation status and roadmap

_Last updated: 2026-09-26_

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

Performance rule: **optimise App execution before increasing Databricks compute.** The current performance work is split into (1) App execution efficiency and (2) later measured Databricks sizing/scaling/concurrency configuration. Detailed status is in `docs/51_app_performance_and_concurrency.md`.

## 2. DONE — current local release candidate

### Product/App architecture

The current App separation is implemented for:

1. Home;
2. News & Alerts;
3. Audio transcription;
4. Analyse Documents;
5. Findings & Evidence;
6. Timeline;
7. Knowledge Graph;
8. Ask LLMs;
9. Review & Validate;
10. Terms of reference.

The shared Active analysis model and question-independent analysis workflow remain the intended operating model.

Top-level capability execution is now lazy: only the selected capability body executes on a Streamlit rerun. Inner Ask tabs remain unchanged. This is intended to reduce unnecessary Neo4j, SQL, graph/UI and transcript-discovery work while preserving the existing capability logic and governance controls.

### Evidence and provenance

- MAIRA-first passage reuse by full SHA-256 for published investigation material.
- MAIRA passage identity, exact text/hash, page bounds and order preserved.
- Direct text remains an IKF-specific ingress and requires explicit information classification before processing.
- Evidence locations use `document_id|page_start|page_end`.
- Source viewer supports IKF and MAIRA source roots.
- Class-B catalogue routing is MAIRA-only; A/C/D document routing is IKF-only.
- QuestionRun scope, retrieval snapshot and citation boundaries are encoded in reusable deterministic policy.

### Governance

Reusable `src/ikf` modules and local regression tests now cover:

- information-class pre-screen;
- explicit direct-text classification fail-closed handling;
- source routing;
- evidence-location parsing;
- QuestionRun scope/provenance;
- relationship-review governance;
- chronology-versus-causality semantics;
- SHIELD two-gate governance;
- EMCIP governed-shortlist restrictions;
- graph document-scope/structural passthrough rules;
- transient-content retention calculations;
- source-agnostic pseudonymisation and governed reusable derivatives;
- top-level lazy capability execution.

### App adoption and packaging

- Repository is an installable Python package.
- The historical monolithic App is incrementally bound to canonical `src/ikf` policy through a strict fail-closed adoption layer.
- A deterministic bundle builder creates the exact Databricks App source under `build/databricks_app`.
- The bundle includes canonical `src/ikf`, a materialisation marker and a manifest with source/materialised hashes and policy-adoption metadata.
- CI compiles/checks the materialised App and performs undefined-name analysis.
- Bundle contract is currently `IKF_DATABRICKS_APP_BUNDLE_V0.16`.

### Cost-control / pre-cloud safeguards

- `sql/02_databricks_cost_audit.sql` is the mandatory Gate-0 cost audit.
- Static tests ensure the cost audit remains SELECT-only.
- `notebooks/60_validate_persisted_release_candidate_read_paths.py` is the cheapest first live read-path check and is guarded against Job triggers, model calls, writes and `%pip install`.
- `notebooks/55_validate_consolidated_release_preflight.py` now checks the complete current App `valueFrom` resource contract.
- A regression test compares the notebook-55 required-resource set directly with `app/app.yaml`.
- CI watches notebook 55, notebook 60 and the Gate-0 SQL.

### Current local validation baseline

Latest performance/refactor validation:

GitHub Actions run:

`36230961830`

Status:

- deterministic regression tests **PASS**;
- materialised App bundle build **PASS**;
- undefined-name check **PASS**;
- lazy-navigation regression contract **PASS**;
- Timeline preservation **PASS**;
- inner Ask tabs preservation **PASS**;
- valid Review layout preservation **PASS**;
- explicit-classification fail-closed handling **PASS**.

The performance change has therefore passed local/GitHub integration checks. It has **not yet been runtime-benchmarked after deployment**, so no numerical speed-up or 20-user capacity claim is made yet.

Historical frozen baseline remains:

`release/ikf-local-baseline-2026-09-23`

Validated code commit:

`f8aea8c2e59f98634222bd9e11d99d2b421e5224`

Historical GitHub Actions run:

`35923614601`

No Databricks App, Job or model endpoint was invoked to establish the historical baseline.

## 3. Historical runtime evidence already available

Earlier Databricks work established useful runtime evidence, including:

- MAIRA/IKF passage bridge and governed retrieval snapshots;
- dual-model benchmark persistence and canonical-gold review;
- successful persisted QuestionRun `question_1af98ef693404bc69d5b24a26eff10fd` for analysis `analysis_6b330c0e0ce24b6caebb40e041038c55`;
- persisted MAIRA benchmark `maira_benchmark_9e059930506d33295105addcd06e821d`;
- prior consolidated preflight/runtime checks and corpus-indexing work.

These are reusable evidence assets. They do **not** by themselves make the new local release candidate runtime-validated after the latest refactor.

## 4. NEXT — exact execution order

### Performance Step 1B — deploy and measure the lazy-capability build

Before changing Databricks compute configuration, deploy the generated bundle and verify the performance refactor against persisted state.

Validate, in order:

1. App startup and Home;
2. switch through all ten top-level capabilities;
3. News & Alerts only queries/renders when selected;
4. Audio transcription state remains available;
5. Analyse Documents classification, source selection, direct text and pseudonymisation behave as before;
6. Findings & Evidence loads existing results;
7. Timeline renders existing chronology;
8. Knowledge Graph renders existing graph/review state;
9. both inner Ask modes remain available;
10. Review & Validate remains complete;
11. Terms of reference renders normally.

Measure at minimum initial load, capability-switch time, Analyse interaction time, Findings/Graph/News load time, Ask refresh time and App CPU/memory. A functional regression is a release blocker.

### Gate 0A — cost audit

First live action for any fresh cloud/inference work remains:

`sql/02_databricks_cost_audit.sql`

Do not trigger fresh model/Job work before reviewing the billing views.

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

Build from the current main/release candidate:

```bash
python scripts/build_databricks_app_bundle.py
```

Deploy the generated `build/databricks_app` bundle, not the historical raw `app/` directory.

### Gate 2 — persisted-state validation

Validate existing state before fresh inference:

1. resource/environment resolution;
2. existing analysis listing/read;
3. MAIRA Class-B routing;
4. IKF A/C/D routing;
5. source/page viewer on existing evidence;
6. existing Knowledge Graph rendering/filtering;
7. existing review states;
8. existing QuestionRun rendering/citations.

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

- deploy lazy-capability bundle and confirm all ten capabilities: **PENDING**;
- measure before/after interactive latency and App CPU/memory: **PENDING**;
- Gate-0 billing audit: **PENDING**;
- notebook-60 persisted read-path proof: **PENDING**;
- broader notebook-55 preflight: **CONDITIONAL / PENDING**;
- Files API/page viewer under deployed user token: **PENDING**;
- latest resource-binding validation in live App: **PENDING**;
- persisted QuestionRun/graph/review rendering on latest build: **PENDING**;
- post-validation measured incremental cost: **PENDING**.

### P2 — Databricks performance/concurrency configuration

**This is Performance Step 2 and is intentionally deferred until Step 1 is deployed and measured.**

Review only after runtime measurements identify the limiting component:

- Databricks App compute size;
- App horizontal scaling / instance count;
- SQL warehouse sizing/concurrency for News and related queries;
- Model Serving concurrency/autoscaling and throttling;
- Databricks Jobs concurrency/queueing for independent analyses;
- Neo4j connection/query latency under concurrent sessions;
- controlled 1/5/10/20-user load test;
- P50/P90/P99 latency, queueing, timeout/error rates, CPU/memory and user-visible response time.

Do not increase infrastructure merely because the App previously felt slow; scale the component demonstrated by measurement to be the bottleneck.

### P3 — production/governance hardening

- final Class-D endpoint/security approval and explicit runtime validation;
- access-control/PII/retention/audit hardening;
- monitoring and operational alerting;
- rollback/deployment runbook refinement;
- remove transitional App source-transform layer as physical modularisation progresses;
- retire IKF local-parser fallback once MAIRA coverage is sufficient.

### P4 — validation and capability expansion

- Bosuil-informed Event/ContributingFactor category coverage pass after coverage diagnostics;
- global consolidation refinement while preserving provenance;
- validation dashboard for Event/ContributingFactor precision, recall and F1;
- causal-overreach, evidence-support and consolidation-retention metrics;
- hybrid retrieval benchmark before changing retrieval defaults;
- richer cross-case validated-knowledge analysis;
- controlled human-feedback/evaluation loop without conflating validation with automatic model training.

## 6. Definition of completion for the current milestone

The current release-candidate milestone is complete when:

1. the lazy-capability bundle deploys and all ten capabilities pass runtime smoke validation;
2. its actual latency/resource effect is measured;
3. Gate-0 costs are understood and unnecessary resources are stopped;
4. persisted read paths pass;
5. existing governed artefacts render with correct source/page provenance, graph scope and review state;
6. any truly necessary fresh inference is minimal and documented;
7. post-validation incremental cost is measured;
8. PASS/FAIL evidence and remaining defects are recorded in GitHub.

Until those conditions are met, the current state is **locally validated / cloud integration pending**, not production ready.
