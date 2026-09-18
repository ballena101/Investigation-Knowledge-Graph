import os
import re
import time
import uuid

import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem
from neo4j import GraphDatabase
from streamlit_cytoscape import (
    streamlit_cytoscape,
    NodeStyle,
    EdgeStyle,
)

CASE_ID = "commodore_clipper_2010"
GRAPH_VERSION = "CASE_GRAPH_V0.2"

st.set_page_config(
    page_title="Commodore Clipper Knowledge Graph",
    page_icon="🔗",
    layout="wide",
)

st.title("Commodore Clipper Knowledge Graph")
st.caption(
    "Evidence-grounded knowledge graph and investigator review workspace."
)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")
RELATIONSHIP_REVIEW_TABLE = os.getenv("RELATIONSHIP_REVIEW_TABLE")

missing_graph_variables = [
    name
    for name, value in {
        "NEO4J_URI": NEO4J_URI,
        "NEO4J_USERNAME": NEO4J_USERNAME,
        "NEO4J_PASSWORD": NEO4J_PASSWORD,
    }.items()
    if not value
]

if missing_graph_variables:
    st.error(
        "Missing Databricks App environment variables: "
        + ", ".join(missing_graph_variables)
    )
    st.stop()


def valid_uc_table_name(value: str | None) -> bool:
    if not value:
        return False
    return bool(
        re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*\."
            r"[A-Za-z_][A-Za-z0-9_]*\."
            r"[A-Za-z_][A-Za-z0-9_]*",
            value,
        )
    )


REVIEW_ENABLED = bool(
    WAREHOUSE_ID
    and valid_uc_table_name(RELATIONSHIP_REVIEW_TABLE)
)


@st.cache_resource
def get_driver():
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    return driver


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient()


@st.cache_data(ttl=60)
def load_graph():
    query = """
    MATCH (source:KGNode {case_id: $case_id})
          -[r]->
          (target:KGNode {case_id: $case_id})
    RETURN
        source.node_id AS source_id,
        source.label AS source_name,
        source.node_kind AS source_kind,
        source.proposed_emcip_entity AS source_emcip_entity,
        source.mapping_disposition AS source_mapping_disposition,
        source.emcip_mappings AS source_emcip_mappings,
        r.edge_id AS edge_id,
        type(r) AS relationship,
        r.edge_class AS edge_class,
        r.evidence_status AS evidence_status,
        r.evidence_anchor AS evidence_anchor,
        r.evidence AS evidence,
        target.node_id AS target_id,
        target.label AS target_name,
        target.node_kind AS target_kind,
        target.proposed_emcip_entity AS target_emcip_entity,
        target.mapping_disposition AS target_mapping_disposition,
        target.emcip_mappings AS target_emcip_mappings
    ORDER BY source_name, relationship, target_name
    """
    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(query, case_id=CASE_ID)
        ]


def state_name(response) -> str:
    state = getattr(getattr(response, "status", None), "state", None)
    if state is None:
        return "UNKNOWN"
    return getattr(state, "value", str(state)).upper()


def execute_sql(statement: str, parameters=None):
    response = get_workspace_client().statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=statement,
        parameters=parameters or [],
        wait_timeout="10s",
    )

    for _ in range(60):
        state = state_name(response)
        if state not in {"PENDING", "RUNNING"}:
            break
        time.sleep(0.5)
        response = get_workspace_client().statement_execution.get_statement(
            response.statement_id
        )

    state = state_name(response)
    if state != "SUCCEEDED":
        error = getattr(getattr(response, "status", None), "error", None)
        raise RuntimeError(
            f"Databricks SQL statement finished with state {state}: {error}"
        )

    return response


