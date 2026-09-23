# IKF cost-efficient validation strategy

_Last updated: 2026-09-23_

## Purpose

Databricks is a cloud execution environment with direct compute and model-serving cost. IKF therefore treats Databricks as the **integration-proof environment**, not as the routine place to discover software defects or iterate on application logic.

The default engineering rule is:

> **Validate locally and in GitHub first. Use Databricks only for checks that require the Databricks runtime, governed cloud resources or deployed model services.**

This rule applies to new development, regression testing, UI changes, retrieval logic, graph logic, review workflows and release validation.

## 1. Validation hierarchy

IKF uses four validation layers, in this order.

### Layer 1 — static and deterministic local validation

Run without Databricks wherever possible:

- schema and contract validation;
- pure Python transformation logic;
- source-routing rules;
- information-class routing;
- evidence-location parsing;
- passage/citation integrity checks;
- graph node/relationship transformation logic;
- deterministic retrieval logic using fixed fixtures;
- QuestionRun scope enforcement;
- EMCIP shortlist restrictions;
- SHIELD Gate-1 / Gate-2 rules;
- retention-rule calculations;
- privacy/classification pre-screen behaviour;
- provenance and identifier consistency.

Tests should use small synthetic or frozen fixtures and should not call live model endpoints.

### Layer 2 — replay against frozen benchmark artefacts

Existing persisted benchmark/evaluation outputs should be reused before rerunning models.

Examples include:

- frozen MAIRA passages;
- frozen retrieval snapshots;
- persisted model outputs;
- human-adjudicated benchmark labels;
- previously validated graph candidates;
- stored citation/page metadata.

Downstream logic should be tested against these frozen artefacts so that a UI, graph, review or governance change does not unnecessarily trigger model inference.

### Layer 3 — mocked service/integration validation

Where practical, external interfaces should be tested with mocks or contract fixtures for:

- Databricks Jobs status responses;
- Files API responses;
- model-service responses;
- Neo4j reads/writes;
- governed catalogue lookups.

The objective is to catch interface and application errors before cloud execution.

### Layer 4 — Databricks integration proof

Databricks is reserved for behaviour that cannot be established credibly outside the deployed environment, including:

- Unity Catalog permissions and governed data access;
- Files API access under forwarded user authorisation;
- Lakeflow Job wiring and resource bindings;
- deployed model endpoint connectivity and routing;
- live Neo4j connectivity from the Databricks environment;
- deployed Streamlit/App compatibility;
- real source-page PDF rendering from governed volumes;
- one representative end-to-end workflow;
- retention/deletion behaviour that depends on deployed jobs or cloud storage.

## 2. Release-candidate validation instead of continuous redeployment

IKF should not redeploy the Databricks App after every small code or UI change.

Changes should be grouped into a **release candidate** after local tests pass. A cloud validation session should then exercise that candidate as a batch.

Recommended sequence:

1. implement and document changes in GitHub;
2. run local/unit/contract tests;
3. replay frozen benchmark fixtures;
4. resolve failures locally;
5. freeze the release candidate;
6. deploy once to Databricks;
7. run the smallest representative integration test set;
8. record PASS/FAIL and cloud-specific findings;
9. return to local development for corrections where possible;
10. redeploy only when a cloud-dependent correction genuinely requires it.

## 3. Reuse one analysis across multiple validators

A validator notebook number does **not** imply that a fresh analysis or model run must be created.

Where validators are read-only or inspect persisted state, they should reuse the same validated analysis, QuestionRun, retrieval snapshot, graph and review artefacts.

The current validation notebooks should therefore be grouped around shared fixtures wherever possible rather than executed as independent end-to-end workflows.

For example, one fresh Class-B MAIRA analysis can support validation of:

- MAIRA passage identity/provenance;
- structured analysis coverage;
- source-page metadata;
- Findings & Evidence rendering;
- Knowledge Graph coverage;
- relationship-review provenance;
- EMCIP proposal/review governance;
- Similar MAIRA Cases provenance.

A separate QuestionRun may then support multiple Ask/retrieval/citation validators without recreating the underlying analysis.

## 4. LLM cost-control rule

A model must not be rerun merely to test downstream presentation or deterministic logic.

Rerun an LLM only when the behaviour under test depends materially on:

- a changed prompt or output contract;
- a changed model/version/endpoint;
- changed evidence supplied to the model;
- changed retrieval that materially alters the model context;
- changed model-routing logic;
- a benchmark specifically measuring model behaviour.

Changes to UI rendering, review screens, citation presentation, graph layout, deterministic filtering or persistence validation should normally reuse existing model output.

## 5. Local refactoring requirement

To enable cost-efficient validation, stable business logic should progressively move out of the large Streamlit `app/app.py` and Databricks-only notebooks into reusable modules under `src/ikf/`.

Priority candidates include:

- evidence and citation utilities;
- source/catalogue routing;
- QuestionRun scope validation;
- graph transformations and filtering;
- relationship-review rules;
- EMCIP mapping governance;
- SHIELD gate logic;
- retrieval contracts;
- provenance validation;
- retention calculations.

`app/app.py` should increasingly orchestrate these modules rather than implement core rules directly.

## 6. Automated test priority

The current automated-test surface is much smaller than the implemented capability surface. Expanding `tests/` is therefore a priority before broad additional feature development.

The minimum regression suite should cover:

1. classification and source routing;
2. analysis/evidence contracts;
3. citation and page-location integrity;
4. QuestionRun evidence-scope enforcement;
5. retrieval snapshot boundaries;
6. relationship-review governance;
7. EMCIP controlled-shortlist rules;
8. SHIELD two-gate rules;
9. graph transformation/coverage logic;
10. retention and deletion decisions.

## 7. Cost-aware Databricks validation session

A normal release-candidate cloud session should aim to use the minimum set of live operations required to prove integration.

Default target:

- one App deployment;
- one representative Class-B MAIRA analysis;
- reuse that analysis across read-only validators;
- one scoped QuestionRun where Ask integration must be tested;
- no model reruns for presentation-only validation;
- Class-D live execution only when the Class-D route itself is the subject of the milestone;
- reuse indexed SHIELD and REFERENCE_CONTEXT corpora rather than rebuilding them unless their indexing implementation changed.

## 8. Status terminology

Capability status should distinguish:

- **Designed** — architecture/contract documented;
- **Code complete** — implementation committed;
- **Local validated** — deterministic/local regression tests pass;
- **Runtime validated** — required Databricks integration proof passes;
- **Benchmark validated** — model-quality/evaluation criteria pass where applicable;
- **Production ready** — security, operational, retention, monitoring and deployment controls are complete.

`Code complete` must not be treated as equivalent to `Runtime validated`, but `Runtime validated` should not be demanded for logic that can be proven reliably without cloud execution.

## 9. Guiding principle

Cloud execution is a scarce validation resource.

IKF should spend Databricks compute only on evidence that cannot reasonably be obtained locally. This reduces cost while improving engineering quality because deterministic bugs, contract errors and regression failures are caught earlier in a faster and more reproducible environment.
