"""Source adapters for IKF pseudonymisation.

These helpers obtain text for privacy transformation without changing the
canonical investigation source. They support the source types currently used
by the PoC: PDF, plain text/Markdown and transcript-style JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz

PSEUDONYMISATION_SOURCE_ADAPTER_VERSION = "IKF_PSEUDONYMISATION_SOURCE_ADAPTER_V0.1"
TEXT_SUFFIXES = frozenset({".txt", ".md", ".text", ".log", ".csv"})
JSON_SUFFIXES = frozenset({".json"})


def _safe_path(path: str, allowed_roots) -> Path:
    candidate = Path(str(path or "")).resolve()
    roots = [Path(root).resolve() for root in allowed_roots]
    if not any(candidate == root or root in candidate.parents for root in roots):
        raise PermissionError("Source is outside the governed IKF/MAIRA volumes.")
    if not candidate.is_file():
        raise FileNotFoundError(str(candidate))
    return candidate


def _json_text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_json_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        # Prefer transcript/evidence-like fields and avoid serialising metadata.
        preferred = []
        for key in ("text", "transcript", "content", "segments", "utterances"):
            if key in value:
                part = _json_text(value[key])
                if part:
                    preferred.append(part)
        if preferred:
            return "\n".join(preferred)
        return "\n".join(
            part
            for part in (_json_text(item) for item in value.values())
            if part
        )
    return ""


def read_source_text(path: str, *, allowed_roots) -> dict:
    """Read one governed source into text plus page-aware display markers."""

    source = _safe_path(path, allowed_roots)
    suffix = source.suffix.lower()

    if suffix == ".pdf":
        pages = []
        document = fitz.open(source)
        try:
            for index, page in enumerate(document, start=1):
                text = (page.get_text("text") or "").strip()
                if text:
                    pages.append(f"[[PAGE {index}]]\n{text}")
        finally:
            document.close()
        return {
            "text": "\n\n".join(pages),
            "format": "PDF",
            "page_markers": True,
        }

    if suffix in TEXT_SUFFIXES:
        return {
            "text": source.read_text(encoding="utf-8", errors="replace"),
            "format": suffix.lstrip(".").upper() or "TEXT",
            "page_markers": False,
        }

    if suffix in JSON_SUFFIXES:
        payload = json.loads(source.read_text(encoding="utf-8"))
        return {
            "text": _json_text(payload),
            "format": "JSON_TRANSCRIPT",
            "page_markers": False,
        }

    raise ValueError(
        "Pseudonymisation v0.1 supports PDF, TXT/Markdown/text-like files and "
        "transcript JSON. Other formats should first use the governed IKF "
        "extraction/transcription route."
    )
