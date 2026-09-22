import hashlib
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
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
CLASS_D_CONTENT_RETENTION_HOURS = 24
OTHER_CONTENT_RETENTION_HOURS = 72
LLAMA_DAILY_QUESTION_LIMIT = int(os.getenv("LLAMA_DAILY_QUESTION_LIMIT", "5"))
QUOTA_TIMEZONE = "Europe/Lisbon"

PUBLIC_MODEL_SERVICE = "system.ai.meta-llama-3-3-70b-instruct"
INTERNAL_MODEL_SERVICE = "system.ai.gpt-oss-120b"
CLASS_D_GPT20_ENDPOINT = os.getenv("CLASS_D_GPT20_ENDPOINT")
CLASS_D_LLAMA70_ENDPOINT = (
    os.getenv("CLASS_D_LLAMA70_ENDPOINT")
    or os.getenv("CLASS_D_OLLAMA_LLAMA70_URL")
)

NEWS_DASHBOARD_URL = os.getenv("NEWS_DASHBOARD_URL")

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
        "model_name": "Meta Llama 3.3 70B Instruct via Databricks system.ai",
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
        "model_name": "Meta Llama 3.3 70B Instruct via Databricks system.ai",
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
        "model_name": "Dedicated IKG GPT-OSS 20B and/or Llama 3.3 70B Databricks model services",
        "data_flow": (
            "Class D uses a dedicated GPT-OSS 20B Databricks Model Serving endpoint "
            "and/or the dedicated Databricks Llama 3.3 70B model service. The investigator "
            "may run either route or both on the same evidence. "
            "No fallback to A/B/C model routes is permitted."
        ),
    },
}

APP_BUILD = "2026-09-22-analysis-driven-capabilities-v3"

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
    page_title="Safety Investigation Knowledge & AI Support",
    page_icon="🔗",
    layout="wide",
)

st.title("Safety Investigation Knowledge & AI Support")
st.caption(
    "Proof of Concept for AI-assisted safety investigation analysis, "
    "evidence-grounded knowledge structuring and investigator review."
)
st.caption(f"App build: {APP_BUILD}")

st.info(
    """
**Purpose of this PoC**

This application evaluates how artificial-intelligence and structured-knowledge
tools can support safety investigators in analysing documentary evidence,
identifying evidence-grounded concepts and relationships, comparing model
outputs, preserving provenance and supporting human review.

It does **not** replace the investigator, make legal findings, determine blame,
or automatically convert AI output into an investigation conclusion.
"""
)

st.markdown("### AI models, confidentiality and Article 9 suitability")

model_disclosure_rows = [
    {
        "Information class": "A — Public / technical",
        "Model": "Meta Llama 3.3 70B Instruct",
        "Serving route": "Databricks system.ai.meta-llama-3-3-70b-instruct",
        "Confidentiality level": "Public / non-sensitive",
        "Article 9 / Class D": "Not approved for protected Class D evidence",
    },
    {
        "Information class": "B — Published investigation material",
        "Model": "Meta Llama 3.3 70B Instruct",
        "Serving route": "Databricks system.ai.meta-llama-3-3-70b-instruct",
        "Confidentiality level": "Published / non-sensitive",
        "Article 9 / Class D": "Not approved for protected Class D evidence",
    },
    {
        "Information class": "C — Internal / restricted",
        "Model": "OpenAI GPT-OSS 120B",
        "Serving route": "Databricks-hosted system.ai.gpt-oss-120b",
        "Confidentiality level": "Internal / restricted",
        "Article 9 / Class D": "Not automatically approved for Article 9 evidence",
    },
    {
        "Information class": "D — Protected / Article 9",
        "Model": "OpenAI GPT-OSS 20B",
        "Serving route": "Dedicated IKG Databricks endpoint",
        "Confidentiality level": "Protected / confidential",
        "Article 9 / Class D": "Conditionally suitable only after endpoint approval",
    },
    {
        "Information class": "D — Protected / Article 9",
        "Model": "Meta Llama 3.3 70B Instruct",
        "Serving route": "Dedicated IKG Databricks endpoint",
        "Confidentiality level": "Protected / confidential",
        "Article 9 / Class D": "Conditionally suitable only after endpoint approval",
    },
]

st.dataframe(
    model_disclosure_rows,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Article 9 status shown here is a project processing classification, not a "
    "legal certification. Class D model use remains blocked unless the dedicated "
    "endpoint, access, networking, logging, retention and organisational/legal/"
    "security approval are in place."
)


