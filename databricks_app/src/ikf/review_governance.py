"""Deterministic governance rules for IKF relationship review.

These helpers encode existing project policy only. They do not persist reviews
and do not modify graph relationships.
"""

from __future__ import annotations

from dataclasses import dataclass


HUMAN_DECISIONS = {"VALIDATED", "REJECTED", "AMENDED"}
HUMAN_STATUSES = {
    "VALIDATED": "HUMAN_VALIDATED",
    "REJECTED": "HUMAN_REJECTED",
    "AMENDED": "HUMAN_AMENDED",
}

# Structural/plumbing relationships are excluded from semantic human review.
STRUCTURAL_RELATIONSHIPS = {
    "INVOLVED_IN",
    "HAS_SOURCE",
    "HAS_MODEL_RUN",
    "HAS_QUESTION_RUN",
    "HAS_MODEL_ANSWER",
    "HAS_REVIEW",
}


@dataclass(frozen=True)
class RelationshipReviewDecision:
    decision: str
    status: str
    relationship: str
    amended_relationship: str | None = None

    @property
    def effective_relationship(self) -> str | None:
        if self.decision == "REJECTED":
            return None
        if self.decision == "AMENDED":
            return self.amended_relationship
        return self.relationship


def is_semantic_relationship(relationship: str) -> bool:
    value = str(relationship or "").strip().upper()
    return bool(value) and value not in STRUCTURAL_RELATIONSHIPS


def validate_human_relationship_review(
    *,
    relationship: str,
    decision: str,
    status: str | None = None,
    amended_relationship: str | None = None,
) -> RelationshipReviewDecision:
    relationship = str(relationship or "").strip().upper()
    decision = str(decision or "").strip().upper()
    amended = (
        str(amended_relationship or "").strip().upper() or None
    )

    if not is_semantic_relationship(relationship):
        raise ValueError("Structural relationships are not eligible for semantic human review.")

    if decision not in HUMAN_DECISIONS:
        raise ValueError(f"Unsupported human relationship review decision: {decision}")

    expected_status = HUMAN_STATUSES[decision]
    actual_status = str(status or expected_status).strip().upper()
    if actual_status != expected_status:
        raise ValueError(
            f"Decision {decision} requires status {expected_status}, got {actual_status}."
        )

    if decision == "AMENDED":
        if not amended:
            raise ValueError("AMENDED relationship review requires an amended relationship.")
        if not is_semantic_relationship(amended):
            raise ValueError("A relationship amendment must resolve to a semantic relationship.")
    elif amended is not None:
        raise ValueError("Only AMENDED reviews may contain an amended relationship.")

    return RelationshipReviewDecision(
        decision=decision,
        status=actual_status,
        relationship=relationship,
        amended_relationship=amended,
    )


def latest_review(reviews):
    """Return the last review in append-only order, or None for no reviews."""
    values = list(reviews or [])
    return values[-1] if values else None
