# Databricks notebook source
# MAGIC %md
# MAGIC # 36 — Ask processed evidence
# MAGIC
# MAGIC Executes one persisted QuestionRun against an already processed IKF
# MAGIC evidence set.
# MAGIC
# MAGIC Important boundaries:
# MAGIC - does not extract source documents;
# MAGIC - does not rebuild or modify the case knowledge graph;
# MAGIC - does not create new source passage identities;
# MAGIC - answers only from the selected analysis passages;
# MAGIC - persists document/page citations and passage IDs;
# MAGIC - supports one approved model or the existing Class-D dual-model choice.
# MAGIC
# MAGIC Until governed MAIRA retrieval is connected, oversized evidence scopes
# MAGIC fail clearly instead of being silently truncated.

# COMMAND ----------

dbutils.widgets.text(
    "question_run_id",
    "",
    "Question run ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 databricks-sdk==0.139.0 cryptography==46.0.2

# COMMAND ----------

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from cryptography.fernet import Fernet
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ChatMessage,
    ChatMessageRole,
)
from neo4j import GraphDatabase
from pyspark.sql import functions as F

QUESTION_RUN_VERSION = "IKF_QUESTION_RUN_V0.1"
ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"

MAX_SCOPE_PASSAGES = 80
MAX_SCOPE_CHARS = 120000

question_run_id = dbutils.widgets.get(
    "question_run_id"
).strip()

if not re.fullmatch(
    r"question_[0-9a-f]{32}",
    question_run_id,
):
    raise ValueError(
        "Enter a valid question_run_id created by the App."
    )

# COMMAND ----------

NEO4J_URI = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_uri",
)
NEO4J_USERNAME = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_username",
)
NEO4J_PASSWORD = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_password",
)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

w = WorkspaceClient()

print("Question run:", question_run_id)
print("Neo4j connection: OK")

# IKF query runner import path + sibling MAIRA source discovery.
#
# GitHub remains authoritative; the workspace Git folders are only runtime
# imports for the PoC jobs.
current_notebook_path = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
workspace_notebook_path = (
    "/Workspace" + current_notebook_path
    if current_notebook_path.startswith("/Users/")
    else current_notebook_path
)
ikf_repo_root = workspace_notebook_path.rsplit(
    "/notebooks/",
    1,
)[0]
ikf_src_path = os.path.join(
    ikf_repo_root,
    "src",
)

if ikf_src_path not in sys.path:
    sys.path.insert(0, ikf_src_path)

maira_import_error = None

try:
    import maira  # noqa: F401
except ModuleNotFoundError as exc:
    maira_import_error = exc
    workspace_user_root = ikf_repo_root.rsplit(
        "/",
        1,
    )[0]

    for candidate_name in (
        "MAIRA",
        "MAIRA-main",
    ):
        candidate = os.path.join(
            workspace_user_root,
            candidate_name,
            "src",
        )
        if os.path.isdir(candidate):
            sys.path.insert(0, candidate)
            try:
                import maira  # noqa: F401
                maira_import_error = None
                break
            except ModuleNotFoundError as retry_exc:
                maira_import_error = retry_exc

# COMMAND ----------

with driver.session() as session:
    record = session.run(
        """
        MATCH (a:AnalysisGroup)-[:HAS_QUESTION_RUN]->(
            q:QuestionRun {question_run_id: $question_run_id}
        )
        OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
        WITH a, q, collect({
            document_id: d.document_id,
            filename: d.filename,
            source_managed_by: coalesce(
                properties(d)["source_managed_by"],
                "IKF"
            ),
            maira_document_role: properties(d)["maira_document_role"]
        }) AS documents
        RETURN
            a.analysis_id AS analysis_id,
            a.analysis_title AS analysis_title,
            properties(a)["information_class"] AS information_class,
            a.output_language AS output_language,
            properties(a)["input_mode"] AS input_mode,
            q.scope_mode AS scope_mode,
            coalesce(q.scope_document_ids, []) AS scope_document_ids,
            q.model_keys AS model_keys,
            q.model_services AS model_services,
            q.question_text AS question_text,
            q.encrypted_question_text AS encrypted_question_text,
            q.question_encryption_scheme AS question_encryption_scheme,
            documents
        """,
        question_run_id=question_run_id,
    ).single()

if record is None:
    driver.close()
    raise ValueError(
        f"QuestionRun not found: {question_run_id}"
    )

