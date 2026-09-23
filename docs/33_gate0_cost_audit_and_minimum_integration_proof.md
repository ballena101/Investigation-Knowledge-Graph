# Gate 0 — Databricks cost audit and minimum integration proof

_Date: 2026-09-23_

## Objective

This runbook defines the first Databricks session after the local-first IKF
refactor. The goal is to understand cost exposure before any new deployment or
model execution and, only if acceptable, perform the smallest integration proof
needed to validate the release candidate.

The frozen local baseline is:

- branch: `release/ikf-local-baseline-2026-09-23`
- validated commit: `967c680ab697d24a78cc618b1a807f2e8a7cf610`
- GitHub Actions run: `35915596757`
- local tests: **81 PASS**
- materialised App bundle: **PASS**
- undefined-name static check: **PASS**

## Gate 0A — cost audit only

Do **not** deploy the App, start a Lakeflow Job, invoke a model endpoint, rebuild
an index, or rerun an analysis before this step is reviewed.

Run:

`sql/02_databricks_cost_audit.sql`

The SQL is read-only and returns three views:

1. workspace usage/cost by billing origin and SKU since 2026-09-01;
2. Lakeflow / Jobs usage by job and job run;
3. daily cost trend by billing origin.

Save or copy the three result tables before taking any action.

### What to inspect

For each material cost line, determine whether it belongs to:

- Databricks Apps;
- Lakeflow / Jobs;
- model serving / Foundation Model API;
- SQL / serverless compute used for development or validation;
- another workspace workload unrelated to IKF.

For IKF-related items, identify whether the resource is:

- required continuously;
- required only during an explicit validation run;
- historical usage that is no longer running;
- unexplained.

### STOP conditions

Stop before deployment if **any** of the following is true:

- a continuously billed IKF resource is running without a current need;
- model-serving cost is occurring while no planned validation requires model
  inference;
- an IKF Job appears to be executing unexpectedly or recurrently;
- a material cost line cannot be attributed to a known resource or activity;
- the daily trend shows continued cost after the development activity that was
  expected to have stopped;
- the cost exposure is higher than the user is comfortable accepting for the
  next validation session.

The correct action under a STOP condition is to identify/stop the unnecessary
resource first and then recheck the audit. Do not compensate by reducing the
number of validation assertions while leaving unexplained resources running.

### GO conditions

Proceed to Gate 0B only when:

- there is no unexplained ongoing IKF cost;
- no unnecessary continuously billed IKF resource remains active;
- any model endpoint that will not be tested can remain unused or be stopped as
  appropriate;
- the expected cost-generating actions for the integration proof are known in
  advance;
- existing persisted results have been identified for reuse.

No fixed currency threshold is imposed by the repository. The decision depends
on actual workspace pricing and the user's acceptable validation budget.

## Gate 0B — read-only persisted-artifact preflight

Before fresh inference, confirm that existing governed artefacts can be reused.
Current known candidates from the completed IKF work include:

- analysis: `analysis_6b330c0e0ce24b6caebb40e041038c55`;
- successful QuestionRun: `question_1af98ef693404bc69d5b24a26eff10fd`;
- MAIRA benchmark: `maira_benchmark_9e059930506d33295105addcd06e821d`.

Use these as **candidates**, not assumptions. Verify their presence read-only in
the live environment before relying on them.

The persisted-artifact preflight should answer:

1. Does the analysis still exist and remain readable?
2. Are its source-document links/provenance present?
3. Is the successful QuestionRun readable without rerunning the Ask Job?
4. Are existing review / graph / SHIELD / EMCIP artefacts sufficient to verify
   the corresponding App pages without new model execution?

If yes, reuse them.

## Gate 1 — build the exact deployment source

Build from the frozen release-candidate branch, not from an arbitrary workspace
copy:

```bash
python scripts/build_databricks_app_bundle.py
```

Expected local output:

`build/databricks_app`

Before upload/deployment, verify the generated bundle contains:

- `app.py`;
- `bootstrap.py`;
- `app.yaml`;
- `requirements.txt`;
- `src/ikf/`;
- `.ikf_shared_policy_materialized`;
- `ikf_bundle_manifest.json`.

The manifest must identify the shared-policy adoption version and contain both
source and materialised App hashes.

## Gate 2 — one App deployment

Deploy the generated bundle **once**.

Do not run model Jobs merely because the App has been redeployed.

Validate in this order:

1. App starts successfully.
2. Required Databricks resource bindings/environment variables resolve.
3. The landing/capabilities UI loads.
4. Existing analyses can be listed/read.
5. Published investigation material resolves through the MAIRA catalogue path.
6. Technical/internal material resolves through the IKF path.
7. Source-document viewer opens an existing source and preserves page
   references.
8. Existing Knowledge Graph content renders and document filtering behaves as
   expected.
9. Existing human-review states render without modification.
10. Existing QuestionRun output renders without rerunning inference.

A failure in steps 1–10 should be investigated before triggering fresh model
execution.

## Gate 3 — fresh execution only if a live path remains unproven

Fresh work is permitted only for a capability that cannot be validated with
persisted artefacts.

### Class B analysis

Run one fresh Class-B analysis only if the new MAIRA source-selection / viewer
path cannot be proven with existing persisted analysis data.

Use one report, not a multi-document batch, unless the defect under test is
specifically multi-document behaviour.

### QuestionRun

Run one new QuestionRun only if the latest Ask Job wiring itself must be
validated. If the App merely needs to display, scope or cite an existing
QuestionRun, reuse the persisted successful run instead.

### SHIELD / EMCIP / relationship correction

Do not generate new proposals solely to validate UI rendering or deterministic
review rules. Reuse persisted proposal/review data where available.

### Class D

Do not invoke Class-D models during this integration proof unless Class-D
runtime routing is the explicit unresolved requirement. Local governance and
endpoint-name compatibility are already covered by the repository regression
suite; cloud model execution is a separate, potentially higher-cost and
higher-governance test.

### Reference corpora

Do not rebuild SHIELD or `REFERENCE_CONTEXT` indexes unless the indexing code or
source corpus has materially changed.

## Gate 4 — immediate post-validation cost check

After the minimum integration proof, rerun `sql/02_databricks_cost_audit.sql`.

Record:

- incremental cost attributable to the validation session;
- App-related usage;
- Job runs executed;
- model/API usage, if any;
- resources stopped after validation;
- any unexpected residual daily cost.

This post-run comparison is required so future validation sessions can be
planned from measured cost rather than assumptions.

## Evidence to retain in GitHub

After the Databricks session, update project documentation with:

- Gate-0 audit date and high-level cost summary;
- which resources were found active and which were stopped;
- exact release-candidate commit/bundle manifest used;
- integration checks PASS/FAIL;
- any fresh Job/model runs performed and why they were necessary;
- post-validation incremental cost;
- defects found and corrective actions;
- next pending step.

Do not commit credentials, tokens, protected source content, or sensitive
workspace configuration values.

## Definition of success

The integration milestone is successful when the locally validated release
candidate is shown to start and consume the existing governed IKF artefacts in
the Databricks runtime, with source routing, source/page provenance, graph and
review views functioning, while fresh inference is limited to only what cannot
be proven from persisted state.
