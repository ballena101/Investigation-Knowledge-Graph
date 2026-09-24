"""Deterministic Timeline V0.1 adoption for the IKF Streamlit App.

The timeline is a governed representation of investigator-reviewed chronology.
V0.1 never infers a date/time from free text and never invokes an LLM.  It can
link a human-validated timeline event to an existing KG Event candidate while
preserving the evidence references already attached to that KG node.
"""

from __future__ import annotations


TIMELINE_ADOPTION_VERSION = "IKF_APP_TIMELINE_ADOPTION_V0.1"


_IMPORT_ANCHOR = "from neo4j import GraphDatabase\n"
_IMPORT_REPLACEMENT = '''from neo4j import GraphDatabase
from ikf.timeline import (
    ABSOLUTE_PRECISIONS,
    RELATIVE_PRECISIONS,
    TIMELINE_PHASES,
    TIMELINE_VERSION,
    format_relative_seconds,
    normalise_timeline_event,
    timeline_sort_key,
)
'''

_HELPER_ANCHOR = "\n\n# ACTIVE_ANALYSIS_CONTEXT\n"
_HELPERS = r'''

@st.cache_data(ttl=15)
def load_timeline_events(analysis_id):
    query = """
    MATCH (:AnalysisGroup {analysis_id: $analysis_id})
          -[:HAS_TIMELINE_EVENT]->
          (t:TimelineEvent)
    OPTIONAL MATCH (t)-[:REPRESENTS]->(n:KGNode)
    RETURN
        t.timeline_event_id AS timeline_event_id,
        t.analysis_id AS analysis_id,
        t.summary AS summary,
        t.event_type AS event_type,
        t.phase AS phase,
        t.time_basis AS time_basis,
        t.time_precision AS time_precision,
        t.event_time_start AS event_time_start,
        t.event_time_end AS event_time_end,
        t.relative_start_s AS relative_start_s,
        t.relative_end_s AS relative_end_s,
        coalesce(t.evidence_references, []) AS evidence_references,
        coalesce(t.evidence_locations, []) AS evidence_locations,
        t.review_status AS review_status,
        t.created_by AS created_by,
        toString(t.created_at) AS created_at,
        n.node_id AS source_node_id,
        n.label AS source_node_label
    ORDER BY
        CASE t.time_basis
            WHEN 'ABSOLUTE' THEN 0
            WHEN 'RELATIVE_AUDIO' THEN 1
            ELSE 2
        END,
        t.event_time_start,
        t.relative_start_s,
        t.created_at
    """
    with get_driver().session() as session:
        rows = [
            record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
            )
        ]
    return sorted(rows, key=timeline_sort_key)


@st.cache_data(ttl=30)
def load_timeline_event_candidates(analysis_id):
    query = """
    MATCH (n:KGNode {
        analysis_id: $analysis_id,
        node_kind: 'Event'
    })
    WHERE NOT EXISTS {
        MATCH (:AnalysisGroup {analysis_id: $analysis_id})
              -[:HAS_TIMELINE_EVENT]->
              (:TimelineEvent)-[:REPRESENTS]->(n)
    }
    RETURN
        n.node_id AS node_id,
        n.label AS label,
        properties(n)["description"] AS description,
        coalesce(properties(n)["evidence_references"], []) AS evidence_references,
        coalesce(properties(n)["evidence_locations"], []) AS evidence_locations
    ORDER BY n.label
    """
    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
            )
        ]


def save_timeline_event(payload):
    event = normalise_timeline_event(payload)
    reviewer = get_current_user_key()
    if reviewer == "unknown":
        raise PermissionError(
            "A resolved authenticated user identity is required to validate a timeline event."
        )

    timeline_event_id = "timeline_event_" + uuid.uuid4().hex
    with get_driver().session() as session:
        result = session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            CREATE (t:TimelineEvent {
                timeline_event_id: $timeline_event_id,
                analysis_id: $analysis_id,
                timeline_version: $timeline_version,
                summary: $summary,
                event_type: $event_type,
                phase: $phase,
                time_basis: $time_basis,
                time_precision: $time_precision,
                event_time_start: $event_time_start,
                event_time_end: $event_time_end,
                relative_start_s: $relative_start_s,
                relative_end_s: $relative_end_s,
                evidence_references: $evidence_references,
                evidence_locations: $evidence_locations,
                review_status: 'HUMAN_VALIDATED',
                created_by: $reviewer,
                created_at: datetime()
            })
            MERGE (a)-[:HAS_TIMELINE_EVENT]->(t)
            RETURN t.timeline_event_id AS timeline_event_id
            """,
            timeline_event_id=timeline_event_id,
            timeline_version=TIMELINE_VERSION,
            reviewer=reviewer,
            **event,
        ).single()

        if result is None:
            raise RuntimeError("Timeline event could not be persisted")

        if event.get("source_node_id"):
            session.run(
                """
                MATCH (t:TimelineEvent {
                    timeline_event_id: $timeline_event_id
                })
                MATCH (n:KGNode {
                    analysis_id: $analysis_id,
                    node_id: $source_node_id,
                    node_kind: 'Event'
                })
                MERGE (t)-[:REPRESENTS]->(n)
                """,
                timeline_event_id=timeline_event_id,
                analysis_id=event["analysis_id"],
                source_node_id=event["source_node_id"],
            ).consume()

    return timeline_event_id


def timeline_time_label(event):
    basis = event.get("time_basis")
    if basis == "ABSOLUTE":
        start = str(event.get("event_time_start") or "—")
        end = str(event.get("event_time_end") or "")
        if event.get("time_precision") == "DATE_ONLY":
            return start[:10]
        if end:
            return start + " → " + end
        return start
    if basis == "RELATIVE_AUDIO":
        start = format_relative_seconds(event.get("relative_start_s"))
        end = event.get("relative_end_s")
        if end is not None:
            return start + " → " + format_relative_seconds(end)
        return start + " from audio start"
    return "Order only / no supported clock time"


def timeline_chart_rows(events, time_basis):
    rows = []
    for event in events:
        if event.get("time_basis") != time_basis:
            continue
        if time_basis == "ABSOLUTE":
            start = event.get("event_time_start")
            if not start:
                continue
            rows.append(
                {
                    "event": event.get("summary") or "Event",
                    "phase": event.get("phase") or "UNASSIGNED",
                    "start": start,
                    "end": event.get("event_time_end"),
                    "precision": event.get("time_precision") or "—",
                    "event_type": event.get("event_type") or "EVENT",
                }
            )
        elif time_basis == "RELATIVE_AUDIO":
            start = event.get("relative_start_s")
            if start is None:
                continue
            rows.append(
                {
                    "event": event.get("summary") or "Event",
                    "phase": event.get("phase") or "UNASSIGNED",
                    "start": float(start),
                    "end": (
                        float(event["relative_end_s"])
                        if event.get("relative_end_s") is not None
                        else None
                    ),
                    "start_clock": format_relative_seconds(start),
                    "end_clock": format_relative_seconds(event.get("relative_end_s")),
                    "precision": event.get("time_precision") or "—",
                    "event_type": event.get("event_type") or "EVENT",
                }
            )
    return rows
'''

