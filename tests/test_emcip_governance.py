import pytest

from ikf.emcip_governance import (
    validate_human_emcip_review,
    validate_proposal_selection,
)


def test_model_selection_must_be_in_shortlist():
    validate_proposal_selection(
        selected_candidate_id="c2",
        shortlist_candidate_ids=["c1", "c2"],
    )
    with pytest.raises(ValueError):
        validate_proposal_selection(
            selected_candidate_id="invented",
            shortlist_candidate_ids=["c1", "c2"],
        )


def test_no_mapping_is_allowed():
    validate_proposal_selection(
        selected_candidate_id="NO_MAPPING",
        shortlist_candidate_ids=["c1"],
    )


def test_validated_review_keeps_proposed_candidate():
    result = validate_human_emcip_review(
        decision="VALIDATED",
        proposed_candidate_id="c1",
        shortlist_candidate_ids=["c1", "c2"],
    )
    assert result.authoritative_candidate_id == "c1"


def test_rejected_review_has_no_authoritative_candidate():
    result = validate_human_emcip_review(
        decision="REJECTED",
        proposed_candidate_id="c1",
        shortlist_candidate_ids=["c1"],
    )
    assert result.authoritative_candidate_id is None


def test_amendment_must_be_from_original_shortlist():
    result = validate_human_emcip_review(
        decision="AMENDED",
        proposed_candidate_id="c1",
        amended_candidate_id="c2",
        shortlist_candidate_ids=["c1", "c2"],
    )
    assert result.authoritative_candidate_id == "c2"

    with pytest.raises(ValueError):
        validate_human_emcip_review(
            decision="AMENDED",
            proposed_candidate_id="c1",
            amended_candidate_id="outside",
            shortlist_candidate_ids=["c1", "c2"],
        )
