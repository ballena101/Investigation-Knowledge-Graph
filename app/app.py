import hashlib
import os
import uuid
import streamlit as st
from cryptography.fernet import Fernet
from databricks.sdk import WorkspaceClient
from neo4j import GraphDatabase
from streamlit_cytoscape import (
    streamlit_cytoscape,
    NodeStyle,
    EdgeStyle,
)

CASE_ID = "commodore_clipper_2010"
GRAPH_VERSION = "CASE_GRAPH_V0.2"

PIPELINE_VERSION = "GROUP_ANALYSIS_V0.1"
ANALYSIS_JOB_ID = os.getenv("ANALYSIS_JOB_ID")
CLASS_D_ANALYSIS_JOB_ID = os.getenv("CLASS_D_ANALYSIS_JOB_ID")
DIRECT_TEXT_ENCRYPTION_KEY = os.getenv("DIRECT_TEXT_ENCRYPTION_KEY")
IKG_ADMIN_USERS = {
    item.strip().lower()
    for item in (os.getenv("IKG_ADMIN_USERS") or "").split(",")
    if item.strip()
}

MAX_DOCUMENTS_PER_ANALYSIS = 5
LLAMA_DAILY_QUESTION_LIMIT = 5
QUOTA_TIMEZONE = "Europe/Lisbon"

PUBLIC_MODEL_SERVICE = "system.ai.gpt-5-6-sol"
INTERNAL_MODEL_SERVICE = "system.ai.gpt-oss-120b"
CLASS_D_GPT20_ENDPOINT = os.getenv("CLASS_D_GPT20_ENDPOINT")
CLASS_D_LLAMA70_ENDPOINT = os.getenv("CLASS_D_LLAMA70_ENDPOINT")

CLASS_D_MODEL_OPTIONS = {
    "GPT-OSS 20B": "GPT20",
    "Llama 3.3 70B": "LLAMA70",
    "Both models": "BOTH",
}

INFORMATION_CLASSES = {
    "A": {
        "label": "A — Public / technical",
        "description": "Code, public technical material or other non-sensitive content.",
        "model": PUBLIC_MODEL_SERVICE,
        "model_name": "OpenAI GPT-5.6 Sol via Databricks system.ai",
        "data_flow": (
            "Databricks Foundation Model API / ADI path. Suitable for "
            "public/non-sensitive material; Databricks retention and applicable "
            "provider safety terms may apply."
        ),
    },
    "B": {
        "label": "B — Published investigation material",
        "description": "Published final reports, published recommendations and other approved non-sensitive investigation material.",
        "model": PUBLIC_MODEL_SERVICE,
        "model_name": "OpenAI GPT-5.6 Sol via Databricks system.ai",
        "data_flow": (
            "Databricks Foundation Model API / ADI path. Intended for published "
            "material; Databricks retention and applicable provider safety terms may apply."
        ),
    },
    "C": {
        "label": "C — Internal / restricted analytical material",
        "description": "Internal analytical material that is not Article 9/Class D protected evidence.",
        "model": INTERNAL_MODEL_SERVICE,
        "model_name": "OpenAI GPT-OSS 120B hosted by Databricks",
        "data_flow": (
            "Databricks-hosted open-weight model. Reduces external model-provider "
            "inference exposure, while Databricks Foundation Model API controls/retention still apply."
        ),
    },
    "D": {
        "label": "D — Protected / Article 9 confidential evidence",
        "description": "Witness statements, identities, sensitive personal data, investigator notes/drafts, VTS/VDR material or equivalent protected evidence.",
        "model": None,
        "model_name": "Dedicated IKG GPT-OSS 20B and/or Llama 3.3 70B endpoints",
        "data_flow": (
            "Dedicated/custom Databricks Model Serving endpoints. The investigator "
            "may run GPT-OSS 20B, Llama 3.3 70B, or both on the same evidence. "
            "No fallback to A/B/C model routes is permitted."
        ),
    },
}

APP_BUILD = "2026-09-20-class-d-dual-model-poc-v1"

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

with st.expander(
    "Compliance, confidentiality and AI-use notice",
    expanded=False,
):
    st.markdown(
        """
**Directive alignment status:** **PoC design-aligned / conditionally aligned — not a legal certification of compliance.**

The design is intended to support the confidentiality requirements of
**Article 9 of Directive 2009/18/EC, as amended by Directive (EU) 2024/3017**.
Article 9 protects specified safety-investigation records from use or
disclosure for purposes other than the safety investigation, subject to the
competent-authority public-interest test, and operates without prejudice to
the GDPR.

**How the design respects Article 9 principles**

- source material remains in governed Databricks storage;
- access is intended to follow least privilege;
- evidence provenance is preserved from document → page → passage → analysis;
- model-generated statements are kept separate from source evidence;
- the App does not require direct raw-volume browsing in the preferred design;
- Neo4j is intended primarily for graph references/authorised derivatives,
  rather than as a raw-evidence store;
- routine logs should use identifiers/counters, not protected source text;
- confidential/protected material must not be sent to an LLM merely because
  the pipeline is technically capable of doing so.

**Information classes used by this PoC**

- **Class A — Code / public technical documentation:** suitable for GitHub.
- **Class B — Published / non-sensitive investigation material:** preferred
  validation material for the PoC.
- **Class C — Internal analytical derivatives:** passages, candidates,
  mappings, summaries and reviews; treat as internal unless approved otherwise.
- **Class D — Confidential / protected investigation material:** witness
  statements, identities, sensitive personal/health information,
  investigators' notes/opinions, draft reports, operational communications,
  VTS material and VDR/S-VDR material. Use only after the authorised processing
  path has been confirmed.

**AI processing policy and model routing**

The App selects the model path from the declared information class:

- **A / B:** OpenAI GPT-5.6 Sol through Databricks
  `system.ai.gpt-5-6-sol`.
- **C:** OpenAI GPT-OSS 120B hosted by Databricks through
  `system.ai.gpt-oss-120b`.
- **D:** dedicated IKG GPT-OSS 20B Databricks Model Serving endpoint.
  There is **no automatic fallback** to A/B/C model routes.

The exact model/endpoint is disclosed before submission, stored with the
analysis and displayed with the result.

The model developer, serving path and information-class authorisation are
treated as separate governance properties.

**Privacy-by-design output rule**

The product is designed not merely to state confidentiality requirements but
to reduce unnecessary exposure of protected information. Analytical outputs
are **de-identified by default**:

- use functional roles instead of personal names where possible;
- omit email addresses, phone numbers, home addresses, personal IDs, dates of
  birth, health details and other unnecessary identifiers;
- do not reproduce witness identities merely because they appear in source
  material;
- avoid combinations of details that could unnecessarily re-identify a person;
- preserve the protected original evidence separately so authorised users can
  trace an analytical statement without broadly reproducing the source.

A personal identity should appear in an analytical output only where it is
strictly necessary for the authorised safety-analysis purpose and the relevant
processing/disclosure is permitted.

For Databricks Model Serving, Databricks documents logical isolation,
authentication/authorisation and encryption in transit/at rest. For paid
accounts, Databricks states that Model Serving inputs/outputs are not used to
train models or improve Databricks services. Foundation Model APIs may,
however, temporarily process/store inputs and outputs for abuse/safety
purposes, and partner-model terms may add further requirements.

For **OpenAI GPT-5.6 Sol**, Databricks lists the applicable OpenAI **Usage
Policy** and **high-risk use-case mitigation requirements** in addition to the
customer's Databricks agreement.

**Operational rule:** Class D processing is blocked until the dedicated
GPT-OSS 20B endpoint and its organisational/legal/security approval are in
place. The App does not downgrade Class D to a less-private model path.

See repository documentation:
`docs/14_tooling_inventory.md` and
`docs/15_data_protection_confidentiality.md`.
        """
    )

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


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient()


