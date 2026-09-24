# IKF cloud resource inventory for Gate 0

_Date: 2026-09-24_

## Purpose

This document lists the known IKF Databricks resources, execution routes, external services and identifiers that should be recognised during the Gate-0 billing review. It is an attribution aid, not a declaration that every listed resource currently exists or is running.

The billing audit should remain broad first. Do **not** filter the billing query to only these names, because unexpected duplicate Apps, Jobs, notebooks or endpoints are precisely the kind of cost exposure Gate 0 is intended to detect.

A resource appearing in this inventory means **known/configured/used historically** unless a section explicitly says it is the current execution route. Actual billed consumption must be confirmed from `system.billing.usage` and related Databricks billing/system tables.

## Current resource and invocation map

The following map records the principal resources and tools IKF may invoke, and distinguishes configured resources from the currently selected transcription route.

| Resource / tool | IKF role | Invocation / status | Cost relevance |
| --- | --- | --- | --- |
| Databricks App `investigation-kg-poc` | Streamlit investigator-facing application | Known deployment resource; running state must be checked before each validation session | App compute while active |
| Lakeflow Jobs | Analysis, Ask, Class-D, EMCIP, SHIELD, relationship correction, similar cases | Bound through `app/app.yaml`; live numeric IDs must be read from Databricks | Job/serverless compute + model calls triggered by tasks |
| Job `803905874377828` — `Investigation KG - Automated Analysis` | Historical automated analysis chain | Known historical job | Job compute and downstream model/service use when executed |
| Databricks serverless notebooks/jobs | Current preferred execution route for notebook 61 because the user cannot create classic compute | **Current Whisper pilot route: CPU serverless** | DBU consumption while notebook/job runs |
| Serverless Base Environment Standard v5 | Python/runtime base for notebook 61 | **Recommended current base environment** | Standard serverless DBU; no GPU |
| Serverless Base Environment ML v5 | Alternative serverless environment with ML packages preinstalled | Available but **not required** for notebook 61 | Does not itself add a GPU; may carry unnecessary package surface |
| Serverless memory — Standard | REPL memory for notebook execution | **Recommended first setting: 16 GB** | Lower DBU emission than high-memory mode |
| Serverless high memory | Larger notebook REPL memory | Use only after a reproducible out-of-memory failure; current Microsoft documentation lists 32 GB | Higher DBU emission rate |
| `faster-whisper==1.2.1` | Speech-to-text engine for Type-D audio | Installed as notebook/serverless dependency | Package installation + CPU runtime; no separate model-serving endpoint |
| Whisper `large-v3` | High-quality transcription candidate | Pilot model in notebook 61 | CPU time and model download/cache |
| Whisper `turbo` | Faster transcription candidate | Pilot comparison model in notebook 61 | CPU time and model download/cache |
| Unity Catalog Volume `bdw_analysis_prod.kg_poc.investigation_sources` | Governed Type-D source/output storage | Reads audio and writes pilot transcript JSON | Storage plus compute used to read/write; volume itself is not a GPU resource |
| `audios/` | Type-D source audio folder | Source for notebook 61 | Read operations during pilot |
| `type_d_transcripts/` | Restricted pilot output folder | Required output route for notebook 61 | Write operations during pilot |
| Databricks Model Serving / system.ai routes | Governed LLM inference for analysis/Ask workflows | Used only by workflows that explicitly call them; not used by faster-whisper transcription | Token/model-serving cost when invoked |
| Neo4j AuraDB | Knowledge-graph projection, traversal and review metadata | External service used by graph/review workflows | External Neo4j service cost, not Databricks DBU |
| MAIRA governed corpus/retrieval | Published investigation evidence and retrieval | Read/integration dependency | Cost depends on Databricks read/retrieval/model execution used by the calling workflow |
| Databricks SQL / dashboard resources | News dashboard and billing/audit queries | Invoked when dashboard/query is used | SQL/serverless warehouse or dashboard compute |
| `system.billing.usage` + `system.billing.list_prices` | Gate-0 cost audit | Read-only audit | Query compute only; must not trigger IKF analysis/model jobs |
| GitHub | Authoritative source code/documentation | External to Databricks | Not Databricks compute |

### Transcription path selected on 2026-09-24

The original preferred design was an on-demand GPU job. The user does not currently have permission to create a classic GPU compute resource, and the notebook Environment pane does not expose a serverless GPU Accelerator selector. Therefore the current executable fallback is:

