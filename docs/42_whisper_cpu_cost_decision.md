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

## Duration correction

The first duration-probe implementation contained a PyAV unit-conversion error. `container.duration` is expressed in AV_TIME_BASE units and must be divided by `av.time_base`; the notebook multiplied instead, producing the impossible value `815700000000000.0` seconds.

The corresponding source duration is approximately **815.7 seconds (13 minutes 35.7 seconds)**. Notebook 61 has been corrected to divide by `av.time_base`, print both seconds and minutes, and retain the stream-time-base fallback.

This changes the interpretation of the stopped `large-v3` run. Exceeding 15 minutes for ~13.6 minutes of audio implies a lower-bound RTF of only about **1.10**, not the extreme slowdown initially suspected. Because the run was stopped before completion, this remains a lower bound rather than a completed benchmark result.

## Cost decision

Do not increase notebook memory from 16 GB to 32 GB solely to improve transcription speed.

Databricks high-memory serverless increases available memory but has a higher DBU emission rate. It does not, by itself, add CPU cores. No out-of-memory error or measured memory constraint has been observed in this pilot. The current CPU route therefore remains the appropriate baseline until there is evidence that memory, rather than CPU inference throughput, is the limiting resource.

Use 32 GB only if one of the following is observed:

1. an explicit out-of-memory failure;
2. reproducible memory pressure that prevents stable model execution;
3. measured evidence that the higher-memory tier also changes effective compute in the specific workspace and reduces total billed cost enough to justify the higher DBU rate.

## Turbo preparation result

The same governed persistent-cache path was then used to prepare `turbo`.

Observed result:

- model: `turbo`;
- repository: `mobiuslabsgmbh/faster-whisper-large-v3-turbo`;
- preparation elapsed: **10.78 seconds**;
- persistent snapshot revision: `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`;
- local snapshot path: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`.

This confirms that the authenticated persistent-cache design is working for both candidate models and keeps repeat model-preparation overhead low.

## Next controlled test

The next smoke test keeps the same source audio and runs `turbo` only.

Notebook 61:

- uses the corrected source duration of approximately 815.7 seconds;
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

1. `turbo` transcription elapsed time and RTF;
2. human quality assessment of the same recording;
3. Databricks billing attribution where available.

Then compare `turbo` against the large-v3 baseline. Since large-v3 was stopped before completion, rerun it to completion only if its likely quality advantage justifies obtaining an exact benchmark after the turbo result is available.

Only then decide whether the production candidate should be:

- `turbo` on serverless CPU;
- `large-v3` on serverless CPU;
- `large-v3` on a governed on-demand GPU route;
- or another validated configuration.

The persistent cache remains part of the cost-control design so model artifacts are not repeatedly downloaded across serverless sessions.
