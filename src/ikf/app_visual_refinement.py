"""Purpose-fit UI refinements for the IKF Databricks App.

This layer intentionally changes presentation only. It preserves the governed
TimelineEvent/KG evidence model, provenance, chronology rules, SHIELD project
capabilities and investigator review workflow while keeping the deployed app
focused on the investigator's core tasks.
"""

from __future__ import annotations


VISUAL_REFINEMENT_VERSION = "IKF_APP_VISUAL_REFINEMENT_V0.2"


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
    "EVENT": "OPERATION_CONTEXT",
    "OTHER": "OPERATION_CONTEXT",
    "ALARM": "FAILURE_HAZARD",
    "FAILURE": "FAILURE_HAZARD",
    "COMMUNICATION": "ACTION_COMMUNICATION",
    "ACTION": "ACTION_COMMUNICATION",
    "FIRE": "ACCIDENT_CONSEQUENCE",
    "COLLISION_CONTACT": "ACCIDENT_CONSEQUENCE",
    "GROUNDING": "ACCIDENT_CONSEQUENCE",
    "DISTRESS": "RESPONSE_RECOVERY",
    "RESPONSE": "RESPONSE_RECOVERY",
    "RESCUE": "RESPONSE_RECOVERY",
}


def _timeline_category_label(category):
    return _TIMELINE_CATEGORY_META.get(
        category,
        _TIMELINE_CATEGORY_META["OPERATION_CONTEXT"],
    )[0]


def _timeline_visual_category(event, reviewed_event=None):
    """Map an event into one of five display categories without an LLM call."""

    reviewed_type = str((reviewed_event or {}).get("event_type") or "").strip().upper()
    if reviewed_type in _TIMELINE_CATEGORY_META:
        return reviewed_type
    if reviewed_type in _OLD_EVENT_TYPE_TO_CATEGORY:
        return _OLD_EVENT_TYPE_TO_CATEGORY[reviewed_type]

    text = " ".join(
        str(event.get(key) or "")
        for key in ("label", "description")
    ).casefold()

    response_terms = (
        "distress", "mayday", "rescue", "rescued", "evacuat", "abandon",
        "emergency response", "firefighting", "fire-fighting", "lifeboat",
        "recovery", "recovered",
    )
    consequence_terms = (
        "collision", "contact", "allision", "ground", "capsiz", "sink",
        "sank", "fire", "explosion", "flood", "injur", "fatal", "death",
        "damage", "pollution", "spill", "person overboard",
    )
    failure_terms = (
        "failure", "failed", "fault", "malfunction", "overheat", "leak",
        "alarm", "loss of pressure", "loss of power", "blackout", "blocked",
        "obstructed", "defect", "breakdown",
    )
    action_terms = (
        "crew", "master", "officer", "engineer", "action", "ordered",
        "communicat", "reported", "called", "requested", "started", "stopped",
        "activated", "manoeuv", "maneuv", "decision",
    )

    if any(term in text for term in response_terms):
        return "RESPONSE_RECOVERY"
    if any(term in text for term in consequence_terms):
        return "ACCIDENT_CONSEQUENCE"
    if any(term in text for term in failure_terms):
        return "FAILURE_HAZARD"
    if any(term in text for term in action_terms):
        return "ACTION_COMMUNICATION"
    return "OPERATION_CONTEXT"


def _short_timeline_label(value, limit=34):
    text = str(value or "Event").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
'''


_VISUAL_TIMELINE_BLOCK = r'''            timeline_rows = []
            for item in default_events:
                reviewed = validated_by_node.get(item.get("node_id"))
                category = _timeline_visual_category(item, reviewed)
                timeline_rows.append(
                    {
                        "item": item,
                        "category": category,
                        "category_label": _timeline_category_label(category),
                        "time_label": default_timeline_time_label(item, audio_anchor),
                        "review": (
                            "Human validated"
                            if reviewed
                            else "Default candidate"
                        ),
                    }
                )

            st.markdown("#### Event sequence")
            st.caption(
                "Five simple categories are used for display. Hover over an event for "
                "its supported time, ordering basis, evidence count and review status. "
                "The horizontal position is sequence order, so events with no supported "
                "clock time remain visible without inventing precision."
            )

            timeline_fig = go.Figure()
            for category in _TIMELINE_CATEGORY_ORDER:
                category_rows = [
                    row for row in timeline_rows
                    if row["category"] == category
                ]
                if not category_rows:
                    continue
                category_label, category_colour = _TIMELINE_CATEGORY_META[category]
                timeline_fig.add_trace(
                    go.Scatter(
                        x=[row["item"].get("sequence_position") for row in category_rows],
                        y=[category_label] * len(category_rows),
                        mode="markers+text",
                        name=category_label,
                        marker={
                            "size": 16,
                            "color": category_colour,
                            "line": {"width": 1, "color": "white"},
                        },
                        text=[
                            _short_timeline_label(row["item"].get("label"))
                            for row in category_rows
                        ],
                        textposition="top center",
                        customdata=[
                            [
                                row["time_label"],
                                row["item"].get("label") or "Event",
                                row["item"].get("ordering_basis") or "—",
                                len(row["item"].get("evidence_references") or []),
                                row["review"],
                            ]
                            for row in category_rows
                        ],
                        hovertemplate=(
                            "<b>%{customdata[1]}</b><br>"
                            "Time: %{customdata[0]}<br>"
                            "Order basis: %{customdata[2]}<br>"
                            "Evidence references: %{customdata[3]}<br>"
                            "Review: %{customdata[4]}"
                            "<extra></extra>"
                        ),
                    )
                )

            timeline_fig.update_layout(
                height=max(390, 280 + 24 * len(default_events)),
                margin={"l": 10, "r": 10, "t": 30, "b": 30},
                xaxis={
                    "title": "Event sequence",
                    "dtick": 1,
                    "fixedrange": False,
                    "showgrid": True,
                    "zeroline": False,
                },
                yaxis={
                    "title": "",
                    "categoryorder": "array",
                    "categoryarray": [
                        _TIMELINE_CATEGORY_META[key][0]
                        for key in reversed(_TIMELINE_CATEGORY_ORDER)
                    ],
                    "fixedrange": True,
                },
                hovermode="closest",
                showlegend=False,
            )
            st.plotly_chart(
                timeline_fig,
                use_container_width=True,
                config={
                    "displaylogo": False,
                    "scrollZoom": True,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                },
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
                st.dataframe(
                    [
                        {
                            "#": row["item"].get("sequence_position"),
                            "Time": row["time_label"],
                            "Category": row["category_label"],
                            "Event": row["item"].get("label") or "Event",
                            "Order basis": row["item"].get("ordering_basis") or "—",
                            "Evidence": len(row["item"].get("evidence_references") or []),
                            "Review": row["review"],
                            "Flag": (
                                "REVIEW"
                                if row["item"].get("ordering_conflict")
                                else ""
                            ),
                        }
                        for row in timeline_rows
                    ],
                    hide_index=True,
                    use_container_width=True,
                )

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
                "Phase",
                options=list(_simple_phase_labels),
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
                "Category",
                options=_TIMELINE_CATEGORY_ORDER,
                format_func=_timeline_category_label,
                key="timeline_type_" + timeline_analysis_id,
                help=(
                    "Five broad categories keep the chronology readable while the "
                    "underlying evidence and Knowledge Graph retain their full detail."
                ),
            )