def resolve_model_policy(information_class):
    policy = INFORMATION_CLASSES[information_class]

    if information_class == "D":
        return {
            **policy,
            "model": None,
            "gpt20_endpoint": CLASS_D_GPT20_ENDPOINT,
            "llama70_endpoint": CLASS_D_LLAMA70_ENDPOINT,
            "ready": bool(
                CLASS_D_GPT20_ENDPOINT
                or CLASS_D_LLAMA70_ENDPOINT
            ),
        }

    return {
        **policy,
        "ready": True,
    }


def information_class_label(class_code):
    return INFORMATION_CLASSES[class_code]["label"]


def get_current_user_key():
    reviewer = get_reviewer_identity()
    return (
        reviewer["email"]
        if reviewer["email"] != "unknown"
        else reviewer["username"]
    ).strip().lower()


def is_current_user_admin():
    return get_current_user_key() in IKG_ADMIN_USERS


def quota_date():
    return datetime.now(
        ZoneInfo(QUOTA_TIMEZONE)
    ).date().isoformat()


def get_llama_daily_usage():
    user_key = get_current_user_key()
    usage_key = f"{user_key}|LLAMA70|{quota_date()}"

    query = """
    MERGE (u:ModelDailyUsage {usage_key: $usage_key})
    ON CREATE SET
        u.user_key = $user_key,
        u.model_key = 'LLAMA70',
        u.usage_date = $usage_date,
        u.question_count = 0,
        u.created_at = datetime()
    RETURN u.question_count AS question_count
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            usage_key=usage_key,
            user_key=user_key,
            usage_date=quota_date(),
        ).single()

    return int(record["question_count"] or 0)


def consume_llama_daily_usage():
    user_key = get_current_user_key()
    usage_key = f"{user_key}|LLAMA70|{quota_date()}"

    query = """
    MERGE (u:ModelDailyUsage {usage_key: $usage_key})
    ON CREATE SET
        u.user_key = $user_key,
        u.model_key = 'LLAMA70',
        u.usage_date = $usage_date,
        u.question_count = 0,
        u.created_at = datetime()
    WITH u
    WHERE u.question_count < $limit
    SET
        u.question_count = u.question_count + 1,
        u.updated_at = datetime()
    RETURN u.question_count AS question_count
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            usage_key=usage_key,
            user_key=user_key,
            usage_date=quota_date(),
            limit=LLAMA_DAILY_QUESTION_LIMIT,
        ).single()

    return (
        int(record["question_count"])
        if record
        else None
    )


def reset_llama_daily_usage():
    if not is_current_user_admin():
        raise PermissionError(
            "Only an IKG administrator can reset the Llama daily quota."
        )

    user_key = get_current_user_key()
    usage_key = f"{user_key}|LLAMA70|{quota_date()}"

    with get_driver().session() as session:
        session.run(
            """
            MERGE (u:ModelDailyUsage {usage_key: $usage_key})
            ON CREATE SET
                u.user_key = $user_key,
                u.model_key = 'LLAMA70',
                u.usage_date = $usage_date,
                u.created_at = datetime()
            SET
                u.question_count = 0,
                u.reset_at = datetime(),
                u.reset_by = $user_key
            """,
            usage_key=usage_key,
            user_key=user_key,
            usage_date=quota_date(),
        ).consume()


def encrypt_direct_text(value):
    if not DIRECT_TEXT_ENCRYPTION_KEY:
        raise RuntimeError(
            "DIRECT_TEXT_ENCRYPTION_KEY is not configured."
        )

    return Fernet(
        DIRECT_TEXT_ENCRYPTION_KEY.encode("utf-8")
    ).encrypt(
        value.encode("utf-8")
    ).decode("utf-8")


def trigger_class_d_analysis_job(
    analysis_id,
    model_selection,
):
    if not CLASS_D_ANALYSIS_JOB_ID:
        raise RuntimeError(
            "No Class D analysis Job is attached to the App."
        )

    run_gpt20 = model_selection in {
        "GPT20",
        "BOTH",
    }
    run_llama70 = model_selection in {
        "LLAMA70",
        "BOTH",
    }

    if run_gpt20 and not CLASS_D_GPT20_ENDPOINT:
        raise RuntimeError(
            "The dedicated GPT-OSS 20B endpoint is not configured."
        )

    if run_llama70 and not CLASS_D_LLAMA70_ENDPOINT:
        raise RuntimeError(
            "The dedicated Llama 3.3 70B endpoint is not configured."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(
                CLASS_D_ANALYSIS_JOB_ID
            ),
            "job_parameters": {
                "analysis_id": analysis_id,
                "model_selection": model_selection,
                "gpt20_endpoint": (
                    CLASS_D_GPT20_ENDPOINT
                    if run_gpt20
                    else "__SKIP__"
                ),
                "llama70_endpoint": (
                    CLASS_D_LLAMA70_ENDPOINT
                    if run_llama70
                    else "__SKIP__"
                ),
            },
        },
    )

    run_id = response.get("run_id")
    if not run_id:
        raise RuntimeError(
            "Databricks did not return a Class D Job run_id."
        )

    with get_driver().session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            SET
                a.status = 'QUEUED',
                a.processing_stage = 'JOB_QUEUED',
                a.job_id = $job_id,
                a.job_run_id = $run_id,
                a.processing_updated_at = datetime(),
                a.processing_error = NULL
            """,
            analysis_id=analysis_id,
            job_id=str(
                CLASS_D_ANALYSIS_JOB_ID
            ),
            run_id=str(run_id),
        ).consume()

    return str(run_id)


def trigger_analysis_job(analysis_id, model_service):
    if not ANALYSIS_JOB_ID:
        raise RuntimeError(
            "No analysis job is attached to the App. Add the Lakeflow Job "
            "resource with key 'analysis_job' and Can manage run permission."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(ANALYSIS_JOB_ID),
            "job_parameters": {
                "analysis_id": analysis_id,
                "model_service": model_service,
            },
        },
    )

    run_id = response.get("run_id")

    if not run_id:
        raise RuntimeError(
            "Databricks accepted the job trigger but did not return a run_id."
        )

    with get_driver().session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            SET
                a.status = 'QUEUED',
                a.processing_stage = 'JOB_QUEUED',
                a.job_id = $job_id,
                a.job_run_id = $run_id,
                a.processing_updated_at = datetime(),
                a.processing_error = NULL
            """,
            analysis_id=analysis_id,
            job_id=str(ANALYSIS_JOB_ID),
            run_id=str(run_id),
        ).consume()

    return str(run_id)


