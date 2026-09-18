import hashlib
import os
import uuid
import streamlit as st
from neo4j import GraphDatabase
from streamlit_cytoscape import (
    streamlit_cytoscape,
    NodeStyle,
    EdgeStyle,
)

CASE_ID = "commodore_clipper_2010"
GRAPH_VERSION = "CASE_GRAPH_V0.2"

PIPELINE_VERSION = "GROUP_ANALYSIS_V0.1"
MAX_DOCUMENTS_PER_ANALYSIS = 5
APP_BUILD = "2026-09-18-document-library-v4"

SUPPORTED_LANGUAGES = [
    "Auto-detect per document",
    "English",
    "Spanish",
    "Portuguese",
    "French",
    "German",
    "Italian",
    "Dutch",
    "Norwegian",
    "Icelandic",
    "Danish",
    "Swedish",
    "Finnish",
    "Polish",
    "Greek",
    "Other / mixed",
]

st.set_page_config(
    page_title="Investigation Knowledge Graph",
    page_icon="🔗",
    layout="wide",
)

st.title("Investigation Knowledge Graph")
st.caption(
    "Create document-group analyses and review evidence-grounded investigation graphs."
)
st.caption(f"App build: {APP_BUILD}")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

missing_variables = [
    name
    for name, value in {
        "NEO4J_URI": NEO4J_URI,
        "NEO4J_USERNAME": NEO4J_USERNAME,
        "NEO4J_PASSWORD": NEO4J_PASSWORD,
    }.items()
    if not value
]

if missing_variables:
    st.error(
        "Missing Databricks App environment variables: "
        + ", ".join(missing_variables)
    )
    st.stop()


@st.cache_resource
def get_driver():
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    return driver


@st.cache_data(ttl=30)
def load_source_documents():
    query = """
    MATCH (d:SourceDocument)
    RETURN
        d.document_id AS document_id,
        d.filename AS filename,
        d.volume_path AS volume_path,
        d.relative_path AS relative_path,
        d.source_type AS source_type,
        d.byte_size AS byte_size,
        d.sha256 AS sha256,
        coalesce(
            properties(d)["detected_language"],
            "PENDING"
        ) AS detected_language,
        toString(d.indexed_at) AS indexed_at
    ORDER BY d.filename, d.volume_path
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(query)
        ]


def create_analysis_from_documents(
    title,
    objective,
    selected_document_ids,
    language_mode,
    output_language,
):
    reviewer = get_reviewer_identity()

    creator = (
        reviewer["email"]
        if reviewer["email"] != "unknown"
        else reviewer["username"]
    )

    analysis_id = f"analysis_{uuid.uuid4().hex}"

    query = """
    CREATE (a:AnalysisGroup {
        analysis_id: $analysis_id,
        analysis_title: $analysis_title,
        analysis_objective: $analysis_objective,
        language_mode: $language_mode,
        output_language: $output_language,
        status: 'PENDING_PROCESSING',
        created_by: $created_by,
        created_at: datetime(),
        pipeline_version: $pipeline_version
    })
    WITH a
    UNWIND $document_ids AS document_id
    MATCH (d:SourceDocument {document_id: document_id})
    MERGE (a)-[:HAS_SOURCE]->(d)
    WITH a, count(d) AS linked_documents
    SET a.document_count = linked_documents
    RETURN
        a.analysis_id AS analysis_id,
        linked_documents
    """

    params = {
        "analysis_id": analysis_id,
        "analysis_title": title,
        "analysis_objective": objective or None,
        "language_mode": language_mode,
        "output_language": output_language,
        "created_by": creator,
        "pipeline_version": PIPELINE_VERSION,
        "document_ids": selected_document_ids,
    }

    with get_driver().session() as session:
        record = session.run(query, **params).single()

    if not record:
        raise RuntimeError("Neo4j did not return the created analysis.")

    if record["linked_documents"] != len(selected_document_ids):
        raise RuntimeError(
            "The analysis was created, but not all selected documents "
            "could be linked. Refresh the document index and try again."
        )

    return record["analysis_id"], record["linked_documents"]


@st.cache_data(ttl=30)
def load_recent_analyses():
    query = """
    MATCH (a:AnalysisGroup)
    OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
    RETURN
        a.analysis_id AS analysis_id,
        a.analysis_title AS analysis_title,
        a.status AS status,
        a.output_language AS output_language,
        a.created_by AS created_by,
        toString(a.created_at) AS created_at,
        count(d) AS document_count
    ORDER BY created_at DESC
    LIMIT 20
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(query)
        ]