def get_reviewer_identity():
    try:
        headers = st.context.headers
        return {
            "email": headers.get("X-Forwarded-Email")
            or headers.get("x-forwarded-email")
            or "unknown",
            "user_id": headers.get("X-Forwarded-User")
            or headers.get("x-forwarded-user")
            or "unknown",
            "username": headers.get("X-Forwarded-Preferred-Username")
            or headers.get("x-forwarded-preferred-username")
            or "unknown",
        }
    except Exception:
        return {
            "email": "unknown",
            "user_id": "unknown",
            "username": "unknown",
        }


def sql_param(name: str, value):
    return StatementParameterListItem(
        name=name,
        value=None if value is None else str(value),
    )


def save_relationship_review(
    edge,
    decision: str,
    amended_relationship: str | None,
    comment: str,
):
    reviewer = get_reviewer_identity()

    status_by_decision = {
        "VALIDATED": "HUMAN_VALIDATED",
        "REJECTED": "HUMAN_REJECTED",
        "AMENDED": "HUMAN_AMENDED",
    }

    statement = f"""
    INSERT INTO {RELATIONSHIP_REVIEW_TABLE} (
        review_id,
        case_id,
        graph_version,
        edge_id,
        source_node_id,
        source_label,
        original_relationship,
        target_node_id,
        target_label,
        assistant_review_status,
        human_review_decision,
        human_review_status,
        amended_relationship,
        reviewer_email,
        reviewer_user_id,
        reviewer_username,
        reviewed_at,
        review_comment
    )
    VALUES (
        :review_id,
        :case_id,
        :graph_version,
        :edge_id,
        :source_node_id,
        :source_label,
        :original_relationship,
        :target_node_id,
        :target_label,
        :assistant_review_status,
        :human_review_decision,
        :human_review_status,
        :amended_relationship,
        :reviewer_email,
        :reviewer_user_id,
        :reviewer_username,
        current_timestamp(),
        :review_comment
    )
    """

    parameters = [
        sql_param("review_id", str(uuid.uuid4())),
        sql_param("case_id", CASE_ID),
        sql_param("graph_version", GRAPH_VERSION),
        sql_param("edge_id", edge["edge_id"]),
        sql_param("source_node_id", edge["source_id"]),
        sql_param("source_label", edge["source_name"]),
        sql_param("original_relationship", edge["relationship"]),
        sql_param("target_node_id", edge["target_id"]),
        sql_param("target_label", edge["target_name"]),
        sql_param("assistant_review_status", edge["evidence_status"]),
        sql_param("human_review_decision", decision),
        sql_param("human_review_status", status_by_decision[decision]),
        sql_param("amended_relationship", amended_relationship),
        sql_param("reviewer_email", reviewer["email"]),
        sql_param("reviewer_user_id", reviewer["user_id"]),
        sql_param("reviewer_username", reviewer["username"]),
        sql_param("review_comment", comment or None),
    ]

    execute_sql(statement, parameters)


def load_reviewed_edge_ids():
    if not REVIEW_ENABLED:
        return set()

    statement = f"""
    SELECT DISTINCT edge_id
    FROM {RELATIONSHIP_REVIEW_TABLE}
    WHERE case_id = :case_id
    """

    response = execute_sql(
        statement,
        [sql_param("case_id", CASE_ID)],
    )

    data_array = getattr(getattr(response, "result", None), "data_array", None)
    if not data_array:
        return set()

    return {row[0] for row in data_array if row and row[0]}


try:
    rows = load_graph()
except Exception as exc:
    st.error("Could not connect to the Neo4j knowledge graph.")
    st.exception(exc)
    st.stop()

if not rows:
    st.warning(
        "The Neo4j connection succeeded, but no relationships "
        "were found for the Commodore Clipper case."
    )
    st.stop()


def mappings_to_text(mappings):
    if not mappings:
        return "No validated EMCIP mapping"
    return " | ".join(mappings)


nodes = {}
edges = []

