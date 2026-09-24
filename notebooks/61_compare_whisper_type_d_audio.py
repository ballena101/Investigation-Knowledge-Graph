# Databricks notebook source
# MAGIC %md
# MAGIC # IKF Type D audio transcription — quality pilot
# MAGIC
# MAGIC Run manually on the minimum approved Databricks compute available. The notebook
# MAGIC automatically uses CUDA/FP16 when an NVIDIA GPU is visible; otherwise it falls back
# MAGIC to CPU/INT8 so the pilot can run on serverless CPU without cluster-creation rights.
# MAGIC Install `faster-whisper` in the notebook/job environment. Model artifacts are
# MAGIC downloaded once into a persistent governed Volume cache using a read-only Hugging Face
# MAGIC token stored as a Unity Catalog secret. The token is never printed or written to output.
# MAGIC This notebook does not publish transcripts or modify the knowledge graph. Never commit
# MAGIC audio, generated transcripts, model-cache contents or credentials to GitHub.
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

import av
import ctranslate2
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download

SOURCE_ROOT = Path('/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios')
OUTPUT_ROOT = Path('/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts')

# Persistent pilot cache inside the already-governed IKF Volume. This avoids repeated
# multi-GB model downloads across serverless notebook sessions. A separate dedicated model-
# artifact Volume can replace this path later without changing the transcription outputs.
MODEL_CACHE_ROOT = Path(
    '/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper'
)

HF_SECRET_CATALOG = 'bdw_analysis_prod'
HF_SECRET_SCHEMA = 'kg_poc'
HF_SECRET_KEY = 'huggingface_read_token'

FILES = (
    '19970212-090-sv-gale-runner-mayday-call.wav',
    'MV_Summit_Venture_Mayday_Call.flac',
    'Paul-Taverner-interview.mp3',
)
MODELS = ('large-v3', 'turbo')  # One-time comparison; retain only the selected model afterwards.
MODEL_REPOS = {
    'large-v3': 'Systran/faster-whisper-large-v3',
    'turbo': 'mobiuslabsgmbh/faster-whisper-large-v3-turbo',
}
MODEL_ALLOW_PATTERNS = (
    'config.json',
    'preprocessor_config.json',
    'model.bin',
    'tokenizer.json',
    'vocabulary.*',
)

# Cost-control gate.
# The first large-v3 CPU/INT8 run was stopped after >15 minutes before completion. The source
# recording is ~13.6 minutes, so this was only modestly slower than real time rather than the
# severe slowdown initially suspected. The next controlled comparison still uses turbo on the
# same audio because it gives a clean speed/quality comparison without expanding the matrix.
SMOKE_TEST = True
SMOKE_FILE = FILES[0]
SMOKE_MODEL = 'turbo'
ACTIVE_FILES = (SMOKE_FILE,) if SMOKE_TEST else FILES
ACTIVE_MODELS = (SMOKE_MODEL,) if SMOKE_TEST else MODELS

# Runtime selection: GPU when available; otherwise serverless/classic CPU.
CUDA_DEVICES = ctranslate2.get_cuda_device_count()
DEVICE = 'cuda' if CUDA_DEVICES > 0 else 'cpu'
COMPUTE_TYPE = 'float16' if DEVICE == 'cuda' else 'int8'
CPU_THREADS = 0  # Let CTranslate2 use its default CPU-thread policy on serverless compute.


def audio_duration_seconds(path):
    """Read container/stream metadata only; do not decode or transcribe audio."""
    with av.open(str(path)) as container:
        # PyAV container.duration is expressed in AV_TIME_BASE units (microseconds), so
        # convert to seconds by dividing by av.time_base. Do not multiply: that produces a
        # value 10^12 too large.
        if container.duration is not None:
            duration_s = float(container.duration) / float(av.time_base)
            if duration_s > 0:
                return duration_s

        audio_streams = [stream for stream in container.streams if stream.type == 'audio']
        if audio_streams:
            stream = audio_streams[0]
            if stream.duration is not None and stream.time_base is not None:
                duration_s = float(stream.duration * stream.time_base)
                if duration_s > 0:
                    return duration_s

    return None


