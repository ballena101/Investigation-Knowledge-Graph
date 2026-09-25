# Databricks notebook source
# MAGIC %md
# MAGIC # 66 — Controlled Whisper vs Parakeet audio benchmark
# MAGIC
# MAGIC Purpose: compare two independent ASR technologies on a short, difficult
# MAGIC Class-D audio window before treating Parakeet as production-equivalent.
# MAGIC
# MAGIC This notebook deliberately does **not** publish a transcript, call an LLM,
# MAGIC write graph knowledge, or change the App. Run only on a deliberately chosen
# MAGIC short window (recommended 60–180 seconds) to control cost.

# COMMAND ----------

# Version-range requirements are quoted deliberately. Databricks executes %pip
# through a shell and unquoted '<' / '>' characters can be interpreted as shell
# redirection rather than as PEP 440 version operators.
# MAGIC %pip install faster-whisper==1.2.1 transformers==5.17.0 "safetensors>=0.4" "huggingface-hub>=0.34,<2"

# COMMAND ----------

AUDIO_PATH = ""  # /Volumes/.../investigation_sources/audios/file.wav
START_S = 0.0
END_S = 120.0

if not AUDIO_PATH.strip():
    raise ValueError("Set AUDIO_PATH to one governed Type-D audio file.")
if START_S < 0 or END_S <= START_S:
    raise ValueError("Set a valid START_S / END_S range.")
if END_S - START_S > 180:
    raise ValueError("Controlled benchmark windows are limited to 180 seconds.")

# COMMAND ----------

from pathlib import Path
import json
import os
import tempfile
import time

import av
import ctranslate2
import torch
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download
from transformers import pipeline

HF_TOKEN = dbutils.secrets.get(
    catalog="bdw_analysis_prod",
    schema="kg_poc",
    key="huggingface_read_token",
)

WHISPER_CACHE = "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper"
PARAKEET_CACHE = "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/parakeet"

# COMMAND ----------

# Create a short governed temporary WAV excerpt locally on the ephemeral Job node.
# The source file remains authoritative and is not modified.
tmp_dir = tempfile.mkdtemp(prefix="asr_benchmark_")
excerpt_path = os.path.join(tmp_dir, "excerpt.wav")

with av.open(AUDIO_PATH) as input_container:
    audio_stream = next(s for s in input_container.streams if s.type == "audio")
    input_container.seek(int(START_S / float(av.time_base)), any_frame=False, backward=True)
    with av.open(excerpt_path, mode="w") as output_container:
        output_stream = output_container.add_stream("pcm_s16le", rate=16000)
        output_stream.layout = "mono"
        resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in input_container.decode(audio_stream):
            frame_start = float(frame.time or 0.0)
            if frame_start > END_S:
                break
            if frame_start + float(frame.duration * frame.time_base) < START_S:
                continue
            for converted in resampler.resample(frame):
                for packet in output_stream.encode(converted):
                    output_container.mux(packet)
        for packet in output_stream.encode(None):
            output_container.mux(packet)

print("Benchmark excerpt:", START_S, "to", END_S, "seconds")

# COMMAND ----------

# Whisper large-v3-turbo — existing baseline.
whisper_path = snapshot_download(
    repo_id="mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    cache_dir=WHISPER_CACHE,
    token=HF_TOKEN,
    allow_patterns=[
        "config.json", "preprocessor_config.json", "model.bin",
        "tokenizer.json", "vocabulary.*",
    ],
)
whisper_device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
whisper_compute = "float16" if whisper_device == "cuda" else "int8"
whisper = WhisperModel(
    whisper_path,
    device=whisper_device,
    compute_type=whisper_compute,
    cpu_threads=0,
    num_workers=1,
    local_files_only=True,
)
started = time.monotonic()
whisper_segments, whisper_info = whisper.transcribe(
    excerpt_path,
    task="transcribe",
    beam_size=5,
    vad_filter=False,
    word_timestamps=False,
    condition_on_previous_text=False,
)
whisper_text = " ".join(segment.text.strip() for segment in whisper_segments).strip()
whisper_elapsed = time.monotonic() - started

# COMMAND ----------

# NVIDIA Parakeet TDT 0.6B v3 — independent FastConformer/TDT route.
parakeet_path = snapshot_download(
    repo_id="nvidia/parakeet-tdt-0.6b-v3",
    cache_dir=PARAKEET_CACHE,
    token=HF_TOKEN,
    allow_patterns=[
        "config.json", "generation_config.json", "model.safetensors",
        "processor_config.json", "tokenizer.json", "tokenizer_config.json",
    ],
)
parakeet_device_index = 0 if torch.cuda.is_available() else -1
parakeet_dtype = torch.float16 if parakeet_device_index == 0 else torch.float32
parakeet = pipeline(
    "automatic-speech-recognition",
    model=parakeet_path,
    device=parakeet_device_index,
    dtype=parakeet_dtype,
)
started = time.monotonic()
try:
    parakeet_result = parakeet(excerpt_path, return_timestamps=True)
except (TypeError, ValueError):
    parakeet_result = parakeet(excerpt_path)
parakeet_elapsed = time.monotonic() - started
parakeet_text = str(parakeet_result.get("text") or "").strip()

# COMMAND ----------

window_duration = END_S - START_S
comparison = [
    {
        "engine": "faster-whisper",
        "model": "large-v3-turbo",
        "elapsed_s": round(whisper_elapsed, 2),
        "rtf": round(whisper_elapsed / window_duration, 4),
        "language": whisper_info.language,
        "text": whisper_text,
    },
    {
        "engine": "parakeet-transformers",
        "model": "nvidia/parakeet-tdt-0.6b-v3",
        "elapsed_s": round(parakeet_elapsed, 2),
        "rtf": round(parakeet_elapsed / window_duration, 4),
        "language": None,
        "text": parakeet_text,
    },
]

display(spark.createDataFrame(comparison).select("engine", "model", "elapsed_s", "rtf", "language", "text"))

print("HUMAN REVIEW REQUIRED")
print("Compare names/callsigns, numbers, maritime terminology, omissions and noise/silence hallucinations.")
print("Do not promote either output to evidence from this benchmark notebook.")
