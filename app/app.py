import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import fitz
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
ASK_JOB_ID = os.getenv("ASK_JOB_ID")
EMCIP_MAPPING_JOB_ID = os.getenv("EMCIP_MAPPING_JOB_ID")
SHIELD_PROPOSAL_JOB_ID = os.getenv("SHIELD_PROPOSAL_JOB_ID")
RELATIONSHIP_CORRECTION_JOB_ID = os.getenv(
    "RELATIONSHIP_CORRECTION_JOB_ID"
)
SIMILAR_CASES_JOB_ID = os.getenv(
    "SIMILAR_CASES_JOB_ID"
)
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

IKF_SOURCE_VOLUME_ROOT = (
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources"
)
MAIRA_SOURCE_VOLUME_ROOT = (
    "/Volumes/bdw_analysis_prod/maira/source_documents"
)
IKF_REFERENCE_VOLUME_ROOT = (
    "/Volumes/bdw_analysis_prod/kg_poc/reference_context"
)
ALLOWED_SOURCE_VOLUME_ROOTS = (
    IKF_SOURCE_VOLUME_ROOT,
    MAIRA_SOURCE_VOLUME_ROOT,
    IKF_REFERENCE_VOLUME_ROOT,
)

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


APP_PRESCREEN_VERSION = "IKF_APP_PRESCREEN_V0.1"