print('IKF Whisper runtime preflight')
print('  device:', DEVICE)
print('  compute_type:', COMPUTE_TYPE)
print('  visible_cuda_devices:', CUDA_DEVICES)
print('  logical_cpu_count:', os.cpu_count())
print('  source_root:', SOURCE_ROOT)
print('  output_root:', OUTPUT_ROOT)
print('  model_cache_root:', MODEL_CACHE_ROOT)
print('  smoke_test:', SMOKE_TEST)
print('  active_files:', ACTIVE_FILES)
print('  active_models:', ACTIVE_MODELS)

assert SOURCE_ROOT.is_dir(), 'Source volume is unavailable'
assert all((SOURCE_ROOT / name).is_file() for name in FILES), 'One or more source files are missing'

# Probe duration before any model preparation/inference. This is metadata-only and lets the
# project calculate real-time factor (RTF = transcription seconds / audio seconds) objectively.
AUDIO_DURATIONS = {}
for filename in ACTIVE_FILES:
    duration = audio_duration_seconds(SOURCE_ROOT / filename)
    AUDIO_DURATIONS[filename] = duration
    print(
        '  audio_duration:', filename,
        'duration_s:', round(duration, 2) if duration is not None else 'unknown',
        'duration_min:', round(duration / 60.0, 2) if duration is not None else 'unknown',
    )

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

# Create the persistent model-cache directory using the same existing governed Volume access.
try:
    MODEL_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
except Exception as exc:
    raise PermissionError(
        'The persistent Whisper model cache could not be created. The executing identity '
        'needs WRITE VOLUME on bdw_analysis_prod.kg_poc.investigation_sources. '
        'Do not fall back to an ephemeral cache for this pilot because that would cause '
        'repeated multi-GB downloads. Original error: ' + repr(exc)
    ) from exc

assert MODEL_CACHE_ROOT.is_dir(), 'Whisper model-cache path is unavailable'

# Verify transcript write/delete capability without writing transcript content.
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

# Verify model-cache write/delete capability before attempting a large download.
CACHE_WRITE_PROBE = MODEL_CACHE_ROOT / f'.ikf_cache_probe_{os.getpid()}.tmp'
try:
    with CACHE_WRITE_PROBE.open('x', encoding='utf-8') as handle:
        handle.write('IKF_MODEL_CACHE_WRITE_PROBE\n')
    CACHE_WRITE_PROBE.unlink()
except Exception as exc:
    try:
        if CACHE_WRITE_PROBE.exists():
            CACHE_WRITE_PROBE.unlink()
    except Exception:
        pass
    raise PermissionError(
        'The Whisper model-cache directory is visible but not writable. Do not continue '
        'because an ephemeral model download would defeat the cost-control design. '
        'Original error: ' + repr(exc)
    ) from exc

# Retrieve the read-only Hugging Face token from Unity Catalog secrets. Fail closed before
# model download if it has not been configured. Never print, persist or pass this value to
# transcript metadata.
try:
    HF_TOKEN = dbutils.secrets.get(
        catalog=HF_SECRET_CATALOG,
        schema=HF_SECRET_SCHEMA,
        key=HF_SECRET_KEY,
    )
except Exception as exc:
    raise RuntimeError(
        'Hugging Face read token is not available. Create Unity Catalog secret '
        'bdw_analysis_prod.kg_poc.huggingface_read_token and rerun only this preflight cell. '
        'The token must be read-only and must never be committed to GitHub or printed. '
        'Original error: ' + repr(exc)
    ) from exc

if not HF_TOKEN or not HF_TOKEN.strip():
    raise RuntimeError(
        'Unity Catalog secret bdw_analysis_prod.kg_poc.huggingface_read_token is empty.'
    )

