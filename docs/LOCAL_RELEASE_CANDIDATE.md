# IKF local release candidate

_Date: 2026-09-23_

## Purpose

This record freezes the locally validated IKF baseline that should be used for
the next cost-controlled Databricks integration proof.

## Validation baseline

Final locally validated release-candidate state:

- GitHub Actions run: `35915596757`
- validated code commit: `967c680ab697d24a78cc618b1a807f2e8a7cf610`
- frozen branch: `release/ikf-local-baseline-2026-09-23`
- result: **81 deterministic tests passed**
- materialised App bundle build: **PASS**
- static undefined-name check on materialised App: **PASS**

The tested baseline includes:

- reusable deterministic governance modules under `src/ikf`;
- strict App adoption against the real `app/app.py` source;
- locally materialised Databricks App bundle generation;
- App bundle manifest/hash contract;
- source-routing, evidence-location and QuestionRun boundaries;
- relationship, SHIELD and EMCIP governance;
- graph document-scope invariants;
- retention calculations;
- Class-D Llama legacy-variable compatibility fix;
- pre-cloud undefined-name checking of the generated App source.

## Deployment source

Do not deploy the historical `app/` directory directly for the next validation.
Generate the derived source bundle first:

```bash
python scripts/build_databricks_app_bundle.py
```

Default output:

`build/databricks_app`

The generated bundle contains:

- materialised `app.py` using the shared governance rules;
- `bootstrap.py`;
- `app.yaml`;
- `requirements.txt`;
- canonical `src/ikf` package;
- `.ikf_shared_policy_materialized` marker;
- `ikf_bundle_manifest.json` containing source/materialised hashes and applied
  policy-adoption metadata.

## Gate 0 — mandatory before Databricks validation

The first cloud action is the read-only cost audit:

`sql/02_databricks_cost_audit.sql`

Before deploying or running an IKF Job:

1. review Databricks usage/cost exposure;
2. identify any App, Job or model-serving resources that are unnecessarily
   running;
3. stop unnecessary continuously billed resources;
4. confirm the exact minimum integration checks to execute;
5. prefer existing persisted analyses, QuestionRuns, retrieval snapshots and
   indexed corpora over fresh model inference.

Detailed execution and decision criteria are in:

`docs/33_gate0_cost_audit_and_minimum_integration_proof.md`

## Minimum intended integration proof

Subject to the Gate-0 cost review, the intended cloud proof is limited to:

- one generated App-bundle deployment;
- App startup/resource-binding verification;
- governed source/Files API access;
- reuse of existing persisted case artefacts where possible;
- one fresh Class-B analysis only if existing artefacts cannot prove the new
  source/viewer path;
- one QuestionRun only if Ask Job wiring materially requires it;
- no Class-D model execution unless Class-D runtime itself is the explicit
  validation subject;
- no rebuilding of SHIELD or REFERENCE_CONTEXT unless their indexing code has
  materially changed.

## What is not yet claimed

This baseline is **locally validated**, not Databricks-runtime validated.

It does not claim that:

- Databricks App deployment packaging has been proven in the live workspace;
- Unity Catalog permissions are correct for every user;
- Files API page rendering works under the deployed user token;
- Lakeflow resource bindings are correct after the latest App changes;
- model endpoints are operational/approved;
- retention cleanup has been revalidated after deployment.

Those are integration concerns and should be tested only after Gate 0.
