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
# MAGIC Small scopes may use all selected passages. Large scopes use MAIRA's
# MAGIC deterministic free-text lexical retrieval baseline. Exact persisted
# MAGIC governed questions still use the stronger relationship-evidence path.

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

QUESTION_RUN_VERSION = "IKF_QUESTION_RUN_V0.5_DIRECT_REFERENCE"
ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"
REFERENCE_DOCUMENT_TABLE = "bdw_analysis_prod.kg_poc.reference_document"
REFERENCE_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.reference_passage"

MAX_SCOPE_PASSAGES = 80
MAX_SCOPE_CHARS = 120000
RETRIEVAL_MAX_PASSAGES = 40
RETRIEVAL_MAX_CHARS = 60000
REFERENCE_MAX_PASSAGES = 24
REFERENCE_MAX_CHARS = 30000

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
        MATCH (q:QuestionRun {
            question_run_id: $question_run_id
        })
        OPTIONAL MATCH (
            a:AnalysisGroup
        )-[:HAS_QUESTION_RUN]->(q)
        OPTIONAL MATCH (a)-[:HAS_SOURCE]->(
            d:SourceDocument
        )
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
            coalesce(
                properties(a)["information_class"],
                q.information_class,
                "A"
            ) AS information_class,
            coalesce(
                a.output_language,
                "English"
            ) AS output_language,
            properties(a)["input_mode"] AS input_mode,
            coalesce(
                q.interaction_surface,
                "ASK_COMPARE"
            ) AS interaction_surface,
            q.scope_mode AS scope_mode,
            coalesce(
                q.scope_document_ids,
                []
            ) AS scope_document_ids,
            coalesce(
                q.direct_reference_document_ids,
                []
            ) AS direct_reference_document_ids,
            coalesce(
                q.include_reference_context,
                false
            ) AS include_reference_context,
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
analysis_id = question_run.get(
    "analysis_id"
)
interaction_surface = (
    question_run.get(
        "interaction_surface"
    )
    or "ASK_COMPARE"
)
direct_document_ask = (
    interaction_surface
    == "DIRECT_DOCUMENT_ASK"
)
information_class = (
    question_run.get("information_class")
    or "A"
)
scope_mode = (
    question_run.get("scope_mode")
    or "WHOLE_CASE"
)
scope_document_ids = list(
    question_run.get(
        "scope_document_ids"
    )
    or []
)
direct_reference_document_ids = list(
    question_run.get(
        "direct_reference_document_ids"
    )
    or []
)
include_reference_context = bool(
    question_run.get(
        "include_reference_context"
    )
)
model_keys = list(
    question_run.get(
        "model_keys"
    )
    or []
)
model_services = list(
    question_run.get(
        "model_services"
    )
    or []
)

if (
    not direct_document_ask
    and not analysis_id
):
    driver.close()
    raise ValueError(
        "Non-direct QuestionRun is not linked to an AnalysisGroup."
    )

