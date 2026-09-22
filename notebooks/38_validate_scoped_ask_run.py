# Databricks notebook source
# MAGIC %md
# MAGIC # 38 — Validate scoped Ask / Compare run
# MAGIC
# MAGIC Read-only validation for one persisted QuestionRun.
# MAGIC
# MAGIC Validates the separation of:
# MAGIC - SOURCE_EVIDENCE — case-specific processed passages;
# MAGIC - REFERENCE_CONTEXT — governed IKF legal/IMO/technical passages;
# MAGIC - CONTROLLED_TAXONOMY — not treated here as occurrence evidence.
# MAGIC
# MAGIC This notebook does not modify Neo4j, Delta, source files or the graph.

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
REFERENCE_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.reference_passage"
REFERENCE_DOCUMENT_TABLE = "bdw_analysis_prod.kg_poc.reference_document"
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
    question_record = session.run(
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
            coalesce(q.include_reference_context, false) AS include_reference_context,
            q.status AS status,
            q.retrieval_mode AS retrieval_mode,
            q.retrieval_snapshot_id AS retrieval_snapshot_id,
            coalesce(q.retrieval_passage_ids, []) AS retrieval_passage_ids,
            q.reference_retrieval_mode AS reference_retrieval_mode,
            q.reference_retrieval_snapshot_id AS reference_retrieval_snapshot_id,
            coalesce(q.reference_retrieval_passage_ids, []) AS reference_retrieval_passage_ids,
            coalesce(q.reference_context_passage_count, 0) AS reference_context_passage_count,
            q.governed_query_id AS governed_query_id,
            q.governed_query_spec_id AS governed_query_spec_id,
            q.governed_relationship AS governed_relationship,
            q.deterministic_answer AS deterministic_answer,
            analysis_document_ids
        """,
        question_run_id=question_run_id,
    ).single()

if question_record is None:
    driver.close()
    raise ValueError(
        f"QuestionRun not found: {question_run_id}"
    )

question = question_record.data()
analysis_id = question["analysis_id"]

print("QuestionRun:", question_run_id)
print("Analysis:", analysis_id)
print("Status:", question["status"])
print("Primary retrieval:", question.get("retrieval_mode"))
print(
    "Reference context:",
    bool(question.get("include_reference_context")),
)
print(
    "Reference retrieval:",
    question.get("reference_retrieval_mode"),
)

# COMMAND ----------

analysis_document_ids = {
    value
    for value in (
        question.get("analysis_document_ids")
        or []
    )
    if value
}

scope_mode = (
    question.get("scope_mode")
    or "WHOLE_CASE"
)
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
            "to the primary AnalysisGroup."
        )

    effective_document_ids = scope_document_ids
else:
    driver.close()
    raise ValueError(
        f"Unsupported QuestionRun scope_mode: {scope_mode}"
    )

primary_passages = (
    spark.table(ANALYSIS_PASSAGE_TABLE)
    .filter(F.col("analysis_id") == analysis_id)
)

if effective_document_ids:
    primary_passages = primary_passages.filter(
        F.col("document_id").isin(
            sorted(effective_document_ids)
        )
    )

primary_rows = (
    primary_passages
    .select(
        "document_id",
        "passage_id",
        "page_start",
        "page_end",
    )
    .collect()
)

primary_by_id = {
    row["passage_id"]: row.asDict(recursive=True)
    for row in primary_rows
}

if not primary_by_id:
    driver.close()
    raise ValueError(
        "The selected SOURCE_EVIDENCE scope has no persisted passages."
    )

print("SOURCE_EVIDENCE passages:", len(primary_by_id))

# COMMAND ----------

reference_by_id = {}

if question.get("include_reference_context"):
    if (
        not spark.catalog.tableExists(REFERENCE_PASSAGE_TABLE)
        or not spark.catalog.tableExists(REFERENCE_DOCUMENT_TABLE)
    ):
        driver.close()
        raise RuntimeError(
            "REFERENCE_CONTEXT was requested but its governed Delta corpus "
            "is not available."
        )

    reference_rows = (
        spark.table(REFERENCE_PASSAGE_TABLE)
        .filter(
            F.col("source_layer")
            == "REFERENCE_CONTEXT"
        )
        .select(
            F.col("reference_document_id").alias("document_id"),
            F.col("reference_passage_id").alias("passage_id"),
            "page_start",
            "page_end",
        )
        .collect()
    )

    reference_by_id = {
        row["passage_id"]: row.asDict(recursive=True)
        for row in reference_rows
    }

    print(
        "REFERENCE_CONTEXT corpus passages:",
        len(reference_by_id),
    )

# COMMAND ----------

primary_snapshot_ids = set(
    question.get("retrieval_passage_ids")
    or []
)
reference_snapshot_ids = set(
    question.get("reference_retrieval_passage_ids")
    or []
)

errors = []

if primary_snapshot_ids:
    unknown_primary_snapshot = sorted(
        primary_snapshot_ids
        - set(primary_by_id)
    )
    if unknown_primary_snapshot:
        errors.append(
            "Primary retrieval snapshot contains passage IDs outside "
            "the selected SOURCE_EVIDENCE scope: "
            + ", ".join(unknown_primary_snapshot)
        )

if question.get("include_reference_context"):
    unknown_reference_snapshot = sorted(
        reference_snapshot_ids
        - set(reference_by_id)
    )
    if unknown_reference_snapshot:
        errors.append(
            "Reference retrieval snapshot contains IDs outside the "
            "REFERENCE_CONTEXT corpus: "
            + ", ".join(unknown_reference_snapshot)
        )
else:
    if reference_snapshot_ids:
        errors.append(
            "QuestionRun did not request REFERENCE_CONTEXT but contains "
            "reference retrieval passage IDs."
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
                coalesce(m.source_evidence_passage_ids, []) AS source_evidence_passage_ids,
                coalesce(m.source_evidence_locations, []) AS source_evidence_locations,
                coalesce(m.reference_context_passage_ids, []) AS reference_context_passage_ids,
                coalesce(m.reference_context_locations, []) AS reference_context_locations,
                coalesce(m.insufficient_evidence, false) AS insufficient_evidence
            ORDER BY m.model_key
            """,
            question_run_id=question_run_id,
        )
    ]

