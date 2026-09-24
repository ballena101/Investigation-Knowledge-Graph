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

## App handoff (September 2026)

The Transcriptions tab reads notebook 61's pilot JSON results only for identities
listed in the app environment variable `TYPE_D_TRANSCRIPT_REVIEWERS` (comma
separated email/username). An empty list denies all access. The Databricks App
service identity must have `READ VOLUME` on `investigation_sources`. The
transcription job's run-as identity requires `READ VOLUME` for the audio and
`WRITE VOLUME` for the pilot output. The end user does not need `WRITE VOLUME`.
Unity Catalog Volume permissions apply at Volume scope, not to the output
subfolder; check inherited grants before storing protected content there.

In the app, the reviewer compares model output with the original audio, edits
unclear passages, and explicitly confirms that listening and checking are
complete. The source audio SHA-256 is verified before this action is enabled.
Machine and edited TXT downloads are available to the same allowlisted user.
The confirmation stores a review audit node with source/model/reviewed-text
hash, reviewer and time (no transcript content) in Neo4j. The approved text
then prefills **Analyse Documents → Direct text**, forces Class D, and the
analysis is linked to its review record before the existing Class D job starts.
If the user changes that text before submission, the app requires a new review.
This uses the existing encrypted direct-text ingress and its retention policy.

The pilot file and original audio are retained in the Volume under its actual
permissions. Downloading TXT creates a copy outside IKF's control, so export
policy and recipients require operational review. The app still warns that the
Class D direct-text transient-storage path needs approval for operational use.
No deployment or runtime verification was performed by the code change.

### Execution order and cost

1. Check Volume grants and configure the allowlist; create the output directory
   using an authorised job identity. Do not expand grants merely to run the pilot.
2. Configure notebook 61 as an unscheduled on-demand GPU job with a timeout,
   no retries and `faster-whisper` installed; run one comparison on three files.
3. Inspect results in the app, review audio/text, compare critical-field errors
   and elapsed/billed compute; select the model.
4. Pin model/package revisions, implement governed Type D table persistence and
   downstream timestamp evidence binding for reusable production ingestion.
