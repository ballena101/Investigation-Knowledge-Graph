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

## Correct source duration

The first duration-probe implementation contained a PyAV unit-conversion error. `container.duration` is expressed in AV_TIME_BASE units and must be divided by `av.time_base`; the notebook multiplied instead, producing the impossible value `815700000000000.0` seconds.

The corrected source duration is **815.7 seconds (13 minutes 35.7 seconds)**.

This changes the interpretation of the stopped `large-v3` run. Exceeding 15 minutes for 815.7 seconds of audio implies a lower-bound RTF of approximately **1.103**, not the extreme slowdown initially suspected. Because the run was stopped before completion, this remains a lower bound rather than a completed benchmark result.

## Memory decision

Do not increase notebook memory from 16 GB to 32 GB solely to improve transcription speed.

Databricks high-memory serverless increases available memory but has a higher DBU emission rate. It does not, by itself, add CPU cores. No out-of-memory error or measured memory constraint has been observed in this pilot. The current CPU route therefore remains the appropriate baseline until there is evidence that memory, rather than CPU inference throughput, is the limiting resource.

Use 32 GB only if one of the following is observed:

1. an explicit out-of-memory failure;
2. reproducible memory pressure that prevents stable model execution;
3. measured evidence that the higher-memory tier also changes effective compute in the specific workspace and reduces total billed cost enough to justify the higher DBU rate.

## Turbo preparation result

The same governed persistent-cache path was used to prepare `turbo`.

Observed result:

- model: `turbo`;
- repository: `mobiuslabsgmbh/faster-whisper-large-v3-turbo`;
- preparation elapsed: **10.78 seconds**;
- persistent snapshot revision: `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`;
- local snapshot path: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`.

This confirms that the authenticated persistent-cache design is working and keeps repeat model-preparation overhead low.

## Completed turbo transcription benchmark

The one-file `turbo` smoke test completed successfully on the same Standard v6 / 16 GB / 4-logical-CPU / CPU-INT8 route.

Observed notebook output:

- source: `19970212-090-sv-gale-runner-mayday-call.wav`;
- source duration: **815.7 seconds**;
- transcription elapsed: **696.13 seconds** (approximately **11 minutes 36 seconds**);
- real-time factor: **0.8534**;
- result: `DONE`;
- output: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts/10915255195ae92e16c44ed93befdf5e45846e5d3dff5bb37f2c464d5d04cca0__turbo.json`.

Interpretation:

- RTF 0.8534 means the CPU route completed approximately **14.7% faster than real time**;
- the `turbo` run completed at least about **22.6% faster** than the stopped `large-v3` observation at 15 minutes, because 15 minutes is only a lower bound for the incomplete `large-v3` run;
- model preparation is no longer the bottleneck because the governed snapshot is cached and reusable;
- on measured runtime alone, `turbo` is the current **provisional cost/performance winner** for the 4-CPU serverless route.

This is not yet a production-model decision. Runtime/cost is only one axis.

## Quality gate before expansion

Do not run the full three-file/two-model matrix yet.

The completed `turbo` transcript must first be inspected against the authoritative audio, with targeted human listening for safety-critical fields including:

- vessel and call sign;
- coordinates, times and other numbers;
- distress wording and urgency;
- instructions and acknowledgements;
- negation;
- chronology;
- speaker attribution;
- omissions or hallucinated content in noisy/overlapping sections.

The JSON output should also be checked for the expected provenance fields, model identity, source hash, language metadata, segment timestamps and completion status without rerunning inference.

If `turbo` quality is acceptable, keep Standard v6 / 16 GB / CPU-INT8 as the provisional operating route and proceed to one additional representative recording before any broader batch processing.

If quality is materially insufficient, obtain a completed `large-v3` benchmark on the same file only if the likely quality gain justifies the extra compute. Do not move to 32 GB merely for speed. A governed on-demand GPU comparison should be considered only after CPU quality/runtime evidence shows that higher-quality inference is required and CPU throughput is the limiting factor.

## Current decision

Current provisional ranking after the completed smoke test:

1. **`turbo` on Standard v6 CPU/INT8** — measured RTF 0.8534; preferred cost/performance candidate pending quality validation.
2. **`large-v3` on Standard v6 CPU/INT8** — quality-reference candidate; incomplete runtime observation >15 minutes, lower-bound RTF >1.103.
3. **32 GB serverless** — not justified at present; no memory-pressure evidence.
4. **GPU route** — deferred until a demonstrated quality requirement justifies it.

The persistent cache remains mandatory for the pilot so model artifacts are not repeatedly downloaded across serverless sessions.
