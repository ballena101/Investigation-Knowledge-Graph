# Databricks notebook source
# MAGIC %md
# MAGIC # 38 — Validate scoped Ask / Compare run
# MAGIC
# MAGIC Read-only validation for one persisted QuestionRun.
# MAGIC
# MAGIC Checks:
# MAGIC - QuestionRun belongs to one AnalysisGroup;
# MAGIC - primary document scope is valid for that analysis;
# MAGIC - SOURCE_EVIDENCE answer passage IDs stay inside the primary retrieval snapshot;
# MAGIC - REFERENCE_CONTEXT analyses are completed Class A only;
# MAGIC - REFERENCE_CONTEXT answer passage IDs stay inside the independent
# MAGIC   reference-retrieval snapshot;
# MAGIC - source layers do not cross;
# MAGIC - cited document/page locations are backed by passages from the correct layer;
# MAGIC - governed-query metadata is internally consistent when present;
# MAGIC - no question execution requires graph modification.

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
            coalesce(q.reference_analysis_ids, []) AS reference_analysis_ids,
            q.status AS status,
            q.retrieval_mode AS retrieval_mode,
            q.retrieval_snapshot_id AS retrieval_snapshot_id,
            coalesce(q.retrieval_passage_ids, []) AS retrieval_passage_ids,
            coalesce(q.retrieval_candidate_count, 0) AS retrieval_candidate_count,
            coalesce(q.retrieval_selected_count, 0) AS retrieval_selected_count,
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
print("Primary retrieval:", question.get("retrieval_mode"))
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
    effective_document_ids = (
        analysis_document_ids
    )
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

    effective_document_ids = (
        scope_document_ids
    )
else:
    driver.close()
    raise ValueError(
        f"Unsupported QuestionRun scope_mode: {scope_mode}"
    )

# COMMAND ----------

primary_passages = (
    spark.table(
        ANALYSIS_PASSAGE_TABLE
    )
    .filter(
        F.col("analysis_id")
        == analysis_id
    )
)

