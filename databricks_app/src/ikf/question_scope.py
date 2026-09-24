"""Deterministic QuestionRun scope and provenance validation for IKF.

This module contains pure-Python guards shared by Ask/Compare, graph-scoped
questions and local regression tests. It deliberately has no Databricks,
Neo4j or model-service dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

SUPPORTED_SCOPE_MODES = {
    "WHOLE_CASE",
    "ONE_DOCUMENT",
    "SELECTED_DOCUMENTS",
}


@dataclass(frozen=True)
class ScopeResolution:
    scope_mode: str
    effective_document_ids: tuple[str, ...]


class ScopeValidationError(ValueError):
    """Raised when a QuestionRun evidence scope is invalid."""


def _normalise_ids(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(value).strip()
                for value in (values or [])
                if str(value or "").strip()
            }
        )
    )


def resolve_effective_document_scope(
    *,
    scope_mode: str | None,
    analysis_document_ids: Iterable[str],
    scope_document_ids: Iterable[str] | None = None,
) -> ScopeResolution:
    """Resolve and validate the effective SOURCE_EVIDENCE document scope.

    Rules mirror the governed Ask contract:
    - WHOLE_CASE uses every document linked to the AnalysisGroup;
    - ONE_DOCUMENT requires exactly one selected document;
    - SELECTED_DOCUMENTS requires at least one selected document;
    - selected document IDs must be linked to the primary AnalysisGroup.
    """

    mode = str(scope_mode or "WHOLE_CASE").strip().upper()
    if mode not in SUPPORTED_SCOPE_MODES:
        raise ScopeValidationError(
            f"Unsupported QuestionRun scope_mode: {mode}"
        )

    analysis_ids = set(_normalise_ids(analysis_document_ids))
    selected_ids = set(_normalise_ids(scope_document_ids))

    if mode == "WHOLE_CASE":
        return ScopeResolution(
            scope_mode=mode,
            effective_document_ids=tuple(sorted(analysis_ids)),
        )

    if not selected_ids:
        raise ScopeValidationError(
            "Document-scoped QuestionRun has no scope_document_ids."
        )

    if mode == "ONE_DOCUMENT" and len(selected_ids) != 1:
        raise ScopeValidationError(
            "ONE_DOCUMENT scope must contain exactly one document ID."
        )

    outside_analysis = selected_ids - analysis_ids
    if outside_analysis:
        raise ScopeValidationError(
            "QuestionRun scope includes document IDs not linked to the "
            "primary AnalysisGroup: "
            + ", ".join(sorted(outside_analysis))
        )

    return ScopeResolution(
        scope_mode=mode,
        effective_document_ids=tuple(sorted(selected_ids)),
    )


def validate_retrieval_snapshot_scope(
    *,
    retrieval_passage_ids: Iterable[str] | None,
    passage_document_by_id: Mapping[str, str],
    effective_document_ids: Iterable[str],
) -> tuple[str, ...]:
    """Return retrieval passage IDs after enforcing document-scope boundaries.

    Every persisted retrieval passage must exist in the supplied passage map
    and belong to one of the effective SOURCE_EVIDENCE documents.
    """

    retrieval_ids = _normalise_ids(retrieval_passage_ids)
    allowed_documents = set(_normalise_ids(effective_document_ids))

    unknown = [
        passage_id
        for passage_id in retrieval_ids
        if passage_id not in passage_document_by_id
    ]
    if unknown:
        raise ScopeValidationError(
            "Retrieval snapshot contains unknown passage IDs: "
            + ", ".join(unknown)
        )

    outside = [
        passage_id
        for passage_id in retrieval_ids
        if passage_document_by_id[passage_id] not in allowed_documents
    ]
    if outside:
        raise ScopeValidationError(
            "Retrieval snapshot contains passage IDs outside the selected "
            "SOURCE_EVIDENCE document scope: "
            + ", ".join(outside)
        )

    return retrieval_ids


def validate_answer_passage_boundaries(
    *,
    source_evidence_passage_ids: Iterable[str] | None,
    reference_context_passage_ids: Iterable[str] | None,
    combined_passage_ids: Iterable[str] | None,
    allowed_source_passage_ids: Iterable[str],
    allowed_reference_passage_ids: Iterable[str] | None = None,
    source_retrieval_snapshot_ids: Iterable[str] | None = None,
    reference_retrieval_snapshot_ids: Iterable[str] | None = None,
    reference_context_requested: bool = False,
) -> None:
    """Validate persisted answer provenance against evidence-layer boundaries."""

    source_ids = set(_normalise_ids(source_evidence_passage_ids))
    reference_ids = set(_normalise_ids(reference_context_passage_ids))
    combined_ids = set(_normalise_ids(combined_passage_ids))
    allowed_source = set(_normalise_ids(allowed_source_passage_ids))
    allowed_reference = set(_normalise_ids(allowed_reference_passage_ids))
    source_snapshot = set(_normalise_ids(source_retrieval_snapshot_ids))
    reference_snapshot = set(_normalise_ids(reference_retrieval_snapshot_ids))

    invalid_source = source_ids - allowed_source
    if invalid_source:
        raise ScopeValidationError(
            "Answer cites SOURCE_EVIDENCE passage IDs outside the selected "
            "case scope: "
            + ", ".join(sorted(invalid_source))
        )

    if reference_ids and not reference_context_requested:
        raise ScopeValidationError(
            "Answer contains REFERENCE_CONTEXT passage IDs although reference "
            "context was not requested."
        )

    invalid_reference = reference_ids - allowed_reference
    if invalid_reference:
        raise ScopeValidationError(
            "Answer cites REFERENCE_CONTEXT passage IDs outside the governed "
            "reference corpus: "
            + ", ".join(sorted(invalid_reference))
        )

    if source_snapshot:
        outside_source_snapshot = source_ids - source_snapshot
        if outside_source_snapshot:
            raise ScopeValidationError(
                "Answer cites SOURCE_EVIDENCE passage IDs outside the primary "
                "retrieval snapshot: "
                + ", ".join(sorted(outside_source_snapshot))
            )

    if reference_snapshot:
        outside_reference_snapshot = reference_ids - reference_snapshot
        if outside_reference_snapshot:
            raise ScopeValidationError(
                "Answer cites REFERENCE_CONTEXT passage IDs outside the "
                "reference retrieval snapshot: "
                + ", ".join(sorted(outside_reference_snapshot))
            )
    elif reference_ids:
        raise ScopeValidationError(
            "Answer cites REFERENCE_CONTEXT passages but no reference retrieval "
            "snapshot is available."
        )

    overlap = source_ids & reference_ids
    if overlap:
        raise ScopeValidationError(
            "Passage IDs are attributed to both SOURCE_EVIDENCE and "
            "REFERENCE_CONTEXT: "
            + ", ".join(sorted(overlap))
        )

    expected_combined = source_ids | reference_ids
    if combined_ids != expected_combined:
        raise ScopeValidationError(
            "combined passage_ids must equal the union of SOURCE_EVIDENCE and "
            "REFERENCE_CONTEXT passage IDs."
        )


def validate_deterministic_no_support_contract(
    *,
    deterministic_answer: str | None,
    model_answer_count: int,
) -> None:
    """Fail if a deterministic no-support result also persisted model answers."""

    if str(deterministic_answer or "").strip() and model_answer_count:
        raise ScopeValidationError(
            "A deterministic no-support result must not also contain model "
            "answers."
        )
