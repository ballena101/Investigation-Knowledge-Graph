# Databricks notebook source
# MAGIC %md
# MAGIC # 65 — IKF Type D audio transcription / publication job
# MAGIC
# MAGIC Reusable Lakeflow Job task used by the IKF App.
# MAGIC
# MAGIC Actions:
# MAGIC - `TRANSCRIBE`: transcribe one selected governed audio source with faster-whisper;
# MAGIC - `PUBLISH_REVIEW`: publish one already-human-reviewed transcript as an ordinary
# MAGIC   Class D `SourceDocument` backed by a governed TXT file.
# MAGIC
# MAGIC The App never passes transcript text as a Job parameter. Reviewed text is stored
# MAGIC encrypted in Neo4j and is decrypted only inside the governed publication task.
# MAGIC
# MAGIC This notebook does not call an LLM and does not create graph knowledge.

# COMMAND ----------

# MAGIC %pip install faster-whisper==1.2.1 huggingface-hub>=0.34,<2 neo4j==6.3.1 cryptography==46.0.2

# COMMAND ----------

dbutils.widgets.dropdown(
    "action",
    "TRANSCRIBE",
    ["TRANSCRIBE", "PUBLISH_REVIEW"],
    "Action",
)
dbutils.widgets.text("transcription_run_id", "", "Transcription run ID")
dbutils.widgets.text("source_path", "", "Governed audio source path")
dbutils.widgets.dropdown("model", "turbo", ["turbo", "large-v3"], "Whisper model")
dbutils.widgets.text("review_id", "", "Transcript review ID")

# COMMAND ----------

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import av
import ctranslate2
from cryptography.fernet import Fernet
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download
from neo4j import GraphDatabase

current_notebook_path = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
workspace_notebook_path = (
    "/Workspace" + current_notebook_path
    if current_notebook_path.startswith("/Users/")
    else current_notebook_path
)
ikf_repo_root = workspace_notebook_path.rsplit("/notebooks/", 1)[0]
ikf_src_path = os.path.join(ikf_repo_root, "src")
if ikf_src_path not in sys.path:
    sys.path.insert(0, ikf_src_path)

from ikf.transcription_governance import (
    TRANSCRIPTION_WORKFLOW_VERSION,
    normalise_transcription_model,
    normalise_type_d_audio_path,
    transcript_publication_properties,
)

AUDIO_ROOT = Path(
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios"
)
TRANSCRIPT_ROOT = Path(
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts"
)
VALIDATED_TRANSCRIPT_ROOT = Path(
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/validated_transcripts"
)
MODEL_CACHE_ROOT = Path(
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper"
)

MODEL_REPOS = {
    "large-v3": "Systran/faster-whisper-large-v3",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}
MODEL_ALLOW_PATTERNS = (
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
)

HF_SECRET_CATALOG = "bdw_analysis_prod"
HF_SECRET_SCHEMA = "kg_poc"
HF_SECRET_KEY = "huggingface_read_token"

ACTION = dbutils.widgets.get("action").strip().upper()
TRANSCRIPTION_RUN_ID = dbutils.widgets.get("transcription_run_id").strip()
SOURCE_PATH_VALUE = dbutils.widgets.get("source_path").strip()
MODEL_NAME = normalise_transcription_model(dbutils.widgets.get("model").strip())
REVIEW_ID = dbutils.widgets.get("review_id").strip()

if ACTION not in {"TRANSCRIBE", "PUBLISH_REVIEW"}:
    raise ValueError("Unsupported action")

NEO4J_URI = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_uri")
NEO4J_USERNAME = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_username")
NEO4J_PASSWORD = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_password")
DIRECT_TEXT_ENCRYPTION_KEY = dbutils.secrets.get(
    scope="kg-poc-app",
    key="direct_text_encryption_key",
)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def audio_duration_seconds(path: Path) -> float | None:
    with av.open(str(path)) as container:
        if container.duration is not None:
            duration_s = float(container.duration) / float(av.time_base)
            if duration_s > 0:
                return duration_s
        audio_streams = [stream for stream in container.streams if stream.type == "audio"]
        if audio_streams:
            stream = audio_streams[0]
            if stream.duration is not None and stream.time_base is not None:
                duration_s = float(stream.duration * stream.time_base)
                if duration_s > 0:
                    return duration_s
    return None