if effective_document_ids:
    primary_passages = (
        primary_passages.filter(
            F.col("document_id").isin(
                sorted(
                    effective_document_ids
                )
            )
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

primary_passage_by_id = {
    row["passage_id"]:
        row.asDict(recursive=True)
    for row in primary_rows
}

if not primary_passage_by_id:
    driver.close()
    raise ValueError(
        "The primary QuestionRun scope contains no persisted passages."
    )

print(
    "Primary scoped passages:",
    len(primary_passage_by_id),
)

# COMMAND ----------

reference_analysis_ids = list(
    question.get("reference_analysis_ids")
    or []
)
reference_passage_by_id = {}

if reference_analysis_ids:
    with driver.session() as session:
        reference_meta = [
            record.data()
            for record in session.run(
                """
                UNWIND $reference_analysis_ids AS reference_analysis_id
                MATCH (r:AnalysisGroup {
                    analysis_id: reference_analysis_id
                })
                RETURN
                    r.analysis_id AS analysis_id,
                    r.status AS status,
                    properties(r)["information_class"] AS information_class
                """,
                reference_analysis_ids=reference_analysis_ids,
            )
        ]

    reference_meta_by_id = {
        item["analysis_id"]: item
        for item in reference_meta
    }

    missing = sorted(
        set(reference_analysis_ids)
        - set(reference_meta_by_id)
    )
    if missing:
        driver.close()
        raise ValueError(
            "Reference analyses not found: "
            + ", ".join(missing)
        )

    invalid = sorted(
        reference_analysis_id
        for reference_analysis_id
        in reference_analysis_ids
        if (
            reference_meta_by_id[
                reference_analysis_id
            ].get("status")
            != "COMPLETED"
            or reference_meta_by_id[
                reference_analysis_id
            ].get("information_class")
            != "A"
        )
    )

    if invalid:
        driver.close()
        raise ValueError(
            "REFERENCE_CONTEXT contains analyses that are not "
            "completed Class A: "
            + ", ".join(invalid)
        )

    reference_rows = (
        spark.table(
            ANALYSIS_PASSAGE_TABLE
        )
        .filter(
            F.col("analysis_id").isin(
                reference_analysis_ids
            )
        )
        .select(
            "analysis_id",
            "document_id",
            "passage_id",
            "page_start",
            "page_end",
        )
        .collect()
    )

    reference_passage_by_id = {
        row["passage_id"]:
            row.asDict(recursive=True)
        for row in reference_rows
    }

print(
    "Reference-library passages:",
    len(reference_passage_by_id),
)

# COMMAND ----------

with driver.session() as session:
    model_runs = [
        record.data()
        for record in session.run(
            """
            MATCH (q:QuestionRun {
                question_run_id: $question_run_id
            })-[:HAS_MODEL_ANSWER]->(
                m:QuestionModelRun
            )
            RETURN
                m.model_key AS model_key,
                m.status AS status,
                coalesce(m.passage_ids, []) AS passage_ids,
                coalesce(m.source_evidence_passage_ids, []) AS source_evidence_passage_ids,
                coalesce(m.source_evidence_references, []) AS source_evidence_references,
                coalesce(m.source_evidence_locations, []) AS source_evidence_locations,
                coalesce(m.reference_context_passage_ids, []) AS reference_context_passage_ids,
                coalesce(m.reference_context_references, []) AS reference_context_references,
                coalesce(m.reference_context_locations, []) AS reference_context_locations,
                coalesce(m.insufficient_evidence, false) AS insufficient_evidence
            ORDER BY m.model_key
            """,
            question_run_id=question_run_id,
        )
    ]

print(
    "Question model runs:",
    len(model_runs),
)

# COMMAND ----------

errors = []
validation_rows = []

primary_retrieval_ids = set(
    question.get(
        "retrieval_passage_ids"
    )
    or []
)
reference_retrieval_ids = set(
    question.get(
        "reference_retrieval_passage_ids"
    )
    or []
)

if (
    question.get("status")
    == "COMPLETED"
    and model_runs
    and not question.get(
        "retrieval_snapshot_id"
    )
):
    errors.append(
        "Completed model-answering QuestionRun has no primary retrieval snapshot."
    )

primary_snapshot_outside_scope = sorted(
    passage_id
    for passage_id
    in primary_retrieval_ids
    if passage_id
    not in primary_passage_by_id
)
if primary_snapshot_outside_scope:
    errors.append(
        "Primary retrieval snapshot contains passages outside the selected "
        "primary evidence scope: "
        + str(
            primary_snapshot_outside_scope
        )
    )

if (
    reference_analysis_ids
    and model_runs
    and not question.get(
        "reference_retrieval_snapshot_id"
    )
):
    errors.append(
        "QuestionRun uses reference analyses but has no independent "
        "reference-retrieval snapshot."
    )

reference_snapshot_outside_layer = sorted(
    passage_id
    for passage_id
    in reference_retrieval_ids
    if passage_id
    not in reference_passage_by_id
)
if reference_snapshot_outside_layer:
    errors.append(
        "Reference retrieval snapshot contains passages outside the "
        "selected Class-A reference analyses: "
        + str(
            reference_snapshot_outside_layer
        )
    )

cross_layer_snapshot_ids = sorted(
    primary_retrieval_ids
    & reference_retrieval_ids
)
if cross_layer_snapshot_ids:
    errors.append(
        "The same passage ID appears in both source-layer snapshots: "
        + str(cross_layer_snapshot_ids)
    )

# COMMAND ----------

def validate_locations(
    *,
    raw_locations,
    passage_by_id,
    layer_label,
):
    location_errors = []

    for raw_location in (
        raw_locations or []
    ):
        parts = str(
            raw_location
        ).split("|")

        if len(parts) != 3:
            location_errors.append(
                f"{layer_label}: invalid location format: {raw_location}"
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

        matching_passage = any(
            row["document_id"]
            == document_id
            and row["page_start"]
            == page_start
            and (
                row["page_end"]
                == page_end
                or (
                    row["page_end"]
                    is None
                    and page_end
                    == page_start
                )
            )
            for row in (
                passage_by_id.values()
            )
        )

        if not matching_passage:
            location_errors.append(
                f"{layer_label}: page location is not backed by a passage "
                f"from that layer: {raw_location}"
            )

    return location_errors


for model_run in model_runs:
    model_key = model_run[
        "model_key"
    ]

    source_ids = set(
        model_run.get(
            "source_evidence_passage_ids"
        )
        or []
    )
    reference_ids = set(
        model_run.get(
            "reference_context_passage_ids"
        )
        or []
    )
    combined_ids = set(
        model_run.get(
            "passage_ids"
        )
        or []
    )

    invalid_source_ids = sorted(
        passage_id
        for passage_id in source_ids
        if passage_id
        not in primary_passage_by_id
    )
    if invalid_source_ids:
        errors.append(
            f"{model_key}: SOURCE_EVIDENCE IDs are outside the primary "
            f"scope: {invalid_source_ids}"
        )

    invalid_reference_ids = sorted(
        passage_id
        for passage_id
        in reference_ids
        if passage_id
        not in reference_passage_by_id
    )
    if invalid_reference_ids:
        errors.append(
            f"{model_key}: REFERENCE_CONTEXT IDs are outside the selected "
            f"Class-A reference analyses: {invalid_reference_ids}"
        )

    if primary_retrieval_ids:
        outside_primary_snapshot = sorted(
            source_ids
            - primary_retrieval_ids
        )
        if outside_primary_snapshot:
            errors.append(
                f"{model_key}: SOURCE_EVIDENCE answer IDs are outside the "
                f"primary retrieval snapshot: {outside_primary_snapshot}"
            )

    if reference_ids:
        outside_reference_snapshot = sorted(
            reference_ids
            - reference_retrieval_ids
        )
        if outside_reference_snapshot:
            errors.append(
                f"{model_key}: REFERENCE_CONTEXT answer IDs are outside the "
                f"reference retrieval snapshot: {outside_reference_snapshot}"
            )

    cross_layer_ids = sorted(
        source_ids
        & reference_ids
    )
    if cross_layer_ids:
        errors.append(
            f"{model_key}: answer places passage IDs in both source layers: "
            f"{cross_layer_ids}"
        )

    expected_combined = (
        source_ids
        | reference_ids
    )

    if combined_ids != expected_combined:
        errors.append(
            f"{model_key}: legacy combined passage_ids do not equal the union "
            "of SOURCE_EVIDENCE and REFERENCE_CONTEXT IDs."
        )

    source_location_errors = (
        validate_locations(
            raw_locations=model_run.get(
                "source_evidence_locations"
            ),
            passage_by_id=primary_passage_by_id,
            layer_label="SOURCE_EVIDENCE",
        )
    )
    reference_location_errors = (
        validate_locations(
            raw_locations=model_run.get(
                "reference_context_locations"
            ),
            passage_by_id=reference_passage_by_id,
            layer_label="REFERENCE_CONTEXT",
        )
    )

    errors.extend(
        f"{model_key}: {value}"
        for value in (
            source_location_errors
            + reference_location_errors
        )
    )

    validation_rows.append(
        {
            "model_key": model_key,
            "status": model_run[
                "status"
            ],
            "source_evidence_passages": len(
                source_ids
            ),
            "reference_context_passages": len(
                reference_ids
            ),
            "source_location_errors": len(
                source_location_errors
            ),
            "reference_location_errors": len(
                reference_location_errors
            ),
            "insufficient_evidence": bool(
                model_run.get(
                    "insufficient_evidence"
                )
            ),
        }
    )

if validation_rows:
    display(
        spark.createDataFrame(
            validation_rows
        )
    )

# COMMAND ----------

retrieval_mode = question.get(
    "retrieval_mode"
)

if (
    retrieval_mode
    == "DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1"
):
    if not question.get(
        "retrieval_snapshot_id"
    ):
        errors.append(
            "Deterministic lexical retrieval has no primary retrieval snapshot."
        )

    selected_count = int(
        question.get(
            "retrieval_selected_count"
        )
        or 0
    )

    if (
        primary_retrieval_ids
        and selected_count
        != len(
            primary_retrieval_ids
        )
    ):
        errors.append(
            "retrieval_selected_count does not match primary retrieval_passage_ids."
        )

governed_query_id = question.get(
    "governed_query_id"
)
governed_query_spec_id = (
    question.get(
        "governed_query_spec_id"
    )
)

if governed_query_id:
    if (
        retrieval_mode
        != "GOVERNED_RELATIONSHIP_EVIDENCE"
    ):
        errors.append(
            "governed_query_id is present but primary retrieval_mode is not "
            "GOVERNED_RELATIONSHIP_EVIDENCE."
        )

    if not spark.catalog.tableExists(
        QUERY_SPEC_TABLE
    ):
        errors.append(
            "MAIRA query_specifications table is unavailable."
        )
    else:
        matching_specs = (
            spark.table(
                QUERY_SPEC_TABLE
            )
            .filter(
                (
                    F.col("query_id")
                    == governed_query_id
                )
                & (
                    F.col(
                        "query_spec_id"
                    )
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
    question.get(
        "deterministic_answer"
    )
    and model_runs
):
    errors.append(
        "A deterministic no-support answer should not also have "
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
        "Scoped Ask / Compare source-layer validation failed."
    )

print("")
print(
    "PASS — SCOPED ASK / COMPARE PRESERVES SOURCE_EVIDENCE "
    "AND REFERENCE_CONTEXT BOUNDARIES"
)
print(
    "question_run_id:",
    question_run_id,
)
print(
    "analysis_id:",
    analysis_id,
)
print(
    "primary retrieval:",
    retrieval_mode,
)
print(
    "reference retrieval:",
    question.get(
        "reference_retrieval_mode"
    ),
)
print(
    "model_runs:",
    len(model_runs),
)

driver.close()