```text
Notebook 61
    -> Databricks serverless CPU
    -> Standard base environment v5
    -> standard memory initially (16 GB)
    -> faster-whisper 1.2.1
    -> device=cpu
    -> compute_type=int8
    -> large-v3 + turbo one-time quality pilot
    -> restricted Unity Catalog transcript output
```

Notebook 61 automatically detects whether CUDA is available. With no accelerator it runs `device="cpu"` and `compute_type="int8"`; if a governed GPU route becomes available later, it can use CUDA/FP16 without maintaining a separate transcription implementation.

**ML v5 is not required for this CPU route.** The ML base environment preinstalls Databricks Runtime for Machine Learning Python/system packages, but `faster-whisper` is already declared as a dependency and the notebook does not require Spark ML. Selecting ML v5 does not create or expose a GPU.

**Do not increase memory pre-emptively.** Start with the standard 16 GB serverless notebook memory. Notebook 61 processes the three audio files sequentially and does not use batch transcription. High-memory serverless should be enabled only if the run produces a reproducible out-of-memory condition. Current Azure Databricks documentation lists Standard as 16 GB total notebook memory and High as 32 GB, and states that high-memory serverless has a higher DBU emission rate. If the workspace UI displays a different high-memory amount, record the UI value and billing SKU in the execution record before selecting it.

The official `faster-whisper` documentation supports CPU INT8 execution and reports substantially lower memory use for INT8 than full precision in its published CPU benchmarks. The exact large-v3 memory requirement in the Databricks serverless environment must still be observed in the pilot; the project should not convert a one-time high-memory fallback into the default without evidence.

## Databricks App

Known App name from the IKF deployment history:

- `investigation-kg-poc`

Billing records for Databricks Apps can expose `usage_metadata.app_name` and `usage_metadata.app_id`. Gate 0 should check the complete APPS result set and then identify the IKF App by name/ID.

## Lakeflow / Jobs

Known historical automated-analysis Job:

- Job ID: `803905874377828`
- Name: `Investigation KG - Automated Analysis`
- historical task chain: `15_extract_analysis_evidence` -> `16_analyse_evidence_and_build_graph`

The current App binds to the following logical job resources through `app/app.yaml`:

- `analysis_job`
- `class_d_analysis_job`
- `ask_job`
- `emcip_mapping_job`
- `shield_proposal_job`
- `relationship_correction_job`
- `similar_cases_job`

Their live numeric job IDs must be read from Databricks/runtime configuration; they should not be guessed from GitHub.

### Job/tool call rule

A job binding does not mean the job is continuously consuming resources. Cost is incurred when a job/serverless task is actually executed, when the App is actively consuming its allocated compute, or when an invoked model-serving/SQL resource produces billable usage. Each Gate-0 execution record should therefore capture at minimum:

- job name and numeric job ID;
- task/notebook path;
- run ID;
- start/end timestamps;
- serverless/classic compute route;
- base environment and memory mode where applicable;
- model endpoint/model name if inference is invoked;
- source/retrieval snapshot or analysis ID reused;
- success/failure status;
- retry count;
- attributable billing SKU/DBUs/cost when available.

## Planned / deferred GPU transcription compute

IKF audio transcription was initially designed as a separate **on-demand Lakeflow Job** using `faster-whisper`. This remains the preferred performance route if a governed GPU resource later becomes available, but it is **not the current executable route** because the user does not have permission to create classic compute and serverless GPU is not exposed in the current notebook UI.

The GPU compute must not be treated as permanent App infrastructure and must not remain running while no transcription is being performed.

Current workspace selection / preferred available classic node type observed during configuration:

- Databricks Runtime: **17.3 LTS for Machine Learning**;
- Apache Spark: **4.0.0**;
- Scala: **2.13.16**;
- Machine Learning runtime: **enabled**;
- preferred node type observed: `Standard_NC24ads_A100_v4`;
- CPU: **24 vCPUs**;
- system memory: **220 GiB**;
- accelerator: **1 x NVIDIA A100 PCIe GPU**;
- GPU memory: **80 GB**.

### Why the Machine Learning runtime was selected for the GPU design

The Machine Learning runtime was selected because the proposed classic transcription workload was GPU accelerated, not because IKF requires Spark ML for transcription. On GPU clusters, Databricks Runtime 17.3 LTS ML provides the NVIDIA software stack required by GPU-accelerated Python workloads. `faster-whisper` uses CTranslate2 and can therefore execute Whisper inference on the NVIDIA GPU without IKF having to build and maintain a separate CUDA base environment.

This logic applies to the **classic GPU design only**. It must not be confused with selecting the **ML v5 serverless CPU base environment**, which does not add an accelerator.

### Performance and cost interpretation

`Standard_NC24ads_A100_v4` is **not an IKF minimum hardware requirement**. It was the smallest/preferred one-GPU node exposed during the attempted configuration. The A100 provides substantially more GPU memory and CPU/system memory than `faster-whisper` normally requires for a single transcription stream.

If classic GPU permission is granted later, the design decision is:

1. use GPU compute only **on demand**;
2. create/start the job compute when a transcription is requested;
3. process the audio and persist governed transcription/provenance output;
4. terminate the job compute immediately when the task completes;
5. do not attach this GPU to the continuously available IKF App;
6. do not schedule the transcription job unless a future operational need is explicitly approved;
7. if a smaller compatible one-GPU SKU (for example T4/A10 class) becomes available, benchmark it before accepting A100 as the operating default.

The distinction between **available configuration** and **technical minimum** must be preserved. The 220 GiB of system memory and 80 GB A100 VRAM are consequences of the available Azure SKU, not requirements imposed by Whisper or IKF.

## Model services / endpoints

Public/internal Databricks-hosted routes used by the application include:

- `system.ai.meta-llama-3-3-70b-instruct`
- `system.ai.gpt-oss-120b`

Class-D dedicated endpoint names appearing in the repository/design include:

- `ikg-class-d-gpt-oss-20b`
- `ikg-class-d-llama-3-3-70b`
- `bdw_analysis_prod.kg_poc.ikf-llama-3-3-70b-poc` (current App configuration value for `CLASS_D_LLAMA70_ENDPOINT`)

The endpoint-creation helper uses `scale_to_zero_enabled = True` and applies project/information-class tags when it creates custom endpoints. Existence does not mean the endpoint is approved for Class-D use.

Gate 0 must review **all** endpoint names returned by billing, including names not present in this inventory.

## SQL / serverless notebook workloads

The billing table can expose `usage_metadata.notebook_path`, `job_name`, `job_id`, `job_run_id` and the executing identity where Databricks can attribute the usage.

Known IKF notebook families include:

- extraction/analysis: notebooks 15-16;
- MAIRA bridge/benchmark: notebooks 25-31;
- App/MAIRA runtime validation: notebooks 32-35;
- Ask: notebooks 36-38;
- Type-D audio/transcription: notebooks 38-40 and notebook 61 quality pilot;
- relationship/EMCIP review: notebooks 39-43;
- reference context / SHIELD: notebooks 44-48;
- relationship correction: notebooks 49-51;
- similar cases: notebooks 52-54;
- consolidated/coverage validation: notebooks 55-60.

The presence of one of these notebook paths in billing does not automatically mean the run was unnecessary. Gate 0 is intended to identify the workload, associate it with a development action, and determine whether similar future runs can be avoided or reused.

### AI Transcribe status

Databricks AI Transcribe Preview was attempted earlier but the workspace returned that the preview is not enabled and requires a workspace administrator. Therefore AI Transcribe is **not an available IKF transcription service in the current workspace configuration** and should not be documented as an operational dependency. The `faster-whisper` route was introduced specifically so transcription can proceed without depending on that preview.

A failed availability check may still have used ordinary notebook/serverless compute for the code that reached the service, but it did not establish an operational AI Transcribe workload. Billing attribution should rely on `system.billing.usage`, not on assumptions from the error alone.

## Persisted artefacts to reuse instead of rerunning models

Known persisted identifiers useful for the minimum integration proof include:

- Analysis: `analysis_6b330c0e0ce24b6caebb40e041038c55`
- QuestionRun: `question_1af98ef693404bc69d5b24a26eff10fd`
- MAIRA benchmark: `maira_benchmark_9e059930506d33295105addcd06e821d`
- MAIRA retrieval snapshot: `snapshot_742f8e0adbccbbf8bf3610015e824415`

These should be preferred for read-path and UI integration checks when the validation question does not materially require new inference.

## Gate-0 attribution rule

Classify each material billing line as one of:

1. **IKF attributable / expected** — explained by a known development or validation activity;
2. **IKF attributable / avoidable** — attributable to IKF but likely reducible through stopping, scale-to-zero, reuse or batching;
3. **not IKF / known other workload** — explained by another project/service;
4. **unexplained** — investigate before GO.

A material unexplained charge or an unnecessary continuously billed resource is a STOP condition for new IKF cloud execution until understood or stopped.
