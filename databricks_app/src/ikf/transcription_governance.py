"""Deterministic governance helpers for IKF Type-D audio transcription.

These helpers are deliberately runtime-agnostic. They validate audio-source
paths, stable transcript-document identities and publication metadata without
calling Databricks, Neo4j, Whisper or any LLM.
"""

from __future__ import annotations

from pathlib import PurePosixPath
import hashlib
import re


TRANSCRIPTION_WORKFLOW_VERSION = "IKF_TYPE_D_TRANSCRIPTION_V0.2"
SUPPORTED_AUDIO_EXTENSIONS = frozenset({".wav", ".flac", ".mp3", ".m4a", ".ogg"})
SUPPORTED_TRANSCRIPTION_MODELS = frozenset({"turbo", "large-v3"})
_SHA256 = re.compile(r"[0-9a-f]{64}")


def normalise_type_d_audio_path(path: str, *, audio_root: str) -> str:
    """Return one governed audio path or fail closed.

    V0.2 intentionally accepts only direct children of the configured audio
    folder. Recursive browsing can be added later with an explicit catalogue
    contract rather than silently widening the protected-source boundary.
    """

    value = str(path or "").strip()
    root = str(audio_root or "").strip().rstrip("/")
    if not value or not root:
        raise ValueError("Audio path and governed audio root are required")

    candidate = PurePosixPath(value)
    root_path = PurePosixPath(root)
    if candidate.parent != root_path:
        raise ValueError("Audio source is outside the governed Type D audio folder")
    if candidate.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError("Unsupported audio source type")
    if candidate.name in {".", ".."} or not candidate.name:
        raise ValueError("Invalid audio source filename")
    return str(candidate)


def normalise_transcription_model(value: str) -> str:
    model = str(value or "").strip()
    if model not in SUPPORTED_TRANSCRIPTION_MODELS:
        raise ValueError("Unsupported transcription model")
    return model


def reviewed_transcript_document_id(
    *,
    source_sha256: str,
    reviewed_text_sha256: str,
    model: str,
) -> str:
    """Build a stable SourceDocument id for one accepted reviewed transcript."""

    source_hash = str(source_sha256 or "").strip().lower()
    text_hash = str(reviewed_text_sha256 or "").strip().lower()
    model = normalise_transcription_model(model)
    if not _SHA256.fullmatch(source_hash):
        raise ValueError("source_sha256 must be a SHA-256")
    if not _SHA256.fullmatch(text_hash):
        raise ValueError("reviewed_text_sha256 must be a SHA-256")

    identity = hashlib.sha256(
        (source_hash + "|" + model + "|" + text_hash).encode("utf-8")
    ).hexdigest()
    return "doc_" + identity[:24]


def reviewed_transcript_filename(source_name: str) -> str:
    """Return an investigator-readable virtual document filename."""

    name = PurePosixPath(str(source_name or "audio").strip()).name or "audio"
    stem = PurePosixPath(name).stem or "audio"
    return stem + " — validated transcript.txt"


def transcript_publication_properties(
    *,
    source_name: str,
    source_path: str,
    source_sha256: str,
    model: str,
    reviewed_text_sha256: str,
    byte_size: int,
) -> dict:
    """Return SourceDocument metadata for an accepted reviewed transcript.

    `source_type=TXT` deliberately reuses the existing document extraction path;
    `document_kind=TRANSCRIPT` preserves the semantic origin without creating a
    second analysis pipeline.
    """

    document_id = reviewed_transcript_document_id(
        source_sha256=source_sha256,
        reviewed_text_sha256=reviewed_text_sha256,
        model=model,
    )
    if int(byte_size) < 1:
        raise ValueError("Accepted transcript must not be empty")

    return {
        "document_id": document_id,
        "filename": reviewed_transcript_filename(source_name),
        "source_type": "TXT",
        "document_kind": "TRANSCRIPT",
        "source_managed_by": "IKF",
        "source_repository": "IKF_TYPE_D_TRANSCRIPT",
        "information_class": "D",
        "catalogue_status": "AVAILABLE",
        "sha256": reviewed_text_sha256.lower(),
        "byte_size": int(byte_size),
        "audio_source_name": PurePosixPath(str(source_name or "")).name,
        "audio_source_path": str(source_path or "").strip(),
        "audio_source_sha256": source_sha256.lower(),
        "transcript_model": normalise_transcription_model(model),
        "transcription_workflow_version": TRANSCRIPTION_WORKFLOW_VERSION,
    }
