"""Purpose-fit UI refinements for the IKF Databricks App.

Presentation-only layer. SHIELD remains in the project and backend; only its
Streamlit section is hidden from this investigator-facing app.
"""

from __future__ import annotations

VISUAL_REFINEMENT_VERSION = "IKF_APP_VISUAL_REFINEMENT_V0.3"

_CATEGORY_HELPERS = r'''

_TIMELINE_CATEGORY_META = {
    "OPERATION_CONTEXT": ("Context / operation", "#4C78A8"),
    "FAILURE_HAZARD": ("Failure / hazard", "#F58518"),
    "ACTION_COMMUNICATION": ("Action / communication", "#54A24B"),
    "ACCIDENT_CONSEQUENCE": ("Accident / consequence", "#E45756"),
    "RESPONSE_RECOVERY": ("Response / recovery", "#B279A2"),
}
_TIMELINE_CATEGORY_ORDER = list(_TIMELINE_CATEGORY_META)
_OLD_EVENT_TYPE_TO_CATEGORY = {
    "EVENT": "OPERATION_CONTEXT", "OTHER": "OPERATION_CONTEXT",
    "ALARM": "FAILURE_HAZARD", "FAILURE": "FAILURE_HAZARD",
    "COMMUNICATION": "ACTION_COMMUNICATION", "ACTION": "ACTION_COMMUNICATION",
    "FIRE": "ACCIDENT_CONSEQUENCE", "COLLISION_CONTACT": "ACCIDENT_CONSEQUENCE",
    "GROUNDING": "ACCIDENT_CONSEQUENCE", "DISTRESS": "RESPONSE_RECOVERY",
    "RESPONSE": "RESPONSE_RECOVERY", "RESCUE": "RESPONSE_RECOVERY",
}

def _timeline_category_label(category):
    return _TIMELINE_CATEGORY_META.get(
        category, _TIMELINE_CATEGORY_META["OPERATION_CONTEXT"]
    )[0]

def _timeline_visual_category(event, reviewed_event=None):
    reviewed_type = str((reviewed_event or {}).get("event_type") or "").strip().upper()
    if reviewed_type in _TIMELINE_CATEGORY_META:
        return reviewed_type
    if reviewed_type in _OLD_EVENT_TYPE_TO_CATEGORY:
        return _OLD_EVENT_TYPE_TO_CATEGORY[reviewed_type]
    text = " ".join(str(event.get(k) or "") for k in ("label", "description")).casefold()
    groups = (
        ("RESPONSE_RECOVERY", ("distress", "mayday", "rescue", "evacuat", "abandon", "emergency response", "lifeboat", "recovery")),
        ("ACCIDENT_CONSEQUENCE", ("collision", "contact", "allision", "ground", "capsiz", "sink", "sank", "fire", "explosion", "flood", "injur", "fatal", "death", "damage", "pollution", "spill", "overboard")),
        ("FAILURE_HAZARD", ("failure", "failed", "fault", "malfunction", "overheat", "leak", "alarm", "loss of pressure", "loss of power", "blackout", "blocked", "obstructed", "defect", "breakdown")),
        ("ACTION_COMMUNICATION", ("crew", "master", "officer", "engineer", "action", "ordered", "communicat", "reported", "called", "requested", "started", "stopped", "activated", "manoeuv", "maneuv", "decision")),
    )
    for category, terms in groups:
        if any(term in text for term in terms):
            return category
    return "OPERATION_CONTEXT"

def _short_timeline_label(value, limit=34):
    text = str(value or "Event").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
'''

