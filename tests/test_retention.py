from datetime import datetime, timezone

import pytest

from ikf.retention import (
    analysis_content_retention_hours,
    analysis_expiry_at,
    direct_text_payload_should_purge,
    source_expiry_at,
    source_is_persistent,
)


def test_class_d_retention_is_24_hours_and_others_72():
    assert analysis_content_retention_hours("D") == 24
    for value in ("A", "B", "C"):
        assert analysis_content_retention_hours(value) == 72


def test_analysis_expiry_is_deterministic():
    created = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    assert analysis_expiry_at(
        created_at=created,
        information_class="D",
    ).hour == 12
    assert (
        analysis_expiry_at(created_at=created, information_class="D")
        - created
    ).total_seconds() == 24 * 3600


def test_persistent_governed_sources_have_no_transient_expiry():
    created = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    assert source_is_persistent(source_managed_by="MAIRA")
    assert source_is_persistent(source_managed_by="IKF_SHIELD")
    assert source_is_persistent(source_role="REFERENCE_CONTEXT")
    assert source_expiry_at(
        created_at=created,
        information_class="B",
        source_managed_by="MAIRA",
    ) is None


def test_transient_ikf_source_uses_information_class_retention():
    created = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    expiry = source_expiry_at(
        created_at=created,
        information_class="C",
        source_managed_by="IKF",
    )
    assert (expiry - created).total_seconds() == 72 * 3600


def test_direct_text_payload_purges_after_successful_extraction():
    assert direct_text_payload_should_purge(extraction_succeeded=True)
    assert not direct_text_payload_should_purge(extraction_succeeded=False)


def test_unknown_information_class_fails_closed():
    with pytest.raises(ValueError):
        analysis_content_retention_hours("X")
