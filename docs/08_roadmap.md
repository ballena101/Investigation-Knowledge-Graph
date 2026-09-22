# Roadmap

## Phase 0 — Reference methodology demonstrator

Status: complete / retained as benchmark.

Reference case:

- Commodore Clipper 2010.

Delivered:

- reviewed graph;
- evidence-linked relationships;
- EMCIP mapping layer;
- Neo4j projection;
- relationship-review UI;
- append-only human-review provenance.

Purpose now:

- methodology reference;
- validation benchmark candidate;
- evidence/causality exemplar.

## Phase 1 — Current Class D dual-model PoC

Status: active.

Goal:

Allow an investigator to supply protected/confidential source material and a
question, run one or two privacy-oriented models against identical evidence,
and compare evidence-grounded knowledge graphs.

Implemented in repository:

- document and direct-text inputs;
- encrypted direct-text ingress;
- A/B/C/D information classes;
- GPT-OSS 20B Class D route;
- Llama 3.3 70B Class D route;
- model choice: 20B / 70B / both;
- evidence extraction once;
- independent model-run namespaces;
- side-by-side output rendering;
- privacy-validation stage;
- de-identified output by default;
- 5-question/day Llama limit;
- administrator-only quota reset;
- automated Lakeflow comparison workflow;
- Class D comparison finalizer.

Environment/deployment work still required:

- deploy/register approved open-weight models;
- create/approve dedicated serving endpoints;
- attach `class_d_analysis_job` to the App;
- configure encryption/admin secrets;
- validate networking, logging and retention;
- implement and test automatic Class D source purge within the 24-hour maximum;
- run the first end-to-end Class D comparison.

## Phase 2 — Model validation and review

Goal:

Move from "the pipeline runs" to "model behaviour is measured."

Add/complete:

- generic relationship review for model-run graphs;
- benchmark dataset versioning;
- evidence-grounding metrics;
- relationship precision/recall;
- causal-overreach false-positive metric;
- privacy-leakage metric;
- graph completeness;
- model stability/repeatability;
- side-by-side human preference/acceptance data;
- locked test-set governance.

See:

`docs/18_model_validation_and_feedback.md`

## Phase 3 — Controlled learning loop

Use human-validated graphs as:

1. evaluation ground truth;
2. retrieval knowledge;
3. few-shot examples;
4. versioned feedback examples.

Fine-tuning is optional and later.

Critical rule:

A benchmark case used for training/examples cannot simultaneously serve as an
independent test case for the same model/version.

## Phase 4 — Heterogeneous investigation evidence

Extend source support to:

- interview transcripts;
- witness statements;
- VDR / communications transcripts;
- procedures;
- correspondence;
- technical documentation;
- images/diagrams where an approved multimodal route exists.

## Phase 5 — Corpus and cross-case knowledge

Add:

- graph normalisation across cases;
- cross-case traversal;
- recurring-factor analysis;
- similarity search;
- corroboration / contradiction;
- recommendations/actions chain.

## Phase 6 — Production hardening

Requirements include:

- stronger PII/NER validation;
- access control;
- audit logging;
- retries;
- endpoint/version governance;
- performance and cost testing;
- enforced raw Class D source purge within 24 hours;
- retention/deletion policy for Delta derivatives, model outputs, logs and backups;
- private networking validation;
- review workload metrics;
- production monitoring;
- GitHub-native deployment and retirement of the transitional workspace source.


## Consolidated integration priority — 2026-09-21

The implementation sequence is now governed by
`docs/23_maira_bosuil_integration_plan.md`.

Key correction: IKF must converge on MAIRA for investigation-document passages,
EMCIP controlled vocabulary, governed query specifications, terminology
normalisation, deterministic retrieval and supported deterministic relationship
assessment. IKF must not build parallel substitutes for those capabilities.

Bosuil remains an external design reference only. Its useful ideas are evaluated
as measurable improvements inside the MAIRA→IKF architecture rather than
introduced as a third runtime stack.

Immediate priorities are:

1. finish one clean generic A/B end-to-end App run;
2. migrate the IKF document path to canonical MAIRA passages;
3. generalise relationship and EMCIP review to generated analyses;
4. consume the governed MAIRA EMCIP registry for mapping;
5. add versioned Directive/IMO reference-context retrieval;
6. add Class-D pre-flight fail-closed detection;
7. after human validation of a contributing factor, let the LLM suggest SHIELD classification and require a separate human validation of that SHIELD mapping.

## Capability-based App interface — 2026-09-22

The App now presents five direct user capabilities rather than requiring a
linear traversal of the whole pipeline:

1. News & Alerts;
2. Analyse Documents;
3. Compare LLMs;
4. Review & Validate;
5. Findings & Knowledge.

The knowledge graph remains central underneath and available as an optional
view. The LLM will be embedded contextually in News & Alerts and Findings &
Knowledge. Any LLM-assisted graph correction must remain a proposal until a
human approves it. Functions that are not connected yet are presented only as
disabled, clearly labelled previews.

See `docs/24_simple_capability_ui.md`.
