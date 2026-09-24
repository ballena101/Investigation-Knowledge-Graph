"""Timeline V0.3 adoption for the IKF Streamlit App.

The Timeline is a chronological projection of the same evidence-derived Event
nodes and FOLLOWED_BY relationships used by the Knowledge Graph.  It therefore
appears by default after analysis without requiring an investigator to build it
manually.  Investigator-reviewed timeline events remain an overlay that can
validate, amend or add precision without replacing the source-derived view.

No additional LLM call is made by the Timeline page.
"""

from __future__ import annotations


TIMELINE_ADOPTION_VERSION = "IKF_APP_TIMELINE_ADOPTION_V0.3"

_IMPORT_ANCHOR = "from neo4j import GraphDatabase\n"
_IMPORT_REPLACEMENT = '''from neo4j import GraphDatabase
from ikf.timeline import (
    ABSOLUTE_PRECISIONS,
    RELATIVE_PRECISIONS,
    TIMELINE_PHASES,
    TIMELINE_VERSION,
    align_audio_offset,
    format_relative_seconds,
    normalise_timeline_event,
    project_default_timeline,
    timeline_sort_key,
)
'''

_HELPER_ANCHOR = "\n\n# ACTIVE_ANALYSIS_CONTEXT\n"
_HELPERS = r'''

@st.cache_data(ttl=15)
def load_timeline_events(analysis_id):
    query = """
    MATCH (:AnalysisGroup {analysis_id: $analysis_id})
          -[:HAS_TIMELINE_EVENT]->(t:TimelineEvent)
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
    ORDER BY t.created_at
    """
    with get_driver().session() as session:
        rows = [
            record.data()
            for record in session.run(query, analysis_id=analysis_id)
        ]
    return sorted(rows, key=timeline_sort_key)


@st.cache_data(ttl=20)
def load_timeline_context(analysis_id):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
    RETURN
        properties(a)["analysis_summary"] AS analysis_summary,
        coalesce(properties(a)["key_findings"], []) AS key_findings,
        coalesce(properties(a)["uncertainties"], []) AS uncertainties,
        coalesce(properties(a)["source_conflicts"], []) AS source_conflicts,
        properties(a)["timeline_audio_anchor"] AS timeline_audio_anchor,
        properties(a)["timeline_audio_anchor_source"] AS timeline_audio_anchor_source,
        properties(a)["timeline_audio_anchor_reviewed_by"] AS timeline_audio_anchor_reviewed_by
    """
    with get_driver().session() as session:
        record = session.run(query, analysis_id=analysis_id).single()
    return record.data() if record else {}


def _timeline_evidence_order_key(event):
    parsed = []
    for value in event.get("evidence_locations") or []:
        item = parse_evidence_location(value)
        if item is None:
            continue
        page = item.get("page_start")
        parsed.append(
            (
                str(item.get("document_id") or ""),
                int(page) if page is not None else 10**9,
            )
        )
    if parsed:
        return min(parsed) + (str(event.get("label") or "").casefold(),)
    return ("~", 10**9, str(event.get("label") or "").casefold())


@st.cache_data(ttl=15)
def load_default_timeline_projection(analysis_id):
    with get_driver().session() as session:
        run_record = session.run(
            """
            MATCH (:AnalysisGroup {analysis_id: $analysis_id})-[:HAS_MODEL_RUN]->(m:ModelRun)
            WHERE m.status = 'COMPLETED'
            RETURN
                m.model_run_id AS model_run_id,
                m.model_key AS model_key,
                toString(m.completed_at) AS completed_at
            ORDER BY
                CASE WHEN m.model_key = 'PRIMARY' THEN 0 ELSE 1 END,
                m.completed_at DESC
            LIMIT 1
            """,
            analysis_id=analysis_id,
        ).single()

        model_run_id = run_record["model_run_id"] if run_record else None

        if model_run_id:
            node_query = """
            MATCH (n:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_kind: 'Event'
            })
            RETURN
                n.node_id AS node_id,
                n.label AS label,
                properties(n)["description"] AS description,
                n.model_run_id AS model_run_id,
                coalesce(properties(n)["evidence_references"], []) AS evidence_references,
                coalesce(properties(n)["evidence_locations"], []) AS evidence_locations,
                coalesce(properties(n)["audio_evidence_locations"], []) AS audio_evidence_locations,
                properties(n)["source_sequence_index"] AS source_sequence_index,
                properties(n)["explicit_time_label"] AS explicit_time_label,
                properties(n)["explicit_time_minutes"] AS explicit_time_minutes,
                coalesce(properties(n)["timeline_time_conflict"], false) AS timeline_time_conflict
            """
            edge_query = """
            MATCH (s:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_kind: 'Event'
            })-[r:FOLLOWED_BY]->(t:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_kind: 'Event'
            })
            RETURN
                s.node_id AS source_node_id,
                t.node_id AS target_node_id,
                properties(r)["edge_id"] AS edge_id,
                properties(r)["edge_class"] AS edge_class,
                coalesce(properties(r)["evidence_references"], []) AS evidence_references
            """
            events = [
                record.data()
                for record in session.run(
                    node_query,
                    analysis_id=analysis_id,
                    model_run_id=model_run_id,
                )
            ]
            edges = [
                record.data()
                for record in session.run(
                    edge_query,
                    analysis_id=analysis_id,
                    model_run_id=model_run_id,
                )
            ]
        else:
            events = [
                record.data()
                for record in session.run(
                    """
                    MATCH (n:KGNode {analysis_id: $analysis_id, node_kind: 'Event'})
                    RETURN
                        n.node_id AS node_id,
                        n.label AS label,
                        properties(n)["description"] AS description,
                        n.model_run_id AS model_run_id,
                        coalesce(properties(n)["evidence_references"], []) AS evidence_references,
                        coalesce(properties(n)["evidence_locations"], []) AS evidence_locations,
                        coalesce(properties(n)["audio_evidence_locations"], []) AS audio_evidence_locations,
                        properties(n)["source_sequence_index"] AS source_sequence_index,
                        properties(n)["explicit_time_label"] AS explicit_time_label,
                        properties(n)["explicit_time_minutes"] AS explicit_time_minutes,
                        coalesce(properties(n)["timeline_time_conflict"], false) AS timeline_time_conflict
                    """,
                    analysis_id=analysis_id,
                )
            ]
            edges = [
                record.data()
                for record in session.run(
                    """
                    MATCH (s:KGNode {analysis_id: $analysis_id, node_kind: 'Event'})
                          -[r:FOLLOWED_BY]->
                          (t:KGNode {analysis_id: $analysis_id, node_kind: 'Event'})
                    RETURN
                        s.node_id AS source_node_id,
                        t.node_id AS target_node_id,
                        properties(r)["edge_id"] AS edge_id,
                        properties(r)["edge_class"] AS edge_class,
                        coalesce(properties(r)["evidence_references"], []) AS evidence_references
                    """,
                    analysis_id=analysis_id,
                )
            ]

    # Backward-compatible passage/page fallback for analyses created before
    # source_sequence_index became a graph property.  This affects display order
    # only; it does not create a FOLLOWED_BY fact.
    missing_sequence = [
        item for item in events
        if item.get("source_sequence_index") in (None, "")
    ]
    for rank, item in enumerate(
        sorted(missing_sequence, key=_timeline_evidence_order_key),
        start=1,
    ):
        item["source_sequence_index"] = rank

    projected, conflicts = project_default_timeline(events, edges)
    return {
        "model_run_id": model_run_id,
        "events": projected,
        "followed_by_edges": edges,
        "conflicts": conflicts,
    }


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
                MATCH (t:TimelineEvent {timeline_event_id: $timeline_event_id})
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


def save_timeline_audio_anchor(analysis_id, anchor_iso, source_note):
    reviewer = get_current_user_key()
    if reviewer == "unknown":
        raise PermissionError("A resolved user identity is required")
    # validate before persistence
    align_audio_offset(anchor_iso, 0)
    with get_driver().session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            SET a.timeline_audio_anchor = $anchor_iso,
                a.timeline_audio_anchor_source = $source_note,
                a.timeline_audio_anchor_reviewed_by = $reviewer,
                a.timeline_audio_anchor_reviewed_at = datetime()
            """,
            analysis_id=analysis_id,
            anchor_iso=anchor_iso,
            source_note=source_note,
            reviewer=reviewer,
        ).consume()


def timeline_time_label(event):
    basis = event.get("time_basis")
    if basis == "ABSOLUTE":
        start = str(event.get("event_time_start") or "—")
        end = str(event.get("event_time_end") or "")
        if event.get("time_precision") == "DATE_ONLY":
            return start[:10]
        return start + ((" → " + end) if end else "")
    if basis == "RELATIVE_AUDIO":
        start = format_relative_seconds(event.get("relative_start_s"))
        end = event.get("relative_end_s")
        if end is not None:
            return start + " → " + format_relative_seconds(end)
        return start + " from audio start"
    return "Order only / no supported clock time"


def default_timeline_time_label(event, audio_anchor=None):
    if event.get("explicit_time_label"):
        return str(event["explicit_time_label"])
    if event.get("relative_start_s") is not None:
        relative = format_relative_seconds(event.get("relative_start_s"))
        if audio_anchor:
            try:
                aligned = align_audio_offset(audio_anchor, event["relative_start_s"])
                return relative + " · aligned " + aligned
            except Exception:
                pass
        return relative + " from audio start"
    return "Sequence only"
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
            "See an automatic evidence-derived chronology for every completed analysis, "
            "then validate or refine it as an investigator."
        )
        st.caption(
            "The timeline reuses KG events and evidence; no additional LLM call is made."
        )

    st.divider()
    st.markdown("### Current validation milestone")
'''