with st.expander(
    "Compliance, confidentiality and AI-use notice",
    expanded=False,
):
    st.markdown(
        """
**Directive alignment status:** **PoC design-aligned / conditionally aligned — not a legal certification of compliance.**

**Product mission:** confidentiality and data minimisation are functional
requirements of the product, not only legal notices. The system is designed to
limit exposure of protected investigation information, route data according to
its declared class, de-identify analytical outputs by default, and preserve the
original evidence separately from AI-generated derivatives.

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

A/B/C remain normal supported routes. Class D adds extra protected-data
controls and the optional dual-model comparison; it does not replace A/B/C.

The App selects the model path from the declared information class:

- **A / B:** Meta Llama 3.3 70B Instruct through Databricks
  `system.ai.meta-llama-3-3-70b-instruct`.
- **C:** OpenAI GPT-OSS 120B hosted by Databricks through
  `system.ai.gpt-oss-120b`.
- **D:** dedicated GPT-OSS 20B and Meta Llama 3.3 70B Databricks model services. The investigator chooses GPT-OSS 20B,
  Ollama Llama 3.3 70B, or both. There is **no automatic fallback** to A/B/C
  model routes.

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

For **Meta Llama 3.3 70B Instruct**, Databricks lists the applicable OpenAI **Usage
Policy** and **high-risk use-case mitigation requirements** in addition to the
customer's Databricks agreement.

**Operational rule:** a requested Class D model is blocked until its dedicated
endpoint and organisational/legal/security approval are in place. The App does
not downgrade Class D to a less-private model path.

**Content retention:** the source/evidence layer is ephemeral for every
information class. Class D source/evidence content becomes eligible for deletion
after one complete day (24 hours). A/B/C source/evidence content becomes
eligible after more than three complete days (72 hours) and is removed by the
next once-daily cleanup run. Compact de-identified graphs, human-review records
and usage metadata may remain. Raw evidence does not receive an automatic
"retain for validation" exception.

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


def content_retention_hours(information_class):
    return (
        CLASS_D_CONTENT_RETENTION_HOURS
        if information_class == "D"
        else OTHER_CONTENT_RETENTION_HOURS
    )


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


def list_llama_daily_usage():
    if not is_current_user_admin():
        return []

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(
                """
                MATCH (u:ModelDailyUsage {
                    model_key: 'LLAMA70',
                    usage_date: $usage_date
                })
                RETURN
                    u.user_key AS user_key,
                    u.question_count AS question_count
                ORDER BY u.user_key
                """,
                usage_date=quota_date(),
            )
        ]


def reset_llama_daily_usage(target_user_key):
    if not is_current_user_admin():
        raise PermissionError(
            "Only an IKG administrator can reset the Llama daily quota."
        )

    user_key = target_user_key.strip().lower()
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
                u.reset_by = $reset_by
            """,
            usage_key=usage_key,
            user_key=user_key,
            usage_date=quota_date(),
            reset_by=get_current_user_key(),
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
            "The dedicated Llama 3.3 70B Databricks model service is not configured."
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
    retention_hours = content_retention_hours(
        information_class
    )
    objective_hash = (
        hashlib.sha256(
            objective.encode("utf-8")
        ).hexdigest()
        if objective
        else None
    )

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
        retention_policy: 'DAILY_CLASS_BASED',
        content_retention_hours: $content_retention_hours,
        content_expires_at: datetime() + duration({hours: $content_retention_hours}),
        content_purge_status: 'ACTIVE',
        question_present: $question_present,
        question_hash: $question_hash,
        created_by: $created_by,
        created_at: datetime(),
        pipeline_version: $pipeline_version
    })
    WITH a
    UNWIND $document_ids AS document_id
    MATCH (d:SourceDocument {document_id: document_id})
    MERGE (a)-[:HAS_SOURCE]->(d)
    WITH a, d,
         d.first_indexed_at + duration({hours: $content_retention_hours}) AS requested_expiry
    SET
        d.source_expires_at = CASE
            WHEN d.source_expires_at IS NULL THEN requested_expiry
            WHEN requested_expiry < d.source_expires_at THEN requested_expiry
            ELSE d.source_expires_at
        END,
        d.source_retention_hours = CASE
            WHEN d.source_retention_hours IS NULL THEN $content_retention_hours
            WHEN $content_retention_hours < d.source_retention_hours THEN $content_retention_hours
            ELSE d.source_retention_hours
        END,
        d.source_purge_status = 'ACTIVE'
    WITH a, count(d) AS linked_documents, sum(coalesce(d.byte_size, 0)) AS source_bytes_total
    SET
        a.document_count = linked_documents,
        a.source_bytes_total = source_bytes_total
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
        "content_retention_hours": retention_hours,
        "question_present": bool(objective),
        "question_hash": objective_hash,
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
    retention_hours = content_retention_hours(
        information_class
    )
    objective_hash = (
        hashlib.sha256(
            objective.encode("utf-8")
        ).hexdigest()
        if objective
        else None
    )
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
        retention_policy: 'DAILY_CLASS_BASED',
        content_retention_hours: $content_retention_hours,
        content_expires_at: datetime() + duration({hours: $content_retention_hours}),
        content_purge_status: 'ACTIVE',
        question_present: $question_present,
        question_hash: $question_hash,
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
        content_expires_at: datetime() + duration({hours: $content_retention_hours}),
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
        "content_retention_hours": retention_hours,
        "question_present": bool(objective),
        "question_hash": objective_hash,
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
        properties(a)["retention_policy"] AS retention_policy,
        properties(a)["content_retention_hours"] AS content_retention_hours,
        toString(properties(a)["content_expires_at"]) AS content_expires_at,
        properties(a)["content_purge_status"] AS content_purge_status,
        coalesce(properties(a)["source_bytes_total"], 0) AS source_bytes_total,
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
        properties(a)["processing_stage"] AS processing_stage,
        properties(a)["extraction_duration_seconds"] AS extraction_duration_seconds
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
    """Render investigator-facing progress, hiding technical pipeline detail."""

    effective_stage = processing_stage or status or "PENDING_PROCESSING"
    if status == "QUEUED":
        effective_stage = "JOB_QUEUED"

    user_steps = [
        {
            "label": "Prepare evidence",
            "description": (
                "Open the selected source, preserve provenance and create the "
                "evidence passages used for analysis."
            ),
            "stages": {
                "PENDING_PROCESSING",
                "JOB_QUEUED",
                "EXTRACTING",
                "EVIDENCE_READY",
            },
        },
        {
            "label": "Analyse evidence",
            "description": (
                "Identify evidence-grounded events, concepts and supported "
                "relationships, then consolidate duplicates."
            ),
            "stages": {
                "CANDIDATE_EXTRACTION",
                "RESOLVING",
            },
        },
        {
            "label": "Check output",
            "description": (
                "Apply privacy and output-safety checks before publication."
            ),
            "stages": {
                "PRIVACY_VALIDATION",
            },
        },
        {
            "label": "Build result",
            "description": (
                "Publish the final candidate knowledge structure and graph "
                "for investigator review."
            ),
            "stages": {
                "BUILDING_GRAPH",
                "COMPLETED",
            },
        },
    ]

    technical_order = [
        "PENDING_PROCESSING",
        "JOB_QUEUED",
        "EXTRACTING",
        "EVIDENCE_READY",
        "CANDIDATE_EXTRACTION",
        "RESOLVING",
        "PRIVACY_VALIDATION",
        "BUILDING_GRAPH",
        "COMPLETED",
    ]

    failure_to_step = {
        "EXTRACTION_FAILED": 0,
        "CANDIDATE_EXTRACTION_FAILED": 1,
        "RESOLUTION_FAILED": 1,
        "PRIVACY_VALIDATION_FAILED": 2,
        "GRAPH_BUILD_FAILED": 3,
    }

    if status == "FAILED":
        current_step = failure_to_step.get(effective_stage, 0)
    else:
        current_technical_index = (
            technical_order.index(effective_stage)
            if effective_stage in technical_order
            else 0
        )
        current_step = 0
        for index, step in enumerate(user_steps):
            if any(
                technical_order.index(stage) <= current_technical_index
                for stage in step["stages"]
                if stage in technical_order
            ):
                current_step = index

    st.markdown("### Progress")

    if status == "COMPLETED":
        st.success("Result ready for review.")

    for index, step in enumerate(user_steps):
        if status == "FAILED" and index == current_step:
            marker = "❌"
            state_text = "Failed"
        elif status == "COMPLETED" or index < current_step:
            marker = "✅"
            state_text = "Completed"
        elif index == current_step:
            marker = "🔄"
            state_text = "In progress"
        else:
            marker = "○"
            state_text = "Pending"

        st.write(
            f"{marker} **{step['label']}** — {state_text}"
        )
        if index == current_step and status != "COMPLETED":
            st.caption(step["description"])

    with st.expander("Technical details", expanded=False):
        st.write(
            f"Current pipeline stage: {effective_stage}"
        )

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
        st.write(
            "Evidence: "
            f"{documents_processed}/{documents_total} documents · "
            f"{pages_processed}/{pages_total} pages · "
            f"{passages_total} passages"
        )

        batches_processed = int(
            result_meta.get("batches_processed") or 0
        )
        batches_total = int(
            result_meta.get("batches_total") or 0
        )
        if batches_total:
            st.write(
                f"Analysis batches: {batches_processed}/{batches_total}"
            )

        if evidence_counts.get("processing_error"):
            st.code(
                evidence_counts["processing_error"],
                language=None,
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
        properties(m)["duration_seconds"] AS duration_seconds,
        coalesce(properties(m)["prompt_tokens"], 0) AS prompt_tokens,
        coalesce(properties(m)["completion_tokens"], 0) AS completion_tokens,
        coalesce(properties(m)["total_tokens"], 0) AS total_tokens,
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
        coalesce(properties(r)["edge_class"], "REPORT_DERIVED") AS edge_class,
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

    e1, e2 = st.columns(2)
    duration = model_run.get(
        "duration_seconds"
    )
    e1.metric(
        "Elapsed",
        (
            f"{float(duration):.1f} s"
            if duration is not None
            else "—"
        ),
    )
    e2.metric(
        "Tokens",
        model_run.get("total_tokens") or "—",
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
    analysis_id: str,
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
    MATCH (source:KGNode {
        analysis_id: $analysis_id,
        node_id: $source_node_id
    })
    MATCH (target:KGNode {
        analysis_id: $analysis_id,
        node_id: $target_node_id
    })
    CREATE (review:RelationshipReview {
        review_id: $review_id,
        analysis_id: $analysis_id,
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
        "analysis_id": analysis_id,
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


def load_latest_relationship_reviews(analysis_id):
    query = """
    MATCH (review:RelationshipReview {analysis_id: $analysis_id})
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
            for record in session.run(
                query,
                analysis_id=analysis_id,
            )
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
            "background-color": "#2563EB",
            "border-color": "#1E3A8A",
            "color": "#FFFFFF",
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
            "background-color": "#CFFAFE",
            "border-color": "#0E7490",
            "color": "#0F172A",
            "shape": "round-rectangle",
            "width": 135,
            "height": 76,
            "text-wrap": "wrap",
            "text-max-width": 175,
            "font-size": 12,
            "font-weight": "bold",
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="Event",
        caption="name",
        custom_styles={
            "background-color": "#F59E0B",
            "border-color": "#92400E",
            "color": "#111827",
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
            "background-color": "#EF4444",
            "border-color": "#7F1D1D",
            "color": "#FFFFFF",
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
        custom_styles={"line-color": "#DC2626", "target-arrow-color": "#DC2626"},
    ),
    EdgeStyle(
        label="AFFECTED",
        caption="label",
        directed=True,
        curve_style="bezier",
        custom_styles={"line-color": "#7C3AED", "target-arrow-color": "#7C3AED"},
    ),
    EdgeStyle(
        label="CONTRIBUTED_TO",
        caption="label",
        directed=True,
        curve_style="bezier",
        custom_styles={"line-color": "#EA580C", "target-arrow-color": "#EA580C"},
    ),
    EdgeStyle(
        label="HAS_VESSEL",
        caption="label",
        directed=True,
        curve_style="bezier",
        custom_styles={"line-color": "#64748B", "target-arrow-color": "#64748B"},
    ),
]

analysis_node_styles = [
    NodeStyle(
        label="Event",
        caption="name",
        custom_styles={
            "background-color": "#F59E0B",
            "border-color": "#92400E",
            "color": "#111827",
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
            "background-color": "#EF4444",
            "border-color": "#7F1D1D",
            "color": "#FFFFFF",
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
            "background-color": "#2563EB",
            "border-color": "#1E3A8A",
            "color": "#FFFFFF",
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
            "background-color": "#7C3AED",
            "border-color": "#4C1D95",
            "color": "#FFFFFF",
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
            "background-color": "#16A34A",
            "border-color": "#14532D",
            "color": "#FFFFFF",
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
            "background-color": "#DB2777",
            "border-color": "#831843",
            "color": "#FFFFFF",
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
            "background-color": "#CFFAFE",
            "border-color": "#0E7490",
            "color": "#0F172A",
            "shape": "round-rectangle",
            "width": 135,
            "height": 76,
            "text-wrap": "wrap",
            "text-max-width": 175,
            "font-size": 12,
            "font-weight": "bold",
            "border-width": 2,
        },
    ),
    NodeStyle(
        label="System",
        caption="name",
        custom_styles={
            "background-color": "#475569",
            "border-color": "#0F172A",
            "color": "#FFFFFF",
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
            "background-color": "#A16207",
            "border-color": "#713F12",
            "color": "#FFFFFF",
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
        custom_styles={"line-color": "#DC2626", "target-arrow-color": "#DC2626"},
    ),
    EdgeStyle(
        label="CONTRIBUTED_TO",
        caption="label",
        directed=True,
        curve_style="bezier",
        custom_styles={"line-color": "#EA580C", "target-arrow-color": "#EA580C"},
    ),
    EdgeStyle(
        label="AFFECTED",
        caption="label",
        directed=True,
        curve_style="bezier",
        custom_styles={"line-color": "#7C3AED", "target-arrow-color": "#7C3AED"},
    ),
    EdgeStyle(
        label="FOLLOWED_BY",
        caption="label",
        directed=True,
        curve_style="bezier",
        custom_styles={"line-color": "#2563EB", "target-arrow-color": "#2563EB"},
    ),
    EdgeStyle(
        label="SUPPORTS",
        caption="label",
        directed=True,
        curve_style="bezier",
        custom_styles={"line-color": "#16A34A", "target-arrow-color": "#16A34A"},
    ),
    EdgeStyle(
        label="INVOLVED_IN",
        caption="label",
        directed=True,
        curve_style="bezier",
        custom_styles={"line-style": "dashed"},
    ),
]


(
    tab_home,
    tab_news,
    tab_new_analysis,
    tab_analyses,
    tab_review,
    tab_graph,
    tab_example,
    tab_about,
) = st.tabs(
    [
        "Home",
        "News & Alerts",
        "Analyse Documents",
        "Compare LLMs",
        "Review & Validate",
        "Findings & Knowledge",
        "Commodore Clipper example",
        "Terms of reference",
    ]
)

# Relationship and EMCIP reviews are deliberately presented in one capability.
# Re-entering the same Streamlit tab later appends the mapping-review section.
tab_mapping_review = tab_review

with tab_home:
    st.subheader("What would you like to do?")
    st.caption(
        "Choose one capability. The full evidence and validation pipeline "
        "remains available underneath, but you do not need to follow every "
        "step when you only want to perform one task."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("### News & Alerts")
        st.info("Preview")
        st.write(
            "Open the existing country news dashboard and, when connected, "
            "ask the LLM questions about the governed news tables."
        )
        st.caption(
            "News remains an external signal, not validated investigation "
            "knowledge."
        )

    with c2:
        st.markdown("### Analyse Documents")
        st.success("Active PoC")
        st.write(
            "Start and follow an evidence-grounded analysis of investigation "
            "documents or protected direct text."
        )
        st.caption(
            "Current focus: integrate the validated MAIRA governed-retrieval "
            "and dual-model review path into this App workflow."
        )

    with c3:
        st.markdown("### Compare LLMs")
        st.success("Active PoC")
        st.write(
            "Compare independent model answers against the same question and "
            "evidence without having to use the graph."
        )
        st.caption(
            "Currently available for completed Class D dual-model analyses."
        )

    c4, c5 = st.columns(2)

    with c4:
        st.markdown("### Review & Validate")
        st.success("Active PoC")
        st.write(
            "Review relationships and EMCIP mappings. SHIELD suggestions will "
            "also appear here after contributing factors are validated."
        )
        st.caption(
            "AI suggestions never become validated knowledge without a human "
            "decision."
        )

    with c5:
        st.markdown("### Findings & Knowledge")
        st.success("Graph available")
        st.write(
            "Search findings, ask the LLM about processed knowledge and open "
            "the relationship graph only when it helps."
        )
        st.caption(
            "LLM search and assisted relationship correction are shown as "
            "previews."
        )

    st.divider()
    st.markdown("### Current validation milestone")

    m1, m2, m3 = st.columns(3)
    m1.metric("Real MAIRA benchmark", "Persisted")
    m2.metric("Independent Delta verification", "Passed")
    m3.metric("Canonical gold matching", "Passed")

    st.caption(
        "The first real frozen-snapshot MAIRA dual-model benchmark has been "
        "executed, human-reviewed, persisted and independently reproduced from "
        "Delta. Relationship accuracy and quotation/contract compliance are "
        "kept as separate validation dimensions."
    )

    with st.expander("Technical benchmark reference", expanded=False):
        st.code(
            "maira_benchmark_9e059930506d33295105addcd06e821d",
            language=None,
        )
        st.write(
            "Canonical relationship denominator: distinct semantic "
            "relationships, not the number of supporting passage-level "
            "evidence assessments."
        )

with tab_news:
    st.subheader("News & Alerts")
    st.caption(
        "Existing Databricks AI/BI dashboard for maritime-safety news and "
        "country-level alerts."
    )

    n1, n2, n3 = st.columns(3)
    n1.metric(
        "Country dashboard",
        "Connected" if NEWS_DASHBOARD_URL else "Ready to connect",
    )
    n2.metric("News table access", "Read-only")
    n3.metric("LLM questions", "Next step")

    st.info(
        "News is treated as external, unvalidated information. It is not "
        "mixed silently with validated investigation findings."
    )

    if NEWS_DASHBOARD_URL:
        st.link_button(
            "Open News & Alerts dashboard",
            NEWS_DASHBOARD_URL,
            type="primary",
            use_container_width=True,
        )
    else:
        st.write(
            "Copy the published dashboard link from Databricks and configure "
            "it as NEWS_DASHBOARD_URL for this App."
        )

with tab_new_analysis:
    st.subheader("Analyse Documents")
    st.caption(
        "Create and run a new evidence-grounded analysis from indexed documents "
        "or direct text, then follow its processing status. Use Compare LLMs "
        "afterwards only when you want to compare model outputs."
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
                "Run GPT-OSS 20B, Ollama Llama 3.3 70B, or both against the same "
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
            if CLASS_D_OLLAMA_LLAMA70_URL:
                st.caption(
                    "Llama 3.3 70B Databricks model service: "
                    + CLASS_D_LLAMA70_ENDPOINT
                )
            else:
                st.error(
                    "Controlled Ollama Llama 3.3 70B service is not configured."
                )

            llama_used = get_llama_daily_usage()
            llama_remaining = max(
                LLAMA_DAILY_QUESTION_LIMIT
                - llama_used,
                0,
            )
            st.metric(
                "Llama 3.3 70B questions remaining today",
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
                usage_rows = list_llama_daily_usage()
                admin_users = [
                    row["user_key"]
                    for row in usage_rows
                ]

                if get_current_user_key() not in admin_users:
                    admin_users.append(
                        get_current_user_key()
                    )

                reset_target = st.selectbox(
                    "Admin quota reset user",
                    options=sorted(set(admin_users)),
                    key="llama_reset_user",
                )

                if st.button(
                    "Admin: reset selected user's Llama quota",
                    key="reset_llama_quota",
                ):
                    reset_llama_daily_usage(
                        reset_target
                    )
                    st.success(
                        "Today's Ollama quota has been reset for "
                        + reset_target
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
            if information_class == "D":
                st.warning(
                    "Class D direct text is a controlled PoC capability. "
                    "It is encrypted before temporary persistence and purged "
                    "after governed passages are created, but operational use "
                    "with Article 9 evidence still requires approval of the "
                    "transient-storage path or a secure direct-to-governed "
                    "Databricks ingress."
                )
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
            if needs_llama70 and not CLASS_D_OLLAMA_LLAMA70_URL:
                errors.append(
                    "The dedicated Llama 3.3 70B Databricks model service is not configured."
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
                        model_service=(
                            "CLASS_D_POLICY_ROUTED"
                            if information_class == "D"
                            else policy["model"]
                        ),
                        model_selection=class_d_model_selection,
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

@st.fragment
def render_compare_llms():
    st.subheader("Compare LLMs")
    st.caption(
        "Choose an existing analysis and compare independent model outputs "
        "against exactly the same question and evidence. This page does not "
        "create an analysis and does not require the graph."
    )

    st.info(
        "Direct question-and-passage comparison will be added here after its "
        "validated MAIRA benchmark route is connected to the App."
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
        st.toast("Status refreshed")

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

        extraction_seconds = evidence_counts.get(
            "extraction_duration_seconds"
        )
        if extraction_seconds is not None:
            st.caption(
                "Evidence extraction time: "
                f"{float(extraction_seconds):.1f} seconds "
                "(not including any queue delay before the task starts)."
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

        st.markdown("**Content retention**")
        retention_hours = (
            selected_analysis.get("content_retention_hours")
            or content_retention_hours(
                selected_analysis.get("information_class")
                or "B"
            )
        )
        if (
            selected_analysis.get("information_class")
            == "D"
        ):
            st.write(
                "Protected/Class D source and evidence content: "
                "deleted after one complete day (24 hours)."
            )
        else:
            st.write(
                "Source and evidence content: deleted after more than "
                "three complete days (72 hours; picked up by the next "
                "daily cleanup run)."
            )

        if selected_analysis.get("content_expires_at"):
            st.caption(
                "Eligible for cleanup from: "
                + selected_analysis["content_expires_at"]
            )

        st.caption(
            "The cleanup Job runs once per day. Compact de-identified graph, "
            "review and usage metadata may remain; raw source/evidence content "
            "does not receive a validation-retention exception."
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
                "Evidence is ready. The automated workflow continues with "
                "analytical processing, concept resolution and knowledge-graph "
                "construction. Use Refresh status to follow progress."
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



with tab_analyses:
    render_compare_llms()

with tab_graph:
    st.subheader("Findings & Knowledge")
    st.caption(
        "Search and ask about processed findings. Open the graph when the "
        "relationships are useful; it is a view of the knowledge, not a "
        "mandatory workflow step."
    )

    knowledge_question = st.text_input(
        "Search or ask about findings and relationships",
        placeholder=(
            "Example: Which events preceded the fire, and what evidence supports them?"
        ),
        disabled=True,
        key="knowledge_question_preview",
    )
    st.button(
        "Ask the knowledge assistant — coming soon",
        disabled=True,
        key="knowledge_assistant_preview",
    )
    st.caption(
        "The assistant will answer from processed sources with citations and "
        "will distinguish candidate relationships from human-validated knowledge."
    )

    st.markdown("### Existing analysis")
    try:
        knowledge_analyses = load_analysis_groups()
    except Exception as exc:
        knowledge_analyses = []
        st.error("Existing analyses could not be loaded.")
        st.exception(exc)

    if knowledge_analyses:
        knowledge_by_id = {
            item["analysis_id"]: item
            for item in knowledge_analyses
        }
        knowledge_analysis_id = st.selectbox(
            "Analysis to explore",
            options=list(knowledge_by_id),
            format_func=lambda value: (
                f"{knowledge_by_id[value]['analysis_title']} · "
                f"{knowledge_by_id[value]['status']}"
            ),
            key="knowledge_analysis_selector",
        )
        knowledge_graph = load_analysis_graph(
            knowledge_analysis_id
        )
        knowledge_elements = {
            "nodes": [
                {
                    "data": {
                        "id": node["node_id"],
                        "label": node["node_kind"],
                        "name": node["label"],
                        "description": node.get("description") or "",
                        "passage_ids": node.get("passage_ids") or [],
                    }
                }
                for node in knowledge_graph["nodes"]
            ],
            "edges": [
                {
                    "data": {
                        "id": edge["edge_id"],
                        "label": edge["relationship"],
                        "source": edge["source_id"],
                        "target": edge["target_id"],
                        "relationship": edge["relationship"],
                        "passage_ids": edge.get("passage_ids") or [],
                    }
                }
                for edge in knowledge_graph["edges"]
            ],
        }

        if knowledge_elements["nodes"]:
            with st.expander("View graph", expanded=False):
                st.caption(
                    "Colour key — event: amber · contributing factor: red · "
                    "finding: blue · safety issue: purple · recommendation: "
                    "green · actor: pink · vessel: teal · system: slate."
                )
                streamlit_cytoscape(
                    elements=knowledge_elements,
                    layout="fcose",
                    node_styles=analysis_node_styles,
                    edge_styles=analysis_edge_styles,
                    height=700,
                    key="knowledge_analysis_graph_" + knowledge_analysis_id,
                )
        else:
            st.info("This analysis does not yet contain a published graph.")
    else:
        st.info("No existing analyses are available yet.")

    st.markdown("### Similar cases")
    similar_left, similar_right = st.columns(2)
    with similar_left:
        st.markdown("**MAIRA investigation reports**")
        st.info(
            "Coming soon: retrieve similar cases from the MAIRA PDF repository "
            "and list each report with a short evidence-grounded description."
        )
    with similar_right:
        st.markdown("**News & alerts**")
        st.info(
            "Coming soon: identify potentially related news alerts and clearly "
            "report when no related alerts are found."
        )

with tab_example:
    st.subheader("Commodore Clipper — complete worked example")
    st.caption(
        "One reference sheet showing how the different capabilities work "
        "together. It is an example, not the data source for the operational pages."
    )

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Case", "Commodore Clipper")
    e2.metric("Date", "16 June 2010")
    e3.metric("Source", "Published report")
    e4.metric("Review status", "Reference case")

    st.markdown("### 1. Document analysis")
    st.write(
        "The published investigation material has been structured into "
        "evidence-grounded concepts, events, contributing factors and relationships."
    )

    st.markdown("### 2. LLM comparison")
    st.info(
        "The graph/evidence methodology is available for this reference case. "
        "A current dual-model result is not claimed unless both model runs were "
        "executed against the same frozen evidence snapshot."
    )

    st.markdown("### 3. Review & validation")
    st.write(
        f"{validated_edges} of {len(edges)} displayed relationships carry the "
        "reference assistant-validation status. Human review remains separately recorded."
    )

    st.markdown("### 4. EMCIP and SHIELD")
    taxonomy_left, taxonomy_right = st.columns(2)
    with taxonomy_left:
        st.markdown("**EMCIP mappings**")
        st.write(
            f"{len(mapping_rows_by_key)} reference mapping candidate(s) are "
            "available in the Clipper demonstrator with their mapping disposition."
        )
    with taxonomy_right:
        st.markdown("**SHIELD classification**")
        st.info(
            "No SHIELD classification is asserted in this example build. A future "
            "LLM suggestion may be made only after the contributing factor is "
            "human validated and will then require separate human validation."
        )

    st.markdown("### 5. Similar cases and external signals")
    example_case_left, example_case_right = st.columns(2)
    with example_case_left:
        st.markdown("**MAIRA repository**")
        st.info(
            "Similar-report retrieval is not connected in this build; no similar "
            "MAIRA cases are asserted here."
        )
    with example_case_right:
        st.markdown("**News & alerts**")
        st.info(
            "No related news alerts have been identified by the App because the "
            "news-table search is not connected in this build."
        )

    st.markdown("### 6. Findings and knowledge graph")
    c1, c2, c3 = st.columns(3)
    c1.metric("Nodes", len(nodes))
    c2.metric("Relationships", len(edges))
    c3.metric("Evidence-validated", validated_edges)

    st.markdown("#### Interactive knowledge graph")
    st.caption(
        "Select a node or relationship to inspect its properties, "
        "EMCIP mapping and supporting evidence."
    )
    st.caption(
        "Colour key — occurrence: blue · vessel: teal · event: amber · "
        "contributing factor: red. Relationship colours also distinguish "
        "result, contribution, effect and structural links."
    )

    streamlit_cytoscape(
        elements=elements,
        layout="fcose",
        node_styles=node_styles,
        edge_styles=edge_styles,
        height=700,
        key="commodore_clipper_graph",
    )

    with st.expander("Review a graph relationship with the LLM — preview"):
        st.write(
            "Select a relationship, ask the LLM to check it against the source "
            "evidence, and inspect the proposed change before deciding."
        )
        st.text_area(
            "What should the LLM review?",
            placeholder=(
                "Example: Check whether this should be FOLLOWED_BY rather than CAUSED_BY."
            ),
            disabled=True,
            key="graph_llm_review_preview",
        )
        st.button(
            "Review selected relationship — coming soon",
            disabled=True,
            key="graph_llm_review_button_preview",
        )
        st.caption(
            "The LLM will create a proposal with evidence. It will not directly "
            "change the validated graph; a human must approve or reject it."
        )

with tab_review:
    st.subheader("Review & Validate")
    st.caption(
        "Select an existing analysis. This operational review page does not "
        "use the Commodore Clipper example as its underlying dataset."
    )

    try:
        review_analyses = load_analysis_groups()
    except Exception as exc:
        review_analyses = []
        st.error("Existing analyses could not be loaded for review.")
        st.exception(exc)

    review_by_id = {
        item["analysis_id"]: item
        for item in review_analyses
    }
    selected_review_analysis_id = st.selectbox(
        "Analysis to review",
        options=list(review_by_id),
        format_func=lambda value: (
            f"{review_by_id[value]['analysis_title']} · "
            f"{review_by_id[value]['status']}"
        ),
        key="review_analysis_selector",
        disabled=not review_by_id,
    ) if review_by_id else None

    st.markdown("### Relationship review")
    st.caption(
        "Human review is stored as a separate append-only review record. "
        "The original graph relationship and assistant review are not overwritten."
    )

    selected_review_graph = (
        load_analysis_graph(selected_review_analysis_id)
        if selected_review_analysis_id
        else {"nodes": [], "edges": []}
    )
    reviewable_rows = [
        {
            "edge_id": edge["edge_id"],
            "source_id": edge["source_id"],
            "source_name": edge["source_label"],
            "relationship": edge["relationship"],
            "target_id": edge["target_id"],
            "target_name": edge["target_label"],
            "evidence_status": edge.get("evidence_class") or "ASSISTANT_CANDIDATE",
            "evidence_anchor": ", ".join(edge.get("passage_ids") or []),
            "evidence": (
                "Supporting passage IDs: "
                + ", ".join(edge.get("passage_ids") or [])
                if edge.get("passage_ids")
                else "No supporting passage ID was published for this relationship."
            ),
        }
        for edge in selected_review_graph["edges"]
        if edge.get("edge_class") != "STRUCTURAL"
    ]

    try:
        latest_reviews = (
            load_latest_relationship_reviews(
                selected_review_analysis_id
            )
            if selected_review_analysis_id
            else {}
        )
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
        disabled=not reviewable_rows,
    ) if reviewable_rows else None

    review_controls_disabled = selected_index is None
    selected = (
        reviewable_rows[selected_index]
        if selected_index is not None
        else {
            "edge_id": "",
            "source_id": "",
            "source_name": "—",
            "relationship": "—",
            "target_id": "",
            "target_name": "—",
            "evidence_status": "—",
            "evidence_anchor": "",
            "evidence": "No relationship selected.",
        }
    )
    latest = latest_reviews.get(selected["edge_id"])

    if not selected:
        st.info(
            "The selected analysis has no published relationships available "
            "for review yet."
        )

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


with tab_mapping_review:
    st.divider()
    st.markdown("### EMCIP mapping review")
    st.caption(
        "EMCIP mappings will be loaded for the same selected analysis above. "
        "The Commodore Clipper reference mappings are not used here."
    )

    mapping_rows = []
    latest_mapping_reviews = {}

    reviewed_mapping_keys = set(latest_mapping_reviews)

    m1, m2, m3 = st.columns(3)
    m1.metric("Reviewable mappings", len(mapping_rows))
    m2.metric("Human reviewed", len(reviewed_mapping_keys))
    m3.metric(
        "Remaining",
        max(0, len(mapping_rows) - len(reviewed_mapping_keys)),
    )

    if not mapping_rows:
        st.info(
            "No EMCIP mapping candidates are currently published for this "
            "analysis. The analysis-specific EMCIP mapping contract is pending."
        )
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

    st.divider()
    st.markdown("### SHIELD classification review")
    st.info(
        "Coming next: after a contributing factor has been human validated, "
        "the LLM may suggest a SHIELD classification here. The suggestion will "
        "require a separate human validation before acceptance."
    )

with tab_about:
    st.markdown(
        f"""
### Current Proof of Concept

The current IKG PoC is the **Class D dual-model investigation-analysis
workflow**.

The investigator can:

- select governed documents or provide encrypted direct text;
- state an investigation question/objective;
- choose GPT-OSS 20B, Ollama-hosted Llama 3.3 70B, or both for Class D;
- inspect independent evidence-grounded outputs;
- compare both models side by side;
- inspect privacy-validation results and generated knowledge graphs.

Ollama Llama 3.3 70B is limited to
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
by itself validate GPT-OSS 20B or Ollama Llama 3.3 70B.

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

- `docs/README.md` — current documentation index
- `docs/01_current_poc_scope.md`
- `docs/15_data_protection_confidentiality.md`
- `docs/17_class_d_dual_model_poc.md`
- `docs/18_model_validation_and_feedback.md`
        """
    )
