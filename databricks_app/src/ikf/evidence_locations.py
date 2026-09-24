"""Pure-Python evidence-location utilities for IKF.

IKF persists machine-readable evidence locations in the compact form:

    document_id|page_start|page_end

This module validates and parses that contract without requiring Databricks,
Neo4j, Streamlit or a model endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True, order=True)
class EvidenceLocation:
    document_id: str
    page_start: int
    page_end: int

    @property
    def page_label(self) -> str:
        if self.page_start == self.page_end:
            return f"p. {self.page_start}"
        return f"pp. {self.page_start}-{self.page_end}"

    def serialise(self) -> str:
        return f"{self.document_id}|{self.page_start}|{self.page_end}"


def parse_evidence_location(value: str) -> EvidenceLocation:
    """Parse one persisted IKF evidence-location value.

    Fail closed on malformed identifiers, non-integer pages, page zero/negative
    values or reversed page ranges.
    """

    raw = str(value or "").strip()
    parts = raw.split("|")
    if len(parts) != 3:
        raise ValueError(
            "Evidence location must use document_id|page_start|page_end"
        )

    document_id = parts[0].strip()
    if not document_id:
        raise ValueError("Evidence location document_id cannot be empty")

    try:
        page_start = int(parts[1])
        page_end = int(parts[2])
    except ValueError as exc:
        raise ValueError("Evidence location pages must be integers") from exc

    if page_start < 1 or page_end < 1:
        raise ValueError("Evidence location pages must be positive integers")
    if page_end < page_start:
        raise ValueError("Evidence location page_end cannot precede page_start")

    return EvidenceLocation(
        document_id=document_id,
        page_start=page_start,
        page_end=page_end,
    )


def parse_evidence_locations(
    values: Iterable[str],
    *,
    deduplicate: bool = True,
) -> tuple[EvidenceLocation, ...]:
    parsed = tuple(parse_evidence_location(value) for value in values)
    if not deduplicate:
        return parsed
    return tuple(sorted(set(parsed)))


def validate_locations_within_documents(
    locations: Iterable[EvidenceLocation],
    allowed_document_ids: Iterable[str],
) -> tuple[EvidenceLocation, ...]:
    """Return locations only when every citation stays inside the scope."""

    allowed = {
        str(document_id).strip()
        for document_id in allowed_document_ids
        if str(document_id).strip()
    }

    locations = tuple(locations)
    outside = [
        location
        for location in locations
        if location.document_id not in allowed
    ]
    if outside:
        outside_ids = sorted({location.document_id for location in outside})
        raise ValueError(
            "Evidence location escaped the allowed document scope: "
            + ", ".join(outside_ids)
        )

    return locations
