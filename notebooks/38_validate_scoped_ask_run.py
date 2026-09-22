# Databricks notebook source
# MAGIC %md
# MAGIC # 38 — Validate scoped Ask / Compare run
# MAGIC
# MAGIC Read-only validation for one persisted QuestionRun.
# MAGIC
# MAGIC Checks:
# MAGIC - QuestionRun belongs to one AnalysisGroup;
# MAGIC - document scope is valid for that analysis;
# MAGIC - answer passage IDs belong to the scoped analysis evidence;
# MAGIC - cited page locations resolve to the same scoped passages;
# MAGIC - governed retrieval metadata is internally consistent when present;
# MAGIC - no graph modification is required for question execution.

# COMMAND ----------

dbutils.widgets.text(
    "question_run_id",
    "",
    "Question run ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

import re

from neo4j import GraphDatabase
from pyspark.sql import functions as F

ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"
QUERY_SPEC_TABLE = "bdw_analysis_prod.maira.query_specifications"

question_run_id = dbutils.widgets.get(
    "question_run_id"
).strip()

if not re.fullmatch(
    r"question_[0-9a-f]{32}",
    question_run_id,
):
    raise ValueError(
        "Enter a valid question_<32 hex> QuestionRun ID."
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

# COMMAND ----------

with driver.session() as session:
    question = session.run(
        """
        MATCH (a:AnalysisGroup)-[:HAS_QUESTION_RUN]->(
            q:QuestionRun {question_run_id: $question_run_id}
        )
        OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
        WITH a, q, collect(d.document_id) AS analysis_document_ids
        RETURN
            a.analysis_id AS analysis_id,
            q.scope_mode AS scope_mode,
            coalesce(q.scope_document_ids, []) AS scope_document_ids,
            q.status AS status,
            q.retrieval_mode AS retrieval_mode,
            q.governed_query_id AS governed_query_id,
            q.governed_query_spec_id AS governed_query_spec_id,
            q.governed_relationship AS governed_relationship,
            q.deterministic_answer AS deterministic_answer,
            analysis_document_ids
        """,
        question_run_id=question_run_id,
    ).single()

if question is None:
    driver.close()
    raise ValueError(
        f"QuestionRun not found: {question_run_id}"
    )

question = question.data()
analysis_id = question["analysis_id"]

print("QuestionRun:", question_run_id)
print("Analysis:", analysis_id)
print("Status:", question["status"])
print("Scope:", question["scope_mode"])
print("Retrieval:", question["retrieval_mode"])

# COMMAND ----------

analysis_document_ids = {
    value
    for value in (
        question.get("analysis_document_ids")
        or []
    )
    if value
}

scope_mode = question.get("scope_mode") or "WHOLE_CASE"
scope_document_ids = set(
    question.get("scope_document_ids")
    or []
)

if scope_mode == "WHOLE_CASE":
    effective_document_ids = analysis_document_ids
elif scope_mode in {
    "ONE_DOCUMENT",
    "SELECTED_DOCUMENTS",
}:
    if not scope_document_ids:
        driver.close()
        raise ValueError(
            "Document-scoped QuestionRun has no scope_document_ids."
        )
    if not scope_document_ids.issubset(
        analysis_document_ids
    ):
        driver.close()
        raise ValueError(
            "QuestionRun scope includes a document that is not linked "
            "to the AnalysisGroup."
        )
    effective_document_ids = scope_document_ids
else:
    driver.close()
    raise ValueError(
        f"Unsupported QuestionRun scope_mode: {scope_mode}"
    )

print(
    "Effective document IDs:",
    sorted(effective_document_ids),
)

# COMMAND ----------

scoped_passages = (
    spark.table(ANALYSIS_PASSAGE_TABLE)
    .filter(F.col("analysis_id") == analysis_id)
)

if effective_document_ids:
    scoped_passages = scoped_passages.filter(
        F.col("document_id").isin(
            sorted(effective_document_ids)
        )
    )

scoped_rows = scoped_passages.select(
    "document_id",
    "passage_id",
    "page_start",
    "page_end",
).collect()

scoped_passage_by_id = {
    row["passage_id"]: row.asDict(recursive=True)
    for row in scoped_rows
}

print("Scoped passage count:", len(scoped_passage_by_id))

if not scoped_passage_by_id:
    driver.close()
    raise ValueError(
        "The QuestionRun scope contains no persisted analysis passages."
    )

# COMMAND ----------

with driver.session() as session:
    model_runs = [
        record.data()
        for record in session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })-[:HAS_MODEL_ANSWER]->(m:QuestionModelRun)
            RETURN
                m.model_key AS model_key,
                m.status AS status,
                coalesce(m.passage_ids, []) AS passage_ids,
                coalesce(m.evidence_locations, []) AS evidence_locations,
                coalesce(m.evidence_references, []) AS evidence_references,
                coalesce(m.insufficient_evidence, false) AS insufficient_evidence
            ORDER BY m.model_key
            """,
            question_run_id=question_run_id,
        )
    ]

print("Question model runs:", len(model_runs))

# COMMAND ----------

validation_rows = []
errors = []

for model_run in model_runs:
    invalid_passage_ids = sorted(
        {
            passage_id
            for passage_id in (
                model_run.get("passage_ids")
                or []
            )
            if passage_id not in scoped_passage_by_id
        }
    )

    if invalid_passage_ids:
        errors.append(
            f"{model_run['model_key']}: answer references passages "
            f"outside the selected scope: {invalid_passage_ids}"
        )

    location_errors = []

    for raw_location in (
        model_run.get("evidence_locations")
        or []
    ):
        parts = str(raw_location).split("|")
        if len(parts) != 3:
            location_errors.append(
                f"invalid format: {raw_location}"
            )
            continue

        document_id = parts[0]
        page_start = (
            int(parts[1])
            if parts[1].isdigit()
            else None
        )
        page_end = (
            int(parts[2])
            if parts[2].isdigit()
            else page_start
        )

        if (
            effective_document_ids
            and document_id not in effective_document_ids
        ):
            location_errors.append(
                f"document outside scope: {raw_location}"
            )
            continue

        matching_passage = any(
            row["document_id"] == document_id
            and row["page_start"] == page_start
            and (
                row["page_end"] == page_end
                or (
                    row["page_end"] is None
                    and page_end == page_start
                )
            )
            for row in scoped_passage_by_id.values()
        )

        if not matching_passage:
            location_errors.append(
                f"page location not backed by scoped passage: {raw_location}"
            )

    if location_errors:
        errors.extend(
            f"{model_run['model_key']}: {value}"
            for value in location_errors
        )

    validation_rows.append(
        {
            "model_key": model_run["model_key"],
            "status": model_run["status"],
            "answer_passages": len(
                model_run.get("passage_ids") or []
            ),
            "references": len(
                model_run.get("evidence_references") or []
            ),
            "locations": len(
                model_run.get("evidence_locations") or []
            ),
            "invalid_passages": len(
                invalid_passage_ids
            ),
            "location_errors": len(
                location_errors
            ),
            "insufficient_evidence": bool(
                model_run.get("insufficient_evidence")
            ),
        }
    )

if validation_rows:
    display(
        spark.createDataFrame(validation_rows)
    )

# COMMAND ----------

governed_query_id = question.get(
    "governed_query_id"
)
governed_query_spec_id = question.get(
    "governed_query_spec_id"
)

if governed_query_id:
    if question.get("retrieval_mode") != "GOVERNED_RELATIONSHIP_EVIDENCE":
        errors.append(
            "governed_query_id is present but retrieval_mode is not "
            "GOVERNED_RELATIONSHIP_EVIDENCE"
        )

    if not spark.catalog.tableExists(
        QUERY_SPEC_TABLE
    ):
        errors.append(
            "MAIRA query_specifications table is unavailable."
        )
    else:
        matching_specs = (
            spark.table(QUERY_SPEC_TABLE)
            .filter(
                (F.col("query_id") == governed_query_id)
                & (
                    F.col("query_spec_id")
                    == governed_query_spec_id
                )
            )
            .count()
        )

        if matching_specs != 1:
            errors.append(
                "Governed query metadata does not resolve to exactly one "
                "persisted MAIRA query specification."
            )

if (
    question.get("deterministic_answer")
    and model_runs
):
    errors.append(
        "A deterministic no-governed-support answer should not also have "
        "QuestionModelRun outputs."
    )

# COMMAND ----------

if errors:
    print("")
    print("VALIDATION ERRORS")
    for error in errors:
        print(" -", error)

    driver.close()
    raise RuntimeError(
        "Scoped Ask / Compare validation failed."
    )

print("")
print("PASS — SCOPED ASK / COMPARE RUN IS EVIDENCE-BOUNDED")
print("question_run_id:", question_run_id)
print("analysis_id:", analysis_id)
print("scope_mode:", scope_mode)
print("retrieval_mode:", question.get("retrieval_mode"))
print("model_runs:", len(model_runs))

driver.close()
