# IKF Databricks runtime consumption ledger

_Date started: 2026-09-24_

## Purpose

This ledger records IKF Databricks execution that can consume billable resources or invoke external/model services. It complements `35_ikf_cloud_resource_inventory.md`, which lists known/configured resources. The distinction is deliberate:

- **inventory** = what exists, is configured, or may be invoked;
- **ledger** = what was actually selected, started, called, or observed during development/validation.

Actual DBUs and monetary cost must still be reconciled against Databricks billing/system tables. Do not infer cost solely from this ledger.

## Current Whisper pilot — observed execution

### Preflight run — 2026-09-24

Notebook:
- `notebooks/61_compare_whisper_type_d_audio.py`

Observed runtime from notebook preflight:
- execution route: Databricks **serverless CPU notebook**;
- base environment: **Standard v6**;
- notebook memory setting: **standard / 16 GB** unless explicitly changed later;
- CUDA devices visible: **0**;
- logical CPU count visible to the notebook: **4**;
- faster-whisper device selected by notebook: `cpu`;
- compute type selected by notebook: `int8`;
- source path visible: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios`;
- output path visible: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts`.

What this preflight consumed/called:
- Databricks serverless notebook compute for the preflight cell;
- Unity Catalog Volume metadata/path access checks.

What the preflight did **not** call:
- no GPU;
- no classic cluster;
- no A100 node;
- no Databricks model-serving endpoint;
- no OpenAI/external transcription API;
- no Databricks AI Transcribe service;
- no Neo4j write;
- no MAIRA retrieval;
- no SHIELD classifier;
- no IKF analysis/Ask job;
- no Whisper transcription inference yet;
- no `large-v3` or `turbo` model inference yet.

The preflight therefore validates compute/path visibility only. It is not evidence that the transcription model has run successfully.

## Whisper dependency and model execution

Planned notebook dependency:
- `faster-whisper==1.2.1`.

When the actual transcription cell runs, record separately:
- dependency installation status;
- whether model weights were downloaded or loaded from cache;
- model name (`large-v3` or `turbo`);
- audio file processed;
- source audio SHA-256;
- elapsed seconds;
- serverless environment version;
- memory mode;
- success/failure;
- output path;
- whether a rerun was avoided because output already existed.

The first production-like test should be a **single audio file with a single model** before running the full three-file/two-model comparison. This limits serverless CPU consumption while validating dependency, model loading, read/write permissions and transcription output.

## Databricks resources known to IKF

### Databricks App
- `investigation-kg-poc`

### Known historical Lakeflow Job
- Job ID: `803905874377828`
- Name: `Investigation KG - Automated Analysis`
- historical chain: `15_extract_analysis_evidence` -> `16_analyse_evidence_and_build_graph`

### App-bound logical jobs
The current App configuration binds to:
- `analysis_job`;
- `class_d_analysis_job`;
- `ask_job`;
- `emcip_mapping_job`;
- `shield_proposal_job`;
- `relationship_correction_job`;
- `similar_cases_job`.

A binding does not mean a job is running. Each actual invocation must be recorded with numeric job ID, run ID and timestamps when available.

### Databricks model routes known in IKF
Public/internal routes appearing in the current architecture:
- `system.ai.meta-llama-3-3-70b-instruct`;
- `system.ai.gpt-oss-120b`.

Class-D endpoint names appearing in the design/configuration:
- `ikg-class-d-gpt-oss-20b`;
- `ikg-class-d-llama-3-3-70b`;
- `bdw_analysis_prod.kg_poc.ikf-llama-3-3-70b-poc`.

Record a model endpoint here only when a run actually invokes it. Endpoint existence/configuration alone is not consumption.

### Unity Catalog / storage
Current Type-D audio routes:
- source: `bdw_analysis_prod.kg_poc.investigation_sources/audios`;
- derived pilot output: `bdw_analysis_prod.kg_poc.investigation_sources/type_d_transcripts`.

Original audio remains authoritative. Transcript files are derived Class-D material and must retain source identity/provenance and access controls.

### Deferred GPU route
A classic GPU route was explored but could not be created with the user's current permissions. The observed candidate was:
- `Standard_NC24ads_A100_v4`;
- 24 vCPU;
- 220 GiB system RAM;
- 1 x NVIDIA A100 PCIe;
- 80 GB GPU VRAM;
- DBR 17.3 LTS ML.

This route is **not currently consumed** by the Whisper pilot and must not appear as actual usage unless Databricks billing confirms a future run.

### AI Transcribe
Databricks AI Transcribe Preview returned a workspace permission/feature-disabled error. It is not an operational IKF transcription route and should not be treated as a recurring service dependency.

## External/non-Databricks services relevant to IKF

These may be called by IKF workflows but are not Databricks DBU resources themselves:
- Neo4j AuraDB — knowledge graph persistence/query;
- GitHub — authoritative source code/documentation;
- MAIRA corpus/retrieval integration — may cause Databricks read/model compute depending on the calling workflow.

## Run-record template

For every material Databricks execution, append or persist an equivalent record with:

| Field | Value |
| --- | --- |
| Date/time | |
| Purpose | |
| Notebook/task | |
| Job name / ID | |
| Job run ID | |
| Compute route | |
| Base environment/runtime | |
| Memory mode | |
| CPU/GPU visible | |
| Dependency/tool invoked | |
| Model/endpoint invoked | |
| Source/retrieval ID | |
| Output/analysis ID | |
| Start/end time | |
| Retry count | |
| Result | |
| DBU / SKU / cost | reconcile from billing |
| Reusable output produced | |
| Could future rerun be avoided? | |

## Cost-control rules

1. Prefer persisted analyses, retrieval snapshots and benchmark outputs over rerunning models.
2. Keep GPU routes on-demand only; never attach a GPU to the continuously available IKF App.
3. Use standard serverless memory first and increase memory only after a reproducible memory failure or measured need.
4. Do not run full corpus/model comparisons until a single-file/single-model smoke test passes.
5. Keep retries disabled for expensive experimental jobs unless a specific failure mode justifies them.
6. Reconcile significant runs against `system.billing.usage` / pricing data rather than relying on estimates.
7. Treat unexplained recurring consumption as a STOP condition before further cloud validation.
