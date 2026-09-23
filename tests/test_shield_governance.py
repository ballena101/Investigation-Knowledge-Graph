import pytest

from ikf.review_governance import validate_human_relationship_review
from ikf.shield_governance import (
    gate1_confirms_contributing_factor,
    proposal_is_current,
    validate_gate2_review,
    validate_grounded_proposal,
)


def test_gate1_requires_human_confirmed_contributed_to():
    validated = validate_human_relationship_review(
        relationship="CONTRIBUTED_TO",
        decision="VALIDATED",
    )
    assert gate1_confirms_contributing_factor(validated)

    chronology = validate_human_relationship_review(
        relationship="FOLLOWED_BY",
        decision="VALIDATED",
    )
    assert not gate1_confirms_contributing_factor(chronology)


def test_gate1_amendment_to_contributed_to_is_eligible():
    amended = validate_human_relationship_review(
        relationship="FOLLOWED_BY",
        decision="AMENDED",
        amended_relationship="CONTRIBUTED_TO",
    )
    assert gate1_confirms_contributing_factor(amended)


def test_stale_gate1_proposal_is_not_current():
    assert proposal_is_current(
        proposal_gate1_review_id="r2",
        latest_gate1_review_id="r2",
    )
    assert not proposal_is_current(
        proposal_gate1_review_id="r1",
        latest_gate1_review_id="r2",
    )


def test_grounded_proposal_must_stay_inside_retrieval_set():
    validate_grounded_proposal(
        status="PROPOSED",
        proposed_label="Human factors",
        cited_passage_ids=["p1"],
        retrieval_passage_ids=["p1", "p2"],
    )

    with pytest.raises(ValueError):
        validate_grounded_proposal(
            status="PROPOSED",
            proposed_label="Human factors",
            cited_passage_ids=["p3"],
            retrieval_passage_ids=["p1", "p2"],
        )


def test_no_grounded_proposal_carries_no_classification():
    validate_grounded_proposal(
        status="NO_GROUNDED_PROPOSAL",
        proposed_label=None,
        cited_passage_ids=[],
        retrieval_passage_ids=["p1"],
    )


def test_gate2_rejected_proposal_has_no_authoritative_label():
    result = validate_gate2_review(
        decision="REJECTED",
        proposed_label="Human factors",
    )
    assert result.authoritative_label is None


def test_gate2_amendment_requires_label():
    with pytest.raises(ValueError):
        validate_gate2_review(
            decision="AMENDED",
            proposed_label="Human factors",
        )

    result = validate_gate2_review(
        decision="AMENDED",
        proposed_label="Human factors",
        amended_label="Organisational factors",
    )
    assert result.authoritative_label == "Organisational factors"
