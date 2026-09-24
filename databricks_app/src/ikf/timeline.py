"""Governed timeline helpers for IKF.

Timeline V0.3 has two complementary layers:

* a default chronology projected deterministically from already-extracted KG
  Event nodes, FOLLOWED_BY relationships, source passage order and reviewed
  audio timestamps; and
* investigator-authored/validated timeline events that can refine that default.

The helper layer never turns chronology into causality and never invents an
absolute clock time.  When no supported time exists, events remain visible in
an order-only sequence whose basis is explicit to the investigator.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ikf.audio_evidence import parse_audio_evidence_location


TIMELINE_VERSION = "IKF_TIMELINE_V0.3"
TIMELINE_PROJECTION_VERSION = "IKF_TIMELINE_PROJECTION_V0.3"

TIMELINE_PHASES = (
    "PRE_ACCIDENT",
    "ACCIDENT_INITIATION",
    "ESCALATION",
    "EMERGENCY_RESPONSE",
    "ABANDONMENT_RESCUE",
    "POST_OCCURRENCE",
    "INVESTIGATION",
    "UNASSIGNED",
)

TIME_BASES = (
    "ABSOLUTE",
    "RELATIVE_AUDIO",
    "ORDER_ONLY",
)

ABSOLUTE_PRECISIONS = (
    "EXACT",
    "MINUTE",
    "APPROXIMATE",
    "RANGE",
    "DATE_ONLY",
)

RELATIVE_PRECISIONS = (
    "RELATIVE_AUDIO",
    "APPROXIMATE",
    "RANGE",
)

DEFAULT_ORDERING_BASES = (
    "EXPLICIT_TIME",
    "RELATIVE_AUDIO",
    "FOLLOWED_BY",
    "SOURCE_ORDER",
    "UNRESOLVED_ORDER",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_iso(value: Any, field_name: str) -> str:
    text = _clean(value)
    if not text:
        raise ValueError(f"{field_name} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO-8601") from exc
    return parsed.isoformat()


def normalise_timeline_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a human-reviewed timeline event without inventing precision."""

    analysis_id = _clean(payload.get("analysis_id"))
    summary = _clean(payload.get("summary"))
    if not analysis_id:
        raise ValueError("analysis_id is required")
    if not summary:
        raise ValueError("summary is required")

    phase = _clean(payload.get("phase")) or "UNASSIGNED"
    if phase not in TIMELINE_PHASES:
        raise ValueError("Unsupported timeline phase")

    time_basis = _clean(payload.get("time_basis"))
    if time_basis not in TIME_BASES:
        raise ValueError("Unsupported time basis")

    event = {
        "analysis_id": analysis_id,
        "summary": summary,
        "event_type": _clean(payload.get("event_type")) or "EVENT",
        "phase": phase,
        "time_basis": time_basis,
        "time_precision": _clean(payload.get("time_precision")),
        "event_time_start": None,
        "event_time_end": None,
        "relative_start_s": None,
        "relative_end_s": None,
        "source_node_id": _clean(payload.get("source_node_id")) or None,
        "evidence_references": [
            _clean(value)
            for value in (payload.get("evidence_references") or [])
            if _clean(value)
        ],
        "evidence_locations": [
            _clean(value)
            for value in (payload.get("evidence_locations") or [])
            if _clean(value)
        ],
    }

    if time_basis == "ABSOLUTE":
        precision = event["time_precision"] or "MINUTE"
        if precision not in ABSOLUTE_PRECISIONS:
            raise ValueError("Unsupported absolute-time precision")
        start = _parse_iso(payload.get("event_time_start"), "event_time_start")
        end_value = payload.get("event_time_end")
        end = _parse_iso(end_value, "event_time_end") if _clean(end_value) else None
        if end and datetime.fromisoformat(end) < datetime.fromisoformat(start):
            raise ValueError("event_time_end precedes event_time_start")
        event["time_precision"] = precision
        event["event_time_start"] = start
        event["event_time_end"] = end

    elif time_basis == "RELATIVE_AUDIO":
        precision = event["time_precision"] or "RELATIVE_AUDIO"
        if precision not in RELATIVE_PRECISIONS:
            raise ValueError("Unsupported relative-audio precision")
        try:
            start_s = float(payload.get("relative_start_s"))
        except (TypeError, ValueError) as exc:
            raise ValueError("relative_start_s is required") from exc
        if start_s < 0:
            raise ValueError("relative_start_s cannot be negative")
        end_raw = payload.get("relative_end_s")
        end_s = None
        if end_raw not in (None, ""):
            try:
                end_s = float(end_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("relative_end_s must be numeric") from exc
            if end_s < start_s:
                raise ValueError("relative_end_s precedes relative_start_s")
        event["time_precision"] = precision
        event["relative_start_s"] = start_s
        event["relative_end_s"] = end_s

    else:
        event["time_precision"] = "ORDER_ONLY"

    return event


def timeline_sort_key(event: dict[str, Any]) -> tuple[Any, ...]:
    """Stable sort without pretending unlike temporal bases are comparable."""

    basis = event.get("time_basis")
    if basis == "ABSOLUTE":
        value = event.get("event_time_start") or "9999-12-31T23:59:59"
        return (0, value, event.get("summary") or "")
    if basis == "RELATIVE_AUDIO":
        value = event.get("relative_start_s")
        return (
            1,
            float(value) if value is not None else float("inf"),
            event.get("summary") or "",
        )
    return (2, event.get("created_at") or "", event.get("summary") or "")


def format_relative_seconds(seconds: Any) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(round(float(seconds))))
    return f"{total // 3600:02}:{(total // 60) % 60:02}:{total % 60:02}"