_APP_PROTECTED_TEXT_RULES = (
    (
        "PERSONAL_ID_RECORD",
        re.compile(
            r"\b(?:passport|national\s+id|identity\s+card|id\s+number)"
            r"\s*[:#-]?\s*[A-Z0-9-]{4,}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "WITNESS_RECORD",
        re.compile(
            r"\b(?:witness\s+(?:statement|interview|testimony)|"
            r"statement\s+of\s+witness)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "VDR_RAW_RECORD",
        re.compile(
            r"\b(?:(?:vdr|voyage\s+data\s+recorder)\s+"
            r"(?:audio|recording|transcript|conversation)|"
            r"(?:audio|recording|transcript)\s+from\s+(?:the\s+)?vdr)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "VTS_RAW_RECORD",
        re.compile(
            r"\b(?:vts|vessel\s+traffic\s+service)\s+"
            r"(?:audio|recording|transcript|conversation)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "INVESTIGATOR_WORKING_RECORD",
        re.compile(
            r"\b(?:investigator(?:'s)?\s+(?:notes?|draft)|"
            r"investigation\s+working\s+notes?|"
            r"draft\s+(?:investigation\s+)?report)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "MEDICAL_RECORD",
        re.compile(
            r"\b(?:medical\s+(?:record|report|history)|"
            r"health\s+record|patient\s+record)\b",
            re.IGNORECASE,
        ),
    ),
)

_APP_PROTECTED_METADATA_RULES = (
    (
        "WITNESS_RECORD_METADATA",
        re.compile(
            r"(?:witness[_\s-]*(?:statement|interview)|"
            r"statement[_\s-]*of[_\s-]*witness)",
            re.IGNORECASE,
        ),
    ),
    (
        "VDR_RAW_RECORD_METADATA",
        re.compile(
            r"(?:vdr|voyage[_\s-]*data[_\s-]*recorder)"
            r".*(?:audio|recording|transcript)",
            re.IGNORECASE,
        ),
    ),
    (
        "VTS_RAW_RECORD_METADATA",
        re.compile(
            r"(?:vts|vessel[_\s-]*traffic[_\s-]*service)"
            r".*(?:audio|recording|transcript)",
            re.IGNORECASE,
        ),
    ),
    (
        "INVESTIGATOR_WORKING_RECORD_METADATA",
        re.compile(
            r"(?:investigator[_\s-]*notes?|"
            r"investigation[_\s-]*working[_\s-]*notes?|"
            r"draft[_\s-]*(?:investigation[_\s-]*)?report)",
            re.IGNORECASE,
        ),
    ),
    (
        "MEDICAL_RECORD_METADATA",
        re.compile(
            r"(?:medical|health|patient)[_\s-]*(?:record|report|history)",
            re.IGNORECASE,
        ),
    ),
)


def app_protected_prescreen(
    *,
    text=None,
    metadata_values=None,
):
    """Return rule IDs only; never return or log matched protected text."""

    found = set()

    if text:
        for rule_id, pattern in _APP_PROTECTED_TEXT_RULES:
            if pattern.search(text):
                found.add(rule_id)

    for value in metadata_values or []:
        value = str(value or "")
        for rule_id, pattern in _APP_PROTECTED_METADATA_RULES:
            if pattern.search(value):
                found.add(rule_id)

    return sorted(found)


def record_app_prescreen_block(
    *,
    declared_class,
    input_mode,
    rule_ids,
    document_ids=None,
    direct_text=None,
):
    """Persist compact audit metadata without protected source text."""

    event_id = (
        "prescreen_event_"
        + uuid.uuid4().hex
    )
    reviewer = get_reviewer_identity()
    actor = (
        reviewer["email"]
        if reviewer["email"] != "unknown"
        else reviewer["username"]
    )

    content_sha256 = (
        hashlib.sha256(
            direct_text.encode("utf-8")
        ).hexdigest()
        if direct_text
        else None
    )

    with get_driver().session() as session:
        session.run(
            """
            CREATE (e:ClassificationPrescreenAttempt {
                event_id: $event_id,
                prescreen_version: $prescreen_version,
                prescreen_layer: 'APP_PREFLIGHT',
                decision: 'BLOCKED_REQUIRES_CLASS_D',
                required_class: 'D',
                declared_class: $declared_class,
                input_mode: $input_mode,
                rule_ids: $rule_ids,
                document_ids: $document_ids,
                content_sha256: $content_sha256,
                created_by: $created_by,
                created_at: datetime()
            })
            """,
            event_id=event_id,
            prescreen_version=APP_PRESCREEN_VERSION,
            declared_class=declared_class,
            input_mode=input_mode,
            rule_ids=list(rule_ids),
            document_ids=list(
                document_ids or []
            ),
            content_sha256=content_sha256,
            created_by=actor,
        ).consume()

    return event_id

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

APP_BUILD = "2026-09-22-case-centric-gui-v22"

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

with st.expander(
    "AI model routing and Article 9 suitability",
    expanded=False,
):
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


def decrypt_protected_text(value):
    if not value:
        return ""

    if not DIRECT_TEXT_ENCRYPTION_KEY:
        raise RuntimeError(
            "DIRECT_TEXT_ENCRYPTION_KEY is not configured."
        )

    return Fernet(
        DIRECT_TEXT_ENCRYPTION_KEY.encode("utf-8")
    ).decrypt(
        value.encode("utf-8")
    ).decode("utf-8")


def create_question_run(
    *,
    analysis,
    question_text,
    scope_mode,
    scope_document_ids,
    model_selection,
    include_reference_context,
    interaction_surface="ASK_COMPARE",
):
    if analysis.get("status") != "COMPLETED":
        raise ValueError(
            "Questions can currently be asked only against a completed analysis."
        )

    information_class = (
        analysis.get("information_class")
        or "B"
    )
    policy = resolve_model_policy(
        information_class
    )

    if information_class == "D":
        model_plan = []

        if model_selection in {"GPT20", "BOTH"}:
            if not CLASS_D_GPT20_ENDPOINT:
                raise RuntimeError(
                    "The dedicated GPT-OSS 20B endpoint is not configured."
                )
            model_plan.append(
                ("GPT20", CLASS_D_GPT20_ENDPOINT)
            )

        if model_selection in {"LLAMA70", "BOTH"}:
            if not CLASS_D_LLAMA70_ENDPOINT:
                raise RuntimeError(
                    "The dedicated Llama 3.3 70B endpoint is not configured."
                )
            model_plan.append(
                ("LLAMA70", CLASS_D_LLAMA70_ENDPOINT)
            )

        if not model_plan:
            raise ValueError(
                "Select at least one approved Class D model."
            )
    else:
        model_service = policy.get("model")
        if not model_service:
            raise RuntimeError(
                "No approved default model is configured for this information class."
            )
        model_plan = [
            ("DEFAULT", model_service)
        ]
        model_selection = "DEFAULT"

    question_run_id = (
        "question_" + uuid.uuid4().hex
    )
    question_hash = hashlib.sha256(
        question_text.encode("utf-8")
    ).hexdigest()

    if information_class == "D":
        question_plain = ""
        question_encrypted = encrypt_direct_text(
            question_text
        )
        encryption_scheme = "FERNET"
    else:
        question_plain = question_text
        question_encrypted = ""
        encryption_scheme = ""

    reviewer = get_reviewer_identity()
    creator = (
        reviewer["email"]
        if reviewer["email"] != "unknown"
        else reviewer["username"]
    )

    model_keys = [
        item[0]
        for item in model_plan
    ]
    model_services = [
        item[1]
        for item in model_plan
    ]

    with get_driver().session() as session:
        record = session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            WHERE a.status = 'COMPLETED'
            CREATE (q:QuestionRun {
                question_run_id: $question_run_id,
                analysis_id: $analysis_id,
                information_class: $information_class,
                scope_mode: $scope_mode,
                scope_document_ids: $scope_document_ids,
                model_selection: $model_selection,
                include_reference_context: $include_reference_context,
                interaction_surface: $interaction_surface,
                model_keys: $model_keys,
                model_services: $model_services,
                question_text: $question_text,
                encrypted_question_text: $encrypted_question_text,
                question_encryption_scheme: $question_encryption_scheme,
                question_sha256: $question_sha256,
                status: 'PENDING',
                processing_stage: 'PENDING',
                created_by: $created_by,
                created_at: datetime(),
                retention_policy: properties(a)["retention_policy"],
                content_expires_at: properties(a)["content_expires_at"]
            })
            CREATE (a)-[:HAS_QUESTION_RUN]->(q)
            RETURN q.question_run_id AS question_run_id
            """,
            analysis_id=analysis["analysis_id"],
            question_run_id=question_run_id,
            information_class=information_class,
            scope_mode=scope_mode,
            scope_document_ids=scope_document_ids,
            model_selection=model_selection,
            include_reference_context=bool(include_reference_context),
            interaction_surface=interaction_surface,
            model_keys=model_keys,
            model_services=model_services,
            question_text=question_plain,
            encrypted_question_text=question_encrypted,
            question_encryption_scheme=encryption_scheme,
            question_sha256=question_hash,
            created_by=creator,
        ).single()

    if record is None:
        raise RuntimeError(
            "The QuestionRun could not be created. Confirm that the analysis is completed."
        )

    return question_run_id


def trigger_question_job(question_run_id):
    if not ASK_JOB_ID:
        raise RuntimeError(
            "No Ask Job is attached to the App. Create notebook 37's Job, "
            "attach it with resource key 'ask_job', and redeploy."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(ASK_JOB_ID),
            "job_parameters": {
                "question_run_id": question_run_id,
            },
        },
    )

    run_id = response.get("run_id")
    if not run_id:
        raise RuntimeError(
            "Databricks accepted the Ask Job but returned no run_id."
        )

    with get_driver().session() as session:
        session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })
            SET
                q.status = 'QUEUED',
                q.processing_stage = 'JOB_QUEUED',
                q.job_id = $job_id,
                q.job_run_id = $job_run_id,
                q.processing_error = NULL,
                q.updated_at = datetime()
            """,
            question_run_id=question_run_id,
            job_id=str(ASK_JOB_ID),
            job_run_id=str(run_id),
        ).consume()

    return str(run_id)


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


def get_user_access_token():
    """Return the Databricks OBO token forwarded to the Streamlit App."""

    try:
        headers = st.context.headers
        return (
            headers.get("X-Forwarded-Access-Token")
            or headers.get("x-forwarded-access-token")
        )
    except Exception:
        return None


def normalise_allowed_source_path(path):
    """Validate that a source path remains inside an approved UC volume."""

    value = str(path or "").strip()
    if not value:
        raise ValueError("No source file path is available.")

    normalized = os.path.normpath(value)

    if not normalized.startswith("/Volumes/"):
        raise ValueError(
            "The document viewer accepts Unity Catalog volume paths only."
        )

    allowed = any(
        normalized == root
        or normalized.startswith(root.rstrip("/") + "/")
        for root in ALLOWED_SOURCE_VOLUME_ROOTS
    )

    if not allowed:
        raise PermissionError(
            "The source path is outside the approved IKF/MAIRA document volumes."
        )

    return normalized


def download_source_file_as_user(path):
    """Read a UC-volume file through Databricks Files API as the logged-in user."""

    normalized = normalise_allowed_source_path(path)
    token = get_user_access_token()

    if not token:
        raise PermissionError(
            "No forwarded Databricks user token is available. "
            "User authorization with the files scope is required."
        )

    host = get_workspace_client().config.host.rstrip("/")
    encoded_path = urllib.parse.quote(
        normalized,
        safe="/",
    )
    url = (
        host
        + "/api/2.0/fs/files"
        + encoded_path
    )

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=90,
        ) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise PermissionError(
                "You are not authorised to read this source document "
                "from its Unity Catalog volume."
            ) from exc
        if exc.code == 404:
            raise FileNotFoundError(
                "The source document is no longer available at the "
                "registered Unity Catalog path."
            ) from exc
        raise RuntimeError(
            f"Databricks Files API returned HTTP {exc.code}."
        ) from exc


def parse_evidence_location(value):
    """Parse document_id|page_start|page_end emitted by notebook 16."""

    parts = str(value or "").split("|")
    if len(parts) != 3 or not parts[0]:
        return None

    def parse_page(raw):
        raw = raw.strip()
        return int(raw) if raw.isdigit() else None

    return {
        "document_id": parts[0],
        "page_start": parse_page(parts[1]),
        "page_end": parse_page(parts[2]),
    }


def pdf_page_range_bytes(pdf_bytes, page_start, page_end):
    """Create a small PDF containing only the evidence page range."""

    source = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )
    try:
        if source.page_count < 1:
            raise ValueError("The PDF contains no pages.")

        start = int(page_start or 1)
        end = int(page_end or start)

        if start < 1 or end < start or start > source.page_count:
            raise ValueError(
                "The evidence page reference is outside the source PDF."
            )

        end = min(end, source.page_count)

        excerpt = fitz.open()
        try:
            excerpt.insert_pdf(
                source,
                from_page=start - 1,
                to_page=end - 1,
            )
            return excerpt.tobytes()
        finally:
            excerpt.close()
    finally:
        source.close()


def format_evidence_location(location, source):
    filename = (
        (source or {}).get("viewer_source_filename")
        or (source or {}).get("filename")
        or location["document_id"]
    )
    start = location.get("page_start")
    end = location.get("page_end")

    if start is None:
        page_text = "page unknown"
    elif end is None or end == start:
        page_text = f"p. {start}"
    else:
        page_text = f"pp. {start}–{end}"

    repository = (
        (source or {}).get("viewer_source_repository")
        or "source"
    )

    return f"{filename} · {page_text} · {repository}"


@st.cache_data(ttl=30)
def load_source_documents():
    query = """
    MATCH (d:SourceDocument)
    WHERE coalesce(
        properties(d)["catalogue_status"],
        "AVAILABLE"
    ) = "AVAILABLE"
    RETURN
        d.document_id AS document_id,
        d.filename AS filename,
        d.volume_path AS volume_path,
        d.relative_path AS relative_path,
        d.source_type AS source_type,
        d.byte_size AS byte_size,
        d.sha256 AS sha256,
        coalesce(
            properties(d)["source_managed_by"],
            "IKF"
        ) AS source_managed_by,
        coalesce(
            properties(d)["source_repository"],
            properties(d)["source_managed_by"],
            "IKF"
        ) AS source_repository,
        properties(d)["maira_report_package_id"] AS maira_report_package_id,
        properties(d)["maira_document_role"] AS maira_document_role,
        properties(d)["report_title"] AS report_title,
        properties(d)["vessel_name"] AS vessel_name,
        coalesce(
            properties(d)["detected_language"],
            "PENDING"
        ) AS detected_language,
        toString(d.indexed_at) AS indexed_at
    ORDER BY
        CASE
            WHEN coalesce(
                properties(d)["source_managed_by"],
                "IKF"
            ) = "MAIRA"
            THEN 0
            ELSE 1
        END,
        coalesce(
            properties(d)["report_title"],
            d.filename
        ),
        d.filename
    """

    with get_driver().session() as session:
        rows = [
            record.data()
            for record in session.run(query)
        ]

    # The same physical report can temporarily exist in both catalogues during
    # migration. Prefer the MAIRA canonical catalogue entry for identical SHA.
    by_sha = {}
    without_sha = []

    for row in rows:
        sha256 = str(row.get("sha256") or "").lower().strip()

        if not sha256:
            without_sha.append(row)
            continue

        existing = by_sha.get(sha256)

        if existing is None:
            by_sha[sha256] = row
            continue

        existing_is_maira = (
            existing.get("source_managed_by") == "MAIRA"
        )
        row_is_maira = (
            row.get("source_managed_by") == "MAIRA"
        )

        if row_is_maira and not existing_is_maira:
            by_sha[sha256] = row

    deduplicated = list(by_sha.values()) + without_sha

    return sorted(
        deduplicated,
        key=lambda item: (
            0
            if item.get("source_managed_by") == "MAIRA"
            else 1,
            (
                item.get("report_title")
                or item.get("filename")
                or ""
            ).casefold(),
            (item.get("filename") or "").casefold(),
        ),
    )


def create_analysis_from_documents(
    title,
    description,
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

    query = """
    CREATE (a:AnalysisGroup {
        analysis_id: $analysis_id,
        analysis_title: $analysis_title,
        analysis_description: $analysis_description,
        analysis_objective: NULL,
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
        question_present: false,
        question_hash: NULL,
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
            WHEN coalesce(
                properties(d)["source_managed_by"],
                "IKF"
            ) = "MAIRA"
            THEN NULL
            WHEN d.source_expires_at IS NULL
            THEN requested_expiry
            WHEN requested_expiry < d.source_expires_at
            THEN requested_expiry
            ELSE d.source_expires_at
        END,
        d.source_retention_hours = CASE
            WHEN coalesce(
                properties(d)["source_managed_by"],
                "IKF"
            ) = "MAIRA"
            THEN NULL
            WHEN d.source_retention_hours IS NULL
            THEN $content_retention_hours
            WHEN $content_retention_hours < d.source_retention_hours
            THEN $content_retention_hours
            ELSE d.source_retention_hours
        END,
        d.source_purge_status = CASE
            WHEN coalesce(
                properties(d)["source_managed_by"],
                "IKF"
            ) = "MAIRA"
            THEN "EXEMPT_MAIRA_CANONICAL"
            ELSE "ACTIVE"
        END
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
        "analysis_description": description or None,
        "information_class": information_class,
        "language_mode": language_mode,
        "output_language": output_language,
        "model_service": model_service,
        "model_selection": model_selection,
        "created_by": creator,
        "content_retention_hours": retention_hours,
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
    description,
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
        analysis_description: $analysis_description,
        analysis_objective: NULL,
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
        question_present: false,
        question_hash: NULL,
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
        "analysis_description": description or None,
        "information_class": information_class,
        "language_mode": language_mode,
        "output_language": output_language,
        "model_service": model_service,
        "model_selection": model_selection,
        "created_by": creator,
        "content_retention_hours": retention_hours,
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
        properties(a)["analysis_description"] AS analysis_description,
        a.analysis_objective AS legacy_analysis_objective,
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
        properties(a)["classification_prescreen_version"] AS classification_prescreen_version,
        properties(a)["classification_prescreen_status"] AS classification_prescreen_status,
        coalesce(properties(a)["classification_prescreen_rule_ids"], []) AS classification_prescreen_rule_ids,
        properties(a)["classification_prescreen_required_class"] AS classification_prescreen_required_class,
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
            properties(d)["viewer_source_path"],
            d.volume_path
        ) AS viewer_source_path,
        coalesce(
            properties(d)["viewer_source_repository"],
            "IKF"
        ) AS viewer_source_repository,
        coalesce(
            properties(d)["viewer_source_filename"],
            d.filename
        ) AS viewer_source_filename,
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
        properties(a)["extraction_duration_seconds"] AS extraction_duration_seconds,
        properties(a)["evidence_source_mode"] AS evidence_source_mode,
        properties(a)["classification_prescreen_version"] AS classification_prescreen_version,
        properties(a)["classification_prescreen_status"] AS classification_prescreen_status,
        coalesce(
            properties(a)["classification_prescreen_rule_ids"],
            []
        ) AS classification_prescreen_rule_ids,
        properties(a)["classification_prescreen_required_class"] AS classification_prescreen_required_class,
        properties(a)["classification_prescreen_declared_class"] AS classification_prescreen_declared_class,
        toString(
            properties(a)["classification_prescreen_checked_at"]
        ) AS classification_prescreen_checked_at
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
        "PREPARE_EVIDENCE_FAILED": 0,
        "CLASSIFICATION_PRESCREEN_BLOCKED": 0,
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

    st.markdown("### Processing progress")

    progress_columns = st.columns(4)

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

        with progress_columns[index]:
            with st.container(border=True):
                st.markdown(
                    f"**{index + 1}. {step['label']}**"
                )
                st.write(
                    marker + " " + state_text
                )
                if (
                    index == current_step
                    and status != "COMPLETED"
                ):
                    st.caption(
                        step["description"]
                    )

    if status == "COMPLETED":
        st.success(
            "All four processing stages completed. Result ready for review."
        )

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

        evidence_source_mode = evidence_counts.get(
            "evidence_source_mode"
        )
        if evidence_source_mode:
            evidence_source_labels = {
                "MAIRA_CANONICAL": "MAIRA canonical passages",
                "MAIRA_FIRST_MIXED": "MAIRA canonical + temporary IKF fallback",
                "IKF_LOCAL_FALLBACK": "Temporary IKF local extraction",
                "IKF_DIRECT_TEXT": "IKF direct-text evidence",
            }
            st.write(
                "Evidence source: "
                + evidence_source_labels.get(
                    evidence_source_mode,
                    evidence_source_mode,
                )
            )


        prescreen_status = evidence_counts.get(
            "classification_prescreen_status"
        )
        if prescreen_status:
            st.write(
                "Information-class pre-screen: "
                + prescreen_status
            )
            prescreen_version = evidence_counts.get(
                "classification_prescreen_version"
            )
            if prescreen_version:
                st.caption(
                    "Pre-screen rule version: "
                    + prescreen_version
                )

            prescreen_rules = (
                evidence_counts.get(
                    "classification_prescreen_rule_ids"
                )
                or []
            )
            if prescreen_rules:
                st.caption(
                    "Triggered rule IDs: "
                    + ", ".join(
                        prescreen_rules
                    )
                )

            required_class = evidence_counts.get(
                "classification_prescreen_required_class"
            )
            if required_class:
                st.caption(
                    "Required processing class: "
                    + required_class
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
        properties(a)["answer_to_question"] AS answer_to_question,
        coalesce(properties(a)["answer_passage_ids"], []) AS answer_passage_ids,
        coalesce(properties(a)["answer_references"], []) AS answer_references,
        coalesce(properties(a)["answer_locations"], []) AS answer_locations,
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
        properties(m)["answer_to_question"] AS answer_to_question,
        coalesce(properties(m)["answer_passage_ids"], []) AS answer_passage_ids,
        coalesce(properties(m)["answer_references"], []) AS answer_references,
        coalesce(properties(m)["answer_locations"], []) AS answer_locations,
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


@st.cache_data(ttl=60)
def load_reference_documents():
    query = """
    MATCH (d:ReferenceDocument)
    WHERE coalesce(
        d.catalogue_status,
        'AVAILABLE'
    ) = 'AVAILABLE'
    RETURN
        d.reference_document_id AS reference_document_id,
        d.filename AS filename,
        d.source_type AS source_type,
        d.reference_family AS reference_family,
        d.reference_code AS reference_code,
        d.reference_title AS reference_title,
        d.source_authority AS source_authority,
        d.canonical_url AS canonical_url,
        d.retrieval_origin AS retrieval_origin,
        d.viewer_source_repository AS viewer_source_repository,
        d.viewer_source_path AS viewer_source_path,
        d.viewer_source_filename AS viewer_source_filename,
        coalesce(d.page_count, 0) AS page_count
    ORDER BY
        d.reference_family,
        coalesce(
            d.reference_code,
            d.reference_title,
            d.filename
        )
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(query)
        ]


@st.cache_data(ttl=30)
def load_question_runs(analysis_id):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
          -[:HAS_QUESTION_RUN]->
          (q:QuestionRun)
    RETURN
        q.question_run_id AS question_run_id,
        q.analysis_id AS analysis_id,
        q.information_class AS information_class,
        q.scope_mode AS scope_mode,
        coalesce(q.scope_document_ids, []) AS scope_document_ids,
        q.model_selection AS model_selection,
        coalesce(q.interaction_surface, 'ASK_COMPARE') AS interaction_surface,
        coalesce(q.include_reference_context, false) AS include_reference_context,
        coalesce(q.model_keys, []) AS model_keys,
        q.question_text AS question_text,
        q.encrypted_question_text AS encrypted_question_text,
        q.question_encryption_scheme AS question_encryption_scheme,
        q.status AS status,
        q.processing_stage AS processing_stage,
        q.processing_error AS processing_error,
        q.job_run_id AS job_run_id,
        q.retrieval_mode AS retrieval_mode,
        q.retrieval_snapshot_id AS retrieval_snapshot_id,
        coalesce(q.retrieval_passage_ids, []) AS retrieval_passage_ids,
        q.reference_retrieval_mode AS reference_retrieval_mode,
        q.reference_retrieval_snapshot_id AS reference_retrieval_snapshot_id,
        coalesce(q.reference_retrieval_passage_ids, []) AS reference_retrieval_passage_ids,
        coalesce(q.reference_context_passage_count, 0) AS reference_context_passage_count,
        coalesce(q.retrieval_candidate_count, 0) AS retrieval_candidate_count,
        coalesce(q.retrieval_selected_count, 0) AS retrieval_selected_count,
        coalesce(q.retrieval_selected_characters, 0) AS retrieval_selected_characters,
        coalesce(q.retrieval_query_terms, []) AS retrieval_query_terms,
        coalesce(q.retrieval_activated_expansions, []) AS retrieval_activated_expansions,
        q.governed_query_id AS governed_query_id,
        q.governed_query_spec_id AS governed_query_spec_id,
        q.governed_relationship AS governed_relationship,
        q.deterministic_answer AS deterministic_answer,
        coalesce(q.insufficient_evidence, false) AS insufficient_evidence,
        q.created_by AS created_by,
        toString(q.created_at) AS created_at,
        toString(q.completed_at) AS completed_at
    ORDER BY q.created_at DESC
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
def load_question_model_runs(question_run_id):
    query = """
    MATCH (q:QuestionRun {
        question_run_id: $question_run_id
    })-[:HAS_MODEL_ANSWER]->(m:QuestionModelRun)
    RETURN
        m.question_model_run_id AS question_model_run_id,
        m.model_key AS model_key,
        m.model_label AS model_label,
        m.model_service AS model_service,
        m.status AS status,
        m.answer AS answer,
        coalesce(m.passage_ids, []) AS passage_ids,
        coalesce(m.evidence_references, []) AS evidence_references,
        coalesce(m.evidence_locations, []) AS evidence_locations,
        coalesce(m.source_evidence_passage_ids, []) AS source_evidence_passage_ids,
        coalesce(m.source_evidence_references, []) AS source_evidence_references,
        coalesce(m.source_evidence_locations, []) AS source_evidence_locations,
        coalesce(m.reference_context_passage_ids, []) AS reference_context_passage_ids,
        coalesce(m.reference_context_references, []) AS reference_context_references,
        coalesce(m.reference_context_locations, []) AS reference_context_locations,
        coalesce(m.limitations, []) AS limitations,
        coalesce(m.insufficient_evidence, false) AS insufficient_evidence,
        m.duration_seconds AS duration_seconds,
        coalesce(m.total_tokens, 0) AS total_tokens,
        m.processing_error AS processing_error,
        toString(m.completed_at) AS completed_at
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
                question_run_id=question_run_id,
            )
        ]


def question_display_text(question_run):
    plain = str(
        question_run.get("question_text")
        or ""
    ).strip()

    if plain:
        return plain

    encrypted = question_run.get(
        "encrypted_question_text"
    )
    if encrypted:
        try:
            return decrypt_protected_text(
                encrypted
            )
        except Exception:
            return "[Protected Class D question]"

    return "—"


def render_question_answer(
    *,
    analysis_id,
    question_run,
    model_run,
    render_key,
):
    st.markdown(
        f"### {model_run.get('model_label') or model_run.get('model_key') or 'Model'}"
    )
    st.caption(
        f"{model_run.get('model_service') or '—'} · "
        f"{model_run.get('status') or 'UNKNOWN'}"
    )

    if model_run.get("status") == "FAILED":
        st.error(
            model_run.get("processing_error")
            or "The model answer failed."
        )
        return

    answer = model_run.get("answer")
    if answer:
        if model_run.get("insufficient_evidence"):
            st.warning(answer)
        else:
            st.info(answer)
    else:
        st.info("No answer has been returned yet.")

    source_references = (
        model_run.get(
            "source_evidence_references"
        )
        or []
    )
    reference_references = (
        model_run.get(
            "reference_context_references"
        )
        or []
    )

    if source_references:
        st.markdown(
            "**Case evidence — SOURCE_EVIDENCE**"
        )
        for reference in source_references:
            st.write(f"• {reference}")

    if reference_references:
        st.markdown(
            "**Reference context — REFERENCE_CONTEXT**"
        )
        for reference in reference_references:
            st.write(f"• {reference}")
        st.caption(
            "Reference context supports framework, methodology or technical "
            "background. It is not evidence that a case fact occurred."
        )

    if (
        not source_references
        and not reference_references
        and model_run.get("status")
        == "COMPLETED"
    ):
        st.warning(
            "The answer contains no valid source-layer citation."
        )

    limitations = (
        model_run.get("limitations")
        or []
    )
    if limitations:
        with st.expander("Limitations", expanded=False):
            for item in limitations:
                st.write(f"• {item}")

    m1, m2 = st.columns(2)
    duration = model_run.get("duration_seconds")
    m1.metric(
        "Elapsed",
        (
            f"{float(duration):.1f} s"
            if duration is not None
            else "—"
        ),
    )
    m2.metric(
        "Tokens",
        model_run.get("total_tokens") or "—",
    )

    source_locations = [
        {
            "layer": "SOURCE_EVIDENCE",
            "location": parsed,
        }
        for parsed in (
            parse_evidence_location(value)
            for value in (
                model_run.get(
                    "source_evidence_locations"
                )
                or []
            )
        )
        if parsed is not None
    ]

    reference_locations = [
        {
            "layer": "REFERENCE_CONTEXT",
            "location": parsed,
        }
        for parsed in (
            parse_evidence_location(value)
            for value in (
                model_run.get(
                    "reference_context_locations"
                )
                or []
            )
        )
        if parsed is not None
    ]

    layered_locations = (
        source_locations
        + reference_locations
    )

    if not layered_locations:
        return

    source_by_id = {
        source["document_id"]: source
        for source in load_analysis_sources(
            analysis_id
        )
    }

    for reference_source in load_reference_documents():
        source_by_id[
            reference_source["reference_document_id"]
        ] = reference_source

    location_index = st.selectbox(
        "Cited source page",
        options=list(
            range(
                len(layered_locations)
            )
        ),
        format_func=lambda index: (
            layered_locations[index][
                "layer"
            ]
            + " · "
            + format_evidence_location(
                layered_locations[index][
                    "location"
                ],
                source_by_id.get(
                    layered_locations[index][
                        "location"
                    ]["document_id"]
                ),
            )
        ),
        key=(
            "question_citation_"
            + question_run[
                "question_run_id"
            ]
            + "_"
            + render_key
        ),
    )

    selected_layered_location = (
        layered_locations[
            location_index
        ]
    )
    layer = selected_layered_location[
        "layer"
    ]
    location = selected_layered_location[
        "location"
    ]
    source = source_by_id.get(
        location["document_id"]
    )

    st.caption(
        "Source layer: "
        + layer
        + (
            " — case-specific occurrence evidence."
            if layer == "SOURCE_EVIDENCE"
            else (
                " — framework/technical context only; "
                "not proof of a case fact."
            )
        )
    )

    if source is None:
        st.caption(
            "The cited document is not available in the relevant governed source catalogue."
        )
        return

    if layer == "REFERENCE_CONTEXT":
        canonical_url = str(
            source.get("canonical_url")
            or ""
        ).strip()
        source_authority = str(
            source.get("source_authority")
            or ""
        ).strip()

        if source_authority:
            st.caption(
                "Authoritative source: "
                + source_authority
            )

        if canonical_url:
            st.link_button(
                "Open authoritative source",
                canonical_url,
            )

    source_path = source.get(
        "viewer_source_path"
    )
    source_type = str(
        source.get("source_type") or ""
    ).upper()

    if (
        source_type != "PDF"
        or not source_path
    ):
        st.caption(
            "The citation is available, but an embedded PDF source is not available."
        )
        return

    try:
        pdf_bytes = download_source_file_as_user(
            source_path
        )
        excerpt_bytes = pdf_page_range_bytes(
            pdf_bytes,
            location.get("page_start"),
            location.get("page_end"),
        )

        st.pdf(
            excerpt_bytes,
            height=650,
            key=(
                "question_pdf_"
                + hashlib.sha256(
                    (
                        question_run[
                            "question_run_id"
                        ]
                        + "|"
                        + render_key
                        + "|"
                        + layer
                        + "|"
                        + source_path
                        + "|"
                        + str(
                            location.get(
                                "page_start"
                            )
                        )
                        + "|"
                        + str(
                            location.get(
                                "page_end"
                            )
                        )
                    ).encode("utf-8")
                ).hexdigest()[:16]
            ),
        )
    except PermissionError as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.caption(
            "The cited page could not be rendered: "
            + str(exc)
        )


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
        coalesce(properties(n)["evidence_passage_ids"], []) AS passage_ids,
        coalesce(properties(n)["evidence_references"], []) AS evidence_references,
        coalesce(properties(n)["evidence_locations"], []) AS evidence_locations
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
        source.label AS source_label,
        target.node_id AS target_id,
        target.label AS target_label,
        source.model_run_id AS model_run_id,
        properties(r)["evidence_class"] AS evidence_class,
        coalesce(properties(r)["edge_class"], "REPORT_DERIVED") AS edge_class,
        coalesce(properties(r)["evidence_passage_ids"], []) AS passage_ids,
        coalesce(properties(r)["evidence_references"], []) AS evidence_references,
        coalesce(properties(r)["evidence_locations"], []) AS evidence_locations
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


def render_visible_source_references(graph, *, empty_message=True):
    """Show report/page references prominently for a completed graph."""

    references = []
    seen = set()

    for item in (
        list(graph.get("nodes") or [])
        + list(graph.get("edges") or [])
    ):
        for reference in item.get("evidence_references") or []:
            if reference not in seen:
                seen.add(reference)
                references.append(reference)

    if references:
        st.markdown("**Source pages**")
        for reference in references:
            st.write(f"• {reference}")
        return True

    if empty_message:
        st.caption(
            "No page-level references are stored for this analysis. "
            "Analyses created before the page-reference update must be rerun "
            "to generate document/page locations."
        )

    return False


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

    if model_run.get("answer_to_question"):
        st.markdown("**Answer to question / objective**")
        st.info(model_run["answer_to_question"])
        answer_refs = model_run.get("answer_references") or []
        if answer_refs:
            st.caption(
                "Evidence: " + " · ".join(answer_refs)
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
                    "evidence_references": (
                        node.get("evidence_references")
                        or []
                    ),
                    "evidence_locations": (
                        node.get("evidence_locations")
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
                    "evidence_references": (
                        edge.get("evidence_references")
                        or []
                    ),
                    "evidence_locations": (
                        edge.get("evidence_locations")
                        or []
                    ),
                }
            }
            for edge in graph["edges"]
        ],
    }

    render_visible_source_references(
        graph,
        empty_message=True,
    )

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
        coalesce(properties(n)["evidence_passage_ids"], []) AS passage_ids,
        coalesce(properties(n)["evidence_references"], []) AS evidence_references,
        coalesce(properties(n)["evidence_locations"], []) AS evidence_locations
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
        source.model_run_id AS model_run_id,
        properties(r)["evidence_class"] AS evidence_class,
        coalesce(properties(r)["edge_class"], "REPORT_DERIVED") AS edge_class,
        coalesce(properties(r)["evidence_passage_ids"], []) AS passage_ids,
        coalesce(properties(r)["evidence_references"], []) AS evidence_references,
        coalesce(properties(r)["evidence_locations"], []) AS evidence_locations
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
    MATCH (a:AnalysisGroup {
        analysis_id: $analysis_id
    })
    MATCH (source:KGNode {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id,
        node_id: $source_node_id
    })
    MATCH (target:KGNode {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id,
        node_id: $target_node_id
    })
    CREATE (review:RelationshipReview {
        review_id: $review_id,
        analysis_id: $analysis_id,
        model_run_id: $model_run_id,
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
    CREATE (a)-[:HAS_RELATIONSHIP_REVIEW]->(review)
    CREATE (review)-[:REVIEWS_SOURCE]->(source)
    CREATE (review)-[:REVIEWS_TARGET]->(target)
    RETURN review.review_id AS review_id
    """

    params = {
        "review_id": review_id,
        "analysis_id": analysis_id,
        "model_run_id": edge["model_run_id"],
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
        latest.model_run_id AS model_run_id,
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



def trigger_relationship_correction_job(
    analysis_id,
    model_run_id,
    edge_id,
):
    if not RELATIONSHIP_CORRECTION_JOB_ID:
        raise RuntimeError(
            "No relationship-correction Job is attached to the App. "
            "Create notebook 50's Job, attach it with resource key "
            "'relationship_correction_job', and redeploy."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(
                RELATIONSHIP_CORRECTION_JOB_ID
            ),
            "job_parameters": {
                "analysis_id": analysis_id,
                "model_run_id": model_run_id,
                "edge_id": edge_id,
            },
        },
    )

    run_id = response.get("run_id")
    if not run_id:
        raise RuntimeError(
            "Databricks accepted the relationship-correction Job "
            "but returned no run_id."
        )

    with get_driver().session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            SET
                a.relationship_correction_status = 'QUEUED',
                a.relationship_correction_model_run_id = $model_run_id,
                a.relationship_correction_edge_id = $edge_id,
                a.relationship_correction_job_run_id = $job_run_id,
                a.relationship_correction_error = NULL,
                a.relationship_correction_updated_at = datetime()
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
            edge_id=edge_id,
            job_run_id=str(run_id),
        ).consume()

    return str(run_id)


@st.cache_data(ttl=30)
def load_relationship_correction_proposals(
    analysis_id,
    model_run_id,
    edge_id=None,
):
    query = """
    MATCH (a:AnalysisGroup {
        analysis_id: $analysis_id
    })-[:HAS_RELATIONSHIP_CORRECTION_PROPOSAL]->(
        p:RelationshipCorrectionProposal {
            model_run_id: $model_run_id
        }
    )
    WHERE $edge_id IS NULL
       OR p.edge_id = $edge_id
    OPTIONAL MATCH (
        latest:RelationshipReview {
            analysis_id: $analysis_id,
            model_run_id: $model_run_id,
            edge_id: p.edge_id
        }
    )
    WITH a, p, latest
    ORDER BY latest.reviewed_at DESC
    WITH
        a,
        p,
        head(collect(latest)) AS latest_review
    RETURN
        p.proposal_id AS proposal_id,
        p.analysis_id AS analysis_id,
        p.model_run_id AS model_run_id,
        p.edge_id AS edge_id,
        p.source_node_id AS source_node_id,
        p.source_label AS source_label,
        p.target_node_id AS target_node_id,
        p.target_label AS target_label,
        p.original_relationship AS original_relationship,
        p.base_relationship_review_id AS base_review_id,
        p.assistant_status AS assistant_status,
        p.action AS action,
        p.proposed_relationship AS proposed_relationship,
        p.rationale AS rationale,
        coalesce(
            p.evidence_passage_ids,
            []
        ) AS evidence_passage_ids,
        coalesce(
            p.evidence_references,
            []
        ) AS evidence_references,
        coalesce(
            p.evidence_locations,
            []
        ) AS evidence_locations,
        p.proposal_version AS proposal_version,
        p.model_service AS model_service,
        CASE
            WHEN p.base_relationship_review_id IS NULL
                 AND latest_review IS NULL
            THEN true
            WHEN latest_review IS NOT NULL
                 AND latest_review.review_id
                     = p.base_relationship_review_id
            THEN true
            ELSE false
        END AS base_review_is_current,
        CASE
            WHEN latest_review IS NULL
            THEN NULL
            ELSE latest_review.review_id
        END AS current_relationship_review_id,
        toString(p.updated_at) AS updated_at
    ORDER BY p.updated_at DESC, p.proposal_id
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
                edge_id=edge_id,
            )
        ]


@st.cache_data(ttl=30)
def load_latest_relationship_correction_reviews(
    analysis_id,
    model_run_id,
):
    query = """
    MATCH (review:RelationshipCorrectionReview {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id
    })
    WITH review
    ORDER BY review.reviewed_at DESC
    WITH
        review.proposal_id AS proposal_id,
        collect(review)[0] AS latest
    RETURN
        proposal_id,
        latest.review_id AS review_id,
        latest.human_decision AS decision,
        latest.applied_relationship_decision AS applied_relationship_decision,
        latest.applied_relationship AS applied_relationship,
        latest.authoritative_relationship_review_id AS authoritative_relationship_review_id,
        latest.reviewer_email AS reviewer_email,
        latest.reviewer_username AS reviewer_username,
        latest.review_comment AS review_comment,
        toString(latest.reviewed_at) AS reviewed_at
    """

    with get_driver().session() as session:
        return {
            record["proposal_id"]: record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
            )
        }


def save_relationship_correction_review(
    proposal,
    *,
    decision,
    amended_outcome=None,
    comment="",
):
    if not proposal.get("base_review_is_current"):
        raise ValueError(
            "The human relationship review changed after this proposal was "
            "generated. Regenerate the correction proposal first."
        )

    if (
        proposal.get("assistant_status")
        != "ASSISTANT_PROPOSED"
    ):
        raise ValueError(
            "Only a grounded relationship-correction proposal can be reviewed."
        )

    allowed_relationships = {
        "FOLLOWED_BY",
        "CONTRIBUTED_TO",
        "RESULTED_IN",
        "AFFECTED",
        "SUPPORTS",
    }

    if decision not in {
        "APPROVED",
        "DISMISSED",
        "APPLIED_WITH_AMENDMENT",
    }:
        raise ValueError(
            "Unsupported relationship-correction review decision."
        )

    assistant_action = proposal.get(
        "action"
    )
    original_relationship = proposal.get(
        "original_relationship"
    )
    proposed_relationship = proposal.get(
        "proposed_relationship"
    )

    relationship_decision = None
    applied_relationship = None

    if decision == "APPROVED":
        if assistant_action == "KEEP":
            relationship_decision = "VALIDATED"
        elif assistant_action == "REJECT_RELATIONSHIP":
            relationship_decision = "REJECTED"
        elif assistant_action == "CHANGE_RELATIONSHIP":
            if (
                proposed_relationship
                not in allowed_relationships
            ):
                raise ValueError(
                    "The proposal does not contain a valid replacement relationship."
                )
            relationship_decision = "AMENDED"
            applied_relationship = proposed_relationship
        else:
            raise ValueError(
                "This assistant proposal has no actionable correction to approve."
            )

    elif decision == "APPLIED_WITH_AMENDMENT":
        outcome = str(
            amended_outcome or ""
        ).strip().upper()

        if outcome == "KEEP_CURRENT":
            relationship_decision = "VALIDATED"
        elif outcome == "REJECT_RELATIONSHIP":
            relationship_decision = "REJECTED"
        elif outcome in allowed_relationships:
            if outcome == original_relationship:
                relationship_decision = "VALIDATED"
            else:
                relationship_decision = "AMENDED"
                applied_relationship = outcome
        else:
            raise ValueError(
                "Choose a valid final human relationship outcome."
            )

    # DISMISSED intentionally creates no authoritative RelationshipReview.
    correction_review_id = (
        "relationship_correction_review_"
        + uuid.uuid4().hex
    )
    relationship_review_id = (
        str(uuid.uuid4())
        if relationship_decision
        else None
    )

    reviewer = get_reviewer_identity()

    def persist(tx):
        current = tx.run(
            """
            MATCH (p:RelationshipCorrectionProposal {
                proposal_id: $proposal_id,
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                edge_id: $edge_id
            })
            OPTIONAL MATCH (latest:RelationshipReview {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                edge_id: $edge_id
            })
            WITH p, latest
            ORDER BY latest.reviewed_at DESC
            WITH p, head(collect(latest)) AS latest_review
            RETURN
                p.proposal_id AS proposal_id,
                p.base_relationship_review_id AS base_review_id,
                CASE
                    WHEN p.base_relationship_review_id IS NULL
                         AND latest_review IS NULL
                    THEN true
                    WHEN latest_review IS NOT NULL
                         AND latest_review.review_id
                             = p.base_relationship_review_id
                    THEN true
                    ELSE false
                END AS is_current
            """,
            proposal_id=proposal["proposal_id"],
            analysis_id=proposal["analysis_id"],
            model_run_id=proposal["model_run_id"],
            edge_id=proposal["edge_id"],
        ).single()

        if (
            current is None
            or not current["is_current"]
        ):
            raise ValueError(
                "The correction proposal is stale because the relationship "
                "has a newer human review."
            )

        tx.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            MATCH (p:RelationshipCorrectionProposal {
                proposal_id: $proposal_id
            })
            CREATE (review:RelationshipCorrectionReview {
                review_id: $review_id,
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                proposal_id: $proposal_id,
                edge_id: $edge_id,
                human_decision: $human_decision,
                assistant_action: $assistant_action,
                assistant_proposed_relationship: $assistant_proposed_relationship,
                applied_relationship_decision: $applied_relationship_decision,
                applied_relationship: $applied_relationship,
                authoritative_relationship_review_id: $authoritative_relationship_review_id,
                reviewer_email: $reviewer_email,
                reviewer_user_id: $reviewer_user_id,
                reviewer_username: $reviewer_username,
                reviewed_at: datetime(),
                review_comment: $review_comment
            })
            CREATE (a)-[:HAS_RELATIONSHIP_CORRECTION_REVIEW]->(review)
            CREATE (review)-[:REVIEWS_RELATIONSHIP_CORRECTION_PROPOSAL]->(p)
            """,
            review_id=correction_review_id,
            analysis_id=proposal["analysis_id"],
            model_run_id=proposal["model_run_id"],
            proposal_id=proposal["proposal_id"],
            edge_id=proposal["edge_id"],
            human_decision=decision,
            assistant_action=assistant_action,
            assistant_proposed_relationship=proposed_relationship,
            applied_relationship_decision=relationship_decision,
            applied_relationship=applied_relationship,
            authoritative_relationship_review_id=relationship_review_id,
            reviewer_email=reviewer["email"],
            reviewer_user_id=reviewer["user_id"],
            reviewer_username=reviewer["username"],
            review_comment=comment or None,
        ).consume()

        if not relationship_decision:
            return

        status_by_decision = {
            "VALIDATED": "HUMAN_VALIDATED",
            "REJECTED": "HUMAN_REJECTED",
            "AMENDED": "HUMAN_AMENDED",
        }

        tx.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            MATCH (source:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $source_node_id
            })
            MATCH (target:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $target_node_id
            })
            MATCH (p:RelationshipCorrectionProposal {
                proposal_id: $proposal_id
            })
            MATCH (correction_review:RelationshipCorrectionReview {
                review_id: $correction_review_id
            })
            CREATE (review:RelationshipReview {
                review_id: $relationship_review_id,
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                edge_id: $edge_id,
                source_node_id: $source_node_id,
                source_label: $source_label,
                original_relationship: $original_relationship,
                target_node_id: $target_node_id,
                target_label: $target_label,
                assistant_review_status: 'LLM_CORRECTION_PROPOSAL',
                human_review_decision: $human_review_decision,
                human_review_status: $human_review_status,
                amended_relationship: $amended_relationship,
                correction_proposal_id: $proposal_id,
                correction_review_id: $correction_review_id,
                reviewer_email: $reviewer_email,
                reviewer_user_id: $reviewer_user_id,
                reviewer_username: $reviewer_username,
                reviewed_at: datetime(),
                review_comment: $review_comment
            })
            CREATE (a)-[:HAS_RELATIONSHIP_REVIEW]->(review)
            CREATE (review)-[:REVIEWS_SOURCE]->(source)
            CREATE (review)-[:REVIEWS_TARGET]->(target)
            CREATE (review)-[:APPLIES_CORRECTION_PROPOSAL]->(p)
            CREATE (correction_review)-[:CREATED_RELATIONSHIP_REVIEW]->(review)
            """,
            relationship_review_id=relationship_review_id,
            correction_review_id=correction_review_id,
            analysis_id=proposal["analysis_id"],
            model_run_id=proposal["model_run_id"],
            proposal_id=proposal["proposal_id"],
            edge_id=proposal["edge_id"],
            source_node_id=proposal["source_node_id"],
            source_label=proposal["source_label"],
            original_relationship=original_relationship,
            target_node_id=proposal["target_node_id"],
            target_label=proposal["target_label"],
            human_review_decision=relationship_decision,
            human_review_status=status_by_decision[
                relationship_decision
            ],
            amended_relationship=applied_relationship,
            reviewer_email=reviewer["email"],
            reviewer_user_id=reviewer["user_id"],
            reviewer_username=reviewer["username"],
            review_comment=comment or None,
        ).consume()

    with get_driver().session() as session:
        session.execute_write(
            persist
        )

    return {
        "correction_review_id":
            correction_review_id,
        "relationship_review_id":
            relationship_review_id,
        "relationship_decision":
            relationship_decision,
        "applied_relationship":
            applied_relationship,
    }


def trigger_similar_cases_job(
    analysis_id,
):
    if not SIMILAR_CASES_JOB_ID:
        raise RuntimeError(
            "No Similar MAIRA Cases Job is attached to the App. "
            "Create notebook 53's Job, attach it with resource key "
            "'similar_cases_job', and redeploy."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(
                SIMILAR_CASES_JOB_ID
            ),
            "job_parameters": {
                "analysis_id":
                    analysis_id,
            },
        },
    )

    run_id = response.get(
        "run_id"
    )

    if not run_id:
        raise RuntimeError(
            "Databricks accepted the Similar MAIRA Cases Job "
            "but returned no run_id."
        )

    with get_driver().session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            SET
                a.similar_cases_status = 'QUEUED',
                a.similar_cases_job_run_id = $job_run_id,
                a.similar_cases_error = NULL,
                a.similar_cases_updated_at = datetime()
            """,
            analysis_id=analysis_id,
            job_run_id=str(
                run_id
            ),
        ).consume()

    return str(
        run_id
    )


