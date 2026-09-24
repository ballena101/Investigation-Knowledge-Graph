"""Deterministic investigator-workflow transformations for the IKF Streamlit App.

This layer keeps product-workflow changes separate from the core governance and
presentation transformations. It is intentionally deterministic and is applied
after ``app_ui_adoption`` both in the raw bootstrap path and in the materialized
Databricks App bundle.
"""

from __future__ import annotations


WORKFLOW_ADOPTION_VERSION = "IKF_APP_WORKFLOW_ADOPTION_V0.1"


_GRAPH_REVIEW_HELPER = r'''
def apply_latest_relationship_reviews_to_graph(
    analysis_id,
    graph,
    model_run_id=None,
):
    """Return a reviewed graph projection without mutating the persisted AI graph."""

    review_query = """
    MATCH (review:RelationshipReview {analysis_id: $analysis_id})
    WITH review
    ORDER BY review.reviewed_at DESC
    WITH review.edge_id AS edge_id, collect(review)[0] AS latest
    RETURN
        edge_id,
        latest.model_run_id AS model_run_id,
        latest.human_review_decision AS decision,
        latest.amended_relationship AS amended_relationship
    """

    with get_driver().session() as session:
        latest_reviews = {
            record["edge_id"]: record.data()
            for record in session.run(
                review_query,
                analysis_id=analysis_id,
            )
        }

    reviewed_edges = []
    hidden_rejected = 0
    amended_count = 0
    validated_count = 0

    for edge in graph.get("edges") or []:
        if edge.get("edge_class") == "STRUCTURAL":
            reviewed_edges.append(edge)
            continue

        review = latest_reviews.get(edge.get("edge_id"))
        if (
            review
            and model_run_id
            and review.get("model_run_id")
            and review.get("model_run_id") != model_run_id
        ):
            review = None

        if not review:
            reviewed_edges.append(edge)
            continue

        decision = str(review.get("decision") or "").upper()
        if decision == "REJECTED":
            hidden_rejected += 1
            continue

        effective_edge = dict(edge)
        effective_edge["human_review_decision"] = decision

        if decision == "AMENDED" and review.get("amended_relationship"):
            effective_edge["relationship"] = review["amended_relationship"]
            amended_count += 1
        elif decision == "VALIDATED":
            validated_count += 1

        reviewed_edges.append(effective_edge)

    return {
        "nodes": list(graph.get("nodes") or []),
        "edges": reviewed_edges,
        "review_projection": {
            "hidden_rejected": hidden_rejected,
            "amended": amended_count,
            "validated": validated_count,
        },
    }
'''