@st.cache_data(ttl=30)
def load_analysis_groups():
    query = """
    MATCH (a:AnalysisGroup)
    OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
    RETURN
        a.analysis_id AS analysis_id,
        a.analysis_title AS analysis_title,
        a.analysis_objective AS analysis_objective,
        a.status AS status,
        a.language_mode AS language_mode,
        a.output_language AS output_language,
        a.created_by AS created_by,
        toString(a.created_at) AS created_at,
        count(d) AS document_count
    ORDER BY created_at DESC
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(query)
        ]


@st.cache_data(ttl=30)
def load_analysis_sources(analysis_id):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
          -[:HAS_SOURCE]->
          (d:SourceDocument)
    RETURN
        d.document_id AS document_id,
        d.filename AS filename,
        d.volume_path AS volume_path,
        d.relative_path AS relative_path,
        d.source_type AS source_type,
        d.byte_size AS byte_size,
        coalesce(
            properties(d)["detected_language"],
            "PENDING"
        ) AS detected_language
    ORDER BY d.filename, d.relative_path
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
            )
        ]


@st.cache_data(ttl=30)
def load_analysis_graph_counts(analysis_id):
    query = """
    MATCH (n:KGNode {analysis_id: $analysis_id})
    WITH count(n) AS nodes
    OPTIONAL MATCH (:KGNode {analysis_id: $analysis_id})
                   -[r]->
                   (:KGNode {analysis_id: $analysis_id})
    RETURN nodes, count(r) AS relationships
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            analysis_id=analysis_id,
        ).single()

    if not record:
        return {
            "nodes": 0,
            "relationships": 0,
        }

    return record.data()


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


