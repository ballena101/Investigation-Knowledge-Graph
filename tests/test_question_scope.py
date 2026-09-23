"""Tests for deterministic QuestionRun scope and provenance guards."""

import pytest

from ikf.question_scope import (
    ScopeValidationError,
    resolve_effective_document_scope,
    validate_answer_passage_boundaries,
    validate_deterministic_no_support_contract,
    validate_retrieval_snapshot_scope,
)


def test_whole_case_uses_all_analysis_documents():
    result = resolve_effective_document_scope(
        scope_mode="WHOLE_CASE",
        analysis_document_ids=["doc_b", "doc_a"],
    )
    assert result.effective_document_ids == ("doc_a", "doc_b")


def test_one_document_requires_exactly_one_selected_document():
    with pytest.raises(ScopeValidationError):
        resolve_effective_document_scope(
            scope_mode="ONE_DOCUMENT",
            analysis_document_ids=["doc_a", "doc_b"],
            scope_document_ids=["doc_a", "doc_b"],
        )


def test_selected_documents_must_belong_to_analysis():
    with pytest.raises(ScopeValidationError):
        resolve_effective_document_scope(
            scope_mode="SELECTED_DOCUMENTS",
            analysis_document_ids=["doc_a", "doc_b"],
            scope_document_ids=["doc_b", "doc_c"],
        )


def test_selected_documents_resolve_deterministically():
    result = resolve_effective_document_scope(
        scope_mode="SELECTED_DOCUMENTS",
        analysis_document_ids=["doc_a", "doc_b", "doc_c"],
        scope_document_ids=["doc_c", "doc_a", "doc_a"],
    )
    assert result.effective_document_ids == ("doc_a", "doc_c")


def test_retrieval_snapshot_cannot_escape_document_scope():
    with pytest.raises(ScopeValidationError):
        validate_retrieval_snapshot_scope(
            retrieval_passage_ids=["p1", "p2"],
            passage_document_by_id={
                "p1": "doc_a",
                "p2": "doc_b",
            },
            effective_document_ids=["doc_a"],
        )


def test_retrieval_snapshot_rejects_unknown_passage():
    with pytest.raises(ScopeValidationError):
        validate_retrieval_snapshot_scope(
            retrieval_passage_ids=["p_unknown"],
            passage_document_by_id={"p1": "doc_a"},
            effective_document_ids=["doc_a"],
        )


def test_answer_source_ids_must_stay_inside_case_scope():
    with pytest.raises(ScopeValidationError):
        validate_answer_passage_boundaries(
            source_evidence_passage_ids=["p1", "p_out"],
            reference_context_passage_ids=[],
            combined_passage_ids=["p1", "p_out"],
            allowed_source_passage_ids=["p1", "p2"],
        )


def test_reference_ids_require_reference_context_request():
    with pytest.raises(ScopeValidationError):
        validate_answer_passage_boundaries(
            source_evidence_passage_ids=["p1"],
            reference_context_passage_ids=["r1"],
            combined_passage_ids=["p1", "r1"],
            allowed_source_passage_ids=["p1"],
            allowed_reference_passage_ids=["r1"],
            reference_retrieval_snapshot_ids=["r1"],
            reference_context_requested=False,
        )


def test_answer_ids_must_stay_inside_retrieval_snapshots():
    with pytest.raises(ScopeValidationError):
        validate_answer_passage_boundaries(
            source_evidence_passage_ids=["p2"],
            reference_context_passage_ids=[],
            combined_passage_ids=["p2"],
            allowed_source_passage_ids=["p1", "p2"],
            source_retrieval_snapshot_ids=["p1"],
        )


def test_reference_layer_requires_reference_snapshot():
    with pytest.raises(ScopeValidationError):
        validate_answer_passage_boundaries(
            source_evidence_passage_ids=["p1"],
            reference_context_passage_ids=["r1"],
            combined_passage_ids=["p1", "r1"],
            allowed_source_passage_ids=["p1"],
            allowed_reference_passage_ids=["r1"],
            reference_context_requested=True,
        )


def test_source_and_reference_layers_cannot_share_passage_id():
    with pytest.raises(ScopeValidationError):
        validate_answer_passage_boundaries(
            source_evidence_passage_ids=["shared"],
            reference_context_passage_ids=["shared"],
            combined_passage_ids=["shared"],
            allowed_source_passage_ids=["shared"],
            allowed_reference_passage_ids=["shared"],
            source_retrieval_snapshot_ids=["shared"],
            reference_retrieval_snapshot_ids=["shared"],
            reference_context_requested=True,
        )


def test_combined_ids_equal_union_of_two_layers():
    validate_answer_passage_boundaries(
        source_evidence_passage_ids=["p1", "p2"],
        reference_context_passage_ids=["r1"],
        combined_passage_ids=["r1", "p2", "p1"],
        allowed_source_passage_ids=["p1", "p2"],
        allowed_reference_passage_ids=["r1", "r2"],
        source_retrieval_snapshot_ids=["p1", "p2"],
        reference_retrieval_snapshot_ids=["r1"],
        reference_context_requested=True,
    )


def test_combined_ids_mismatch_is_rejected():
    with pytest.raises(ScopeValidationError):
        validate_answer_passage_boundaries(
            source_evidence_passage_ids=["p1"],
            reference_context_passage_ids=["r1"],
            combined_passage_ids=["p1"],
            allowed_source_passage_ids=["p1"],
            allowed_reference_passage_ids=["r1"],
            source_retrieval_snapshot_ids=["p1"],
            reference_retrieval_snapshot_ids=["r1"],
            reference_context_requested=True,
        )


def test_deterministic_no_support_cannot_have_model_answers():
    with pytest.raises(ScopeValidationError):
        validate_deterministic_no_support_contract(
            deterministic_answer="No supported relationship was found.",
            model_answer_count=1,
        )


def test_deterministic_no_support_without_model_answer_is_valid():
    validate_deterministic_no_support_contract(
        deterministic_answer="No supported relationship was found.",
        model_answer_count=0,
    )
