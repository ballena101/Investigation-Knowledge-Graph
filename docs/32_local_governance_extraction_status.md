# IKF local governance extraction and adoption status

_Last updated: 2026-09-23_

## Purpose

This file records the completed local-first governance extraction milestone and
the current adoption work. It complements `docs/25_implementation_status_and_roadmap.md`
and `docs/31_local_regression_baseline.md` without changing the authoritative
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

## DONE — first App adoption slice

The repository now has an installable `src/ikf` package through
`pyproject.toml`.

The App launch path uses `app/bootstrap.py`. During the incremental transition
away from the historical monolithic `app.py`, the bootstrap loads the canonical
`src/ikf` package and applies a strict, fail-closed policy-adoption layer.

The current adoption layer replaces duplicated App policy behaviour with the
shared modules for:

1. content-retention hours;
2. evidence-location parsing;
3. classification-driven MAIRA/IKF catalogue routing;
4. QuestionRun document-scope validation;
5. relationship-review validation;
6. SHIELD Gate-2 validation;
7. EMCIP shortlist-review validation;
8. Knowledge Graph document-scope filtering.

The transformation is tested against the **real `app/app.py` source** and the
resulting Streamlit source must compile. If an expected governed block drifts,
the transformation fails closed rather than silently retaining an independent
policy implementation.

The `ikf` package root was also changed to lazy-load Databricks/PySpark-specific
orchestration functions. Deterministic governance modules can therefore be
imported and tested on an ordinary Python runner without installing PySpark.

## LOCAL VALIDATION STATUS

GitHub Actions run `35914349803` completed successfully on 2026-09-23.

Result:

**77 deterministic tests passed.**

The successful run included:

- editable installation of the IKF package;
- all deterministic governance tests;
- the real-App policy-adoption test;
- compilation of the transformed real `app/app.py` source.

Earlier failed CI runs were useful pre-cloud findings:

- eager `ikf.__init__` imports incorrectly required PySpark for local tests;
- the App adoption layer initially referenced the retention helper under the
  wrong API name.

Both were corrected in GitHub before any Databricks deployment.

## NEXT — physical modularisation

The current bootstrap/adoption layer is intentionally transitional. The next
engineering objective is to make the source tree itself smaller and clearer,
not merely share policy at runtime.

Planned order:

1. move App-facing source/catalogue and evidence-view utilities into reusable
   modules;
2. move QuestionRun creation/scope adapters out of `app.py`;
3. move relationship / EMCIP / SHIELD review adapters out of `app.py`;
4. move Knowledge Graph scope/filter preparation out of `app.py`;
5. replace duplicated retention calculations in cleanup/provisioning notebooks
   where the shared package is available;
6. reduce the transitional source transformer until it is no longer required;
7. keep GitHub CI green after every slice;
8. freeze a release candidate only after local tests pass.

## PENDING BEFORE DATABRICKS

Before the next Databricks session:

- the accumulated refactor must remain green in GitHub CI;
- behaviour parity must be reviewed;
- a release candidate must be frozen in GitHub;
- `sql/02_databricks_cost_audit.sql` must be run first;
- current App/Job/model-serving cost exposure must be reviewed;
- unnecessary continuously running resources should be stopped;
- the minimum cloud integration test set must be defined in advance.

## CLOUD RULE

Databricks remains the integration-proof environment. A validator notebook does
not justify a fresh model run by itself. Existing analyses, retrieval snapshots,
model outputs and indexed governed corpora should be reused whenever the test
does not materially depend on rerunning inference.