def update_transcription_run(*, status: str, stage: str, **properties) -> None:
    if not TRANSCRIPTION_RUN_ID:
        return
    allowed = {
        "source_sha256",
        "source_name",
        "output_path",
        "detected_language",
        "language_probability",
        "duration_s",
        "elapsed_s",
        "real_time_factor",
        "device",
        "compute_type",
        "error_message",
    }
    assignments = [
        "r.status = $status",
        "r.processing_stage = $stage",
        "r.updated_at = datetime()",
    ]
    params = {
        "run_id": TRANSCRIPTION_RUN_ID,
        "status": status,
        "stage": stage,
    }
    for key, value in properties.items():
        if key not in allowed:
            continue
        assignments.append(f"r.{key} = ${key}")
        params[key] = value

    with driver.session() as session:
        session.run(
            "MATCH (r:TranscriptionRun {transcription_run_id: $run_id}) SET "
            + ", ".join(assignments),
            **params,
        ).consume()


def fail_transcription(exc: Exception) -> None:
    update_transcription_run(
        status="FAILED",
        stage="FAILED",
        error_message=f"{type(exc).__name__}: {exc}",
    )


def run_transcription() -> None:
    if not re.fullmatch(r"transcription_[0-9a-f]{32}", TRANSCRIPTION_RUN_ID):
        raise ValueError("A valid transcription_run_id is required")

    source_path = Path(
        normalise_type_d_audio_path(
            SOURCE_PATH_VALUE,
            audio_root=str(AUDIO_ROOT),
        )
    )
    if not source_path.is_file():
        raise FileNotFoundError("Selected governed audio file is not readable")

    TRANSCRIPT_ROOT.mkdir(parents=True, exist_ok=True)
    MODEL_CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    update_transcription_run(
        status="RUNNING",
        stage="PREPARING_SOURCE",
        source_name=source_path.name,
    )

    source_hash = sha256_file(source_path)
    source_duration = audio_duration_seconds(source_path)
    destination = TRANSCRIPT_ROOT / f"{source_hash}__{MODEL_NAME}.json"

    update_transcription_run(
        status="RUNNING",
        stage="PREPARING_MODEL",
        source_sha256=source_hash,
        duration_s=source_duration,
    )

    if destination.is_file():
        try:
            with destination.open("r", encoding="utf-8") as handle:
                existing = json.load(handle)
            if (
                existing.get("classification") == "D"
                and existing.get("source_sha256") == source_hash
                and existing.get("model") == MODEL_NAME
                and existing.get("status") == "MACHINE_GENERATED_UNVERIFIED"
            ):
                update_transcription_run(
                    status="COMPLETED",
                    stage="MACHINE_TRANSCRIPT_READY",
                    output_path=str(destination),
                    detected_language=existing.get("detected_language"),
                    language_probability=existing.get("language_probability"),
                    duration_s=existing.get("duration_s") or source_duration,
                    elapsed_s=existing.get("elapsed_s"),
                    real_time_factor=existing.get("real_time_factor"),
                    device=existing.get("device"),
                    compute_type=existing.get("compute_type"),
                    error_message=None,
                )
                print("REUSED existing governed machine transcript:", destination)
                return
        except Exception:
            pass

    hf_token = dbutils.secrets.get(
        catalog=HF_SECRET_CATALOG,
        schema=HF_SECRET_SCHEMA,
        key=HF_SECRET_KEY,
    )
    if not hf_token or not hf_token.strip():
        raise RuntimeError("Hugging Face read token is unavailable")

    model_path = snapshot_download(
        repo_id=MODEL_REPOS[MODEL_NAME],
        cache_dir=str(MODEL_CACHE_ROOT),
        token=hf_token,
        allow_patterns=list(MODEL_ALLOW_PATTERNS),
    )

    cuda_devices = ctranslate2.get_cuda_device_count()
    device = "cuda" if cuda_devices > 0 else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    update_transcription_run(
        status="RUNNING",
        stage="TRANSCRIBING",
        device=device,
        compute_type=compute_type,
    )

    model = WhisperModel(
        model_path,
        device=device,
        compute_type=compute_type,
        cpu_threads=0,
        num_workers=1,
        local_files_only=True,
    )

    started = time.monotonic()
    segments, info = model.transcribe(
        str(source_path),
        task="transcribe",
        beam_size=5,
        vad_filter=False,
        word_timestamps=False,
        condition_on_previous_text=False,
    )
    items = [
        {
            "start_s": round(segment.start, 3),
            "end_s": round(segment.end, 3),
            "text": segment.text,
            "avg_logprob": segment.avg_logprob,
            "no_speech_prob": segment.no_speech_prob,
        }
        for segment in segments
    ]
    elapsed = round(time.monotonic() - started, 2)
    effective_duration = float(info.duration or source_duration or 0.0)
    rtf = round(elapsed / effective_duration, 4) if effective_duration > 0 else None

    payload = {
        "classification": "D",
        "status": "MACHINE_GENERATED_UNVERIFIED",
        "transcription_run_id": TRANSCRIPTION_RUN_ID,
        "workflow_version": TRANSCRIPTION_WORKFLOW_VERSION,
        "source_name": source_path.name,
        "source_sha256": source_hash,
        "source_path": str(source_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "faster-whisper",
        "model": MODEL_NAME,
        "model_repo": MODEL_REPOS[MODEL_NAME],
        "model_cache_root": str(MODEL_CACHE_ROOT),
        "device": device,
        "visible_cuda_devices": cuda_devices,
        "compute_type": compute_type,
        "cpu_threads": 0,
        "beam_size": 5,
        "vad_filter": False,
        "condition_on_previous_text": False,
        "detected_language": info.language,
        "language_probability": info.language_probability,
        "duration_s": info.duration or source_duration,
        "elapsed_s": elapsed,
        "real_time_factor": rtf,
        "segments": items,
    }
    atomic_json(destination, payload)

    update_transcription_run(
        status="COMPLETED",
        stage="MACHINE_TRANSCRIPT_READY",
        output_path=str(destination),
        detected_language=info.language,
        language_probability=info.language_probability,
        duration_s=info.duration or source_duration,
        elapsed_s=elapsed,
        real_time_factor=rtf,
        device=device,
        compute_type=compute_type,
        error_message=None,
    )
    print("DONE", source_path.name, MODEL_NAME, "output", destination)


def run_publication() -> None:
    if not re.fullmatch(r"transcript_review_[0-9a-f]{24}", REVIEW_ID):
        raise ValueError("A valid review_id is required")

    with driver.session() as session:
        record = session.run(
            """
            MATCH (r:TypeDTranscriptReview {review_id: $review_id})
            RETURN
                r.review_id AS review_id,
                r.source_sha256 AS source_sha256,
                r.source_name AS source_name,
                r.source_path AS source_path,
                r.model AS model,
                r.reviewed_text_sha256 AS reviewed_text_sha256,
                r.encrypted_text AS encrypted_text,
                r.encryption_scheme AS encryption_scheme,
                r.status AS status,
                r.reviewed_by AS reviewed_by
            """,
            review_id=REVIEW_ID,
        ).single()

    if record is None:
        raise ValueError("Transcript review not found")
    review = record.data()
    if review.get("status") != "HUMAN_REVIEWED":
        raise RuntimeError("Only HUMAN_REVIEWED transcripts can be published")
    if review.get("encryption_scheme") != "FERNET" or not review.get("encrypted_text"):
        raise RuntimeError("Reviewed transcript is not stored with approved encryption")

    reviewed_text = Fernet(
        DIRECT_TEXT_ENCRYPTION_KEY.encode("utf-8")
    ).decrypt(
        review["encrypted_text"].encode("utf-8")
    ).decode("utf-8")
    text_hash = hashlib.sha256(reviewed_text.encode("utf-8")).hexdigest()
    if text_hash != review.get("reviewed_text_sha256"):
        raise RuntimeError("Reviewed transcript hash validation failed")

    publication = transcript_publication_properties(
        source_name=review.get("source_name") or "audio",
        source_path=review.get("source_path") or "",
        source_sha256=review.get("source_sha256") or "",
        model=review.get("model") or "",
        reviewed_text_sha256=text_hash,
        byte_size=len(reviewed_text.encode("utf-8")),
    )
    document_id = publication["document_id"]
    filename = document_id + ".txt"
    VALIDATED_TRANSCRIPT_ROOT.mkdir(parents=True, exist_ok=True)
    destination = VALIDATED_TRANSCRIPT_ROOT / filename
    temporary = destination.with_suffix(".txt.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(reviewed_text)
        if not reviewed_text.endswith("\n"):
            handle.write("\n")
    os.replace(temporary, destination)

    persisted_hash = sha256_file(destination)
    if persisted_hash != text_hash:
        raise RuntimeError("Published transcript file hash validation failed")

    relative_path = "validated_transcripts/" + filename
    with driver.session() as session:
        session.run(
            """
            MATCH (r:TypeDTranscriptReview {review_id: $review_id})
            MERGE (d:SourceDocument {document_id: $document_id})
            SET
                d.filename = $filename,
                d.volume_path = $volume_path,
                d.relative_path = $relative_path,
                d.source_type = 'TXT',
                d.document_kind = 'TRANSCRIPT',
                d.source_managed_by = 'IKF',
                d.source_repository = 'IKF_TYPE_D_TRANSCRIPT',
                d.information_class = 'D',
                d.catalogue_status = 'AVAILABLE',
                d.sha256 = $sha256,
                d.byte_size = $byte_size,
                d.audio_source_name = $audio_source_name,
                d.audio_source_path = $audio_source_path,
                d.audio_source_sha256 = $audio_source_sha256,
                d.transcript_model = $transcript_model,
                d.transcript_review_id = $review_id,
                d.transcript_review_status = 'HUMAN_REVIEWED',
                d.transcription_workflow_version = $workflow_version,
                d.validated_by = $validated_by,
                d.validated_at = datetime(),
                d.updated_at = datetime()
            MERGE (d)-[:DERIVED_FROM_TRANSCRIPT_REVIEW]->(r)
            SET
                r.publication_status = 'PUBLISHED',
                r.source_document_id = $document_id,
                r.published_at = datetime(),
                r.updated_at = datetime(),
                r.publication_error = NULL
            """,
            review_id=REVIEW_ID,
            document_id=document_id,
            filename=publication["filename"],
            volume_path=str(destination),
            relative_path=relative_path,
            sha256=text_hash,
            byte_size=publication["byte_size"],
            audio_source_name=publication["audio_source_name"],
            audio_source_path=publication["audio_source_path"],
            audio_source_sha256=publication["audio_source_sha256"],
            transcript_model=publication["transcript_model"],
            workflow_version=publication["transcription_workflow_version"],
            validated_by=review.get("reviewed_by"),
        ).consume()

    print("PUBLISHED Class D transcript SourceDocument:", document_id)
    print("Governed TXT:", destination)


try:
    if ACTION == "TRANSCRIBE":
        run_transcription()
    else:
        run_publication()
except Exception as exc:
    if ACTION == "TRANSCRIBE":
        fail_transcription(exc)
    elif REVIEW_ID:
        try:
            with driver.session() as session:
                session.run(
                    """
                    MATCH (r:TypeDTranscriptReview {review_id: $review_id})
                    SET r.publication_status = 'FAILED',
                        r.publication_error = $error_message,
                        r.updated_at = datetime()
                    """,
                    review_id=REVIEW_ID,
                    error_message=f"{type(exc).__name__}: {exc}",
                ).consume()
        except Exception:
            pass
    raise
finally:
    driver.close()
