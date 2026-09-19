# Automated analysis orchestration

## User experience

The normal user must not manually execute processing notebooks.

The target workflow is:

```text
Document library
      ↓
App: select 1–5 documents
      ↓
Create analysis
      ↓
App triggers Lakeflow Job
      ↓
Task 1 — evidence extraction
      ↓
Task 2 — cross-document analysis + graph build
      ↓
COMPLETED
      ↓
App: summary + findings + evidence status + graph
```

The processing notebooks remain implementation modules and debugging surfaces,
not user-facing workflow steps.

## Lakeflow Job

One reusable Lakeflow Job contains two sequential notebook tasks:

1. `15_extract_analysis_evidence`
2. `16_analyse_evidence_and_build_graph`

The Job accepts one job parameter:

- `analysis_id`

Notebook task parameters are populated automatically from the job parameter.

The Job runs under its configured **Run as** identity. In the initial PoC this
should remain the creator/owner identity that already has permission to read the
source Unity Catalog volume and write the PoC Delta tables.

## App integration

The Job is attached to the Databricks App as a managed resource:

- resource type: Lakeflow Job;
- resource key: `analysis_job`;
- permission: `Can manage run`.

The App receives the Job ID through:

```yaml
- name: ANALYSIS_JOB_ID
  valueFrom: analysis_job
```

After creating an `AnalysisGroup`, the App calls Jobs API `run-now` with the
new `analysis_id`.

The App's own service principal only requires permission to trigger and monitor
the Job. It does not require direct access to the source Unity Catalog volume.

## Processing statuses

Expected lifecycle:

```text
PENDING_PROCESSING
QUEUED
EXTRACTING
EVIDENCE_READY
ANALYSING
COMPLETED
```

Failure states use:

```text
FAILED
```

with a specific `processing_stage` and `processing_error`.

Progress metadata is kept on the Neo4j `AnalysisGroup` so the App can render:

- documents processed / total;
- pages processed / total;
- passages created;
- analysis batches processed / total;
- graph node count;
- graph relationship count;
- Databricks Job run ID.

## Evidence and methodological controls

Automation must not weaken the investigation methodology.

The pipeline preserves:

- analysis → document → page → passage provenance;
- original-language source text;
- deterministic passage IDs;
- candidate vs reviewed analytical status;
- explicit uncertainty and source conflicts.

Chronology must never be promoted automatically to causality.

Cross-document resolution may consolidate equivalent concepts and previously
supported relationships, but it must not invent a new causal or contributory
relationship.

## Human review

Automation ends with machine-generated **candidate** analysis.

Human review remains a separate controlled stage. The existing relationship and
EMCIP review patterns will be generalised to generic AnalysisGroups.

## Debugging

Notebooks 15 and 16 may still be run manually by a developer for debugging or
validation. Manual execution is not part of the normal investigator workflow.


## Visible process timeline

The App must expose the whole processing lifecycle, not only the current
high-level status. For every AnalysisGroup, the Analyses tab displays the
ordered pipeline:

1. Analysis created
2. Workflow queued
3. Evidence extraction
4. Evidence ready
5. Candidate extraction
6. Cross-document resolution
7. Privacy validation
8. Knowledge graph construction
9. Completed

Each stage is shown as one of:

- Pending
- Running
- Completed
- Failed

Where available, progress counters are displayed alongside the relevant stage:

- documents processed / total;
- pages processed / total;
- passages created;
- analysis batches processed / total;
- graph nodes;
- graph relationships.

Failure remains attached to the exact processing stage through
`processing_stage` and `processing_error`.

This status view is part of the normal investigator workflow so the user never
has to infer whether processing is still running or has finished.

## Source-of-truth and deployment decision

The long-term source of truth for the Investigation Knowledge Graph project is
the GitHub repository:

`ballena101/Investigation-Knowledge-Graph`

The current Databricks workspace source folder is transitional only.

Target state:

1. all application code, processing notebooks and documentation are maintained
   in GitHub;
2. the Databricks App is deployed from the Git-backed project source rather
   than a manually copied workspace folder;
3. processing jobs reference the Git-backed source consistently;
4. after successful Git-based deployment and validation, the old workspace App
   source folder can be retired;
5. no future feature should require maintaining two independent copies of the
   App source.

The workspace folder must not be deleted until the Git-based deployment,
Lakeflow Job execution and rollback path have all been validated successfully.


## Input modes and model policy

The automated Job accepts analyses created from either indexed documents or
Direct text.

The App records `input_mode`, `information_class` and the
policy-selected `requested_model_service` before the Job starts.

Current routing:

- A/B → `system.ai.gpt-5-6-sol`
- C → `system.ai.gpt-oss-120b`
- D → `CLASS_D_MODEL_ENDPOINT` (dedicated GPT-OSS 20B)

The Job receives the exact model service/endpoint as `model_service`.

Direct-text A/B/C sources are converted into Delta passages by notebook 15 and
then their raw Neo4j `text_content` field is removed. Class D direct text is
blocked pending secure governed ingress.

See `docs/16_unified_input_and_model_routing.md`.