def get_analysis_job_run(run_id):
    if not run_id:
        return None

    try:
        return get_workspace_client().api_client.do(
            "GET",
            f"/api/2.2/jobs/runs/get?run_id={run_id}",
        )
    except Exception:
        return None


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
    information_class,
    model_service,
    model_selection=None,
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
        input_mode: 'DOCUMENTS',
        information_class: $information_class,
        language_mode: $language_mode,
        output_language: $output_language,
        requested_model_service: $model_service,
        requested_model_selection: $model_selection,
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
        "information_class": information_class,
        "language_mode": language_mode,
        "output_language": output_language,
        "model_service": model_service,
        "model_selection": model_selection,
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


def create_analysis_from_text(
    title,
    objective,
    direct_text,
    language_mode,
    output_language,
    information_class,
    model_service,
    model_selection=None,
):
    reviewer = get_reviewer_identity()
    creator = (
        reviewer["email"]
        if reviewer["email"] != "unknown"
        else reviewer["username"]
    )

    analysis_id = f"analysis_{uuid.uuid4().hex}"
    source_id = f"text_{uuid.uuid4().hex}"
    text_sha256 = hashlib.sha256(
        direct_text.encode("utf-8")
    ).hexdigest()
    encrypted_text = encrypt_direct_text(
        direct_text
    )

    query = """
    CREATE (a:AnalysisGroup {
        analysis_id: $analysis_id,
        analysis_title: $analysis_title,
        analysis_objective: $analysis_objective,
        input_mode: 'DIRECT_TEXT',
        information_class: $information_class,
        language_mode: $language_mode,
        output_language: $output_language,
        requested_model_service: $model_service,
        requested_model_selection: $model_selection,
        status: 'PENDING_PROCESSING',
        created_by: $created_by,
        created_at: datetime(),
        pipeline_version: $pipeline_version,
        document_count: 1
    })
    CREATE (s:DirectTextSource {
        source_id: $source_id,
        analysis_id: $analysis_id,
        source_type: 'DIRECT_TEXT',
        encrypted_text: $encrypted_text,
        encryption_scheme: 'FERNET',
        text_sha256: $text_sha256,
        retention_status: 'ENCRYPTED_TRANSIENT_UNTIL_EVIDENCE_READY',
        created_at: datetime()
    })
    CREATE (a)-[:HAS_SOURCE_TEXT]->(s)
    RETURN a.analysis_id AS analysis_id
    """

    params = {
        "analysis_id": analysis_id,
        "analysis_title": title,
        "analysis_objective": objective or None,
        "information_class": information_class,
        "language_mode": language_mode,
        "output_language": output_language,
        "model_service": model_service,
        "model_selection": model_selection,
        "created_by": creator,
        "pipeline_version": PIPELINE_VERSION,
        "source_id": source_id,
        "encrypted_text": encrypted_text,
        "text_sha256": text_sha256,
    }

    with get_driver().session() as session:
        record = session.run(query, **params).single()

    if not record:
        raise RuntimeError("Neo4j did not return the created text analysis.")

    return record["analysis_id"], source_id


