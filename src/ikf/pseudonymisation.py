"""Deterministic pseudonymisation helpers for IKF.

V0.1 deliberately separates detection from replacement. Structured identifiers
are detected with deterministic patterns. Free-form names or terms can be
supplied explicitly by an authorised user and are then replaced consistently.
No LLM is called from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

PSEUDONYMISATION_VERSION = "IKF_PSEUDONYMISATION_V0.1"

DEFAULT_CATEGORIES = ("PERSON", "EMAIL", "PHONE", "PERSONAL_ID")
OPTIONAL_CATEGORIES = (
    "ORGANISATION",
    "VESSEL",
    "IMO",
    "MMSI",
    "PORT",
    "LOCATION",
    "NATIONALITY",
    "ROLE",
    "DATE_TIME",
    "CASE_REFERENCE",
)
ALL_CATEGORIES = DEFAULT_CATEGORIES + OPTIONAL_CATEGORIES

_PATTERNS = {
    "EMAIL": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "PHONE": re.compile(r"(?<!\w)(?:\+?\d[\d .()\-/]{6,}\d)(?!\w)"),
    "IMO": re.compile(r"\bIMO\s*[:#-]?\s*\d{7}\b", re.IGNORECASE),
    "MMSI": re.compile(r"\bMMSI\s*[:#-]?\s*\d{9}\b", re.IGNORECASE),
    "PERSONAL_ID": re.compile(
        r"\b(?:passport|national\s+id|identity\s+card|id\s+number)"
        r"\s*[:#-]?\s*[A-Z0-9-]{4,}\b",
        re.IGNORECASE,
    ),
    "CASE_REFERENCE": re.compile(
        r"\b(?:case|file|reference|ref\.?|investigation)\s*(?:no\.?|number|#)?"
        r"\s*[:#-]?\s*[A-Z0-9][A-Z0-9._/-]{3,}\b",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class Replacement:
    category: str
    original: str
    pseudonym: str
    start: int
    end: int
    detected_by: str


def _normalise_categories(categories: Iterable[str]) -> tuple[str, ...]:
    selected = []
    for category in categories:
        value = str(category or "").strip().upper()
        if value in ALL_CATEGORIES and value not in selected:
            selected.append(value)
    return tuple(selected)


def _manual_terms(manual_terms: dict[str, Iterable[str]] | None):
    prepared: dict[str, list[str]] = {}
    for category, terms in (manual_terms or {}).items():
        key = str(category or "").strip().upper()
        if key not in ALL_CATEGORIES:
            continue
        cleaned = []
        for term in terms or []:
            value = str(term or "").strip()
            if value and value not in cleaned:
                cleaned.append(value)
        if cleaned:
            prepared[key] = cleaned
    return prepared


def pseudonymise_text(
    text: str,
    *,
    categories: Iterable[str] = DEFAULT_CATEGORIES,
    manual_terms: dict[str, Iterable[str]] | None = None,
):
    """Return deterministic pseudonymised text plus replacement metadata.

    Structured categories are auto-detected by regex. Contextual categories
    such as PERSON are only replaced when supplied in ``manual_terms`` in v0.1.
    Overlapping matches are resolved by preferring the longest candidate.
    """

    source = str(text or "")
    selected = _normalise_categories(categories)
    manual = _manual_terms(manual_terms)

    candidates = []
    for category in selected:
        pattern = _PATTERNS.get(category)
        if pattern:
            for match in pattern.finditer(source):
                candidates.append(
                    (match.start(), match.end(), category, match.group(0), "RULE")
                )
        for term in manual.get(category, []):
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            for match in pattern.finditer(source):
                candidates.append(
                    (match.start(), match.end(), category, match.group(0), "MANUAL")
                )

    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
    accepted = []
    occupied_until = -1
    for candidate in candidates:
        start, end, *_ = candidate
        if start < occupied_until:
            continue
        accepted.append(candidate)
        occupied_until = end

    counters: dict[str, int] = {}
    identity_map: dict[tuple[str, str], str] = {}
    replacements: list[Replacement] = []

    def token_for(category: str, original: str) -> str:
        key = (category, original.casefold())
        if key not in identity_map:
            counters[category] = counters.get(category, 0) + 1
            identity_map[key] = f"{category}_{counters[category]:03d}"
        return identity_map[key]

    chunks = []
    cursor = 0
    for start, end, category, original, detected_by in accepted:
        chunks.append(source[cursor:start])
        token = token_for(category, original)
        chunks.append(token)
        replacements.append(
            Replacement(
                category=category,
                original=original,
                pseudonym=token,
                start=start,
                end=end,
                detected_by=detected_by,
            )
        )
        cursor = end
    chunks.append(source[cursor:])

    return {
        "version": PSEUDONYMISATION_VERSION,
        "text": "".join(chunks),
        "categories": selected,
        "replacements": replacements,
        "mapping": {
            replacement.pseudonym: replacement.original
            for replacement in replacements
        },
    }
