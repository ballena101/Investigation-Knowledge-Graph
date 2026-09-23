# Type D audio evidence references and end-to-end validation

Date: 2026-09-23

## Purpose

This change completes the evidence-location layer for Type D audio transcripts without creating a separate LLM-analysis pipeline.

The existing IKF LLM pipeline continues to consume `bdw_analysis_prod.kg_poc.analysis_passage`. Audio transcript segments are bound to that contract by notebook 39. Notebook 40 adds a canonical source-reference resolver so the application can present timestamp/speaker references for audio and page references for documents.

## Canonical resolver

Notebook:

`notebooks/40_type_d_audio_reference_and_chain_validation.py`

Creates or refreshes:

`bdw_analysis_prod.kg_poc.analysis_evidence_reference`

The view resolves each `analysis_passage.passage_id` as follows:

- normal document passage → `p. N` or `pp. N–M`;
- Type D audio transcript passage → `HH:MM:SS–HH:MM:SS · Speaker X` when a speaker ID is available.

The transcript text itself remains unchanged. Timestamps and speaker information remain provenance metadata linked by `passage_id = transcript_segment_id`.

## Type D inheritance

For audio-derived rows, the resolver exposes the source classification from `type_d_transcript_segment`. Notebook 40 fails closed if any bound transcript passage is not `TYPE_D`, if timestamps are missing/invalid, or if a source reference cannot be rendered.

The Type D chain therefore remains:

`Type D audio → Type D transcript → Type D analysis passage → existing Type D LLM workflow → human review → validated graph/SHIELD workflow`

No classification downgrade is introduced at the transcription or evidence-binding stage.

## Downstream LLM traceability

When `analysis_candidate` and/or `analysis_candidate_relationship` rows already exist for the analysis, notebook 40 explodes their `passage_ids` and verifies that every cited passage still resolves through the canonical evidence-reference view.

A PASS therefore means that downstream LLM evidence identifiers can still be traced back to the protected source location. For audio this means an exact timestamp range and speaker where available.

## Cost and side effects

Notebook 40 does not:

- invoke `ai_transcribe()`;
- call an LLM;
- call `ai_translate()`;
- write to Neo4j;
- publish protected content;
- alter the document evidence pipeline.

The only persistent object it may create is the SQL view `analysis_evidence_reference`.

## Controlled validation sequence

For the first audio test use:

1. Notebook 38 — transcribe one controlled English/Spanish Type D audio file with `PERSIST=False` first; review transcript quality.
2. Notebook 38 — rerun with persistence only after review.
3. Notebook 39 — bind that persisted transcription to an existing Type D analysis, preview first and then persist.
4. Notebook 16 — run the existing Type D LLM analysis without any audio-specific LLM code.
5. Notebook 40 — validate Type D inheritance, timestamp/speaker traceability and resolution of all LLM-cited passage IDs.

The application should use `analysis_evidence_reference.source_reference` instead of assuming every evidence item has a page number.
