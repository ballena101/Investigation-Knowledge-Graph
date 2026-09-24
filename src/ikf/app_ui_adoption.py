"""Deterministic UI source transformations for the IKF Streamlit App.

These transformations are deliberately separated from governance adoption. They
only change investigator-facing presentation and are applied both by the raw
bootstrap path and by the materialized Databricks App bundle builder.
"""

from __future__ import annotations

import re


UI_ADOPTION_VERSION = "IKF_APP_UI_ADOPTION_V0.2"


_ACTIVE_ANALYSIS_PATTERN = re.compile(
    r"        h1, h2, h3, h4 = st\.columns\(\n"
    r"(?:.|\n)*?"
    r"        h4\.metric\(\n"
    r"            \"Status\",\n"
    r"            active_analysis\.get\(\n"
    r"                \"status\"\n"
    r"            \)\n"
    r"            or \"UNKNOWN\",\n"
    r"        \)\n",
)

_ACTIVE_ANALYSIS_REPLACEMENT = '''        h1, h2, h3, h4 = st.columns(
            [2.6, 0.7, 0.8, 1.0]
        )
        active_analysis_title = html.escape(
            str(active_analysis.get("analysis_title") or active_analysis_id)
        )
        active_analysis_class = html.escape(
            str(active_analysis.get("information_class") or "—")
        )
        active_analysis_sources = html.escape(
            "Text"
            if active_analysis.get("input_mode") == "DIRECT_TEXT"
            else str(active_analysis.get("document_count") or 0)
        )
        active_analysis_status = html.escape(
            str(active_analysis.get("status") or "UNKNOWN")
        )

        with h1:
            st.markdown(
                (
                    '<div style="font-size:1.05rem;font-weight:700;'
                    'color:#1f77b4;line-height:1.3;margin-top:0.18rem;">'
                    f'Active analysis: {active_analysis_title}</div>'
                ),
                unsafe_allow_html=True,
            )
            st.caption("ID: " + active_analysis_id)

        h2.markdown(
            (
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Class</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                f'{active_analysis_class}</div>'
            ),
            unsafe_allow_html=True,
        )
        h3.markdown(
            (
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Sources</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                f'{active_analysis_sources}</div>'
            ),
            unsafe_allow_html=True,
        )
        h4.markdown(
            (
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Status</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                f'{active_analysis_status}</div>'
            ),
            unsafe_allow_html=True,
        )
'''

_ASK_TOP_REFRESH = '''    if st.button(
        "↻",
        key="refresh_analysis_status",
        help="Refresh question and analysis status",
    ):
        load_analysis_groups.clear()
        load_analysis_sources.clear()
        load_analysis_text_source.clear()
        load_analysis_graph_counts.clear()
        load_analysis_evidence_counts.clear()
        load_analysis_result.clear()
        load_analysis_graph.clear()
        load_model_runs.clear()
        load_model_run_graph.clear()
        load_question_runs.clear()
        load_question_model_runs.clear()
        st.toast("Status refreshed")

'''

_ASK_FORM = '''            with st.form(
                (
                    "ask_question_form_"
                    + selected_analysis_id
                ),
                clear_on_submit=False,
            ):
                ask_question_text = st.text_area(
                    "Question",
                    placeholder=(
                        "Example: What factors contributed to the contact "
                        "with the quay?"
                    ),
                    height=120,
                )
                ask_submitted = st.form_submit_button(
                    "Ask",
                    type="primary",
                )
'''

_ASK_FORM_WITH_REFRESH = '''            ask_question_col, ask_refresh_col = st.columns([0.92, 0.08])
            with ask_question_col:
                with st.form(
                    (
                        "ask_question_form_"
                        + selected_analysis_id
                    ),
                    clear_on_submit=False,
                ):
                    ask_question_text = st.text_area(
                        "Question",
                        placeholder=(
                            "Example: What factors contributed to the contact "
                            "with the quay?"
                        ),
                        height=120,
                    )
                    ask_submitted = st.form_submit_button(
                        "Ask",
                        type="primary",
                    )

            with ask_refresh_col:
                st.caption("Refresh")
                if st.button(
                    "↻",
                    key="refresh_analysis_status",
                    help="Refresh question and answer status",
                    use_container_width=True,
                ):
                    load_analysis_groups.clear()
                    load_analysis_sources.clear()
                    load_analysis_text_source.clear()
                    load_analysis_graph_counts.clear()
                    load_analysis_evidence_counts.clear()
                    load_analysis_result.clear()
                    load_analysis_graph.clear()
                    load_model_runs.clear()
                    load_model_run_graph.clear()
                    load_question_runs.clear()
                    load_question_model_runs.clear()
                    st.toast("Question status refreshed")
'''

