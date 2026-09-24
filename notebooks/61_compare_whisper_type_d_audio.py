# Databricks notebook source
# MAGIC %md
# MAGIC # IKF Type D audio transcription — quality pilot
# MAGIC
# MAGIC Run manually on the minimum approved Databricks compute available. The notebook
# MAGIC automatically uses CUDA/FP16 when an NVIDIA GPU is visible; otherwise it falls back
# MAGIC to CPU/INT8 so the pilot can run on serverless CPU without cluster-creation rights.
# MAGIC Install `faster-whisper` in the notebook/job environment. Pin package and model
# MAGIC revisions after the pilot. This notebook does not publish transcripts or modify the
# MAGIC knowledge graph. Never commit audio or generated transcripts to GitHub.
# MAGIC
# MAGIC Access: grant only designated Type D reviewers permission to read the audio and
# MAGIC transcript storage. Audio and transcripts may contain protected witness statements,
# MAGIC identifying details and other Article 9 material. Confirm access/retention rules with
# MAGIC the competent owner before operational use. The source recording remains authoritative.

# COMMAND ----------

from pathlib import Path
import hashlib
import json
import os
import time
from datetime import datetime, timezone

import ctranslate2
from faster_whisper import WhisperModel

SOURCE_ROOT = Path('/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios')
OUTPUT_ROOT = Path('/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts')
FILES = (
    '19970212-090-sv-gale-runner-mayday-call.wav',
    'MV_Summit_Venture_Mayday_Call.flac',
    'Paul-Taverner-interview.mp3',
)
MODELS = ('large-v3', 'turbo')  # One-time comparison; retain only the selected model afterwards.

# Cost-control gate. Keep True until one heavy-model transcription succeeds end-to-end.
# This first smoke test intentionally uses one short distress-call recording + large-v3.
SMOKE_TEST = True
SMOKE_FILE = FILES[0]
SMOKE_MODEL = 'large-v3'
ACTIVE_FILES = (SMOKE_FILE,) if SMOKE_TEST else FILES
ACTIVE_MODELS = (SMOKE_MODEL,) if SMOKE_TEST else MODELS

# Runtime selection: GPU when available; otherwise serverless/classic CPU.
CUDA_DEVICES = ctranslate2.get_cuda_device_count()
DEVICE = 'cuda' if CUDA_DEVICES > 0 else 'cpu'
COMPUTE_TYPE = 'float16' if DEVICE == 'cuda' else 'int8'
CPU_THREADS = 0  # Let CTranslate2 use its default CPU-thread policy on serverless compute.

print('IKF Whisper runtime preflight')
print('  device:', DEVICE)
print('  compute_type:', COMPUTE_TYPE)
print('  visible_cuda_devices:', CUDA_DEVICES)
print('  logical_cpu_count:', os.cpu_count())
print('  source_root:', SOURCE_ROOT)
print('  output_root:', OUTPUT_ROOT)
print('  smoke_test:', SMOKE_TEST)
print('  active_files:', ACTIVE_FILES)
print('  active_models:', ACTIVE_MODELS)

assert SOURCE_ROOT.is_dir(), 'Source volume is unavailable'
assert all((SOURCE_ROOT / name).is_file() for name in FILES), 'One or more source files are missing'

# Create the derived-transcript directory only if the executing identity already has
# the required Unity Catalog WRITE VOLUME permission. We do not broaden permissions here.
if not OUTPUT_ROOT.exists():
    print('OUTPUT DIRECTORY MISSING — attempting governed creation:', OUTPUT_ROOT)
    try:
        OUTPUT_ROOT.mkdir(parents=False, exist_ok=False)
        print('OUTPUT DIRECTORY CREATED:', OUTPUT_ROOT)
    except Exception as exc:
        raise PermissionError(
            'The transcript output directory does not exist and this notebook could not create it. '
            'The executing identity needs WRITE VOLUME on '
            'bdw_analysis_prod.kg_poc.investigation_sources (and USE CATALOG / USE SCHEMA as applicable). '
            'Do not grant broader permissions solely for this pilot. Original error: '
            + repr(exc)
        ) from exc

assert OUTPUT_ROOT.is_dir(), 'Transcript output path exists but is not a directory'

# Verify write/delete capability without writing transcript content.
WRITE_PROBE = OUTPUT_ROOT / f'.ikf_write_probe_{os.getpid()}.tmp'
try:
    with WRITE_PROBE.open('x', encoding='utf-8') as handle:
        handle.write('IKF_WRITE_PROBE\n')
    WRITE_PROBE.unlink()