question_run = record.data()
analysis_id = question_run["analysis_id"]
information_class = (
    question_run.get("information_class")
    or "B"
)
scope_mode = question_run.get("scope_mode") or "WHOLE_CASE"
scope_document_ids = list(
    question_run.get("scope_document_ids")
    or []
)
model_keys = list(
    question_run.get("model_keys")
    or []
)
model_services = list(
    question_run.get("model_services")
    or []
)

if not model_keys or len(model_keys) != len(model_services):
    driver.close()
    raise ValueError(
        "QuestionRun has an invalid model plan."
    )

document_names = {
    item["document_id"]: item["filename"]
    for item in question_run.get("documents") or []
    if item.get("document_id")
}

# COMMAND ----------

if information_class == "D":
    encrypted_question = (
        question_run.get("encrypted_question_text")
        or ""
    )

    if not encrypted_question:
        driver.close()
        raise ValueError(
            "Class D QuestionRun does not contain an encrypted question."
        )

    encryption_key = dbutils.secrets.get(
        scope="kg-poc-app",
        key="direct_text_encryption_key",
    )

    question_text = (
        Fernet(encryption_key.encode("utf-8"))
        .decrypt(
            encrypted_question.encode("utf-8")
        )
        .decode("utf-8")
    )
else:
    question_text = str(
        question_run.get("question_text")
        or ""
    ).strip()

if not question_text:
    driver.close()
    raise ValueError(
        "Question text is empty."
    )

print("Analysis:", analysis_id)
print("Scope:", scope_mode)
print("Scoped documents:", len(scope_document_ids))
print("Models:", model_keys)

# Exact governed-query recognition.
#
# Arbitrary free-text questions are NOT semantically forced into a governed
# query spec. Only exact normalized matches to persisted MAIRA user_query values
# activate this path.
governed_query_id = None
governed_query_spec_id = None
governed_relationship = None
retrieval_mode = "SCOPED_ALL_PASSAGES"

if (
    information_class == "B"
    and spark.catalog.tableExists(
        "bdw_analysis_prod.maira.query_specifications"
    )
):
    normalized_question = " ".join(
        question_text.casefold().split()
    )

    governed_matches = [
        row.asDict(recursive=True)
        for row in (
            spark.table(
                "bdw_analysis_prod.maira.query_specifications"
            )
            .select(
                "query_id",
                "query_spec_id",
                "user_query",
                "relationship",
            )
            .collect()
        )
        if " ".join(
            str(row["user_query"] or "")
            .casefold()
            .split()
        )
        == normalized_question
    ]

    if len(governed_matches) > 1:
        driver.close()
        raise RuntimeError(
            "More than one persisted governed MAIRA query matched the "
            "normalized question. Resolve the governance ambiguity first."
        )

    if len(governed_matches) == 1:
        governed = governed_matches[0]
        governed_query_id = governed["query_id"]
        governed_query_spec_id = governed["query_spec_id"]
        governed_relationship = governed["relationship"]

        print(
            "Exact governed query recognized:",
            governed_query_id,
            governed_relationship,
        )

# COMMAND ----------

passages = (
    spark.table(ANALYSIS_PASSAGE_TABLE)
    .filter(F.col("analysis_id") == analysis_id)
)

if scope_mode in {
    "ONE_DOCUMENT",
    "SELECTED_DOCUMENTS",
}:
    if not scope_document_ids:
        driver.close()
        raise ValueError(
            "Document-scoped QuestionRun has no document IDs."
        )

    passages = passages.filter(
        F.col("document_id").isin(scope_document_ids)
    )

passage_rows = (
    passages
    .select(
        "document_id",
        "passage_id",
        "page_start",
        "page_end",
        "passage_order",
        "detected_language",
        "passage_text",
    )
    .orderBy(
        "document_id",
        "passage_order",
    )
    .collect()
)