'''


_COUNTRY_CHART = '''                with ch2:
                    st.markdown("#### Alerts by country")
                    _country = (
                        _filtered[_filtered["match_country"].notna()]
                        .drop_duplicates(subset=["alert_id", "match_country"])
                        .groupby("match_country")["alert_id"].nunique()
                        .sort_values(ascending=False).head(15)
                    )
                    if not _country.empty:
                        st.bar_chart(_country)
'''

_DAILY_CHART = '''                with ch4:
                    st.markdown("#### Daily alert count")
                    _daily = (
                        _filtered.assign(day=_filtered["alert_timestamp"].dt.date)
                        .drop_duplicates(subset=["alert_id", "day"])
                        .groupby("day")["alert_id"].nunique().sort_index()
                    )
                    if not _daily.empty:
                        st.bar_chart(_daily)
'''

_SHIELD_START = '''with tab_review:
    st.divider()
    st.markdown("### SHIELD classification of contributing factors")
'''

_SHIELD_END = '''with tab_about:
'''


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Visual refinement failed at {label}: expected one match, found {count}."
        )
    return source.replace(old, new, 1)


def _replace_default_timeline_table(source: str) -> str:
    section = source.find('        st.markdown("### Default chronology")')
    if section < 0:
        raise RuntimeError("Visual refinement could not locate Default chronology.")
    table_start = source.find("            st.dataframe(\n", section)
    selector_start = source.find(
        "            selected_default_node = st.selectbox(\n",
        table_start,
    )
    if table_start < 0 or selector_start < 0:
        raise RuntimeError("Visual refinement could not isolate the default timeline table.")
    return source[:table_start] + _VISUAL_TIMELINE_BLOCK + source[selector_start:]


def _remove_news_charts(source: str) -> str:
    source = _replace_once(
        source,
        _COUNTRY_CHART,
        "",
        "Alerts by country chart",
    )
    source = _replace_once(
        source,
        _DAILY_CHART,
        "",
        "Daily alert count chart",
    )
    return source


def _remove_shield_app_section(source: str) -> str:
    start = source.find(_SHIELD_START)
    if start < 0:
        raise RuntimeError("Visual refinement could not locate the SHIELD app section.")
    end = source.find(_SHIELD_END, start)
    if end < 0:
        raise RuntimeError("Visual refinement could not locate the end of SHIELD app section.")
    return source[:start] + source[end:]


def transform_app_visual_refinement(source: str) -> tuple[str, tuple[str, ...]]:
    """Apply purpose-fit visual and navigation simplifications."""

    applied: list[str] = []

    source = _replace_once(
        source,
        "import pydeck as pdk\n",
        "import pydeck as pdk\nimport plotly.graph_objects as go\n",
        "Plotly import",
    )
    applied.append("plotly_timeline_dependency")

    timeline_anchor = "\n\nwith tab_timeline:\n"
    source = _replace_once(
        source,
        timeline_anchor,
        _CATEGORY_HELPERS + timeline_anchor,
        "timeline category helpers",
    )
    applied.append("five_timeline_categories")

    source = _replace_default_timeline_table(source)
    applied.extend(["visual_event_sequence", "timeline_table_in_expander"])

    source = _replace_once(
        source,
        _PHASE_SELECT_OLD,
        _PHASE_SELECT_NEW,
        "simplified timeline phases",
    )
    source = _replace_once(
        source,
        _EVENT_TYPE_OLD,
        _EVENT_TYPE_NEW,
        "simplified timeline event categories",
    )
    applied.append("five_phase_choices")

    source = _remove_news_charts(source)
    applied.extend(["remove_alerts_by_country", "remove_daily_alert_count"])

    source = _remove_shield_app_section(source)
    applied.append("hide_shield_from_app_only")

    return source, tuple(applied)
