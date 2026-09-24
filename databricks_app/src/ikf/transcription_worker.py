"""Runtime worker for governed IKF Type-D audio transcription and publication.

This module is invoked by Databricks notebook 65. It intentionally accepts only
opaque run/review identifiers from the Lakeflow Job surface; protected source
paths and reviewed text are resolved inside Neo4j and are not Job parameters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import time

import av
import ctranslate2
from cryptography.fernet import Fernet
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download
from neo4j import GraphDatabase

from .transcription_governance import (
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def _audio_duration_seconds(path: Path) -> float | None:
    with av.open(str(path)) as container:
        if container.duration is not None:
            # PyAV container.duration is expressed in av.time_base units.
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


def _update_transcription_run(
    driver,
    transcription_run_id: str,
    *,
    status: str,
    stage: str,
    **properties,
) -> None:
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
        "run_id": transcription_run_id,
        "status": status,
        "stage": stage,
    }
    for key, value in properties.items():
        if key in allowed:
            assignments.append(f"r.{key} = ${key}")
            params[key] = value

    with driver.session() as session:
        session.run(
            "MATCH (r:TranscriptionRun {transcription_run_id: $run_id}) SET "
            + ", ".join(assignments),
            **params,
        ).consume()


def _load_transcription_request(driver, transcription_run_id: str) -> dict:
    if not re.fullmatch(r"transcription_[0-9a-f]{32}", transcription_run_id):
        raise ValueError("A valid transcription_run_id is required")

    with driver.session() as session:
        record = session.run(
            """
            MATCH (r:TranscriptionRun {
                transcription_run_id: $run_id,
                classification: 'D'
            })
            RETURN
                r.source_path AS source_path,
                r.source_name AS source_name,
                r.model AS model
            """,
            run_id=transcription_run_id,
        ).single()
    if record is None:
        raise ValueError("Governed transcription request not found")
    return record.data()


def _run_transcription(driver, transcription_run_id: str, hf_token: str) -> dict:
    request = _load_transcription_request(driver, transcription_run_id)
    model_name = normalise_transcription_model(request.get("model"))
    source_path = Path(
        normalise_type_d_audio_path(
            request.get("source_path"),
            audio_root=str(AUDIO_ROOT),
        )
    )
    if not source_path.is_file():
        raise FileNotFoundError("Selected governed audio file is not readable")
    if not hf_token or not str(hf_token).strip():
        raise RuntimeError("Hugging Face read token is unavailable")

    TRANSCRIPT_ROOT.mkdir(parents=True, exist_ok=True)
    MODEL_CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    _update_transcription_run(
        driver,
        transcription_run_id,
        status="RUNNING",
        stage="PREPARING_SOURCE",
        source_name=source_path.name,
    )

    source_hash = _sha256_file(source_path)
    source_duration = _audio_duration_seconds(source_path)
    destination = TRANSCRIPT_ROOT / f"{source_hash}__{model_name}.json"

    _update_transcription_run(
        driver,
        transcription_run_id,
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
                and existing.get("model") == model_name
                and existing.get("status") == "MACHINE_GENERATED_UNVERIFIED"
            ):
                _update_transcription_run(
                    driver,
                    transcription_run_id,
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
                return {
                    "status": "REUSED",
                    "output_path": str(destination),
                }
        except Exception:
            pass

    model_path = snapshot_download(
        repo_id=MODEL_REPOS[model_name],
        cache_dir=str(MODEL_CACHE_ROOT),
        token=hf_token,
        allow_patterns=list(MODEL_ALLOW_PATTERNS),
    )

    cuda_devices = ctranslate2.get_cuda_device_count()
    device = "cuda" if cuda_devices > 0 else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    _update_transcription_run(
        driver,
        transcription_run_id,
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
        "transcription_run_id": transcription_run_id,
        "workflow_version": TRANSCRIPTION_WORKFLOW_VERSION,
        "source_name": source_path.name,
        "source_sha256": source_hash,
        "source_path": str(source_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "faster-whisper",
        "model": model_name,
        "model_repo": MODEL_REPOS[model_name],
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
    _atomic_json(destination, payload)

    _update_transcription_run(
        driver,
        transcription_run_id,
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
    return {
        "status": "COMPLETED",
        "output_path": str(destination),
        "elapsed_s": elapsed,
        "real_time_factor": rtf,
    }


def _run_publication(driver, review_id: str, encryption_key: str) -> dict:
    if not re.fullmatch(r"transcript_review_[0-9a-f]{24}", review_id):
        raise ValueError("A valid review_id is required")
    if not encryption_key:
        raise RuntimeError("Direct-text encryption key is unavailable")

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
            review_id=review_id,
        ).single()
    if record is None:
        raise ValueError("Transcript review not found")

    review = record.data()
    if review.get("status") != "HUMAN_REVIEWED":
        raise RuntimeError("Only HUMAN_REVIEWED transcripts can be published")
    if review.get("encryption_scheme") != "FERNET" or not review.get("encrypted_text"):
        raise RuntimeError("Reviewed transcript is not stored with approved encryption")

    reviewed_text = Fernet(encryption_key.encode("utf-8")).decrypt(
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
    VALIDATED_TRANSCRIPT_ROOT.mkdir(parents=True, exist_ok=True)
    destination = VALIDATED_TRANSCRIPT_ROOT / f"{document_id}.txt"
    temporary = destination.with_suffix(".txt.tmp")
    if temporary.exists():
        temporary.unlink()
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(reviewed_text)
    os.replace(temporary, destination)

    persisted_hash = _sha256_file(destination)
    if persisted_hash != text_hash:
        raise RuntimeError("Published transcript file hash validation failed")

    relative_path = "validated_transcripts/" + destination.name
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
            review_id=review_id,
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

    return {
        "status": "PUBLISHED",
        "document_id": document_id,
        "volume_path": str(destination),
    }


def run_transcription_action(
    *,
    action: str,
    transcription_run_id: str,
    review_id: str,
    neo4j_uri: str,
    neo4j_username: str,
    neo4j_password: str,
    encryption_key: str,
    hf_token: str | None = None,
) -> dict:
    """Execute one governed worker action and persist failure state."""

    action = str(action or "").strip().upper()
    if action not in {"TRANSCRIBE", "PUBLISH_REVIEW"}:
        raise ValueError("Unsupported transcription worker action")

    driver = GraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_username, neo4j_password),
    )
    driver.verify_connectivity()

    try:
        if action == "TRANSCRIBE":
            try:
                return _run_transcription(
                    driver,
                    transcription_run_id,
                    hf_token or "",
                )
            except Exception as exc:
                if transcription_run_id:
                    _update_transcription_run(
                        driver,
                        transcription_run_id,
                        status="FAILED",
                        stage="FAILED",
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                raise

        try:
            return _run_publication(driver, review_id, encryption_key)
        except Exception as exc:
            if review_id:
                try:
                    with driver.session() as session:
                        session.run(
                            """
                            MATCH (r:TypeDTranscriptReview {review_id: $review_id})
                            SET r.publication_status = 'FAILED',
                                r.publication_error = $error_message,
                                r.updated_at = datetime()
                            """,
                            review_id=review_id,
                            error_message=f"{type(exc).__name__}: {exc}",
                        ).consume()
                except Exception:
                    pass
            raise
    finally:
        driver.close()