@st.cache_data(ttl=30)
def load_recent_analyses():
    query = """
    MATCH (a:AnalysisGroup)
    OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
    RETURN
        a.analysis_id AS analysis_id,
        a.analysis_title AS analysis_title,
        a.status AS status,
        properties(a)["input_mode"] AS input_mode,
        properties(a)["information_class"] AS information_class,
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
        properties(a)["input_mode"] AS input_mode,
        properties(a)["information_class"] AS information_class,
        a.status AS status,
        a.processing_stage AS processing_stage,
        a.documents_total AS documents_total,
        a.documents_processed AS documents_processed,
        a.pages_total AS pages_total,
        a.pages_processed AS pages_processed,
        a.passages_total AS passages_total,
        properties(a)["processing_error"] AS processing_error,
        properties(a)["job_run_id"] AS job_run_id,
        properties(a)["job_id"] AS job_id,
        properties(a)["requested_model_service"] AS requested_model_service,
        properties(a)["requested_model_selection"] AS requested_model_selection,
        properties(a)["model_service"] AS effective_model_service,
        properties(a)["detected_language"] AS detected_language,
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
def load_analysis_text_source(analysis_id):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
    OPTIONAL MATCH (a)-[:HAS_SOURCE_TEXT]->(s:DirectTextSource)
    RETURN
        s.source_id AS source_id,
        properties(s)["retention_status"] AS retention_status,
        properties(s)["extraction_status"] AS extraction_status,
        properties(s)["detected_language"] AS detected_language,
        properties(s)["passage_count"] AS passage_count,
        properties(s)["text_sha256"] AS text_sha256
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            analysis_id=analysis_id,
        ).single()

    return record.data() if record else {}


@st.cache_data(ttl=30)
def load_analysis_evidence_counts(analysis_id):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
    RETURN
        coalesce(a.documents_processed, 0) AS documents_processed,
        coalesce(a.documents_total, a.document_count, 0) AS documents_total,
        coalesce(a.pages_processed, 0) AS pages_processed,
        coalesce(a.pages_total, 0) AS pages_total,
        coalesce(a.passages_total, 0) AS passages_total,
        properties(a)["detected_language"] AS detected_language,
        properties(a)["processing_error"] AS processing_error,
        properties(a)["processing_stage"] AS processing_stage
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            analysis_id=analysis_id,
        ).single()

    return record.data() if record else {}


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


def render_pipeline_status(
    status,
    processing_stage,
    evidence_counts,
    result_meta,
):
    stages = [
        ("Analysis created", "PENDING_PROCESSING"),
        ("Workflow queued", "JOB_QUEUED"),
        ("Evidence extraction", "EXTRACTING"),
        ("Evidence ready", "EVIDENCE_READY"),
        ("Candidate extraction", "CANDIDATE_EXTRACTION"),
        ("Cross-document resolution", "RESOLVING"),
        ("Privacy validation", "PRIVACY_VALIDATION"),
        ("Knowledge graph construction", "BUILDING_GRAPH"),
        ("Completed", "COMPLETED"),
    ]

    failure_stages = {
        "EXTRACTION_FAILED": "Evidence extraction",
        "CANDIDATE_EXTRACTION_FAILED": "Candidate extraction",
        "RESOLUTION_FAILED": "Cross-document resolution",
        "PRIVACY_VALIDATION_FAILED": "Privacy validation",
        "GRAPH_BUILD_FAILED": "Knowledge graph construction",
    }

    order = {
        stage_key: index
        for index, (_, stage_key) in enumerate(stages)
    }

    effective_stage = processing_stage or status or "PENDING_PROCESSING"

    if status == "QUEUED":
        effective_stage = "JOB_QUEUED"

    failed_label = failure_stages.get(effective_stage)

    if status == "FAILED" and failed_label:
        current_index = next(
            (
                index
                for index, (label, _) in enumerate(stages)
                if label == failed_label
            ),
            0,
        )
    else:
        current_index = order.get(
            effective_stage,
            order.get(status, 0),
        )

    st.markdown("### Process status")

    for index, (label, stage_key) in enumerate(stages):
        if status == "FAILED" and index == current_index:
            marker = "❌"
            state_text = "Failed"
        elif index < current_index:
            marker = "✅"
            state_text = "Completed"
        elif index == current_index:
            if stage_key == "COMPLETED" and status == "COMPLETED":
                marker = "✅"
                state_text = "Completed"
            else:
                marker = "🔄"
                state_text = "Running"
        else:
            marker = "○"
            state_text = "Pending"

        detail = ""

        if stage_key == "EXTRACTING":
            documents_processed = int(
                evidence_counts.get("documents_processed") or 0
            )
            documents_total = int(
                evidence_counts.get("documents_total") or 0
            )
            pages_processed = int(
                evidence_counts.get("pages_processed") or 0
            )
            pages_total = int(
                evidence_counts.get("pages_total") or 0
            )
            passages_total = int(
                evidence_counts.get("passages_total") or 0
            )

            if documents_total or pages_total or passages_total:
                detail = (
                    f" — documents {documents_processed}/{documents_total}, "
                    f"pages {pages_processed}/{pages_total}, "
                    f"passages {passages_total}"
                )

        if stage_key == "CANDIDATE_EXTRACTION":
            batches_processed = int(
                result_meta.get("batches_processed") or 0
            )
            batches_total = int(
                result_meta.get("batches_total") or 0
            )

            if batches_total:
                detail = (
                    f" — batches {batches_processed}/{batches_total}"
                )

        st.write(
            f"{marker} **{label}** — {state_text}{detail}"
        )


@st.cache_data(ttl=30)
def load_analysis_result(analysis_id):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
    RETURN
        properties(a)["analysis_summary"] AS overview,
        coalesce(properties(a)["key_findings"], []) AS key_findings,
        coalesce(properties(a)["uncertainties"], []) AS uncertainties,
        coalesce(properties(a)["source_conflicts"], []) AS source_conflicts,
        properties(a)["analysis_version"] AS analysis_version,
        properties(a)["model_service"] AS model_service,
        properties(a)["privacy_output_mode"] AS privacy_output_mode,
        properties(a)["privacy_validation_status"] AS privacy_validation_status,
        coalesce(properties(a)["privacy_redaction_count"], 0) AS privacy_redaction_count,
        coalesce(properties(a)["analysis_batches_total"], 0) AS batches_total,
        coalesce(properties(a)["analysis_batches_processed"], 0) AS batches_processed
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            analysis_id=analysis_id,
        ).single()

    return record.data() if record else {}


@st.cache_data(ttl=30)
def load_model_runs(analysis_id):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
          -[:HAS_MODEL_RUN]->
          (m:ModelRun)
    RETURN
        m.model_run_id AS model_run_id,
        m.model_key AS model_key,
        m.model_label AS model_label,
        m.model_service AS model_service,
        m.status AS status,
        properties(m)["overview"] AS overview,
        coalesce(properties(m)["key_findings"], []) AS key_findings,
        coalesce(properties(m)["uncertainties"], []) AS uncertainties,
        coalesce(properties(m)["source_conflicts"], []) AS source_conflicts,
        properties(m)["privacy_output_mode"] AS privacy_output_mode,
        properties(m)["privacy_validation_status"] AS privacy_validation_status,
        coalesce(properties(m)["privacy_redaction_count"], 0) AS privacy_redaction_count,
        coalesce(properties(m)["graph_node_count"], 0) AS graph_node_count,
        coalesce(properties(m)["graph_relationship_count"], 0) AS graph_relationship_count,
        toString(properties(m)["completed_at"]) AS completed_at
    ORDER BY
        CASE m.model_key
            WHEN 'GPT20' THEN 1
            WHEN 'LLAMA70' THEN 2
            ELSE 9
        END
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
def load_model_run_graph(
    analysis_id,
    model_run_id,
):
    node_query = """
    MATCH (n:KGNode {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id
    })
    RETURN
        n.node_id AS node_id,
        n.label AS label,
        n.node_kind AS node_kind,
        properties(n)["description"] AS description,
        coalesce(properties(n)["evidence_passage_ids"], []) AS passage_ids
    ORDER BY n.label
    """

    edge_query = """
    MATCH (source:KGNode {
            analysis_id: $analysis_id,
            model_run_id: $model_run_id
          })
          -[r]->
          (target:KGNode {
            analysis_id: $analysis_id,
            model_run_id: $model_run_id
          })
    RETURN
        r.edge_id AS edge_id,
        type(r) AS relationship,
        source.node_id AS source_id,
        target.node_id AS target_id,
        properties(r)["evidence_class"] AS evidence_class,
        coalesce(properties(r)["evidence_passage_ids"], []) AS passage_ids
    ORDER BY source.label, relationship, target.label
    """

    with get_driver().session() as session:
        nodes = [
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

    return {
        "nodes": nodes,
        "edges": edges,
    }


def render_model_run(
    analysis_id,
    model_run,
    column_key,
):
    st.markdown(
        f"### {model_run['model_label']}"
    )
    st.caption(
        f"{model_run.get('model_service') or '—'} · "
        f"{model_run.get('status') or 'UNKNOWN'}"
    )

    if model_run.get("overview"):
        st.markdown("**Summary**")
        st.write(model_run["overview"])

    findings = model_run.get("key_findings") or []
    if findings:
        st.markdown("**Key findings**")
        for item in findings:
            st.write(f"• {item}")

    uncertainties = model_run.get("uncertainties") or []
    if uncertainties:
        st.markdown("**Uncertainties**")
        for item in uncertainties:
            st.write(f"• {item}")

    conflicts = model_run.get("source_conflicts") or []
    if conflicts:
        st.markdown("**Source conflicts**")
        for item in conflicts:
            st.write(f"• {item}")

    m1, m2 = st.columns(2)
    m1.metric(
        "Graph nodes",
        model_run.get("graph_node_count") or 0,
    )
    m2.metric(
        "Relationships",
        model_run.get("graph_relationship_count") or 0,
    )

    st.caption(
        "Privacy validation: "
        f"{model_run.get('privacy_validation_status') or '—'} · "
        "automatic redactions: "
        f"{model_run.get('privacy_redaction_count') or 0}"
    )

    graph = load_model_run_graph(
        analysis_id,
        model_run["model_run_id"],
    )

    elements = {
        "nodes": [
            {
                "data": {
                    "id": node["node_id"],
                    "label": node["node_kind"],
                    "name": node["label"],
                    "node_kind": node["node_kind"],
                    "description": (
                        node.get("description")
                        or ""
                    ),
                    "passage_ids": (
                        node.get("passage_ids")
                        or []
                    ),
                }
            }
            for node in graph["nodes"]
        ],
        "edges": [
            {
                "data": {
                    "id": edge["edge_id"],
                    "label": edge["relationship"],
                    "source": edge["source_id"],
                    "target": edge["target_id"],
                    "relationship": edge["relationship"],
                    "evidence_class": (
                        edge.get("evidence_class")
                        or "—"
                    ),
                    "passage_ids": (
                        edge.get("passage_ids")
                        or []
                    ),
                }
            }
            for edge in graph["edges"]
        ],
    }

    if elements["nodes"]:
        streamlit_cytoscape(
            elements=elements,
            layout="fcose",
            node_styles=analysis_node_styles,
            edge_styles=analysis_edge_styles,
            height=620,
            key=(
                "model_graph_"
                + analysis_id
                + "_"
                + column_key
            ),
        )
    else:
        st.warning(
            "No graph nodes were published for this model run."
        )


@st.cache_data(ttl=30)
def load_analysis_graph(analysis_id):
    node_query = """
    MATCH (n:KGNode {analysis_id: $analysis_id})
    RETURN
        n.node_id AS node_id,
        n.label AS label,
        n.node_kind AS node_kind,
        properties(n)["description"] AS description,
        coalesce(properties(n)["evidence_passage_ids"], []) AS passage_ids
    ORDER BY n.label
    """

    edge_query = """
    MATCH (source:KGNode {analysis_id: $analysis_id})
          -[r]->
          (target:KGNode {analysis_id: $analysis_id})
    RETURN
        r.edge_id AS edge_id,
        type(r) AS relationship,
        source.node_id AS source_id,
        source.label AS source_label,
        target.node_id AS target_id,
        target.label AS target_label,
        properties(r)["evidence_class"] AS evidence_class,
        coalesce(properties(r)["evidence_passage_ids"], []) AS passage_ids
    ORDER BY source.label, relationship, target.label
    """

    with get_driver().session() as session:
        nodes = [
            record.data()
            for record in session.run(
                node_query,
                analysis_id=analysis_id,
            )
        ]
        edges = [
            record.data()
            for record in session.run(
                edge_query,
                analysis_id=analysis_id,
            )
        ]

    return {
        "nodes": nodes,
        "edges": edges,
    }


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

analysis_node_styles = [
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
    NodeStyle(
        label="Finding",
        caption="name",
        custom_styles={
            "shape": "round-rectangle",
            "width": 125,
            "height": 80,
            "text-wrap": "wrap",
            "text-max-width": 165,
            "font-size": 11,
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="SafetyIssue",
        caption="name",
        custom_styles={
            "shape": "hexagon",
            "width": 120,
            "height": 105,
            "text-wrap": "wrap",
            "text-max-width": 160,
            "font-size": 11,
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="Recommendation",
        caption="name",
        custom_styles={
            "shape": "round-rectangle",
            "width": 130,
            "height": 85,
            "text-wrap": "wrap",
            "text-max-width": 170,
            "font-size": 11,
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="Actor",
        caption="name",
        custom_styles={
            "shape": "ellipse",
            "width": 100,
            "height": 100,
            "text-wrap": "wrap",
            "text-max-width": 140,
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
        label="System",
        caption="name",
        custom_styles={
            "shape": "rectangle",
            "width": 110,
            "height": 75,
            "text-wrap": "wrap",
            "text-max-width": 150,
            "font-size": 11,
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="Claim",
        caption="name",
        custom_styles={
            "shape": "round-rectangle",
            "width": 125,
            "height": 80,
            "text-wrap": "wrap",
            "text-max-width": 165,
            "font-size": 11,
            "border-width": 2,
        },
    ),
]

analysis_edge_styles = [
    EdgeStyle(
        label="RESULTED_IN",
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
        label="AFFECTED",
        caption="label",
        directed=True,
        curve_style="bezier",
    ),
    EdgeStyle(
        label="FOLLOWED_BY",
        caption="label",
        directed=True,
        curve_style="bezier",
    ),
    EdgeStyle(
        label="SUPPORTS",
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
    st.subheader("New analysis")
    st.caption(
        "Create one evidence-grounded knowledge graph from either indexed "
        "documents or text you provide directly. The information class controls "
        "the permitted model path."
    )

    try:
        source_documents = load_source_documents()
    except Exception as exc:
        source_documents = []
        st.error("The document catalogue could not be loaded from Neo4j.")
        st.exception(exc)

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

    input_mode = st.radio(
        "Input source",
        options=["Documents", "Direct text"],
        horizontal=True,
        help=(
            "Both routes use the same evidence-grounded graph pipeline. "
            "Direct text is encrypted before temporary storage and purged "
            "after governed passages are created."
        ),
    )

    information_class = st.selectbox(
        "Information classification",
        options=list(INFORMATION_CLASSES),
        format_func=information_class_label,
        help=(
            "This is a processing control, not only a label. It determines "
            "which model path the App is allowed to use."
        ),
    )

    policy = resolve_model_policy(information_class)

    st.markdown("**Processing disclosure**")
    st.write(policy["description"])
    st.write(f"**Model path:** {policy['model_name']}")
    if policy["model"]:
        st.code(policy["model"], language=None)
    st.caption(policy["data_flow"])

    class_d_model_selection = None

    if information_class == "D":
        class_d_model_label = st.radio(
            "Class D model comparison",
            options=list(
                CLASS_D_MODEL_OPTIONS
            ),
            horizontal=True,
            help=(
                "Run GPT-OSS 20B, Llama 3.3 70B, or both against the same "
                "evidence and question. Both produces side-by-side results."
            ),
        )
        class_d_model_selection = (
            CLASS_D_MODEL_OPTIONS[
                class_d_model_label
            ]
        )

        needs_gpt20 = (
            class_d_model_selection
            in {"GPT20", "BOTH"}
        )
        needs_llama70 = (
            class_d_model_selection
            in {"LLAMA70", "BOTH"}
        )

        if needs_gpt20:
            if CLASS_D_GPT20_ENDPOINT:
                st.caption(
                    "GPT-OSS 20B endpoint: "
                    + CLASS_D_GPT20_ENDPOINT
                )
            else:
                st.error(
                    "Dedicated GPT-OSS 20B endpoint is not configured."
                )

        if needs_llama70:
            if CLASS_D_LLAMA70_ENDPOINT:
                st.caption(
                    "Llama 3.3 70B endpoint: "
                    + CLASS_D_LLAMA70_ENDPOINT
                )
            else:
                st.error(
                    "Dedicated Llama 3.3 70B endpoint is not configured."
                )

            llama_used = get_llama_daily_usage()
            llama_remaining = max(
                LLAMA_DAILY_QUESTION_LIMIT
                - llama_used,
                0,
            )
            st.metric(
                "Llama questions remaining today",
                llama_remaining,
                help=(
                    f"Limit: {LLAMA_DAILY_QUESTION_LIMIT} per user per day "
                    f"({QUOTA_TIMEZONE}). Running both models consumes one "
                    "Llama question."
                ),
            )

            if llama_remaining == 0:
                st.warning(
                    "The daily Llama 3.3 70B question limit has been reached."
                )

            if is_current_user_admin():
                if st.button(
                    "Admin: reset my Llama quota",
                    key="reset_llama_quota",
                ):
                    reset_llama_daily_usage()
                    st.success(
                        "Today's Llama quota has been reset."
                    )
                    st.rerun()

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
                "Optional. State what you want the analysis to focus on. "
                "This guides synthesis but does not change source evidence."
            ),
        )

        selected_document_ids = []
        direct_text = ""

        if input_mode == "Documents":
            st.caption(
                f"Select 1–{MAX_DOCUMENTS_PER_ANALYSIS} indexed source documents."
            )
            selected_document_ids = st.multiselect(
                "Available documents",
                options=list(documents_by_id),
                format_func=source_document_label,
                max_selections=MAX_DOCUMENTS_PER_ANALYSIS,
            )
            if not source_documents:
                st.warning(
                    "No indexed documents are currently available."
                )
        else:
            direct_text = st.text_area(
                "Text to analyse and map",
                height=260,
                placeholder=(
                    "Write or paste the material from which you want the "
                    "knowledge graph to be constructed."
                ),
                help=(
                    "The text is encrypted before temporary storage, converted "
                    "into governed evidence passages, and the temporary encrypted "
                    "payload is purged after extraction."
                ),
            )

        language_mode = st.selectbox(
            "Source language handling",
            options=SUPPORTED_LANGUAGES,
            index=0,
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

        st.caption(
            "Outputs are de-identified by default. Personal names and other "
            "unnecessary identifiers should not be propagated into graph labels, "
            "summaries or findings."
        )

        create_submitted = st.form_submit_button(
            "Create and analyse",
            type="primary",
        )

    if create_submitted:
        errors = []

        if not analysis_title.strip():
            errors.append("Enter an analysis title.")

        if information_class == "D":
            if not analysis_objective.strip():
                errors.append(
                    "Enter the investigation question for the Class D comparison."
                )

            needs_gpt20 = class_d_model_selection in {
                "GPT20",
                "BOTH",
            }
            needs_llama70 = class_d_model_selection in {
                "LLAMA70",
                "BOTH",
            }

            if needs_gpt20 and not CLASS_D_GPT20_ENDPOINT:
                errors.append(
                    "The dedicated GPT-OSS 20B endpoint is not configured."
                )
            if needs_llama70 and not CLASS_D_LLAMA70_ENDPOINT:
                errors.append(
                    "The dedicated Llama 3.3 70B endpoint is not configured."
                )
            if (
                needs_llama70
                and get_llama_daily_usage()
                >= LLAMA_DAILY_QUESTION_LIMIT
            ):
                errors.append(
                    "The daily Llama 3.3 70B question limit has been reached."
                )
        elif not policy["ready"]:
            errors.append(
                "The model path required by this information class is not configured."
            )

        if input_mode == "Documents":
            if not selected_document_ids:
                errors.append("Select at least one source document.")
        else:
            if not direct_text.strip():
                errors.append("Enter text to analyse.")
            if not DIRECT_TEXT_ENCRYPTION_KEY:
                errors.append(
                    "Secure direct-text encryption is not configured."
                )

        if errors:
            for error in errors:
                st.error(error)
        else:
            try:
                if input_mode == "Documents":
                    analysis_id, linked_count = create_analysis_from_documents(
                        title=analysis_title.strip(),
                        objective=analysis_objective.strip(),
                        selected_document_ids=selected_document_ids,
                        language_mode=language_mode,
                        output_language=output_language,
                        information_class=information_class,
                        model_service=(
                            "CLASS_D_POLICY_ROUTED"
                            if information_class == "D"
                            else policy["model"]
                        ),
                        model_selection=class_d_model_selection,
                    )
                    source_description = f"{linked_count} document(s)"
                else:
                    analysis_id, source_id = create_analysis_from_text(
                        title=analysis_title.strip(),
                        objective=analysis_objective.strip(),
                        direct_text=direct_text.strip(),
                        language_mode=language_mode,
                        output_language=output_language,
                        information_class=information_class,
                        model_service=policy["model"],
                    )
                    source_description = "direct text"

                load_recent_analyses.clear()
                load_analysis_groups.clear()

                st.success(f"Analysis created: {analysis_id}")
                st.write(f"Input: {source_description}")
                st.write(
                    f"Information class: "
                    f"{INFORMATION_CLASSES[information_class]['label']}"
                )
                if information_class == "D":
                    st.write(
                        "Class D model selection: "
                        + class_d_model_label
                    )

                    if class_d_model_selection in {
                        "LLAMA70",
                        "BOTH",
                    }:
                        new_count = (
                            consume_llama_daily_usage()
                        )
                        if new_count is None:
                            raise RuntimeError(
                                "The Llama daily quota was reached before "
                                "the analysis could start."
                            )

                    run_id = trigger_class_d_analysis_job(
                        analysis_id,
                        class_d_model_selection,
                    )
                else:
                    st.write(
                        f"AI model path: "
                        f"{policy['model_name']}"
                    )
                    st.code(
                        policy["model"],
                        language=None,
                    )
                    if not ANALYSIS_JOB_ID:
                        raise RuntimeError(
                            "The automated Lakeflow Job resource is not attached."
                        )
                    run_id = trigger_analysis_job(
                        analysis_id,
                        policy["model"],
                    )

                load_analysis_groups.clear()
                load_recent_analyses.clear()
                st.success("Automated processing started.")
                st.write(
                    f"Databricks Job run ID: {run_id}"
                )
                st.info(
                    "Stay in the App and open Analyses to follow every "
                    "processing stage through to the completed graph."
                )

            except Exception as exc:
                st.error("The analysis could not be created or started.")
                st.exception(exc)

    st.divider()
    st.markdown("**Recent analyses**")

    try:
        recent_analyses = load_recent_analyses()
        if recent_analyses:
            for analysis in recent_analyses:
                source_label = (
                    "text"
                    if analysis.get("input_mode") == "DIRECT_TEXT"
                    else f"{analysis['document_count']} document(s)"
                )
                class_label = (
                    analysis.get("information_class")
                    or "unclassified"
                )
                st.write(
                    f"{analysis['analysis_title']} · "
                    f"{source_label} · Class {class_label} · "
                    f"{analysis['status']} · {analysis['analysis_id']}"
                )
        else:
            st.caption("No analysis groups have been created yet.")
    except Exception as exc:
        st.caption("Recent analyses could not be loaded.")
        st.exception(exc)

with tab_analyses:
    st.subheader("Analyses")
    st.caption(
        "Select an analysis group to inspect its source documents and "
        "processing status. Analytical outputs will appear here as the "
        "generic processing pipeline is connected."
    )

    if st.button(
        "Refresh status",
        key="refresh_analysis_status",
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
        st.rerun()

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
            source_label = (
                "direct text"
                if analysis.get("input_mode") == "DIRECT_TEXT"
                else f"{analysis['document_count']} document(s)"
            )
            class_label = (
                analysis.get("information_class")
                or "unclassified"
            )
            return (
                f"{analysis['analysis_title']} · "
                f"{source_label} · Class {class_label} · "
                f"{analysis['status']}"
            )

        selected_analysis_id = st.selectbox(
            "Analysis",
            options=list(analyses_by_id),
            format_func=analysis_label,
            key="analysis_results_selector",
        )

        selected_analysis = analyses_by_id[selected_analysis_id]

        if selected_analysis.get("job_run_id"):
            run_info = get_analysis_job_run(
                selected_analysis["job_run_id"]
            )

            if run_info:
                state = run_info.get("state") or {}
                life_cycle_state = (
                    state.get("life_cycle_state")
                    or state.get("life_cycle_state_message")
                    or "UNKNOWN"
                )
                result_state = (
                    state.get("result_state")
                    or ""
                )

                st.caption(
                    "Databricks workflow run: "
                    f"{selected_analysis['job_run_id']} · "
                    f"{life_cycle_state}"
                    + (
                        f" · {result_state}"
                        if result_state
                        else ""
                    )
                )

        evidence_counts = load_analysis_evidence_counts(
            selected_analysis_id
        )
        graph_counts = load_analysis_graph_counts(
            selected_analysis_id
        )
        result_meta = load_analysis_result(
            selected_analysis_id
        )

        render_pipeline_status(
            status=selected_analysis.get("status"),
            processing_stage=selected_analysis.get("processing_stage"),
            evidence_counts=evidence_counts,
            result_meta=result_meta,
        )

        st.divider()

        a1, a2, a3, a4 = st.columns(4)
        a1.metric(
            "Status",
            selected_analysis["status"] or "UNKNOWN",
        )
        a2.metric(
            "Documents",
            (
                f"{evidence_counts.get('documents_processed', 0)} / "
                f"{evidence_counts.get('documents_total', selected_analysis['document_count'])}"
            ),
        )
        a3.metric(
            "Pages",
            (
                f"{evidence_counts.get('pages_processed', 0)} / "
                f"{evidence_counts.get('pages_total', 0)}"
            ),
        )
        a4.metric(
            "Passages",
            evidence_counts.get("passages_total", 0),
        )

        g1, g2 = st.columns(2)
        g1.metric(
            "Graph nodes",
            graph_counts.get("nodes", 0),
        )
        g2.metric(
            "Relationships",
            graph_counts.get("relationships", 0),
        )

        st.markdown("**Analysis title**")
        st.write(selected_analysis["analysis_title"])

        st.markdown("**Input / information class**")
        input_mode_value = (
            selected_analysis.get("input_mode")
            or "DOCUMENTS"
        )
        class_value = (
            selected_analysis.get("information_class")
            or "B"
        )
        st.write(
            f"{'Direct text' if input_mode_value == 'DIRECT_TEXT' else 'Documents'} · "
            f"{INFORMATION_CLASSES.get(class_value, {}).get('label', class_value)}"
        )

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

        st.markdown("**AI model / policy**")
        analysis_class = (
            selected_analysis.get("information_class")
            or "B"
        )
        class_policy = resolve_model_policy(
            analysis_class
        )

        if analysis_class == "D":
            selection = (
                selected_analysis.get(
                    "requested_model_selection"
                )
                or "—"
            )
            st.write(
                f"Class D comparison selection: {selection}"
            )
            st.caption(
                class_policy["model_name"]
                + " — "
                + class_policy["data_flow"]
            )
        else:
            configured_model = (
                selected_analysis.get(
                    "effective_model_service"
                )
                or selected_analysis.get(
                    "requested_model_service"
                )
                or PUBLIC_MODEL_SERVICE
            )
            st.code(
                configured_model,
                language=None,
            )
            st.caption(
                class_policy["model_name"]
                + " — "
                + class_policy["data_flow"]
            )

        if input_mode_value == "DIRECT_TEXT":
            st.markdown("**Direct text source**")
            text_source_meta = load_analysis_text_source(
                selected_analysis_id
            )
            if text_source_meta.get("source_id"):
                st.write(
                    f"Source ID: {text_source_meta['source_id']}"
                )
                st.write(
                    "Raw source retention: "
                    f"{text_source_meta.get('retention_status') or 'pending'}"
                )
                if text_source_meta.get("passage_count") is not None:
                    st.write(
                        "Governed passages: "
                        f"{text_source_meta.get('passage_count')}"
                    )
                st.caption(
                    "Direct-text content is encrypted before temporary storage. "
                    "The encrypted payload is purged after governed Delta passages "
                    "are created."
                )
        else:
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

        status = selected_analysis["status"] or "UNKNOWN"

        if status == "QUEUED":
            st.info(
                "Automated processing is queued in Databricks."
            )

        elif status == "PENDING_PROCESSING":
            st.warning(
                "This analysis is defined, but evidence extraction has not "
                "started yet. Run notebook 15 for this analysis_id."
            )
            st.code(
                selected_analysis_id,
                language=None,
            )

        elif status == "EXTRACTING":
            st.info(
                "Evidence extraction is currently running."
            )

            doc_total = max(
                int(evidence_counts.get("documents_total") or 0),
                1,
            )
            doc_done = int(
                evidence_counts.get("documents_processed") or 0
            )

            page_total = max(
                int(evidence_counts.get("pages_total") or 0),
                1,
            )
            page_done = int(
                evidence_counts.get("pages_processed") or 0
            )

            st.progress(
                min(doc_done / doc_total, 1.0),
                text=f"Documents: {doc_done} / {doc_total}",
            )
            st.progress(
                min(page_done / page_total, 1.0),
                text=f"Pages: {page_done} / {page_total}",
            )

        elif status == "EVIDENCE_READY":
            st.success(
                "Evidence extraction is complete. Source text has been "
                "converted into deterministic passages with provenance and "
                "language metadata."
            )
            st.write(
                "Detected analysis language:",
                evidence_counts.get("detected_language") or "UNKNOWN",
            )
            st.info(
                "Next stage: run notebook 16 for this analysis_id to "
                "analyse the evidence group, resolve concepts and build "
                "the knowledge graph."
            )
            st.code(
                selected_analysis_id,
                language=None,
            )

        elif status == "ANALYSING":
            stage = (
                selected_analysis.get("processing_stage")
                or evidence_counts.get("processing_stage")
                or "ANALYSING"
            )
            st.info(
                f"Analytical processing is running: {stage}"
            )

            batches_total = int(
                result_meta.get("batches_total") or 0
            )
            batches_processed = int(
                result_meta.get("batches_processed") or 0
            )

            if batches_total > 0:
                st.progress(
                    min(
                        batches_processed / batches_total,
                        1.0,
                    ),
                    text=(
                        f"Evidence batches: "
                        f"{batches_processed} / {batches_total}"
                    ),
                )

        elif status == "COMPLETED":
            st.success(
                "Group analysis completed."
            )

            if class_value == "D":
                model_runs = load_model_runs(
                    selected_analysis_id
                )

                if not model_runs:
                    st.warning(
                        "The Class D workflow completed but no model-run "
                        "results are available."
                    )
                elif len(model_runs) == 1:
                    render_model_run(
                        selected_analysis_id,
                        model_runs[0],
                        model_runs[0]["model_key"],
                    )
                else:
                    st.markdown(
                        "## Side-by-side model comparison"
                    )
                    st.caption(
                        "Both models analysed the same evidence passages and "
                        "the same investigation question independently."
                    )
                    columns = st.columns(
                        len(model_runs)
                    )
                    for column, model_run in zip(
                        columns,
                        model_runs,
                    ):
                        with column:
                            render_model_run(
                                selected_analysis_id,
                                model_run,
                                model_run["model_key"],
                            )
            else:
                if result_meta.get("overview"):
                    st.markdown("### Analysis summary")
                    st.write(result_meta["overview"])

                key_findings = result_meta.get(
                    "key_findings"
                ) or []
                if key_findings:
                    st.markdown("### Key findings")
                    for item in key_findings:
                        st.write(f"• {item}")

                uncertainties = result_meta.get(
                    "uncertainties"
                ) or []
                if uncertainties:
                    st.markdown("### Uncertainties")
                    for item in uncertainties:
                        st.write(f"• {item}")

                source_conflicts = result_meta.get(
                    "source_conflicts"
                ) or []
                if source_conflicts:
                    st.markdown("### Source conflicts")
                    for item in source_conflicts:
                        st.write(f"• {item}")

                st.caption(
                    "Model service: "
                    f"{result_meta.get('model_service') or '—'} · "
                    "Privacy mode: "
                    f"{result_meta.get('privacy_output_mode') or 'DE_IDENTIFIED_BY_DEFAULT'} · "
                    "Analysis version: "
                    f"{result_meta.get('analysis_version') or '—'}"
                )
                st.write(
                    "Privacy validation: "
                    f"{result_meta.get('privacy_validation_status') or '—'}"
                    " · automatic redactions: "
                    f"{result_meta.get('privacy_redaction_count') or 0}"
                )

                analysis_graph = load_analysis_graph(
                    selected_analysis_id
                )

                analysis_elements = {
                    "nodes": [
                        {
                            "data": {
                                "id": node["node_id"],
                                "label": node["node_kind"],
                                "name": node["label"],
                                "node_kind": node["node_kind"],
                                "description": (
                                    node.get("description")
                                    or ""
                                ),
                                "passage_ids": node.get(
                                    "passage_ids"
                                ) or [],
                            }
                        }
                        for node in analysis_graph["nodes"]
                    ],
                    "edges": [
                        {
                            "data": {
                                "id": edge["edge_id"],
                                "label": edge["relationship"],
                                "source": edge["source_id"],
                                "target": edge["target_id"],
                                "relationship": edge["relationship"],
                                "evidence_class": (
                                    edge.get("evidence_class")
                                    or "—"
                                ),
                                "passage_ids": edge.get(
                                    "passage_ids"
                                ) or [],
                            }
                        }
                        for edge in analysis_graph["edges"]
                    ],
                }

                if analysis_elements["nodes"]:
                    st.markdown("### Knowledge graph")
                    st.caption(
                        "Machine-generated analytical graph. Relationships "
                        "remain candidates until human review."
                    )
                    streamlit_cytoscape(
                        elements=analysis_elements,
                        layout="fcose",
                        node_styles=analysis_node_styles,
                        edge_styles=analysis_edge_styles,
                        height=700,
                        key=(
                            "analysis_graph_"
                            + selected_analysis_id
                        ),
                    )
                else:
                    st.warning(
                        "The analysis completed but no graph nodes were "
                        "published."
                    )

        elif status == "FAILED":
            st.error(
                "Processing failed."
            )
            if evidence_counts.get("processing_error"):
                st.code(
                    evidence_counts["processing_error"],
                    language=None,
                )

        else:
            st.info(
                f"Processing status: {status}"
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
### Current Proof of Concept

The current IKG PoC is the **Class D dual-model investigation-analysis
workflow**.

The investigator can:

- select governed documents or provide encrypted direct text;
- state an investigation question/objective;
- choose GPT-OSS 20B, Llama 3.3 70B, or both for Class D;
- inspect independent evidence-grounded outputs;
- compare both models side by side;
- inspect privacy-validation results and generated knowledge graphs.

Llama 3.3 70B is limited to
**{LLAMA_DAILY_QUESTION_LIMIT} questions per user per day** in the PoC.

### Validation status

The model-validation framework covers:

- evidence grounding;
- relationship correctness;
- causal overreach;
- graph completeness;
- privacy leakage;
- stability;
- human review acceptance/amendment.

The **Commodore Clipper 2010** graph is retained as a controlled reference and
benchmark candidate. It validates the graph/evidence methodology; it does not
by itself validate GPT-OSS 20B or Llama 3.3 70B.

### Human-feedback learning loop

Human-validated graph relationships can feed future model assistance as:

1. evaluation ground truth;
2. retrieval context;
3. few-shot examples;
4. versioned active-learning feedback;
5. potentially future fine-tuning data, subject to governance.

The same case must not be used simultaneously as both a training/example case
and an independent validation case for the same model/version.

### Compliance and privacy

Class D processing is intended to respect the confidentiality requirements of
Article 9 of Directive 2009/18/EC through controlled model routing,
least-privilege storage, encrypted direct-text ingress, evidence provenance,
de-identified output by default and a privacy-validation gate.

This PoC is design-aligned / conditionally aligned and does not constitute a
legal certification of compliance.

### Reference demonstrator

**Reference case:** Commodore Clipper  
**Occurrence:** Fire on the main vehicle deck  
**Date:** 16 June 2010  
**Reference graph version:** {GRAPH_VERSION}

The reference graph remains available in the other App tabs for methodology,
relationship-review and EMCIP-mapping demonstrations.

### Documentation

Key project documents:

- `docs/01_current_poc_scope.md`
- `docs/15_data_protection_confidentiality.md`
- `docs/17_class_d_dual_model_poc.md`
- `docs/18_model_validation_and_feedback.md`
        """
    )
