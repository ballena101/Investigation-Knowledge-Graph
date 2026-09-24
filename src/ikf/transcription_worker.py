"""Runtime worker for governed Type-D audio transcription and publication.

The worker supports two independent ASR technologies under one governance
contract:
- faster-whisper (Whisper large-v3 / large-v3-turbo)
- NVIDIA Parakeet TDT 0.6B v3 through Hugging Face Transformers

The Lakeflow Job receives only opaque run/review identifiers. Protected source
paths and reviewed text are resolved inside the governed runtime and are not Job
parameters. All machine transcripts remain unverified until human acceptance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.metadata
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
    PARAKEET_TDT_06B_V3,
    TRANSCRIPTION_WORKFLOW_VERSION,
    transcription_engine,
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
WHISPER_CACHE_ROOT = Path(
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/faster_whisper"
)
PARAKEET_CACHE_ROOT = Path(
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/_model_cache/parakeet"
)

MODEL_REPOS = {
    "large-v3": "Systran/faster-whisper-large-v3",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    PARAKEET_TDT_06B_V3: "nvidia/parakeet-tdt-0.6b-v3",
}
WHISPER_ALLOW_PATTERNS = (
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
)
PARAKEET_ALLOW_PATTERNS = (
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "processor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
)


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


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
        "engine",
        "engine_version",
        "model_repo",
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


def _reuse_existing_transcript(
    *, driver, transcription_run_id: str, destination: Path, source_hash: str,
    model_name: str, source_duration: float | None,
) -> dict | None:
    if not destination.is_file():
        return None
    try:
        with destination.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)
        if not (
            existing.get("classification") == "D"
            and existing.get("source_sha256") == source_hash
            and existing.get("model") == model_name
            and existing.get("status") == "MACHINE_GENERATED_UNVERIFIED"
        ):
            return None
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
            engine=existing.get("engine"),
            engine_version=existing.get("engine_version"),
            model_repo=existing.get("model_repo"),
            error_message=None,
        )
        return {"status": "REUSED", "output_path": str(destination)}
    except Exception:
        return None


def _run_whisper(
    *, source_path: Path, source_duration: float | None, model_name: str,
    hf_token: str,
) -> dict:
    WHISPER_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    model_path = snapshot_download(
        repo_id=MODEL_REPOS[model_name],
        cache_dir=str(WHISPER_CACHE_ROOT),
        token=hf_token,
        allow_patterns=list(WHISPER_ALLOW_PATTERNS),
    )
    cuda_devices = ctranslate2.get_cuda_device_count()
    device = "cuda" if cuda_devices > 0 else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
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
    return {
        "engine": "faster-whisper",
        "engine_version": _package_version("faster-whisper"),
        "model_repo": MODEL_REPOS[model_name],
        "model_cache_root": str(WHISPER_CACHE_ROOT),
        "device": device,
        "visible_cuda_devices": cuda_devices,
        "compute_type": compute_type,
        "detected_language": info.language,
        "language_probability": info.language_probability,
        "duration_s": info.duration or source_duration,
        "elapsed_s": elapsed,
        "real_time_factor": (
            round(elapsed / effective_duration, 4)
            if effective_duration > 0 else None
        ),
        "segments": items,
        "settings": {
            "cpu_threads": 0,
            "beam_size": 5,
            "vad_filter": False,
            "condition_on_previous_text": False,
        },
    }


def _parakeet_segments(result: dict, duration_s: float | None) -> list[dict]:
    chunks = result.get("chunks") if isinstance(result, dict) else None
    items: list[dict] = []
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            text = str(chunk.get("text") or "").strip()
            timestamp = chunk.get("timestamp") or chunk.get("timestamps")
            start_s = end_s = None
            if isinstance(timestamp, (list, tuple)) and len(timestamp) >= 2:
                if isinstance(timestamp[0], (int, float)):
                    start_s = float(timestamp[0])
                if isinstance(timestamp[1], (int, float)):
                    end_s = float(timestamp[1])
            if text:
                items.append(
                    {
                        "start_s": round(start_s or 0.0, 3),
                        "end_s": round(
                            end_s if end_s is not None else (start_s or 0.0), 3
                        ),
                        "text": text,
                    }
                )
    if items:
        return items

    text = str((result or {}).get("text") or "").strip()
    return [
        {
            "start_s": 0.0,
            "end_s": round(float(duration_s or 0.0), 3),
            "text": text,
        }
    ] if text else []


def _run_parakeet(
    *, source_path: Path, source_duration: float | None, hf_token: str,
) -> dict:
    # Import lazily so Whisper runs do not pay Transformers/PyTorch import cost.
    import torch
    import transformers
    from transformers import pipeline

    PARAKEET_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    model_path = snapshot_download(
        repo_id=MODEL_REPOS[PARAKEET_TDT_06B_V3],
        cache_dir=str(PARAKEET_CACHE_ROOT),
        token=hf_token,
        allow_patterns=list(PARAKEET_ALLOW_PATTERNS),
    )
    device_index = 0 if torch.cuda.is_available() else -1
    device = "cuda" if device_index == 0 else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    asr = pipeline(
        "automatic-speech-recognition",
        model=model_path,
        device=device_index,
        dtype=dtype,
    )
    started = time.monotonic()
    try:
        result = asr(str(source_path), return_timestamps=True)
    except (TypeError, ValueError):
        # Timestamp support can differ by Transformers/model release. Preserve
        # a valid transcript even if chunk timestamps are unavailable.
        result = asr(str(source_path))
    elapsed = round(time.monotonic() - started, 2)
    effective_duration = float(source_duration or 0.0)
    return {
        "engine": "parakeet-transformers",
        "engine_version": getattr(transformers, "__version__", None),
        "model_repo": MODEL_REPOS[PARAKEET_TDT_06B_V3],
        "model_cache_root": str(PARAKEET_CACHE_ROOT),
        "device": device,
        "visible_cuda_devices": int(torch.cuda.device_count()),
        "compute_type": str(dtype).replace("torch.", ""),
        "detected_language": None,
        "language_probability": None,
        "duration_s": source_duration,
        "elapsed_s": elapsed,
        "real_time_factor": (
            round(elapsed / effective_duration, 4)
            if effective_duration > 0 else None
        ),
        "segments": _parakeet_segments(result, source_duration),
        "settings": {
            "transformers_pipeline": "automatic-speech-recognition",
            "return_timestamps_requested": True,
        },
    }


def _run_transcription(driver, transcription_run_id: str, hf_token: str) -> dict:
    request = _load_transcription_request(driver, transcription_run_id)
    model_name = normalise_transcription_model(request.get("model"))
    engine = transcription_engine(model_name)
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
    _update_transcription_run(
        driver, transcription_run_id,
        status="RUNNING", stage="PREPARING_SOURCE",
        source_name=source_path.name,
        engine=engine,
        model_repo=MODEL_REPOS[model_name],
    )

    source_hash = _sha256_file(source_path)
    source_duration = _audio_duration_seconds(source_path)
    destination = TRANSCRIPT_ROOT / f"{source_hash}__{model_name}.json"
    _update_transcription_run(
        driver, transcription_run_id,
        status="RUNNING", stage="PREPARING_MODEL",
        source_sha256=source_hash, duration_s=source_duration,
    )

    reused = _reuse_existing_transcript(
        driver=driver,
        transcription_run_id=transcription_run_id,
        destination=destination,
        source_hash=source_hash,
        model_name=model_name,
        source_duration=source_duration,
    )
    if reused:
        return reused

    _update_transcription_run(
        driver, transcription_run_id,
        status="RUNNING", stage="TRANSCRIBING",
    )
    if model_name == PARAKEET_TDT_06B_V3:
        outcome = _run_parakeet(
            source_path=source_path,
            source_duration=source_duration,
            hf_token=hf_token,
        )
    else:
        outcome = _run_whisper(
            source_path=source_path,
            source_duration=source_duration,
            model_name=model_name,
            hf_token=hf_token,
        )

    if not outcome.get("segments"):
        raise RuntimeError("Transcription engine returned no transcript segments")

    payload = {
        "classification": "D",
        "status": "MACHINE_GENERATED_UNVERIFIED",
        "transcription_run_id": transcription_run_id,
        "workflow_version": TRANSCRIPTION_WORKFLOW_VERSION,
        "source_name": source_path.name,
        "source_sha256": source_hash,
        "source_path": str(source_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": model_name,
        **outcome,
    }
    _atomic_json(destination, payload)

    _update_transcription_run(
        driver, transcription_run_id,
        status="COMPLETED", stage="MACHINE_TRANSCRIPT_READY",
        output_path=str(destination),
        detected_language=outcome.get("detected_language"),
        language_probability=outcome.get("language_probability"),
        duration_s=outcome.get("duration_s") or source_duration,
        elapsed_s=outcome.get("elapsed_s"),
        real_time_factor=outcome.get("real_time_factor"),
        device=outcome.get("device"),
        compute_type=outcome.get("compute_type"),
        engine=outcome.get("engine"),
        engine_version=outcome.get("engine_version"),
        model_repo=outcome.get("model_repo"),
        error_message=None,
    )
    return {
        "status": "COMPLETED",
        "output_path": str(destination),
        "engine": outcome.get("engine"),
        "elapsed_s": outcome.get("elapsed_s"),
        "real_time_factor": outcome.get("real_time_factor"),
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
    if _sha256_file(destination) != text_hash:
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
                d.transcription_engine = $transcription_engine,
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
            transcription_engine=publication["transcription_engine"],
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
                    driver, transcription_run_id, hf_token or ""
                )
            except Exception as exc:
                if transcription_run_id:
                    _update_transcription_run(
                        driver, transcription_run_id,
                        status="FAILED", stage="FAILED",
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
