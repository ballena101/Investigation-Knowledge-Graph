"""Deterministic governance helpers for Type-D audio transcription.

These helpers are deliberately runtime-agnostic. They validate audio-source
paths, transcription-engine/model choices, language compatibility, stable
transcript-document identities and publication metadata without calling
Databricks, Neo4j, an ASR engine or any LLM.
"""

from __future__ import annotations

from pathlib import PurePosixPath
import hashlib
import re


TRANSCRIPTION_WORKFLOW_VERSION = "IKF_TYPE_D_TRANSCRIPTION_V0.3"
SUPPORTED_AUDIO_EXTENSIONS = frozenset({".wav", ".flac", ".mp3", ".m4a", ".ogg"})
WHISPER_TURBO = "turbo"
WHISPER_LARGE_V3 = "large-v3"
PARAKEET_TDT_06B_V3 = "parakeet-tdt-0.6b-v3"
SUPPORTED_TRANSCRIPTION_MODELS = frozenset(
    {WHISPER_TURBO, WHISPER_LARGE_V3, PARAKEET_TDT_06B_V3}
)
PARAKEET_SUPPORTED_LANGUAGES = frozenset(
    {
        "en", "es", "fr", "de", "bg", "hr", "cs", "da", "nl", "et",
        "fi", "el", "hu", "it", "lv", "lt", "mt", "pl", "pt", "ro",
        "sk", "sl", "sv", "ru", "uk",
    }
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


def transcription_engine(model: str) -> str:
    value = normalise_transcription_model(model)
    return "parakeet" if value == PARAKEET_TDT_06B_V3 else "faster-whisper"


def model_display_name(model: str) -> str:
    value = normalise_transcription_model(model)
    return {
        WHISPER_TURBO: "Whisper large-v3-turbo",
        WHISPER_LARGE_V3: "Whisper large-v3",
        PARAKEET_TDT_06B_V3: "NVIDIA Parakeet TDT 0.6B v3",
    }[value]


def parakeet_supports_language(language_code: str | None) -> bool:
    """Return whether a known ISO-like language code is supported by Parakeet.

    Unknown/empty language is not rejected here because language may be detected
    only after transcription. The App should present Parakeet as a controlled
    alternative and disclose its published language set.
    """

    value = str(language_code or "").strip().lower()
    if not value:
        return True
    return value in PARAKEET_SUPPORTED_LANGUAGES


def normalise_type_d_audio_path(path: str, *, audio_root: str) -> str:
    """Return one governed audio path or fail closed."""

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
    """Return SourceDocument metadata for an accepted reviewed transcript."""

    document_id = reviewed_transcript_document_id(
        source_sha256=source_sha256,
        reviewed_text_sha256=reviewed_text_sha256,
        model=model,
    )
    if int(byte_size) < 1:
        raise ValueError("Accepted transcript must not be empty")

    model = normalise_transcription_model(model)
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
        "transcript_model": model,
        "transcription_engine": transcription_engine(model),
        "transcription_workflow_version": TRANSCRIPTION_WORKFLOW_VERSION,
    }