@st.cache_data(ttl=60)
def load_emcip_mappings():
    query = """
    MATCH (n:KGNode {case_id: $case_id})
    WHERE n.emcip_mappings IS NOT NULL
      AND size(n.emcip_mappings) > 0
    RETURN
        n.node_id AS node_id,
        n.label AS node_label,
        n.node_kind AS node_kind,
        n.proposed_emcip_entity AS proposed_emcip_entity,
        n.mapping_disposition AS mapping_disposition,
        n.emcip_mappings AS emcip_mappings
    ORDER BY node_label
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(query, case_id=CASE_ID)
        ]


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

    review_id = str(uuid.uuid4())

    query = """
    MATCH (source:KGNode {node_id: $source_node_id})
    MATCH (target:KGNode {node_id: $target_node_id})
    CREATE (review:RelationshipReview {
        review_id: $review_id,
        case_id: $case_id,
        graph_version: $graph_version,
        edge_id: $edge_id,
        source_node_id: $source_node_id,
        source_label: $source_label,
        original_relationship: $original_relationship,
        target_node_id: $target_node_id,
        target_label: $target_label,
        assistant_review_status: $assistant_review_status,
        human_review_decision: $human_review_decision,
        human_review_status: $human_review_status,
        amended_relationship: $amended_relationship,
        reviewer_email: $reviewer_email,
        reviewer_user_id: $reviewer_user_id,
        reviewer_username: $reviewer_username,
        reviewed_at: datetime(),
        review_comment: $review_comment
    })
    CREATE (review)-[:REVIEWS_SOURCE]->(source)
    CREATE (review)-[:REVIEWS_TARGET]->(target)
    RETURN review.review_id AS review_id
    """

    params = {
        "review_id": review_id,
        "case_id": CASE_ID,
        "graph_version": GRAPH_VERSION,
        "edge_id": edge["edge_id"],
        "source_node_id": edge["source_id"],
        "source_label": edge["source_name"],
        "original_relationship": edge["relationship"],
        "target_node_id": edge["target_id"],
        "target_label": edge["target_name"],
        "assistant_review_status": edge["evidence_status"],
        "human_review_decision": decision,
        "human_review_status": status_by_decision[decision],
        "amended_relationship": amended_relationship,
        "reviewer_email": reviewer["email"],
        "reviewer_user_id": reviewer["user_id"],
        "reviewer_username": reviewer["username"],
        "review_comment": comment or None,
    }

    with get_driver().session() as session:
        record = session.run(query, **params).single()

    return record["review_id"] if record else review_id


def load_latest_relationship_reviews():
    query = """
    MATCH (review:RelationshipReview {case_id: $case_id})
    WITH review
    ORDER BY review.reviewed_at DESC
    WITH review.edge_id AS edge_id, collect(review)[0] AS latest
    RETURN
        edge_id,
        latest.review_id AS review_id,
        latest.human_review_decision AS decision,
        latest.human_review_status AS status,
        properties(latest)["amended_relationship"] AS amended_relationship,
        latest.reviewer_email AS reviewer_email,
        latest.reviewer_username AS reviewer_username,
        toString(latest.reviewed_at) AS reviewed_at,
        properties(latest)["review_comment"] AS review_comment
    """

    with get_driver().session() as session:
        return {
            record["edge_id"]: record.data()
            for record in session.run(query, case_id=CASE_ID)
        }



def mapping_key(node_id: str, original_mapping: str) -> str:
    raw = f"{node_id}|{original_mapping}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def save_mapping_review(
    mapping,
    decision: str,
    amended_mapping: str | None,
    comment: str,
):
    reviewer = get_reviewer_identity()

    status_by_decision = {
        "VALIDATED": "HUMAN_VALIDATED",
        "REJECTED": "HUMAN_REJECTED",
        "AMENDED": "HUMAN_AMENDED",
    }

    review_id = str(uuid.uuid4())

    query = """
    MATCH (concept:KGNode {node_id: $node_id})
    CREATE (review:EMCIPMappingReview {
        review_id: $review_id,
        case_id: $case_id,
        graph_version: $graph_version,
        mapping_key: $mapping_key,
        node_id: $node_id,
        node_label: $node_label,
        node_kind: $node_kind,
        proposed_emcip_entity: $proposed_emcip_entity,
        assistant_mapping_status: $assistant_mapping_status,
        original_mapping: $original_mapping,
        human_review_decision: $human_review_decision,
        human_review_status: $human_review_status,
        amended_mapping: $amended_mapping,
        reviewer_email: $reviewer_email,
        reviewer_user_id: $reviewer_user_id,
        reviewer_username: $reviewer_username,
        reviewed_at: datetime(),
        review_comment: $review_comment
    })
    CREATE (review)-[:REVIEWS_MAPPING_OF]->(concept)
    RETURN review.review_id AS review_id
    """

    params = {
        "review_id": review_id,
        "case_id": CASE_ID,
        "graph_version": GRAPH_VERSION,
        "mapping_key": mapping["mapping_key"],
        "node_id": mapping["node_id"],
        "node_label": mapping["node_label"],
        "node_kind": mapping["node_kind"],
        "proposed_emcip_entity": mapping["proposed_emcip_entity"],
        "assistant_mapping_status": mapping["mapping_disposition"],
        "original_mapping": mapping["original_mapping"],
        "human_review_decision": decision,
        "human_review_status": status_by_decision[decision],
        "amended_mapping": amended_mapping,
        "reviewer_email": reviewer["email"],
        "reviewer_user_id": reviewer["user_id"],
        "reviewer_username": reviewer["username"],
        "review_comment": comment or None,
    }

    with get_driver().session() as session:
        record = session.run(query, **params).single()

    return record["review_id"] if record else review_id


def load_latest_mapping_reviews():
    query = """
    MATCH (review:EMCIPMappingReview {case_id: $case_id})
    WITH review
    ORDER BY review.reviewed_at DESC
    WITH review.mapping_key AS mapping_key, collect(review)[0] AS latest
    RETURN
        mapping_key,
        latest.review_id AS review_id,
        latest.human_review_decision AS decision,
        latest.human_review_status AS status,
        properties(latest)["amended_mapping"] AS amended_mapping,
        latest.reviewer_email AS reviewer_email,
        latest.reviewer_username AS reviewer_username,
        toString(latest.reviewed_at) AS reviewed_at,
        properties(latest)["review_comment"] AS review_comment
    """

    with get_driver().session() as session:
        return {
            record["mapping_key"]: record.data()
            for record in session.run(query, case_id=CASE_ID)
        }


try:
    rows = load_graph()
    emcip_mapping_nodes = load_emcip_mappings()
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


mapping_rows_by_key = {}

for node in emcip_mapping_nodes:
    for original_mapping in node.get("emcip_mappings") or []:
        original_mapping = original_mapping.strip()
        if not original_mapping:
            continue

        key = mapping_key(node["node_id"], original_mapping)
        mapping_rows_by_key[key] = {
            "mapping_key": key,
            "node_id": node["node_id"],
            "node_label": node["node_label"],
            "node_kind": node["node_kind"],
            "proposed_emcip_entity": node["proposed_emcip_entity"] or "—",
            "mapping_disposition": node["mapping_disposition"] or "—",
            "original_mapping": original_mapping,
        }

mapping_rows = sorted(
    mapping_rows_by_key.values(),
    key=lambda item: (
        item["node_label"],
        item["original_mapping"],
    ),
)


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

tab_new_analysis, tab_analyses, tab_graph, tab_review, tab_mapping_review, tab_about = st.tabs(
    [
        "New analysis",
        "Analyses",
        "Reference graph",
        "Relationship review",
        "EMCIP mapping review",
        "About",
    ]
)

with tab_new_analysis:
    st.subheader("New document-group analysis")
    st.caption(
        "Select any combination of documents already indexed from your "
        "Unity Catalog volume. The App stores only the analysis definition "
        "and document links in Neo4j; it does not need access to the files."
    )

    try:
        source_documents = load_source_documents()
    except Exception as exc:
        source_documents = []
        st.error("The document catalogue could not be loaded from Neo4j.")
        st.exception(exc)

    if source_documents:
        st.success(
            f"{len(source_documents)} indexed source document(s) available."
        )
    else:
        st.warning(
            "No indexed source documents are available yet. Run notebook "
            "14_index_volume_documents_to_neo4j.py after placing documents "
            "in your Unity Catalog volume."
        )

    documents_by_id = {
        document["document_id"]: document
        for document in source_documents
    }

    def source_document_label(document_id):
        document = documents_by_id[document_id]
        relative = (
            document.get("relative_path")
            or document.get("volume_path")
            or ""
        )
        source_type = document.get("source_type") or "FILE"
        language = document.get("detected_language") or "language pending"

        return (
            f"{document['filename']} · {source_type} · "
            f"{language} · {relative}"
        )

    with st.form(
        "new_analysis_form",
        clear_on_submit=False,
    ):
        analysis_title = st.text_input(
            "Analysis title",
            placeholder="e.g. Engine-room fire evidence set",
        )

        analysis_objective = st.text_area(
            "Analysis objective or question",
            placeholder=(
                "Optional. State the analytical objective. This guides "
                "later extraction and synthesis but never changes the "
                "underlying source evidence."
            ),
        )

        st.caption(
            f"Maximum documents per analysis: {MAX_DOCUMENTS_PER_ANALYSIS}"
        )

        selected_document_ids = st.multiselect(
            "Available documents",
            options=list(documents_by_id),
            format_func=source_document_label,
            max_selections=MAX_DOCUMENTS_PER_ANALYSIS,
            help=(
                "Select between 1 and 5 documents to analyse together. "
                "The same source document may be reused in more than one "
                "analysis."
            ),
        )

        language_mode = st.selectbox(
            "Document language handling",
            options=SUPPORTED_LANGUAGES,
            index=0,
            help=(
                "Use auto-detect when the selected documents may use "
                "different languages. Original-language evidence is always "
                "preserved."
            ),
        )

        output_language = st.selectbox(
            "Analysis output language",
            options=[
                "English",
                "Spanish",
                "Portuguese",
                "French",
                "German",
                "Italian",
                "Dutch",
                "Norwegian",
                "Icelandic",
                "Danish",
                "Swedish",
                "Finnish",
                "Polish",
                "Greek",
            ],
            index=0,
        )

        create_submitted = st.form_submit_button(
            "Create analysis",
            type="primary",
            disabled=not bool(source_documents),
        )

    if create_submitted:
        if not analysis_title.strip():
            st.error("Enter an analysis title.")
        elif not selected_document_ids:
            st.error("Select at least one source document.")
        elif len(selected_document_ids) > MAX_DOCUMENTS_PER_ANALYSIS:
            st.error(
                f"Select no more than {MAX_DOCUMENTS_PER_ANALYSIS} documents."
            )
        else:
            try:
                analysis_id, linked_documents = (
                    create_analysis_from_documents(
                        title=analysis_title.strip(),
                        objective=analysis_objective.strip(),
                        selected_document_ids=selected_document_ids,
                        language_mode=language_mode,
                        output_language=output_language,
                    )
                )

                load_recent_analyses.clear()

                st.success(
                    f"Analysis created: {analysis_id}"
                )
                st.write(
                    f"Linked source documents: {linked_documents}"
                )
                st.write(
                    f"Source language handling: {language_mode}"
                )
                st.write(
                    f"Analysis output language: {output_language}"
                )
                st.info(
                    "Status: PENDING_PROCESSING. The analysis definition is "
                    "saved, but no analytical outcome exists yet. Open the "
                    "Analyses tab to follow its status. After the processing "
                    "pipeline runs, that tab will expose the resulting "
                    "summary, evidence and graph."
                )

            except Exception as exc:
                st.error("The analysis could not be created.")
                st.exception(exc)

    st.divider()
    st.markdown("**Recent analyses**")

    try:
        recent_analyses = load_recent_analyses()
        if recent_analyses:
            for analysis in recent_analyses:
                st.write(
                    f"{analysis['analysis_title']} · "
                    f"{analysis['document_count']} document(s) · "
                    f"{analysis['status']} · "
                    f"{analysis['analysis_id']}"
                )
        else:
            st.caption("No analysis groups have been created yet.")
    except Exception as exc:
        st.caption(
            "Recent analyses could not be loaded."
        )
        st.exception(exc)

with tab_analyses:
    st.subheader("Analyses")
    st.caption(
        "Select an analysis group to inspect its source documents and "
        "processing status. Analytical outputs will appear here as the "
        "generic processing pipeline is connected."
    )

    try:
        analysis_groups = load_analysis_groups()
    except Exception as exc:
        analysis_groups = []
        st.error("Analyses could not be loaded from Neo4j.")
        st.exception(exc)

    if not analysis_groups:
        st.info("No analysis groups have been created yet.")
    else:
        analyses_by_id = {
            analysis["analysis_id"]: analysis
            for analysis in analysis_groups
        }

        def analysis_label(analysis_id):
            analysis = analyses_by_id[analysis_id]
            return (
                f"{analysis['analysis_title']} · "
                f"{analysis['document_count']} document(s) · "
                f"{analysis['status']}"
            )

        selected_analysis_id = st.selectbox(
            "Analysis",
            options=list(analyses_by_id),
            format_func=analysis_label,
            key="analysis_results_selector",
        )

        selected_analysis = analyses_by_id[selected_analysis_id]

        a1, a2, a3 = st.columns(3)
        a1.metric(
            "Status",
            selected_analysis["status"] or "UNKNOWN",
        )
        a2.metric(
            "Documents",
            selected_analysis["document_count"],
        )

        graph_counts = load_analysis_graph_counts(
            selected_analysis_id
        )
        a3.metric(
            "Graph nodes",
            graph_counts.get("nodes", 0),
        )

        st.markdown("**Analysis title**")
        st.write(selected_analysis["analysis_title"])

        if selected_analysis.get("analysis_objective"):
            st.markdown("**Objective / question**")
            st.write(selected_analysis["analysis_objective"])

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Source language handling**")
            st.write(
                selected_analysis.get("language_mode")
                or "—"
            )
        with c2:
            st.markdown("**Output language**")
            st.write(
                selected_analysis.get("output_language")
                or "—"
            )

        st.markdown("**Source documents**")

        sources = load_analysis_sources(
            selected_analysis_id
        )

        for source in sources:
            st.write(
                "• "
                f"{source['filename']} · "
                f"{source['source_type']} · "
                f"{source['detected_language']}"
            )
            st.caption(source["volume_path"])

        st.divider()

        if selected_analysis["status"] == "PENDING_PROCESSING":
            st.warning(
                "No analytical outcome exists yet. This analysis has been "
                "defined and its source documents have been linked, but "
                "document extraction and group-level analysis have not run."
            )
            st.markdown(
                "**Next pipeline stage:** extract → passage → "
                "cross-document resolution → relationships → graph."
            )
        else:
            st.success(
                "Processing has started or completed. Generic analytical "
                "results will be displayed here as pipeline outputs are "
                "connected."
            )

        st.caption(
            f"Analysis ID: {selected_analysis_id}"
        )


with tab_graph:
    st.subheader("Commodore Clipper reference demonstrator")
    st.caption(
        "The existing controlled case remains available while the generic "
        "document-group workflow is being implemented."
    )
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
        "Human review is stored as a separate append-only review record. "
        "The original graph relationship and assistant review are not overwritten."
    )

    reviewable_rows = [
        row for row in rows
        if row["relationship"] != "HAS_VESSEL"
    ]

    try:
        latest_reviews = load_latest_relationship_reviews()
    except Exception as exc:
        latest_reviews = {}
        st.warning(
            "The graph is readable, but existing human-review records "
            "could not be loaded."
        )
        st.exception(exc)

    reviewed_edge_ids = set(latest_reviews)

    r1, r2, r3 = st.columns(3)
    r1.metric("Reviewable relationships", len(reviewable_rows))
    r2.metric("Human reviewed", len(reviewed_edge_ids))
    r3.metric(
        "Remaining",
        max(0, len(reviewable_rows) - len(reviewed_edge_ids)),
    )

    def edge_option_label(index):
        edge = reviewable_rows[index]
        latest = latest_reviews.get(edge["edge_id"])
        if latest:
            marker = {
                "VALIDATED": "✓",
                "REJECTED": "✕",
                "AMENDED": "✎",
            }.get(latest["decision"], "•")
            prefix = f"{marker} "
        else:
            prefix = ""

        return (
            f"{prefix}{edge['source_name']} "
            f"— {edge['relationship']} → {edge['target_name']}"
        )

    selected_index = st.selectbox(
        "Relationship",
        options=list(range(len(reviewable_rows))),
        format_func=edge_option_label,
    )

    selected = reviewable_rows[selected_index]
    latest = latest_reviews.get(selected["edge_id"])

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

    st.divider()

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
    ):
        try:
            review_id = save_relationship_review(
                selected,
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


with tab_mapping_review:
    st.subheader("EMCIP mapping review")
    st.caption(
        "Review the analytical mapping between a case concept and an EMCIP "
        "taxonomy value. Human review is appended separately; the original "
        "assistant mapping is not overwritten."
    )

    try:
        latest_mapping_reviews = load_latest_mapping_reviews()
    except Exception as exc:
        latest_mapping_reviews = {}
        st.warning(
            "The graph is readable, but existing EMCIP mapping-review "
            "records could not be loaded."
        )
        st.exception(exc)

    reviewed_mapping_keys = set(latest_mapping_reviews)

    m1, m2, m3 = st.columns(3)
    m1.metric("Reviewable mappings", len(mapping_rows))
    m2.metric("Human reviewed", len(reviewed_mapping_keys))
    m3.metric(
        "Remaining",
        max(0, len(mapping_rows) - len(reviewed_mapping_keys)),
    )

    if not mapping_rows:
        st.info("No validated EMCIP mappings are available for review.")
    else:
        def mapping_option_label(index):
            mapping = mapping_rows[index]
            latest_mapping = latest_mapping_reviews.get(
                mapping["mapping_key"]
            )

            if latest_mapping:
                marker = {
                    "VALIDATED": "✓",
                    "REJECTED": "✕",
                    "AMENDED": "✎",
                }.get(latest_mapping["decision"], "•")
                prefix = f"{marker} "
            else:
                prefix = ""

            return (
                f"{prefix}{mapping['node_label']} "
                f"→ {mapping['original_mapping']}"
            )

        selected_mapping_index = st.selectbox(
            "Mapping",
            options=list(range(len(mapping_rows))),
            format_func=mapping_option_label,
            key="mapping_selector",
        )

        selected_mapping = mapping_rows[selected_mapping_index]
        latest_mapping = latest_mapping_reviews.get(
            selected_mapping["mapping_key"]
        )

        st.markdown("**Case concept**")
        st.write(selected_mapping["node_label"])

        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown("**Concept type**")
            st.write(selected_mapping["node_kind"])
        with mc2:
            st.markdown("**EMCIP entity**")
            st.write(selected_mapping["proposed_emcip_entity"])

        st.markdown("**Assistant mapping**")
        st.info(selected_mapping["original_mapping"])

        st.markdown("**Assistant mapping disposition**")
        st.write(selected_mapping["mapping_disposition"])

        if latest_mapping:
            st.markdown("**Latest human review**")
            st.write(
                f"{latest_mapping['decision']} · "
                f"{latest_mapping['reviewed_at']} · "
                f"{latest_mapping['reviewer_email'] or latest_mapping['reviewer_username'] or 'unknown'}"
            )

            if latest_mapping["amended_mapping"]:
                st.write(
                    "Proposed amended mapping:",
                    latest_mapping["amended_mapping"],
                )

            if latest_mapping["review_comment"]:
                st.write(
                    "Comment:",
                    latest_mapping["review_comment"],
                )

        st.divider()

        if "mapping_review_flash" in st.session_state:
            flash = st.session_state.pop("mapping_review_flash")
            st.success(flash)

        with st.form("emcip_mapping_review_form"):
            mapping_decision = st.radio(
                "Human mapping decision",
                options=["VALIDATED", "REJECTED", "AMENDED"],
                horizontal=True,
                key="mapping_decision",
            )

            amended_mapping = None
            if mapping_decision == "AMENDED":
                amended_mapping = st.text_input(
                    "Proposed amended EMCIP mapping",
                    placeholder=(
                        "Enter the replacement taxonomy path/value. "
                        "It will be stored as a proposal and will not overwrite "
                        "the original mapping."
                    ),
                    key="mapping_amended_value",
                ).strip()

                if not amended_mapping:
                    st.info(
                        "An amended mapping value is required before an "
                        "AMENDED review can be saved."
                    )

            mapping_comment = st.text_area(
                "Mapping review comment",
                placeholder=(
                    "Optional for validation; strongly recommended for rejection "
                    "or amendment."
                ),
                key="mapping_review_comment",
            )

            mapping_reviewer = get_reviewer_identity()
            mapping_reviewer_display = (
                mapping_reviewer["email"]
                if mapping_reviewer["email"] != "unknown"
                else mapping_reviewer["username"]
            )
            st.caption(
                f"Reviewer recorded as: {mapping_reviewer_display}"
            )

            mapping_save_disabled = (
                mapping_decision == "AMENDED"
                and not amended_mapping
            )

            mapping_submitted = st.form_submit_button(
                "Save mapping review",
                type="primary",
                disabled=mapping_save_disabled,
            )

        if mapping_submitted:
            try:
                mapping_review_id = save_mapping_review(
                    selected_mapping,
                    decision=mapping_decision,
                    amended_mapping=amended_mapping,
                    comment=mapping_comment.strip(),
                )

                with get_driver().session() as session:
                    persisted = session.run(
                        """
                        MATCH (r:EMCIPMappingReview {review_id: $review_id})
                        RETURN
                            r.human_review_decision AS decision,
                            r.human_review_status AS status
                        """,
                        review_id=mapping_review_id,
                    ).single()

                if persisted is None:
                    raise RuntimeError(
                        "The write returned a review ID but the review record "
                        "could not be read back from Neo4j."
                    )

                st.session_state["mapping_review_flash"] = (
                    f"Mapping review saved: {persisted['decision']} — "
                    f"review ID {mapping_review_id}"
                )
                st.rerun()

            except Exception as exc:
                st.error(
                    "The EMCIP mapping review could not be saved to Neo4j."
                )
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

Assistant review and human review are separate provenance layers.

For this PoC, human review is stored as append-only
`RelationshipReview` and `EMCIPMappingReview` nodes in Neo4j. The
reviewed graph edges and original EMCIP mappings are not silently modified.

If the project later requires a governed institutional audit store, these
review records can be exported to Delta / Unity Catalog from a controlled
Databricks notebook or workflow.
"""
    )
