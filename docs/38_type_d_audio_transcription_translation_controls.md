# Type D audio transcription and translation controls

Date: 2026-09-23
Status: Architecture / governance rule for IKF

## Purpose

Apply the existing IKF Type D / Article 9 protection model to speech-to-text and translation without creating a second confidentiality regime.

## Baseline rule

All audio designated Type D remains Type D throughout every derivative processing step:

`Type D audio -> Type D transcript -> Type D translated transcript -> Type D evidence / model output / graph candidate`

No transcription or translation step may downgrade the source classification, broaden access, publish the content, or move the material into the MAIRA public-document corpus.

## ai_transcribe

Databricks documents that `ai_transcribe()` processes audio within the Databricks security perimeter and does not store the parameters supplied to the AI function call, while retaining operational metadata such as runtime-version information.

IKF decision:

- `ai_transcribe()` is acceptable as the initial Type D speech-to-text route, subject to the same Unity Catalog permissions and purpose limitation already applied to Type D documents.
- Original audio remains the source record.
- Transcript segments are derived evidence and remain Type D.
- Each segment must retain the source audio identifier/hash, start/end timestamp, speaker label when available, transcription engine/function, processing time, and transcript text.
- Transcript access must inherit the source Type D access boundary.

## ai_translate

Databricks documents that `ai_translate()` uses Databricks Foundation Model APIs. Foundation Model API inputs and outputs may be temporarily processed and stored for security/abuse-prevention purposes for up to 30 days, isolated from other customers and stored in the same region as the workspace.

IKF decision for the Article 9-by-design baseline:

- Do not automatically enable `ai_translate()` for Type D material.
- Translation of Type D transcripts remains gated until the organisation explicitly accepts the applicable Foundation Model API retention and processing terms for protected investigation material, or a translation route is selected that removes that retention path.
- If/when enabled, the translated text remains Type D and must never replace the original-language transcript.
- The original-language transcript remains the evidential reference; translation is a derived working aid.

## Purpose limitation

Type D audio and derivatives may only be processed within the authorised safety-investigation purpose and existing IKF access model. They must not automatically be exposed to:

- public dashboards;
- the general MAIRA public corpus;
- unrestricted cross-case retrieval;
- external publication workflows;
- users without the same Type D authorisation.

## Implementation order

1. Reuse existing Type D document permissions/classification logic.
2. Add Type D audio ingestion.
3. Add `ai_transcribe()` only.
4. Preserve timestamps, speaker labels and provenance.
5. Validate output quality and access inheritance.
6. Keep Type D `ai_translate()` disabled until the retention/processing gate is explicitly cleared.

## Design objective

IKF is to operate to the amended Article 9 protection standard now, ahead of national transposition deadlines, rather than defer the protection boundary until 2027.