_TABS_TUPLE_OLD = '''    tab_findings,
    tab_knowledge_graph,
'''
_TABS_TUPLE_NEW = '''    tab_findings,
    tab_timeline,
    tab_knowledge_graph,
'''

_TABS_LABELS_OLD = '''        "Findings & Evidence",
        "Knowledge Graph",
'''
_TABS_LABELS_NEW = '''        "Findings & Evidence",
        "Timeline",
        "Knowledge Graph",
'''

_HOME_MILESTONE_ANCHOR = '''    st.divider()
    st.markdown("### Current validation milestone")
'''
_HOME_TIMELINE_CARD = '''    c7, c8, c9 = st.columns(3)
    with c7:
        st.markdown("### Timeline")
        st.success("Active PoC")
        st.write(
            "Build a human-validated chronology from explicit dates/times, "
            "relative audio timestamps and existing event concepts."
        )
        st.caption(
            "V0.1 never invents temporal precision and does not call an LLM."
        )

    st.divider()
    st.markdown("### Current validation milestone")
'''

_KG_ANCHOR = "\n\nwith tab_knowledge_graph:\n"
_TIMELINE_PANEL = r'''

with tab_timeline:
    st.subheader("Timeline")
    st.caption(
        "Human-validated chronology for the active analysis. V0.1 uses explicit "
        "dates/times, relative audio offsets or order-only events; it does not infer "
        "missing time information and does not invoke an LLM."
    )

    if not active_analysis_id or not active_analysis:
        st.info(
            "Create or select an active analysis to build its investigation timeline."
        )
    else:
        timeline_analysis_id = active_analysis_id
        timeline_events = load_timeline_events(timeline_analysis_id)
        timeline_candidates = load_timeline_event_candidates(timeline_analysis_id)

        tm1, tm2, tm3, tm4 = st.columns(4)
        tm1.metric("Validated events", len(timeline_events))
        tm2.metric(
            "Absolute time",
            sum(1 for item in timeline_events if item.get("time_basis") == "ABSOLUTE"),
        )
        tm3.metric(
            "Audio-relative",
            sum(1 for item in timeline_events if item.get("time_basis") == "RELATIVE_AUDIO"),
        )
        tm4.metric("Unlinked KG event candidates", len(timeline_candidates))

        absolute_rows = timeline_chart_rows(timeline_events, "ABSOLUTE")
        if absolute_rows:
            st.markdown("### Absolute chronology")
            absolute_points = [row for row in absolute_rows if not row.get("end")]
            absolute_ranges = [row for row in absolute_rows if row.get("end")]
            absolute_layers = []
            if absolute_ranges:
                absolute_layers.append(
                    {
                        "data": {"values": absolute_ranges},
                        "mark": {"type": "bar", "cornerRadius": 4, "height": 14},
                        "encoding": {
                            "x": {"field": "start", "type": "temporal", "title": "Time"},
                            "x2": {"field": "end"},
                            "y": {"field": "phase", "type": "nominal", "title": "Phase"},
                            "color": {"field": "phase", "type": "nominal", "legend": None},
                            "tooltip": [
                                {"field": "event", "type": "nominal", "title": "Event"},
                                {"field": "event_type", "type": "nominal", "title": "Type"},
                                {"field": "precision", "type": "nominal", "title": "Precision"},
                                {"field": "start", "type": "temporal", "title": "Start"},
                                {"field": "end", "type": "temporal", "title": "End"},
                            ],
                        },
                    }
                )
            if absolute_points:
                absolute_layers.append(
                    {
                        "data": {"values": absolute_points},
                        "mark": {"type": "point", "filled": True, "size": 120},
                        "encoding": {
                            "x": {"field": "start", "type": "temporal", "title": "Time"},
                            "y": {"field": "phase", "type": "nominal", "title": "Phase"},
                            "color": {"field": "phase", "type": "nominal", "legend": None},
                            "tooltip": [
                                {"field": "event", "type": "nominal", "title": "Event"},
                                {"field": "event_type", "type": "nominal", "title": "Type"},
                                {"field": "precision", "type": "nominal", "title": "Precision"},
                                {"field": "start", "type": "temporal", "title": "Time"},
                            ],
                        },
                    }
                )
            st.vega_lite_chart(
                {"layer": absolute_layers, "height": 260},
                use_container_width=True,
            )

        relative_rows = timeline_chart_rows(timeline_events, "RELATIVE_AUDIO")
        if relative_rows:
            st.markdown("### Audio-relative chronology")
            relative_points = [row for row in relative_rows if row.get("end") is None]
            relative_ranges = [row for row in relative_rows if row.get("end") is not None]
            relative_layers = []
            if relative_ranges:
                relative_layers.append(
                    {
                        "data": {"values": relative_ranges},
                        "mark": {"type": "bar", "cornerRadius": 4, "height": 14},
                        "encoding": {
                            "x": {"field": "start", "type": "quantitative", "title": "Seconds from audio start"},
                            "x2": {"field": "end"},
                            "y": {"field": "phase", "type": "nominal", "title": "Phase"},
                            "color": {"field": "phase", "type": "nominal", "legend": None},
                            "tooltip": [
                                {"field": "event", "type": "nominal", "title": "Event"},
                                {"field": "event_type", "type": "nominal", "title": "Type"},
                                {"field": "start_clock", "type": "nominal", "title": "Start"},
                                {"field": "end_clock", "type": "nominal", "title": "End"},
                                {"field": "precision", "type": "nominal", "title": "Precision"},
                            ],
                        },
                    }
                )
            if relative_points:
                relative_layers.append(
                    {
                        "data": {"values": relative_points},
                        "mark": {"type": "point", "filled": True, "size": 120},
                        "encoding": {
                            "x": {"field": "start", "type": "quantitative", "title": "Seconds from audio start"},
                            "y": {"field": "phase", "type": "nominal", "title": "Phase"},
                            "color": {"field": "phase", "type": "nominal", "legend": None},
                            "tooltip": [
                                {"field": "event", "type": "nominal", "title": "Event"},
                                {"field": "event_type", "type": "nominal", "title": "Type"},
                                {"field": "start_clock", "type": "nominal", "title": "Audio time"},
                                {"field": "precision", "type": "nominal", "title": "Precision"},
                            ],
                        },
                    }
                )
            st.vega_lite_chart(
                {"layer": relative_layers, "height": 240},
                use_container_width=True,
            )

        if not timeline_events:
            st.info(
                "No human-validated timeline events exist yet. Add one below or "
                "link an existing KG Event after checking its time against evidence."
            )
        else:
            st.markdown("### Validated event register")
            st.dataframe(
                [
                    {
                        "Time": timeline_time_label(item),
                        "Phase": item.get("phase") or "UNASSIGNED",
                        "Type": item.get("event_type") or "EVENT",
                        "Event": item.get("summary") or "",
                        "Precision": item.get("time_precision") or "—",
                        "Evidence": len(item.get("evidence_references") or []),
                        "Reviewed by": item.get("created_by") or "—",
                    }
                    for item in timeline_events
                ],
                use_container_width=True,
                hide_index=True,
            )

            selected_timeline_id = st.selectbox(
                "Inspect validated event",
                options=[item["timeline_event_id"] for item in timeline_events],
                format_func=lambda value: next(
                    item.get("summary") or value
                    for item in timeline_events
                    if item["timeline_event_id"] == value
                ),
                key="timeline_event_inspect_" + timeline_analysis_id,
            )
            selected_timeline_event = next(
                item for item in timeline_events
                if item["timeline_event_id"] == selected_timeline_id
            )
            st.caption(
                timeline_time_label(selected_timeline_event)
                + " · "
                + str(selected_timeline_event.get("review_status") or "HUMAN_VALIDATED")
            )
            if selected_timeline_event.get("source_node_label"):
                st.write(
                    "Linked KG event: "
                    + str(selected_timeline_event["source_node_label"])
                )
            if selected_timeline_event.get("evidence_references"):
                st.markdown("**Supporting evidence**")
                for reference in selected_timeline_event["evidence_references"]:
                    st.write("• " + str(reference))

        st.divider()
        st.markdown("### Add validated event")
        st.caption(
            "A timeline event is persisted only after you explicitly confirm that "
            "its time/order is supported by the investigation evidence."
        )

        candidate_by_id = {
            item["node_id"]: item
            for item in timeline_candidates
        }
        candidate_options = [""] + list(candidate_by_id)
        source_node_id = st.selectbox(
            "Link an existing KG Event (optional)",
            options=candidate_options,
            format_func=lambda value: (
                "Manual / not linked to a KG event"
                if not value
                else candidate_by_id[value].get("label") or value
            ),
            key="timeline_candidate_" + timeline_analysis_id,
        )
        source_candidate = candidate_by_id.get(source_node_id) or {}

        event_summary = st.text_input(
            "Event summary",
            value=source_candidate.get("label") or "",
            key="timeline_summary_" + timeline_analysis_id + "_" + (source_node_id or "manual"),
            help="Use a concise, de-identified description. Do not infer missing facts.",
        )
        add_left, add_right = st.columns(2)
        with add_left:
            event_phase = st.selectbox(
                "Phase",
                options=list(TIMELINE_PHASES),
                index=list(TIMELINE_PHASES).index("UNASSIGNED"),
                key="timeline_phase_" + timeline_analysis_id,
            )
        with add_right:
            event_type = st.selectbox(
                "Event type",
                options=[
                    "EVENT",
                    "ALARM",
                    "FAILURE",
                    "COMMUNICATION",
                    "ACTION",
                    "DISTRESS",
                    "RESPONSE",
                    "RESCUE",
                    "FIRE",
                    "COLLISION_CONTACT",
                    "GROUNDING",
                    "OTHER",
                ],
                key="timeline_type_" + timeline_analysis_id,
            )

        basis_labels = {
            "Absolute date/time": "ABSOLUTE",
            "Relative to audio start": "RELATIVE_AUDIO",
            "Order only / no supported clock time": "ORDER_ONLY",
        }
        basis_label = st.radio(
            "Time basis",
            options=list(basis_labels),
            horizontal=True,
            key="timeline_basis_" + timeline_analysis_id,
        )
        event_time_basis = basis_labels[basis_label]

        event_time_start = None
        event_time_end = None
        relative_start_s = None
        relative_end_s = None
        event_precision = "ORDER_ONLY"

        if event_time_basis == "ABSOLUTE":
            event_precision = st.selectbox(
                "Time precision",
                options=list(ABSOLUTE_PRECISIONS),
                index=list(ABSOLUTE_PRECISIONS).index("MINUTE"),
                key="timeline_precision_abs_" + timeline_analysis_id,
            )
            t1, t2 = st.columns(2)
            with t1:
                event_date = st.date_input(
                    "Date",
                    key="timeline_date_" + timeline_analysis_id,
                )
            with t2:
                event_clock = st.time_input(
                    "Time",
                    disabled=(event_precision == "DATE_ONLY"),
                    key="timeline_clock_" + timeline_analysis_id,
                )
            if event_precision == "DATE_ONLY":
                event_time_start = datetime.combine(
                    event_date,
                    datetime.min.time(),
                ).isoformat()
            else:
                event_time_start = datetime.combine(
                    event_date,
                    event_clock,
                ).isoformat()

            if event_precision == "RANGE":
                e1, e2 = st.columns(2)
                with e1:
                    end_date = st.date_input(
                        "End date",
                        value=event_date,
                        key="timeline_end_date_" + timeline_analysis_id,
                    )
                with e2:
                    end_clock = st.time_input(
                        "End time",
                        key="timeline_end_clock_" + timeline_analysis_id,
                    )
                event_time_end = datetime.combine(
                    end_date,
                    end_clock,
                ).isoformat()

        elif event_time_basis == "RELATIVE_AUDIO":
            event_precision = st.selectbox(
                "Audio-time precision",
                options=list(RELATIVE_PRECISIONS),
                key="timeline_precision_audio_" + timeline_analysis_id,
            )
            relative_start_s = st.number_input(
                "Seconds from audio start",
                min_value=0.0,
                step=1.0,
                key="timeline_audio_start_" + timeline_analysis_id,
            )
            if event_precision == "RANGE":
                relative_end_s = st.number_input(
                    "End seconds from audio start",
                    min_value=float(relative_start_s),
                    value=float(relative_start_s),
                    step=1.0,
                    key="timeline_audio_end_" + timeline_analysis_id,
                )

        evidence_references = list(source_candidate.get("evidence_references") or [])
        evidence_locations = list(source_candidate.get("evidence_locations") or [])
        manual_reference = st.text_input(
            "Additional evidence reference (optional)",
            placeholder="e.g. Report p.17 or VHF recording 00:09:49",
            key="timeline_reference_" + timeline_analysis_id,
        )
        if manual_reference.strip():
            evidence_references.append(manual_reference.strip())

        confirmed_timeline = st.checkbox(
            "I checked the evidence and confirm that this time/order is supported; the timeline must not imply greater precision than the source.",
            key="timeline_confirm_" + timeline_analysis_id,
        )

        if st.button(
            "Add validated timeline event",
            type="primary",
            disabled=not confirmed_timeline,
            key="timeline_add_" + timeline_analysis_id,
        ):
            if not event_summary.strip():
                st.error("Enter an event summary.")
            else:
                protected_rules = app_protected_prescreen(text=event_summary)
                if protected_rules:
                    st.error(
                        "Timeline summaries are derived knowledge and must be de-identified. "
                        "Protected-record indicators were detected: "
                        + ", ".join(protected_rules)
                    )
                else:
                    try:
                        timeline_event_id = save_timeline_event(
                            {
                                "analysis_id": timeline_analysis_id,
                                "summary": event_summary.strip(),
                                "event_type": event_type,
                                "phase": event_phase,
                                "time_basis": event_time_basis,
                                "time_precision": event_precision,
                                "event_time_start": event_time_start,
                                "event_time_end": event_time_end,
                                "relative_start_s": relative_start_s,
                                "relative_end_s": relative_end_s,
                                "source_node_id": source_node_id or None,
                                "evidence_references": evidence_references,
                                "evidence_locations": evidence_locations,
                            }
                        )
                        load_timeline_events.clear()
                        load_timeline_event_candidates.clear()
                        st.success("Validated timeline event added: " + timeline_event_id)
                        st.rerun()
                    except Exception as exc:
                        st.error("The timeline event could not be saved.")
                        st.exception(exc)
'''


