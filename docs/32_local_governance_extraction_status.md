# IKF local governance extraction and adoption status

_Last updated: 2026-09-23_

## Purpose

This file records the completed local-first governance extraction and App-adoption milestone. The authoritative operational next steps are maintained in `docs/25_implementation_status_and_roadmap.md` and `docs/33_gate0_cost_audit_and_minimum_integration_proof.md`.

## DONE — deterministic governance extraction

Reusable `src/ikf/` policy and regression coverage now exist for:

- information-class pre-screen;
- MAIRA/IKF source ownership and catalogue routing;
- evidence-location parsing and document-scope enforcement;
- QuestionRun scope / retrieval-snapshot / citation boundaries;
- relationship-review governance;
- SHIELD Gate-1 / Gate-2 governance;
- EMCIP governed-shortlist restrictions;
- graph document scope / structural passthrough / chronology-vs-causality rules;
- Class-D and ordinary transient-content retention calculations.

## DONE — App adoption and deployable bundle

The repository is installable through `pyproject.toml`, with Databricks/PySpark orchestration lazy-loaded so deterministic policy remains locally testable.

The transitional App-adoption layer binds duplicated historical `app.py` behaviour to canonical modules for:

1. retention policy;
2. evidence-location parsing;
3. source routing;
4. QuestionRun scope;
5. relationship review;
6. SHIELD Gate 2;
7. EMCIP review;
8. graph document scope;
9. Class-D Llama endpoint compatibility.

`scripts/build_databricks_app_bundle.py` materialises those policies before deployment, compiles the result and produces a derived App bundle containing canonical `src/ikf`, the materialisation marker and the bundle manifest/hash contract.

## DONE — pre-cloud safety controls

The release candidate now includes deterministic guards that ensure:

- the Gate-0 billing SQL remains SELECT-only;
- notebook 60 remains read-only and cannot trigger a Job/model call or write;
- `app/app.yaml` exposes the expected release-candidate environment contract;
- every `valueFrom` resource in `app.yaml` is required by notebook 55;
- notebook 55, notebook 60 and the cost-audit SQL trigger CI when changed;
- the materialised App has no undefined-name regression detectable by the static check.

Notebook 55 now checks the complete current App resource contract, including:

- Neo4j bindings;
- all seven Lakeflow Job bindings;
- Class-D GPT-OSS endpoint binding;
- legacy Class-D Llama resource binding used for compatibility;
- direct-text encryption key;
- admin-user binding.

Literal configuration such as `CLASS_D_LLAMA70_ENDPOINT` remains covered by the local App configuration tests rather than by the Databricks resource list.

## CURRENT LOCAL VALIDATION STATUS

Frozen branch:

`release/ikf-local-baseline-2026-09-23`

Validated code commit:

`f8aea8c2e59f98634222bd9e11d99d2b421e5224`

GitHub Actions run:

`35923614601`

Result:

**87 deterministic tests passed.**

Additional checks:

- materialised App bundle: **PASS**;
- undefined-name static check: **PASS**;
- App resource/environment contract: **PASS**;
- `app.yaml` ↔ notebook-55 resource parity: **PASS**;
- notebook-60 no-inference/no-write guard: **PASS**;
- Gate-0 cost SQL SELECT-only guard: **PASS**.

No Databricks deployment, Lakeflow Job or model endpoint was invoked to reach this state.

## Defects caught locally before cloud execution

Local/GitHub validation has already prevented several paid-cloud debugging cycles, including:

- accidental PySpark coupling in the deterministic package root;
- incorrect retention helper API usage;
- Class-D Llama legacy-variable `NameError` risk;
- bundle-manifest expectation drift after a new policy adoption;
- incomplete notebook-55 resource checks relative to `app.yaml`.

## Retention note

`notebooks/23_purge_expired_analysis_artifacts.py` consumes persisted expiry timestamps and does not independently recreate the 24-hour / 72-hour policy. Canonical retention calculation remains under `src/ikf/retention.py` for refactored/new creation paths.

## NEXT

Local functional refactoring is intentionally paused at this boundary. The next useful evidence is live integration evidence, in this strict order:

1. Gate-0 billing audit;
2. stop/understand unnecessary cost exposure;
3. notebook 60 persisted read-path check;
4. notebook 55 broader preflight only if needed;
5. build the frozen release bundle;
6. one App deployment;
7. validate persisted state before any fresh inference;
8. run fresh Class-B/Ask inference only if a changed live path cannot be proven otherwise;
9. immediately re-run the billing audit and record incremental cost.

Databricks remains the integration-proof environment, not the routine debugging environment.