@st.cache_data(ttl=30)
def load_similar_case_candidates(
    analysis_id,
):
    query = """
    MATCH (a:AnalysisGroup {
        analysis_id: $analysis_id
    })-[:HAS_SIMILAR_CASE_RUN]->(
        run:SimilarCaseRun
    )-[:HAS_SIMILAR_CASE_CANDIDATE]->(
        c:SimilarCaseCandidate
    )
    WITH
        run,
        c
    ORDER BY
        run.updated_at DESC,
        c.rank ASC
    WITH
        collect({
            run_id:
                run.similar_case_run_id,
            retrieval_method:
                run.retrieval_method,
            retrieval_snapshot_id:
                run.retrieval_snapshot_id,
            run_updated_at:
                toString(
                    run.updated_at
                ),
            candidate_id:
                c.candidate_id,
            rank:
                c.rank,
            report_package_id:
                c.report_package_id,
            report_title:
                c.report_title,
            vessel_name:
                c.vessel_name,
            source_filename:
                c.source_filename,
            publication_date:
                c.publication_date,
            investigation_body:
                c.investigation_body,
            matched_query_terms:
                coalesce(
                    c.matched_query_terms,
                    []
                ),
            matched_expansion_terms:
                coalesce(
                    c.matched_expansion_terms,
                    []
                ),
            total_score:
                c.total_score,
            max_passage_score:
                c.max_passage_score,
            evidence_passage_ids:
                coalesce(
                    c.evidence_passage_ids,
                    []
                ),
            evidence_references:
                coalesce(
                    c.evidence_references,
                    []
                ),
            evidence_locations:
                coalesce(
                    c.evidence_locations,
                    []
                )
        }) AS rows
    RETURN rows
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            analysis_id=analysis_id,
        ).single()

    if record is None:
        return []

    rows = record[
        "rows"
    ] or []

    if not rows:
        return []

    latest_run_id = rows[0][
        "run_id"
    ]

    return [
        row
        for row in rows
        if row[
            "run_id"
        ]
        == latest_run_id
    ]


def trigger_shield_proposal_job(
    analysis_id,
    model_run_id,
):
    if not SHIELD_PROPOSAL_JOB_ID:
        raise RuntimeError(
            "No SHIELD proposal Job is attached to the App. "
            "Create notebook 47's Job, attach it with resource key "
            "'shield_proposal_job', and redeploy."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(
                SHIELD_PROPOSAL_JOB_ID
            ),
            "job_parameters": {
                "analysis_id": analysis_id,
                "model_run_id": model_run_id,
            },
        },
    )

    run_id = response.get("run_id")
    if not run_id:
        raise RuntimeError(
            "Databricks accepted the SHIELD proposal Job but returned no run_id."
        )

    with get_driver().session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            SET
                a.shield_proposal_status = 'QUEUED',
                a.shield_proposal_model_run_id = $model_run_id,
                a.shield_proposal_job_run_id = $job_run_id,
                a.shield_proposal_error = NULL,
                a.shield_proposal_updated_at = datetime()
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
            job_run_id=str(run_id),
        ).consume()

    return str(run_id)


@st.cache_data(ttl=30)
def load_shield_gate_eligible_factors(
    analysis_id,
    model_run_id,
):
    query = """
    MATCH (a:AnalysisGroup {
        analysis_id: $analysis_id
    })-[:HAS_RELATIONSHIP_REVIEW]->(
        review:RelationshipReview {
            model_run_id: $model_run_id
        }
    )
    WITH review
    ORDER BY review.reviewed_at DESC
    WITH
        review.edge_id AS edge_id,
        collect(review)[0] AS latest
    MATCH (source:KGNode {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id,
        node_id: latest.source_node_id
    })
    MATCH (target:KGNode {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id,
        node_id: latest.target_node_id
    })
    WHERE
        source.node_kind = 'ContributingFactor'
        AND (
            (
                latest.human_review_decision = 'VALIDATED'
                AND latest.original_relationship = 'CONTRIBUTED_TO'
            )
            OR
            (
                latest.human_review_decision = 'AMENDED'
                AND latest.amended_relationship = 'CONTRIBUTED_TO'
            )
        )
    RETURN
        latest.review_id AS gate_review_id,
        latest.edge_id AS edge_id,
        source.node_id AS factor_node_id,
        source.label AS factor_label,
        target.node_id AS target_node_id,
        target.label AS target_label
    ORDER BY source.label, target.label
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
            )
        ]


@st.cache_data(ttl=30)
def load_shield_proposals(
    analysis_id,
    model_run_id,
):
    query = """
    MATCH (a:AnalysisGroup {
        analysis_id: $analysis_id
    })-[:HAS_SHIELD_PROPOSAL]->(
        p:ShieldProposal {
            model_run_id: $model_run_id
        }
    )-[:CLASSIFIES_FACTOR]->(n:KGNode)
    MATCH (p)-[:GATED_BY_REVIEW]->(gate:RelationshipReview)
    OPTIONAL MATCH (latest:RelationshipReview {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id,
        edge_id: p.edge_id
    })
    WITH a, p, n, gate, latest
    ORDER BY latest.reviewed_at DESC
    WITH
        a, p, n, gate,
        head(collect(latest)) AS newest_gate_review
    RETURN
        p.proposal_id AS proposal_id,
        p.analysis_id AS analysis_id,
        p.model_run_id AS model_run_id,
        p.factor_node_id AS factor_node_id,
        p.factor_label AS factor_label,
        p.target_node_id AS target_node_id,
        p.target_label AS target_label,
        p.edge_id AS edge_id,
        p.gate_relationship_review_id AS gate_review_id,
        p.gate_human_decision AS gate_human_decision,
        p.assistant_status AS assistant_status,
        p.proposed_shield_label AS proposed_shield_label,
        p.proposed_shield_code AS proposed_shield_code,
        p.proposed_shield_path AS proposed_shield_path,
        p.rationale AS rationale,
        coalesce(p.shield_passage_ids, []) AS shield_passage_ids,
        coalesce(p.shield_references, []) AS shield_references,
        coalesce(p.shield_locations, []) AS shield_locations,
        p.shield_corpus_snapshot_id AS shield_corpus_snapshot_id,
        p.retrieval_method AS retrieval_method,
        p.proposal_version AS proposal_version,
        p.model_service AS model_service,
        CASE
            WHEN newest_gate_review IS NULL
            THEN false
            ELSE newest_gate_review.review_id = gate.review_id
        END AS gate_is_current,
        CASE
            WHEN newest_gate_review IS NULL
            THEN NULL
            ELSE newest_gate_review.review_id
        END AS current_gate_review_id,
        toString(p.updated_at) AS updated_at
    ORDER BY p.factor_label, p.target_label
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
            )
        ]


@st.cache_data(ttl=30)
def load_latest_shield_reviews(
    analysis_id,
    model_run_id,
):
    query = """
    MATCH (review:ShieldReview {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id
    })
    WITH review
    ORDER BY review.reviewed_at DESC
    WITH
        review.proposal_id AS proposal_id,
        collect(review)[0] AS latest
    RETURN
        proposal_id,
        latest.review_id AS review_id,
        latest.human_review_decision AS decision,
        latest.human_review_status AS status,
        latest.amended_shield_label AS amended_shield_label,
        latest.amended_shield_code AS amended_shield_code,
        latest.amended_shield_path AS amended_shield_path,
        latest.reviewer_email AS reviewer_email,
        latest.reviewer_username AS reviewer_username,
        latest.review_comment AS review_comment,
        toString(latest.reviewed_at) AS reviewed_at
    """

    with get_driver().session() as session:
        return {
            record["proposal_id"]: record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
            )
        }


@st.cache_data(ttl=60)
def load_shield_documents():
    query = """
    MATCH (d:ShieldDocument)
    WHERE coalesce(
        d.catalogue_status,
        'AVAILABLE'
    ) = 'AVAILABLE'
    RETURN
        d.shield_document_id AS shield_document_id,
        d.filename AS filename,
        d.source_type AS source_type,
        d.viewer_source_repository AS viewer_source_repository,
        d.viewer_source_path AS viewer_source_path,
        d.viewer_source_filename AS viewer_source_filename,
        d.corpus_snapshot_id AS corpus_snapshot_id
    ORDER BY d.filename
    """

    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(query)
        ]


def save_shield_review(
    proposal,
    *,
    decision,
    amended_label,
    amended_code,
    amended_path,
    comment,
):
    if not proposal.get("gate_is_current"):
        raise ValueError(
            "The Gate-1 relationship review has changed. "
            "Regenerate SHIELD proposals before reviewing this item."
        )

    if proposal.get("assistant_status") != "ASSISTANT_PROPOSED":
        raise ValueError(
            "Only a grounded assistant SHIELD proposal can enter Gate 2 review."
        )

    if decision == "AMENDED" and not str(
        amended_label or ""
    ).strip():
        raise ValueError(
            "Enter an amended SHIELD label."
        )

    reviewer = get_reviewer_identity()
    status_by_decision = {
        "VALIDATED": "HUMAN_VALIDATED",
        "REJECTED": "HUMAN_REJECTED",
        "AMENDED": "HUMAN_AMENDED",
    }

    review_id = (
        "shield_review_"
        + uuid.uuid4().hex
    )

    with get_driver().session() as session:
        record = session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            MATCH (p:ShieldProposal {
                proposal_id: $proposal_id,
                analysis_id: $analysis_id,
                model_run_id: $model_run_id
            })-[:CLASSIFIES_FACTOR]->(
                n:KGNode {
                    node_id: $factor_node_id,
                    analysis_id: $analysis_id,
                    model_run_id: $model_run_id
                }
            )
            MATCH (p)-[:GATED_BY_REVIEW]->(
                gate:RelationshipReview {
                    review_id: $gate_review_id
                }
            )
            CREATE (review:ShieldReview {
                review_id: $review_id,
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                proposal_id: $proposal_id,
                factor_node_id: $factor_node_id,
                factor_label: $factor_label,
                gate_relationship_review_id: $gate_review_id,
                assistant_status: $assistant_status,
                original_shield_label: $original_shield_label,
                original_shield_code: $original_shield_code,
                original_shield_path: $original_shield_path,
                shield_corpus_snapshot_id: $shield_corpus_snapshot_id,
                human_review_decision: $human_review_decision,
                human_review_status: $human_review_status,
                amended_shield_label: $amended_shield_label,
                amended_shield_code: $amended_shield_code,
                amended_shield_path: $amended_shield_path,
                reviewer_email: $reviewer_email,
                reviewer_user_id: $reviewer_user_id,
                reviewer_username: $reviewer_username,
                reviewed_at: datetime(),
                review_comment: $review_comment
            })
            CREATE (a)-[:HAS_SHIELD_REVIEW]->(review)
            CREATE (review)-[:REVIEWS_SHIELD_PROPOSAL]->(p)
            CREATE (review)-[:REVIEWS_SHIELD_OF]->(n)
            CREATE (review)-[:REVIEW_GATE]->(gate)
            RETURN review.review_id AS review_id
            """,
            review_id=review_id,
            analysis_id=proposal["analysis_id"],
            model_run_id=proposal["model_run_id"],
            proposal_id=proposal["proposal_id"],
            factor_node_id=proposal["factor_node_id"],
            factor_label=proposal["factor_label"],
            gate_review_id=proposal["gate_review_id"],
            assistant_status=proposal["assistant_status"],
            original_shield_label=proposal.get(
                "proposed_shield_label"
            ),
            original_shield_code=proposal.get(
                "proposed_shield_code"
            ),
            original_shield_path=proposal.get(
                "proposed_shield_path"
            ),
            shield_corpus_snapshot_id=proposal.get(
                "shield_corpus_snapshot_id"
            ),
            human_review_decision=decision,
            human_review_status=status_by_decision[
                decision
            ],
            amended_shield_label=(
                amended_label.strip()
                if decision == "AMENDED"
                else None
            ),
            amended_shield_code=(
                amended_code.strip()
                if (
                    decision == "AMENDED"
                    and amended_code
                )
                else None
            ),
            amended_shield_path=(
                amended_path.strip()
                if (
                    decision == "AMENDED"
                    and amended_path
                )
                else None
            ),
            reviewer_email=reviewer["email"],
            reviewer_user_id=reviewer["user_id"],
            reviewer_username=reviewer["username"],
            review_comment=comment or None,
        ).single()

    if record is None:
        raise RuntimeError(
            "SHIELD human review was not persisted."
        )

    return record["review_id"]


def trigger_emcip_mapping_job(
    analysis_id,
    model_run_id,
):
    if not EMCIP_MAPPING_JOB_ID:
        raise RuntimeError(
            "No EMCIP mapping proposal Job is attached to the App. "
            "Create notebook 41's Job, attach it with resource key "
            "'emcip_mapping_job', and redeploy."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(
                EMCIP_MAPPING_JOB_ID
            ),
            "job_parameters": {
                "analysis_id": analysis_id,
                "model_run_id": model_run_id,
            },
        },
    )

    run_id = response.get("run_id")
    if not run_id:
        raise RuntimeError(
            "Databricks accepted the EMCIP mapping Job but returned no run_id."
        )

    with get_driver().session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            SET
                a.emcip_mapping_proposal_status = 'QUEUED',
                a.emcip_mapping_proposal_model_run_id = $model_run_id,
                a.emcip_mapping_job_run_id = $job_run_id,
                a.emcip_mapping_proposal_error = NULL,
                a.emcip_mapping_proposal_updated_at = datetime()
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
            job_run_id=str(run_id),
        ).consume()

    return str(run_id)


@st.cache_data(ttl=30)
def load_emcip_mapping_proposals(
    analysis_id,
    model_run_id,
):
    query = """
    MATCH (a:AnalysisGroup {
        analysis_id: $analysis_id
    })-[:HAS_EMCIP_MAPPING_PROPOSAL]->(
        p:EMCIPMappingProposal {
            model_run_id: $model_run_id
        }
    )-[:MAPS_NODE]->(n:KGNode)
    RETURN
        p.proposal_id AS proposal_id,
        p.analysis_id AS analysis_id,
        p.model_run_id AS model_run_id,
        p.node_id AS node_id,
        p.node_label AS node_label,
        p.node_kind AS node_kind,
        p.assistant_mapping_status AS assistant_mapping_status,
        p.proposal_method AS proposal_method,
        p.proposed_entity AS proposed_entity,
        p.proposed_entity_path AS proposed_entity_path,
        p.proposed_attribute_name AS proposed_attribute_name,
        p.proposed_attribute_idcode AS proposed_attribute_idcode,
        p.proposed_code_value AS proposed_code_value,
        p.proposed_code_idcode AS proposed_code_idcode,
        p.candidate_options_json AS candidate_options_json,
        p.rationale AS rationale,
        coalesce(p.evidence_passage_ids, []) AS evidence_passage_ids,
        coalesce(p.evidence_references, []) AS evidence_references,
        coalesce(p.evidence_locations, []) AS evidence_locations,
        coalesce(p.taxonomy_source_document_ids, []) AS taxonomy_source_document_ids,
        coalesce(p.taxonomy_registry_versions, []) AS taxonomy_registry_versions,
        p.mapping_version AS mapping_version,
        p.model_service AS model_service,
        toString(p.updated_at) AS updated_at
    ORDER BY p.node_kind, p.node_label
    """

    with get_driver().session() as session:
        rows = [
            record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
            )
        ]

    for row in rows:
        raw = row.get(
            "candidate_options_json"
        ) or "[]"
        try:
            row["candidate_options"] = json.loads(
                raw
            )
        except Exception:
            row["candidate_options"] = []

    return rows


@st.cache_data(ttl=30)
def load_latest_analysis_mapping_reviews(
    analysis_id,
    model_run_id,
):
    query = """
    MATCH (review:EMCIPMappingReview {
        analysis_id: $analysis_id,
        model_run_id: $model_run_id
    })
    WITH review
    ORDER BY review.reviewed_at DESC
    WITH review.proposal_id AS proposal_id,
         collect(review)[0] AS latest
    RETURN
        proposal_id,
        latest.review_id AS review_id,
        latest.human_review_decision AS decision,
        latest.human_review_status AS status,
        latest.amended_entity_path AS amended_entity_path,
        latest.amended_attribute_name AS amended_attribute_name,
        latest.amended_code_value AS amended_code_value,
        latest.amended_code_idcode AS amended_code_idcode,
        latest.reviewer_email AS reviewer_email,
        latest.reviewer_username AS reviewer_username,
        toString(latest.reviewed_at) AS reviewed_at,
        latest.review_comment AS review_comment
    """

    with get_driver().session() as session:
        return {
            record["proposal_id"]: record.data()
            for record in session.run(
                query,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
            )
        }


