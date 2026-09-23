# IKF roadmap

_Last updated: 2026-09-23_

## 1. Current direction

IKF is the investigator-facing orchestration, analysis, review and validated-knowledge layer.

MAIRA remains the canonical investigation-evidence layer for published investigation material, passages, provenance, governed terminology and governed retrieval.

The current priority is **baseline consolidation and economical validation**, not broad feature expansion.

The engineering rule is:

> **Validate locally and in GitHub first. Use Databricks only for integration proof that genuinely requires the Databricks runtime, governed cloud resources or deployed model services.**

See `30_cost_efficient_validation_strategy.md`.

## 2. Capability objectives

IKF development is now organised around seven stable objectives.

### O1 — Evidence integrity

Every analytical conclusion must remain traceable to source evidence.

### O2 — Investigator augmentation

AI supports identification, organisation, comparison and questioning of investigation information without replacing investigator judgement.

### O3 — Governed knowledge creation

Machine-generated candidate knowledge must remain distinguishable from human-validated knowledge.

### O4 — Cross-case intelligence

Validated structured knowledge should support similar-case retrieval, comparison and later recurring-pattern analysis.

### O5 — Controlled classification

EMCIP and SHIELD mappings remain governed proposals until the required human decision is recorded.

### O6 — Privacy and confidentiality by design

Processing routes must minimise unnecessary exposure and respect information classification.

### O7 — Measurable quality

The project must evaluate grounding, semantic precision/recall, completeness/coverage, unsupported inference, causal overreach, privacy leakage and model stability rather than only whether an LLM produces plausible output.

## 3. Product capability model

The current investigator-facing architecture is:

1. **Analyse Documents** — question-independent structured analysis and processing status;
2. **Findings & Evidence** — item-level evidence inspection and cited source pages;
3. **Knowledge Graph** — graph exploration and evidence-scoped graph questions;
4. **Ask / Compare LLMs** — scoped questions over processed evidence or governed reference documents;
5. **Review & Validate** — relationship, EMCIP and SHIELD governance;
6. **News & Alerts** — external signals kept separate from validated investigation knowledge.

The Knowledge Graph is a central representation, but it is not the definition of the product.

## 4. Phase history

### Phase 0 — Reference methodology demonstrator

**Status: complete / retained as benchmark.**

Reference case: Commodore Clipper 2010.

Delivered:

- reviewed graph;
- evidence-linked relationships;
- EMCIP mapping layer;
- Neo4j projection;
- relationship-review UI;
- append-only human-review provenance.

Purpose now:

- methodology reference;
- regression/benchmark asset;
- evidence and relationship-governance exemplar.

### Phase 1 — Generic evidence-grounded PoC

**Status: substantially implemented; consolidation/validation active.**

Delivered or code-complete capabilities include:

- document and direct-text ingress;
- A/B/C/D information classes;
- MAIRA-first Class-B document/passages route;
- independent model-run namespaces;
- structured analytical extraction;
- evidence/page provenance;
- explicit QuestionRun workflow;
- scoped Ask / Compare;
- reference-context separation;
- generic relationship review;
- EMCIP governed mapping workflow;
- SHIELD two-gate workflow;
- Knowledge Graph workspace;
- similar MAIRA case retrieval;
- privacy/classification pre-screen;
- Class-D protected-data route and safeguards;
- coverage-preserving graph/relationship improvements.

The remaining work in this phase is not primarily new capability development. It is consolidation, automated regression testing and economical runtime proof.

## 5. Current milestone — IKF baseline consolidation

### M1 — Documentation and architecture consolidation

- keep GitHub as the authoritative project record;
- maintain one current architecture and one current operational status view;
- clearly mark historical/superseded PoC descriptions;
- avoid adding parallel canonical models to MAIRA;
- keep News, REFERENCE_CONTEXT, EMCIP and SHIELD source roles distinct.

### M2 — Local-first refactoring and regression testing

- progressively move stable business rules from `app/app.py` and Databricks-only notebooks into `src/ikf/`;
- expand `tests/` beyond the current classification pre-screen test;
- add deterministic fixtures for passages, citations, QuestionRuns, graphs, reviews, EMCIP proposals and SHIELD decisions;
- test retrieval boundaries, provenance and governance rules without live model calls where possible;
- replay persisted benchmark/model artefacts for downstream regression testing.

