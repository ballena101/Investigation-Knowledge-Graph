# IKF Databricks runtime consumption ledger

_Date started: 2026-09-24_

## Purpose

This ledger records IKF Databricks execution that can consume billable resources or invoke external/model services. It complements `35_ikf_cloud_resource_inventory.md`, which lists known/configured resources. The distinction is deliberate:

- **inventory** = what exists, is configured, or may be invoked;
- **ledger** = what was actually selected, started, called, or observed during development/validation.

Actual DBUs and monetary cost must still be reconciled against Databricks billing/system tables. Do not infer cost solely from this ledger.

## Current Whisper pilot — observed execution

### Preflight run 1 — 2026-09-24

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
- output path configured: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts`.

Observed result:
- source volume and runtime were visible;
- smoke-test configuration was active: one audio file + `large-v3`;
- preflight stopped before model inference because the restricted transcript output directory did not yet exist;
- error: `AssertionError: Restricted transcript output directory is unavailable`;
- no transcript was written and no Whisper model inference was started by this failed preflight.

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

Notebook 61 was updated after this failure so that future preflight runs:
- attempt to create `type_d_transcripts` only if the executing identity already has the required Unity Catalog permissions;
- do **not** broaden permissions automatically;
- perform a temporary write/delete probe before any model loading;
- fail with a targeted `WRITE VOLUME` permission message if the directory cannot be created or written.

### Preflight run 2 — successful storage/write validation — 2026-09-24

Observed runtime remained:
- Databricks **serverless CPU**;
- Standard v6;
- standard 16 GB notebook memory setting;
- 4 logical CPUs;
- 0 CUDA devices;
- faster-whisper target runtime `cpu` / `int8`;
- smoke test active with `19970212-090-sv-gale-runner-mayday-call.wav` + `large-v3`.

Observed result:
- source audio path visible;
- output directory did not initially exist;
- notebook successfully created `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts` using the executing identity's existing governed permissions;
- temporary write/delete probe succeeded;
- preflight printed `PRECHECK PASS`;
- therefore source read visibility and output create/write/delete capability were confirmed before model loading.

What this successful preflight consumed/called:
- Databricks serverless CPU notebook compute for the preflight cell;
- Unity Catalog Volume directory creation plus a minimal temporary write/delete probe.

What it still did **not** call:
- no GPU or classic cluster;
- no A100;
- no Databricks model-serving endpoint;
- no external transcription API;
- no AI Transcribe;
- no Neo4j/MAIRA/SHIELD/IKF analysis job;
- no Whisper model inference yet;
- no `large-v3` weights were loaded by the preflight cell itself.

This successful preflight is the GO condition for the next controlled step: one audio file with one model (`large-v3`) on CPU/INT8. Do not expand to the full three-file/two-model comparison until that single smoke test succeeds and its runtime/cost/output are recorded.

### Smoke test — unauthenticated model load/download initiated — 2026-09-24

Observed notebook output:
- `LOADING MODEL large-v3 device cpu compute_type int8`;
- Hugging Face Hub warning that requests were unauthenticated and an `HF_TOKEN` would provide higher rate limits/faster downloads.

Interpretation and external call:
- `faster-whisper` began resolving/downloading the public CTranslate2 `large-v3` model from the Hugging Face Hub;
- this was an external **model-artifact download**, not an upload of IKF audio;
- the source audio remained in the Databricks Unity Catalog Volume and was not sent to Hugging Face by notebook 61;
- no `HF_TOKEN` was configured for this attempt;
- unauthenticated download of public model repositories is permitted but subject to anonymous rate limits;
- this step consumed Databricks serverless CPU/runtime plus outbound network/model-download activity; actual Databricks DBUs/cost remain to be reconciled from billing;
- no successful transcription result was recorded from this attempt before the notebook design was changed.

### Implementation change — authenticated persistent model cache — 2026-09-24

Notebook 61 was changed so future model preparation:
- retrieves a read-only Hugging Face token from Unity Catalog secret `bdw_analysis_prod.kg_poc.huggingface_read_token`;
- never prints or persists the token;
- creates/reuses persistent cache `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper`;
- performs a cache write/delete probe before download;
- downloads only required faster-whisper model artifacts with `huggingface_hub.snapshot_download()`;
- caches the snapshot in the governed Volume so later serverless sessions can reuse it;
- loads inference from the returned local snapshot with `local_files_only=True`;
- keeps the one-file/one-model `large-v3` smoke-test gate enabled.

Current model repository mapping:
- `large-v3` -> `Systran/faster-whisper-large-v3`;
- `turbo` -> `mobiuslabsgmbh/faster-whisper-large-v3-turbo`.

### Authenticated model preparation — successful — 2026-09-24

Observed result:
- model: `large-v3`;
- repository: `Systran/faster-whisper-large-v3`;
- authenticated Hugging Face access: confirmed by preflight (`hf_token_configured: True`);
- preparation elapsed: **32.39 seconds**;
- persistent local snapshot: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper/models--Systran--faster-whisper-large-v3/snapshots/edaa852ec7e145841d8ffdb056a99866b5f0a478`;
- snapshot revision/hash component: `edaa852ec7e145841d8ffdb056a99866b5f0a478`;
- the incidental `pyspark.databricks.pandas.usage_logger` JVM-not-initialised warning did not prevent model preparation; the authoritative completion marker was `MODEL READY`.