def emcip_mapping_text(mapping):
    if (
        not mapping.get("proposed_code_value")
        or not mapping.get("proposed_code_idcode")
    ):
        return "NO_MAPPING"

    parts = [
        mapping.get(
            "proposed_entity_path"
        )
        or mapping.get(
            "proposed_entity"
        )
        or "EMCIP",
        mapping.get(
            "proposed_attribute_name"
        )
        or "",
        mapping.get(
            "proposed_code_value"
        )
        or "",
    ]

    return (
        " → ".join(
            part
            for part in parts
            if part
        )
        + " ["
        + str(
            mapping.get(
                "proposed_code_idcode"
            )
        )
        + "]"
    )


def save_analysis_mapping_review(
    proposal,
    decision,
    amended_candidate,
    comment,
):
    reviewer = get_reviewer_identity()

    status_by_decision = {
        "VALIDATED": "HUMAN_VALIDATED",
        "REJECTED": "HUMAN_REJECTED",
        "AMENDED": "HUMAN_AMENDED",
    }

    review_id = (
        "emcip_review_"
        + uuid.uuid4().hex
    )

    amended_candidate = (
        amended_candidate
        if decision == "AMENDED"
        else None
    )

    with get_driver().session() as session:
        record = session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            MATCH (p:EMCIPMappingProposal {
                proposal_id: $proposal_id,
                analysis_id: $analysis_id,
                model_run_id: $model_run_id
            })-[:MAPS_NODE]->(n:KGNode {
                node_id: $node_id,
                analysis_id: $analysis_id,
                model_run_id: $model_run_id
            })
            CREATE (review:EMCIPMappingReview {
                review_id: $review_id,
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                proposal_id: $proposal_id,
                node_id: $node_id,
                node_label: $node_label,
                node_kind: $node_kind,
                assistant_mapping_status: $assistant_mapping_status,
                original_entity_path: $original_entity_path,
                original_attribute_name: $original_attribute_name,
                original_code_value: $original_code_value,
                original_code_idcode: $original_code_idcode,
                human_review_decision: $human_review_decision,
                human_review_status: $human_review_status,
                amended_entity_path: $amended_entity_path,
                amended_attribute_name: $amended_attribute_name,
                amended_code_value: $amended_code_value,
                amended_code_idcode: $amended_code_idcode,
                reviewer_email: $reviewer_email,
                reviewer_user_id: $reviewer_user_id,
                reviewer_username: $reviewer_username,
                reviewed_at: datetime(),
                review_comment: $review_comment
            })
            CREATE (a)-[:HAS_EMCIP_MAPPING_REVIEW]->(review)
            CREATE (review)-[:REVIEWS_MAPPING_PROPOSAL]->(p)
            CREATE (review)-[:REVIEWS_MAPPING_OF]->(n)
            RETURN review.review_id AS review_id
            """,
            review_id=review_id,
            analysis_id=proposal["analysis_id"],
            model_run_id=proposal["model_run_id"],
            proposal_id=proposal["proposal_id"],
            node_id=proposal["node_id"],
            node_label=proposal["node_label"],
            node_kind=proposal["node_kind"],
            assistant_mapping_status=proposal[
                "assistant_mapping_status"
            ],
            original_entity_path=proposal.get(
                "proposed_entity_path"
            ),
            original_attribute_name=proposal.get(
                "proposed_attribute_name"
            ),
            original_code_value=proposal.get(
                "proposed_code_value"
            ),
            original_code_idcode=proposal.get(
                "proposed_code_idcode"
            ),
            human_review_decision=decision,
            human_review_status=status_by_decision[
                decision
            ],
            amended_entity_path=(
                amended_candidate.get(
                    "entity_path"
                )
                if amended_candidate
                else None
            ),
            amended_attribute_name=(
                amended_candidate.get(
                    "attribute_name"
                )
                if amended_candidate
                else None
            ),
            amended_code_value=(
                amended_candidate.get(
                    "code_value"
                )
                if amended_candidate
                else None
            ),
            amended_code_idcode=(
                amended_candidate.get(
                    "code_idcode"
                )
                if amended_candidate
                else None
            ),
            reviewer_email=reviewer["email"],
            reviewer_user_id=reviewer[
                "user_id"
            ],
            reviewer_username=reviewer[
                "username"
            ],
            review_comment=comment or None,
        ).single()

    if record is None:
        raise RuntimeError(
            "The EMCIP mapping review was not persisted."
        )

    return record["review_id"]


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


# ACTIVE_ANALYSIS_CONTEXT
#
# One analysis is selected once and reused across Analyse Documents,
# Findings & Knowledge, Ask / Compare and Review & Validate.
try:
    active_analysis_rows = load_analysis_groups()
except Exception:
    active_analysis_rows = []

active_analysis_by_id = {
    item["analysis_id"]: item
    for item in active_analysis_rows
}
active_analysis_ids = list(
    active_analysis_by_id
)
active_analysis_id = None
active_analysis = None

if active_analysis_ids:
    pending_active_analysis_id = (
        st.session_state.pop(
            "pending_active_analysis_id",
            None,
        )
    )

    if (
        pending_active_analysis_id
        in active_analysis_by_id
    ):
        st.session_state[
            "active_analysis_id"
        ] = pending_active_analysis_id

    if (
        st.session_state.get(
            "active_analysis_id"
        )
        not in active_analysis_by_id
    ):
        st.session_state[
            "active_analysis_id"
        ] = active_analysis_ids[0]

    with st.sidebar:
        st.markdown("### Active analysis")
        active_analysis_id = st.selectbox(
            "Use this analysis across the App",
            options=active_analysis_ids,
            format_func=lambda value: (
                active_analysis_by_id[value][
                    "analysis_title"
                ]
                + " · Class "
                + str(
                    active_analysis_by_id[
                        value
                    ].get(
                        "information_class"
                    )
                    or "—"
                )
                + " · "
                + str(
                    active_analysis_by_id[
                        value
                    ].get(
                        "status"
                    )
                    or "UNKNOWN"
                )
            ),
            key="active_analysis_id",
        )
        st.caption(
            "Change this once to switch the working case "
            "throughout Analyse, Findings, Ask and Review."
        )

    active_analysis = (
        active_analysis_by_id[
            active_analysis_id
        ]
    )

    with st.container(border=True):
        h1, h2, h3, h4 = st.columns(
            [2.2, 0.8, 0.9, 1.1]
        )
        with h1:
            st.markdown(
                "**Active analysis:** "
                + str(
                    active_analysis.get(
                        "analysis_title"
                    )
                    or active_analysis_id
                )
            )
            st.caption(
                "ID: " + active_analysis_id
            )
        h2.metric(
            "Class",
            active_analysis.get(
                "information_class"
            )
            or "—",
        )
        h3.metric(
            "Sources",
            (
                "Text"
                if active_analysis.get(
                    "input_mode"
                )
                == "DIRECT_TEXT"
                else str(
                    active_analysis.get(
                        "document_count"
                    )
                    or 0
                )
            ),
        )
        h4.metric(
            "Status",
            active_analysis.get(
                "status"
            )
            or "UNKNOWN",
        )
else:
    with st.sidebar:
        st.markdown("### Active analysis")
        st.caption(
            "Create an analysis to establish a shared working case."
        )

(
    tab_home,
    tab_news,
    tab_new_analysis,
    tab_findings,
    tab_knowledge_graph,
    tab_analyses,
    tab_review,
    tab_about,
) = st.tabs(
    [
        "Home",
        "News & Alerts",
        "Analyse Documents",
        "Findings & Evidence",
        "Knowledge Graph",
        "Ask / Compare LLMs",
        "Review & Validate",
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
            "Create an evidence-grounded analysis and inspect the structured outputs: "
            "events, contributing factors, findings, safety issues and recommendations."
        )
        st.caption(
            "Analysis is question-independent. Class B uses MAIRA investigation "
            "material; other classes use the governed IKF source routes."
        )

    with c3:
        st.markdown("### Ask / Compare LLMs")
        st.success("Active PoC")
        st.write(
            "Ask questions about one processed case, one document or selected "
            "documents. Compare model answers only when useful."
        )
        st.caption(
            "Scoped free-text questioning and optional model comparison are "
            "implemented in source, with document/page citations."
        )

    c4, c5, c6 = st.columns(3)

    with c4:
        st.markdown("### Findings & Evidence")
        st.success("Active PoC")
        st.write(
            "Browse extracted findings, relationships and cited source pages; "
            "retrieve deterministic similar MAIRA cases."
        )
        st.caption(
            "Read-only evidence exploration. Human decisions remain in Review & Validate."
        )

    with c5:
        st.markdown("### Knowledge Graph")
        st.success("Active PoC")
        st.write(
            "Explore the analytical graph by document, concept type, relationship "
            "type and layout, and ask questions against the same governed scope."
        )
        st.caption(
            "Diagram controls change the view only; graph knowledge changes require human review."
        )

    with c6:
        st.markdown("### Review & Validate")
        st.success("Active PoC")
        st.write(
            "Make human decisions on relationships, optional assistant correction "
            "proposals, EMCIP mappings and SHIELD classifications."
        )
        st.caption(
            "AI suggestions never become validated knowledge without a human decision."
        )

    st.divider()
    st.markdown("### Current validation milestone")

    m1, m2, m3 = st.columns(3)
    m1.metric("Release preflight", "PASS")
    m2.metric("SHIELD corpus", "Indexed")
    m3.metric("Reference context", "4 sources / 81 passages")

    st.caption(
        "Environment/setup validation is complete with zero warnings and zero "
        "errors. Functional validation now proceeds capability by capability, "
        "starting with a fresh Class-B MAIRA analysis and source-page rendering."
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
        "Prepare and analyse a governed evidence set from indexed documents or "
        "direct text. Questions are asked later in Ask / Compare LLMs so the "
        "evidence structure does not depend on one initial question."
    )

    try:
        source_documents = load_source_documents()
    except Exception as exc:
        source_documents = []
        st.error("The document catalogue could not be loaded from Neo4j.")
        st.exception(exc)

    all_documents_by_id = {
        document["document_id"]: document
        for document in source_documents
    }
    documents_by_id = dict(all_documents_by_id)

    def source_document_label(document_id):
        document = documents_by_id[document_id]
        repository = (
            document.get("source_managed_by")
            or "IKF"
        )
        source_type = document.get("source_type") or "FILE"
        language = (
            document.get("detected_language")
            or "language pending"
        )

        if repository == "MAIRA":
            role = (
                document.get("maira_document_role")
                or "INVESTIGATION"
            )
            title = (
                document.get("report_title")
                or document.get("vessel_name")
                or document.get("filename")
            )
            return (
                f"[MAIRA · {role}] {title} · "
                f"{document['filename']} · {source_type}"
            )

        return (
            f"[IKF] {document['filename']} · "
            f"{source_type} · {language}"
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

    # CLASSIFICATION_DRIVEN_CATALOGUE
    #
    # Source ownership follows the actual project architecture:
    # - Class B (published investigation material) is sourced from MAIRA.
    # - Classes A/C/D use IKF-managed documents only.
    # Direct text remains independent of this catalogue filter.
    if information_class == "B":
        available_documents = [
            document
            for document in source_documents
            if document.get("source_managed_by") == "MAIRA"
        ]
        catalogue_scope_label = "MAIRA published investigation material"
    else:
        available_documents = [
            document
            for document in source_documents
            if document.get("source_managed_by") != "MAIRA"
        ]
        catalogue_scope_label = "IKF document library"

    documents_by_id = {
        document["document_id"]: document
        for document in available_documents
    }

    policy = resolve_model_policy(information_class)

    st.markdown("**Processing disclosure**")
    st.write(policy["description"])
    with st.expander(
        "Technical processing details",
        expanded=False,
    ):
        st.write(
            f"**Model path:** {policy['model_name']}"
        )
        if policy["model"]:
            st.code(
                policy["model"],
                language=None,
            )
        st.caption(
            policy["data_flow"]
        )

    if input_mode == "Documents":
        if information_class == "B":
            st.caption(
                "Document catalogue: Published investigation material is "
                "selected from the MAIRA investigation repository."
            )
        else:
            st.caption(
                "Document catalogue: This information class uses the "
                "IKF-managed document library."
            )

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
                "prepared evidence set. Both produces side-by-side analytical outputs."
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

        analysis_description = st.text_area(
            "Analysis description",
            placeholder=(
                "Optional. Briefly describe the case or evidence set. "
                "This is descriptive metadata only and does not steer extraction."
            ),
        )

        selected_document_ids = []
        direct_text = ""

        if input_mode == "Documents":
            st.caption(
                f"Document source for Class {information_class}: "
                f"{catalogue_scope_label}. "
                f"{len(available_documents)} document(s) available. "
                f"Select 1–{MAX_DOCUMENTS_PER_ANALYSIS}."
            )
            selected_document_ids = st.multiselect(
                "Available documents",
                options=list(documents_by_id),
                format_func=source_document_label,
                max_selections=MAX_DOCUMENTS_PER_ANALYSIS,
                filter_mode="contains",
                help=(
                    "Class B lists MAIRA published investigation material. "
                    "Classes A, C and D list IKF-managed documents only."
                ),
            )
            if not available_documents:
                if information_class == "B":
                    st.warning(
                        "No MAIRA published investigation documents are "
                        "currently available in the catalogue."
                    )
                else:
                    st.warning(
                        "No IKF-managed documents are currently available "
                        "for this information class."
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

        # Early UI pre-screen. Backend notebook 15 repeats the authoritative
        # content check after extraction, so bypassing this UI cannot bypass
        # the fail-closed routing control.
        if (
            information_class != "D"
            and not (
                information_class == "B"
                and input_mode == "Documents"
            )
        ):
            if input_mode == "Direct text":
                prescreen_rule_ids = app_protected_prescreen(
                    text=direct_text,
                )
            else:
                prescreen_metadata_values = []
                for document_id in selected_document_ids:
                    document = documents_by_id.get(
                        document_id,
                        {},
                    )
                    prescreen_metadata_values.extend(
                        [
                            document.get("filename"),
                            document.get("relative_path"),
                            document.get("report_title"),
                        ]
                    )

                prescreen_rule_ids = app_protected_prescreen(
                    metadata_values=prescreen_metadata_values,
                )

            if prescreen_rule_ids:
                try:
                    prescreen_event_id = record_app_prescreen_block(
                        declared_class=information_class,
                        input_mode=(
                            "DIRECT_TEXT"
                            if input_mode == "Direct text"
                            else "DOCUMENTS"
                        ),
                        rule_ids=prescreen_rule_ids,
                        document_ids=(
                            selected_document_ids
                            if input_mode == "Documents"
                            else []
                        ),
                        direct_text=(
                            direct_text
                            if input_mode == "Direct text"
                            else None
                        ),
                    )
                except Exception:
                    prescreen_event_id = None

                errors.append(
                    "Protected-record indicators were detected before "
                    "processing (" + ", ".join(prescreen_rule_ids) + "). "
                    "This input must use Class D or be reviewed before "
                    "continuing."
                    + (
                        f" Audit event: {prescreen_event_id}."
                        if prescreen_event_id
                        else ""
                    )
                )

        if errors:
            for error in errors:
                st.error(error)
        else:
            try:
                if input_mode == "Documents":
                    analysis_id, linked_count = create_analysis_from_documents(
                        title=analysis_title.strip(),
                        description=analysis_description.strip(),
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
                        description=analysis_description.strip(),
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
                st.session_state[
                    "pending_active_analysis_id"
                ] = analysis_id

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
                    "Stay in Analyse Documents and use Refresh status above to "
                    "follow the four processing stages through to the structured outputs."
                )

            except Exception as exc:
                st.error("The analysis could not be created or started.")
                st.exception(exc)

    st.divider()
    st.markdown("### Active analysis status")

    if active_analysis_id and active_analysis:
        refresh_col, status_col = st.columns(
            [0.8, 3.2]
        )
        with refresh_col:
            if st.button(
                "Refresh status",
                key="refresh_analyse_status",
                use_container_width=True,
            ):
                load_analysis_groups.clear()
                load_recent_analyses.clear()
                load_analysis_evidence_counts.clear()
                load_analysis_result.clear()
                load_analysis_graph_counts.clear()
                load_model_runs.clear()
                load_model_run_graph.clear()
                st.rerun()

        with status_col:
            st.caption(
                "Tracking: "
                + str(
                    active_analysis.get(
                        "analysis_title"
                    )
                    or active_analysis_id
                )
            )

        active_evidence_counts = (
            load_analysis_evidence_counts(
                active_analysis_id
            )
        )
        active_result_meta = (
            load_analysis_result(
                active_analysis_id
            )
        )

        render_pipeline_status(
            status=active_analysis.get(
                "status"
            ),
            processing_stage=active_analysis.get(
                "processing_stage"
            ),
            evidence_counts=active_evidence_counts,
            result_meta=active_result_meta,
        )
    else:
        st.info(
            "Create an analysis to follow the four processing stages."
        )

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


    st.divider()
    st.markdown("### Analysis results")
    st.caption(
        "See what the analysis identified before asking any questions. "
        "These are model-derived analytical outputs with source provenance; "
        "relationships remain candidates until human review."
    )

    try:
        result_analyses = load_analysis_groups()
    except Exception as exc:
        result_analyses = []
        st.error(
            "Analysis results could not be loaded."
        )
        st.exception(exc)

    if result_analyses:
        result_by_id = {
            item["analysis_id"]: item
            for item in result_analyses
        }

        result_analysis_id = (
            active_analysis_id
            if active_analysis_id
            in result_by_id
            else list(result_by_id)[0]
        )
        result_meta = result_by_id[
            result_analysis_id
        ]
        st.caption(
            "Using active analysis: "
            + str(
                result_meta.get(
                    "analysis_title"
                )
                or result_analysis_id
            )
        )

        if result_meta.get("status") != "COMPLETED":
            st.info(
                "Structured results become available after processing "
                "completes. Use Refresh status above to update the four-stage view."
            )
        else:
            completed_model_runs = [
                item
                for item in load_model_runs(
                    result_analysis_id
                )
                if item.get("status") == "COMPLETED"
            ]

            if len(completed_model_runs) > 1:
                result_model_by_id = {
                    item["model_run_id"]: item
                    for item in completed_model_runs
                }
                result_model_run_id = st.selectbox(
                    "Model output",
                    options=list(
                        result_model_by_id
                    ),
                    format_func=lambda value: (
                        result_model_by_id[value].get(
                            "model_label"
                        )
                        or result_model_by_id[value].get(
                            "model_key"
                        )
                        or value
                    ),
                    key=(
                        "analyse_result_model_"
                        + result_analysis_id
                    ),
                )
                result_graph = load_model_run_graph(
                    result_analysis_id,
                    result_model_run_id,
                )
            elif len(completed_model_runs) == 1:
                result_graph = load_model_run_graph(
                    result_analysis_id,
                    completed_model_runs[0][
                        "model_run_id"
                    ],
                )
            else:
                result_graph = load_analysis_graph(
                    result_analysis_id
                )

            result_nodes = result_graph[
                "nodes"
            ]
            result_edges = result_graph[
                "edges"
            ]

            nodes_by_kind = {}
            for node in result_nodes:
                nodes_by_kind.setdefault(
                    node.get("node_kind")
                    or "Other",
                    [],
                ).append(node)

            event_nodes = nodes_by_kind.get(
                "Event",
                [],
            )
            contributing_nodes = nodes_by_kind.get(
                "ContributingFactor",
                [],
            )
            finding_nodes = nodes_by_kind.get(
                "Finding",
                [],
            )
            safety_issue_nodes = nodes_by_kind.get(
                "SafetyIssue",
                [],
            )
            recommendation_nodes = nodes_by_kind.get(
                "Recommendation",
                [],
            )

            result_metrics = st.columns(5)
            result_metrics[0].metric(
                "Events",
                len(event_nodes),
            )
            result_metrics[1].metric(
                "Contributing factors",
                len(contributing_nodes),
            )
            result_metrics[2].metric(
                "Findings",
                len(finding_nodes),
            )
            result_metrics[3].metric(
                "Safety issues",
                len(safety_issue_nodes),
            )
            result_metrics[4].metric(
                "Recommendations",
                len(recommendation_nodes),
            )

            result_category = st.radio(
                "Show results",
                options=[
                    "All",
                    "Events",
                    "Contributing factors",
                    "Findings",
                    "Safety issues",
                    "Recommendations",
                    "Relationships",
                ],
                horizontal=True,
                key=(
                    "analyse_result_category_"
                    + result_analysis_id
                ),
            )

            try:
                result_relationship_reviews = (
                    load_latest_relationship_reviews(
                        result_analysis_id
                    )
                )
            except Exception:
                result_relationship_reviews = {}

            node_kind_by_id = {
                node["node_id"]: (
                    node.get("node_kind")
                    or "Other"
                )
                for node in result_nodes
            }

            validated_contributing_factor_ids = set()

            for edge in result_edges:
                if (
                    edge.get("relationship")
                    != "CONTRIBUTED_TO"
                    or node_kind_by_id.get(
                        edge.get("source_id")
                    )
                    != "ContributingFactor"
                ):
                    continue

                review = (
                    result_relationship_reviews.get(
                        edge.get("edge_id")
                    )
                )

                if not review:
                    continue

                if (
                    review.get("decision")
                    == "VALIDATED"
                ):
                    validated_contributing_factor_ids.add(
                        edge.get("source_id")
                    )
                elif (
                    review.get("decision")
                    == "AMENDED"
                    and review.get(
                        "amended_relationship"
                    )
                    == "CONTRIBUTED_TO"
                ):
                    validated_contributing_factor_ids.add(
                        edge.get("source_id")
                    )

            def render_result_group(
                title,
                items,
                empty_text,
            ):
                st.markdown(
                    "#### " + title
                )
                if not items:
                    st.caption(
                        empty_text
                    )
                    return

                for item in items:
                    with st.expander(
                        item.get("label")
                        or "Unnamed item",
                        expanded=False,
                    ):
                        item_left, item_right = (
                            st.columns(
                                [1.25, 1.0]
                            )
                        )

                        with item_left:
                            if (
                                item.get(
                                    "node_kind"
                                )
                                == "ContributingFactor"
                                and item.get(
                                    "node_id"
                                )
                                in (
                                    validated_contributing_factor_ids
                                )
                            ):
                                st.success(
                                    "Human validated: contributing "
                                    "relationship confirmed."
                                )
                            else:
                                st.caption(
                                    "Status: AI identified / candidate"
                                )

                            st.write(
                                item.get(
                                    "description"
                                )
                                or "No description was published."
                            )

                        with item_right:
                            references = (
                                item.get(
                                    "evidence_references"
                                )
                                or []
                            )

                            st.markdown(
                                "**Investigation evidence**"
                            )

                            if references:
                                for reference in references:
                                    st.write(
                                        "• "
                                        + str(reference)
                                    )
                            else:
                                st.caption(
                                    "No page-level citation is available "
                                    "for this item."
                                )

            if result_category in {
                "All",
                "Events",
            }:
                render_result_group(
                    "Events / casualty sequence",
                    event_nodes,
                    "No Event nodes were identified.",
                )

            if result_category in {
                "All",
                "Contributing factors",
            }:
                render_result_group(
                    "Contributing factors",
                    contributing_nodes,
                    "No ContributingFactor nodes were identified.",
                )

            if result_category in {
                "All",
                "Findings",
            }:
                render_result_group(
                    "Findings",
                    finding_nodes,
                    "No Finding nodes were identified.",
                )

            if result_category in {
                "All",
                "Safety issues",
            }:
                render_result_group(
                    "Safety issues",
                    safety_issue_nodes,
                    "No SafetyIssue nodes were identified.",
                )

            if result_category in {
                "All",
                "Recommendations",
            }:
                render_result_group(
                    "Safety recommendations",
                    recommendation_nodes,
                    "No Recommendation nodes were identified.",
                )

            analytical_relationships = [
                edge
                for edge in result_edges
                if (
                    edge.get("edge_class")
                    != "STRUCTURAL"
                    and edge.get("relationship")
                    in {
                        "FOLLOWED_BY",
                        "CONTRIBUTED_TO",
                        "RESULTED_IN",
                        "AFFECTED",
                        "SUPPORTS",
                    }
                )
            ]

            if result_category in {
                "All",
                "Relationships",
            }:
                st.markdown(
                    "#### Analytical relationships"
                    )
                st.caption(
                    "These relationships describe sequence/support/contribution "
                    "as extracted from the report. They are not authoritative "
                    "until reviewed where human validation is required."
                )

                if analytical_relationships:
                    for edge in analytical_relationships:
                        st.write(
                            "• "
                            + edge["source_label"]
                            + " — "
                            + edge["relationship"]
                            + " → "
                            + edge["target_label"]
                        )
                        for reference in (
                            edge.get(
                                "evidence_references"
                            )
                            or []
                        ):
                            st.caption(
                                str(reference)
                            )
                else:
                    st.caption(
                        "No evidence-derived analytical relationships were published."
                    )

            st.info(
                "Use Findings & Knowledge for detailed evidence browsing and "
                "the graph. Use Review & Validate for human decisions. Use "
                "Ask / Compare LLMs only when you want to pose a question."
            )
    else:
        st.info(
            "No analyses are available yet."
        )

@st.fragment
def render_compare_llms():
    st.subheader("Ask / Compare LLMs")
    st.caption(
        "Use an already processed evidence set. Ask about the whole case, one "
        "document or selected documents; compare models only when needed."
    )

    st.info(
        "Questions are separate from document analysis. Select a processed "
        "evidence set, choose the scope, ask in free text, and receive an "
        "answer with document/page citations. Model comparison is optional "
        "where the information-class policy allows it."
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
        load_question_runs.clear()
        load_question_model_runs.clear()
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

        selected_analysis_id = (
            active_analysis_id
            if active_analysis_id
            in analyses_by_id
            else list(analyses_by_id)[0]
        )

        selected_analysis = analyses_by_id[
            selected_analysis_id
        ]
        st.caption(
            "Using active analysis: "
            + analysis_label(
                selected_analysis_id
            )
        )

        st.markdown("### Ask this evidence set")

        if selected_analysis.get("status") != "COMPLETED":
            st.info(
                "Questioning is enabled after the selected evidence set has "
                "completed processing."
            )
        else:
            ask_sources = load_analysis_sources(
                selected_analysis_id
            )
            ask_source_by_id = {
                source["document_id"]: source
                for source in ask_sources
            }

            input_mode_value_for_ask = (
                selected_analysis.get("input_mode")
                or "DOCUMENTS"
            )
            class_for_ask = (
                selected_analysis.get("information_class")
                or "B"
            )

            if input_mode_value_for_ask == "DIRECT_TEXT":
                scope_label = "Entire evidence set"
                scope_mode = "WHOLE_CASE"
                scope_document_ids = []
            else:
                scope_options = {
                    "Entire case / analysis": "WHOLE_CASE",
                    "One document": "ONE_DOCUMENT",
                    "Selected documents": "SELECTED_DOCUMENTS",
                }
                scope_label = st.radio(
                    "Evidence scope",
                    options=list(scope_options),
                    horizontal=True,
                    key=(
                        "ask_scope_"
                        + selected_analysis_id
                    ),
                )
                scope_mode = scope_options[
                    scope_label
                ]

                def ask_source_label(document_id):
                    source = ask_source_by_id[
                        document_id
                    ]
                    repository = (
                        source.get(
                            "viewer_source_repository"
                        )
                        or "IKF"
                    )
                    return (
                        f"[{repository}] "
                        f"{source.get('viewer_source_filename') or source.get('filename')}"
                    )

                if scope_mode == "ONE_DOCUMENT":
                    one_document_id = st.selectbox(
                        "Use this document for the question",
                        options=list(
                            ask_source_by_id
                        ),
                        format_func=ask_source_label,
                        key=(
                            "ask_one_document_"
                            + selected_analysis_id
                        ),
                    )
                    scope_document_ids = (
                        [one_document_id]
                        if one_document_id
                        else []
                    )
                elif scope_mode == "SELECTED_DOCUMENTS":
                    scope_document_ids = st.multiselect(
                        "Use these documents for the question",
                        options=list(
                            ask_source_by_id
                        ),
                        format_func=ask_source_label,
                        max_selections=MAX_DOCUMENTS_PER_ANALYSIS,
                        filter_mode="contains",
                        key=(
                            "ask_selected_documents_"
                            + selected_analysis_id
                        ),
                    )
                else:
                    scope_document_ids = []

            if class_for_ask == "D":
                ask_model_label = st.radio(
                    "Model mode",
                    options=list(
                        CLASS_D_MODEL_OPTIONS
                    ),
                    horizontal=True,
                    key=(
                        "ask_model_mode_"
                        + selected_analysis_id
                    ),
                    help=(
                        "Protected/Class D questions use only the dedicated "
                        "approved model routes. Both models receive exactly "
                        "the same scoped evidence and question."
                    ),
                )
                ask_model_selection = (
                    CLASS_D_MODEL_OPTIONS[
                        ask_model_label
                    ]
                )

                if ask_model_selection in {
                    "LLAMA70",
                    "BOTH",
                }:
                    llama_used = get_llama_daily_usage()
                    llama_remaining = max(
                        LLAMA_DAILY_QUESTION_LIMIT
                        - llama_used,
                        0,
                    )
                    st.caption(
                        "Llama 3.3 70B questions remaining today: "
                        f"{llama_remaining}"
                    )
            else:
                ask_model_selection = "DEFAULT"
                ask_policy = resolve_model_policy(
                    class_for_ask
                )
                with st.expander(
                    "Technical model details",
                    expanded=False,
                ):
                    st.caption(
                        "Model route: "
                        + (
                            ask_policy.get("model_name")
                            or ask_policy.get("model")
                            or "default class model"
                        )
                    )

            available_reference_documents = load_reference_documents()

            include_reference_context = st.checkbox(
                "Include legal / IMO / technical references",
                value=False,
                disabled=not bool(
                    available_reference_documents
                ),
                help=(
                    "Adds governed legal, IMO and technical material separately "
                    "from investigation evidence. It may support context or "
                    "interpretation but cannot prove what happened in the occurrence."
                ),
                key=(
                    "ask_reference_context_"
                    + selected_analysis_id
                ),
            )

            if include_reference_context:
                reference_families = sorted(
                    {
                        item.get("reference_family")
                        or "TECHNICAL_REFERENCE"
                        for item in available_reference_documents
                    }
                )
                st.caption(
                    "Reference material available: "
                    + ", ".join(reference_families)
                )
            elif not available_reference_documents:
                st.caption(
                    "No governed legal / IMO / technical reference material "
                    "is currently available."
                )

            if scope_mode == "WHOLE_CASE":
                ask_scope_summary = (
                    "Entire prepared case / analysis"
                )
            elif (
                scope_mode == "ONE_DOCUMENT"
                and scope_document_ids
            ):
                ask_scope_summary = (
                    ask_source_label(
                        scope_document_ids[0]
                    )
                )
            elif scope_mode == "SELECTED_DOCUMENTS":
                ask_scope_summary = (
                    str(
                        len(scope_document_ids)
                    )
                    + " selected document(s)"
                )
            else:
                ask_scope_summary = (
                    "No document selected"
                )

            if include_reference_context:
                ask_scope_summary += (
                    " + legal / IMO / technical references"
                )

            st.info(
                "Question scope: "
                + ask_scope_summary
            )

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

            if ask_submitted:
                ask_errors = []

                if not ask_question_text.strip():
                    ask_errors.append(
                        "Enter a question."
                    )

                if (
                    scope_mode
                    == "SELECTED_DOCUMENTS"
                    and not scope_document_ids
                ):
                    ask_errors.append(
                        "Select at least one document."
                    )

                if class_for_ask == "D":
                    if (
                        ask_model_selection
                        in {"LLAMA70", "BOTH"}
                        and get_llama_daily_usage()
                        >= LLAMA_DAILY_QUESTION_LIMIT
                    ):
                        ask_errors.append(
                            "The daily Llama 3.3 70B question limit has been reached."
                        )

                if not ASK_JOB_ID:
                    ask_errors.append(
                        "The Ask Job has not yet been attached to this App deployment."
                    )

                if ask_errors:
                    for error in ask_errors:
                        st.error(error)
                else:
                    question_run_id = None
                    try:
                        question_run_id = create_question_run(
                            analysis=selected_analysis,
                            question_text=ask_question_text.strip(),
                            scope_mode=scope_mode,
                            scope_document_ids=scope_document_ids,
                            model_selection=ask_model_selection,
                            include_reference_context=include_reference_context,
                        )

                        if (
                            class_for_ask == "D"
                            and ask_model_selection
                            in {"LLAMA70", "BOTH"}
                        ):
                            consumed = consume_llama_daily_usage()
                            if consumed is None:
                                raise RuntimeError(
                                    "The Llama daily quota could not be reserved."
                                )

                        run_id = trigger_question_job(
                            question_run_id
                        )

                        load_question_runs.clear()
                        load_question_model_runs.clear()

                        st.success(
                            "Question queued."
                        )
                        st.caption(
                            f"Question run: {question_run_id} · "
                            f"Databricks run: {run_id}"
                        )

                    except Exception as exc:
                        if question_run_id:
                            with get_driver().session() as session:
                                session.run(
                                    """
                                    MATCH (q:QuestionRun {
                                        question_run_id: $question_run_id
                                    })
                                    SET
                                        q.status = 'FAILED',
                                        q.processing_stage = 'JOB_TRIGGER_FAILED',
                                        q.processing_error = $error_message,
                                        q.updated_at = datetime()
                                    """,
                                    question_run_id=question_run_id,
                                    error_message=(
                                        f"{type(exc).__name__}: {exc}"
                                    ),
                                ).consume()
                        st.error(
                            "The question could not be queued."
                        )
                        st.exception(exc)

            question_runs = [
                item
                for item in load_question_runs(
                    selected_analysis_id
                )
                if (
                    item.get(
                        "interaction_surface"
                    )
                    in {
                        None,
                        "",
                        "ASK_COMPARE",
                    }
                )
            ]

            if question_runs:
                st.markdown("### Question history")

                question_by_id = {
                    item["question_run_id"]: item
                    for item in question_runs
                }

                selected_question_run_id = st.selectbox(
                    "Question run",
                    options=list(question_by_id),
                    format_func=lambda value: (
                        question_display_text(
                            question_by_id[value]
                        )[:100]
                        + " · "
                        + (
                            question_by_id[value].get(
                                "status"
                            )
                            or "UNKNOWN"
                        )
                    ),
                    key=(
                        "question_history_"
                        + selected_analysis_id
                    ),
                )

                selected_question = question_by_id[
                    selected_question_run_id
                ]

                st.markdown("**Question**")
                st.write(
                    question_display_text(
                        selected_question
                    )
                )
                st.caption(
                    "Scope: "
                    + (
                        selected_question.get(
                            "scope_mode"
                        )
                        or "WHOLE_CASE"
                    )
                    + " · Status: "
                    + (
                        selected_question.get(
                            "status"
                        )
                        or "UNKNOWN"
                    )
                )

                retrieval_mode = (
                    selected_question.get(
                        "retrieval_mode"
                    )
                    or "SCOPED_ALL_PASSAGES"
                )

                st.caption(
                    "Reference context: "
                    + (
                        "included"
                        if selected_question.get(
                            "include_reference_context"
                        )
                        else "not included"
                    )
                )

                if retrieval_mode == "GOVERNED_RELATIONSHIP_EVIDENCE":
                    st.caption(
                        "Retrieval: governed MAIRA relationship evidence"
                        + (
                            " · "
                            + selected_question["governed_query_id"]
                            if selected_question.get("governed_query_id")
                            else ""
                        )
                    )
                elif retrieval_mode == "DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1":
                    st.caption(
                        "Retrieval: deterministic free-text lexical ranking"
                        + (
                            " · "
                            + str(
                                selected_question.get(
                                    "retrieval_selected_count"
                                )
                                or len(
                                    selected_question.get(
                                        "retrieval_passage_ids"
                                    )
                                    or []
                                )
                            )
                            + " passage(s)"
                        )
                    )
                    expansions = (
                        selected_question.get(
                            "retrieval_activated_expansions"
                        )
                        or []
                    )
                    if expansions:
                        st.caption(
                            "Governed terminology expansions: "
                            + " · ".join(expansions)
                        )
                else:
                    st.caption(
                        "Retrieval: complete selected evidence scope "
                        "(small-scope all-passages path)."
                    )

                if selected_question.get(
                    "retrieval_snapshot_id"
                ):
                    with st.expander(
                        "Retrieval provenance",
                        expanded=False,
                    ):
                        st.code(
                            selected_question[
                                "retrieval_snapshot_id"
                            ],
                            language=None,
                        )
                        if selected_question.get(
                            "retrieval_query_terms"
                        ):
                            st.write(
                                "Query terms: "
                                + ", ".join(
                                    selected_question[
                                        "retrieval_query_terms"
                                    ]
                                )
                            )

                question_status = (
                    selected_question.get("status")
                    or "UNKNOWN"
                )

                if question_status in {
                    "PENDING",
                    "QUEUED",
                    "RUNNING",
                }:
                    st.info(
                        "The question is being processed. Use Refresh status "
                        "to update this view."
                    )
                elif question_status == "FAILED":
                    st.error(
                        selected_question.get(
                            "processing_error"
                        )
                        or "Question processing failed."
                    )
                elif question_status == "COMPLETED":
                    deterministic_answer = (
                        selected_question.get(
                            "deterministic_answer"
                        )
                    )

                    if deterministic_answer:
                        st.warning(
                            deterministic_answer
                        )

                    answer_runs = load_question_model_runs(
                        selected_question_run_id
                    )

                    if len(answer_runs) == 1:
                        render_question_answer(
                            analysis_id=selected_analysis_id,
                            question_run=selected_question,
                            model_run=answer_runs[0],
                            render_key=answer_runs[0]["model_key"],
                        )
                    elif answer_runs:
                        st.markdown(
                            "### Model comparison"
                        )
                        st.caption(
                            "Same question and same scoped evidence were used "
                            "for each model."
                        )
                        answer_columns = st.columns(
                            len(answer_runs)
                        )
                        for answer_column, answer_run in zip(
                            answer_columns,
                            answer_runs,
                        ):
                            with answer_column:
                                render_question_answer(
                                    analysis_id=selected_analysis_id,
                                    question_run=selected_question,
                                    model_run=answer_run,
                                    render_key=answer_run["model_key"],
                                )



with tab_analyses:
    render_compare_llms()

with tab_findings:
    st.subheader("Findings & Evidence")
    st.caption(
        "Browse processed findings and their evidence. Open the graph when "
        "relationships help, and retrieve similar MAIRA cases. Questions are "
        "asked in Ask / Compare LLMs; validation decisions are made in Review & Validate."
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
        knowledge_analysis_id = (
            active_analysis_id
            if active_analysis_id
            in knowledge_by_id
            else list(knowledge_by_id)[0]
        )
        st.caption(
            "Using active analysis: "
            + str(
                knowledge_by_id[
                    knowledge_analysis_id
                ].get(
                    "analysis_title"
                )
                or knowledge_analysis_id
            )
        )
        knowledge_graph = load_analysis_graph(
            knowledge_analysis_id
        )

        knowledge_meta = knowledge_by_id[
            knowledge_analysis_id
        ]

        st.info(
            "Free-text questions and model comparison are handled in "
            "Ask / Compare LLMs. This page is intentionally read-only: "
            "browse the extracted knowledge, inspect investigation evidence, view "
            "relationships and retrieve similar MAIRA cases."
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
                        "evidence_references": node.get(
                            "evidence_references"
                        ) or [],
                        "evidence_locations": node.get(
                            "evidence_locations"
                        ) or [],
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
                        "evidence_references": edge.get(
                            "evidence_references"
                        ) or [],
                        "evidence_locations": edge.get(
                            "evidence_locations"
                        ) or [],
                    }
                }
                for edge in knowledge_graph["edges"]
            ],
        }

        if knowledge_elements["nodes"]:
            st.markdown("### Evidence sheet")
            st.caption(
                "Select a finding, event, concept or relationship to inspect "
                "its evidence and source page. This page does not change "
                "the graph or create model answers."
            )

            evidence_items = []
            knowledge_result = load_analysis_result(
                knowledge_analysis_id
            )
            knowledge_meta = knowledge_by_id[
                knowledge_analysis_id
            ]

            for node in knowledge_graph["nodes"]:
                evidence_items.append(
                    {
                        "kind": "Node",
                        "label": (
                            f"{node['node_kind']}: {node['label']}"
                        ),
                        "description": (
                            node.get("description")
                            or "No description was published."
                        ),
                        "references": (
                            node.get("evidence_references")
                            or []
                        ),
                        "locations": (
                            node.get("evidence_locations")
                            or []
                        ),
                        "passage_ids": (
                            node.get("passage_ids")
                            or []
                        ),
                    }
                )

            for edge in knowledge_graph["edges"]:
                evidence_items.append(
                    {
                        "kind": "Relationship",
                        "label": (
                            f"{edge['source_label']} — "
                            f"{edge['relationship']} → "
                            f"{edge['target_label']}"
                        ),
                        "description": (
                            "Relationship proposed from the referenced "
                            "source evidence."
                        ),
                        "references": (
                            edge.get("evidence_references")
                            or []
                        ),
                        "locations": (
                            edge.get("evidence_locations")
                            or []
                        ),
                        "passage_ids": (
                            edge.get("passage_ids")
                            or []
                        ),
                    }
                )

            selected_evidence_index = st.selectbox(
                "Answer / finding / relationship",
                options=list(range(len(evidence_items))),
                format_func=lambda index: evidence_items[index]["label"],
                key="knowledge_evidence_selector",
            )

            selected_evidence = evidence_items[
                selected_evidence_index
            ]

            evidence_left, evidence_right = st.columns(
                [1.0, 1.2]
            )

            with evidence_left:
                st.markdown("**Description**")
                st.write(selected_evidence["description"])

                st.markdown("**Source reference**")
                if selected_evidence["references"]:
                    for reference in selected_evidence["references"]:
                        st.write(f"• {reference}")
                else:
                    st.write(
                        "No page-level source reference is available for "
                        "this item in an older analysis."
                    )

                with st.expander("Technical evidence IDs"):
                    for passage_id in selected_evidence["passage_ids"]:
                        st.code(passage_id, language=None)

            with evidence_right:
                st.markdown("**Source document**")

                parsed_locations = [
                    parsed
                    for parsed in (
                        parse_evidence_location(value)
                        for value in selected_evidence["locations"]
                    )
                    if parsed is not None
                ]

                analysis_sources = load_analysis_sources(
                    knowledge_analysis_id
                )
                source_by_id = {
                    source["document_id"]: source
                    for source in analysis_sources
                }

                if not parsed_locations:
                    st.info(
                        "No source-page location is available for this "
                        "item. Analyses created with the newer citation-enabled "
                        "pipeline include viewer locations and page references."
                    )
                else:
                    location_index = st.selectbox(
                        "Evidence page",
                        options=list(range(len(parsed_locations))),
                        format_func=lambda index: format_evidence_location(
                            parsed_locations[index],
                            source_by_id.get(
                                parsed_locations[index]["document_id"]
                            ),
                        ),
                        key=(
                            "knowledge_source_page_"
                            + str(selected_evidence_index)
                        ),
                    )

                    location = parsed_locations[
                        location_index
                    ]
                    source = source_by_id.get(
                        location["document_id"]
                    )

                    if source is None:
                        st.warning(
                            "The evidence reference exists, but its source "
                            "document is not linked to this analysis."
                        )
                    else:
                        source_path = source.get(
                            "viewer_source_path"
                        )
                        source_type = str(
                            source.get("source_type") or ""
                        ).upper()

                        if source_type != "PDF":
                            st.info(
                                "The source reference is available, but the "
                                "embedded viewer currently supports PDF "
                                "documents only."
                            )
                        elif not source_path:
                            st.warning(
                                "No governed source-document path is "
                                "registered for this evidence."
                            )
                        else:
                            try:
                                pdf_bytes = download_source_file_as_user(
                                    source_path
                                )
                                excerpt_bytes = pdf_page_range_bytes(
                                    pdf_bytes,
                                    location.get("page_start"),
                                    location.get("page_end"),
                                )

                                st.caption(
                                    format_evidence_location(
                                        location,
                                        source,
                                    )
                                )
                                st.pdf(
                                    excerpt_bytes,
                                    height=720,
                                    key=(
                                        "evidence_pdf_"
                                        + hashlib.sha256(
                                            (
                                                source_path
                                                + "|"
                                                + str(location.get("page_start"))
                                                + "|"
                                                + str(location.get("page_end"))
                                            ).encode("utf-8")
                                        ).hexdigest()[:16]
                                    ),
                                )

                                with st.expander(
                                    "View full source report",
                                    expanded=False,
                                ):
                                    st.pdf(
                                        pdf_bytes,
                                        height=800,
                                        key=(
                                            "full_pdf_"
                                            + hashlib.sha256(
                                                source_path.encode("utf-8")
                                            ).hexdigest()[:16]
                                        ),
                                    )

                            except PermissionError as exc:
                                st.warning(str(exc))
                                st.caption(
                                    "The viewer uses your Databricks user "
                                    "authorization, so Unity Catalog access "
                                    "is not bypassed."
                                )
                            except FileNotFoundError as exc:
                                st.warning(str(exc))
                            except Exception as exc:
                                st.error(
                                    "The source document could not be "
                                    "rendered."
                                )
                                st.caption(str(exc))

            st.info(
                "Relationship validation and optional assistant correction "
                "checks are handled in Review & Validate."
            )

        else:
            st.info("This analysis does not yet contain a published graph.")
    else:
        st.info("No existing analyses are available yet.")

    st.markdown("### Similar cases")
    similar_left, similar_right = st.columns(2)

    with similar_left:
        st.markdown("**MAIRA investigation reports**")
        st.caption(
            "Deterministic lexical retrieval from processed case concepts. "
            "No embedding or LLM similarity score is used."
        )

        if (
            knowledge_analyses
            and knowledge_meta.get("status")
            == "COMPLETED"
        ):
            if st.button(
                "Find similar MAIRA cases",
                key=(
                    "find_similar_cases_"
                    + knowledge_analysis_id
                ),
                disabled=(
                    not SIMILAR_CASES_JOB_ID
                ),
            ):
                try:
                    similar_job_run_id = (
                        trigger_similar_cases_job(
                            knowledge_analysis_id
                        )
                    )
                    load_similar_case_candidates.clear()
                    st.success(
                        "Similar-case retrieval queued."
                    )
                    st.caption(
                        "Databricks run: "
                        + similar_job_run_id
                    )
                except Exception as exc:
                    st.error(
                        "Similar-case retrieval could not be queued."
                    )
                    st.exception(exc)

            if not SIMILAR_CASES_JOB_ID:
                st.caption(
                    "Similar MAIRA Cases Job is not attached to this "
                    "App deployment yet."
                )

            similar_candidates = (
                load_similar_case_candidates(
                    knowledge_analysis_id
                )
            )

            if similar_candidates:
                global_source_by_id = {
                    source[
                        "document_id"
                    ]: source
                    for source in load_source_documents()
                }

                st.caption(
                    "Retrieval: "
                    + (
                        similar_candidates[0].get(
                            "retrieval_method"
                        )
                        or "deterministic"
                    )
                )

                for candidate in similar_candidates:
                    candidate_title = (
                        candidate.get(
                            "report_title"
                        )
                        or candidate.get(
                            "vessel_name"
                        )
                        or candidate.get(
                            "source_filename"
                        )
                        or candidate[
                            "report_package_id"
                        ]
                    )

                    with st.expander(
                        (
                            f"#{candidate.get('rank') or '—'} · "
                            + candidate_title
                        ),
                        expanded=(
                            candidate.get(
                                "rank"
                            )
                            == 1
                        ),
                    ):
                        matched_terms = (
                            candidate.get(
                                "matched_query_terms"
                            )
                            or []
                        )

                        if matched_terms:
                            st.markdown(
                                "**Why this matched**"
                            )
                            st.write(
                                ", ".join(
                                    matched_terms
                                )
                            )

                        if candidate.get(
                            "publication_date"
                        ):
                            st.caption(
                                "Publication: "
                                + str(
                                    candidate[
                                        "publication_date"
                                    ]
                                )
                            )

                        references = (
                            candidate.get(
                                "evidence_references"
                            )
                            or []
                        )

                        if references:
                            st.markdown(
                                "**Matched source pages**"
                            )
                            for reference in references:
                                st.write(
                                    f"• {reference}"
                                )

                        locations = [
                            parsed
                            for parsed in (
                                parse_evidence_location(
                                    value
                                )
                                for value in (
                                    candidate.get(
                                        "evidence_locations"
                                    )
                                    or []
                                )
                            )
                            if parsed is not None
                        ]

                        if locations:
                            similar_location_index = (
                                st.selectbox(
                                    "Matched page",
                                    options=list(
                                        range(
                                            len(
                                                locations
                                            )
                                        )
                                    ),
                                    format_func=lambda index: (
                                        format_evidence_location(
                                            locations[
                                                index
                                            ],
                                            global_source_by_id.get(
                                                locations[
                                                    index
                                                ][
                                                    "document_id"
                                                ]
                                            ),
                                        )
                                    ),
                                    key=(
                                        "similar_case_page_"
                                        + candidate[
                                            "candidate_id"
                                        ]
                                    ),
                                )
                            )

                            similar_location = (
                                locations[
                                    similar_location_index
                                ]
                            )
                            similar_source = (
                                global_source_by_id.get(
                                    similar_location[
                                        "document_id"
                                    ]
                                )
                            )

                            if (
                                similar_source
                                and str(
                                    similar_source.get(
                                        "source_type"
                                    )
                                    or ""
                                ).upper()
                                == "PDF"
                                and similar_source.get(
                                    "viewer_source_path"
                                )
                            ):
                                try:
                                    similar_pdf_bytes = (
                                        download_source_file_as_user(
                                            similar_source[
                                                "viewer_source_path"
                                            ]
                                        )
                                    )
                                    similar_excerpt = (
                                        pdf_page_range_bytes(
                                            similar_pdf_bytes,
                                            similar_location.get(
                                                "page_start"
                                            ),
                                            similar_location.get(
                                                "page_end"
                                            ),
                                        )
                                    )
                                    st.pdf(
                                        similar_excerpt,
                                        height=520,
                                        key=(
                                            "similar_case_pdf_"
                                            + candidate[
                                                "candidate_id"
                                            ]
                                        ),
                                    )
                                except PermissionError as exc:
                                    st.warning(
                                        str(exc)
                                    )
                                except Exception as exc:
                                    st.caption(
                                        "Matched page could not be rendered: "
                                        + str(exc)
                                    )
            else:
                st.info(
                    "No similar-case retrieval result is stored yet for "
                    "this analysis."
                )
        else:
            st.info(
                "Select a completed analysis to retrieve similar MAIRA cases."
            )

    with similar_right:
        st.markdown("**News & alerts**")
        st.info(
            "External/news similarity remains separate from validated "
            "investigation knowledge and is handled in the News/dashboard "
            "workstream."
        )


with tab_knowledge_graph:
    st.subheader("Knowledge Graph")
    st.caption(
        "Explore the active analysis as an interactive knowledge graph. "
        "Document selection changes the evidence scope represented in the "
        "diagram; concept, relationship and layout controls change only the view."
    )

    if not active_analysis_id or not active_analysis:
        st.info(
            "Create or select an active analysis to explore its knowledge graph."
        )
    elif active_analysis.get("status") != "COMPLETED":
        st.info(
            "The Knowledge Graph becomes available after the active analysis "
            "has completed all four processing stages."
        )
    else:
        graph_analysis_id = active_analysis_id
        graph_meta = active_analysis

        graph_model_runs = [
            item
            for item in load_model_runs(
                graph_analysis_id
            )
            if item.get("status") == "COMPLETED"
        ]

        graph_model_run_id = None
        if len(graph_model_runs) > 1:
            graph_model_by_id = {
                item["model_run_id"]: item
                for item in graph_model_runs
            }
            graph_model_run_id = st.selectbox(
                "Model graph",
                options=list(
                    graph_model_by_id
                ),
                format_func=lambda value: (
                    graph_model_by_id[value].get(
                        "model_label"
                    )
                    or graph_model_by_id[value].get(
                        "model_key"
                    )
                    or value
                ),
                key=(
                    "graph_model_run_"
                    + graph_analysis_id
                ),
            )
            raw_graph = load_model_run_graph(
                graph_analysis_id,
                graph_model_run_id,
            )
        elif len(graph_model_runs) == 1:
            graph_model_run_id = (
                graph_model_runs[0][
                    "model_run_id"
                ]
            )
            raw_graph = load_model_run_graph(
                graph_analysis_id,
                graph_model_run_id,
            )
        else:
            raw_graph = load_analysis_graph(
                graph_analysis_id
            )

        graph_sources = load_analysis_sources(
            graph_analysis_id
        )
        graph_source_by_id = {
            item["document_id"]: item
            for item in graph_sources
        }
        all_graph_document_ids = list(
            graph_source_by_id
        )

        def graph_source_label(document_id):
            source = graph_source_by_id[
                document_id
            ]
            repository = (
                source.get(
                    "viewer_source_repository"
                )
                or "IKF"
            )
            return (
                "["
                + repository
                + "] "
                + str(
                    source.get(
                        "viewer_source_filename"
                    )
                    or source.get(
                        "filename"
                    )
                    or document_id
                )
            )

        st.markdown("### Graph scope and view")

        scope_left, scope_right = st.columns(
            [1.35, 1.0]
        )

        with scope_left:
            if all_graph_document_ids:
                selected_graph_document_ids = (
                    st.multiselect(
                        "Documents represented in the graph",
                        options=all_graph_document_ids,
                        default=all_graph_document_ids,
                        format_func=graph_source_label,
                        filter_mode="contains",
                        key=(
                            "graph_documents_"
                            + graph_analysis_id
                        ),
                        help=(
                            "Only graph items supported by the selected "
                            "documents are shown. This same document scope "
                            "is used for graph questions."
                        ),
                    )
                )
            else:
                selected_graph_document_ids = []
                st.caption(
                    "This analysis does not use document sources; the whole "
                    "prepared evidence set is represented."
                )

        def graph_item_document_ids(
            evidence_locations,
        ):
            document_ids = set()
            for value in evidence_locations or []:
                parsed = parse_evidence_location(
                    value
                )
                if (
                    parsed
                    and parsed.get(
                        "document_id"
                    )
                ):
                    document_ids.add(
                        parsed[
                            "document_id"
                        ]
                    )
            return document_ids

        selected_document_set = set(
            selected_graph_document_ids
        )
        all_document_set = set(
            all_graph_document_ids
        )
        document_filter_active = bool(
            all_document_set
        ) and (
            selected_document_set
            != all_document_set
        )

        scoped_nodes = list(
            raw_graph["nodes"]
        )
        scoped_edges = list(
            raw_graph["edges"]
        )

        if document_filter_active:
            node_ids_from_documents = {
                node["node_id"]
                for node in raw_graph[
                    "nodes"
                ]
                if (
                    graph_item_document_ids(
                        node.get(
                            "evidence_locations"
                        )
                    )
                    & selected_document_set
                )
            }

            evidence_scoped_edges = [
                edge
                for edge in raw_graph[
                    "edges"
                ]
                if (
                    graph_item_document_ids(
                        edge.get(
                            "evidence_locations"
                        )
                    )
                    & selected_document_set
                )
            ]

            endpoint_ids = set()
            for edge in evidence_scoped_edges:
                endpoint_ids.add(
                    edge["source_id"]
                )
                endpoint_ids.add(
                    edge["target_id"]
                )

            scoped_node_ids = (
                node_ids_from_documents
                | endpoint_ids
            )

            scoped_nodes = [
                node
                for node in raw_graph[
                    "nodes"
                ]
                if node["node_id"]
                in scoped_node_ids
            ]

            scoped_edges = [
                edge
                for edge in raw_graph[
                    "edges"
                ]
                if (
                    edge["source_id"]
                    in scoped_node_ids
                    and edge["target_id"]
                    in scoped_node_ids
                    and (
                        edge
                        in evidence_scoped_edges
                        or edge.get(
                            "edge_class"
                        )
                        == "STRUCTURAL"
                    )
                )
            ]

        available_node_kinds = sorted(
            {
                node.get(
                    "node_kind"
                )
                or "Other"
                for node in scoped_nodes
            }
        )
        available_relationships = sorted(
            {
                edge.get(
                    "relationship"
                )
                or "OTHER"
                for edge in scoped_edges
            }
        )

        with scope_right:
            graph_layout_options = {
                "Force-directed":
                    "fcose",
                "Hierarchy":
                    "breadthfirst",
                "Circle":
                    "circle",
                "Concentric":
                    "concentric",
                "Grid":
                    "grid",
            }
            graph_layout_label = st.selectbox(
                "Diagram layout",
                options=list(
                    graph_layout_options
                ),
                key=(
                    "graph_layout_"
                    + graph_analysis_id
                ),
            )
            graph_layout = (
                graph_layout_options[
                    graph_layout_label
                ]
            )

        filter_left, filter_right = st.columns(
            2
        )

        with filter_left:
            selected_node_kinds = st.multiselect(
                "Concept types",
                options=available_node_kinds,
                default=available_node_kinds,
                key=(
                    "graph_node_types_"
                    + graph_analysis_id
                ),
            )

        with filter_right:
            selected_relationships = st.multiselect(
                "Relationship types",
                options=available_relationships,
                default=available_relationships,
                key=(
                    "graph_relationship_types_"
                    + graph_analysis_id
                ),
            )

        selected_node_kind_set = set(
            selected_node_kinds
        )
        selected_relationship_set = set(
            selected_relationships
        )

        visible_nodes = [
            node
            for node in scoped_nodes
            if (
                node.get(
                    "node_kind"
                )
                or "Other"
            )
            in selected_node_kind_set
        ]
        visible_node_ids = {
            node["node_id"]
            for node in visible_nodes
        }

        visible_edges = [
            edge
            for edge in scoped_edges
            if (
                edge.get(
                    "relationship"
                )
                or "OTHER"
            )
            in selected_relationship_set
            and edge["source_id"]
            in visible_node_ids
            and edge["target_id"]
            in visible_node_ids
        ]

        graph_elements = {
            "nodes": [
                {
                    "data": {
                        "id": node[
                            "node_id"
                        ],
                        "label": node.get(
                            "node_kind"
                        )
                        or "Other",
                        "name": node.get(
                            "label"
                        )
                        or node[
                            "node_id"
                        ],
                        "description": node.get(
                            "description"
                        )
                        or "",
                    }
                }
                for node in visible_nodes
            ],
            "edges": [
                {
                    "data": {
                        "id": edge[
                            "edge_id"
                        ],
                        "label": edge.get(
                            "relationship"
                        )
                        or "OTHER",
                        "source": edge[
                            "source_id"
                        ],
                        "target": edge[
                            "target_id"
                        ],
                        "relationship": edge.get(
                            "relationship"
                        )
                        or "OTHER",
                    }
                }
                for edge in visible_edges
            ],
        }

        graph_metrics = st.columns(3)
        graph_metrics[0].metric(
            "Visible concepts",
            len(
                visible_nodes
            ),
        )
        graph_metrics[1].metric(
            "Visible relationships",
            len(
                visible_edges
            ),
        )
        graph_metrics[2].metric(
            "Documents in scope",
            (
                len(
                    selected_graph_document_ids
                )
                if all_graph_document_ids
                else "Text"
            ),
        )

        if not graph_elements["nodes"]:
            st.warning(
                "No graph concepts match the current document/type filters."
            )
        else:
            st.caption(
                "Colour key — event: amber · contributing factor: red · "
                "finding: blue · safety issue: purple · recommendation: "
                "green · actor: pink · vessel: teal · system: slate."
            )
            streamlit_cytoscape(
                elements=graph_elements,
                layout=graph_layout,
                node_styles=analysis_node_styles,
                edge_styles=analysis_edge_styles,
                height=760,
                key=(
                    "knowledge_graph_workspace_"
                    + graph_analysis_id
                    + "_"
                    + graph_layout
                ),
            )

        st.caption(
            "Diagram filters and layout do not edit knowledge. Relationship "
            "validation/amendment remains in Review & Validate."
        )

        st.divider()
        st.markdown("### Ask about this graph scope")
        st.caption(
            "The question uses governed source evidence from the selected "
            "documents. Visual node/relationship filters do not silently "
            "remove evidence from retrieval."
        )

        graph_class = (
            graph_meta.get(
                "information_class"
            )
            or "B"
        )

        if graph_class == "D":
            graph_model_label = st.radio(
                "Protected-evidence model mode",
                options=list(
                    CLASS_D_MODEL_OPTIONS
                ),
                horizontal=True,
                key=(
                    "graph_question_model_"
                    + graph_analysis_id
                ),
            )
            graph_question_model_selection = (
                CLASS_D_MODEL_OPTIONS[
                    graph_model_label
                ]
            )
        else:
            graph_question_model_selection = (
                "DEFAULT"
            )

        graph_reference_context = st.checkbox(
            "Include legal / IMO / technical references",
            value=False,
            key=(
                "graph_reference_context_"
                + graph_analysis_id
            ),
            help=(
                "Reference material remains separate from case evidence and "
                "cannot prove an occurrence fact."
            ),
        )

        if not all_graph_document_ids:
            graph_question_scope_mode = (
                "WHOLE_CASE"
            )
            graph_question_document_ids = []
            graph_scope_text = (
                "Entire prepared evidence set"
            )
        elif (
            selected_document_set
            == all_document_set
        ):
            graph_question_scope_mode = (
                "WHOLE_CASE"
            )
            graph_question_document_ids = []
            graph_scope_text = (
                "All analysis documents"
            )
        elif len(
            selected_graph_document_ids
        ) == 1:
            graph_question_scope_mode = (
                "ONE_DOCUMENT"
            )
            graph_question_document_ids = list(
                selected_graph_document_ids
            )
            graph_scope_text = (
                graph_source_label(
                    selected_graph_document_ids[
                        0
                    ]
                )
            )
        else:
            graph_question_scope_mode = (
                "SELECTED_DOCUMENTS"
            )
            graph_question_document_ids = list(
                selected_graph_document_ids
            )
            graph_scope_text = (
                str(
                    len(
                        selected_graph_document_ids
                    )
                )
                + " selected document(s)"
            )

        st.info(
            "Graph question evidence scope: "
            + graph_scope_text
        )

        with st.form(
            "graph_question_form_"
            + graph_analysis_id,
            clear_on_submit=False,
        ):
            graph_question_text = st.text_area(
                "Question about this graph",
                placeholder=(
                    "Example: Which contributing factors are connected to "
                    "the fire event, and what source evidence supports those links?"
                ),
                height=110,
            )
            graph_question_submit = (
                st.form_submit_button(
                    "Ask",
                    type="primary",
                )
            )

        if graph_question_submit:
            graph_question_errors = []

            if not graph_question_text.strip():
                graph_question_errors.append(
                    "Enter a question."
                )

            if (
                graph_question_scope_mode
                == "SELECTED_DOCUMENTS"
                and not graph_question_document_ids
            ):
                graph_question_errors.append(
                    "Select at least one document for the graph question."
                )

            if not ASK_JOB_ID:
                graph_question_errors.append(
                    "The Ask Job is not attached to this App deployment."
                )

            if (
                graph_class == "D"
                and graph_question_model_selection
                in {
                    "LLAMA70",
                    "BOTH",
                }
                and get_llama_daily_usage()
                >= LLAMA_DAILY_QUESTION_LIMIT
            ):
                graph_question_errors.append(
                    "The daily Llama 3.3 70B question limit has been reached."
                )

            if graph_question_errors:
                for error in graph_question_errors:
                    st.error(
                        error
                    )
            else:
                graph_question_run_id = None
                try:
                    graph_question_run_id = (
                        create_question_run(
                            analysis=graph_meta,
                            question_text=(
                                graph_question_text.strip()
                            ),
                            scope_mode=(
                                graph_question_scope_mode
                            ),
                            scope_document_ids=(
                                graph_question_document_ids
                            ),
                            model_selection=(
                                graph_question_model_selection
                            ),
                            include_reference_context=(
                                graph_reference_context
                            ),
                            interaction_surface=(
                                "KNOWLEDGE_GRAPH"
                            ),
                        )
                    )

                    if (
                        graph_class == "D"
                        and graph_question_model_selection
                        in {
                            "LLAMA70",
                            "BOTH",
                        }
                    ):
                        consumed = (
                            consume_llama_daily_usage()
                        )
                        if consumed is None:
                            raise RuntimeError(
                                "The Llama daily quota could not be reserved."
                            )

                    graph_question_job_run_id = (
                        trigger_question_job(
                            graph_question_run_id
                        )
                    )

                    load_question_runs.clear()
                    load_question_model_runs.clear()

                    st.success(
                        "Graph question queued."
                    )
                    st.caption(
                        "Question run: "
                        + graph_question_run_id
                        + " · Databricks run: "
                        + graph_question_job_run_id
                    )

                except Exception as exc:
                    if graph_question_run_id:
                        with get_driver().session() as session:
                            session.run(
                                """
                                MATCH (q:QuestionRun {
                                    question_run_id: $question_run_id
                                })
                                SET
                                    q.status = 'FAILED',
                                    q.processing_stage = 'JOB_TRIGGER_FAILED',
                                    q.processing_error = $error_message,
                                    q.updated_at = datetime()
                                """,
                                question_run_id=graph_question_run_id,
                                error_message=(
                                    f"{type(exc).__name__}: {exc}"
                                ),
                            ).consume()
                    st.error(
                        "The graph question could not be queued."
                    )
                    st.exception(
                        exc
                    )

        graph_question_runs = [
            item
            for item in load_question_runs(
                graph_analysis_id
            )
            if (
                item.get(
                    "interaction_surface"
                )
                == "KNOWLEDGE_GRAPH"
            )
        ]

        if graph_question_runs:
            st.markdown(
                "### Graph question history"
            )

            graph_question_by_id = {
                item[
                    "question_run_id"
                ]: item
                for item in graph_question_runs
            }

            selected_graph_question_id = (
                st.selectbox(
                    "Graph question",
                    options=list(
                        graph_question_by_id
                    ),
                    format_func=lambda value: (
                        question_display_text(
                            graph_question_by_id[
                                value
                            ]
                        )[:100]
                        + " · "
                        + (
                            graph_question_by_id[
                                value
                            ].get(
                                "status"
                            )
                            or "UNKNOWN"
                        )
                    ),
                    key=(
                        "graph_question_history_"
                        + graph_analysis_id
                    ),
                )
            )

            selected_graph_question = (
                graph_question_by_id[
                    selected_graph_question_id
                ]
            )

            st.write(
                question_display_text(
                    selected_graph_question
                )
            )
            st.caption(
                "Scope: "
                + (
                    selected_graph_question.get(
                        "scope_mode"
                    )
                    or "WHOLE_CASE"
                )
                + " · Status: "
                + (
                    selected_graph_question.get(
                        "status"
                    )
                    or "UNKNOWN"
                )
            )

            if (
                selected_graph_question.get(
                    "status"
                )
                == "COMPLETED"
            ):
                graph_answer_runs = (
                    load_question_model_runs(
                        selected_graph_question_id
                    )
                )

                if len(
                    graph_answer_runs
                ) == 1:
                    render_question_answer(
                        analysis_id=(
                            graph_analysis_id
                        ),
                        question_run=(
                            selected_graph_question
                        ),
                        model_run=(
                            graph_answer_runs[
                                0
                            ]
                        ),
                        render_key=(
                            "graph_"
                            + graph_answer_runs[
                                0
                            ][
                                "model_key"
                            ]
                        ),
                    )
                elif graph_answer_runs:
                    graph_answer_columns = (
                        st.columns(
                            len(
                                graph_answer_runs
                            )
                        )
                    )
                    for (
                        graph_answer_column,
                        graph_answer_run,
                    ) in zip(
                        graph_answer_columns,
                        graph_answer_runs,
                    ):
                        with graph_answer_column:
                            render_question_answer(
                                analysis_id=(
                                    graph_analysis_id
                                ),
                                question_run=(
                                    selected_graph_question
                                ),
                                model_run=(
                                    graph_answer_run
                                ),
                                render_key=(
                                    "graph_"
                                    + graph_answer_run[
                                        "model_key"
                                    ]
                                ),
                            )
            elif (
                selected_graph_question.get(
                    "status"
                )
                == "FAILED"
            ):
                st.error(
                    selected_graph_question.get(
                        "processing_error"
                    )
                    or "Graph question processing failed."
                )
            else:
                st.info(
                    "The graph question is queued or running."
                )


with tab_review:
    st.subheader("Review & Validate")
    st.caption(
        "Select a completed analysis and make human governance decisions on "
        "its evidence-derived relationships and taxonomy proposals."
    )

    st.markdown("### Review queue")
    st.caption(
        "Work through only the areas that need a human decision. "
        "Relationships are reviewed first; SHIELD becomes available only "
        "after an eligible contributing relationship has been validated."
    )

    try:
        review_analyses = [
            item
            for item in load_analysis_groups()
            if item.get("status") == "COMPLETED"
        ]
    except Exception as exc:
        review_analyses = []
        st.error("Existing analyses could not be loaded for review.")
        st.exception(exc)

    review_by_id = {
        item["analysis_id"]: item
        for item in review_analyses
    }
    selected_review_analysis_id = (
        active_analysis_id
        if (
            active_analysis_id
            and active_analysis_id
            in review_by_id
        )
        else None
    )

    if selected_review_analysis_id:
        st.caption(
            "Using active analysis: "
            + str(
                review_by_id[
                    selected_review_analysis_id
                ].get(
                    "analysis_title"
                )
                or selected_review_analysis_id
            )
        )
    elif active_analysis_id:
        st.info(
            "The active analysis is not yet completed, so human review "
            "controls are not available."
        )

    st.markdown("### 1. Relationship review")
    st.caption(
        "Human review is stored as a separate append-only review record. "
        "The original graph relationship and assistant review are not overwritten."
    )

    selected_review_graph = {
        "nodes": [],
        "edges": [],
    }
    selected_review_model_run_id = None

    if selected_review_analysis_id:
        review_analysis = review_by_id[
            selected_review_analysis_id
        ]
        review_model_runs = load_model_runs(
            selected_review_analysis_id
        )

        if len(review_model_runs) > 1:
            review_model_run_by_id = {
                item["model_run_id"]: item
                for item in review_model_runs
                if item.get("status") == "COMPLETED"
            }

            if review_model_run_by_id:
                selected_review_model_run_id = st.selectbox(
                    "Model output to review",
                    options=list(
                        review_model_run_by_id
                    ),
                    format_func=lambda value: (
                        review_model_run_by_id[value].get(
                            "model_label"
                        )
                        or review_model_run_by_id[value].get(
                            "model_key"
                        )
                        or value
                    ),
                    key="review_model_run_selector",
                )
                selected_review_graph = load_model_run_graph(
                    selected_review_analysis_id,
                    selected_review_model_run_id,
                )
        elif len(review_model_runs) == 1:
            selected_review_model_run_id = (
                review_model_runs[0][
                    "model_run_id"
                ]
            )
            selected_review_graph = load_model_run_graph(
                selected_review_analysis_id,
                selected_review_model_run_id,
            )
        else:
            selected_review_graph = load_analysis_graph(
                selected_review_analysis_id
            )

    reviewable_rows = [
        {
            "edge_id": edge["edge_id"],
            "model_run_id": (
                edge.get("model_run_id")
                or selected_review_model_run_id
                or (
                    selected_review_analysis_id
                    + "__primary"
                    if selected_review_analysis_id
                    else ""
                )
            ),
            "source_id": edge["source_id"],
            "source_name": edge["source_label"],
            "relationship": edge["relationship"],
            "target_id": edge["target_id"],
            "target_name": edge["target_label"],
            "evidence_status": edge.get("evidence_class") or "ASSISTANT_CANDIDATE",
            "passage_ids": edge.get("passage_ids") or [],
            "evidence_references": edge.get("evidence_references") or [],
            "evidence_locations": edge.get("evidence_locations") or [],
            "evidence_anchor": ", ".join(edge.get("passage_ids") or []),
            "evidence": (
                " · ".join(edge.get("evidence_references") or [])
                if edge.get("evidence_references")
                else (
                    "Supporting passage IDs: "
                    + ", ".join(edge.get("passage_ids") or [])
                    if edge.get("passage_ids")
                    else "No supporting passage ID was published for this relationship."
                )
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
            "model_run_id": "",
            "source_id": "",
            "source_name": "—",
            "relationship": "—",
            "target_id": "",
            "target_name": "—",
            "evidence_status": "—",
            "passage_ids": [],
            "evidence_references": [],
            "evidence_locations": [],
            "evidence_anchor": "",
            "evidence": "No relationship selected.",
        }
    )
    latest = latest_reviews.get(selected["edge_id"])

    if selected_index is None:
        st.info(
            "The selected analysis has no published non-structural "
            "relationships available for review yet."
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

    if (
        selected.get("model_run_id")
        or selected["evidence_anchor"]
    ):
        with st.expander(
            "Technical provenance",
            expanded=False,
        ):
            if selected.get("model_run_id"):
                st.markdown(
                    "**Model run**"
                )
                st.code(
                    selected["model_run_id"],
                    language=None,
                )

            if selected["evidence_anchor"]:
                st.markdown(
                    "**Evidence anchor**"
                )
                st.write(
                    selected[
                        "evidence_anchor"
                    ]
                )

    st.markdown("**Supporting evidence**")

    evidence_left, evidence_right = st.columns(
        [1.0, 1.2]
    )

    with evidence_left:
        references = (
            selected.get("evidence_references")
            or []
        )

        if references:
            for reference in references:
                st.write(f"• {reference}")
        else:
            st.info(
                selected["evidence"]
                or "No page-level source reference is available for this relationship."
            )

        passage_ids = (
            selected.get("passage_ids")
            or []
        )
        if passage_ids:
            with st.expander(
                "Technical evidence IDs",
                expanded=False,
            ):
                for passage_id in passage_ids:
                    st.code(
                        passage_id,
                        language=None,
                    )

    with evidence_right:
        review_locations = [
            parsed
            for parsed in (
                parse_evidence_location(value)
                for value in (
                    selected.get(
                        "evidence_locations"
                    )
                    or []
                )
            )
            if parsed is not None
        ]

        if (
            selected_review_analysis_id
            and review_locations
        ):
            review_sources = load_analysis_sources(
                selected_review_analysis_id
            )
            review_source_by_id = {
                source["document_id"]: source
                for source in review_sources
            }

            review_location_index = st.selectbox(
                "Evidence page",
                options=list(
                    range(
                        len(review_locations)
                    )
                ),
                format_func=lambda index: format_evidence_location(
                    review_locations[index],
                    review_source_by_id.get(
                        review_locations[index][
                            "document_id"
                        ]
                    ),
                ),
                key=(
                    "relationship_review_page_"
                    + selected["edge_id"]
                ),
                disabled=review_controls_disabled,
            )

            review_location = review_locations[
                review_location_index
            ]
            review_source = review_source_by_id.get(
                review_location[
                    "document_id"
                ]
            )

            if review_source:
                review_path = review_source.get(
                    "viewer_source_path"
                )
                review_type = str(
                    review_source.get(
                        "source_type"
                    )
                    or ""
                ).upper()

                if (
                    review_type == "PDF"
                    and review_path
                ):
                    try:
                        review_pdf = download_source_file_as_user(
                            review_path
                        )
                        review_excerpt = pdf_page_range_bytes(
                            review_pdf,
                            review_location.get(
                                "page_start"
                            ),
                            review_location.get(
                                "page_end"
                            ),
                        )
                        st.pdf(
                            review_excerpt,
                            height=620,
                            key=(
                                "relationship_review_pdf_"
                                + hashlib.sha256(
                                    (
                                        selected["edge_id"]
                                        + "|"
                                        + review_path
                                        + "|"
                                        + str(
                                            review_location.get(
                                                "page_start"
                                            )
                                        )
                                    ).encode(
                                        "utf-8"
                                    )
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
                        "A page citation exists, but this source is not "
                        "available as an embedded PDF."
                    )
            else:
                st.caption(
                    "The cited document is not linked to the selected analysis."
                )
        elif selected_index is not None:
            st.caption(
                "No page-level evidence location is stored for this "
                "relationship. Older analyses may require rerunning."
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


with tab_review:
    st.divider()
    st.markdown("### Optional relationship quality check")
    st.caption(
        "Use this only when you want the assistant to challenge or refine one "
        "evidence-derived relationship. The proposal is advisory; the human "
        "review remains authoritative and the graph edge is never overwritten."
    )

    correction_edges = [
        edge
        for edge in selected_review_graph.get(
            "edges",
            [],
        )
        if (
            edge.get("edge_class")
            != "STRUCTURAL"
            and edge.get("model_run_id")
        )
    ]

    if not selected_review_analysis_id:
        st.info(
            "Select a completed analysis above."
        )
    elif not correction_edges:
        st.info(
            "No evidence-derived relationship with model provenance is "
            "available for an assistant check."
        )
    else:
        correction_edge_by_id = {
            edge["edge_id"]: edge
            for edge in correction_edges
        }

        correction_edge_id = st.selectbox(
            "Relationship to check",
            options=list(
                correction_edge_by_id
            ),
            format_func=lambda value: (
                correction_edge_by_id[value][
                    "source_label"
                ]
                + " — "
                + correction_edge_by_id[value][
                    "relationship"
                ]
                + " → "
                + correction_edge_by_id[value][
                    "target_label"
                ]
            ),
            key=(
                "review_correction_edge_"
                + selected_review_analysis_id
            ),
        )

        correction_edge = (
            correction_edge_by_id[
                correction_edge_id
            ]
        )
        correction_model_run_id = (
            correction_edge[
                "model_run_id"
            ]
        )

        current_human_review = (
            load_latest_relationship_reviews(
                selected_review_analysis_id
            ).get(
                correction_edge_id
            )
        )

        if current_human_review:
            st.caption(
                "Current human relationship review: "
                + (
                    current_human_review.get(
                        "status"
                    )
                    or current_human_review.get(
                        "decision"
                    )
                    or "reviewed"
                )
            )
        else:
            st.caption(
                "This relationship has not yet received a human review."
            )

        generate_correction = st.button(
            "Generate evidence-bounded assistant proposal",
            key=(
                "review_generate_relationship_correction_"
                + selected_review_analysis_id
                + "_"
                + correction_edge_id
            ),
            disabled=(
                not RELATIONSHIP_CORRECTION_JOB_ID
            ),
        )

        if not RELATIONSHIP_CORRECTION_JOB_ID:
            st.caption(
                "The Relationship Correction Job is not attached to this "
                "App deployment."
            )

        if generate_correction:
            try:
                correction_run_id = (
                    trigger_relationship_correction_job(
                        selected_review_analysis_id,
                        correction_model_run_id,
                        correction_edge_id,
                    )
                )
                load_relationship_correction_proposals.clear()
                st.success(
                    "Assistant relationship check queued."
                )
                st.caption(
                    "Databricks run: "
                    + correction_run_id
                )
            except Exception as exc:
                st.error(
                    "The relationship check could not be queued."
                )
                st.exception(exc)

        correction_proposals = (
            load_relationship_correction_proposals(
                selected_review_analysis_id,
                correction_model_run_id,
                correction_edge_id,
            )
        )

        if correction_proposals:
            proposal = correction_proposals[0]

            st.markdown(
                "**Assistant proposal**"
            )
            st.write(
                "Action: "
                + (
                    proposal.get(
                        "action"
                    )
                    or "—"
                )
            )

            if proposal.get(
                "proposed_relationship"
            ):
                st.write(
                    "Proposed relationship: "
                    + proposal[
                        "proposed_relationship"
                    ]
                )

            st.write(
                proposal.get(
                    "rationale"
                )
                or "No rationale was returned."
            )

            references = (
                proposal.get(
                    "evidence_references"
                )
                or []
            )
            if references:
                st.markdown(
                    "**Source pages**"
                )
                for reference in references:
                    st.write(
                        "• " + str(reference)
                    )

            if not proposal.get(
                "base_review_is_current"
            ):
                st.warning(
                    "This proposal is stale because a newer human "
                    "relationship review exists. Generate a new proposal "
                    "before acting on it."
                )

            correction_reviews = (
                load_latest_relationship_correction_reviews(
                    selected_review_analysis_id,
                    correction_model_run_id,
                )
            )
            latest_correction_review = (
                correction_reviews.get(
                    proposal[
                        "proposal_id"
                    ]
                )
            )

            if latest_correction_review:
                st.success(
                    "Latest decision on this assistant proposal: "
                    + (
                        latest_correction_review.get(
                            "decision"
                        )
                        or "—"
                    )
                )

            if (
                proposal.get(
                    "assistant_status"
                )
                == "ASSISTANT_PROPOSED"
                and proposal.get(
                    "base_review_is_current"
                )
            ):
                with st.form(
                    "review_relationship_correction_"
                    + proposal[
                        "proposal_id"
                    ]
                ):
                    correction_decision = st.radio(
                        "Human decision on assistant proposal",
                        options=[
                            "APPROVED",
                            "DISMISSED",
                            "APPLIED_WITH_AMENDMENT",
                        ],
                        format_func=lambda value: {
                            "APPROVED":
                                "Approve assistant proposal",
                            "DISMISSED":
                                "Dismiss assistant proposal",
                            "APPLIED_WITH_AMENDMENT":
                                "Apply a different human outcome",
                        }[value],
                    )

                    amended_outcome = None

                    if (
                        correction_decision
                        == "APPLIED_WITH_AMENDMENT"
                    ):
                        amended_outcome = st.selectbox(
                            "Final human outcome",
                            options=[
                                "KEEP_CURRENT",
                                "REJECT_RELATIONSHIP",
                                "FOLLOWED_BY",
                                "CONTRIBUTED_TO",
                                "RESULTED_IN",
                                "AFFECTED",
                                "SUPPORTS",
                            ],
                        )

                    correction_comment = st.text_area(
                        "Review comment",
                        height=80,
                    )

                    correction_submit = (
                        st.form_submit_button(
                            "Save human decision",
                            type="primary",
                        )
                    )

                if correction_submit:
                    try:
                        correction_result = (
                            save_relationship_correction_review(
                                proposal,
                                decision=correction_decision,
                                amended_outcome=amended_outcome,
                                comment=correction_comment,
                            )
                        )
                        load_relationship_correction_proposals.clear()
                        load_latest_relationship_correction_reviews.clear()
                        st.success(
                            "Human decision saved. The graph edge itself "
                            "was not overwritten."
                        )
                        if correction_result.get(
                            "relationship_review_id"
                        ):
                            st.caption(
                                "Authoritative review ID: "
                                + correction_result[
                                    "relationship_review_id"
                                ]
                            )
                    except Exception as exc:
                        st.error(
                            "The human correction decision could not be saved."
                        )
                        st.exception(exc)


with tab_mapping_review:
    st.divider()
    st.markdown("### 2. EMCIP mapping review")
    st.caption(
        "Assistant mappings are generated on demand from the governed MAIRA "
        "EMCIP registry. The proposal never becomes authoritative until a "
        "human validates or amends it."
    )

    try:
        mapping_analyses = [
            item
            for item in load_analysis_groups()
            if item.get("status") == "COMPLETED"
        ]
    except Exception as exc:
        mapping_analyses = []
        st.error(
            "Completed analyses could not be loaded for EMCIP mapping."
        )
        st.exception(exc)

    mapping_analysis_by_id = {
        item["analysis_id"]: item
        for item in mapping_analyses
    }

    mapping_analysis_id = (
        active_analysis_id
        if (
            active_analysis_id
            and active_analysis_id
            in mapping_analysis_by_id
        )
        else None
    )

    if mapping_analysis_id:
        st.caption(
            "EMCIP and SHIELD review use the same active analysis."
        )

    mapping_model_run_id = None
    mapping_model_run = None

    if mapping_analysis_id:
        mapping_model_runs = [
            item
            for item in load_model_runs(mapping_analysis_id)
            if item.get("status") == "COMPLETED"
        ]

        mapping_model_run_by_id = {
            item["model_run_id"]: item
            for item in mapping_model_runs
        }

        if mapping_model_run_by_id:
            mapping_model_run_id = st.selectbox(
                "Model graph to map",
                options=list(mapping_model_run_by_id),
                format_func=lambda value: (
                    mapping_model_run_by_id[value].get("model_label")
                    or mapping_model_run_by_id[value].get("model_key")
                    or value
                ),
                key="mapping_model_run_selector",
            )
            mapping_model_run = mapping_model_run_by_id[
                mapping_model_run_id
            ]
        else:
            st.info(
                "No completed model graph is available for this analysis."
            )

    action_left, action_right = st.columns([1, 1])

    with action_left:
        generate_mapping = st.button(
            "Generate / refresh EMCIP proposals",
            type="primary",
            disabled=(
                mapping_analysis_id is None
                or mapping_model_run_id is None
                or not EMCIP_MAPPING_JOB_ID
            ),
            key="generate_emcip_proposals",
        )

    with action_right:
        refresh_mapping = st.button(
            "Refresh mapping status",
            disabled=(
                mapping_analysis_id is None
                or mapping_model_run_id is None
            ),
            key="refresh_emcip_mapping_status",
        )

    if not EMCIP_MAPPING_JOB_ID:
        st.caption(
            "The generic EMCIP proposal Job is not attached to this App "
            "deployment yet. Source code is ready; runtime setup uses "
            "resource key emcip_mapping_job."
        )

    if refresh_mapping:
        load_emcip_mapping_proposals.clear()
        load_latest_analysis_mapping_reviews.clear()
        load_analysis_groups.clear()
        st.toast("EMCIP mapping status refreshed")

    if generate_mapping:
        try:
            mapping_job_run_id = trigger_emcip_mapping_job(
                mapping_analysis_id,
                mapping_model_run_id,
            )
            load_emcip_mapping_proposals.clear()
            st.success(
                "EMCIP proposal generation queued."
            )
            st.caption(
                "Databricks run: " + mapping_job_run_id
            )
        except Exception as exc:
            st.error(
                "EMCIP proposal generation could not be queued."
            )
            st.exception(exc)

    mapping_proposals = (
        load_emcip_mapping_proposals(
            mapping_analysis_id,
            mapping_model_run_id,
        )
        if (
            mapping_analysis_id
            and mapping_model_run_id
        )
        else []
    )

    latest_mapping_reviews = (
        load_latest_analysis_mapping_reviews(
            mapping_analysis_id,
            mapping_model_run_id,
        )
        if (
            mapping_analysis_id
            and mapping_model_run_id
        )
        else {}
    )

    reviewed_mapping_keys = set(
        latest_mapping_reviews
    )

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Mapping proposals",
        len(mapping_proposals),
    )
    m2.metric(
        "Human reviewed",
        len(reviewed_mapping_keys),
    )
    m3.metric(
        "Remaining",
        max(
            0,
            len(mapping_proposals)
            - len(reviewed_mapping_keys),
        ),
    )

    if (
        mapping_analysis_id
        and mapping_model_run_id
        and not mapping_proposals
    ):
        st.info(
            "No generic EMCIP proposals are available for this analysis/model "
            "graph yet. Generate them on demand above."
        )

    if mapping_proposals:
        def mapping_option_label(index):
            proposal = mapping_proposals[index]
            latest_mapping = latest_mapping_reviews.get(
                proposal["proposal_id"]
            )

            if latest_mapping:
                marker = {
                    "VALIDATED": "✓",
                    "REJECTED": "✕",
                    "AMENDED": "✎",
                }.get(
                    latest_mapping["decision"],
                    "•",
                )
                prefix = f"{marker} "
            else:
                prefix = ""

            return (
                f"{prefix}{proposal['node_kind']}: "
                f"{proposal['node_label']} → "
                f"{emcip_mapping_text(proposal)}"
            )

        selected_mapping_index = st.selectbox(
            "Mapping proposal",
            options=list(range(len(mapping_proposals))),
            format_func=mapping_option_label,
            key="generic_mapping_selector",
        )

        selected_mapping = mapping_proposals[
            selected_mapping_index
        ]
        latest_mapping = latest_mapping_reviews.get(
            selected_mapping["proposal_id"]
        )

        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.markdown("**Concept**")
            st.write(selected_mapping["node_label"])
        with mc2:
            st.markdown("**Concept type**")
            st.write(selected_mapping["node_kind"])
        with mc3:
            st.markdown("**Assistant status**")
            st.write(
                selected_mapping[
                    "assistant_mapping_status"
                ]
            )

        st.markdown("**Assistant EMCIP proposal**")
        if (
            selected_mapping[
                "assistant_mapping_status"
            ]
            == "ASSISTANT_PROPOSED"
        ):
            st.info(
                emcip_mapping_text(
                    selected_mapping
                )
            )
        else:
            st.warning("NO_MAPPING")

        if selected_mapping.get("rationale"):
            st.caption(
                "Assistant rationale: "
                + selected_mapping["rationale"]
            )

        st.caption(
            "Proposal method: "
            + (
                selected_mapping.get("proposal_method")
                or "—"
            )
            + " · Model: "
            + (
                selected_mapping.get("model_service")
                or "—"
            )
        )

        candidate_options = (
            selected_mapping.get("candidate_options")
            or []
        )

        with st.expander(
            "Governed EMCIP shortlist",
            expanded=False,
        ):
            if not candidate_options:
                st.write(
                    "No deterministic taxonomy candidates were available."
                )
            else:
                for candidate in candidate_options:
                    st.write(
                        "• "
                        + (
                            candidate.get("entity_path")
                            or candidate.get("entity_name")
                            or "EMCIP"
                        )
                        + " → "
                        + (
                            candidate.get("attribute_name")
                            or ""
                        )
                        + " → "
                        + (
                            candidate.get("code_value")
                            or ""
                        )
                        + " ["
                        + str(
                            candidate.get("code_idcode")
                            or "—"
                        )
                        + "]"
                        + " · lexical/structural score "
                        + str(candidate.get("score") or 0)
                    )

        st.markdown("**Source evidence for the concept**")
        map_evidence_left, map_evidence_right = st.columns(
            [1.0, 1.2]
        )

        with map_evidence_left:
            map_refs = (
                selected_mapping.get(
                    "evidence_references"
                )
                or []
            )
            if map_refs:
                for reference in map_refs:
                    st.write(f"• {reference}")
            else:
                st.caption(
                    "No page-level source reference is stored for this concept."
                )

            with st.expander(
                "Technical provenance",
                expanded=False,
            ):
                st.write(
                    "Proposal ID:",
                    selected_mapping["proposal_id"],
                )
                st.write(
                    "Mapping version:",
                    selected_mapping.get("mapping_version")
                    or "—",
                )
                st.write(
                    "Registry versions:",
                    ", ".join(
                        selected_mapping.get(
                            "taxonomy_registry_versions"
                        )
                        or []
                    )
                    or "—",
                )
                for passage_id in (
                    selected_mapping.get(
                        "evidence_passage_ids"
                    )
                    or []
                ):
                    st.code(
                        passage_id,
                        language=None,
                    )

        with map_evidence_right:
            map_locations = [
                parsed
                for parsed in (
                    parse_evidence_location(value)
                    for value in (
                        selected_mapping.get(
                            "evidence_locations"
                        )
                        or []
                    )
                )
                if parsed is not None
            ]

            if map_locations:
                map_sources = load_analysis_sources(
                    mapping_analysis_id
                )
                map_source_by_id = {
                    source["document_id"]: source
                    for source in map_sources
                }

                map_location_index = st.selectbox(
                    "Evidence page",
                    options=list(
                        range(len(map_locations))
                    ),
                    format_func=lambda index: format_evidence_location(
                        map_locations[index],
                        map_source_by_id.get(
                            map_locations[index][
                                "document_id"
                            ]
                        ),
                    ),
                    key=(
                        "mapping_evidence_page_"
                        + selected_mapping[
                            "proposal_id"
                        ]
                    ),
                )

                map_location = map_locations[
                    map_location_index
                ]
                map_source = map_source_by_id.get(
                    map_location["document_id"]
                )

                if map_source:
                    map_path = map_source.get(
                        "viewer_source_path"
                    )
                    map_type = str(
                        map_source.get("source_type")
                        or ""
                    ).upper()

                    if (
                        map_type == "PDF"
                        and map_path
                    ):
                        try:
                            map_pdf = download_source_file_as_user(
                                map_path
                            )
                            map_excerpt = pdf_page_range_bytes(
                                map_pdf,
                                map_location.get(
                                    "page_start"
                                ),
                                map_location.get(
                                    "page_end"
                                ),
                            )
                            st.pdf(
                                map_excerpt,
                                height=620,
                                key=(
                                    "mapping_pdf_"
                                    + hashlib.sha256(
                                        (
                                            selected_mapping[
                                                "proposal_id"
                                            ]
                                            + "|"
                                            + map_path
                                            + "|"
                                            + str(
                                                map_location.get(
                                                    "page_start"
                                                )
                                            )
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
                            "A citation exists, but this source is not "
                            "available as an embedded PDF."
                        )
            else:
                st.caption(
                    "No page-level evidence location is stored for this concept."
                )

        if latest_mapping:
            st.markdown("**Latest human review**")
            st.write(
                f"{latest_mapping['decision']} · "
                f"{latest_mapping['reviewed_at']} · "
                f"{latest_mapping['reviewer_email'] or latest_mapping['reviewer_username'] or 'unknown'}"
            )

            if latest_mapping.get("amended_code_value"):
                st.write(
                    "Human amendment:",
                    (
                        (
                            latest_mapping.get(
                                "amended_entity_path"
                            )
                            or "EMCIP"
                        )
                        + " → "
                        + (
                            latest_mapping.get(
                                "amended_attribute_name"
                            )
                            or ""
                        )
                        + " → "
                        + latest_mapping[
                            "amended_code_value"
                        ]
                        + " ["
                        + str(
                            latest_mapping.get(
                                "amended_code_idcode"
                            )
                            or "—"
                        )
                        + "]"
                    ),
                )

            if latest_mapping.get("review_comment"):
                st.write(
                    "Comment:",
                    latest_mapping["review_comment"],
                )

        st.divider()

        with st.form(
            (
                "generic_emcip_review_form_"
                + selected_mapping["proposal_id"]
            )
        ):
            mapping_decision = st.radio(
                "Human mapping decision",
                options=[
                    "VALIDATED",
                    "REJECTED",
                    "AMENDED",
                ],
                horizontal=True,
                key=(
                    "generic_mapping_decision_"
                    + selected_mapping["proposal_id"]
                ),
            )

            amended_candidate = None

            if mapping_decision == "AMENDED":
                if candidate_options:
                    amended_candidate_index = st.selectbox(
                        "Replacement governed EMCIP candidate",
                        options=list(
                            range(len(candidate_options))
                        ),
                        format_func=lambda index: (
                            (
                                candidate_options[index].get(
                                    "entity_path"
                                )
                                or "EMCIP"
                            )
                            + " → "
                            + (
                                candidate_options[index].get(
                                    "attribute_name"
                                )
                                or ""
                            )
                            + " → "
                            + (
                                candidate_options[index].get(
                                    "code_value"
                                )
                                or ""
                            )
                            + " ["
                            + str(
                                candidate_options[index].get(
                                    "code_idcode"
                                )
                                or "—"
                            )
                            + "]"
                        ),
                        key=(
                            "mapping_amend_candidate_"
                            + selected_mapping[
                                "proposal_id"
                            ]
                        ),
                    )
                    amended_candidate = candidate_options[
                        amended_candidate_index
                    ]
                else:
                    st.warning(
                        "No governed shortlist candidate is available for "
                        "an amended mapping."
                    )

            mapping_comment = st.text_area(
                "Mapping review comment",
                placeholder=(
                    "Optional for validation; recommended for rejection "
                    "or amendment."
                ),
                key=(
                    "generic_mapping_comment_"
                    + selected_mapping["proposal_id"]
                ),
            )

            mapping_reviewer = get_reviewer_identity()
            mapping_reviewer_display = (
                mapping_reviewer["email"]
                if mapping_reviewer["email"] != "unknown"
                else mapping_reviewer["username"]
            )
            st.caption(
                "Reviewer recorded as: "
                + mapping_reviewer_display
            )

            mapping_save_disabled = (
                mapping_decision == "AMENDED"
                and amended_candidate is None
            )

            mapping_submitted = st.form_submit_button(
                "Save mapping review",
                type="primary",
                disabled=mapping_save_disabled,
            )

        if mapping_submitted:
            try:
                mapping_review_id = save_analysis_mapping_review(
                    selected_mapping,
                    decision=mapping_decision,
                    amended_candidate=amended_candidate,
                    comment=mapping_comment.strip(),
                )

                load_latest_analysis_mapping_reviews.clear()

                st.success(
                    "Mapping review saved: "
                    + mapping_decision
                    + " — review ID "
                    + mapping_review_id
                )
                st.rerun()

            except Exception as exc:
                st.error(
                    "The generic EMCIP mapping review could not be saved."
                )
                st.exception(exc)

    st.divider()
    st.markdown("### 3. SHIELD classification review")
    st.caption(
        "Gate 1: the contributing factor relationship must already be human "
        "validated as CONTRIBUTED_TO. Gate 2: the SHIELD suggestion requires "
        "its own human validation. Assistant proposals never overwrite the graph."
    )

    shield_analysis_id = mapping_analysis_id
    shield_model_run_id = mapping_model_run_id

    shield_eligible = (
        load_shield_gate_eligible_factors(
            shield_analysis_id,
            shield_model_run_id,
        )
        if (
            shield_analysis_id
            and shield_model_run_id
        )
        else []
    )

    shield_gate_col, shield_job_col = st.columns(
        [1, 1]
    )
    shield_gate_col.metric(
        "Gate-1 eligible factors",
        len(shield_eligible),
    )

    shield_documents = load_shield_documents()
    shield_job_col.metric(
        "SHIELD source documents",
        len(shield_documents),
    )

    if not shield_documents:
        st.warning(
            "The persistent SHIELD corpus is not indexed yet. "
            "Run notebook 45 during the consolidated Databricks setup."
        )

    shield_action_left, shield_action_right = st.columns(
        [1, 1]
    )

    with shield_action_left:
        generate_shield = st.button(
            "Generate / refresh SHIELD proposals",
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

    with shield_action_right:
        refresh_shield = st.button(
            "Refresh SHIELD status",
            disabled=(
                not shield_analysis_id
                or not shield_model_run_id
            ),
            key="refresh_shield_status",
        )

    if not SHIELD_PROPOSAL_JOB_ID:
        st.caption(
            "The SHIELD proposal Job is not attached to this App deployment "
            "yet. Source code is ready; runtime setup uses resource key "
            "shield_proposal_job."
        )

    if (
        shield_analysis_id
        and shield_model_run_id
        and not shield_eligible
    ):
        st.info(
            "No contributing factor currently passes Gate 1. "
            "Validate a ContributingFactor — CONTRIBUTED_TO → target "
            "relationship first."
        )

    if refresh_shield:
        load_shield_gate_eligible_factors.clear()
        load_shield_proposals.clear()
        load_latest_shield_reviews.clear()
        load_shield_documents.clear()
        st.toast("SHIELD status refreshed")

    if generate_shield:
        try:
            shield_job_run_id = trigger_shield_proposal_job(
                shield_analysis_id,
                shield_model_run_id,
            )
            load_shield_proposals.clear()
            st.success(
                "SHIELD proposal generation queued."
            )
            st.caption(
                "Databricks run: "
                + shield_job_run_id
            )
        except Exception as exc:
            st.error(
                "SHIELD proposal generation could not be queued."
            )
            st.exception(exc)

    shield_proposals = (
        load_shield_proposals(
            shield_analysis_id,
            shield_model_run_id,
        )
        if (
            shield_analysis_id
            and shield_model_run_id
        )
        else []
    )

    latest_shield_reviews = (
        load_latest_shield_reviews(
            shield_analysis_id,
            shield_model_run_id,
        )
        if (
            shield_analysis_id
            and shield_model_run_id
        )
        else {}
    )

    s1, s2, s3 = st.columns(3)
    s1.metric(
        "SHIELD proposals",
        len(shield_proposals),
    )
    s2.metric(
        "Human reviewed",
        len(latest_shield_reviews),
    )
    s3.metric(
        "Remaining",
        max(
            0,
            len(shield_proposals)
            - len(latest_shield_reviews),
        ),
    )

    if shield_proposals:
        def shield_option_label(index):
            proposal = shield_proposals[index]
            latest_shield = latest_shield_reviews.get(
                proposal["proposal_id"]
            )

            marker = ""
            if latest_shield:
                marker = {
                    "VALIDATED": "✓ ",
                    "REJECTED": "✕ ",
                    "AMENDED": "✎ ",
                }.get(
                    latest_shield["decision"],
                    "• ",
                )

            stale = (
                " [STALE]"
                if not proposal.get(
                    "gate_is_current"
                )
                else ""
            )

            proposed = (
                proposal.get(
                    "proposed_shield_label"
                )
                or "NO_GROUNDED_PROPOSAL"
            )

            return (
                marker
                + proposal["factor_label"]
                + " → "
                + proposed
                + stale
            )

        selected_shield_index = st.selectbox(
            "SHIELD proposal",
            options=list(
                range(
                    len(shield_proposals)
                )
            ),
            format_func=shield_option_label,
            key="shield_proposal_selector",
        )

        selected_shield = shield_proposals[
            selected_shield_index
        ]
        latest_shield = latest_shield_reviews.get(
            selected_shield[
                "proposal_id"
            ]
        )

        sh1, sh2 = st.columns(2)
        with sh1:
            st.markdown(
                "**Human-validated contributing factor**"
            )
            st.write(
                selected_shield[
                    "factor_label"
                ]
            )
            st.caption(
                "Contributes to: "
                + (
                    selected_shield.get(
                        "target_label"
                    )
                    or "—"
                )
            )
            st.caption(
                "Gate-1 review: "
                + (
                    selected_shield.get(
                        "gate_review_id"
                    )
                    or "—"
                )
            )

        with sh2:
            st.markdown(
                "**Assistant SHIELD proposal**"
            )
            if (
                selected_shield.get(
                    "assistant_status"
                )
                == "ASSISTANT_PROPOSED"
            ):
                proposed_parts = [
                    selected_shield.get(
                        "proposed_shield_path"
                    ),
                    selected_shield.get(
                        "proposed_shield_label"
                    ),
                ]
                proposed_text = " → ".join(
                    part
                    for part in proposed_parts
                    if part
                )
                if selected_shield.get(
                    "proposed_shield_code"
                ):
                    proposed_text += (
                        " ["
                        + selected_shield[
                            "proposed_shield_code"
                        ]
                        + "]"
                    )
                st.info(
                    proposed_text
                    or "SHIELD proposal"
                )
            else:
                st.warning(
                    "NO_GROUNDED_PROPOSAL"
                )

            st.caption(
                "Corpus snapshot: "
                + (
                    selected_shield.get(
                        "shield_corpus_snapshot_id"
                    )
                    or "—"
                )
            )

        if not selected_shield.get(
            "gate_is_current"
        ):
            st.error(
                "Gate 1 has changed since this SHIELD proposal was generated. "
                "This proposal is stale and cannot be validated. Regenerate it."
            )

        if selected_shield.get(
            "rationale"
        ):
            st.caption(
                "Assistant rationale: "
                + selected_shield[
                    "rationale"
                ]
            )

        st.markdown(
            "**SHIELD taxonomy evidence**"
        )
        shield_refs = (
            selected_shield.get(
                "shield_references"
            )
            or []
        )
        for reference in shield_refs:
            st.write(
                "• " + reference
            )

        shield_locations = [
            parsed
            for parsed in (
                parse_evidence_location(
                    value
                )
                for value in (
                    selected_shield.get(
                        "shield_locations"
                    )
                    or []
                )
            )
            if parsed is not None
        ]

        if shield_locations:
            shield_source_by_id = {
                item[
                    "shield_document_id"
                ]: item
                for item in shield_documents
            }

            shield_location_index = st.selectbox(
                "SHIELD source page",
                options=list(
                    range(
                        len(
                            shield_locations
                        )
                    )
                ),
                format_func=lambda index: format_evidence_location(
                    shield_locations[
                        index
                    ],
                    shield_source_by_id.get(
                        shield_locations[
                            index
                        ][
                            "document_id"
                        ]
                    ),
                ),
                key=(
                    "shield_source_page_"
                    + selected_shield[
                        "proposal_id"
                    ]
                ),
            )

            shield_location = shield_locations[
                shield_location_index
            ]
            shield_source = shield_source_by_id.get(
                shield_location[
                    "document_id"
                ]
            )

            if shield_source:
                shield_path = shield_source.get(
                    "viewer_source_path"
                )
                shield_type = str(
                    shield_source.get(
                        "source_type"
                    )
                    or ""
                ).upper()

                if (
                    shield_type == "PDF"
                    and shield_path
                ):
                    try:
                        shield_pdf = download_source_file_as_user(
                            shield_path
                        )
                        shield_excerpt = pdf_page_range_bytes(
                            shield_pdf,
                            shield_location.get(
                                "page_start"
                            ),
                            shield_location.get(
                                "page_end"
                            ),
                        )
                        st.pdf(
                            shield_excerpt,
                            height=620,
                            key=(
                                "shield_taxonomy_pdf_"
                                + hashlib.sha256(
                                    (
                                        selected_shield[
                                            "proposal_id"
                                        ]
                                        + "|"
                                        + shield_path
                                        + "|"
                                        + str(
                                            shield_location.get(
                                                "page_start"
                                            )
                                        )
                                    ).encode(
                                        "utf-8"
                                    )
                                ).hexdigest()[:16]
                            ),
                        )
                    except PermissionError as exc:
                        st.warning(
                            str(exc)
                        )
                    except Exception as exc:
                        st.caption(
                            "The SHIELD source page could not be rendered: "
                            + str(exc)
                        )

        if latest_shield:
            st.markdown(
                "**Latest Gate-2 human review**"
            )
            st.write(
                latest_shield[
                    "decision"
                ]
                + " · "
                + (
                    latest_shield.get(
                        "reviewed_at"
                    )
                    or "—"
                )
            )
            if latest_shield.get(
                "amended_shield_label"
            ):
                st.write(
                    "Amended SHIELD:",
                    latest_shield[
                        "amended_shield_label"
                    ],
                )
            if latest_shield.get(
                "review_comment"
            ):
                st.write(
                    "Comment:",
                    latest_shield[
                        "review_comment"
                    ],
                )

        review_enabled = (
            selected_shield.get(
                "assistant_status"
            )
            == "ASSISTANT_PROPOSED"
            and selected_shield.get(
                "gate_is_current"
            )
        )

        if not review_enabled:
            st.caption(
                "Gate-2 review is enabled only for a grounded, current SHIELD proposal."
            )
        else:
            with st.form(
                "shield_review_form_"
                + selected_shield[
                    "proposal_id"
                ]
            ):
                shield_decision = st.radio(
                    "SHIELD human decision",
                    options=[
                        "VALIDATED",
                        "REJECTED",
                        "AMENDED",
                    ],
                    horizontal=True,
                )

                amended_label = ""
                amended_code = ""
                amended_path = ""

                if shield_decision == "AMENDED":
                    amended_label = st.text_input(
                        "Amended SHIELD label",
                    )
                    amended_code = st.text_input(
                        "Amended SHIELD code (optional)",
                    )
                    amended_path = st.text_input(
                        "Amended SHIELD path / hierarchy (optional)",
                    )
                    st.caption(
                        "Use the SHIELD source page above when amending. "
                        "The human amendment, not the assistant proposal, "
                        "becomes the authoritative reviewed value."
                    )

                shield_comment = st.text_area(
                    "SHIELD review comment",
                    placeholder=(
                        "Optional for validation; recommended for rejection "
                        "or amendment."
                    ),
                )

                shield_submitted = st.form_submit_button(
                    "Save SHIELD review",
                    type="primary",
                    disabled=(
                        shield_decision == "AMENDED"
                        and not amended_label.strip()
                    ),
                )

            if shield_submitted:
                try:
                    shield_review_id = save_shield_review(
                        selected_shield,
                        decision=shield_decision,
                        amended_label=amended_label,
                        amended_code=amended_code,
                        amended_path=amended_path,
                        comment=shield_comment.strip(),
                    )
                    load_latest_shield_reviews.clear()
                    st.success(
                        "SHIELD review saved: "
                        + shield_decision
                        + " — review ID "
                        + shield_review_id
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(
                        "The SHIELD review could not be saved."
                    )
                    st.exception(exc)
    elif (
        shield_analysis_id
        and shield_model_run_id
        and shield_eligible
    ):
        st.info(
            "Gate-1 validated contributing factors are available, but no "
            "SHIELD proposals have been generated yet."
        )

with tab_about:
    st.markdown(
        f"""
