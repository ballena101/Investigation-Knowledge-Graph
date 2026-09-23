# IKF cloud resource inventory for Gate 0

_Date: 2026-09-23_

## Purpose

This document lists the known IKF Databricks resources and identifiers that
should be recognised during the Gate-0 billing review. It is an attribution aid,
not a declaration that every listed resource currently exists or is running.

The billing audit should remain broad first. Do **not** filter the billing query
to only these names, because unexpected duplicate Apps, Jobs or endpoints are
precisely the kind of cost exposure Gate 0 is intended to detect.

## Databricks App

Known App name from the IKF deployment history:

- `investigation-kg-poc`

Billing records for Databricks Apps can expose `usage_metadata.app_name` and
`usage_metadata.app_id`. Gate 0 should check the complete APPS result set and
then identify the IKF App by name/ID.

## Lakeflow / Jobs

Known historical automated-analysis Job:

- Job ID: `803905874377828`
- Name: `Investigation KG - Automated Analysis`
- historical task chain: `15_extract_analysis_evidence` ->
  `16_analyse_evidence_and_build_graph`

The current App also binds to the following logical job resources through
`app/app.yaml`:

- `analysis_job`
- `class_d_analysis_job`
- `ask_job`
- `emcip_mapping_job`
- `shield_proposal_job`
- `relationship_correction_job`
- `similar_cases_job`

Their live numeric job IDs must be read from Databricks/runtime configuration;
they should not be guessed from GitHub.

## Model services / endpoints

Public/internal Databricks-hosted routes used by the application include:

- `system.ai.meta-llama-3-3-70b-instruct`
- `system.ai.gpt-oss-120b`

Class-D dedicated endpoint names appearing in the repository/design include:

- `ikg-class-d-gpt-oss-20b`
- `ikg-class-d-llama-3-3-70b`
- `bdw_analysis_prod.kg_poc.ikf-llama-3-3-70b-poc` (current App configuration value for `CLASS_D_LLAMA70_ENDPOINT`)

The endpoint-creation helper uses `scale_to_zero_enabled = True` and applies
project/information-class tags when it creates custom endpoints. Existence does
not mean the endpoint is approved for Class-D use.

Gate 0 must review **all** endpoint names returned by billing, including names
not present in this inventory.

## SQL / serverless notebook workloads

The billing table can expose `usage_metadata.notebook_path`, `job_name`,
`job_id`, `job_run_id` and the executing identity where Databricks can attribute
the usage.

Known IKF notebook families include:

- extraction/analysis: notebooks 15-16;
- MAIRA bridge/benchmark: notebooks 25-31;
- App/MAIRA runtime validation: notebooks 32-35;
- Ask: notebooks 36-38;
- relationship/EMCIP review: notebooks 39-43;
- reference context / SHIELD: notebooks 44-48;
- relationship correction: notebooks 49-51;
- similar cases: notebooks 52-54;
- consolidated/coverage validation: notebooks 55-59.

The presence of one of these notebook paths in billing does not automatically
mean the run was unnecessary. Gate 0 is intended to identify the workload,
associate it with a development action, and determine whether similar future
runs can be avoided or reused.

## Persisted artefacts to reuse instead of rerunning models

Known persisted identifiers useful for the minimum integration proof include:

- Analysis: `analysis_6b330c0e0ce24b6caebb40e041038c55`
- QuestionRun: `question_1af98ef693404bc69d5b24a26eff10fd`
- MAIRA benchmark: `maira_benchmark_9e059930506d33295105addcd06e821d`
- MAIRA retrieval snapshot: `snapshot_742f8e0adbccbbf8bf3610015e824415`

These should be preferred for read-path and UI integration checks when the
validation question does not materially require new inference.

## Gate-0 attribution rule

Classify each material billing line as one of:

1. **IKF attributable / expected** — explained by a known development or
   validation activity;
2. **IKF attributable / avoidable** — attributable to IKF but likely reducible
   through stopping, scale-to-zero, reuse or batching;
3. **not IKF / known other workload** — explained by another project/service;
4. **unexplained** — investigate before GO.

A material unexplained charge or an unnecessary continuously billed resource is
a STOP condition for new IKF cloud execution until understood or stopped.
