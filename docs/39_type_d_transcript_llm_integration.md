# Type D transcript → existing IKF LLM integration

Date: 2026-09-23

## Decision

A speech-to-text transcription derived from Type D audio is treated as a **Type D document-like evidence source** inside IKF. It is not a lower classification and does not create a separate analytical regime.

The governed chain is:

```text
TYPE_D audio
  → Databricks ai_transcribe()
  → TYPE_D transcript segments
  → analysis_passage compatibility contract
  → existing Type D LLM analysis (notebook 16)
  → human review
  → validated graph / downstream taxonomy workflow
```

Every derivative remains Type D unless an authorised human-controlled disclosure/reclassification process explicitly establishes otherwise.

## Implementation

Notebook:

`notebooks/39_bind_type_d_transcript_to_analysis.py`

The notebook takes:

- an existing IKF `analysis_id` already classified as `D` / `TYPE_D`;
- a persisted `transcription_run_id` created by notebook 38.

It fails closed unless both the destination analysis and every source/segment are Type D.

## Evidence mapping

The existing LLM analysis stage consumes `bdw_analysis_prod.kg_poc.analysis_passage`. Transcript segments are therefore adapted to that same evidence contract rather than creating a second LLM pipeline.

| Transcript field | Existing IKF evidence field |
|---|---|
| `audio_source_id` | `document_id` |
| `transcript_segment_id` | `passage_id` |
| segment order | `passage_order` |
| exact transcript text | `passage_text` |
| segment SHA-256 | `text_sha256` |
| Type D audio binding version | `extraction_version` |

`page_start` and `page_end` remain NULL. IKF must not fabricate page numbers for audio material.

## Timestamp provenance

Timestamp and speaker provenance remains in:

`bdw_analysis_prod.kg_poc.type_d_transcript_segment`

and is joined by:

`analysis_passage.passage_id = type_d_transcript_segment.transcript_segment_id`

This preserves:

- start timestamp;
- end timestamp;
- speaker ID where available;
- source audio identity and hash;
- transcription run identity;
- Type D classification;
- human-review status.

The timestamp is the authoritative source locator for audio-derived evidence, analogous to a page reference for documentary evidence.

## LLM behaviour

No new LLM model or analytical algorithm is introduced. Once the binding is persisted and the AnalysisGroup is marked `EVIDENCE_READY`, notebook 16 reads the transcript passages through the same governed evidence interface used for Type D documents.

This means existing:

- model endpoint controls;
- candidate extraction;
- evidence-class rules;
- human review boundary;
- graph-validation flow;
- SHIELD post-validation boundary;

continue to apply.

## Safety / Article 9-by-design boundary

The adapter does not:

- translate the transcript;
- publish transcript content;
- downgrade Type D;
- copy the evidence into MAIRA's public investigation-report corpus;
- write validated knowledge directly to Neo4j;
- bypass human review.

The transcript is simply another Type D evidence source available to the existing controlled IKF analytical workflow.

## Execution sequence

1. Run notebook 38 against one controlled English or Spanish Type D audio file with preview first.
2. Persist the approved transcription in the governed Type D audio/transcript tables.
3. Create or select an IKF AnalysisGroup already classified as Type D.
4. Run notebook 39 with `persist=false` and inspect the evidence mapping.
5. Run notebook 39 with `persist=true` to mark the transcript evidence `EVIDENCE_READY`.
6. Run the existing notebook 16/model workflow against that `analysis_id`.
7. Human-review model candidates before validated knowledge or SHIELD classification is produced.

## Current UI follow-up

The analytical integration is complete at the evidence-contract level. The application source-reference renderer should next display transcript references as time ranges (for example `00:12:14–00:12:29 · Speaker 2`) instead of the document-oriented fallback `page unknown`. The underlying timestamp provenance is already preserved and available for that rendering step.