def audio_bounds_from_locations(values: Any) -> tuple[float, float] | None:
    """Return the time envelope of governed audio evidence locations."""

    bounds: list[tuple[float, float]] = []
    for value in values or []:
        try:
            location = parse_audio_evidence_location(str(value))
        except ValueError:
            continue
        bounds.append((float(location.start_s), float(location.end_s)))

    if not bounds:
        return None
    return min(item[0] for item in bounds), max(item[1] for item in bounds)


def align_audio_offset(anchor_iso: Any, seconds: Any) -> str:
    """Convert a reviewed audio offset to absolute time using an explicit anchor."""

    anchor = datetime.fromisoformat(_parse_iso(anchor_iso, "audio_anchor"))
    try:
        offset = float(seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("seconds must be numeric") from exc
    if offset < 0:
        raise ValueError("seconds cannot be negative")
    return (anchor + timedelta(seconds=offset)).isoformat()


def _sequence_value(event: dict[str, Any]) -> float:
    raw = event.get("source_sequence_index")
    if raw in (None, ""):
        return float("inf")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float("inf")


def _projection_priority(event: dict[str, Any]) -> tuple[Any, ...]:
    """Prefer evidence passage order, then supported temporal hints, then label."""

    sequence = _sequence_value(event)
    explicit_minutes = event.get("explicit_time_minutes")
    try:
        explicit = float(explicit_minutes)
    except (TypeError, ValueError):
        explicit = float("inf")
    audio = audio_bounds_from_locations(event.get("audio_evidence_locations"))
    audio_start = audio[0] if audio is not None else float("inf")
    return (
        sequence,
        explicit,
        audio_start,
        _clean(event.get("label")).casefold(),
        _clean(event.get("node_id")),
    )


def project_default_timeline(
    events: list[dict[str, Any]],
    followed_by_edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project a default ordered chronology from existing evidence/KG output.

    FOLLOWED_BY constraints are authoritative for ordering within this
    projection because they are already evidence-derived graph relationships.
    Where no such constraint exists, the earliest supporting passage order is
    used as a display-order fallback.  That fallback is labelled SOURCE_ORDER
    and is not promoted to a factual temporal relationship.

    Returns ``(ordered_events, conflicts)``.  Cycles are surfaced as conflicts
    rather than silently broken or converted into causal meaning.
    """

    node_by_id = {
        _clean(event.get("node_id")): dict(event)
        for event in events
        if _clean(event.get("node_id"))
    }
    adjacency = {node_id: set() for node_id in node_by_id}
    indegree = {node_id: 0 for node_id in node_by_id}
    predecessor_count = {node_id: 0 for node_id in node_by_id}
    successor_count = {node_id: 0 for node_id in node_by_id}

    for edge in followed_by_edges or []:
        source = _clean(edge.get("source_node_id"))
        target = _clean(edge.get("target_node_id"))
        if source not in node_by_id or target not in node_by_id or source == target:
            continue
        if target in adjacency[source]:
            continue
        adjacency[source].add(target)
        indegree[target] += 1
        predecessor_count[target] += 1
        successor_count[source] += 1

    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    ready.sort(key=lambda node_id: _projection_priority(node_by_id[node_id]))
    ordered_ids: list[str] = []

    while ready:
        node_id = ready.pop(0)
        ordered_ids.append(node_id)
        for target in sorted(adjacency[node_id]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
        ready.sort(key=lambda item: _projection_priority(node_by_id[item]))

    conflicts: list[dict[str, Any]] = []
    remaining = [node_id for node_id in node_by_id if node_id not in ordered_ids]
    if remaining:
        remaining.sort(key=lambda node_id: _projection_priority(node_by_id[node_id]))
        conflicts.append(
            {
                "conflict_type": "FOLLOWED_BY_CYCLE",
                "node_ids": remaining,
                "message": (
                    "The evidence-derived FOLLOWED_BY relationships contain a cycle; "
                    "the affected events are shown using source-order fallback and "
                    "require investigator review."
                ),
            }
        )
        ordered_ids.extend(remaining)

    projected: list[dict[str, Any]] = []
    cycle_nodes = {
        node_id
        for conflict in conflicts
        for node_id in conflict.get("node_ids", [])
    }

    for position, node_id in enumerate(ordered_ids, start=1):
        event = dict(node_by_id[node_id])
        audio_bounds = audio_bounds_from_locations(
            event.get("audio_evidence_locations")
        )
        explicit_label = _clean(event.get("explicit_time_label"))
        has_followed_by = (
            predecessor_count[node_id] > 0 or successor_count[node_id] > 0
        )

        if explicit_label:
            ordering_basis = "EXPLICIT_TIME"
        elif audio_bounds is not None:
            ordering_basis = "RELATIVE_AUDIO"
        elif has_followed_by:
            ordering_basis = "FOLLOWED_BY"
        elif _sequence_value(event) != float("inf"):
            ordering_basis = "SOURCE_ORDER"
        else:
            ordering_basis = "UNRESOLVED_ORDER"

        event["sequence_position"] = position
        event["ordering_basis"] = ordering_basis
        event["relative_start_s"] = (
            audio_bounds[0] if audio_bounds is not None else None
        )
        event["relative_end_s"] = (
            audio_bounds[1] if audio_bounds is not None else None
        )
        event["ordering_conflict"] = bool(
            event.get("timeline_time_conflict") or node_id in cycle_nodes
        )
        event["projection_version"] = TIMELINE_PROJECTION_VERSION
        projected.append(event)

        if event.get("timeline_time_conflict"):
            conflicts.append(
                {
                    "conflict_type": "MULTIPLE_EXPLICIT_TIMES",
                    "node_ids": [node_id],
                    "message": (
                        f"Event '{event.get('label') or node_id}' has conflicting "
                        "explicit times in its supporting evidence."
                    ),
                }
            )

    return projected, conflicts