print("Question model runs:", len(model_runs))

# COMMAND ----------

def parse_location(value):
    parts = str(value or "").split("|")
    if len(parts) != 3:
        return None

    def page(raw):
        raw = raw.strip()
        return int(raw) if raw.isdigit() else None

    return {
        "document_id": parts[0],
        "page_start": page(parts[1]),
        "page_end": page(parts[2]),
    }


def location_backed_by(
    location,
    passage_by_id,
):
    if location is None:
        return False

    start = location["page_start"]
    end = location["page_end"] or start

    return any(
        row["document_id"] == location["document_id"]
        and row["page_start"] == start
        and (
            row["page_end"] == end
            or (
                row["page_end"] is None
                and end == start
            )
        )
        for row in passage_by_id.values()
    )


validation_rows = []

for model_run in model_runs:
    model_key = model_run["model_key"]

    source_ids = set(
        model_run.get("source_evidence_passage_ids")
        or []
    )
    reference_ids = set(
        model_run.get("reference_context_passage_ids")
        or []
    )
    combined_ids = set(
        model_run.get("passage_ids")
        or []
    )

    invalid_source = sorted(
        source_ids - set(primary_by_id)
    )
    invalid_reference = sorted(
        reference_ids - set(reference_by_id)
    )

    if primary_snapshot_ids:
        outside_primary_snapshot = sorted(
            source_ids - primary_snapshot_ids
        )
    else:
        outside_primary_snapshot = []

    if reference_snapshot_ids:
        outside_reference_snapshot = sorted(
            reference_ids - reference_snapshot_ids
        )
    else:
        outside_reference_snapshot = (
            sorted(reference_ids)
            if reference_ids
            else []
        )

    overlap = sorted(
        source_ids & reference_ids
    )

    union_mismatch = sorted(
        combined_ids
        ^ (source_ids | reference_ids)
    )

    source_location_errors = [
        raw
        for raw in (
            model_run.get("source_evidence_locations")
            or []
        )
        if not location_backed_by(
            parse_location(raw),
            primary_by_id,
        )
    ]

    reference_location_errors = [
        raw
        for raw in (
            model_run.get("reference_context_locations")
            or []
        )
        if not location_backed_by(
            parse_location(raw),
            reference_by_id,
        )
    ]

    if invalid_source:
        errors.append(
            f"{model_key}: SOURCE_EVIDENCE IDs outside case scope: "
            + ", ".join(invalid_source)
        )
    if invalid_reference:
        errors.append(
            f"{model_key}: REFERENCE_CONTEXT IDs outside reference corpus: "
            + ", ".join(invalid_reference)
        )
    if outside_primary_snapshot:
        errors.append(
            f"{model_key}: SOURCE_EVIDENCE IDs outside primary retrieval snapshot: "
            + ", ".join(outside_primary_snapshot)
        )
    if outside_reference_snapshot:
        errors.append(
            f"{model_key}: REFERENCE_CONTEXT IDs outside reference retrieval snapshot: "
            + ", ".join(outside_reference_snapshot)
        )
    if overlap:
        errors.append(
            f"{model_key}: passage IDs attributed to both source layers: "
            + ", ".join(overlap)
        )
    if union_mismatch:
        errors.append(
            f"{model_key}: combined passage_ids are not the union of "
            "SOURCE_EVIDENCE and REFERENCE_CONTEXT IDs."
        )
    if source_location_errors:
        errors.append(
            f"{model_key}: invalid SOURCE_EVIDENCE page location(s): "
            + ", ".join(source_location_errors)
        )
    if reference_location_errors:
        errors.append(
            f"{model_key}: invalid REFERENCE_CONTEXT page location(s): "
            + ", ".join(reference_location_errors)
        )

    validation_rows.append(
        {
            "model_key": model_key,
            "status": model_run["status"],
            "source_evidence_ids": len(source_ids),
            "reference_context_ids": len(reference_ids),
            "combined_ids": len(combined_ids),
            "source_location_errors": len(
                source_location_errors
            ),
            "reference_location_errors": len(
                reference_location_errors
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

governed_query_id = question.get("governed_query_id")
governed_query_spec_id = question.get(
    "governed_query_spec_id"
)

if governed_query_id:
    if (
        question.get("retrieval_mode")
        != "GOVERNED_RELATIONSHIP_EVIDENCE"
    ):
        errors.append(
            "governed_query_id exists but retrieval_mode is not "
            "GOVERNED_RELATIONSHIP_EVIDENCE."
        )

    if not spark.catalog.tableExists(
        QUERY_SPEC_TABLE
    ):
        errors.append(
            "MAIRA query_specifications table is unavailable."
        )
    else:
        matches = (
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
        if matches != 1:
            errors.append(
                "Governed query metadata does not resolve to exactly one "
                "persisted MAIRA query specification."
            )

if (
    question.get("deterministic_answer")
    and model_runs
):
    errors.append(
        "A deterministic no-support result must not also contain model answers."
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
print(
    "PASS — SCOPED ASK / COMPARE PRESERVES "
    "SOURCE_EVIDENCE AND REFERENCE_CONTEXT BOUNDARIES"
)
print("question_run_id:", question_run_id)
print("analysis_id:", analysis_id)
print("scope_mode:", scope_mode)
print("retrieval_mode:", question.get("retrieval_mode"))
print(
    "reference_retrieval_mode:",
    question.get("reference_retrieval_mode"),
)
print("model_runs:", len(model_runs))

driver.close()
