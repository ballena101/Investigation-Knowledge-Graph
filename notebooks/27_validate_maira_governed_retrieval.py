# Databricks notebook source
# MAGIC %md
# MAGIC # 27 — Validate MAIRA governed retrieval for IKF
# MAGIC
# MAGIC Read-only checkpoint after notebook 25. It applies one persisted MAIRA
# MAGIC query specification to the exact MAIRA passages associated with an IKF
# MAGIC analysis, then exposes the frozen result as a temporary view.
# MAGIC
# MAGIC This notebook creates no table, invokes no model and modifies no graph.

# COMMAND ----------

dbutils.widgets.text("analysis_id", "", "Analysis ID")
dbutils.widgets.text("query_id", "Q001", "MAIRA query ID")
dbutils.widgets.text(
    "query_spec_id",
    "",
    "MAIRA query specification ID (optional)",
)
dbutils.widgets.text(
    "maira_src_path",
    "",
    "MAIRA src path (optional)",
)

# COMMAND ----------

import hashlib
import importlib.util
import json
import os
import re
import sys

from pyspark.sql import Row
from pyspark.sql import functions as F


def resolve_maira_src_path():
    if importlib.util.find_spec("maira") is not None:
        return None

    configured_path = dbutils.widgets.get("maira_src_path").strip()
    current_user = spark.sql(
        "SELECT current_user() AS username"
    ).first()["username"]

    candidates = [
        configured_path,
        f"/Workspace/Users/{current_user}/MAIRA/src",
        f"/Workspace/Users/{current_user}/MAIRA-main/src",
    ]

    checked_paths = []
    for candidate in candidates:
        if not candidate:
            continue

        candidate = candidate.rstrip("/")
        if os.path.isfile(
            os.path.join(candidate, "maira", "__init__.py")
        ):
            src_path = candidate
        elif os.path.isfile(
            os.path.join(candidate, "src", "maira", "__init__.py")
        ):
            src_path = os.path.join(candidate, "src")
        else:
            checked_paths.append(candidate)
            continue

        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        importlib.invalidate_caches()

        if importlib.util.find_spec("maira") is not None:
            return src_path

        checked_paths.append(src_path)

    raise ModuleNotFoundError(
        "The MAIRA package is not installed and no sibling MAIRA/src folder "
        "was found. Checked: " + ", ".join(checked_paths)
    )


resolved_maira_src_path = resolve_maira_src_path()

from maira.integration.ikf_passage_contract import (
    PASSAGE_CONTRACT_VERSION,
)
from maira.query.terms import derive_evidence_terms
from maira.retrieval.lexical import retrieve_candidates


ANALYSIS_DOCUMENT_TABLE = "bdw_analysis_prod.kg_poc.analysis_document"
MAIRA_DOCUMENT_TABLE = "bdw_analysis_prod.maira.documents"
MAIRA_PASSAGE_TABLE = "bdw_analysis_prod.maira.passages"
QUERY_SPEC_TABLE = "bdw_analysis_prod.maira.query_specifications"
QUERY_CONCEPT_TABLE = "bdw_analysis_prod.maira.query_spec_concepts"

RETRIEVAL_CONTRACT_VERSION = "MAIRA_GOVERNED_LEXICAL_V0.1"
TEMP_VIEW = "maira_ikf_retrieval_snapshot"

analysis_id = dbutils.widgets.get("analysis_id").strip()
query_id = dbutils.widgets.get("query_id").strip().upper()
requested_query_spec_id = dbutils.widgets.get("query_spec_id").strip()

is_app_analysis = bool(re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id))
is_controlled_bridge_test = bool(
    re.fullmatch(r"ikf_maira_test_[0-9]{3}", analysis_id)
)
if not (is_app_analysis or is_controlled_bridge_test):
    raise ValueError(
        "Enter an IKF App analysis_id or a controlled "
        "ikf_maira_test_<three digits> bridge-test ID."
    )

if not re.fullmatch(r"Q[0-9]{3}", query_id):
    raise ValueError("Enter a governed MAIRA query ID such as Q001.")

print("Analysis:", analysis_id)
print(
    "MAIRA source:",
    resolved_maira_src_path or "installed package",
)
print("Query:", query_id)
print("Passage contract:", PASSAGE_CONTRACT_VERSION)
print("Retrieval contract:", RETRIEVAL_CONTRACT_VERSION)

# COMMAND ----------

