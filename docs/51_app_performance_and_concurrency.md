# IKF App performance and concurrency plan

## Purpose

This note records the performance work prompted by the observed App slowdown on 26 September 2026 and the expected future use of IKF by approximately 20 authorised users.

The optimisation is deliberately split into two stages so that App-code inefficiency is addressed before increasing Databricks compute cost.

## 1. App execution efficiency — IMPLEMENTED AND REGRESSION-VALIDATED

### Problem

The Streamlit application had grown to ten top-level capabilities rendered through one `st.tabs(...)` construct:

- Home
- News & Alerts
- Audio transcription
- Analyse Documents
- Findings & Evidence
- Timeline
- Knowledge Graph
- Ask LLMs
- Review & Validate
- Terms of reference

Top-level Streamlit tab containers do not provide an execution boundary for the Python blocks placed inside them. As IKF added Neo4j reads, SQL alert retrieval, graph rendering, transcript discovery, analysis-state reads and review functions, an ordinary interaction could therefore cause work belonging to inactive capabilities to execute during the same rerun.

### Implemented change

A final deterministic source transform, `src/ikf/app_lazy_navigation.py`, now replaces only the top-level tab execution model with one active-capability selector.

The capability bodies themselves remain unchanged. The transform converts each top-level container into a conditional execution guard so only the capability selected by the user executes on that rerun.

The optimisation intentionally preserves:

- existing Streamlit widget/session keys;
- Databricks Job triggers;
- model-routing and information-class rules;
- News query logic;
- transcription and audio logic;
- document analysis and evidence logic;
- Findings and Knowledge Graph logic;
- Timeline logic;
- the two inner Ask tabs;
- Review & Validate sections;
- pseudonymisation and reusable pseudonymised derivatives;
- source provenance and human-review governance.

It does not change model prompts, evidence extraction, Knowledge Graph semantics, retention, information classes, or user permissions.

### Classification-guard hardening discovered during validation

Full materialisation testing exposed that the direct-text classification guard was too tightly coupled to the exact document-catalogue source-routing implementation. The guard was hardened without relaxing its policy:

- the information class still has an explicit unselected state;
- no document catalogue is exposed when classification is unselected;
- direct text remains disabled until classification is selected;
- submission remains disabled until classification is selected;
- the backend direct-text constructor still rejects an absent/invalid classification.

The catalogue fail-closed rule is now applied immediately before `available_documents` is exposed through `documents_by_id`, making it independent of MAIRA/IKF catalogue wording and future presentation changes.

### Validation performed

The complete transform chain was validated, not only the new navigation transform.

Regression coverage now checks that:

- all ten top-level capabilities remain reachable;
- Timeline is retained;
- inactive top-level tab guards no longer survive in the materialised App;
- inner Ask tabs remain unchanged;
- the valid two-section materialised Review layout is preserved;
- the valid three-section raw/bootstrap Review layout is preserved;
- the transformed source compiles;
- the Databricks App bundle builds;
- the materialised App passes the undefined-name check;
- current News, Class-D quota, transcription, source-routing and governance contracts remain present.

GitHub Actions run `36230961830` (`IKF local regression`) completed successfully after the final changes. Its deterministic tests, derived App-bundle build and materialised-App undefined-name check all passed.

### Expected performance effect

Inactive capability work should no longer be performed on every Streamlit interaction. This should particularly reduce unnecessary Neo4j/SQL/UI work when a user is working only in one capability.

No numerical speed-up is claimed until the updated App is redeployed and runtime measurements are collected.

### Runtime verification after deployment

After redeployment, compare at minimum:

- initial App load time;
- capability-switch time;
- Analyse Documents interaction time;
- Findings load time;
- Knowledge Graph load time;
- News load/query time;
- Ask submission/status refresh time;
- Streamlit process CPU and memory during ordinary use.

Any regression in source selection, classification, analysis creation, News, transcription, Findings, Timeline, graph, Ask, review or pseudonymisation must be treated as a release blocker.

---

## 2. Databricks configuration for concurrency/performance — PENDING, DO NOT CHANGE YET

The next performance stage is infrastructure configuration. It must be considered only after Step 1 is deployed and measured, so additional Databricks cost is tied to an observed bottleneck.

The configuration review will cover:

1. **Databricks App compute size** — verify whether the current App compute is sufficient and whether a larger size materially improves interactive latency under concurrent use.
2. **Databricks App horizontal scaling / instances** — evaluate multi-instance App serving only if App CPU/memory or request concurrency is the bottleneck.
3. **SQL warehouse configuration** — measure News/query concurrency, queueing and warehouse start/query latency; tune only if SQL is limiting the user experience.
4. **Model Serving concurrency/autoscaling** — measure endpoint latency, queueing/throttling and concurrent requests separately for the model routes allowed by each information class.
5. **Databricks Jobs concurrency and queueing** — ensure multiple investigators can create analyses without one user's long-running job unnecessarily blocking another's independent analysis.
6. **Neo4j connection/query behaviour** — measure query latency and connection-pool use under concurrent sessions before attributing delays to Databricks App compute.
7. **Controlled load test** — test approximately 1, 5, 10 and 20 simultaneous users with representative navigation, analysis-status, News, graph and Ask operations.

Metrics to retain include P50/P90/P99 latency, errors/timeouts, HTTP/model throttling, job queue/start delay, SQL latency/queueing, model latency, Neo4j latency, App CPU/memory and user-visible response time.

The principle is: **optimise execution first, then scale only the component shown by measurement to be the bottleneck.**

## Status

| Work item | Status |
|---|---|
| 1. Lazy top-level capability execution | DONE — code and regression validation complete |
| 1a. Harden explicit-classification fail-closed catalogue handling | DONE — discovered and corrected during full-chain validation |
| 1b. Redeploy updated App and measure actual latency change | PENDING — operational step |
| 2. Databricks sizing/scaling/concurrency configuration | PENDING — deliberately not changed yet |
| 2a. 1/5/10/20-user controlled load test | PENDING — after Step 1 deployment |