def transform_app_timeline_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Materialize Timeline V0.1 into the Streamlit App source."""

    applied: list[str] = []

    if _IMPORT_ANCHOR not in source:
        raise RuntimeError("Timeline adoption could not locate the import anchor")
    source = source.replace(_IMPORT_ANCHOR, _IMPORT_REPLACEMENT, 1)
    applied.append("timeline_imports")

    if _HELPER_ANCHOR not in source:
        raise RuntimeError("Timeline adoption could not locate helper anchor")
    source = source.replace(_HELPER_ANCHOR, _HELPERS + _HELPER_ANCHOR, 1)
    applied.append("timeline_store_helpers")

    if _TABS_TUPLE_OLD not in source:
        raise RuntimeError("Timeline adoption could not locate tab tuple")
    source = source.replace(_TABS_TUPLE_OLD, _TABS_TUPLE_NEW, 1)

    if _TABS_LABELS_OLD not in source:
        raise RuntimeError("Timeline adoption could not locate tab labels")
    source = source.replace(_TABS_LABELS_OLD, _TABS_LABELS_NEW, 1)
    applied.append("timeline_tab")

    if _HOME_MILESTONE_ANCHOR not in source:
        raise RuntimeError("Timeline adoption could not locate Home milestone anchor")
    source = source.replace(
        _HOME_MILESTONE_ANCHOR,
        _HOME_TIMELINE_CARD,
        1,
    )
    applied.append("timeline_home_card")

    if _KG_ANCHOR not in source:
        raise RuntimeError("Timeline adoption could not locate Knowledge Graph anchor")
    source = source.replace(_KG_ANCHOR, _TIMELINE_PANEL + _KG_ANCHOR, 1)
    applied.append("timeline_workspace")

    return source, tuple(applied)
