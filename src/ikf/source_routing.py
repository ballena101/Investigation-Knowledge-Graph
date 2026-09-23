"""Deterministic source-routing rules for IKF.

The module contains pure-Python policy rules so catalogue/source ownership can
be regression-tested without Databricks.

Current ownership boundary:
- Class B published investigation material -> MAIRA-managed sources.
- Classes A/C/D -> IKF-managed sources.
- Direct text is an IKF ingress and is not constrained by the document
  catalogue ownership filter.

The functions here do not access Databricks, Neo4j or model endpoints.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


DOCUMENT_INPUT = "DOCUMENTS"
DIRECT_TEXT_INPUT = "DIRECT_TEXT"

MAIRA_MANAGER = "MAIRA"
IKF_MANAGER = "IKF"

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
    """Filter document-catalogue rows by the authoritative ownership rule.

    This function intentionally applies only to document catalogue rows.
    Direct-text ingress has no catalogue to filter.
    """

    route = resolve_source_route(information_class, DOCUMENT_INPUT)
    allowed = set(route.allowed_source_managers)

    return [
        row
        for row in rows
        if str(row.get("source_managed_by") or "").strip().upper() in allowed
    ]
