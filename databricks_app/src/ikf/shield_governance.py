"""Deterministic SHIELD Gate-1/Gate-2 governance for IKF."""

from __future__ import annotations

from dataclasses import dataclass

from .review_governance import RelationshipReviewDecision


GATE2_DECISIONS = {"VALIDATED", "REJECTED", "AMENDED"}
GATE2_STATUSES = {
    "VALIDATED": "HUMAN_VALIDATED",
    "REJECTED": "HUMAN_REJECTED",
    "AMENDED": "HUMAN_AMENDED",
}


@dataclass(frozen=True)
class ShieldReviewDecision:
    decision: str
    status: str
    proposed_label: str | None
    amended_label: str | None = None

    @property
    def authoritative_label(self) -> str | None:
        if self.decision == "VALIDATED":
            return self.proposed_label
        if self.decision == "AMENDED":
            return self.amended_label
        return None


def gate1_confirms_contributing_factor(
    review: RelationshipReviewDecision | None,
) -> bool:
    """Gate 1 passes only when the latest human review confirms CONTRIBUTED_TO."""
    return bool(
        review
        and review.status in {"HUMAN_VALIDATED", "HUMAN_AMENDED"}
        and review.effective_relationship == "CONTRIBUTED_TO"
    )


def proposal_is_current(*, proposal_gate1_review_id: str, latest_gate1_review_id: str) -> bool:
    return bool(proposal_gate1_review_id) and (
        proposal_gate1_review_id == latest_gate1_review_id
    )


def validate_grounded_proposal(
    *,
    status: str,
    proposed_label: str | None,
    cited_passage_ids,
    retrieval_passage_ids,
) -> None:
    status = str(status or "").strip().upper()
    proposed_label = str(proposed_label or "").strip() or None
    cited = set(cited_passage_ids or [])
    retrieved = set(retrieval_passage_ids or [])

    if status == "NO_GROUNDED_PROPOSAL":
        if proposed_label is not None or cited:
            raise ValueError(
                "NO_GROUNDED_PROPOSAL must not contain a classification or cited passages."
            )
        return

    if not proposed_label:
        raise ValueError("A grounded SHIELD proposal requires a proposed label.")
    if not cited:
        raise ValueError("A grounded SHIELD proposal requires supporting SHIELD passages.")
    if not cited.issubset(retrieved):
        raise ValueError("SHIELD proposal cites passages outside its deterministic retrieval set.")


def validate_gate2_review(
    *,
    decision: str,
    proposed_label: str | None,
    status: str | None = None,
    amended_label: str | None = None,
) -> ShieldReviewDecision:
    decision = str(decision or "").strip().upper()
    if decision not in GATE2_DECISIONS:
        raise ValueError(f"Unsupported SHIELD Gate-2 decision: {decision}")

    expected = GATE2_STATUSES[decision]
    actual = str(status or expected).strip().upper()
    if actual != expected:
        raise ValueError(f"Decision {decision} requires status {expected}, got {actual}.")

    proposed = str(proposed_label or "").strip() or None
    amended = str(amended_label or "").strip() or None

    if not proposed:
        raise ValueError("Gate 2 requires an existing grounded SHIELD proposal.")
    if decision == "AMENDED" and not amended:
        raise ValueError("AMENDED SHIELD review requires an amended label.")
    if decision != "AMENDED" and amended is not None:
        raise ValueError("Only AMENDED SHIELD reviews may contain an amended label.")

    return ShieldReviewDecision(
        decision=decision,
        status=actual,
        proposed_label=proposed,
        amended_label=amended,
    )
