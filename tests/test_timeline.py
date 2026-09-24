from __future__ import annotations

import pytest

from ikf.timeline import (
    align_audio_offset,
    format_relative_seconds,
    normalise_timeline_event,
    project_default_timeline,
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


def test_default_projection_respects_followed_by_before_source_fallback():
    events = [
        {"node_id": "e2", "label": "Second", "source_sequence_index": 1},
        {"node_id": "e1", "label": "First", "source_sequence_index": 2},
    ]
    projected, conflicts = project_default_timeline(
        events,
        [{"source_node_id": "e1", "target_node_id": "e2"}],
    )
    assert [item["node_id"] for item in projected] == ["e1", "e2"]
    assert projected[0]["ordering_basis"] == "FOLLOWED_BY"
    assert conflicts == []


def test_default_projection_uses_source_order_when_no_time_or_edge_exists():
    events = [
        {"node_id": "e2", "label": "Later passage", "source_sequence_index": 2},
        {"node_id": "e1", "label": "Earlier passage", "source_sequence_index": 1},
    ]
    projected, conflicts = project_default_timeline(events, [])
    assert [item["node_id"] for item in projected] == ["e1", "e2"]
    assert all(item["ordering_basis"] == "SOURCE_ORDER" for item in projected)
    assert conflicts == []


def test_default_projection_surfaces_cycle_instead_of_hiding_it():
    events = [
        {"node_id": "e1", "label": "A", "source_sequence_index": 1},
        {"node_id": "e2", "label": "B", "source_sequence_index": 2},
    ]
    projected, conflicts = project_default_timeline(
        events,
        [
            {"source_node_id": "e1", "target_node_id": "e2"},
            {"source_node_id": "e2", "target_node_id": "e1"},
        ],
    )
    assert len(projected) == 2
    assert conflicts[0]["conflict_type"] == "FOLLOWED_BY_CYCLE"
    assert all(item["ordering_conflict"] for item in projected)


def test_default_projection_uses_reviewed_audio_location_without_absolute_time():
    audio_location = "audio|" + ("a" * 64) + "|589000|602500"
    projected, conflicts = project_default_timeline(
        [
            {
                "node_id": "e1",
                "label": "Position transmitted",
                "source_sequence_index": 1,
                "audio_evidence_locations": [audio_location],
            }
        ],
        [],
    )
    assert conflicts == []
    assert projected[0]["ordering_basis"] == "RELATIVE_AUDIO"
    assert projected[0]["relative_start_s"] == 589.0
    assert projected[0]["relative_end_s"] == 602.5


def test_audio_anchor_alignment_requires_explicit_anchor():
    assert (
        align_audio_offset("1997-02-12T09:40:00+00:00", 589)
        == "1997-02-12T09:49:49+00:00"
    )