### Current Proof of Concept

IKF separates the investigator workflow into four distinct operational
capabilities:

1. **Analyse Documents** — prepare governed evidence and inspect structured
   analytical outputs without requiring an initial question.
2. **Ask / Compare LLMs** — pose free-text questions against a completed
   evidence set, optionally compare approved model routes, and retain citations.
3. **Findings & Knowledge** — read-only exploration of extracted knowledge,
   evidence, the graph and deterministic similar-case retrieval.
4. **Review & Validate** — human governance of relationships, assistant
   correction proposals, EMCIP mappings and SHIELD classifications.

News & Alerts remains a separate external-signal capability and is not silently
mixed with validated investigation knowledge.

### Source ownership

- Class B published investigation material is sourced from MAIRA.
- Classes A/C/D use the governed IKF-managed source routes.
- REFERENCE_CONTEXT is a separate legal/IMO/technical layer and cannot prove a
  case fact.
- SHIELD remains a separate persistent taxonomy corpus.

### Human governance

Assistant outputs are proposals. Human relationship, EMCIP and SHIELD review
records remain append-only and authoritative according to their governed
workflow. Assistant correction checks never overwrite graph edges.

### Class D

Class D may use GPT-OSS 20B, Llama 3.3 70B, or both against the same prepared
evidence set. Llama 3.3 70B is limited to
**{LLAMA_DAILY_QUESTION_LIMIT} questions per user per day** in the PoC.

### Validation status

The consolidated release preflight has passed with zero warnings and zero
errors. SHIELD and authoritative REFERENCE_CONTEXT corpora are indexed.
Functional runtime validation proceeds capability by capability.

The Commodore Clipper material remains a validation/reference asset in the
project data and documentation; it is no longer presented as a primary
operational App capability.

### Compliance and privacy

Class D processing is intended to respect the confidentiality requirements of
Article 9 of Directive 2009/18/EC through controlled model routing,
least-privilege storage, encrypted direct-text ingress, evidence provenance,
de-identified output by default and a privacy-validation gate.

This PoC is design-aligned / conditionally aligned and does not constitute a
legal certification of compliance.

### Documentation

Key project documents:

- `docs/README.md` — current documentation index
- `docs/01_current_poc_scope.md`
- `docs/15_data_protection_confidentiality.md`
- `docs/17_class_d_dual_model_poc.md`
- `docs/18_model_validation_and_feedback.md`
- `docs/25_implementation_status_and_roadmap.md`
- `docs/26_consolidated_runtime_validation.md`
        """
    )