if governed_query_id is not None:
    if maira_import_error is not None:
        message = (
            "An exact governed MAIRA query was recognized, but the MAIRA "
            "runtime package is not importable by the Ask Job. The governed "
            "path fails closed rather than falling back to an ungoverned answer."
        )
        with driver.session() as session:
            session.run(
                """
                MATCH (q:QuestionRun {
                    question_run_id: $question_run_id
                })
                SET
                    q.status = 'FAILED',
                    q.processing_stage = 'GOVERNED_RUNTIME_UNAVAILABLE',
                    q.processing_error = $message,
                    q.governed_query_id = $governed_query_id,
                    q.governed_query_spec_id = $governed_query_spec_id,
                    q.updated_at = datetime()
                """,
                question_run_id=question_run_id,
                message=message,
                governed_query_id=governed_query_id,
                governed_query_spec_id=governed_query_spec_id,
            ).consume()
        driver.close()
        raise RuntimeError(message)

    from ikf.query_runner import run_query

    scoped_document_ids = sorted(
        {
            row["document_id"]
            for row in passage_rows
        }
    )

    governed_results = run_query(
        spark,
        governed_query_id,
        document_ids=scoped_document_ids,
    )

    governed_passage_ids = sorted(
        {
            item["passage_id"]
            for item in governed_results
        }
    )

    with driver.session() as session:
        session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })
            SET
                q.governed_query_id = $governed_query_id,
                q.governed_query_spec_id = $governed_query_spec_id,
                q.governed_relationship = $governed_relationship,
                q.governed_retrieval_result_count = $result_count,
                q.retrieval_mode = $retrieval_mode,
                q.updated_at = datetime()
            """,
            question_run_id=question_run_id,
            governed_query_id=governed_query_id,
            governed_query_spec_id=governed_query_spec_id,
            governed_relationship=governed_relationship,
            result_count=len(governed_results),
            retrieval_mode="GOVERNED_RELATIONSHIP_EVIDENCE",
        ).consume()

    if not governed_passage_ids:
        deterministic_answer = (
            "No explicit source-language evidence supporting the governed "
            f"{governed_relationship} relationship was found within the "
            "selected evidence scope."
        )

        with driver.session() as session:
            session.run(
                """
                MATCH (q:QuestionRun {
                    question_run_id: $question_run_id
                })
                SET
                    q.status = 'COMPLETED',
                    q.processing_stage = 'COMPLETED',
                    q.retrieval_mode = 'GOVERNED_RELATIONSHIP_EVIDENCE',
                    q.deterministic_answer = $deterministic_answer,
                    q.insufficient_evidence = true,
                    q.completed_at = datetime(),
                    q.updated_at = datetime()
                """,
                question_run_id=question_run_id,
                deterministic_answer=deterministic_answer,
            ).consume()

        print("")
        print("QUESTION RUN: COMPLETED — NO GOVERNED SUPPORT")
        print("governed_query_id:", governed_query_id)
        driver.close()
        dbutils.notebook.exit(
            "COMPLETED_NO_GOVERNED_SUPPORT"
        )

    passage_rows = [
        row
        for row in passage_rows
        if row["passage_id"]
        in set(governed_passage_ids)
    ]
    retrieval_mode = "GOVERNED_RELATIONSHIP_EVIDENCE"

if not passage_rows:
    with driver.session() as session:
        session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })
            SET
                q.status = 'FAILED',
                q.processing_stage = 'NO_SCOPED_EVIDENCE',
                q.processing_error = 'No persisted evidence passages matched the selected scope.',
                q.updated_at = datetime()
            """,
            question_run_id=question_run_id,
        ).consume()

    driver.close()
    raise ValueError(
        "No persisted evidence passages matched the selected scope."
    )

scope_chars = sum(
    len(row["passage_text"] or "")
    for row in passage_rows
)