for row in rows:
    nodes[row["source_id"]] = {
        "data": {
            "id": row["source_id"],
            "label": row["source_kind"],
            "name": row["source_name"],
            "node_kind": row["source_kind"],
            "proposed_emcip_entity": row["source_emcip_entity"] or "—",
            "mapping_disposition": row["source_mapping_disposition"] or "—",
            "emcip_mappings": mappings_to_text(row["source_emcip_mappings"]),
        }
    }

    nodes[row["target_id"]] = {
        "data": {
            "id": row["target_id"],
            "label": row["target_kind"],
            "name": row["target_name"],
            "node_kind": row["target_kind"],
            "proposed_emcip_entity": row["target_emcip_entity"] or "—",
            "mapping_disposition": row["target_mapping_disposition"] or "—",
            "emcip_mappings": mappings_to_text(row["target_emcip_mappings"]),
        }
    }

    edges.append({
        "data": {
            "id": row["edge_id"],
            "label": row["relationship"],
            "source": row["source_id"],
            "target": row["target_id"],
            "relationship": row["relationship"],
            "edge_class": row["edge_class"] or "—",
            "evidence_status": row["evidence_status"] or "—",
            "evidence_anchor": row["evidence_anchor"] or "—",
            "evidence": row["evidence"] or (
                "Structural relationship; no report evidence required."
            ),
        }
    })

elements = {
    "nodes": list(nodes.values()),
    "edges": edges,
}

validated_edges = sum(
    1 for edge in edges
    if edge["data"]["evidence_status"] == "ASSISTANT_VALIDATED"
)

