# Type D Whisper quality pilot and interface defaults

## Decision and scope

AI Transcribe Preview is not enabled in the workspace. Notebook
`61_compare_whisper_type_d_audio.py` compares faster-whisper `large-v3` and
`turbo` on the three existing recordings. Number 40 was already used; the
current repository has notebooks through 60. This pilot is not an unattended
production ingestion route. It does not call notebook 39 or mark an analysis
`EVIDENCE_READY`. Existing notebooks 38/39 assume `ai_transcribe()` output;
the adapter for Whisper output must be reviewed and implemented separately.

## Controlled execution

Create `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts`
with access limited to authorized Type D reviewers. Run notebook 61 manually
with a single on-demand GPU worker, automatic termination and `faster-whisper`
installed in the job environment. No always-on endpoint is needed. The pilot
records a SHA-256 audio identity, model and decoding parameters, timestamps,
language estimate and elapsed time per file. Existing output is skipped by
source hash and model name. The source audio remains the authoritative record.

Before production use, pin dependency/model revisions and ensure the output
directory is restricted. Never commit source audio or transcripts to GitHub.
Do not expose output in public notebook results, logs or app surfaces. The
Type D access and retention owner must confirm the controls for protected
statements, identities, derivative records, disclosure and deletion under
Article 9 and applicable national rules.

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

- Run the controlled pilot; record model versions, review results and billed usage.
- Select one model, then map reviewed Whisper segments to the governed Type D
  audio/transcript tables and notebook 39 evidence contract without fabricated
  PDF page numbers.
- Validate access and audit boundaries across source audio, transcripts,
  queries, extracted evidence and exports before enabling the app workflow.