_VISUAL_TIMELINE_BLOCK = r'''            timeline_rows = []
            for item in default_events:
                reviewed = validated_by_node.get(item.get("node_id"))
                category = _timeline_visual_category(item, reviewed)
                timeline_rows.append({
                    "item": item,
                    "category": category,
                    "category_label": _timeline_category_label(category),
                    "time_label": default_timeline_time_label(item, audio_anchor),
                    "review": "Human validated" if reviewed else "Default candidate",
                })

            st.markdown("#### Event sequence")
            st.caption(
                "The chronology is drawn as a sequence across five simple categories. "
                "Hover for supported time, ordering basis, evidence and review status. "
                "Sequence position is used when no clock time is supported, so the view "
                "does not invent temporal precision."
            )
            timeline_fig = go.Figure()
            for category in _TIMELINE_CATEGORY_ORDER:
                rows = [row for row in timeline_rows if row["category"] == category]
                if not rows:
                    continue
                label, colour = _TIMELINE_CATEGORY_META[category]
                timeline_fig.add_trace(go.Scatter(
                    x=[row["item"].get("sequence_position") for row in rows],
                    y=[label] * len(rows),
                    mode="markers+text",
                    marker={"size": 16, "color": colour, "line": {"width": 1, "color": "white"}},
                    text=[_short_timeline_label(row["item"].get("label")) for row in rows],
                    textposition="top center",
                    customdata=[[
                        row["time_label"], row["item"].get("label") or "Event",
                        row["item"].get("ordering_basis") or "—",
                        len(row["item"].get("evidence_references") or []), row["review"],
                    ] for row in rows],
                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>Time: %{customdata[0]}<br>"
                        "Order basis: %{customdata[2]}<br>Evidence references: %{customdata[3]}<br>"
                        "Review: %{customdata[4]}<extra></extra>"
                    ),
                    name=label,
                ))
            timeline_fig.update_layout(
                height=max(390, 280 + 24 * len(default_events)),
                margin={"l": 10, "r": 10, "t": 30, "b": 30},
                xaxis={"title": "Event sequence", "dtick": 1, "showgrid": True, "zeroline": False},
                yaxis={
                    "title": "", "categoryorder": "array",
                    "categoryarray": [_TIMELINE_CATEGORY_META[k][0] for k in reversed(_TIMELINE_CATEGORY_ORDER)],
                    "fixedrange": True,
                },
                hovermode="closest", showlegend=False,
            )
            st.plotly_chart(
                timeline_fig, use_container_width=True,
                config={"displaylogo": False, "scrollZoom": True, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
            )
            legend_columns = st.columns(5)
            for idx, category in enumerate(_TIMELINE_CATEGORY_ORDER):
                label, colour = _TIMELINE_CATEGORY_META[category]
                with legend_columns[idx]:
                    st.markdown(
                        f"<span style='color:{colour};font-size:1.2rem'>●</span> {label}",
                        unsafe_allow_html=True,
                    )
            with st.expander("View timeline data", expanded=False):
                st.dataframe([{
                    "#": row["item"].get("sequence_position"),
                    "Time": row["time_label"], "Category": row["category_label"],
                    "Event": row["item"].get("label") or "Event",
                    "Order basis": row["item"].get("ordering_basis") or "—",
                    "Evidence": len(row["item"].get("evidence_references") or []),
                    "Review": row["review"],
                    "Flag": "REVIEW" if row["item"].get("ordering_conflict") else "",
                } for row in timeline_rows], hide_index=True, use_container_width=True)

'''

