"""Deterministic information-class pre-screen for IKF.

This is a fail-closed routing aid, not a legal classifier.

The rules identify strong indicators that raw/direct or IKF-managed material may
contain Class-D / Article-9-sensitive investigation records. Published MAIRA
investigation reports are governed separately as Class B and are not escalated
merely because they discuss protected evidence types in a published report.

No LLM is used. The detector returns rule IDs and counts, not matched source
text, so prescreen audit metadata does not reproduce protected content.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Iterable


PRESCREEN_VERSION = "IKF_CLASSIFICATION_PRESCREEN_V0.1"


@dataclass(frozen=True)
class PrescreenFinding:
    rule_id: str
    label: str
    match_count: int
    requires_class: str = "D"


@dataclass(frozen=True)
class PrescreenResult:
    version: str
    required_class: str | None
    findings: tuple[PrescreenFinding, ...]

    @property
    def blocked_for_non_d(self) -> bool:
        return self.required_class == "D"

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(
            finding.rule_id
            for finding in self.findings
        )


_RULES: tuple[
    tuple[str, str, re.Pattern[str]], ...
] = (
    (
        "PERSONAL_ID_RECORD",
        "passport/national identity record",
        re.compile(
            r"\b(?:passport|national\s+id|identity\s+card|"
            r"id\s+number)\s*[:#-]?\s*[A-Z0-9-]{4,}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "WITNESS_RECORD",
        "witness statement/interview record",
        re.compile(
            r"\b(?:witness\s+(?:statement|interview|testimony)|"
            r"statement\s+of\s+witness)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "VDR_RAW_RECORD",
        "VDR raw recording/transcript",
        re.compile(
            r"\b(?:(?:vdr|voyage\s+data\s+recorder)\s+"
            r"(?:audio|recording|transcript|conversation)|"
            r"(?:audio|recording|transcript)\s+from\s+(?:the\s+)?vdr)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "VTS_RAW_RECORD",
        "VTS raw recording/transcript",
        re.compile(
            r"\b(?:vts|vessel\s+traffic\s+service)\s+"
            r"(?:audio|recording|transcript|conversation)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "INVESTIGATOR_WORKING_RECORD",
        "investigator notes/draft working record",
        re.compile(
            r"\b(?:investigator(?:'s)?\s+(?:notes?|draft)|"
            r"investigation\s+working\s+notes?|"
            r"draft\s+(?:investigation\s+)?report)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "MEDICAL_RECORD",
        "medical/health record",
        re.compile(
            r"\b(?:medical\s+(?:record|report|history)|"
            r"health\s+record|patient\s+record)\b",
            re.IGNORECASE,
        ),
    ),
)


_METADATA_RULES: tuple[
    tuple[str, str, re.Pattern[str]], ...
] = (
    (
        "WITNESS_RECORD_METADATA",
        "witness record filename/title",
        re.compile(
            r"(?:witness[_\s-]*(?:statement|interview)|"
            r"statement[_\s-]*of[_\s-]*witness)",
            re.IGNORECASE,
        ),
    ),
    (
        "VDR_RAW_RECORD_METADATA",
        "VDR raw-record filename/title",
        re.compile(
            r"(?:vdr|voyage[_\s-]*data[_\s-]*recorder)"
            r".*(?:audio|recording|transcript)",
            re.IGNORECASE,
        ),
    ),
    (
        "VTS_RAW_RECORD_METADATA",
        "VTS raw-record filename/title",
        re.compile(
            r"(?:vts|vessel[_\s-]*traffic[_\s-]*service)"
            r".*(?:audio|recording|transcript)",
            re.IGNORECASE,
        ),
    ),
    (
        "INVESTIGATOR_WORKING_RECORD_METADATA",
        "investigator working-record filename/title",
        re.compile(
            r"(?:investigator[_\s-]*notes?|"
            r"investigation[_\s-]*working[_\s-]*notes?|"
            r"draft[_\s-]*(?:investigation[_\s-]*)?report)",
            re.IGNORECASE,
        ),
    ),
    (
        "MEDICAL_RECORD_METADATA",
        "medical-record filename/title",
        re.compile(
            r"(?:medical|health|patient)[_\s-]*(?:record|report|history)",
            re.IGNORECASE,
        ),
    ),
)


def _evaluate(
    values: Iterable[str],
    rules,
) -> tuple[PrescreenFinding, ...]:
    counts: dict[
        tuple[str, str], int
    ] = {}

    for raw_value in values:
        value = str(raw_value or "")
        if not value:
            continue

        for rule_id, label, pattern in rules:
            count = len(
                pattern.findall(value)
            )
            if not count:
                continue

            key = (
                rule_id,
                label,
            )
            counts[key] = (
                counts.get(key, 0)
                + count
            )

    return tuple(
        PrescreenFinding(
            rule_id=rule_id,
            label=label,
            match_count=count,
        )
        for (
            rule_id,
            label,
        ), count in sorted(
            counts.items()
        )
    )


def prescreen_text(
    text: str,
) -> PrescreenResult:
    findings = _evaluate(
        [text],
        _RULES,
    )

    return PrescreenResult(
        version=PRESCREEN_VERSION,
        required_class=(
            "D"
            if findings
            else None
        ),
        findings=findings,
    )


def prescreen_texts(
    texts: Iterable[str],
) -> PrescreenResult:
    findings = _evaluate(
        texts,
        _RULES,
    )

    return PrescreenResult(
        version=PRESCREEN_VERSION,
        required_class=(
            "D"
            if findings
            else None
        ),
        findings=findings,
    )


def prescreen_metadata(
    values: Iterable[str],
) -> PrescreenResult:
    findings = _evaluate(
        values,
        _METADATA_RULES,
    )

    return PrescreenResult(
        version=PRESCREEN_VERSION,
        required_class=(
            "D"
            if findings
            else None
        ),
        findings=findings,
    )


def combine_results(
    *results: PrescreenResult,
) -> PrescreenResult:
    combined: dict[
        tuple[str, str], int
    ] = {}

    for result in results:
        for finding in result.findings:
            key = (
                finding.rule_id,
                finding.label,
            )
            combined[key] = (
                combined.get(key, 0)
                + finding.match_count
            )

    findings = tuple(
        PrescreenFinding(
            rule_id=rule_id,
            label=label,
            match_count=count,
        )
        for (
            rule_id,
            label,
        ), count in sorted(
            combined.items()
        )
    )

    return PrescreenResult(
        version=PRESCREEN_VERSION,
        required_class=(
            "D"
            if findings
            else None
        ),
        findings=findings,
    )
