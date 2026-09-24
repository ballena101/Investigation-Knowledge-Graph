"""Deterministic governance helpers for EMCIP mapping proposals and review."""

from __future__ import annotations

from dataclasses import dataclass


HUMAN_DECISIONS = {"VALIDATED", "REJECTED", "AMENDED"}
HUMAN_STATUSES = {
    "VALIDATED": "HUMAN_VALIDATED",
    "REJECTED": "HUMAN_REJECTED",
    "AMENDED": "HUMAN_AMENDED",
}


@dataclass(frozen=True)
class EMCIPReviewDecision:
    decision: str
    status: str
    proposed_candidate_id: str | None
    amended_candidate_id: str | None = None

    @property
    def authoritative_candidate_id(self) -> str | None:
        if self.decision == "VALIDATED":
            return self.proposed_candidate_id
        if self.decision == "AMENDED":
            return self.amended_candidate_id
        return None


def validate_proposal_selection(*, selected_candidate_id: str | None, shortlist_candidate_ids) -> None:
    shortlist = {str(value) for value in shortlist_candidate_ids or [] if value}
    selected = str(selected_candidate_id or "").strip() or None

    if selected is None or selected == "NO_MAPPING":
        return
    if selected not in shortlist:
        raise ValueError("EMCIP proposal selected a candidate outside the governed shortlist.")


def validate_human_emcip_review(
    *,
    decision: str,
    proposed_candidate_id: str | None,
    shortlist_candidate_ids,
    status: str | None = None,
    amended_candidate_id: str | None = None,
) -> EMCIPReviewDecision:
    decision = str(decision or "").strip().upper()
    if decision not in HUMAN_DECISIONS:
        raise ValueError(f"Unsupported EMCIP human review decision: {decision}")

    expected = HUMAN_STATUSES[decision]
    actual = str(status or expected).strip().upper()
    if actual != expected:
        raise ValueError(f"Decision {decision} requires status {expected}, got {actual}.")

    shortlist = {str(value) for value in shortlist_candidate_ids or [] if value}
    proposed = str(proposed_candidate_id or "").strip() or None
    amended = str(amended_candidate_id or "").strip() or None

    validate_proposal_selection(
        selected_candidate_id=proposed,
        shortlist_candidate_ids=shortlist,
    )

    if decision == "AMENDED":
        if not amended:
            raise ValueError("AMENDED EMCIP review requires another governed shortlist candidate.")
        if amended not in shortlist:
            raise ValueError("EMCIP amendment must select a candidate from the original governed shortlist.")
        if amended == "NO_MAPPING":
            raise ValueError("AMENDED EMCIP review must select a governed taxonomy candidate, not NO_MAPPING.")
    elif amended is not None:
        raise ValueError("Only AMENDED EMCIP reviews may contain an amended candidate.")

    return EMCIPReviewDecision(
        decision=decision,
        status=actual,
        proposed_candidate_id=proposed,
        amended_candidate_id=amended,
    )