node_styles = [
    NodeStyle(
        label="Occurrence",
        caption="name",
        custom_styles={
            "shape": "round-rectangle",
            "width": 120,
            "height": 70,
            "text-wrap": "wrap",
            "text-max-width": 150,
            "font-size": 11,
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="Vessel",
        caption="name",
        custom_styles={
            "shape": "round-rectangle",
            "width": 110,
            "height": 70,
            "text-wrap": "wrap",
            "text-max-width": 150,
            "font-size": 11,
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="Event",
        caption="name",
        custom_styles={
            "shape": "ellipse",
            "width": 110,
            "height": 110,
            "text-wrap": "wrap",
            "text-max-width": 150,
            "font-size": 11,
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="ContributingFactor",
        caption="name",
        custom_styles={
            "shape": "diamond",
            "width": 115,
            "height": 115,
            "text-wrap": "wrap",
            "text-max-width": 150,
            "font-size": 11,
            "border-width": 2,
        },
    ),
]

edge_styles = [
    EdgeStyle(
        label="RESULTED_IN",
        caption="label",
        directed=True,
        curve_style="bezier",
    ),
    EdgeStyle(
        label="AFFECTED",
        caption="label",
        directed=True,
        curve_style="bezier",
    ),
    EdgeStyle(
        label="CONTRIBUTED_TO",
        caption="label",
        directed=True,
        curve_style="bezier",
    ),
    EdgeStyle(
        label="HAS_VESSEL",
        caption="label",
        directed=True,
        curve_style="bezier",
    ),
]

tab_graph, tab_review, tab_about = st.tabs(
    ["Knowledge graph", "Relationship review", "About"]
)

with tab_graph:
    c1, c2, c3 = st.columns(3)
    c1.metric("Nodes", len(nodes))
    c2.metric("Relationships", len(edges))
    c3.metric("Evidence-validated", validated_edges)

    st.subheader("Interactive knowledge graph")
    st.caption(
        "Select a node or relationship to inspect its properties, "
        "EMCIP mapping and supporting evidence."
    )

    streamlit_cytoscape(
        elements=elements,
        layout="fcose",
        node_styles=node_styles,
        edge_styles=edge_styles,
        height=700,
        key="commodore_clipper_graph",
    )

with tab_review:
    st.subheader("Relationship review")
    st.caption(
        "Human review is stored separately from assistant review. "
        "The original graph is not overwritten by a validation click."
    )

    reviewable_rows = [
        row for row in rows
        if row["relationship"] != "HAS_VESSEL"
    ]

    if REVIEW_ENABLED:
        try:
            reviewed_edge_ids = load_reviewed_edge_ids()
            r1, r2, r3 = st.columns(3)
            r1.metric("Reviewable relationships", len(reviewable_rows))
            r2.metric("Human reviewed", len(reviewed_edge_ids))
            r3.metric(
                "Remaining",
                max(0, len(reviewable_rows) - len(reviewed_edge_ids)),
            )
        except Exception as exc:
            reviewed_edge_ids = set()
            st.warning(
                "The review resources are configured, but the review table "
                "could not yet be queried."
            )
            st.exception(exc)
    else:
        reviewed_edge_ids = set()
        st.info(
            "Relationship review UI is ready, but the SQL warehouse and "
            "Unity Catalog review-table resources still need to be attached "
            "to this Databricks App."
        )

    def edge_option_label(index):
        edge = reviewable_rows[index]
        reviewed_marker = (
            "✓ " if edge["edge_id"] in reviewed_edge_ids else ""
        )
        return (
            f"{reviewed_marker}{edge['source_name']} "
            f"— {edge['relationship']} → {edge['target_name']}"
        )

    selected_index = st.selectbox(
        "Relationship",
        options=list(range(len(reviewable_rows))),
        format_func=edge_option_label,
    )

    selected = reviewable_rows[selected_index]

    left, centre, right = st.columns([1, 0.7, 1])
    with left:
        st.markdown("**Source concept**")
        st.write(selected["source_name"])
    with centre:
        st.markdown("**Relationship**")
        st.write(selected["relationship"])
    with right:
        st.markdown("**Target concept**")
        st.write(selected["target_name"])

    st.markdown("**Assistant review status**")
    st.write(selected["evidence_status"] or "—")

    if selected["evidence_anchor"]:
        st.markdown("**Evidence anchor**")
        st.write(selected["evidence_anchor"])

    st.markdown("**Supporting evidence**")
    st.info(
        selected["evidence"]
        or "No evidence text is currently available for this relationship."
    )

    st.divider()

    decision = st.radio(
        "Human decision",
        options=["VALIDATED", "REJECTED", "AMENDED"],
        horizontal=True,
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
            ],
        )

    comment = st.text_area(
        "Review comment",
        placeholder=(
            "Optional for validation; strongly recommended for rejection "
            "or amendment."
        ),
    )

    reviewer = get_reviewer_identity()
    st.caption(
        "Reviewer recorded as: "
        + (
            reviewer["email"]
            if reviewer["email"] != "unknown"
            else reviewer["username"]
        )
    )

    save_disabled = not REVIEW_ENABLED

    if st.button(
        "Save human review",
        type="primary",
        disabled=save_disabled,
    ):
        try:
            save_relationship_review(
                selected,
                decision=decision,
                amended_relationship=amended_relationship,
                comment=comment.strip(),
            )
            st.success(
                f"Review saved: {decision} — {selected['source_name']} "
                f"{selected['relationship']} {selected['target_name']}"
            )
            st.rerun()
        except Exception as exc:
            st.error("The review decision could not be saved.")
            st.exception(exc)

with tab_about:
    st.markdown(
        f"""
### Case information

**Case:** Commodore Clipper  
**Occurrence:** Fire on the main vehicle deck  
**Date:** 16 June 2010  
**Knowledge graph version:** {GRAPH_VERSION}

### Method

The graph distinguishes between source evidence, case concepts and analytical
mappings. Chronology is not treated as causality.

Concepts for which a justified EMCIP mapping was not identified remain
deliberately unresolved.

The `HAS_VESSEL` relationship is structural and does not require
investigation-report evidence.

### Review governance

Assistant review and human review are separate provenance layers. Human
validation is appended to the governed review table and does not silently
rewrite the original assistant decision.
"""
    )
