# Databricks notebook source
# MAGIC %md
# MAGIC # IKF Type D audio transcription — quality pilot
# MAGIC
# MAGIC Run manually as an on-demand job with a single GPU worker and automatic termination.
# MAGIC Install `faster-whisper` in the job environment. Pin package and model revisions after
# MAGIC the pilot. This notebook does not publish transcripts or modify the knowledge graph.
# MAGIC Place it in the IKF GitHub repository with this documentation; never commit audio/output.
# MAGIC The three source paths below are the recordings supplied for the initial quality comparison.
# MAGIC
# MAGIC Access: grant only the designated Type D reviewers permission to read the audio and
# MAGIC transcript folder. Audio and transcripts may contain protected witness statements,
# MAGIC identifying details and other Article 9 material. Confirm access/retention rules with
# MAGIC the competent owner before running. The source recording remains authoritative.

# COMMAND ----------

from pathlib import Path
import hashlib
import json
import os
import time
from datetime import datetime, timezone

from faster_whisper import WhisperModel

SOURCE_ROOT = Path('/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios')
# Create this restricted directory in the volume before running; do not use SHIELD or input documents.
OUTPUT_ROOT = Path('/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts')
FILES = (
    '19970212-090-sv-gale-runner-mayday-call.wav',
    'MV_Summit_Venture_Mayday_Call.flac',
    'Paul-Taverner-interview.mp3',
)
MODELS = ('large-v3', 'turbo')  # Compare both once; retain the chosen model for future runs.
COMPUTE_TYPE = 'float16'  # GPU; use int8_float16 if memory constrained and revalidate quality.


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


assert SOURCE_ROOT.is_dir(), 'Source volume is unavailable'
assert OUTPUT_ROOT.is_dir(), 'Create the restricted output directory and verify its permissions first'
assert all((SOURCE_ROOT / name).is_file() for name in FILES), 'One or more source files are missing'

for model_name in MODELS:
    model = WhisperModel(model_name, device='cuda', compute_type=COMPUTE_TYPE)
    for filename in FILES:
        source = SOURCE_ROOT / filename
        source_hash = sha256_file(source)
        destination = OUTPUT_ROOT / (source_hash + '__' + model_name + '.json')
        if destination.exists():
            print('SKIP existing', filename, model_name)
            continue
        start = time.monotonic()
        # Avoid aggressive VAD on short radio calls: it can discard faint speech.
        # Do not supply a context prompt that could bias names, coordinates or instructions.
        segments, info = model.transcribe(
            str(source), task='transcribe', beam_size=5,
            vad_filter=False, word_timestamps=False,
            condition_on_previous_text=False,
        )
        items = [
            {'start_s': round(s.start, 3), 'end_s': round(s.end, 3),
             'text': s.text, 'avg_logprob': s.avg_logprob,
             'no_speech_prob': s.no_speech_prob}
            for s in segments
        ]
        atomic_json(destination, {
            'classification': 'D', 'status': 'MACHINE_GENERATED_UNVERIFIED',
            'source_name': filename, 'source_sha256': source_hash,
            'source_path': str(source), 'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'engine': 'faster-whisper', 'model': model_name,
            'compute_type': COMPUTE_TYPE, 'beam_size': 5, 'vad_filter': False,
            'condition_on_previous_text': False,
            'detected_language': info.language, 'language_probability': info.language_probability,
            'duration_s': info.duration, 'elapsed_s': round(time.monotonic() - start, 2),
            'segments': items,
        })
        print('DONE', filename, model_name, 'duration_s', round(info.duration, 1),
              'elapsed_s', round(time.monotonic() - start, 1))
    del model

# COMMAND ----------

# MAGIC %md
# MAGIC ## Human quality gate and operating decision
# MAGIC
# MAGIC Compare each model against the *audio*, using selected clear and difficult passages
# MAGIC from all three files. Record timestamp, reviewer, verbatim reference transcription,
# MAGIC model output, and errors in vessel identity/call sign, position/coordinates, numbers,
# MAGIC distress description, instructions, negation, chronology and speaker attribution.
# MAGIC Mark inaudible speech as inaudible; never infer missing words from context or an LLM.
# MAGIC Compare critical-field error counts first, then word error rate on the same reviewed
# MAGIC passages, elapsed job time and billed compute. Include a second reviewer for disputed
# MAGIC safety-critical passages. Accept turbo only if its critical-field performance is no
# MAGIC worse on this set; otherwise retain large-v3. Neither model's confidence is a
# MAGIC substitute for listening. Keep human corrections in a separate versioned record.
# MAGIC
# MAGIC Only after a human review may a transcript enter the existing Type D document
# MAGIC pipeline. Carry source hash, time offsets and review status into retrieval and evidence.
# MAGIC Do not expose unreviewed transcripts to the general app, LLM question answering,
# MAGIC SHIELD classification or graph creation. Recheck Article 9 access/disclosure controls
# MAGIC across exports, logs, searches and downstream derivatives.
# MAGIC
# MAGIC ## Next actions / cost boundary
# MAGIC
# MAGIC 1. Create restricted output directory and configure on-demand single-worker GPU job.
# MAGIC 2. Run this comparison once; examine output with designated reviewers.
# MAGIC 3. Record model/package revisions, job configuration, durations, billed usage and
# MAGIC    reviewed error counts in IKF GitHub; select the model and remove the other from MODELS.
# MAGIC 4. Add review UI and Type D ingestion only after that selection and access verification.
# MAGIC
# MAGIC No workspace deployment, billed job run or legal compliance sign-off was performed
# MAGIC by preparing this notebook.