analysis_documents = (
    spark.table(ANALYSIS_DOCUMENT_TABLE)
    .filter(F.col("analysis_id") == analysis_id)
    .select(
        "analysis_id",
        F.col("document_id").alias("ikf_document_id"),
        F.lower(F.col("sha256")).alias("source_document_sha256"),
    )
)

if analysis_documents.count() == 0:
    raise ValueError(f"No IKF analysis documents found for {analysis_id}.")

duplicate_inputs = (
    analysis_documents.groupBy("source_document_sha256")
    .count()
    .filter(F.col("count") > 1)
)
if duplicate_inputs.count():
    display(duplicate_inputs)
    raise ValueError("The IKF analysis contains duplicate document content.")

maira_documents = spark.table(MAIRA_DOCUMENT_TABLE).select(
    F.col("document_id").alias("maira_document_id"),
    "report_package_id",
    F.lower(F.col("sha256")).alias("source_document_sha256"),
)

document_matches = analysis_documents.join(
    maira_documents,
    on="source_document_sha256",
    how="left",
)

match_counts = document_matches.groupBy(
    "analysis_id",
    "ikf_document_id",
    "source_document_sha256",
).agg(F.countDistinct("maira_document_id").alias("maira_document_matches"))

invalid_matches = match_counts.filter(F.col("maira_document_matches") != 1)
if invalid_matches.count():
    display(invalid_matches)
    raise ValueError(
        "Every IKF document must match exactly one MAIRA document by full "
        "SHA-256 before governed retrieval can run."
    )

resolved_documents = document_matches.filter(
    F.col("maira_document_id").isNotNull()
)

maira_passages = spark.table(MAIRA_PASSAGE_TABLE).select(
    F.col("document_id").alias("maira_document_id"),
    "passage_id",
    "passage_number",
    "start_page",
    "end_page",
    "passage_text",
    F.lower(F.col("passage_text_sha256")).alias("text_sha256"),
    "chunking_method",
    "chunking_version",
)

bridge = resolved_documents.join(
    maira_passages,
    on="maira_document_id",
    how="inner",
).select(
    "analysis_id",
    "ikf_document_id",
    "maira_document_id",
    "report_package_id",
    "passage_id",
    "passage_number",
    "start_page",
    "end_page",
    "passage_text",
    "text_sha256",
    "source_document_sha256",
    "chunking_method",
    "chunking_version",
)

invalid_passages = bridge.filter(
    F.col("passage_id").isNull()
    | F.col("passage_text").isNull()
    | (F.length(F.trim(F.col("passage_text"))) == 0)
    | (F.sha2(F.col("passage_text"), 256) != F.col("text_sha256"))
)
if invalid_passages.count():
    display(invalid_passages)
    raise ValueError("MAIRA passage integrity validation failed.")

if bridge.count() == 0:
    raise ValueError("The matched MAIRA documents contain no passages.")

# COMMAND ----------

query_specs = (
    spark.table(QUERY_SPEC_TABLE)
    .filter(F.upper(F.col("query_id")) == query_id)
)

if requested_query_spec_id:
    query_specs = query_specs.filter(
        F.col("query_spec_id") == requested_query_spec_id
    )

query_spec_rows = query_specs.select(
    "query_spec_id",
    "query_id",
    "query_spec_version",
    "user_query",
    "relationship",
).dropDuplicates().collect()

if not query_spec_rows:
    raise ValueError(
        f"No governed MAIRA query specification found for {query_id}."
    )

if len(query_spec_rows) != 1:
    display(query_specs.orderBy("query_spec_id"))
    raise ValueError(
        f"Found {len(query_spec_rows)} specifications for {query_id}. "
        "Enter the exact query_spec_id to select one deterministically."
    )

query_spec = query_spec_rows[0].asDict()
query_spec_id = query_spec["query_spec_id"]

concept_rows = (
    spark.table(QUERY_CONCEPT_TABLE)
    .filter(F.col("query_spec_id") == query_spec_id)
    .select(
        "query_spec_id",
        "component_role",
        "query_token",
        "code_value",
    )
    .collect()
)

terms = derive_evidence_terms(
    [row.asDict() for row in concept_rows],
    query_spec_id,
)

print("Query specification:", query_spec_id)
print("Question:", query_spec["user_query"])
print("Requested relationship:", query_spec["relationship"])
for role, values in terms.items():
    print(role + ":", len(values), "governed terms")

# COMMAND ----------