_SHIELD_SECTION = r'''with tab_review:
    st.divider()
    st.markdown("### SHIELD classification of contributing factors")
    st.caption(
        "SHIELD is shown as an LLM-proposed taxonomy match beside each contributing "
        "factor. The model may classify a factor only after its CONTRIBUTED_TO "
        "relationship has been human validated or amended to CONTRIBUTED_TO. "
        "No manual SHIELD label selection is required."
    )

    shield_analysis_id = selected_review_analysis_id
    shield_model_run_id = selected_review_model_run_id

    contributing_factor_nodes = [
        node
        for node in (selected_review_graph.get("nodes") or [])
        if node.get("node_kind") == "ContributingFactor"
    ]

    shield_eligible = (
        load_shield_gate_eligible_factors(
            shield_analysis_id,
            shield_model_run_id,
        )
        if shield_analysis_id and shield_model_run_id
        else []
    )
    shield_proposals = (
        load_shield_proposals(
            shield_analysis_id,
            shield_model_run_id,
        )
        if shield_analysis_id and shield_model_run_id
        else []
    )

    eligible_by_factor = {}
    for factor in shield_eligible:
        eligible_by_factor.setdefault(
            factor["factor_node_id"],
            [],
        ).append(factor)

    proposals_by_factor = {}
    for proposal in shield_proposals:
        if proposal.get("gate_is_current"):
            proposals_by_factor.setdefault(
                proposal["factor_node_id"],
                [],
            ).append(proposal)

    shield_rows = []
    for factor in sorted(
        contributing_factor_nodes,
        key=lambda item: str(item.get("label") or "").casefold(),
    ):
        factor_id = factor.get("node_id")
        eligible_rows = eligible_by_factor.get(factor_id, [])
        proposals = proposals_by_factor.get(factor_id, [])

        target_labels = sorted(
            {
                str(item.get("target_label"))
                for item in eligible_rows
                if item.get("target_label")
            }
        )

        shield_matches = []
        for proposal in proposals:
            if proposal.get("assistant_status") != "ASSISTANT_PROPOSED":
                continue
            parts = [
                proposal.get("proposed_shield_path"),
                proposal.get("proposed_shield_label"),
            ]
            text = " → ".join(
                str(part)
                for part in parts
                if part
            )
            if proposal.get("proposed_shield_code"):
                text += " [" + str(proposal["proposed_shield_code"]) + "]"
            if text:
                shield_matches.append(text)

        shield_matches = list(dict.fromkeys(shield_matches))

        if shield_matches:
            shield_value = " · ".join(shield_matches)
            shield_status = "LLM match available"
        elif proposals:
            shield_value = "No grounded SHIELD match"
            shield_status = "LLM found no supported match"
        elif eligible_rows:
            shield_value = "—"
            shield_status = "Ready for LLM classification"
        else:
            shield_value = "—"
            shield_status = "Awaiting validated CONTRIBUTED_TO relation"

        shield_rows.append(
            {
                "Contributing factor": factor.get("label") or factor_id,
                "Validated contributes to": (
                    " · ".join(target_labels)
                    if target_labels
                    else "—"
                ),
                "SHIELD (LLM)": shield_value,
                "Status": shield_status,
            }
        )

    if shield_rows:
        st.dataframe(
            shield_rows,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No contributing factors are available in the selected model graph."
        )

    shield_documents = load_shield_documents()
    shield_ready_count = sum(
        1
        for row in shield_rows
        if row["Status"] == "Ready for LLM classification"
    )

    shield_action, shield_refresh = st.columns([1.6, 0.4])
    with shield_action:
        generate_shield = st.button(
            "Generate / refresh LLM SHIELD matches",
            type="primary",
            disabled=(
                not shield_analysis_id
                or not shield_model_run_id
                or not shield_eligible
                or not shield_documents
                or not SHIELD_PROPOSAL_JOB_ID
            ),
            key="generate_shield_proposals",
        )
    with shield_refresh:
        refresh_shield = st.button(
            "↻",
            help="Refresh SHIELD matches",
            disabled=(
                not shield_analysis_id
                or not shield_model_run_id
            ),
            key="refresh_shield_status",
            use_container_width=True,
        )

    if shield_ready_count:
        st.caption(
            str(shield_ready_count)
            + " validated contributing factor(s) are ready for LLM SHIELD classification."
        )

    if not shield_documents:
        st.warning(
            "The persistent SHIELD corpus is not indexed yet."
        )
    elif not SHIELD_PROPOSAL_JOB_ID:
        st.caption(
            "The SHIELD proposal Job is not attached to this App deployment."
        )

    if refresh_shield:
        load_shield_gate_eligible_factors.clear()
        load_shield_proposals.clear()
        load_shield_documents.clear()
        st.rerun()

    if generate_shield:
        try:
            shield_job_run_id = trigger_shield_proposal_job(
                shield_analysis_id,
                shield_model_run_id,
            )
            load_shield_proposals.clear()
            st.success(
                "LLM SHIELD classification queued. Refresh when the run completes."
            )
            st.caption("Databricks run: " + shield_job_run_id)
        except Exception as exc:
            st.error("SHIELD classification could not be queued.")
            st.exception(exc)
'''


def _replace_exact_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"IKF workflow adoption failed at {name}: expected exactly one match, found {count}."
        )
    return source.replace(old, new, 1)