except Exception as exc:
    try:
        if WRITE_PROBE.exists():
            WRITE_PROBE.unlink()
    except Exception:
        pass
    raise PermissionError(
        'The transcript output directory is visible but the notebook cannot write to it. '
        'The executing identity needs WRITE VOLUME on '
        'bdw_analysis_prod.kg_poc.investigation_sources. '
        'Do not continue to model inference until this is resolved. Original error: '
        + repr(exc)
    ) from exc

print('PRECHECK PASS — source files are visible and output write/delete access is confirmed. No transcription has run yet.')


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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute the controlled pilot
# MAGIC
# MAGIC Run this cell only after the preflight cell prints `PRECHECK PASS`.
# MAGIC
# MAGIC While `SMOKE_TEST = True`, this cell processes only the first mayday recording with
# MAGIC `large-v3`. This validates the heaviest candidate model, dependency/model loading,
# MAGIC Volume read/write access and JSON persistence without launching all six combinations.
# MAGIC After a successful smoke test, change `SMOKE_TEST = False`, rerun the preflight cell,
# MAGIC and then run this cell once for the full three-file/two-model comparison.

# COMMAND ----------

for model_name in ACTIVE_MODELS:
    print('LOADING MODEL', model_name, 'device', DEVICE, 'compute_type', COMPUTE_TYPE)
    model = WhisperModel(
        model_name,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        cpu_threads=CPU_THREADS,
        num_workers=1,
    )
    for filename in ACTIVE_FILES:
        source = SOURCE_ROOT / filename
        source_hash = sha256_file(source)
        destination = OUTPUT_ROOT / (source_hash + '__' + model_name + '.json')
        if destination.exists():
            print('SKIP existing', filename, model_name)
            continue

        start = time.monotonic()
        # Avoid aggressive VAD on short radio calls: it can discard faint speech.
        # Do not provide a context prompt that could bias names, coordinates or instructions.
        segments, info = model.transcribe(
            str(source),
            task='transcribe',
            beam_size=5,
            vad_filter=False,
            word_timestamps=False,
            condition_on_previous_text=False,
        )
        items = [
            {
                'start_s': round(s.start, 3),
                'end_s': round(s.end, 3),
                'text': s.text,
                'avg_logprob': s.avg_logprob,
                'no_speech_prob': s.no_speech_prob,
            }
            for s in segments
        ]

        elapsed = round(time.monotonic() - start, 2)
        atomic_json(destination, {
            'classification': 'D',
            'status': 'MACHINE_GENERATED_UNVERIFIED',
            'source_name': filename,
            'source_sha256': source_hash,
            'source_path': str(source),
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'engine': 'faster-whisper',
            'model': model_name,
            'device': DEVICE,
            'visible_cuda_devices': CUDA_DEVICES,
            'compute_type': COMPUTE_TYPE,
            'cpu_threads': CPU_THREADS,
            'beam_size': 5,
            'vad_filter': False,
            'condition_on_previous_text': False,
            'smoke_test': SMOKE_TEST,
            'detected_language': info.language,
            'language_probability': info.language_probability,
            'duration_s': info.duration,
            'elapsed_s': elapsed,
            'segments': items,
        })
        print(
            'DONE', filename, model_name,
            'device', DEVICE,
            'duration_s', round(info.duration, 1),
            'elapsed_s', elapsed,
            'output', destination,
        )
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
# MAGIC passages, elapsed runtime and billed compute. Include a second reviewer for disputed
# MAGIC safety-critical passages. Accept turbo only if its critical-field performance is no
# MAGIC worse on this set; otherwise retain large-v3. Neither model confidence nor the use of
# MAGIC the same model on CPU/GPU is a substitute for listening. Keep human corrections in a
# MAGIC separate versioned record.
# MAGIC
# MAGIC CPU/INT8 is a resource-efficient fallback, not a change to the evidence-governance
# MAGIC rules. If a GPU later becomes available, repeat the selected validation subset on
# MAGIC CUDA/FP16 before declaring the GPU path runtime validated.
# MAGIC
# MAGIC Only after human review may a transcript enter the existing Type D document pipeline.
# MAGIC Carry source hash, time offsets and review status into retrieval and evidence. Do not
# MAGIC expose unreviewed transcripts to the general app, LLM question answering, SHIELD
# MAGIC classification or graph creation.
