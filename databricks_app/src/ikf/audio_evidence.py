"""Deterministic audio-evidence location utilities for IKF.

Reviewed Type-D transcripts use explicit line prefixes such as:

    [00:05:28–00:05:34] reviewed speech

These utilities extract the time range without an LLM and provide a compact
stable location contract for downstream Findings, Evidence and Knowledge Graph
provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


_TIMESTAMP_RANGE = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\s*[–-]\s*"
    r"(\d{2}):(\d{2}):(\d{2})\]"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _hms_to_seconds(hours: str, minutes: str, seconds: str) -> int:
    h = int(hours)
    m = int(minutes)
    s = int(seconds)
    if m > 59 or s > 59:
        raise ValueError("Invalid transcript timestamp")
    return h * 3600 + m * 60 + s


def format_audio_clock(seconds: float) -> str:
    whole = max(0, int(round(float(seconds))))
    return f"{whole // 3600:02}:{whole // 60 % 60:02}:{whole % 60:02}"


@dataclass(frozen=True, order=True)
class AudioEvidenceLocation:
    source_sha256: str
    start_s: float
    end_s: float

    def __post_init__(self):
        source_sha256 = str(self.source_sha256 or "").lower()
        if not _SHA256.fullmatch(source_sha256):
            raise ValueError("Audio evidence source_sha256 must be a SHA-256")
        if self.start_s < 0 or self.end_s < self.start_s:
            raise ValueError("Invalid audio evidence time range")
        object.__setattr__(self, "source_sha256", source_sha256)

    @property
    def time_label(self) -> str:
        return f"{format_audio_clock(self.start_s)}–{format_audio_clock(self.end_s)}"

    def serialise(self) -> str:
        start_ms = int(round(self.start_s * 1000.0))
        end_ms = int(round(self.end_s * 1000.0))
        return f"audio|{self.source_sha256}|{start_ms}|{end_ms}"


def parse_audio_evidence_location(value: str) -> AudioEvidenceLocation:
    parts = str(value or "").strip().split("|")
    if len(parts) != 4 or parts[0] != "audio":
        raise ValueError(
            "Audio evidence location must use audio|sha256|start_ms|end_ms"
        )
    try:
        start_ms = int(parts[2])
        end_ms = int(parts[3])
    except ValueError as exc:
        raise ValueError("Audio evidence milliseconds must be integers") from exc
    if start_ms < 0 or end_ms < start_ms:
        raise ValueError("Invalid audio evidence millisecond range")
    return AudioEvidenceLocation(
        source_sha256=parts[1],
        start_s=start_ms / 1000.0,
        end_s=end_ms / 1000.0,
    )


def extract_audio_time_range(text: str) -> tuple[float, float] | None:
    """Return the envelope of all explicit transcript timestamps in text."""

    ranges: list[tuple[int, int]] = []
    for match in _TIMESTAMP_RANGE.finditer(str(text or "")):
        start_s = _hms_to_seconds(*match.groups()[:3])
        end_s = _hms_to_seconds(*match.groups()[3:])
        if end_s < start_s:
            raise ValueError("Transcript timestamp end precedes start")
        ranges.append((start_s, end_s))

    if not ranges:
        return None
    return float(min(item[0] for item in ranges)), float(max(item[1] for item in ranges))


def audio_evidence_reference(
    *,
    source_name: str,
    location: AudioEvidenceLocation,
) -> str:
    name = str(source_name or "Audio recording").strip() or "Audio recording"
    return f"{name} · {location.time_label}"
