# NVIDIA Parakeet ASR integration

## Decision

The investigation application supports NVIDIA Parakeet TDT 0.6B v3 as a second, independent automatic-speech-recognition (ASR) technology alongside faster-whisper.

Whisper large-v3-turbo remains the default because it has already been exercised on the current 16 GB / 4 logical CPU Databricks serverless environment and has broader language coverage. Parakeet is introduced to provide model/architecture diversity and a controlled second opinion on difficult audio.

This change does not alter the Type-D governance boundary. Machine transcripts from either engine remain `MACHINE_GENERATED_UNVERIFIED` until a person listens to the original recording, corrects the transcript and explicitly accepts it.

## Technologies

### Whisper route

- runtime: `faster-whisper==1.2.1` / CTranslate2;
- models: large-v3-turbo (default), large-v3;
- persistent cache: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper`;
- existing CPU route uses INT8 when CUDA is unavailable.

### Parakeet route

- model: `nvidia/parakeet-tdt-0.6b-v3`;
- architecture family: FastConformer + TDT transducer;
- runtime integration: Hugging Face Transformers `automatic-speech-recognition` pipeline;
- pinned integration version: `transformers==5.17.0`;
- persistent cache: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/parakeet`;
- model weights are approximately 2.5 GB;
- no NVIDIA NeMo runtime is required for the App integration.

The official model publishes support for 25 languages: `en, es, fr, de, bg, hr, cs, da, nl, et, fi, el, hu, it, lv, lt, mt, pl, pt, ro, sk, sl, sv, ru, uk`. Norwegian and Icelandic are therefore not offered as supported Parakeet languages; Whisper remains the appropriate route for them.

## App behaviour

The Audio transcription workspace offers:

1. Whisper large-v3-turbo;
2. NVIDIA Parakeet TDT 0.6B v3;
3. Whisper large-v3 as the slower Whisper reference.

An optional `Also run the independent Whisper / Parakeet comparison` control queues the second ASR engine on the same source audio. The two machine outputs remain separate. The application does not merge them, vote between them or infer a consensus transcript.

When both machine outputs exist, the App shows a compact comparison of runtime, real-time factor and detected language where available. The investigator switches the engine/model selector to inspect each transcript.

Only one reviewed/corrected transcript is accepted and published as the normal Class-D `SourceDocument` used by Analyse Documents.

## Provenance

Machine transcript JSON now records:

- engine;
- engine version;
- model identifier/repository;
- device;
- compute type;
- elapsed time;
- real-time factor;
- source hash;
- source duration;
- segments/timestamps where the runtime provides them;
- workflow version.

The accepted SourceDocument preserves the selected transcript model and transcription engine in addition to the existing source-audio provenance and human review identity.

## Cost control

The Lakeflow transcription Job remains unscheduled, serverless, maximum concurrency 1 and retries 0. Comparison mode can therefore queue two runs but does not create parallel compute by design.

The Parakeet cache is persistent so model weights should not need to be downloaded on every run after the first successful preparation.

## Validation gate before production-equivalent use

Notebook `66_compare_whisper_parakeet_audio.py` is the controlled validation route. It limits a benchmark window to a maximum of 180 seconds and compares:

- faster-whisper large-v3-turbo;
- NVIDIA Parakeet TDT 0.6B v3.

Review should explicitly consider:

- vessel names and callsigns;
- numbers, coordinates and times;
- maritime/radio terminology;
- omissions;
- hallucinations in noise/silence;
- timestamp usefulness;
- elapsed time and real-time factor;
- memory/runtime stability on the existing serverless profile.

Parakeet should remain labelled an alternative/experimental ASR route until this controlled runtime and quality validation is completed on representative maritime audio.

## External-tool disclosure

The App disclaimer identifies Whisper/faster-whisper and NVIDIA Parakeet/Transformers as external software/model dependencies. Their licences, availability and outputs are governed by their respective providers/projects. This does not remove responsibility for the configuration, integration, access controls and governance implemented in this application.
