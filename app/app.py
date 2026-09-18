import hashlib
import os
import re
import time
import uuid
from urllib.parse import quote

import requests
import streamlit as st
from neo4j import GraphDatabase
from streamlit_cytoscape import (
    streamlit_cytoscape,
    NodeStyle,
    EdgeStyle,
)

CASE_ID = "commodore_clipper_2010"
GRAPH_VERSION = "CASE_GRAPH_V0.2"

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")

if DATABRICKS_HOST and not DATABRICKS_HOST.startswith(("http://", "https://")):
    DATABRICKS_HOST = "https://" + DATABRICKS_HOST
WAREHOUSE_ID = "372b5b52ba082619"
SOURCE_VOLUME_PATH = (
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources"
)
ANALYSIS_GROUP_TABLE = "bdw_analysis_prod.kg_poc.analysis_group"
ANALYSIS_DOCUMENT_TABLE = "bdw_analysis_prod.kg_poc.analysis_document"
PIPELINE_VERSION = "GROUP_ANALYSIS_V0.1"
APP_BUILD = "2026-09-18-group-upload-v4"

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


def get_user_access_token():
    try:
        return (
            st.context.headers.get("x-forwarded-access-token")
            or st.context.headers.get("X-Forwarded-Access-Token")
        )
    except Exception:
        return None


