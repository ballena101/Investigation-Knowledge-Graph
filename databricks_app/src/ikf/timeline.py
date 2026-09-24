"""Governed timeline helpers for IKF.

Timeline V0.1 is deliberately deterministic.  These helpers validate and sort
human-reviewed temporal events; they do not infer dates, times, chronology or
causation from free text.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


TIMELINE_VERSION = "IKF_TIMELINE_V0.1"

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
        return (1, float(value) if value is not None else float("inf"), event.get("summary") or "")
    return (2, event.get("created_at") or "", event.get("summary") or "")


def format_relative_seconds(seconds: Any) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(round(float(seconds))))
    return f"{total // 3600:02}:{(total // 60) % 60:02}:{total % 60:02}"