Interpretation:
- the authenticated persistent-cache design materially reduced the model-preparation wait compared with the earlier unauthenticated attempt;
- future sessions should reuse this snapshot rather than download the model again, provided the Volume cache remains intact.

### `large-v3` CPU transcription smoke test — runtime concern — 2026-09-24

Observed while the first transcription cell was running:
- model: `large-v3` from the persistent local snapshot;
- compute: serverless CPU, 4 logical CPUs, INT8, Standard v6 / standard 16 GB memory;
- source: `19970212-090-sv-gale-runner-mayday-call.wav`;
- elapsed wall time observed by the user: **more than 15 minutes**;
- no `DONE` completion marker had been reported at that point.

Cost-control interpretation:
- do not expand this configuration to the remaining recordings or models while its real-time factor is unknown;
- stop the long-running smoke test rather than continue unbounded CPU consumption;
- determine the source recording duration before classifying the run as intrinsically slow, because cost/performance should be assessed as transcription elapsed time divided by source-audio duration;
- if the resulting real-time factor is poor, test `turbo` on the same recording before considering more CPU memory or GPU infrastructure;
- do not infer that `large-v3` is unsuitable for quality reference use; the observation concerns this **4-CPU operating route**, not transcription quality.

Expected cost effect of the cache design:
- first successful authenticated download still consumes serverless runtime and outbound network activity;
- subsequent runs should avoid re-downloading the complete cached snapshot when the Volume cache remains intact;
- this should reduce repeated serverless wait time and external download traffic materially compared with ephemeral/anonymous loading;
- actual savings must be confirmed from runtime and billing rather than assumed.

Longer-term architecture note:
- the pilot cache is deliberately inside the existing governed `investigation_sources` Volume because write access is already validated;
- after the pilot, model binaries should preferably move to a dedicated governed model-artifact Volume so model artifacts and investigation evidence remain logically separated.

## Whisper dependency and model execution

Planned notebook dependency:
- `faster-whisper==1.2.1`.

When the actual transcription cell runs, record separately:
- dependency installation status;
- whether model weights were downloaded or loaded from persistent cache;
- model name (`large-v3` or `turbo`);
- Hugging Face repository ID;
- model-preparation elapsed seconds;
- audio file processed;
- source audio SHA-256;
- transcription elapsed seconds;
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
- derived pilot output: `bdw_analysis_prod.kg_poc.investigation_sources/type_d_transcripts`;
- persistent Whisper model cache: `bdw_analysis_prod.kg_poc.investigation_sources/_model_cache/faster_whisper`.

Original audio remains authoritative. Transcript files are derived Class-D material and must retain source identity/provenance and access controls. The model cache contains public model artifacts, not investigation evidence, despite its temporary pilot placement within the same governed Volume.

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
- MAIRA corpus/retrieval integration — may cause Databricks read/model compute depending on the calling workflow;
- Hugging Face Hub — authenticated read-only public Whisper/CTranslate2 model artifact download during model preparation when the required snapshot is not already present in the persistent cache.

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
4. Persist reusable public model artifacts in governed storage instead of repeatedly downloading them on ephemeral serverless sessions.
5. Do not run full corpus/model comparisons until a single-file/single-model smoke test passes.
6. Keep retries disabled for expensive experimental jobs unless a specific failure mode justifies them.
7. Reconcile significant runs against `system.billing.usage` / pricing data rather than relying on estimates.
8. Treat unexplained recurring consumption as a STOP condition before further cloud validation.