if (
    direct_document_ask
    and not direct_reference_document_ids
):
    driver.close()
    raise ValueError(
        "Direct document QuestionRun has no selected reference documents."
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

reference_document_names = {}

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
print("Reference context requested:", include_reference_context)
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

if direct_document_ask:
    passage_rows = []
    retrieval_mode = "DIRECT_REFERENCE_ONLY"
    retrieval_passage_ids = []
    retrieval_snapshot_id = None

    with driver.session() as session:
        session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })
            SET
                q.retrieval_mode = 'DIRECT_REFERENCE_ONLY',
                q.retrieval_passage_ids = [],
                q.updated_at = datetime()
            """,
            question_run_id=question_run_id,
        ).consume()

    print(
        "Primary case retrieval: skipped "
        "(direct governed reference-document question)"
    )
else:
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
    
            snapshot_payload = {
                "analysis_id": analysis_id,
                "question_sha256": hashlib.sha256(
                    question_text.encode("utf-8")
                ).hexdigest(),
                "scope_mode": scope_mode,
                "scope_document_ids": sorted(
                    scope_document_ids
                ),
                "retrieval_mode": "GOVERNED_RELATIONSHIP_EVIDENCE",
                "governed_query_id": governed_query_id,
                "governed_query_spec_id": governed_query_spec_id,
                "retrieval_passage_ids": [],
            }
            retrieval_snapshot_id = (
                "snapshot_"
                + hashlib.sha256(
                    json.dumps(
                        snapshot_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()[:32]
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
                        q.retrieval_snapshot_id = $retrieval_snapshot_id,
                        q.retrieval_passage_ids = [],
                        q.completed_at = datetime(),
                        q.updated_at = datetime()
                    """,
                    question_run_id=question_run_id,
                    deterministic_answer=deterministic_answer,
                    retrieval_snapshot_id=retrieval_snapshot_id,
                ).consume()
    
            print("")
            print("QUESTION RUN: COMPLETED — NO GOVERNED SUPPORT")
            print("governed_query_id:", governed_query_id)
            print("retrieval_snapshot_id:", retrieval_snapshot_id)
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
        governed_query_id is None
        and (
            len(passage_rows) > MAX_SCOPE_PASSAGES
            or scope_chars > MAX_SCOPE_CHARS
        )
    ):
        if maira_import_error is not None:
            message = (
                "The selected evidence scope requires deterministic retrieval, "
                "but the reusable MAIRA retrieval package is not importable by "
                "the Ask Job."
            )
            with driver.session() as session:
                session.run(
                    """
                    MATCH (q:QuestionRun {
                        question_run_id: $question_run_id
                    })
                    SET
                        q.status = 'FAILED',
                        q.processing_stage = 'RETRIEVAL_RUNTIME_UNAVAILABLE',
                        q.processing_error = $message,
                        q.updated_at = datetime()
                    """,
                    question_run_id=question_run_id,
                    message=message,
                ).consume()
            driver.close()
            raise RuntimeError(message)
    
        from maira.retrieval import retrieve_free_text
    
        expansion_map = {}
    
        if (
            information_class == "B"
            and spark.catalog.tableExists(
                "bdw_analysis_prod.maira.terminology_normalisations"
            )
            and spark.catalog.tableExists(
                "bdw_analysis_prod.maira.emcip_operational_registry"
            )
        ):
            validated_terms = (
                spark.table(
                    "bdw_analysis_prod.maira.terminology_normalisations"
                )
                .filter(
                    F.col("review_status") == "HUMAN_VALIDATED"
                )
                .select(
                    "source_expression",
                    "target_code_idcode",
                )
            )
    
            registry_values = (
                spark.table(
                    "bdw_analysis_prod.maira.emcip_operational_registry"
                )
                .select(
                    F.col("code_idcode").alias(
                        "target_code_idcode"
                    ),
                    "code_value",
                )
                .filter(
                    F.col("target_code_idcode").isNotNull()
                    & F.col("code_value").isNotNull()
                )
                .dropDuplicates()
            )
    
            governed_expansions = (
                validated_terms
                .join(
                    registry_values,
                    on="target_code_idcode",
                    how="inner",
                )
                .select(
                    "source_expression",
                    "code_value",
                )
                .dropDuplicates()
                .collect()
            )
    
            for expansion in governed_expansions:
                source_expression = str(
                    expansion["source_expression"] or ""
                ).strip()
                code_value = str(
                    expansion["code_value"] or ""
                ).strip()
    
                if not source_expression or not code_value:
                    continue
    
                expansion_map.setdefault(
                    source_expression,
                    set(),
                ).add(code_value)
    
                expansion_map.setdefault(
                    code_value,
                    set(),
                ).add(source_expression)
    
        retrieval = retrieve_free_text(
            [
                {
                    "document_id": row["document_id"],
                    "passage_id": row["passage_id"],
                    "passage_number": row["passage_order"],
                    "start_page": row["page_start"],
                    "end_page": row["page_end"],
                    "passage_text": row["passage_text"],
                    "report_package_id": None,
                }
                for row in passage_rows
            ],
            question_text,
            expansions=expansion_map,
            max_passages=RETRIEVAL_MAX_PASSAGES,
            max_characters=RETRIEVAL_MAX_CHARS,
        )
    
        retrieved_ids = {
            hit.passage_id
            for hit in retrieval.hits
        }
    
        retrieval_mode = retrieval.method
    
        with driver.session() as session:
            session.run(
                """
                MATCH (q:QuestionRun {
                    question_run_id: $question_run_id
                })
                SET
                    q.retrieval_mode = $retrieval_mode,
                    q.retrieval_candidate_count = $candidate_count,
                    q.retrieval_selected_count = $selected_count,
                    q.retrieval_selected_characters = $selected_characters,
                    q.retrieval_query_terms = $query_terms,
                    q.retrieval_activated_expansions = $activated_expansions,
                    q.updated_at = datetime()
                """,
                question_run_id=question_run_id,
                retrieval_mode=retrieval.method,
                candidate_count=retrieval.candidate_count,
                selected_count=retrieval.selected_count,
                selected_characters=retrieval.selected_characters,
                query_terms=list(retrieval.query_terms),
                activated_expansions=list(
                    retrieval.activated_expansions
                ),
            ).consume()
    
        if not retrieved_ids:
            deterministic_answer = (
                "The deterministic lexical retrieval found no passage matching "
                "the substantive terms of this question within the selected "
                "evidence scope. No LLM answer was generated."
            )
    
            snapshot_payload = {
                "analysis_id": analysis_id,
                "question_sha256": hashlib.sha256(
                    question_text.encode("utf-8")
                ).hexdigest(),
                "scope_mode": scope_mode,
                "scope_document_ids": sorted(
                    scope_document_ids
                ),
                "retrieval_mode": retrieval.method,
                "retrieval_passage_ids": [],
            }
            retrieval_snapshot_id = (
                "snapshot_"
                + hashlib.sha256(
                    json.dumps(
                        snapshot_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()[:32]
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
                        q.deterministic_answer = $deterministic_answer,
                        q.insufficient_evidence = true,
                        q.retrieval_snapshot_id = $retrieval_snapshot_id,
                        q.retrieval_passage_ids = [],
                        q.completed_at = datetime(),
                        q.updated_at = datetime()
                    """,
                    question_run_id=question_run_id,
                    deterministic_answer=deterministic_answer,
                    retrieval_snapshot_id=retrieval_snapshot_id,
                ).consume()
    
            print("")
            print("QUESTION RUN: COMPLETED — NO LEXICAL MATCH")
            print("retrieval_mode:", retrieval.method)
            print("retrieval_snapshot_id:", retrieval_snapshot_id)
            driver.close()
            dbutils.notebook.exit(
                "COMPLETED_NO_LEXICAL_MATCH"
            )
    
        passage_rows = [
            row
            for row in passage_rows
            if row["passage_id"] in retrieved_ids
        ]
    
        scope_chars = sum(
            len(row["passage_text"] or "")
            for row in passage_rows
        )
    
    print("Evidence passages sent to answer stage:", len(passage_rows))
    print("Evidence characters sent to answer stage:", scope_chars)
    
    # Reproducible retrieval snapshot for every model-answering run.
    retrieval_passage_ids = sorted(
        row["passage_id"]
        for row in passage_rows
    )
    
    snapshot_payload = {
        "analysis_id": analysis_id,
        "question_sha256": hashlib.sha256(
            question_text.encode("utf-8")
        ).hexdigest(),
        "scope_mode": scope_mode,
        "scope_document_ids": sorted(
            scope_document_ids
        ),
        "retrieval_mode": retrieval_mode,
        "governed_query_id": governed_query_id,
        "governed_query_spec_id": governed_query_spec_id,
        "retrieval_passage_ids": retrieval_passage_ids,
    }
    
    retrieval_snapshot_id = (
        "snapshot_"
        + hashlib.sha256(
            json.dumps(
                snapshot_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:32]
    )
    
    with driver.session() as session:
        session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })
            SET
                q.retrieval_snapshot_id = $retrieval_snapshot_id,
                q.retrieval_passage_ids = $retrieval_passage_ids,
                q.retrieval_mode = $retrieval_mode,
                q.updated_at = datetime()
            """,
            question_run_id=question_run_id,
            retrieval_snapshot_id=retrieval_snapshot_id,
            retrieval_passage_ids=retrieval_passage_ids,
            retrieval_mode=retrieval_mode,
        ).consume()
    
    print("Retrieval snapshot:", retrieval_snapshot_id)


# REFERENCE_CONTEXT retrieval is deliberately separate from primary case
# retrieval. Reference passages can explain framework/methodology but are never
# part of the occurrence-evidence retrieval snapshot.

reference_rows = []
reference_retrieval_mode = "NONE"
reference_retrieval_passage_ids = []
reference_retrieval_snapshot_id = None

if include_reference_context or direct_document_ask:
    if maira_import_error is not None:
        message = (
            "Reference context requires MAIRA's deterministic free-text "
            "retrieval module, but the MAIRA runtime package is unavailable."
        )
        with driver.session() as session:
            session.run(
                """
                MATCH (q:QuestionRun {
                    question_run_id: $question_run_id
                })
                SET
                    q.status = 'FAILED',
                    q.processing_stage = 'REFERENCE_RETRIEVAL_RUNTIME_UNAVAILABLE',
                    q.processing_error = $message,
                    q.updated_at = datetime()
                """,
                question_run_id=question_run_id,
                message=message,
            ).consume()
        driver.close()
        raise RuntimeError(message)

    if not spark.catalog.tableExists(
        REFERENCE_DOCUMENT_TABLE
    ) or not spark.catalog.tableExists(
        REFERENCE_PASSAGE_TABLE
    ):
        message = (
            "Reference context was requested, but the governed IKF "
            "REFERENCE_CONTEXT corpus has not been indexed. "
            "Run notebook 44 first."
        )
        with driver.session() as session:
            session.run(
                """
                MATCH (q:QuestionRun {
                    question_run_id: $question_run_id
                })
                SET
                    q.status = 'FAILED',
                    q.processing_stage = 'REFERENCE_CORPUS_NOT_READY',
                    q.processing_error = $message,
                    q.updated_at = datetime()
                """,
                question_run_id=question_run_id,
                message=message,
            ).consume()
        driver.close()
        raise RuntimeError(message)

    from maira.retrieval import retrieve_free_text

    reference_documents = {
        row["reference_document_id"]: row.asDict(
            recursive=True
        )
        for row in (
            spark.table(
                REFERENCE_DOCUMENT_TABLE
            )
            .filter(
                F.col("source_layer")
                == "REFERENCE_CONTEXT"
            )
            .select(
                "reference_document_id",
                "filename",
                "reference_family",
                "reference_code",
                "reference_title",
            )
            .collect()
        )
    }

    if direct_document_ask:
        reference_documents = {
            document_id: item
            for document_id, item
            in reference_documents.items()
            if document_id
            in set(
                direct_reference_document_ids
            )
        }

    reference_document_names = {
        document_id: (
            item.get("reference_code")
            or item.get("reference_title")
            or item.get("filename")
            or document_id
        )
        for document_id, item
        in reference_documents.items()
    }

    reference_candidates_df = (
        spark.table(
            REFERENCE_PASSAGE_TABLE
        )
        .filter(
            F.col("source_layer")
            == "REFERENCE_CONTEXT"
        )
    )

    if direct_document_ask:
        reference_candidates_df = (
            reference_candidates_df
            .filter(
                F.col(
                    "reference_document_id"
                ).isin(
                    direct_reference_document_ids
                )
            )
        )

    reference_candidates = (
        reference_candidates_df
        .select(
            F.col(
                "reference_document_id"
            ).alias("document_id"),
            F.col(
                "reference_passage_id"
            ).alias("passage_id"),
            "page_start",
            "page_end",
            "passage_number",
            "passage_text",
        )
        .orderBy(
            "document_id",
            "passage_number",
        )
        .collect()
    )

    if reference_candidates:
        reference_retrieval = retrieve_free_text(
            [
                {
                    "document_id": row["document_id"],
                    "passage_id": row["passage_id"],
                    "passage_number": row["passage_number"],
                    "start_page": row["page_start"],
                    "end_page": row["page_end"],
                    "passage_text": row["passage_text"],
                    "report_package_id": None,
                }
                for row in reference_candidates
            ],
            question_text,
            expansions=None,
            max_passages=REFERENCE_MAX_PASSAGES,
            max_characters=REFERENCE_MAX_CHARS,
        )

        selected_reference_ids = {
            hit.passage_id
            for hit in reference_retrieval.hits
        }

        reference_rows = [
            {
                "document_id": row["document_id"],
                "passage_id": row["passage_id"],
                "page_start": row["page_start"],
                "page_end": row["page_end"],
                "passage_order": row["passage_number"],
                "detected_language": "REFERENCE",
                "passage_text": row["passage_text"],
            }
            for row in reference_candidates
            if row["passage_id"]
            in selected_reference_ids
        ]

        reference_retrieval_mode = (
            reference_retrieval.method
        )
        reference_retrieval_passage_ids = sorted(
            selected_reference_ids
        )

    reference_snapshot_payload = {
        "question_sha256": hashlib.sha256(
            question_text.encode("utf-8")
        ).hexdigest(),
        "reference_corpus": REFERENCE_PASSAGE_TABLE,
        "reference_retrieval_mode": reference_retrieval_mode,
        "reference_retrieval_passage_ids": (
            reference_retrieval_passage_ids
        ),
    }

    reference_retrieval_snapshot_id = (
        "reference_snapshot_"
        + hashlib.sha256(
            json.dumps(
                reference_snapshot_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:32]
    )

    with driver.session() as session:
        session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })
            SET
                q.reference_retrieval_mode = $reference_retrieval_mode,
                q.reference_retrieval_passage_ids = $reference_retrieval_passage_ids,
                q.reference_retrieval_snapshot_id = $reference_retrieval_snapshot_id,
                q.reference_context_passage_count = $reference_context_passage_count,
                q.updated_at = datetime()
            """,
            question_run_id=question_run_id,
            reference_retrieval_mode=reference_retrieval_mode,
            reference_retrieval_passage_ids=reference_retrieval_passage_ids,
            reference_retrieval_snapshot_id=reference_retrieval_snapshot_id,
            reference_context_passage_count=len(
                reference_rows
            ),
        ).consume()

print(
    "REFERENCE_CONTEXT passages:",
    len(reference_rows),
)
if reference_retrieval_snapshot_id:
    print(
        "Reference retrieval snapshot:",
        reference_retrieval_snapshot_id,
    )

# COMMAND ----------

def format_page_reference(page_start, page_end):
    if page_start is None:
        return "page unknown"
    if page_end is None or page_end == page_start:
        return f"p. {page_start}"
    return f"pp. {page_start}–{page_end}"


source_evidence_by_id = {
    row["passage_id"]: row
    for row in passage_rows
}

reference_context_by_id = {
    row["passage_id"]: row
    for row in reference_rows
}

# Backward-compatible alias for primary case evidence only.
passage_by_id = source_evidence_by_id


def references_for(
    passage_ids,
    row_by_id,
    name_by_document_id,
):
    refs = []
    seen = set()

    for passage_id in passage_ids:
        row = row_by_id.get(
            passage_id
        )
        if row is None:
            continue

        filename = (
            name_by_document_id.get(
                row["document_id"]
            )
            or (
                "Direct text"
                if str(
                    row["document_id"]
                ).startswith("text_")
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


def locations_for(
    passage_ids,
    row_by_id,
):
    locations = []
    seen = set()

    for passage_id in passage_ids:
        row = row_by_id.get(
            passage_id
        )
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


def evidence_references(passage_ids):
    return references_for(
        passage_ids,
        source_evidence_by_id,
        document_names,
    )


def evidence_locations(passage_ids):
    return locations_for(
        passage_ids,
        source_evidence_by_id,
    )


def reference_references(passage_ids):
    return references_for(
        passage_ids,
        reference_context_by_id,
        reference_document_names,
    )


def reference_locations(passage_ids):
    return locations_for(
        passage_ids,
        reference_context_by_id,
    )


def passage_block(
    row,
    *,
    source_layer,
    name_by_document_id,
):
    filename = (
        name_by_document_id.get(
            row["document_id"]
        )
        or (
            "Direct text"
            if str(
                row["document_id"]
            ).startswith("text_")
            else row["document_id"]
        )
    )

    return (
        f"[SOURCE_LAYER: {source_layer}]\n"
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
You answer an investigator's question using ONLY the supplied passages.

Every passage is explicitly labelled with one SOURCE_LAYER.

SOURCE_EVIDENCE:
- occurrence-specific investigation evidence;
- may support statements about what happened in the selected case.

REFERENCE_CONTEXT:
- legal, methodological or technical context from the governed IKF
  reference-context corpus;
- may explain requirements, definitions, methods or technical background;
- MUST NOT be used as proof that an event, condition, cause or factor occurred
  in the selected case.

CONTROLLED_TAXONOMY is not supplied here as occurrence evidence.

Rules:
1. Do not use general maritime knowledge to fill gaps.
2. A case-specific factual claim must be supported by SOURCE_EVIDENCE.
3. REFERENCE_CONTEXT may support framework/context statements. For a
   DIRECT_DOCUMENT_ASK it is the sole governed source and may directly support
   answers about what the selected reference document says, defines or requires.
4. Never transform a general rule, technical possibility or legal requirement
   into a case fact.
5. Return passage IDs in the correct source-layer array only.
6. Distinguish chronology from causality. Sequence alone does not establish
   RESULTED_IN or CONTRIBUTED_TO.
7. If the supplied material does not support an answer, say so explicitly.
8. Preserve uncertainty and conflicting statements.
9. Do not expose unnecessary personal identifiers.
10. Return JSON only.

Required JSON:
{
  "answer": "concise grounded answer",
  "source_evidence_passage_ids": ["passage_..."],
  "reference_context_passage_ids": ["passage_..."],
  "insufficient_evidence": false,
  "limitations": ["..."]
}
"""

source_evidence_text = "\n\n---\n\n".join(
    passage_block(
        row,
        source_layer="SOURCE_EVIDENCE",
        name_by_document_id=document_names,
    )
    for row in passage_rows
)

reference_context_text = "\n\n---\n\n".join(
    passage_block(
        row,
        source_layer="REFERENCE_CONTEXT",
        name_by_document_id=reference_document_names,
    )
    for row in reference_rows
)

user_prompt = (
    (
        "Direct governed reference-document question\n"
        if direct_document_ask
        else (
            "Case / analysis: "
            + str(
                question_run.get(
                    "analysis_title"
                )
                or analysis_id
            )
            + "\n"
        )
    )
    + f"Evidence scope: {scope_mode}\n"
    f"Output language: {question_run.get('output_language') or 'English'}\n"
    f"Question: {question_text}\n\n"
    "SOURCE_EVIDENCE passages:\n\n"
    + source_evidence_text
    + (
        "\n\n==============================\n\n"
        "REFERENCE_CONTEXT passages:\n\n"
        + reference_context_text
        if reference_context_text
        else
        "\n\nREFERENCE_CONTEXT passages: none selected/retrieved."
    )
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
            q.retrieval_snapshot_id = $retrieval_snapshot_id,
            q.retrieval_passage_ids = $retrieval_passage_ids,
            q.updated_at = datetime()
        """,
        question_run_id=question_run_id,
        passage_count=len(passage_rows),
        character_count=scope_chars,
        question_run_version=QUESTION_RUN_VERSION,
        retrieval_mode=retrieval_mode,
        governed_query_id=governed_query_id,
        governed_query_spec_id=governed_query_spec_id,
        retrieval_snapshot_id=retrieval_snapshot_id,
        retrieval_passage_ids=retrieval_passage_ids,
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

        raw_source_ids = {
            str(value)
            for value in result.get(
                "source_evidence_passage_ids",
                [],
            )
        }
        raw_reference_ids = {
            str(value)
            for value in result.get(
                "reference_context_passage_ids",
                [],
            )
        }

        source_valid_ids = sorted(
            passage_id
            for passage_id in raw_source_ids
            if passage_id
            in source_evidence_by_id
        )
        reference_valid_ids = sorted(
            passage_id
            for passage_id in raw_reference_ids
            if passage_id
            in reference_context_by_id
        )

        invalid_source_ids = sorted(
            raw_source_ids
            - set(source_valid_ids)
        )
        invalid_reference_ids = sorted(
            raw_reference_ids
            - set(reference_valid_ids)
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

        if invalid_source_ids:
            limitations.append(
                "One or more returned SOURCE_EVIDENCE passage IDs were "
                "not valid for the selected case-evidence layer."
            )

        if invalid_reference_ids:
            limitations.append(
                "One or more returned REFERENCE_CONTEXT passage IDs were "
                "not valid for the selected reference layer."
            )

        if (
            answer_raw
            and not source_valid_ids
            and not reference_valid_ids
        ):
            insufficient = True
            limitations.append(
                "The model returned no valid supporting passage IDs in "
                "either source layer."
            )
            answer_raw = (
                "The supplied material does not contain a sufficiently "
                "grounded answer with valid source references."
            )

        if not answer_raw:
            insufficient = True
            answer_raw = (
                "The supplied material does not provide a supported answer "
                "to this question."
            )

        answer = redact_direct_identifiers(
            answer_raw
        )

        source_references = evidence_references(
            source_valid_ids
        )
        source_locations = evidence_locations(
            source_valid_ids
        )
        reference_refs = reference_references(
            reference_valid_ids
        )
        reference_locs = reference_locations(
            reference_valid_ids
        )

        valid_ids = sorted(
            set(source_valid_ids)
            | set(reference_valid_ids)
        )
        references = (
            source_references
            + reference_refs
        )
        locations = (
            source_locations
            + reference_locs
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
                    m.source_evidence_passage_ids = $source_evidence_passage_ids,
                    m.source_evidence_references = $source_evidence_references,
                    m.source_evidence_locations = $source_evidence_locations,
                    m.reference_context_passage_ids = $reference_context_passage_ids,
                    m.reference_context_references = $reference_context_references,
                    m.reference_context_locations = $reference_context_locations,
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
                source_evidence_passage_ids=source_valid_ids,
                source_evidence_references=source_references,
                source_evidence_locations=source_locations,
                reference_context_passage_ids=reference_valid_ids,
                reference_context_references=reference_refs,
                reference_context_locations=reference_locs,
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