if (
    len(passage_rows) > MAX_SCOPE_PASSAGES
    or scope_chars > MAX_SCOPE_CHARS
):
    message = (
        "The selected evidence scope is too large for the temporary "
        "all-passages Ask path. Governed retrieval must narrow the scope "
        "before this question can be answered without silent truncation. "
        f"passages={len(passage_rows)}; chars={scope_chars}"
    )

    with driver.session() as session:
        session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })
            SET
                q.status = 'FAILED',
                q.processing_stage = 'GOVERNED_RETRIEVAL_REQUIRED',
                q.processing_error = $message,
                q.updated_at = datetime()
            """,
            question_run_id=question_run_id,
            message=message,
        ).consume()

    driver.close()
    raise RuntimeError(message)

print("Scoped passages:", len(passage_rows))
print("Scoped characters:", scope_chars)

# COMMAND ----------

def format_page_reference(page_start, page_end):
    if page_start is None:
        return "page unknown"
    if page_end is None or page_end == page_start:
        return f"p. {page_start}"
    return f"pp. {page_start}–{page_end}"


passage_by_id = {
    row["passage_id"]: row
    for row in passage_rows
}


def evidence_references(passage_ids):
    refs = []
    seen = set()

    for passage_id in passage_ids:
        row = passage_by_id.get(passage_id)
        if row is None:
            continue

        filename = (
            document_names.get(row["document_id"])
            or (
                "Direct text"
                if str(row["document_id"]).startswith("text_")
                else row["document_id"]
            )
        )
        page_reference = format_page_reference(
            row["page_start"],
            row["page_end"],
        )

        key = (
            row["document_id"],
            row["page_start"],
            row["page_end"],
        )
        if key in seen:
            continue
        seen.add(key)

        refs.append(
            f"{filename} · {page_reference}"
        )

    return refs


def evidence_locations(passage_ids):
    locations = []
    seen = set()

    for passage_id in passage_ids:
        row = passage_by_id.get(passage_id)
        if row is None:
            continue

        key = (
            row["document_id"],
            row["page_start"],
            row["page_end"],
        )
        if key in seen:
            continue
        seen.add(key)

        page_start = (
            ""
            if row["page_start"] is None
            else str(row["page_start"])
        )
        page_end = (
            ""
            if row["page_end"] is None
            else str(row["page_end"])
        )

        locations.append(
            f"{row['document_id']}|{page_start}|{page_end}"
        )

    return locations


def passage_block(row):
    filename = (
        document_names.get(row["document_id"])
        or (
            "Direct text"
            if str(row["document_id"]).startswith("text_")
            else row["document_id"]
        )
    )

    return (
        f"[PASSAGE_ID: {row['passage_id']}]\n"
        f"[DOCUMENT: {filename}]\n"
        f"[DOCUMENT_ID: {row['document_id']}]\n"
        f"[PAGE_START: {row['page_start']}]\n"
        f"[PAGE_END: {row['page_end']}]\n"
        f"[LANGUAGE: {row['detected_language']}]\n"
        f"{row['passage_text']}"
    )

# COMMAND ----------

def extract_chat_final_text(content):
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if str(item.get("type") or "").lower() in {
                    "text",
                    "output_text",
                }:
                    value = item.get("text")
                    if value is not None:
                        parts.append(str(value))
        return "\n".join(parts)

    return str(content)


def strip_code_fences(text):
    value = (text or "").strip()
    fence = chr(96) * 3

    if value.startswith(fence):
        value = re.sub(
            r"^.{3}(?:json)?\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"\s*.{3}$",
            "",
            value,
        )

    return value.strip()


def call_model_json(
    *,
    model_key,
    model_service,
    system_prompt,
    user_prompt,
):
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    last_error = None

    for attempt in range(2):
        active_prompt = user_prompt

        if attempt:
            active_prompt += (
                "\n\nIMPORTANT: Return one valid JSON object only. "
                "Do not include Markdown fences or commentary."
            )

        if model_service.startswith("system.ai."):
            if not re.fullmatch(
                r"system\.ai\.[A-Za-z0-9._-]+",
                model_service,
            ):
                raise ValueError(
                    "Invalid system.ai model identifier."
                )

            request = urllib.request.Request(
                (
                    w.config.host.rstrip("/")
                    + "/ai-gateway/mlflow/v1/chat/completions"
                ),
                data=json.dumps(
                    {
                        "model": model_service,
                        "messages": [
                            {
                                "role": "system",
                                "content": system_prompt,
                            },
                            {
                                "role": "user",
                                "content": active_prompt,
                            },
                        ],
                        "max_tokens": 3500,
                        "temperature": 0.0,
                    }
                ).encode("utf-8"),
                headers={
                    **w.config.authenticate(),
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(
                    request,
                    timeout=600,
                ) as response:
                    payload = json.loads(
                        response.read().decode("utf-8")
                    )
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
                raise RuntimeError(
                    f"Unity Gateway request failed: HTTP {exc.code}: "
                    f"{body[:1000]}"
                ) from exc

            choices = payload.get("choices") or []
            if not choices:
                raise ValueError(
                    "Unity Gateway returned no answer choice."
                )

            text = extract_chat_final_text(
                choices[0]
                .get("message", {})
                .get("content")
            )

            api_usage = payload.get("usage") or {}
            for key in usage:
                usage[key] = int(
                    api_usage.get(key) or 0
                )

        else:
            response = w.serving_endpoints.query(
                name=model_service,
                messages=[
                    ChatMessage(
                        role=ChatMessageRole.SYSTEM,
                        content=system_prompt,
                    ),
                    ChatMessage(
                        role=ChatMessageRole.USER,
                        content=active_prompt,
                    ),
                ],
                temperature=0.0,
                max_tokens=3500,
            )

            text = extract_chat_final_text(
                response.choices[0].message.content
            )

            api_usage = getattr(
                response,
                "usage",
                None,
            )
            if api_usage is not None:
                usage = {
                    "prompt_tokens": int(
                        getattr(
                            api_usage,
                            "prompt_tokens",
                            0,
                        )
                        or 0
                    ),
                    "completion_tokens": int(
                        getattr(
                            api_usage,
                            "completion_tokens",
                            0,
                        )
                        or 0
                    ),
                    "total_tokens": int(
                        getattr(
                            api_usage,
                            "total_tokens",
                            0,
                        )
                        or 0
                    ),
                }

        try:
            return (
                json.loads(
                    strip_code_fences(text)
                ),
                usage,
            )
        except Exception as exc:
            last_error = exc

    raise ValueError(
        "Model response was not valid JSON after retry: "
        + str(last_error)
    )

# COMMAND ----------

EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"
)
PERSONAL_ID_RE = re.compile(
    r"\b(?:passport|national\s+id|identity\s+card|id\s+number)"
    r"\s*[:#-]?\s*[A-Z0-9-]{4,}\b",
    re.IGNORECASE,
)


def redact_direct_identifiers(value):
    text = str(value or "")
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = PERSONAL_ID_RE.sub(
        "[REDACTED_PERSONAL_ID]",
        text,
    )
    return text

# COMMAND ----------

SYSTEM_PROMPT = """
You answer an investigator's question using ONLY the supplied evidence
passages.