_PHASE_SELECT_OLD = '''            event_phase = st.selectbox(
                "Phase",
                options=list(TIMELINE_PHASES),
                index=list(TIMELINE_PHASES).index("UNASSIGNED"),
                key="timeline_phase_" + timeline_analysis_id,
            )
'''
_PHASE_SELECT_NEW = '''            _simple_phase_labels = {
                "PRE_ACCIDENT": "Before occurrence",
                "ACCIDENT_INITIATION": "Occurrence",
                "ESCALATION": "Escalation",
                "EMERGENCY_RESPONSE": "Response / recovery",
                "POST_OCCURRENCE": "After occurrence",
            }
            event_phase = st.selectbox(
                "Phase", options=list(_simple_phase_labels),
                format_func=lambda value: _simple_phase_labels[value],
                key="timeline_phase_" + timeline_analysis_id,
            )
'''
_EVENT_TYPE_OLD = '''            event_type = st.selectbox(
                "Event type",
                options=[
                    "EVENT", "ALARM", "FAILURE", "COMMUNICATION", "ACTION",
                    "DISTRESS", "RESPONSE", "RESCUE", "FIRE",
                    "COLLISION_CONTACT", "GROUNDING", "OTHER",
                ],
                key="timeline_type_" + timeline_analysis_id,
            )
'''
_EVENT_TYPE_NEW = '''            event_type = st.selectbox(
                "Category", options=_TIMELINE_CATEGORY_ORDER,
                format_func=_timeline_category_label,
                key="timeline_type_" + timeline_analysis_id,
                help="Five broad categories keep the chronology readable while evidence and graph detail remain intact.",
            )
'''

def _replace_if_present(source, old, new):
    return source.replace(old, new, 1) if old in source else source

def _replace_default_timeline_table(source):
    section = source.find('        st.markdown("### Default chronology")')
    if section < 0:
        return source
    table_start = source.find("            st.dataframe(\n", section)
    selector_start = source.find("            selected_default_node = st.selectbox(\n", table_start)
    if table_start < 0 or selector_start < 0:
        return source
    return source[:table_start] + _VISUAL_TIMELINE_BLOCK + source[selector_start:]

def _remove_heading_block(source, heading, end_marker, search_start=0):
    heading_pos = source.find(heading, search_start)
    if heading_pos < 0:
        return source
    block_start = source.rfind("                with ch", search_start, heading_pos)
    block_end = source.find(end_marker, heading_pos)
    if block_start < 0 or block_end < 0:
        return source
    return source[:block_start] + source[block_end:]

def _remove_news_charts(source):
    news_start = source.find("with tab_news:\n")
    if news_start < 0:
        return source
    source = _remove_heading_block(
        source, 'st.markdown("#### Alerts by country")',
        "\n\n                ch3, ch4 = st.columns(2)", news_start,
    )
    news_start = source.find("with tab_news:\n")
    source = _remove_heading_block(
        source, 'st.markdown("#### Daily alert count")',
        "\n\n    st.caption(\n", news_start,
    )
    return source

def _remove_shield_app_section(source):
    heading = source.find('st.markdown("### SHIELD classification of contributing factors")')
    if heading < 0:
        return source
    start = source.rfind("with tab_review:\n", 0, heading)
    end = source.find("with tab_about:\n", heading)
    if start < 0 or end < 0:
        return source
    return source[:start] + source[end:]

def transform_app_visual_refinement(source: str) -> tuple[str, tuple[str, ...]]:
    applied = []
    if "import plotly.graph_objects as go\n" not in source:
        source = _replace_if_present(
            source, "import pydeck as pdk\n",
            "import pydeck as pdk\nimport plotly.graph_objects as go\n",
        )
    applied.append("plotly_timeline_dependency")

    anchor = "\n\nwith tab_timeline:\n"
    if _CATEGORY_HELPERS not in source and anchor in source:
        source = source.replace(anchor, _CATEGORY_HELPERS + anchor, 1)
    applied.append("five_timeline_categories")

    source = _replace_default_timeline_table(source)
    source = _replace_if_present(source, _PHASE_SELECT_OLD, _PHASE_SELECT_NEW)
    source = _replace_if_present(source, _EVENT_TYPE_OLD, _EVENT_TYPE_NEW)
    applied.extend(["visual_event_sequence", "timeline_table_in_expander", "five_phase_choices"])

    source = _remove_news_charts(source)
    applied.extend(["remove_alerts_by_country", "remove_daily_alert_count"])

    source = _remove_shield_app_section(source)
    applied.append("hide_shield_from_app_only")
    return source, tuple(applied)
