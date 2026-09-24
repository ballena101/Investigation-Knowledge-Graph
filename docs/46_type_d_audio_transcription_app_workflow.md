# IKF Type D Audio Transcription App Workflow

## Purpose

Type D audio transcription is a single governed workflow inside the IKF App:

```text
select governed audio
        ↓
transcribe
        ↓
processing status
        ↓
machine transcript (unverified)
        ↓
listen + correct + validate
        ↓
accept
        ↓
validated Class D SourceDocument
        ↓
normal Analyse Documents workflow
```

There is deliberately **no duplicate audio-analysis panel** in Analyse Documents.
Once a transcript is accepted, it is simply another governed Class D document
and uses the same evidence extraction, LLM analysis, Findings & Evidence,
Timeline and Knowledge Graph pipeline as other documents.

## Audio selection

The Transcriptions capability lists supported direct-child audio files from:

`/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios`

Supported extensions are WAV, FLAC, MP3, M4A and OGG. Listing and playback use
the Databricks Files API with the logged-in user's forwarded token, matching the
existing MAIRA read-access pattern.

The audio itself is not registered as an ordinary SourceDocument merely because
it can be transcribed. The original recording remains the authoritative source
and is retained as provenance for the validated transcript.

## Processing

A transcription request creates an opaque `TranscriptionRun` in Neo4j. The App
then triggers the Lakeflow Job resource `transcription_job` with **Can manage
run** permission.

Only these Job parameters are used:

- `action`
- `transcription_run_id` for transcription, or
- `review_id` for publication.

Protected audio filenames/paths and reviewed transcript text are not sent as Job
parameters. The Job resolves them from governed metadata after it starts.

The transcription Job is named:

`Investigation KG - Type D Audio Transcription`

Its notebook entry point is:

`notebooks/65_type_d_audio_transcription_job.py`

The reusable worker is:

`src/ikf/transcription_worker.py`

## Whisper engine

Current implementation uses `faster-whisper==1.2.1` and supports:

- `turbo`
- `large-v3`

The existing persistent model cache is reused:

`/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper`

The Hugging Face read token remains the Unity Catalog secret:

- catalog: `bdw_analysis_prod`
- schema: `kg_poc`
- secret: `huggingface_read_token`

The worker selects CUDA/float16 if a GPU is actually visible; otherwise it uses
CPU/int8. The current PoC cost baseline remains serverless CPU/16 GB. No GPU or
32-GB route should be introduced solely by this App integration.

## Processing states and refresh placement

The Transcriptions screen keeps refresh controls beside the processing data.
There is no detached page-level refresh button.

Typical processing stages are:

- `NOT STARTED`
- `PENDING`
- `JOB_QUEUED`
- `PREPARING_SOURCE`
- `PREPARING_MODEL`
- `TRANSCRIBING`
- `MACHINE_TRANSCRIPT_READY`
- `HUMAN REVIEW REQUIRED`
- publication `PENDING` / `QUEUED` / `PUBLISHED` / `FAILED`
- `CLASS D DOCUMENT AVAILABLE`

Existing valid machine transcripts are reused rather than rerun. This allows the
Gale Runner turbo pilot result to enter the new review workflow without paying
for another transcription.

## Human review gate

Every machine transcript remains:

`MACHINE_GENERATED_UNVERIFIED`

The investigator must listen to the original recording, correct the text and
explicitly confirm the review. Critical words, identities, positions, numbers,
negations and maritime-radio phrases must be checked against the audio.

The reviewed text is encrypted with `DIRECT_TEXT_ENCRYPTION_KEY` before it is
persisted temporarily in the `TypeDTranscriptReview` record. Plain reviewed text
is not placed in a Lakeflow Job parameter.

The screen retains both exports:

- machine transcript TXT;
- reviewed transcript TXT.

## Acceptance and publication

On acceptance, the same Lakeflow Job publishes the human-reviewed text to:

`/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/validated_transcripts`

The persisted TXT hash is verified before catalogue publication.

The transcript is then registered as an ordinary Neo4j `SourceDocument` with:

- `source_type = TXT`
- `document_kind = TRANSCRIPT`
- `source_managed_by = IKF`
- `source_repository = IKF_TYPE_D_TRANSCRIPT`
- `information_class = D`
- `catalogue_status = AVAILABLE`
- reviewed-text SHA-256
- original audio name/path/SHA-256
- transcription model
- transcript review id/status
- validator identity/time
- transcription workflow version.

Explicit Class D catalogue metadata is enforced by `src/ikf/source_routing.py`:
a validated transcript cannot silently appear in Class A or C selectors.
Legacy IKF documents without an explicit class retain the existing ownership
routing for backward compatibility.

## Downstream analysis

After publication, no audio-specific analysis UI is used. The investigator opens
Analyse Documents, selects Class D, and the accepted transcript appears in the
same document selector as other governed Class D documents.

Because the physical source is TXT, the existing evidence extraction notebook
already supports it. The `document_kind=TRANSCRIPT` and audio provenance fields
preserve its semantic origin for later audio-timestamp evidence enrichment.

The normal downstream sequence is therefore:

```text
validated transcript SourceDocument
        ↓
Analyse Documents (Class D)
        ↓
existing Class D model route
        ↓
Findings & Evidence
        ↓
Timeline
        ↓
Knowledge Graph
        ↓
SHIELD only after the existing human-validation gate
```

## Access model

Two distinct access contexts are intentionally used:

1. **App read/browse/playback** — logged-in user's forwarded Databricks token,
   same principle as MAIRA Files API reads.
2. **Transcription/publication Job** — Lakeflow Job run-as identity, which must
   have the governed write and secret access needed by the worker.

This avoids granting the App service principal broad direct Volume read/write
permissions merely to implement transcription.

## App resource prerequisite

Before deployment of this version, create/identify the Lakeflow Job above and
add it to `investigation-kg-poc` App resources with:

- resource key: `transcription_job`
- permission: `Can manage run`

`app/app.yaml` exposes its ID as `TRANSCRIPTION_JOB_ID`.

The consolidated release preflight (`notebooks/55_validate_consolidated_release_preflight.py`)
now treats both the Job and the App resource as required prerequisites.

## Cost controls

- Selecting/listing audio causes no inference.
- Refreshing status causes no inference.
- Reviewing/exporting causes no inference.
- Acceptance/publication causes no model inference.
- A Whisper run occurs only when the user explicitly selects an audio/model and
  requests transcription, and an existing matching machine transcript is reused
  when valid.
- No new LLM call is required to make the validated transcript available as a
  Class D document.
