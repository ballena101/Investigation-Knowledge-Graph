"""Pure retention calculations for IKF transient and governed content."""

from __future__ import annotations

from datetime import datetime, timedelta


CLASS_D_CONTENT_RETENTION_HOURS = 24
OTHER_CONTENT_RETENTION_HOURS = 72

PERSISTENT_SOURCE_MANAGERS = {
    "MAIRA",
    "IKF_SHIELD",
    "REFERENCE_CONTEXT",
}


def analysis_content_retention_hours(information_class: str) -> int:
    value = str(information_class or "").strip().upper()
    if value not in {"A", "B", "C", "D"}:
        raise ValueError(f"Unsupported information class: {information_class}")
    return (
        CLASS_D_CONTENT_RETENTION_HOURS
        if value == "D"
        else OTHER_CONTENT_RETENTION_HOURS
    )


def analysis_expiry_at(*, created_at: datetime, information_class: str) -> datetime:
    return created_at + timedelta(
        hours=analysis_content_retention_hours(information_class)
    )


def source_is_persistent(*, source_managed_by: str | None = None, source_role: str | None = None) -> bool:
    manager = str(source_managed_by or "").strip().upper()
    role = str(source_role or "").strip().upper()
    return (
        manager in PERSISTENT_SOURCE_MANAGERS
        or role in {"RESERVED_TAXONOMY", "REFERENCE_CONTEXT"}
    )


def direct_text_payload_should_purge(*, extraction_succeeded: bool) -> bool:
    """Raw direct-text payload is removed as soon as successful extraction completes."""
    return bool(extraction_succeeded)


def source_expiry_at(
    *,
    created_at: datetime,
    information_class: str,
    source_managed_by: str | None = None,
    source_role: str | None = None,
) -> datetime | None:
    """Return transient IKF source expiry; persistent governed sources return None."""
    if source_is_persistent(
        source_managed_by=source_managed_by,
        source_role=source_role,
    ):
        return None
    return analysis_expiry_at(
        created_at=created_at,
        information_class=information_class,
    )