_KG_ANCHOR = "\n\nwith tab_knowledge_graph:\n"
_TIMELINE_PANEL = r'''

with tab_timeline:
    st.subheader("Timeline")
    st.caption(
        "Default chronology projected from the same evidence-derived Event nodes and "
        "FOLLOWED_BY relationships used by the Knowledge Graph. Events remain visible "
        "even when no clock time is known. Investigator validation can refine the view."
    )

    if not active_analysis_id or not active_analysis:
        st.info("Create or select an active analysis to view its timeline.")
    else:
        timeline_analysis_id = active_analysis_id
        projection = load_default_timeline_projection(timeline_analysis_id)
        default_events = projection.get("events") or []
        chronology_conflicts = projection.get("conflicts") or []
        timeline_events = load_timeline_events(timeline_analysis_id)
        timeline_context = load_timeline_context(timeline_analysis_id)
        audio_anchor = timeline_context.get("timeline_audio_anchor")

        validated_by_node = {}
        for reviewed in timeline_events:
            node_id = reviewed.get("source_node_id")
            if node_id:
                validated_by_node[node_id] = reviewed

        tm1, tm2, tm3, tm4 = st.columns(4)
        tm1.metric("Default events", len(default_events))
        tm2.metric("Human validated", len(timeline_events))
        tm3.metric(
            "With supported time",
            sum(
                1 for item in default_events
                if item.get("explicit_time_label")
                or item.get("relative_start_s") is not None
            ),
        )
        tm4.metric("Chronology flags", len(chronology_conflicts))

        st.markdown("### Default chronology")
        st.caption(
            "Order priority: evidence-supported FOLLOWED_BY relationships first; "
            "source passage/page order is used only as a display fallback where the "
            "evidence provides no explicit temporal relation. SOURCE_ORDER does not "
            "create a factual FOLLOWED_BY relationship."
        )

        if not default_events:
            st.info(
                "No Event nodes are available yet. The default timeline will appear "
                "automatically when the analysis has produced its evidence-derived graph."
            )
        else:
            st.dataframe(
                [
                    {
                        "#": item.get("sequence_position"),
                        "Time": default_timeline_time_label(item, audio_anchor),
                        "Event": item.get("label") or "Event",
                        "Order basis": item.get("ordering_basis") or "—",
                        "Evidence": len(item.get("evidence_references") or []),
                        "Review": (
                            "HUMAN_VALIDATED"
                            if item.get("node_id") in validated_by_node
                            else "DEFAULT_CANDIDATE"
                        ),
                        "Flag": "REVIEW" if item.get("ordering_conflict") else "",
                    }
                    for item in default_events
                ],
                hide_index=True,
                use_container_width=True,
            )

            selected_default_node = st.selectbox(
                "Inspect / validate default event",
                options=[item["node_id"] for item in default_events],
                format_func=lambda value: next(
                    (
                        f"{item.get('sequence_position')}. {item.get('label') or value}"
                        for item in default_events
                        if item["node_id"] == value
                    ),
                    value,
                ),
                key="timeline_default_event_" + timeline_analysis_id,
            )
            selected_default = next(
                item for item in default_events
                if item["node_id"] == selected_default_node
            )

            with st.container(border=True):
                st.markdown("**" + str(selected_default.get("label") or "Event") + "**")
                if selected_default.get("description"):
                    st.write(selected_default["description"])
                st.caption(
                    "Position "
                    + str(selected_default.get("sequence_position"))
                    + " · "
                    + default_timeline_time_label(selected_default, audio_anchor)
                    + " · basis "
                    + str(selected_default.get("ordering_basis") or "—")
                )
                for reference in selected_default.get("evidence_references") or []:
                    st.write("• " + str(reference))
                if selected_default.get("ordering_conflict"):
                    st.warning("This event has a chronology flag and requires review.")

        if chronology_conflicts:
            with st.expander("Chronology conflicts / reconciliation", expanded=True):
                for conflict in chronology_conflicts:
                    st.warning(conflict.get("message") or conflict.get("conflict_type"))

        source_conflicts = timeline_context.get("source_conflicts") or []
        uncertainties = timeline_context.get("uncertainties") or []
        if source_conflicts or uncertainties:
            with st.expander("Source conflicts and uncertainties", expanded=False):
                for value in source_conflicts:
                    st.write("• Source conflict: " + str(value))
                for value in uncertainties:
                    st.write("• Uncertainty: " + str(value))

        relative_default_events = [
            item for item in default_events
            if item.get("relative_start_s") is not None
        ]
        if relative_default_events:
            with st.expander("Audio time alignment", expanded=False):
                st.caption(
                    "Optional V0.3 alignment: if the absolute start time of the recording "
                    "is supported by evidence, store it once and IKF will display absolute "
                    "times alongside the reviewed audio offsets."
                )
                current_anchor = str(audio_anchor or "")
                anchor_value = st.text_input(
                    "Recording start (ISO-8601)",
                    value=current_anchor,
                    placeholder="1997-02-12T09:40:00+00:00",
                    key="timeline_audio_anchor_" + timeline_analysis_id,
                )
                anchor_source = st.text_input(
                    "Evidence supporting recording start",
                    value=str(timeline_context.get("timeline_audio_anchor_source") or ""),
                    placeholder="e.g. coastguard log / recording metadata",
                    key="timeline_audio_anchor_source_" + timeline_analysis_id,
                )
                if st.button(
                    "Save reviewed audio alignment",
                    disabled=not anchor_value.strip() or not anchor_source.strip(),
                    key="timeline_audio_anchor_save_" + timeline_analysis_id,
                ):
                    try:
                        save_timeline_audio_anchor(
                            timeline_analysis_id,
                            anchor_value.strip(),
                            anchor_source.strip(),
                        )
                        load_timeline_context.clear()
                        st.success("Audio alignment saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error("The audio alignment could not be saved.")
                        st.exception(exc)

        if timeline_events:
            with st.expander("Investigator-reviewed timeline", expanded=False):
                st.dataframe(
                    [
                        {
                            "Time": timeline_time_label(item),
                            "Phase": item.get("phase") or "UNASSIGNED",
                            "Type": item.get("event_type") or "EVENT",
                            "Event": item.get("summary") or "",
                            "Evidence": len(item.get("evidence_references") or []),
                            "Reviewed by": item.get("created_by") or "—",
                        }
                        for item in timeline_events
                    ],
                    hide_index=True,
                    use_container_width=True,
                )

        st.divider()
        st.markdown("### Validate or refine chronology")
        st.caption(
            "The default timeline remains visible. Saving here creates a human-reviewed "
            "overlay linked to the selected KG event; it does not erase source provenance."
        )

        candidate_by_id = {item["node_id"]: item for item in default_events}
        candidate_options = [""] + list(candidate_by_id)
        source_node_id = st.selectbox(
            "Link default event (optional)",
            options=candidate_options,
            format_func=lambda value: (
                "Manual additional event"
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
            help="Use a concise, de-identified description grounded in available evidence.",
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
                    "EVENT", "ALARM", "FAILURE", "COMMUNICATION", "ACTION",
                    "DISTRESS", "RESPONSE", "RESCUE", "FIRE",
                    "COLLISION_CONTACT", "GROUNDING", "OTHER",
                ],
                key="timeline_type_" + timeline_analysis_id,
            )

        basis_labels = {
            "Order only / no supported clock time": "ORDER_ONLY",
            "Absolute date/time": "ABSOLUTE",
            "Relative to audio start": "RELATIVE_AUDIO",
        }
        default_basis_label = "Order only / no supported clock time"
        if source_candidate.get("relative_start_s") is not None:
            default_basis_label = "Relative to audio start"
        basis_label = st.radio(
            "Time basis",
            options=list(basis_labels),
            index=list(basis_labels).index(default_basis_label),
            horizontal=True,
            key="timeline_basis_" + timeline_analysis_id + "_" + (source_node_id or "manual"),
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
                event_time_start = datetime.combine(event_date, event_clock).isoformat()
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
                event_time_end = datetime.combine(end_date, end_clock).isoformat()

        elif event_time_basis == "RELATIVE_AUDIO":
            event_precision = st.selectbox(
                "Audio-time precision",
                options=list(RELATIVE_PRECISIONS),
                key="timeline_precision_audio_" + timeline_analysis_id,
            )
            suggested_start = float(source_candidate.get("relative_start_s") or 0.0)
            suggested_end = source_candidate.get("relative_end_s")
            relative_start_s = st.number_input(
                "Seconds from audio start",
                min_value=0.0,
                value=suggested_start,
                step=1.0,
                key="timeline_audio_start_" + timeline_analysis_id + "_" + (source_node_id or "manual"),
            )
            if event_precision == "RANGE":
                relative_end_s = st.number_input(
                    "End seconds from audio start",
                    min_value=float(relative_start_s),
                    value=max(
                        float(relative_start_s),
                        float(suggested_end) if suggested_end is not None else float(relative_start_s),
                    ),
                    step=1.0,
                    key="timeline_audio_end_" + timeline_analysis_id + "_" + (source_node_id or "manual"),
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
            "I checked the available evidence and confirm that this event/order/time is supported; the reviewed timeline must not imply greater precision than the source.",
            key="timeline_confirm_" + timeline_analysis_id,
        )

        if st.button(
            "Save investigator timeline decision",
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
                        st.success("Timeline decision saved: " + timeline_event_id)
                        st.rerun()
                    except Exception as exc:
                        st.error("The timeline decision could not be saved.")
                        st.exception(exc)

        st.divider()
        st.markdown("### Evidence-based conclusion")
        conclusion = str(timeline_context.get("analysis_summary") or "").strip()
        key_findings = timeline_context.get("key_findings") or []
        if conclusion:
            st.write(conclusion)
        elif key_findings:
            st.write("Available analysed evidence supports the following findings:")
        else:
            st.info(
                "The conclusion will appear automatically when the evidence analysis "
                "summary is available."
            )
        if key_findings:
            st.markdown("**Key findings from the analysed evidence**")
            for finding in key_findings:
                st.write("• " + str(finding))
        if uncertainties:
            st.caption(
                "The conclusion must be read together with the uncertainties shown above."
            )
'''