Rules:
1. Do not use general maritime knowledge to fill evidence gaps.
2. Every substantive answer must be supported by one or more supplied
   passage_ids.
3. Return only passage_ids that actually appear in the supplied evidence.
4. Distinguish chronology from causality. Sequence alone does not establish
   RESULTED_IN or CONTRIBUTED_TO.
5. If the selected evidence does not support an answer, say so explicitly.
6. Preserve uncertainty and conflicting source statements.
7. Do not expose unnecessary personal identifiers in the answer.
8. Return JSON only.

Required JSON:
{
  "answer": "concise evidence-grounded answer",
  "passage_ids": ["passage_..."],
  "insufficient_evidence": false,
  "limitations": ["..."]
}
"""

evidence_text = "\n\n---\n\n".join(
    passage_block(row)
    for row in passage_rows
)

user_prompt = (
    f"Case / analysis: {question_run['analysis_title']}\n"
    f"Evidence scope: {scope_mode}\n"
    f"Output language: {question_run.get('output_language') or 'English'}\n"
    f"Question: {question_text}\n\n"
    "Evidence passages:\n\n"
    + evidence_text
)

# COMMAND ----------

with driver.session() as session:
    session.run(
        """
        MATCH (q:QuestionRun {
            question_run_id: $question_run_id
        })
        SET
            q.status = 'RUNNING',
            q.processing_stage = 'ANSWERING',
            q.processing_error = NULL,
            q.evidence_passage_count = $passage_count,
            q.evidence_character_count = $character_count,
            q.question_run_version = $question_run_version,
            q.retrieval_mode = $retrieval_mode,
            q.governed_query_id = $governed_query_id,
            q.governed_query_spec_id = $governed_query_spec_id,
            q.updated_at = datetime()
        """,
        question_run_id=question_run_id,
        passage_count=len(passage_rows),
        character_count=scope_chars,
        question_run_version=QUESTION_RUN_VERSION,
        retrieval_mode=retrieval_mode,
        governed_query_id=governed_query_id,
        governed_query_spec_id=governed_query_spec_id,
    ).consume()

# COMMAND ----------

model_labels = {
    "DEFAULT": "Default model",
    "GPT20": "GPT-OSS 20B",
    "LLAMA70": "Llama 3.3 70B",
}

successful_keys = []
failed_keys = []

for model_key, model_service in zip(
    model_keys,
    model_services,
):
    started = time.perf_counter()

    with driver.session() as session:
        session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })
            MERGE (m:QuestionModelRun {
                question_model_run_id: $question_model_run_id
            })
            ON CREATE SET m.created_at = datetime()
            SET
                m.question_run_id = $question_run_id,
                m.model_key = $model_key,
                m.model_label = $model_label,
                m.model_service = $model_service,
                m.status = 'RUNNING',
                m.updated_at = datetime()
            MERGE (q)-[:HAS_MODEL_ANSWER]->(m)
            """,
            question_run_id=question_run_id,
            question_model_run_id=(
                question_run_id
                + "__"
                + model_key.lower()
            ),
            model_key=model_key,
            model_label=model_labels.get(
                model_key,
                model_key,
            ),
            model_service=model_service,
        ).consume()

    try:
        result, usage = call_model_json(
            model_key=model_key,
            model_service=model_service,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        answer_raw = str(
            result.get("answer") or ""
        ).strip()

        valid_ids = sorted(
            {
                str(value)
                for value in result.get(
                    "passage_ids",
                    [],
                )
                if str(value) in passage_by_id
            }
        )

        insufficient = bool(
            result.get("insufficient_evidence")
        )
        limitations = [
            str(item).strip()
            for item in result.get(
                "limitations",
                [],
            )
            if str(item).strip()
        ]

        if answer_raw and not valid_ids:
            insufficient = True
            limitations.append(
                "The model returned no valid supporting passage IDs."
            )
            answer_raw = (
                "The selected evidence does not contain a sufficiently "
                "grounded answer with valid source references."
            )

        if not answer_raw:
            insufficient = True
            answer_raw = (
                "The selected evidence does not provide a supported answer "
                "to this question."
            )

        answer = redact_direct_identifiers(
            answer_raw
        )
        references = evidence_references(
            valid_ids
        )
        locations = evidence_locations(
            valid_ids
        )
        duration = round(
            time.perf_counter() - started,
            3,
        )

        with driver.session() as session:
            session.run(
                """
                MATCH (m:QuestionModelRun {
                    question_model_run_id: $question_model_run_id
                })
                SET
                    m.status = 'COMPLETED',
                    m.answer = $answer,
                    m.passage_ids = $passage_ids,
                    m.evidence_references = $evidence_references,
                    m.evidence_locations = $evidence_locations,
                    m.insufficient_evidence = $insufficient_evidence,
                    m.limitations = $limitations,
                    m.duration_seconds = $duration_seconds,
                    m.prompt_tokens = $prompt_tokens,
                    m.completion_tokens = $completion_tokens,
                    m.total_tokens = $total_tokens,
                    m.privacy_output_mode = 'DE_IDENTIFIED_BY_DEFAULT',
                    m.completed_at = datetime(),
                    m.updated_at = datetime()
                """,
                question_model_run_id=(
                    question_run_id
                    + "__"
                    + model_key.lower()
                ),
                answer=answer,
                passage_ids=valid_ids,
                evidence_references=references,
                evidence_locations=locations,
                insufficient_evidence=insufficient,
                limitations=limitations,
                duration_seconds=duration,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
            ).consume()

        successful_keys.append(model_key)

    except Exception as exc:
        failed_keys.append(model_key)

        with driver.session() as session:
            session.run(
                """
                MATCH (m:QuestionModelRun {
                    question_model_run_id: $question_model_run_id
                })
                SET
                    m.status = 'FAILED',
                    m.processing_error = $error_message,
                    m.updated_at = datetime()
                """,
                question_model_run_id=(
                    question_run_id
                    + "__"
                    + model_key.lower()
                ),
                error_message=(
                    f"{type(exc).__name__}: {exc}"
                ),
            ).consume()

# COMMAND ----------

if failed_keys:
    final_status = "FAILED"
    final_stage = "MODEL_ANSWER_FAILED"
    final_error = (
        "Question model failure(s): "
        + ", ".join(failed_keys)
    )
else:
    final_status = "COMPLETED"
    final_stage = "COMPLETED"
    final_error = None

with driver.session() as session:
    session.run(
        """
        MATCH (q:QuestionRun {
            question_run_id: $question_run_id
        })
        SET
            q.status = $status,
            q.processing_stage = $processing_stage,
            q.processing_error = $processing_error,
            q.completed_model_keys = $completed_model_keys,
            q.failed_model_keys = $failed_model_keys,
            q.completed_at = CASE
                WHEN $status = 'COMPLETED'
                THEN datetime()
                ELSE q.completed_at
            END,
            q.updated_at = datetime()
        """,
        question_run_id=question_run_id,
        status=final_status,
        processing_stage=final_stage,
        processing_error=final_error,
        completed_model_keys=successful_keys,
        failed_model_keys=failed_keys,
    ).consume()

print("")
print("QUESTION RUN:", final_status)
print("question_run_id:", question_run_id)
print("analysis_id:", analysis_id)
print("successful models:", successful_keys)
print("failed models:", failed_keys)

driver.close()

if failed_keys:
    raise RuntimeError(final_error)