def _user_headers(content_type=None):
    token = get_user_access_token()
    if not token:
        raise RuntimeError(
            "User authorization token is unavailable. Configure the App "
            "with the 'files' and 'sql' user authorization scopes, then "
            "re-open the App and grant consent."
        )

    headers = {"Authorization": f"Bearer {token}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _api_url(path):
    if not DATABRICKS_HOST:
        raise RuntimeError("DATABRICKS_HOST is unavailable in the App runtime.")

    host = DATABRICKS_HOST.strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "https://" + host

    return f"{host}{path}"


def execute_user_sql(statement, parameters=None):
    payload = {
        "warehouse_id": WAREHOUSE_ID,
        "statement": statement,
        "parameters": parameters or [],
        "wait_timeout": "10s",
        "on_wait_timeout": "CONTINUE",
    }

    response = requests.post(
        _api_url("/api/2.0/sql/statements"),
        headers=_user_headers("application/json"),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    statement_id = data.get("statement_id")

    for _ in range(60):
        state = (data.get("status") or {}).get("state")

        if state == "SUCCEEDED":
            return data

        if state in {"FAILED", "CANCELED", "CLOSED"}:
            error = (data.get("status") or {}).get("error")
            raise RuntimeError(
                f"SQL statement ended with state {state}: {error}"
            )

        if not statement_id:
            raise RuntimeError(
                "Databricks SQL did not return a statement ID."
            )

        time.sleep(0.5)

        poll = requests.get(
            _api_url(f"/api/2.0/sql/statements/{statement_id}"),
            headers=_user_headers(),
            timeout=30,
        )
        poll.raise_for_status()
        data = poll.json()

    raise TimeoutError("Databricks SQL statement did not finish in time.")


def sql_parameter(name, value, data_type=None):
    item = {"name": name, "value": value}
    if data_type:
        item["type"] = data_type
    return item


def safe_source_filename(filename):
    base = os.path.basename(filename or "document")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return cleaned or "document"


def _raise_databricks_http_error(response, action):
    if response.ok:
        return

    body = (response.text or "").strip()
    if len(body) > 3000:
        body = body[:3000] + "..."

    scope_hint = ""
    if response.status_code == 403:
        scope_hint = (
            " A 403 can mean that the forwarded user token has not been "
            "granted/refreshed with the required OAuth scope, or that the "
            "user lacks a required Unity Catalog privilege."
        )

    raise RuntimeError(
        f"{action} failed with HTTP {response.status_code} "
        f"{response.reason}.{scope_hint}\n"
        f"Databricks response: {body or '<empty response body>'}"
    )


def check_volume_access():
    path = SOURCE_VOLUME_PATH.rstrip("/") + "/"
    encoded = quote(path, safe="/")
    response = requests.head(
        _api_url(f"/api/2.0/fs/directories{encoded}"),
        headers=_user_headers(),
        timeout=30,
    )
    _raise_databricks_http_error(
        response,
        "Volume access check",
    )
    return True


def create_volume_directory(path):
    encoded = quote(path, safe="/")
    response = requests.put(
        _api_url(f"/api/2.0/fs/directories{encoded}/"),
        headers=_user_headers(),
        timeout=30,
    )
    _raise_databricks_http_error(
        response,
        f"Create volume directory {path}",
    )


def upload_volume_file(path, file_bytes):
    encoded = quote(path, safe="/")
    response = requests.put(
        _api_url(f"/api/2.0/fs/files{encoded}?overwrite=false"),
        headers=_user_headers("application/octet-stream"),
        data=file_bytes,
        timeout=120,
    )
    _raise_databricks_http_error(
        response,
        f"Upload file {path}",
    )


def register_analysis_group(
    analysis_id,
    title,
    objective,
    creator,
    document_count,
    language_mode,
    output_language,
):
    statement = f"""
    INSERT INTO {ANALYSIS_GROUP_TABLE} (
        analysis_id,
        analysis_title,
        analysis_objective,
        created_by,
        created_at,
        status,
        document_count,
        pipeline_version,
        graph_version,
        error_message,
        language_mode,
        output_language
    )
    VALUES (
        :analysis_id,
        :analysis_title,
        :analysis_objective,
        :created_by,
        current_timestamp(),
        'UPLOADED',
        :document_count,
        :pipeline_version,
        NULL,
        NULL,
        :language_mode,
        :output_language
    )
    """

    execute_user_sql(
        statement,
        [
            sql_parameter("analysis_id", analysis_id),
            sql_parameter("analysis_title", title),
            sql_parameter("analysis_objective", objective or None),
            sql_parameter("created_by", creator),
            sql_parameter(
                "document_count",
                str(document_count),
                "INT",
            ),
            sql_parameter("pipeline_version", PIPELINE_VERSION),
            sql_parameter("language_mode", language_mode),
            sql_parameter("output_language", output_language),
        ],
    )


def register_analysis_document(
    analysis_id,
    document,
    uploader,
):
    statement = f"""
    INSERT INTO {ANALYSIS_DOCUMENT_TABLE} (
        analysis_id,
        document_id,
        original_filename,
        mime_type,
        byte_size,
        sha256,
        storage_uri,
        source_type,
        page_count,
        uploaded_by,
        uploaded_at,
        extraction_status,
        extraction_version,
        error_message
    )
    VALUES (
        :analysis_id,
        :document_id,
        :original_filename,
        :mime_type,
        :byte_size,
        :sha256,
        :storage_uri,
        :source_type,
        NULL,
        :uploaded_by,
        current_timestamp(),
        'PENDING',
        NULL,
        NULL
    )
    """

    execute_user_sql(
        statement,
        [
            sql_parameter("analysis_id", analysis_id),
            sql_parameter("document_id", document["document_id"]),
            sql_parameter(
                "original_filename",
                document["original_filename"],
            ),
            sql_parameter("mime_type", document["mime_type"]),
            sql_parameter(
                "byte_size",
                str(document["byte_size"]),
                "BIGINT",
            ),
            sql_parameter("sha256", document["sha256"]),
            sql_parameter("storage_uri", document["storage_uri"]),
            sql_parameter("source_type", document["source_type"]),
            sql_parameter("uploaded_by", uploader),
        ],
    )


def create_analysis(
    title,
    objective,
    uploaded_files,
    language_mode,
    output_language,
):
    identity = get_reviewer_identity()
    uploader = (
        identity["email"]
        if identity["email"] != "unknown"
        else identity["username"]
    )

    check_volume_access()

    analysis_id = f"analysis_{uuid.uuid4().hex}"
    analysis_directory = f"{SOURCE_VOLUME_PATH}/{analysis_id}"

    create_volume_directory(analysis_directory)

    documents = []

    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        document_id = f"doc_{sha256[:24]}"
        filename = safe_source_filename(uploaded_file.name)
        storage_uri = (
            f"{analysis_directory}/{document_id}_{filename}"
        )

        upload_volume_file(storage_uri, file_bytes)

        extension = os.path.splitext(filename)[1].lower().lstrip(".")
        source_type = extension.upper() if extension else "UNKNOWN"

        documents.append(
            {
                "document_id": document_id,
                "original_filename": uploaded_file.name,
                "mime_type": uploaded_file.type or None,
                "byte_size": len(file_bytes),
                "sha256": sha256,
                "storage_uri": storage_uri,
                "source_type": source_type,
            }
        )

    register_analysis_group(
        analysis_id=analysis_id,
        title=title,
        objective=objective,
        creator=uploader,
        document_count=len(documents),
        language_mode=language_mode,
        output_language=output_language,
    )

    for document in documents:
        register_analysis_document(
            analysis_id=analysis_id,
            document=document,
            uploader=uploader,
        )

    return analysis_id, documents


@st.cache_resource
def get_driver():
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    return driver


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

tab_new_analysis, tab_graph, tab_review, tab_mapping_review, tab_about = st.tabs(
    [
        "New analysis",
        "Reference graph",
        "Relationship review",
        "EMCIP mapping review",
        "About",
    ]
)

with tab_new_analysis:
    st.subheader("New document-group analysis")
    st.caption(
        "Create one analysis from a group of source documents. "
        "Each source remains individually traceable inside the group."
    )

    if not get_user_access_token():
        st.warning(
            "User authorization is not active yet. The App needs the "
            "'files' and 'sql' scopes before it can store uploads and "
            "register analysis metadata."
        )
    else:
        st.success(
            "User authorization is active for this App session."
        )

    with st.form(
        "new_analysis_form",
        clear_on_submit=False,
    ):
        analysis_title = st.text_input(
            "Analysis title",
            placeholder="e.g. Fire investigation evidence set",
        )

        analysis_objective = st.text_area(
            "Analysis objective or question",
            placeholder=(
                "Optional. Describe what you want the group analysed for. "
                "This will later guide the analytical extraction, but it "
                "does not alter source evidence."
            ),
        )

        language_mode = st.selectbox(
            "Document language handling",
            options=SUPPORTED_LANGUAGES,
            index=0,
            help=(
                "Choose Auto-detect when the group may contain documents "
                "in different languages. Original-language evidence will be "
                "preserved; language detection and optional translation are "
                "handled later in the extraction pipeline."
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
            help=(
                "This controls the language used for future summaries and "
                "analytical explanations. Source evidence remains in its "
                "original language."
            ),
        )

        uploaded_files = st.file_uploader(
            "Source documents",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            help=(
                "Upload all documents that belong to one analysis group. "
                "PDF, DOCX and TXT are accepted for registration; "
                "extraction support will be added in the next step."
            ),
        )

        create_submitted = st.form_submit_button(
            "Create analysis",
            type="primary",
            disabled=not bool(get_user_access_token()),
        )

    if create_submitted:
        if not analysis_title.strip():
            st.error("Enter an analysis title.")
        elif not uploaded_files:
            st.error("Upload at least one source document.")
        else:
            try:
                with st.spinner(
                    "Creating analysis and storing source documents..."
                ):
                    analysis_id, registered_documents = create_analysis(
                        title=analysis_title.strip(),
                        objective=analysis_objective.strip(),
                        uploaded_files=uploaded_files,
                        language_mode=language_mode,
                        output_language=output_language,
                    )

                st.success(
                    f"Analysis created: {analysis_id}"
                )

                st.session_state["last_created_analysis_id"] = (
                    analysis_id
                )

                st.write(
                    f"Registered {len(registered_documents)} source "
                    "document(s)."
                )
                st.write(f"Source language handling: {language_mode}")
                st.write(f"Analysis output language: {output_language}")

                for document in registered_documents:
                    st.write(
                        "• "
                        f"{document['original_filename']} "
                        f"→ {document['document_id']}"
                    )

                st.info(
                    "The files are stored and registered. "
                    "Extraction and group-level analysis are the next "
                    "pipeline step."
                )

            except Exception as exc:
                st.error("The analysis could not be created.")
                st.exception(exc)


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