def transform_app_timeline_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Materialize Timeline V0.3 into the Streamlit App source."""

    applied: list[str] = []

    if _IMPORT_ANCHOR not in source:
        raise RuntimeError("Timeline adoption could not locate the import anchor")
    source = source.replace(_IMPORT_ANCHOR, _IMPORT_REPLACEMENT, 1)
    applied.append("timeline_imports")

    if _HELPER_ANCHOR not in source:
        raise RuntimeError("Timeline adoption could not locate helper anchor")
    source = source.replace(_HELPER_ANCHOR, _HELPERS + _HELPER_ANCHOR, 1)
    applied.extend(
        [
            "timeline_store_helpers",
            "default_graph_chronology_projection",
            "chronology_conflict_detection",
            "audio_absolute_alignment",
            "evidence_based_timeline_conclusion",
        ]
    )

    if _TABS_TUPLE_OLD not in source:
        raise RuntimeError("Timeline adoption could not locate tab tuple")
    source = source.replace(_TABS_TUPLE_OLD, _TABS_TUPLE_NEW, 1)

    if _TABS_LABELS_OLD not in source:
        raise RuntimeError("Timeline adoption could not locate tab labels")
    source = source.replace(_TABS_LABELS_OLD, _TABS_LABELS_NEW, 1)
    applied.append("timeline_tab")

    if _HOME_MILESTONE_ANCHOR not in source:
        raise RuntimeError("Timeline adoption could not locate Home milestone anchor")
    source = source.replace(_HOME_MILESTONE_ANCHOR, _HOME_TIMELINE_CARD, 1)
    applied.append("timeline_home_card")

    if _KG_ANCHOR not in source:
        raise RuntimeError("Timeline adoption could not locate Knowledge Graph anchor")
    source = source.replace(_KG_ANCHOR, _TIMELINE_PANEL + _KG_ANCHOR, 1)
    applied.append("timeline_workspace")

    return source, tuple(applied)
