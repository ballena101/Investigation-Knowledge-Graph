# Whisper CPU cost decision — 24 September 2026

## Observed state

Notebook `61_compare_whisper_type_d_audio.py` is running on Databricks serverless Standard v6 with:

- standard notebook memory: 16 GB;
- 4 logical CPUs;
- no visible CUDA device;
- faster-whisper 1.2.1;
- CPU / INT8 inference;
- governed source/output paths in `bdw_analysis_prod.kg_poc.investigation_sources`;
- authenticated Hugging Face read-only access via Unity Catalog secret;
- persistent model cache under `_model_cache/faster_whisper`.

The authenticated `large-v3` snapshot preparation completed successfully in 32.39 seconds and was persisted at snapshot revision:

`edaa852ec7e145841d8ffdb056a99866b5f0a478`

A subsequent `large-v3` transcription of the first smoke-test recording exceeded 15 minutes on the 4-CPU serverless route and was stopped before completion. No successful `large-v3` transcript/runtime result is claimed from that run.

## Cost decision

Do not increase notebook memory from 16 GB to 32 GB solely to improve transcription speed.

Databricks documents high-memory serverless as a response to out-of-memory conditions. High memory increases REPL memory from 16 GB to 32 GB and has a higher DBU emission rate. It does not, by itself, add CPU cores. The observed bottleneck is therefore treated as CPU/inference throughput unless a later run shows a reproducible memory constraint.

Use 32 GB only if one of the following is observed:

1. an explicit out-of-memory failure;
2. reproducible memory pressure that prevents stable model execution;
3. measured evidence that the higher-memory tier also changes available compute in the specific workspace and reduces total billed cost enough to justify the higher DBU rate.

## Next controlled test

The next smoke test keeps the same source audio and changes only the Whisper model from `large-v3` to `turbo`.

Notebook 61 now:

- probes source audio duration from container metadata before inference;
- prepares/reuses the persistent `turbo` snapshot using the same read-only Hugging Face secret;
- transcribes only `19970212-090-sv-gale-runner-mayday-call.wav` while `SMOKE_TEST=True`;
- records transcription elapsed seconds;
- calculates real-time factor (RTF):

`RTF = transcription elapsed seconds / source audio seconds`

Interpretation:

- RTF < 1: faster than real time;
- RTF = 1: approximately real time;
- RTF > 1: slower than real time.

Runtime/cost is not sufficient for model selection. The `turbo` transcript must still be checked against the audio for safety-critical fields, including vessel/call sign, coordinates/numbers, distress wording, instructions, negation, chronology and speaker attribution.

## Operating rule

Do not run the full three-file/two-model matrix yet.

First obtain:

1. source duration for the smoke file;
2. `turbo` model-preparation elapsed time;
3. `turbo` transcription elapsed time and RTF;
4. human quality assessment of the same recording;
5. Databricks billing attribution where available.

Only then decide whether the production candidate should be:

- `turbo` on serverless CPU;
- `large-v3` on a governed on-demand GPU route;
- or another validated configuration.

The persistent cache remains part of the cost-control design so model artifacts are not repeatedly downloaded across serverless sessions.