print('  hf_token_configured: True')
print('PRECHECK PASS — source/output/cache access, duration metadata and secret retrieval are confirmed. No model download or transcription has run yet.')
print(
    'COST NOTE — High-memory serverless (32 GB) should be used only after an OOM or measured '
    'memory constraint. It does not add CPU cores and has a higher DBU emission rate.'
)


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
# MAGIC ## Prepare the selected model in the persistent cache
# MAGIC
# MAGIC Run this cell only after the preflight prints `PRECHECK PASS`.
# MAGIC
# MAGIC This cell downloads only missing model artifacts using the read-only Hugging Face
# MAGIC token and persists them under `MODEL_CACHE_ROOT`. If the snapshot is already cached,
# MAGIC Hugging Face reuses it rather than downloading the full model again. The returned local
# MAGIC snapshot path is then used by the transcription cell so inference does not need Hub
# MAGIC access.
# MAGIC
# MAGIC The current cost-control smoke model is `turbo`. `large-v3` remains cached from the
# MAGIC previous attempt and is not deleted.

# COMMAND ----------

MODEL_PATHS = {}

for model_name in ACTIVE_MODELS:
    repo_id = MODEL_REPOS[model_name]
    print('PREPARING MODEL', model_name, 'repo', repo_id)
    download_started = time.monotonic()

    model_path = snapshot_download(
        repo_id=repo_id,
        cache_dir=str(MODEL_CACHE_ROOT),
        token=HF_TOKEN,
        allow_patterns=list(MODEL_ALLOW_PATTERNS),
    )

    download_elapsed = round(time.monotonic() - download_started, 2)
    MODEL_PATHS[model_name] = model_path
    print(
        'MODEL READY', model_name,
        'elapsed_s', download_elapsed,
        'local_snapshot', model_path,
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute the controlled pilot
# MAGIC
# MAGIC Run this cell only after the previous cell prints `MODEL READY`.
# MAGIC
# MAGIC While `SMOKE_TEST = True`, this cell processes only the first mayday recording with
# MAGIC the selected smoke model. The model is loaded exclusively from the persistent local
# MAGIC snapshot prepared above; no Hugging Face token is supplied to inference.
# MAGIC
# MAGIC The cell records both elapsed time and real-time factor (RTF):
# MAGIC
# MAGIC `RTF = transcription elapsed seconds / source audio seconds`
# MAGIC
# MAGIC Lower is better. For example, RTF 0.5 means 10 minutes of audio take about 5 minutes
# MAGIC to transcribe; RTF 2.0 means 10 minutes of audio take about 20 minutes.

# COMMAND ----------

for model_name in ACTIVE_MODELS:
    model_path = MODEL_PATHS.get(model_name)
    if not model_path:
        raise RuntimeError(
            f'Model {model_name} has not been prepared. Run the model-cache cell first.'
        )

    print('LOADING LOCAL MODEL', model_name, 'device', DEVICE, 'compute_type', COMPUTE_TYPE)
    model = WhisperModel(
        model_path,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        cpu_threads=CPU_THREADS,
        num_workers=1,
        local_files_only=True,
    )

    for filename in ACTIVE_FILES:
        source = SOURCE_ROOT / filename
        source_hash = sha256_file(source)
        destination = OUTPUT_ROOT / (source_hash + '__' + model_name + '.json')
        if destination.exists():
            print('SKIP existing', filename, model_name)
            continue

        source_duration = AUDIO_DURATIONS.get(filename)
        print(
            'TRANSCRIBING', filename, model_name,
            'source_duration_s', round(source_duration, 2) if source_duration else 'unknown',
        )

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
        effective_duration = float(info.duration or source_duration or 0.0)
        real_time_factor = (
            round(elapsed / effective_duration, 4)
            if effective_duration > 0
            else None
        )

        atomic_json(destination, {
            'classification': 'D',
            'status': 'MACHINE_GENERATED_UNVERIFIED',
            'source_name': filename,
            'source_sha256': source_hash,
            'source_path': str(source),
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'engine': 'faster-whisper',
            'model': model_name,
            'model_repo': MODEL_REPOS[model_name],
            'model_cache_root': str(MODEL_CACHE_ROOT),
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
            'real_time_factor': real_time_factor,
            'segments': items,
        })
        print(
            'DONE', filename, model_name,
            'device', DEVICE,
            'duration_s', round(info.duration, 1),
            'elapsed_s', elapsed,
            'real_time_factor', real_time_factor,
            'output', destination,
        )

    del model

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read-only inspection of the completed turbo smoke transcript
# MAGIC
# MAGIC This cell performs **no model loading and no inference**. It reads the existing
# MAGIC Class-D transcript JSON and original audio only to verify provenance and prepare a
# MAGIC targeted human listening review. The source recording remains authoritative.
# MAGIC
# MAGIC Run only this cell after pulling the notebook update. Do not rerun the transcription.

# COMMAND ----------

from pathlib import Path as _ReviewPath
import hashlib as _review_hashlib
import json as _review_json
import re as _review_re

REVIEW_JSON = _ReviewPath(
    '/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts/'
    '10915255195ae92e16c44ed93befdf5e45846e5d3dff5bb37f2c464d5d04cca0__turbo.json'
)
EXPECTED_SOURCE = _ReviewPath(
    '/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios/'
    '19970212-090-sv-gale-runner-mayday-call.wav'
)
EXPECTED_SOURCE_SHA256 = '10915255195ae92e16c44ed93befdf5e45846e5d3dff5bb37f2c464d5d04cca0'


def _review_sha256(path):
    digest = _review_hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _fmt_time(seconds):
    seconds = max(0.0, float(seconds or 0.0))
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f'{minutes:02d}:{remainder:05.2f}'


assert REVIEW_JSON.is_file(), f'Completed turbo transcript not found: {REVIEW_JSON}'
assert EXPECTED_SOURCE.is_file(), f'Original source audio not found: {EXPECTED_SOURCE}'

with REVIEW_JSON.open('r', encoding='utf-8') as handle:
    review = _review_json.load(handle)

actual_source_hash = _review_sha256(EXPECTED_SOURCE)
segments = list(review.get('segments') or [])

provenance_checks = {
    'classification_is_D': review.get('classification') == 'D',
    'status_unverified': review.get('status') == 'MACHINE_GENERATED_UNVERIFIED',
    'model_is_turbo': review.get('model') == 'turbo',
    'engine_is_faster_whisper': review.get('engine') == 'faster-whisper',
    'source_name_matches': review.get('source_name') == EXPECTED_SOURCE.name,
    'json_source_hash_matches_expected': review.get('source_sha256') == EXPECTED_SOURCE_SHA256,
    'original_audio_hash_matches_expected': actual_source_hash == EXPECTED_SOURCE_SHA256,
    'segments_present': bool(segments),
}

segment_issues = []
previous_end = 0.0
for index, segment in enumerate(segments, start=1):
    start_s = float(segment.get('start_s') or 0.0)
    end_s = float(segment.get('end_s') or 0.0)
    text = str(segment.get('text') or '').strip()
    if end_s < start_s:
        segment_issues.append(f'segment {index}: end before start')
    if start_s + 0.05 < previous_end:
        segment_issues.append(f'segment {index}: timestamp overlaps previous segment')
    if not text:
        segment_issues.append(f'segment {index}: empty text')
    previous_end = max(previous_end, end_s)

critical_pattern = _review_re.compile(
    r'\b(?:mayday|pan[ -]?pan|distress|sinking|fire|collision|ground(?:ed|ing)?|'
    r'abandon|help|coast\s*guard|radio|channel|position|latitude|longitude|'
    r'north|south|east|west|degrees?|minutes?|knots?|vessel|ship|boat|not|no|unable|'
    r'zero|one|two|three|four|five|six|seven|eight|nine|\d)\b',
    flags=_review_re.IGNORECASE,
)

weak_segments = []
critical_segments = []
for index, segment in enumerate(segments, start=1):
    text = str(segment.get('text') or '').strip()
    avg_logprob = segment.get('avg_logprob')
    no_speech_prob = segment.get('no_speech_prob')
    weak = (
        (avg_logprob is not None and float(avg_logprob) < -0.8)
        or (no_speech_prob is not None and float(no_speech_prob) > 0.35)
    )
    if weak:
        weak_segments.append((index, segment))
    if critical_pattern.search(text):
        critical_segments.append((index, segment))

print('IKF TYPE-D TRANSCRIPT — READ-ONLY QUALITY INSPECTION')
print('  transcript:', REVIEW_JSON)
print('  source:', EXPECTED_SOURCE)
print('  model:', review.get('model'))
print('  model_repo:', review.get('model_repo'))
print('  classification:', review.get('classification'))
print('  status:', review.get('status'))
print('  detected_language:', review.get('detected_language'))
print('  language_probability:', review.get('language_probability'))
print('  duration_s:', review.get('duration_s'))
print('  elapsed_s:', review.get('elapsed_s'))
print('  real_time_factor:', review.get('real_time_factor'))
print('  segment_count:', len(segments))
print('  weak_segment_count:', len(weak_segments))
print('  critical_review_segment_count:', len(critical_segments))
print('')
print('PROVENANCE CHECKS')
for name, passed in provenance_checks.items():
    print(' ', 'PASS' if passed else 'FAIL', '—', name)

if not all(provenance_checks.values()):
    raise RuntimeError('Transcript provenance validation failed. Do not review or promote this transcript.')

print('')
print('SEGMENT STRUCTURE:', 'PASS' if not segment_issues else 'REVIEW')
for issue in segment_issues[:20]:
    print('  -', issue)
if len(segment_issues) > 20:
    print('  ...', len(segment_issues) - 20, 'additional issue(s)')

print('')
print('TARGETED LISTENING WINDOWS — LOW CONFIDENCE / HIGH NO-SPEECH')
if weak_segments:
    for index, segment in weak_segments:
        print(
            f'  [{index:03d}] {_fmt_time(segment.get("start_s"))}–{_fmt_time(segment.get("end_s"))}',
            f'logprob={segment.get("avg_logprob")!r}',
            f'no_speech={segment.get("no_speech_prob")!r}',
            '|', str(segment.get('text') or '').strip(),
        )
else:
    print('  none flagged by the pilot thresholds')

print('')
print('TARGETED LISTENING WINDOWS — SAFETY-CRITICAL WORDING / NUMBERS / NEGATION')
for index, segment in critical_segments:
    print(
        f'  [{index:03d}] {_fmt_time(segment.get("start_s"))}–{_fmt_time(segment.get("end_s"))}',
        '|', str(segment.get('text') or '').strip(),
    )

print('')
print('FULL TIMESTAMPED MACHINE TRANSCRIPT — UNVERIFIED')
for index, segment in enumerate(segments, start=1):
    print(
        f'[{index:03d}] {_fmt_time(segment.get("start_s"))}–{_fmt_time(segment.get("end_s"))}',
        str(segment.get('text') or '').strip(),
    )

print('')
print('QUALITY GATE STATUS — HUMAN LISTENING REQUIRED')
print(
    'Do not change MACHINE_GENERATED_UNVERIFIED or expose this transcript to general LLM, '
    'SHIELD or graph routes until the critical and weak windows have been checked against the audio.'
)

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
# MAGIC passages, elapsed runtime, real-time factor and billed compute. Include a second reviewer
# MAGIC for disputed safety-critical passages. Accept turbo only if its critical-field
# MAGIC performance is no worse on this set; otherwise retain large-v3. Neither model confidence
# MAGIC nor the use of the same model on CPU/GPU is a substitute for listening. Keep human
# MAGIC corrections in a separate versioned record.
# MAGIC
# MAGIC CPU/INT8 is a resource-efficient fallback, not a change to the evidence-governance
# MAGIC rules. If a GPU later becomes available, repeat the selected validation subset on
# MAGIC CUDA/FP16 before declaring the GPU path runtime validated.
# MAGIC
# MAGIC Only after human review may a transcript enter the existing Type D document pipeline.
# MAGIC Carry source hash, time offsets and review status into retrieval and evidence. Do not
# MAGIC expose unreviewed transcripts to the general app, LLM question answering, SHIELD
# MAGIC classification or graph creation.