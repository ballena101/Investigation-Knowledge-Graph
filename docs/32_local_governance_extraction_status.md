# IKF local governance extraction status

_Last updated: 2026-09-23_

## Purpose

This file records the completed local-first governance extraction milestone and
its immediate follow-up work. It complements `docs/25_implementation_status_and_roadmap.md`
and `docs/31_local_regression_baseline.md` without changing the authoritative
product architecture.

## DONE

The following deterministic rules are now reusable under `src/ikf/` and covered
by repository tests:

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
- a GitHub Actions pytest workflow exists for deterministic regression testing.

No Databricks deployment, Lakeflow Job or model endpoint was invoked for this
milestone.

## VALIDATION STATUS

The test suite is committed, but a full-suite PASS is not yet claimed. The
assistant execution environment could not clone GitHub because outbound DNS is
blocked, and connector-authored commits did not automatically trigger the
GitHub Actions workflow.

This is a local/GitHub execution issue, not a reason to run Databricks. The
suite should be executed on the next normal local checkout/push or eligible pull
request before any cloud release candidate is created.

## NEXT

The next engineering milestone is **incremental adoption of the tested modules**
inside existing App/notebook code, without changing user-facing policy:

1. replace duplicated source-routing and evidence-location helpers in `app.py`;
2. adopt `question_scope` in Ask/Compare and Knowledge Graph questions;
3. adopt `review_governance` in Review & Validate;
4. adopt SHIELD and EMCIP governance helpers in their respective review paths;
5. adopt graph-governance helpers in Knowledge Graph filtering;
6. adopt retention calculations in cleanup/provisioning logic where compatible;
7. run the complete local regression suite;
8. freeze a release candidate only after local tests pass.

## PENDING BEFORE DATABRICKS

Before the next Databricks session:

- local deterministic regression suite must pass;
- accumulated refactor must be reviewed for behaviour parity;
- release candidate must be frozen in GitHub;
- `sql/02_databricks_cost_audit.sql` must be run first;
- current App/Job/model-serving cost exposure must be reviewed;
- unnecessary continuously running resources should be stopped;
- the minimum cloud integration test set must be defined in advance.

## CLOUD RULE

Databricks remains the integration-proof environment. A validator notebook does
not justify a fresh model run by itself. Existing analyses, retrieval snapshots,
model outputs and indexed governed corpora should be reused whenever the test
does not materially depend on rerunning inference.
