from __future__ import annotations

import pytest

from ikf.timeline import (
    format_relative_seconds,
    normalise_timeline_event,
    timeline_sort_key,
)


def base_payload(**overrides):
    payload = {
        "analysis_id": "analysis_test",
        "summary": "Loss of propulsion reported",
        "event_type": "FAILURE",
        "phase": "ACCIDENT_INITIATION",
        "time_basis": "ABSOLUTE",
        "time_precision": "MINUTE",
        "event_time_start": "2026-09-24T10:15:00",
        "evidence_references": ["Report p.17"],
    }
    payload.update(overrides)
    return payload


def test_absolute_event_preserves_declared_precision():
    event = normalise_timeline_event(base_payload())
    assert event["time_basis"] == "ABSOLUTE"
    assert event["time_precision"] == "MINUTE"
    assert event["event_time_start"] == "2026-09-24T10:15:00"
    assert event["event_time_end"] is None


def test_absolute_range_rejects_backwards_time():
    with pytest.raises(ValueError, match="precedes"):
        normalise_timeline_event(
            base_payload(
                time_precision="RANGE",
                event_time_end="2026-09-24T10:14:00",
            )
        )


def test_relative_audio_requires_non_negative_offset():
    with pytest.raises(ValueError, match="negative"):
        normalise_timeline_event(
            base_payload(
                time_basis="RELATIVE_AUDIO",
                time_precision="RELATIVE_AUDIO",
                event_time_start=None,
                relative_start_s=-1,
            )
        )


def test_relative_audio_range_preserves_offsets():
    event = normalise_timeline_event(
        base_payload(
            time_basis="RELATIVE_AUDIO",
            time_precision="RANGE",
            event_time_start=None,
            relative_start_s=589.0,
            relative_end_s=602.5,
        )
    )
    assert event["relative_start_s"] == 589.0
    assert event["relative_end_s"] == 602.5
    assert event["event_time_start"] is None


def test_order_only_does_not_invent_clock_time():
    event = normalise_timeline_event(
        base_payload(
            time_basis="ORDER_ONLY",
            time_precision="EXACT",
            event_time_start=None,
        )
    )
    assert event["time_precision"] == "ORDER_ONLY"
    assert event["event_time_start"] is None
    assert event["relative_start_s"] is None


def test_sort_keeps_unlike_time_bases_separate():
    absolute = normalise_timeline_event(base_payload())
    relative = normalise_timeline_event(
        base_payload(
            time_basis="RELATIVE_AUDIO",
            time_precision="RELATIVE_AUDIO",
            event_time_start=None,
            relative_start_s=10,
        )
    )
    order_only = normalise_timeline_event(
        base_payload(
            time_basis="ORDER_ONLY",
            event_time_start=None,
        )
    )
    assert timeline_sort_key(absolute)[0] == 0
    assert timeline_sort_key(relative)[0] == 1
    assert timeline_sort_key(order_only)[0] == 2


def test_relative_clock_format():
    assert format_relative_seconds(589) == "00:09:49"