### M3 — Release-candidate freeze

A Databricks deployment should occur only after:

- local/unit/contract tests pass;
- frozen benchmark replay passes;
- documentation is updated;
- the release candidate is explicitly frozen for integration validation.

### M4 — Economical Databricks integration proof

Default target for a normal validation session:

- one App deployment;
- one fresh representative Class-B MAIRA analysis;
- reuse that analysis across all applicable read-only validators;
- one scoped QuestionRun when Ask integration needs proof;
- no LLM rerun for presentation-only, graph-layout or deterministic-governance validation;
- reuse existing SHIELD and REFERENCE_CONTEXT indexes unless their indexing implementation changed;
- run Class-D live inference only when Class D itself is the milestone under test.

Databricks is therefore an integration-proof environment, not the routine development/debugging environment.

## 6. Validation status model

All important capabilities should eventually be tracked using the same maturity states:

1. **Designed**
2. **Code complete**
3. **Local validated**
4. **Runtime validated**
5. **Benchmark validated** — where model behaviour is relevant
6. **Production ready**

This prevents `code complete` from being confused with deployed proof while also avoiding unnecessary cloud execution for deterministic logic that can be validated locally.

## 7. Model-quality and benchmark work

The next evaluation framework should generalise the existing controlled benchmark methodology.

Required measures include:

- semantic relationship precision and recall;
- evidence grounding;
- graph/extraction completeness and coverage;
- unsupported-inference rate;
- causal-overreach rate;
- human amendment/rejection/acceptance rates;
- model repeatability/stability;
- privacy leakage;
- citation/provenance correctness.

Frozen evidence, retrieval snapshots and adjudicated gold should be reused wherever possible rather than regenerating model outputs.

## 8. Controlled learning loop

After the baseline is stable, human-validated material may be used progressively as:

1. evaluation ground truth;
2. retrieval knowledge;
3. few-shot examples;
4. versioned feedback examples.

Fine-tuning is optional and later.

A benchmark case used for training/examples cannot simultaneously remain an independent test case for the same model/version.

## 9. Future functional expansion

### Heterogeneous investigation evidence

Extend operational support beyond published PDF reports to evidence such as:

- interview transcripts;
- witness statements;
- VDR / communications transcripts;
- procedures and manuals;
- correspondence;
- technical documentation;
- images/diagrams where an approved multimodal route exists.

### Cross-case knowledge

Move beyond individual similar-case retrieval toward:

- normalised cross-case graph traversal;
- recurring-factor analysis;
- recurring safety-issue patterns;
- corroboration / contradiction;
- recommendation/action chains;
- pattern discovery over human-validated knowledge.

### News & Alerts

Complete the external-signals capability without mixing unvalidated alerts with validated investigation knowledge.

News should remain a separate source class/workspace and may link to cases or vessels only with explicit provenance and status labels.

## 10. Production hardening

Production-readiness work includes:

- access-control verification;
- audit logging;
- endpoint/version governance;
- stronger PII/NER validation;
- Class-D networking/security approval;
- retention/deletion verification;
- monitoring and operational alerts;
- retry/failure handling;
- performance and cost monitoring;
- deployment/rollback procedure;
- GitHub-native deployment discipline;
- review-workload metrics.

## 11. Immediate work order

Until the baseline milestone is complete, the recommended order is:

1. consolidate current architecture/documentation;
2. increase local modularisation and automated tests;
3. reuse frozen benchmark outputs to validate downstream behaviour;
4. freeze one release candidate;
5. perform one economical Databricks integration session;
6. record capability maturity from that session;
7. fix failures locally wherever possible;
8. only then resume major capability expansion.

## 12. Cost-control principle

A notebook number or validator does not imply a separate Databricks run.

Read-only validators should reuse persisted analyses, QuestionRuns, retrieval snapshots, graphs and review artefacts. A live model call should occur only when the behaviour under test materially depends on the model, prompt, model context, retrieval result or endpoint itself.

See `30_cost_efficient_validation_strategy.md` for the authoritative validation policy.
