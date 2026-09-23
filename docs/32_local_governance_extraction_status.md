# IKF local governance extraction and adoption status

_Last updated: 2026-09-23_

## Purpose

This file records the completed local-first governance extraction milestone,
App adoption work and the current release-candidate preparation state. It
complements `docs/25_implementation_status_and_roadmap.md` and
`docs/31_local_regression_baseline.md` without changing the authoritative
product architecture.

## DONE — deterministic governance extraction

The following rules are reusable under `src/ikf/` and covered by repository
tests:

- information-class pre-screen;
- MAIRA/IKF source ownership and catalogue routing;
- evidence-location parsing and document-scope enforcement;
- QuestionRun scope / retrieval-snapshot / citation boundaries;
- relationship-review governance;
- SHIELD Gate-1 / Gate-2 governance;
- EMCIP governed-shortlist proposal and amendment restrictions;
- graph document-scope / structural passthrough / chronology-vs-causality rules;
- Class-D and ordinary transient-content retention calculations.

Cost controls completed:

- read-only Databricks billing audit SQL committed;
- cost audit is mandatory before the next Databricks validation session;
- local/GitHub validation is the default engineering path;
- GitHub Actions executes the deterministic regression suite without Databricks.

No Databricks deployment, Lakeflow Job or model endpoint was invoked for this
milestone.

## DONE — App adoption and deployment-bundle preparation

The repository has an installable `src/ikf` package through `pyproject.toml`.
The package root lazy-loads Databricks/PySpark orchestration functions so the
deterministic governance modules remain locally importable without PySpark.

The shared-policy adoption layer currently replaces duplicated App behaviour
with canonical modules for:

1. content-retention hours;
2. evidence-location parsing;
3. classification-driven MAIRA/IKF catalogue routing;
4. QuestionRun document-scope validation;
5. relationship-review validation;
6. SHIELD Gate-2 validation;
7. EMCIP shortlist-review validation;
8. Knowledge Graph document-scope filtering;
9. legacy Class-D Llama endpoint alias compatibility.

The transformation is tested against the **real `app/app.py` source** and the
resulting Streamlit source must compile. If a governed source anchor drifts, the
transformation fails closed rather than silently retaining an independent
policy implementation.

### Deployable App bundle

`scripts/build_databricks_app_bundle.py` now creates a derived deployment
bundle under `build/databricks_app` by default.

The builder:

- materialises the tested shared-policy transformations **before** Databricks;
- compiles the materialised App source locally;
- includes the canonical `src/ikf` package inside the App bundle;
- writes `.ikf_shared_policy_materialized` so the Databricks bootstrap does not
  repeat the transformation;
- writes `ikf_bundle_manifest.json` with source/materialised SHA-256 hashes,
  adoption version and the exact applied-policy list;
- fails if required App/package components are missing.

Generated `build/` and `dist/` artefacts are excluded from Git.

This resolves the deployment-boundary problem where a Databricks App sourced
only from `app/` could otherwise omit sibling `src/ikf` and silently fall back
to legacy duplicated policy logic.

## LOCAL VALIDATION STATUS

Latest validated GitHub Actions run:

`35915330053`

Result:

**81 deterministic tests passed.**

The successful suite includes:

- editable installation of the IKF package;
- all deterministic governance tests;
- QuestionRun/source/reference-context boundary tests;
- relationship/SHIELD/EMCIP governance tests;
- graph and retention tests;
- transformation of the real `app/app.py`;
- compilation of the materialised real App source;
- construction of the deployable App bundle;
- verification that the bundle contains canonical `src/ikf` code;
- verification of the deployment manifest and policy-adoption list;
- explicit regression protection for the Class-D Llama legacy endpoint alias.

### Defects caught before cloud execution

Local/GitHub validation has already identified and corrected three issues that
would otherwise have risked appearing during paid cloud testing:

1. eager `ikf.__init__` imports incorrectly required PySpark for deterministic
   local tests;
2. the App adoption layer initially referenced the retention helper under the
   wrong API name;
3. App Class-D UI/error paths referenced `CLASS_D_OLLAMA_LLAMA70_URL` even
   though that legacy variable was not defined at startup.

All three were corrected without a Databricks deployment.

## RETENTION NOTE

`notebooks/23_purge_expired_analysis_artifacts.py` does not independently
recalculate the 24-hour / 72-hour policy. It acts on persisted
`content_expires_at` / `derived_expires_at` values and therefore does not create
a competing retention rule. The canonical retention calculation remains under
`src/ikf/retention.py` for new/refactored creation paths.

## NEXT — freeze the local release candidate

At this point deeper physical rewriting of the historical ~359 KB `app.py`
before any integration proof would add change risk without proving additional
Databricks integration behaviour. The preferred next sequence is therefore:

1. keep the current materialised bundle contract green in GitHub CI;
2. perform a final static release-candidate inventory and record the Git commit
   to be tested;
3. do **not** create new model outputs merely for validation;
4. when a Databricks session is eventually approved, run the billing audit
   first;
5. stop unnecessary continuously running resources;
6. deploy the locally generated App bundle once;
7. perform the smallest integration proof using existing persisted artefacts
   wherever possible;
8. return to physical App decomposition after the integration boundary has
   been proven.

This sequencing avoids performing a large UI/source rewrite and then paying to
debug both architecture and deployment packaging simultaneously.

## PENDING BEFORE DATABRICKS

Before the next Databricks session:

- current GitHub CI must remain green;
- the tested release commit must be recorded;
- `sql/02_databricks_cost_audit.sql` must be the first cloud query;
- current App/Job/model-serving cost exposure must be reviewed;
- unnecessary continuously running resources should be stopped;
- the minimum cloud integration test set must be defined in advance;
- existing analyses, QuestionRuns, retrieval snapshots and governed corpora
  should be reused wherever they can prove the required integration behaviour.

## CLOUD RULE

Databricks remains the integration-proof environment. A validator notebook does
not justify a fresh model run by itself. Existing analyses, retrieval snapshots,
model outputs and indexed governed corpora should be reused whenever the test
does not materially depend on rerunning inference.
