# NVIDIA Parakeet ASR integration

## Decision

The investigation application supports NVIDIA Parakeet TDT 0.6B v3 as a second, independent automatic-speech-recognition (ASR) technology alongside faster-whisper.

Whisper large-v3-turbo remains the default because it has already been exercised on the current 16 GB / 4 logical CPU Databricks serverless environment and has broader published language coverage. Parakeet is introduced to provide model/architecture diversity and a controlled second opinion on difficult audio.

This change does not alter the Type-D governance boundary. Machine transcripts from either engine remain `MACHINE_GENERATED_UNVERIFIED` until a person listens to the original recording, corrects the transcript and explicitly accepts it.

## Capability comparison

The application distinguishes **published capability** from **IKF-observed performance**. Published model specifications are not treated as evidence of runtime performance on the IKF Databricks environment.

| Characteristic | Whisper large-v3-turbo | NVIDIA Parakeet TDT 0.6B v3 |
|---|---|---|
| ASR family | Whisper encoder-decoder Transformer | FastConformer + Token-and-Duration Transducer (TDT) |
| Published language coverage | 99 languages | 25 European languages |
| Reference model-weight file | about 1.62 GB for the OpenAI safetensors checkpoint | about 2.51 GB safetensors; about 0.6B parameters |
| IKF runtime | faster-whisper 1.2.1 / CTranslate2 | Transformers 5.17.0 |
| IKF CPU status | validated on 16 GB / 4 logical CPU | controlled runtime validation pending |
| IKF observed performance | 815.7 s audio in 696.13 s; RTF 0.8534 with large-v3-turbo | not yet measured in the IKF environment |
| IKF role | default / broad-language route | independent alternative / comparison route |

Weight-file size is **not** equivalent to runtime RAM, CPU consumption or Databricks cost. Runtime and cost decisions must be based on measured IKF executions.

### Parakeet published language set

Parakeet TDT 0.6B v3 publishes support for the following 25 languages:

`bg, hr, cs, da, nl, en, et, fi, fr, de, el, hu, it, lv, lt, mt, pl, pt, ro, sk, sl, es, sv, ru, uk`

That corresponds to Bulgarian, Croatian, Czech, Danish, Dutch, English, Estonian, Finnish, French, German, Greek, Hungarian, Italian, Latvian, Lithuanian, Maltese, Polish, Portuguese, Romanian, Slovak, Slovenian, Spanish, Swedish, Russian and Ukrainian.

Norwegian and Icelandic are not in the published Parakeet set. Whisper therefore remains the broad-language route and the required option when a source language is outside Parakeet's published coverage.

Published references checked on 24 September 2026:

- OpenAI Whisper large-v3-turbo model card / generation configuration: `https://huggingface.co/openai/whisper-large-v3-turbo`
- NVIDIA Parakeet TDT 0.6B v3 model card: `https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3`

## Technologies

### Whisper route

- runtime: `faster-whisper==1.2.1` / CTranslate2;
- models: large-v3-turbo (default), large-v3;
- persistent cache: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper`;
- existing CPU route uses INT8 when CUDA is unavailable;
- broad published language coverage (99 languages for Whisper large-v3-turbo).

### Parakeet route

- model: `nvidia/parakeet-tdt-0.6b-v3`;
- architecture family: FastConformer + TDT transducer;
- runtime integration: Hugging Face Transformers `automatic-speech-recognition` pipeline;
- pinned integration version: `transformers==5.17.0`;
- persistent cache: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/parakeet`;
- reference safetensors weights approximately 2.51 GB;
- approximately 0.6B parameters;
- no NVIDIA NeMo runtime is required for the App integration.

## App behaviour

The Audio transcription workspace offers:

1. Whisper large-v3-turbo;
2. NVIDIA Parakeet TDT 0.6B v3;
3. Whisper large-v3 as the slower Whisper reference.

An optional `Also run the independent Whisper / Parakeet comparison` control queues the second ASR engine on the same source audio. The two machine outputs remain separate. The application does not merge them, vote between them or infer a consensus transcript.

The App contains a compact **Transcription model capabilities** expander showing published language coverage, reference model footprint, IKF-observed runtime and validation status. It explicitly marks Parakeet performance as pending until runtime benchmark notebook 66 is completed.

When both machine outputs exist, the App shows a compact comparison of runtime, real-time factor and detected language where available. The investigator switches the engine/model selector to inspect each transcript.

Only one reviewed/corrected transcript is accepted and published as the normal Class-D `SourceDocument` used by Analyse Documents.

## Provenance

Machine transcript JSON records:

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

Both model caches are persistent so model weights should not need to be downloaded on every run after successful preparation.

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

Parakeet remains labelled an alternative route until this controlled runtime and quality validation is completed on representative maritime audio.

## Updating ASR models and LLMs

Model updates should be treated as governed software/model releases, not as automatic replacements of a production model.

The current architecture makes updates relatively contained because model identifiers, runtime versions and Databricks endpoint names are already separated from the review/evidence workflow. A future update therefore normally consists of:

1. detect a new candidate model/version;
2. download/cache or provision it without changing the active route;
3. run deterministic compatibility tests;
4. run the controlled benchmark set on frozen evidence/audio;
5. compare quality, latency, cost, supported languages and governance constraints;
6. require human approval to promote the candidate;
7. record the promoted version and retain rollback information.

### Automation potential

This lifecycle can be substantially automated in the future. The recommended pattern is **automatic detection and testing, manual promotion**.

A scheduled CI/Databricks workflow could:

- check configured Hugging Face repositories and Databricks serving endpoints for candidate revisions;
- compare model/revision hashes with the approved registry;
- create a candidate record when a change is detected;
- run static compatibility tests automatically;
- optionally run a small frozen benchmark suite under a strict cost ceiling;
- calculate quality/runtime/cost deltas;
- produce a promotion report;
- notify an authorised reviewer.

The workflow should **not automatically replace the active ASR or LLM solely because a newer release exists**. Investigation use requires regression testing, provenance and an explicit approval gate.

### Complexity

- **ASR checkpoint/version update within an existing engine:** low-to-moderate complexity. Most changes are model identifier, cache revision and benchmark validation.
- **New ASR architecture/runtime:** moderate complexity because transcript/timestamp outputs and dependencies may differ.
- **Databricks-served LLM version/end-point update:** low-to-moderate if the prompt/output contract remains compatible; model-specific regression is still required.
- **New LLM family or changed structured-output behaviour:** moderate complexity because extraction/relationship benchmark behaviour must be revalidated.
- **Fully automated detection + benchmark + approval report:** moderate implementation effort and realistic with GitHub Actions plus Databricks Jobs.
- **Fully autonomous promotion with no human approval:** technically possible but not recommended for this investigation system.

A future central `model_registry` should hold the approved model id, provider, revision/hash, runtime, supported information classes, language scope, benchmark result, approval state, activation date and rollback target. That would remove model names from scattered code and make upgrades materially simpler.

## External-tool disclosure

The App disclaimer identifies Whisper/faster-whisper and NVIDIA Parakeet/Transformers as external software/model dependencies. Their licences, availability and outputs are governed by their respective providers/projects. This does not remove responsibility for the configuration, integration, access controls and governance implemented in this application.