def transform_app_workflow_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Apply the investigator workflow agreed for the operational App."""

    applied: list[str] = []

    source = _replace_exact_once(
        source,
        '"Optional. Briefly describe the case or evidence set. "\n                "This is descriptive metadata only and does not steer extraction."',
        '"Optional. Briefly describe the case or evidence set. "\n                "This gives the LLM contextual orientation during extraction and "\n                "cross-document resolution, but it is not source evidence and must "\n                "not be used to introduce unsupported facts."',
        "analysis-description explanation",
    )
    applied.append("analysis_description_explanation")

    ask_start = source.find("@st.fragment\ndef render_compare_llms():")
    direct_start = source.find("@st.fragment\ndef render_direct_reference_ask():")
    if ask_start < 0 or direct_start < 0 or direct_start <= ask_start:
        raise RuntimeError("IKF workflow adoption could not locate Ask LLMs fragments.")
    ask_fragment = source[ask_start:direct_start]
    form_marker = "            ask_question_col, ask_refresh_col = st.columns([0.92, 0.08])\n"
    history_marker = "            question_runs = [\n"
    form_index = ask_fragment.find(form_marker)
    history_index = ask_fragment.find(history_marker)
    if form_index < 0 or history_index < 0 or history_index <= form_index:
        raise RuntimeError("IKF workflow adoption could not reorder Ask LLMs history.")
    reordered = (
        ask_fragment[:form_index]
        + ask_fragment[history_index:]
        + "\n\n"
        + ask_fragment[form_index:history_index]
    )
    source = source[:ask_start] + reordered + source[direct_start:]
    applied.append("ask_history_before_question")

    findings_anchor = '''        knowledge_meta = knowledge_by_id[
            knowledge_analysis_id
        ]

        st.info(
'''
    findings_replacement = '''        knowledge_meta = knowledge_by_id[
            knowledge_analysis_id
        ]
        knowledge_result = load_analysis_result(
            knowledge_analysis_id
        )

        st.markdown("### Brief analysis summary")
        if knowledge_result.get("overview"):
            st.info(knowledge_result["overview"])
        else:
            st.caption(
                "No brief analysis summary is stored for this completed evidence set."
            )

        st.info(
'''
    source = _replace_exact_once(
        source,
        findings_anchor,
        findings_replacement,
        "Findings brief analysis summary",
    )
    applied.append("findings_brief_summary")

    emcip_start = source.find("with tab_mapping_review:\n")
    about_start = source.find("\nwith tab_about:\n", emcip_start)
    if emcip_start < 0 or about_start < 0:
        raise RuntimeError("IKF workflow adoption could not locate EMCIP/SHIELD review section.")
    source = source[:emcip_start] + _SHIELD_SECTION + source[about_start:]
    applied.append("remove_emcip_ui")
    applied.append("shield_factor_mapping_view")

    graph_marker = "\nwith tab_knowledge_graph:\n"
    if graph_marker not in source:
        raise RuntimeError("IKF workflow adoption could not locate Knowledge Graph workspace.")
    source = source.replace(
        graph_marker,
        "\n" + _GRAPH_REVIEW_HELPER + graph_marker,
        1,
    )

    raw_graph_anchor = '''        else:
            raw_graph = load_analysis_graph(
                graph_analysis_id
            )

        graph_sources = load_analysis_sources(
'''
    raw_graph_replacement = '''        else:
            raw_graph = load_analysis_graph(
                graph_analysis_id
            )

        raw_graph = apply_latest_relationship_reviews_to_graph(
            graph_analysis_id,
            raw_graph,
            graph_model_run_id,
        )
        review_projection = raw_graph.get("review_projection") or {}
        if (
            review_projection.get("hidden_rejected")
            or review_projection.get("amended")
            or review_projection.get("validated")
        ):
            st.caption(
                "Reviewed projection: "
                + str(review_projection.get("validated") or 0)
                + " validated · "
                + str(review_projection.get("amended") or 0)
                + " amended · "
                + str(review_projection.get("hidden_rejected") or 0)
                + " rejected relationship(s) hidden."
            )

        graph_sources = load_analysis_sources(
'''
    source = _replace_exact_once(
        source,
        raw_graph_anchor,
        raw_graph_replacement,
        "reviewed graph projection",
    )
    applied.append("reviewed_graph_projection")

    graph_question_start = source.find(
        '        st.divider()\n        st.markdown("### Ask about this graph scope")\n'
    )
    graph_review_start = source.find("\nwith tab_review:\n", graph_question_start)
    if graph_question_start < 0 or graph_review_start < 0:
        raise RuntimeError("IKF workflow adoption could not locate graph-question section.")
    source = source[:graph_question_start] + source[graph_review_start:]
    applied.append("remove_graph_questions")

    replacements = (
        (
            '"type and layout, and ask questions against the same governed scope."',
            '"type and layout, using the latest human relationship decisions."',
        ),
        (
            '"Diagram controls change the view only; graph knowledge changes require human review."',
            '"Rejected relationships are hidden and amended relationships are shown with their reviewed type."',
        ),
        (
            '"proposals, EMCIP mappings and SHIELD classifications."',
            '"proposals and LLM SHIELD matches for validated contributing factors."',
        ),
        (
            '"concept/relationship filters, layout controls and graph-scoped questions."',
            '"concept/relationship filters, layout controls and a reviewed relationship projection."',
        ),
        (
            '"correction proposals, EMCIP mappings and SHIELD classifications."',
            '"correction proposals, with LLM SHIELD classification after contributing-factor validation."',
        ),
        (
            '"Assistant outputs are proposals. Human relationship, EMCIP and SHIELD review\nrecords remain append-only and authoritative according to their governed\nworkflow. Assistant correction checks never overwrite graph edges."',
            '"Assistant outputs remain proposals. Human relationship review records remain\nappend-only and authoritative. SHIELD is an LLM-proposed taxonomy derivative\nof human-validated contributing-factor relationships. The persisted raw AI graph\nis retained for traceability; the displayed graph applies the latest reviews."',
        ),
    )
    for old, new in replacements:
        if old in source:
            source = source.replace(old, new, 1)
    applied.append("workflow_wording_cleanup")

    return source, tuple(applied)
