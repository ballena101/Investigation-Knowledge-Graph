"""Local regression tests for IKF source ownership routing."""

import pytest

from ikf.source_routing import (
    DIRECT_TEXT_INPUT,
    IKF_MANAGER,
    MAIRA_MANAGER,
    filter_catalogue_rows,
    resolve_source_route,
)


def test_class_b_documents_route_to_maira_only():
    route = resolve_source_route("B", "Documents")
    assert route.allowed_source_managers == (MAIRA_MANAGER,)
    assert route.catalogue_scope == "MAIRA_PUBLISHED_INVESTIGATION_MATERIAL"


@pytest.mark.parametrize("information_class", ["A", "C", "D"])
def test_non_b_documents_route_to_ikf_only(information_class):
    route = resolve_source_route(information_class, "Documents")
    assert route.allowed_source_managers == (IKF_MANAGER,)
    assert route.catalogue_scope == "IKF_MANAGED_DOCUMENTS"


@pytest.mark.parametrize("information_class", ["A", "B", "C", "D"])
def test_direct_text_remains_ikf_ingress(information_class):
    route = resolve_source_route(information_class, "Direct text")
    assert route.input_mode == DIRECT_TEXT_INPUT
    assert route.allowed_source_managers == (IKF_MANAGER,)
    assert route.catalogue_scope == "DIRECT_TEXT_IKF_INGRESS"


def test_catalogue_filter_prefers_maira_for_class_b():
    rows = [
        {"document_id": "maira-1", "source_managed_by": "MAIRA"},
        {"document_id": "ikf-1", "source_managed_by": "IKF"},
        {"document_id": "unknown-1", "source_managed_by": None},
    ]

    filtered = filter_catalogue_rows(rows, information_class="B")
    assert [row["document_id"] for row in filtered] == ["maira-1"]


def test_catalogue_filter_uses_ikf_for_class_a():
    rows = [
        {"document_id": "maira-1", "source_managed_by": "MAIRA"},
        {"document_id": "ikf-1", "source_managed_by": "ikf"},
    ]

    filtered = filter_catalogue_rows(rows, information_class="A")
    assert [row["document_id"] for row in filtered] == ["ikf-1"]


def test_explicit_class_d_transcript_is_only_visible_in_class_d():
    rows = [
        {
            "document_id": "legacy-ikf",
            "source_managed_by": "IKF",
            "information_class": None,
        },
        {
            "document_id": "validated-transcript",
            "source_managed_by": "IKF",
            "information_class": "D",
            "source_type": "TXT",
            "document_kind": "TRANSCRIPT",
        },
    ]

    class_a = filter_catalogue_rows(rows, information_class="A")
    class_c = filter_catalogue_rows(rows, information_class="C")
    class_d = filter_catalogue_rows(rows, information_class="D")

    assert [row["document_id"] for row in class_a] == ["legacy-ikf"]
    assert [row["document_id"] for row in class_c] == ["legacy-ikf"]
    assert [row["document_id"] for row in class_d] == [
        "legacy-ikf",
        "validated-transcript",
    ]


def test_explicit_class_mismatch_fails_closed_even_with_correct_manager():
    rows = [
        {
            "document_id": "protected",
            "source_managed_by": "IKF",
            "information_class": "D",
        }
    ]
    assert filter_catalogue_rows(rows, information_class="A") == []


def test_invalid_information_class_fails_closed():
    with pytest.raises(ValueError):
        resolve_source_route("E", "Documents")


def test_invalid_input_mode_fails_closed():
    with pytest.raises(ValueError):
        resolve_source_route("B", "Spreadsheet")
