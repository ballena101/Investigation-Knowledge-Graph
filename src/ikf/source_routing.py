"""Deterministic source-routing rules for IKF.

The module contains pure-Python policy rules so catalogue/source ownership can
be regression-tested without Databricks.

Current ownership boundary:
- Class B published investigation material -> MAIRA-managed sources.
- Classes A/C/D -> IKF-managed sources.
- Direct text is an IKF ingress and is not constrained by the document
  catalogue ownership filter.
- Reviewed IKF pseudonymised derivatives are reusable governed sources. They
  remain separate from their parent source and are visible only in their
  explicitly approved processing class.
- if an IKF SourceDocument has an explicit information_class, it is visible
  only in that class. Legacy documents without an explicit class retain the
  existing ownership-only behaviour.

The functions here do not access Databricks, Neo4j or model endpoints.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


DOCUMENT_INPUT = "DOCUMENTS"
DIRECT_TEXT_INPUT = "DIRECT_TEXT"

MAIRA_MANAGER = "MAIRA"
IKF_MANAGER = "IKF"
PSEUDONYMISED_DERIVATIVE = "PSEUDONYMISED_DERIVATIVE"

SUPPORTED_INFORMATION_CLASSES = frozenset({"A", "B", "C", "D"})
SUPPORTED_INPUT_MODES = frozenset({DOCUMENT_INPUT, DIRECT_TEXT_INPUT})


@dataclass(frozen=True)
class SourceRoute:
    information_class: str
    input_mode: str
    allowed_source_managers: tuple[str, ...]
    catalogue_scope: str


def normalise_information_class(value: str) -> str:
    information_class = str(value or "").strip().upper()
    if information_class not in SUPPORTED_INFORMATION_CLASSES:
        raise ValueError(
            f"Unsupported information class: {value!r}. "
            "Expected one of A, B, C or D."
        )
    return information_class


def normalise_input_mode(value: str) -> str:
    raw = str(value or "").strip().upper().replace(" ", "_")
    aliases = {
        "DOCUMENT": DOCUMENT_INPUT,
        "DOCUMENTS": DOCUMENT_INPUT,
        "DIRECT_TEXT": DIRECT_TEXT_INPUT,
        "DIRECTTEXT": DIRECT_TEXT_INPUT,
    }
    try:
        return aliases[raw]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported input mode: {value!r}. "
            "Expected Documents or Direct text."
        ) from exc


def resolve_source_route(
    information_class: str,
    input_mode: str,
) -> SourceRoute:
    """Return the governed source ownership route for an analysis ingress."""

    information_class = normalise_information_class(information_class)
    input_mode = normalise_input_mode(input_mode)

    if input_mode == DIRECT_TEXT_INPUT:
        return SourceRoute(
            information_class=information_class,
            input_mode=input_mode,
            allowed_source_managers=(IKF_MANAGER,),
            catalogue_scope="DIRECT_TEXT_IKF_INGRESS",
        )

    if information_class == "B":
        return SourceRoute(
            information_class=information_class,
            input_mode=input_mode,
            allowed_source_managers=(MAIRA_MANAGER,),
            catalogue_scope="MAIRA_PUBLISHED_INVESTIGATION_MATERIAL",
        )

    return SourceRoute(
        information_class=information_class,
        input_mode=input_mode,
        allowed_source_managers=(IKF_MANAGER,),
        catalogue_scope="IKF_MANAGED_DOCUMENTS",
    )


def filter_catalogue_rows(
    rows: Iterable[dict],
    *,
    information_class: str,
) -> list[dict]:
    """Filter catalogue rows by source owner and explicit class when present.

    Pseudonymised derivatives are special only in source ownership: they are
    created and managed by IKF, but may retain Class B processing when derived
    from already-published Class B material. They must have explicit class and
    REVIEWED/APPROVED status; an unreviewed derivative never enters a selector.
    """

    information_class = normalise_information_class(information_class)
    route = resolve_source_route(information_class, DOCUMENT_INPUT)
    allowed = set(route.allowed_source_managers)

    filtered = []
    for row in rows:
        manager = str(row.get("source_managed_by") or "").strip().upper()
        source_type = str(row.get("source_type") or "").strip().upper()
        explicit_class = str(row.get("information_class") or "").strip().upper()

        is_reviewed_derivative = (
            source_type == PSEUDONYMISED_DERIVATIVE
            and manager == IKF_MANAGER
            and explicit_class == information_class
            and str(row.get("pseudonymisation_review_status") or "").strip().upper()
            in {"REVIEWED", "APPROVED"}
        )

        if manager not in allowed and not is_reviewed_derivative:
            continue

        if explicit_class and explicit_class != information_class:
            continue

        filtered.append(row)

    return filtered
