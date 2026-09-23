"""Local regression tests for IKF evidence-location provenance."""

import pytest

from ikf.evidence_locations import (
    EvidenceLocation,
    parse_evidence_location,
    parse_evidence_locations,
    validate_locations_within_documents,
)


def test_single_page_location_round_trips():
    location = parse_evidence_location("doc_123|7|7")
    assert location == EvidenceLocation("doc_123", 7, 7)
    assert location.page_label == "p. 7"
    assert location.serialise() == "doc_123|7|7"


def test_page_range_location_round_trips():
    location = parse_evidence_location("doc_123|7|9")
    assert location.page_label == "pp. 7-9"
    assert location.serialise() == "doc_123|7|9"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "doc_only",
        "doc|1",
        "doc|one|2",
        "doc|0|1",
        "doc|-1|1",
        "doc|5|4",
        "|1|1",
    ],
)
def test_malformed_location_fails_closed(value):
    with pytest.raises(ValueError):
        parse_evidence_location(value)


def test_duplicate_locations_are_removed_by_default():
    locations = parse_evidence_locations(
        ["doc_b|2|2", "doc_a|1|1", "doc_b|2|2"]
    )
    assert locations == (
        EvidenceLocation("doc_a", 1, 1),
        EvidenceLocation("doc_b", 2, 2),
    )


def test_location_scope_accepts_selected_documents():
    locations = parse_evidence_locations(["doc_a|1|2", "doc_b|4|4"])
    assert validate_locations_within_documents(
        locations,
        ["doc_a", "doc_b"],
    ) == locations


def test_location_scope_rejects_cross_document_leakage():
    locations = parse_evidence_locations(["doc_a|1|1", "doc_b|2|2"])
    with pytest.raises(ValueError, match="doc_b"):
        validate_locations_within_documents(locations, ["doc_a"])
