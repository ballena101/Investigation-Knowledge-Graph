import pytest

from ikf.review_governance import (
    is_semantic_relationship,
    latest_review,
    validate_human_relationship_review,
)


def test_structural_relationship_is_not_semantic():
    assert not is_semantic_relationship("INVOLVED_IN")


def test_followed_by_is_reviewable_without_implying_causality():
    assert is_semantic_relationship("FOLLOWED_BY")
    result = validate_human_relationship_review(
        relationship="FOLLOWED_BY",
        decision="VALIDATED",
    )
    assert result.effective_relationship == "FOLLOWED_BY"


def test_rejected_relationship_has_no_effective_relationship():
    result = validate_human_relationship_review(
        relationship="CONTRIBUTED_TO",
        decision="REJECTED",
    )
    assert result.effective_relationship is None


def test_amendment_requires_semantic_relationship():
    result = validate_human_relationship_review(
        relationship="FOLLOWED_BY",
        decision="AMENDED",
        amended_relationship="CONTRIBUTED_TO",
    )
    assert result.status == "HUMAN_AMENDED"
    assert result.effective_relationship == "CONTRIBUTED_TO"

    with pytest.raises(ValueError):
        validate_human_relationship_review(
            relationship="FOLLOWED_BY",
            decision="AMENDED",
            amended_relationship="INVOLVED_IN",
        )


def test_status_must_match_human_decision():
    with pytest.raises(ValueError):
        validate_human_relationship_review(
            relationship="CONTRIBUTED_TO",
            decision="VALIDATED",
            status="ASSISTANT_VALIDATED",
        )


def test_append_only_latest_review_is_last_record():
    assert latest_review(["r1", "r2", "r3"]) == "r3"
    assert latest_review([]) is None
