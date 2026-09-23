# Gate 0 / minimal integration execution record

_Copy this template when the next Databricks validation session is performed._

## Session identity

- Date:
- Investigator/operator:
- Release branch: `release/ikf-local-baseline-2026-09-23`
- Validated commit: `967c680ab697d24a78cc618b1a807f2e8a7cf610`
- Bundle manifest adoption version:
- Bundle source SHA-256:
- Bundle materialised SHA-256:

## Gate 0A — pre-validation cost audit

Audit source: `sql/02_databricks_cost_audit.sql`

### Overall usage/cost

- Relevant billing origins/SKUs:
- Effective list cost observed:
- Date range reviewed:
- Unexplained usage: YES / NO

### IKF Jobs

- Active/recent IKF jobs identified:
- Unexpected/recurrent runs: YES / NO
- Resources stopped before validation:

### Apps / model serving / other compute

- App-related usage:
- Model-serving/API usage:
- SQL/serverless or other compute:
- Unexpected ongoing cost: YES / NO

### Gate decision

- Decision: GO / STOP
- Reason:
- Corrective action required before deployment:

## Gate 0B — persisted-artifact preflight

Candidate existing artefacts checked:

- `analysis_6b330c0e0ce24b6caebb40e041038c55`: PRESENT / ABSENT / NOT CHECKED
- `question_1af98ef693404bc69d5b24a26eff10fd`: PRESENT / ABSENT / NOT CHECKED
- `maira_benchmark_9e059930506d33295105addcd06e821d`: PRESENT / ABSENT / NOT CHECKED

Reusable without fresh inference:

- Analysis/source provenance:
- Source viewer/page references:
- Knowledge Graph:
- Review states:
- QuestionRun:
- SHIELD:
- EMCIP:

## Gate 1 — deployment bundle

- Bundle built from frozen branch: YES / NO
- `.ikf_shared_policy_materialized` present: YES / NO
- `ikf_bundle_manifest.json` reviewed: YES / NO
- Canonical `src/ikf` present in bundle: YES / NO

## Gate 2 — App integration checks

- App startup: PASS / FAIL / NOT RUN
- Resource/environment bindings: PASS / FAIL / NOT RUN
- Landing/capabilities UI: PASS / FAIL / NOT RUN
- Existing analyses list/read: PASS / FAIL / NOT RUN
- MAIRA published-material routing: PASS / FAIL / NOT RUN
- IKF technical/internal routing: PASS / FAIL / NOT RUN
- Source viewer + page references: PASS / FAIL / NOT RUN
- Knowledge Graph rendering/filtering: PASS / FAIL / NOT RUN
- Human-review states: PASS / FAIL / NOT RUN
- Existing QuestionRun rendering: PASS / FAIL / NOT RUN

Defects/notes:

## Gate 3 — fresh execution exceptions

Fresh execution should remain empty unless persisted state was insufficient.

### Class-B analysis

- Run performed: YES / NO
- Reason required:
- Analysis ID:
- Job/run ID:

### QuestionRun

- Run performed: YES / NO
- Reason required:
- QuestionRun ID:
- Job/run ID:

### Other model/proposal/index execution

- Execution performed:
- Reason required:
- Run/resource IDs:

### Class D

- Class-D model invoked: YES / NO
- If YES, explicit unresolved validation requirement:

## Gate 4 — post-validation cost audit

- Audit rerun: YES / NO
- Incremental effective list cost attributable to session:
- Incremental App usage:
- Incremental Jobs usage:
- Incremental model/API usage:
- Unexpected residual cost after session: YES / NO
- Resources stopped after validation:

## Final outcome

- Integration proof: PASS / PARTIAL / FAIL
- Release-candidate behaviour parity accepted: YES / NO
- Fresh inference kept to minimum necessary: YES / NO
- Cost exposure understood: YES / NO

## Pending / next step

- Pending defects:
- Required code/documentation changes:
- Next planned validation:
