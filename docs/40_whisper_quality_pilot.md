# Type D Whisper quality pilot and interface defaults

## Decision and scope

AI Transcribe Preview is not enabled in the workspace. Notebook
`61_compare_whisper_type_d_audio.py` compares faster-whisper `large-v3` and
`turbo` on the three existing recordings. Number 40 was already used; the
current repository has notebooks through 62. This pilot is not an unattended
production ingestion route. It does not call notebook 39 or mark an analysis
`EVIDENCE_READY`. Existing notebooks 38/39 assume `ai_transcribe()` output;
the adapter for Whisper output must be reviewed and implemented separately.

## Controlled execution

Create `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts`
with access limited to authorized Type D reviewers. Notebook 61 is now portable
across the approved Databricks environments available to the user: it detects a
visible NVIDIA GPU and uses CUDA/FP16 when one exists; otherwise it uses
CPU/INT8. This allows the controlled pilot to run on Databricks serverless CPU
when the user does not have classic cluster-creation rights and Serverless GPU /
AI Runtime is not exposed by the workspace.

The CPU route is a resource/permission fallback, not a statement that GPU is
unnecessary for production throughput. If a governed GPU route is later made
available, the selected validation subset should be repeated on CUDA/FP16 before
the GPU production route is treated as runtime validated.

`faster-whisper` must be installed as an environment dependency. No always-on
endpoint is needed. The pilot records a SHA-256 audio identity, model and decoding
parameters, selected device/compute type, timestamps, language estimate and
elapsed time per file. Existing output is skipped by source hash and model name.
The source audio remains the authoritative record.

Before production use, pin dependency/model revisions and ensure the output
directory is restricted. Never commit source audio or transcripts to GitHub.
Do not expose output in public notebook results, logs or app surfaces. The
Type D access and retention owner must confirm the controls for protected
statements, identities, derivative records, disclosure and deletion under
Article 9 and applicable national rules.

## Authenticated Hugging Face download and persistent cache

Notebook 61 now retrieves a **read-only Hugging Face token** from the Unity
Catalog secret:

`bdw_analysis_prod.kg_poc.huggingface_read_token`

The secret value is never printed, included in transcript metadata, written to
GitHub or stored in the model cache. The preflight fails closed if the secret is
missing or empty.

The selected faster-whisper CTranslate2 model snapshot is downloaded with
Hugging Face `snapshot_download()` into the persistent governed cache:

`/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper`

This is a pilot placement inside the existing governed `investigation_sources`
Volume so the current user can reuse already-approved `WRITE VOLUME` access.
It avoids repeated multi-gigabyte downloads across ephemeral serverless notebook
sessions. A separate model-artifact Volume is preferable for the longer-term
architecture so model binaries are not logically mixed with investigation
evidence; moving the cache later does not require changing transcript outputs.

The pilot explicitly downloads only the model files needed by faster-whisper:
`config.json`, `preprocessor_config.json`, `model.bin`, `tokenizer.json` and
`vocabulary.*`. After the snapshot is present, the transcription cell loads the
model from that local snapshot with `local_files_only=True`; inference therefore
does not need Hugging Face access.

Current repository mappings are:

- `large-v3` -> `Systran/faster-whisper-large-v3`;
- `turbo` -> `mobiuslabsgmbh/faster-whisper-large-v3-turbo`.

The token improves authenticated Hub access and avoids anonymous-request rate
limits, but it is not treated as a guarantee of higher network bandwidth. The
persistent cache is the primary cost-control mechanism because it makes the
large model artifact reusable after the first successful download.

## Base environment decision

For the serverless CPU pilot, a Databricks **Standard v6** base environment is
sufficient when `faster-whisper` is added and shown as installed in Dependencies.
The **ML** base environment is also compatible but is not required merely to run
`faster-whisper` on CPU. Selecting an ML base environment does not itself provide
a GPU. A GPU route is present only when Databricks exposes a Serverless GPU /
Accelerator option or an authorised classic GPU compute resource.

The notebook therefore must not assume `device='cuda'`. Its runtime selection is:

```text
visible NVIDIA GPU -> device=cuda, compute_type=float16
no visible GPU     -> device=cpu,  compute_type=int8
```

This follows faster-whisper/CTranslate2 supported execution modes while keeping
one governed quality-pilot notebook for both environments.

## Quality acceptance

Review difficult and clear timestamped excerpts from each of the three audio
files by listening. Compare critical facts first: vessel/call sign, position,
coordinates, numbers, distress, instructions, negations, speaker and chronology.
Mark unintelligible spans explicitly. Count critical errors and word error rate
on the *same* manually transcribed excerpts. Record reviewer, reference text,
disagreements and resolution separately; use a second reviewer for disputed
critical passages. Compare the elapsed and billed compute for both models.
Select `turbo` only if it is no worse on critical facts; otherwise choose
`large-v3`. Do not treat model confidence as verified testimony or use an LLM
to fill missing words. No quality claim is made before this review is run.

## Interface changes

The app sidebar starts collapsed. In Findings & Evidence, the Source page
viewer in `All` and every other category starts closed and downloads its PDF
only when opened. The full report control remains inside the opened viewer.

## Pending

- Complete the authenticated persistent `large-v3` model download and controlled
  single-file smoke test; record download/inference timing and billed usage.
- Run the controlled model comparison; record model versions, review results and
  billed usage.
- Select one model, then map reviewed Whisper segments to the governed Type D
  audio/transcript tables and notebook 39 evidence contract without fabricated
  PDF page numbers.
- Validate access and audit boundaries across source audio, transcripts,
  queries, extracted evidence and exports before enabling the app workflow.
- After the pilot, move model binaries to a dedicated governed model-artifact
  Volume and pin the accepted model snapshot/revision for reproducibility.

## App handoff (September 2026)

The Transcriptions tab reads notebook 61's pilot JSON results only for identities
listed in the app environment variable `TYPE_D_TRANSCRIPT_REVIEWERS` (comma
separated email/username). An empty list denies all access. The Databricks App
service identity must have `READ VOLUME` on `investigation_sources`. The
transcription job's run-as identity requires `READ VOLUME` for the audio and
`WRITE VOLUME` for the pilot output. The end user does not need `WRITE VOLUME`.
Unity Catalog Volume permissions apply at Volume scope, not to the output
subfolder; check inherited grants before storing protected content there.

In the app, the reviewer compares model output with the original audio, edits
unclear passages, and explicitly confirms that listening and checking are
complete. The source audio SHA-256 is verified before this action is enabled.
Machine and edited TXT downloads are available to the same allowlisted user.
The confirmation stores a review audit node with source/model/reviewed-text
hash, reviewer and time (no transcript content) in Neo4j. The approved text
then prefills **Analyse Documents → Direct text**, forces Class D, and the
analysis is linked to its review record before the existing Class D job starts.
If the user changes that text before submission, the app requires a new review.
This uses the existing encrypted direct-text ingress and its retention policy.

The pilot file and original audio are retained in the Volume under its actual
permissions. Downloading TXT creates a copy outside IKF's control, so export
policy and recipients require operational review. The app still warns that the
Class D direct-text transient-storage path needs approval for operational use.
No deployment or runtime verification was performed by the code change.

### Execution order and cost

1. Check Volume grants and configure the allowlist; create/authorise the output
   directory. Do not expand grants merely to run the pilot.
2. Create the read-only Hugging Face token as Unity Catalog secret
   `bdw_analysis_prod.kg_poc.huggingface_read_token`. Never place the token in
   notebook code, GitHub, transcript metadata or App configuration unless the
   App later has a separate approved need for it.
3. If Serverless GPU is unavailable and the user cannot create classic compute,
   use serverless CPU. Select **Standard v6** and confirm `faster-whisper` is
   shown as installed. Keep standard/16-GB memory unless a reproducible memory
   failure proves a larger setting is required.
4. Pull the current `main` version of notebook 61. It automatically selects
   CPU/INT8 when no GPU is visible.
5. Run only the preflight. Confirm `device: cpu`, `compute_type: int8`, cache
   write access and `hf_token_configured: True`.
6. Run the model-preparation cell. It downloads/reuses the selected model in the
   persistent Volume cache and must print `MODEL READY` before inference.
7. Run the controlled single-file transcription cell with `SMOKE_TEST = True`.
   Do not expand to the full comparison until this completes successfully.
8. Inspect results in the app, review audio/text, compare critical-field errors
   and elapsed/billed compute; select the model.
9. If a governed GPU route later becomes available, repeat the selected validation
   subset on CUDA/FP16 and compare critical-field quality and execution cost.
10. Pin model/package revisions, implement governed Type D table persistence and
    downstream timestamp evidence binding for reusable production ingestion.
