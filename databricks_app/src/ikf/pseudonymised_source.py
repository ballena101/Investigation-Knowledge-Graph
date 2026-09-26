"""Governance helpers for reusable pseudonymised IKF source derivatives.

Pseudonymisation is a privacy transformation, not an information class. A
pseudonymised derivative keeps provenance to its parent source and receives an
explicit processing class only after review.
"""

from __future__ import annotations

from dataclasses import dataclass

PSEUDONYMISED_SOURCE_TYPE = "PSEUDONYMISED_DERIVATIVE"
PSEUDONYMISED_SOURCE_VERSION = "IKF_PSEUDONYMISED_SOURCE_V0.1"

SUPPORTED_CLASSES = frozenset({"A", "B", "C", "D"})


@dataclass(frozen=True)
class PseudonymisedSourcePolicy:
    source_class: str
    default_processing_class: str
    allowed_processing_classes: tuple[str, ...]


def processing_policy(source_class: str) -> PseudonymisedSourcePolicy:
    """Return the fail-closed class policy for a reviewed derivative.

    A/B/C sources remain in their existing processing class. A protected Class
    D source does not become public or published merely because identifiers were
    replaced. Its reviewed pseudonymised derivative may be promoted only to
    Class C in v0.1; otherwise it remains D.
    """

    source_class = str(source_class or "").strip().upper()
    if source_class not in SUPPORTED_CLASSES:
        raise ValueError("Pseudonymised sources require class A, B, C or D.")

    if source_class == "D":
        return PseudonymisedSourcePolicy(
            source_class="D",
            default_processing_class="D",
            allowed_processing_classes=("D", "C"),
        )

    return PseudonymisedSourcePolicy(
        source_class=source_class,
        default_processing_class=source_class,
        allowed_processing_classes=(source_class,),
    )


def validate_processing_class(source_class: str, processing_class: str) -> str:
    policy = processing_policy(source_class)
    value = str(processing_class or "").strip().upper()
    if value not in policy.allowed_processing_classes:
        raise ValueError(
            f"A Class {policy.source_class} source cannot create a reviewed "
            f"pseudonymised derivative for Class {value or '?'} processing in v0.1."
        )
    return value