bridge_rows = bridge.orderBy(
    "report_package_id",
    "maira_document_id",
    "passage_number",
).collect()

retrieval_input = [
    {
        "report_package_id": row["report_package_id"],
        "document_id": row["maira_document_id"],
        "passage_id": row["passage_id"],
        "passage_number": row["passage_number"],
        "start_page": row["start_page"],
        "end_page": row["end_page"],
        "passage_text": row["passage_text"],
    }
    for row in bridge_rows
]

retrieval = retrieve_candidates(retrieval_input, terms)
candidate_package_ids = {
    item["report_package_id"]
    for item in retrieval.package_candidates
}

selected_matches = [
    item
    for item in retrieval.passage_matches
    if item["report_package_id"] in candidate_package_ids
]

if not candidate_package_ids or not selected_matches:
    raise ValueError(
        "The governed retrieval specification found no complete candidate "
        "package in this analysis. No evidence snapshot was created."
    )

bridge_by_passage_id = {
    row["passage_id"]: row.asDict()
    for row in bridge_rows
}

selected_matches = sorted(
    selected_matches,
    key=lambda item: (
        item["report_package_id"],
        item["document_id"],
        item["passage_number"],
        item["passage_id"],
    ),
)

snapshot_material = "\n".join(
    "|".join(
        (
            item["passage_id"],
            bridge_by_passage_id[item["passage_id"]]["text_sha256"],
        )
    )
    for item in selected_matches
)

retrieval_snapshot_id = "snapshot_" + hashlib.sha256(
    "|".join(
        (
            analysis_id,
            query_spec_id,
            PASSAGE_CONTRACT_VERSION,
            RETRIEVAL_CONTRACT_VERSION,
            snapshot_material,
        )
    ).encode("utf-8")
).hexdigest()[:32]

snapshot_rows = []
for item in selected_matches:
    source = bridge_by_passage_id[item["passage_id"]]
    matched_terms = {
        role: list(values)
        for role, values in item["matched_terms"].items()
    }
    snapshot_rows.append(
        Row(
            retrieval_snapshot_id=retrieval_snapshot_id,
            retrieval_contract_version=RETRIEVAL_CONTRACT_VERSION,
            passage_contract_version=PASSAGE_CONTRACT_VERSION,
            analysis_id=analysis_id,
            query_spec_id=query_spec_id,
            query_id=query_id,
            report_package_id=source["report_package_id"],
            ikf_document_id=source["ikf_document_id"],
            maira_document_id=source["maira_document_id"],
            passage_id=source["passage_id"],
            passage_order=source["passage_number"],
            page_start=source["start_page"],
            page_end=source["end_page"],
            passage_text=source["passage_text"],
            text_sha256=source["text_sha256"],
            matched_roles=sorted(matched_terms),
            matched_terms_json=json.dumps(
                matched_terms,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    )

snapshot_df = spark.createDataFrame(snapshot_rows)
snapshot_df.createOrReplaceTempView(TEMP_VIEW)

cluster_temp_view = (
    TEMP_VIEW
    + "_"
    + retrieval_snapshot_id.removeprefix("snapshot_")
)
snapshot_df.createOrReplaceGlobalTempView(cluster_temp_view)

# COMMAND ----------

same_passage_ids = {
    item["passage_id"]
    for item in retrieval.same_passage_candidates
}

display(
    snapshot_df.select(
        "report_package_id",
        "maira_document_id",
        "passage_id",
        "passage_order",
        "page_start",
        "page_end",
        "matched_roles",
        F.col("passage_id").isin(sorted(same_passage_ids)).alias(
            "all_roles_in_same_passage"
        ),
        F.length("passage_text").alias("characters"),
    ).orderBy(
        "report_package_id",
        "maira_document_id",
        "page_start",
        "passage_order",
    )
)

print("Bridge passages inspected:", len(bridge_rows))
print("Passages matching at least one governed role:", len(retrieval.passage_matches))
print("All-role same-passage candidates:", len(retrieval.same_passage_candidates))
print("Complete candidate packages:", len(retrieval.package_candidates))
print("Frozen retrieved passages:", len(snapshot_rows))
print("Retrieval snapshot ID:", retrieval_snapshot_id)
print("Notebook temporary view:", TEMP_VIEW)
print("Cluster temporary view:", "global_temp." + cluster_temp_view)
print("PASS — MAIRA RETRIEVAL CHECKPOINT")