_REVIEW_START = '    st.markdown("**Supporting evidence**")\n'
_REVIEW_END = (
    '\n\nwith tab_review:\n'
    '    st.divider()\n'
    '    st.markdown("### Optional relationship quality check")\n'
)

_COMPACT_REVIEW = r'''    st.markdown("**Supporting evidence and human decision**")
    review_evidence_col, review_decision_col = st.columns(2, gap="large")

    with review_evidence_col:
        references = selected.get("evidence_references") or []
        if references:
            st.markdown("**Supporting evidence**")
            for reference in references:
                st.write(f"• {reference}")
        else:
            st.info(
                selected["evidence"]
                or "No page-level source reference is available for this relationship."
            )

        passage_ids = selected.get("passage_ids") or []
        if passage_ids:
            with st.expander("Technical evidence IDs", expanded=False):
                for passage_id in passage_ids:
                    st.code(passage_id, language=None)

        review_locations = [
            parsed
            for parsed in (
                parse_evidence_location(value)
                for value in (selected.get("evidence_locations") or [])
            )
            if parsed is not None
        ]

        if selected_review_analysis_id and review_locations:
            review_sources = load_analysis_sources(selected_review_analysis_id)
            review_source_by_id = {
                source["document_id"]: source
                for source in review_sources
            }

            review_location_index = st.selectbox(
                "Evidence page",
                options=list(range(len(review_locations))),
                format_func=lambda index: format_evidence_location(
                    review_locations[index],
                    review_source_by_id.get(
                        review_locations[index]["document_id"]
                    ),
                ),
                key=(
                    "relationship_review_page_"
                    + selected["edge_id"]
                ),
                disabled=review_controls_disabled,
            )

            review_location = review_locations[review_location_index]
            review_source = review_source_by_id.get(
                review_location["document_id"]
            )

            if review_source:
                review_path = review_source.get("viewer_source_path")
                review_type = str(
                    review_source.get("source_type") or ""
                ).upper()

                if review_type == "PDF" and review_path:
                    try:
                        review_pdf = download_source_file_as_user(review_path)
                        review_excerpt = pdf_page_range_bytes(
                            review_pdf,
                            review_location.get("page_start"),
                            review_location.get("page_end"),
                        )
                        st.pdf(
                            review_excerpt,
                            height=340,
                            key=(
                                "relationship_review_pdf_"
                                + hashlib.sha256(
                                    (
                                        selected["edge_id"]
                                        + "|"
                                        + review_path
                                        + "|"
                                        + str(review_location.get("page_start"))
                                    ).encode("utf-8")
                                ).hexdigest()[:16]
                            ),
                        )
                    except PermissionError as exc:
                        st.warning(str(exc))
                    except Exception as exc:
                        st.caption(
                            "The cited source page could not be rendered: "
                            + str(exc)
                        )
                else:
                    st.caption(
                        "A page citation exists, but this source is not available as an embedded PDF."
                    )
            else:
                st.caption(
                    "The cited document is not linked to the selected analysis."
                )
        elif selected_index is not None:
            st.caption(
                "No page-level evidence location is stored for this relationship. "
                "Older analyses may require rerunning."
            )

    with review_decision_col:
        if latest:
            st.markdown("**Latest human review**")
            latest_text = (
                f"{latest['decision']} · "
                f"{latest['reviewed_at']} · "
                f"{latest['reviewer_email'] or latest['reviewer_username'] or 'unknown'}"
            )
            st.write(latest_text)

            if latest["amended_relationship"]:
                st.write(
                    "Amended relationship:",
                    latest["amended_relationship"],
                )

            if latest["review_comment"]:
                st.write("Comment:", latest["review_comment"])

        decision = st.radio(
            "Human decision",
            options=["VALIDATED", "REJECTED", "AMENDED"],
            horizontal=True,
            key="relationship_decision",
        )

        amended_relationship = None
        if decision == "AMENDED":
            amended_relationship = st.selectbox(
                "Amended relationship",
                options=[
                    "RESULTED_IN",
                    "CONTRIBUTED_TO",
                    "AFFECTED",
                    "FOLLOWED_BY",
                    "SUPPORTS",
                ],
                key="relationship_amended_value",
            )

        comment = st.text_area(
            "Review comment",
            placeholder=(
                "Optional for validation; strongly recommended for rejection "
                "or amendment."
            ),
            key="relationship_review_comment",
            height=100,
        )

        reviewer = get_reviewer_identity()
        reviewer_display = (
            reviewer["email"]
            if reviewer["email"] != "unknown"
            else reviewer["username"]
        )
        st.caption(f"Reviewer recorded as: {reviewer_display}")

        if st.button(
            "Save human review",
            type="primary",
            disabled=review_controls_disabled,
        ):
            try:
                review_id = save_relationship_review(
                    selected,
                    analysis_id=selected_review_analysis_id,
                    decision=decision,
                    amended_relationship=amended_relationship,
                    comment=comment.strip(),
                )
                st.success(
                    f"Review saved: {decision} — review ID {review_id}"
                )
                st.rerun()
            except Exception as exc:
                st.error(
                    "The review could not be saved to Neo4j. "
                    "The App credentials may be read-only."
                )
                st.exception(exc)
'''


def _replace_exact_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"IKF App UI adoption failed at {name}: expected exactly one match, found {count}."
        )
    return source.replace(old, new, 1)


def transform_app_ui_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Apply strict presentation-only transformations to the App source."""

    applied: list[str] = []

    if "import html\n" not in source:
        import_anchor = "import hashlib\n"
        if import_anchor not in source:
            raise RuntimeError(
                "IKF App UI adoption could not locate the import anchor."
            )
        source = source.replace(
            import_anchor,
            import_anchor + "import html\n",
            1,
        )
        applied.append("html_escape_import")

    source, count = _ACTIVE_ANALYSIS_PATTERN.subn(
        _ACTIVE_ANALYSIS_REPLACEMENT,
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError(
            "IKF App UI adoption failed at active-analysis header: "
            f"expected exactly one match, found {count}."
        )
    applied.append("active_analysis_header")

    if "Ask / Compare LLMs" not in source:
        raise RuntimeError("IKF App UI adoption could not locate Ask / Compare LLMs labels.")
    source = source.replace("Ask / Compare LLMs", "Ask LLMs")
    applied.append("ask_llms_title")

    source = _replace_exact_once(
        source,
        _ASK_TOP_REFRESH,
        "",
        "Ask top refresh removal",
    )
    source = _replace_exact_once(
        source,
        _ASK_FORM,
        _ASK_FORM_WITH_REFRESH,
        "Ask question refresh placement",
    )
    source = source.replace(
        '"Question queued. Use Refresh status above to "\n                            "update the answer."',
        '"Question queued. Use Refresh beside the question to "\n                            "update the answer."',
        1,
    )
    source = source.replace(
        '"The question is being processed. Use Refresh status "\n                        "to update this view."',
        '"The question is being processed. Use Refresh beside the question "\n                        "to update this view."',
        1,
    )
    applied.append("ask_refresh_beside_question")

    end_count = source.count(_REVIEW_END)
    if end_count != 1:
        raise RuntimeError(
            "IKF App UI adoption failed at relationship review boundary: "
            f"expected exactly one optional-quality boundary, found {end_count}."
        )
    end = source.index(_REVIEW_END)
    start = source.rfind(_REVIEW_START, 0, end)
    if start < 0:
        raise RuntimeError(
            "IKF App UI adoption could not locate the relationship review evidence block."
        )
    relationship_block = source[start:end]
    required_markers = (
        '"Evidence page"',
        '"Human decision"',
        '"Save human review"',
    )
    missing_markers = [
        marker for marker in required_markers if marker not in relationship_block
    ]
    if missing_markers:
        raise RuntimeError(
            "IKF App UI adoption selected an unexpected review block; missing: "
            + ", ".join(missing_markers)
        )
    source = source[:start] + _COMPACT_REVIEW + source[end:]
    applied.append("compact_relationship_review")

    return source, tuple(applied)
