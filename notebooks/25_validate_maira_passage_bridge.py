# Databricks notebook source
# MAGIC %md
# MAGIC # 25 — Validate the MAIRA passage bridge
# MAGIC
# MAGIC Read-only parity gate between MAIRA's authoritative investigation
# MAGIC passages and one IKF analysis. No table, graph or model output is changed.

# COMMAND ----------

dbutils.widgets.text("analysis_id", "", "Analysis ID")

# COMMAND ----------

import re

from pyspark.sql import functions as F

try:
    from maira.integration.ikf_passage_contract import (
        IKF_BRIDGE_FIELDS,
        PASSAGE_CONTRACT_VERSION,
    )
    CONTRACT_SOURCE = "MAIRA_PACKAGE"
except ModuleNotFoundError:
    # Compatibility fallback for the first cross-repository Databricks run.
    # A final integration pass still requires the MAIRA package import.
    PASSAGE_CONTRACT_VERSION = "MAIRA_IKF_PASSAGE_V0.1"
    IKF_BRIDGE_FIELDS = (
        "passage_contract_version",
        "analysis_id",
        "ikf_document_id",
        "maira_document_id",
        "report_package_id",
        "passage_id",
        "passage_order",
        "page_start",
        "page_end",
        "passage_text",
        "text_sha256",
        "source_document_sha256",
        "chunking_method",
        "chunking_version",
    )
    CONTRACT_SOURCE = "IKF_COMPATIBILITY_FALLBACK"


ANALYSIS_DOCUMENT_TABLE = "bdw_analysis_prod.kg_poc.analysis_document"
MAIRA_DOCUMENT_TABLE = "bdw_analysis_prod.maira.documents"
MAIRA_PASSAGE_TABLE = "bdw_analysis_prod.maira.passages"

analysis_id = dbutils.widgets.get("analysis_id").strip()
is_app_analysis = bool(
    re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id)
)
is_controlled_bridge_test = bool(
    re.fullmatch(r"ikf_maira_test_[0-9]{3}", analysis_id)
)
if not (is_app_analysis or is_controlled_bridge_test):
    raise ValueError(
        "Enter an IKF App analysis_id or a controlled "
        "ikf_maira_test_<three digits> bridge-test ID."
    )

print("Analysis:", analysis_id)
print("Contract:", PASSAGE_CONTRACT_VERSION)
print("Contract source:", CONTRACT_SOURCE)
if CONTRACT_SOURCE != "MAIRA_PACKAGE":
    print(
        "WARNING: validating the data bridge with the IKF compatibility "
        "contract; MAIRA package import remains pending."
    )

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
).agg(
    F.countDistinct("maira_document_id").alias("maira_document_matches")
)

invalid_matches = match_counts.filter(F.col("maira_document_matches") != 1)
if invalid_matches.count():
    display(invalid_matches)
    raise ValueError(
        "Every IKF document must match exactly one MAIRA document by full "
        "SHA-256 before the passage bridge can be used."
    )

resolved_documents = document_matches.filter(
    F.col("maira_document_id").isNotNull()
)

display(
    resolved_documents.select(
        "ikf_document_id",
        "maira_document_id",
        "report_package_id",
        "source_document_sha256",
    ).orderBy("ikf_document_id")
)

# COMMAND ----------

maira_passages = spark.table(MAIRA_PASSAGE_TABLE).select(
    F.col("document_id").alias("maira_document_id"),
    "passage_id",
    "passage_number",
    "start_page",
    "end_page",
    "passage_text",
    "passage_text_sha256",
    "chunking_method",
    "chunking_version",
)

bridge = resolved_documents.join(
    maira_passages,
    on="maira_document_id",
    how="inner",
).select(
    F.lit(PASSAGE_CONTRACT_VERSION).alias("passage_contract_version"),
    "analysis_id",
    "ikf_document_id",
    "maira_document_id",
    "report_package_id",
    "passage_id",
    F.col("passage_number").alias("passage_order"),
    F.col("start_page").alias("page_start"),
    F.col("end_page").alias("page_end"),
    "passage_text",
    F.lower(F.col("passage_text_sha256")).alias("text_sha256"),
    "source_document_sha256",
    "chunking_method",
    "chunking_version",
)

if tuple(bridge.columns) != IKF_BRIDGE_FIELDS:
    raise ValueError(
        "Bridge columns differ from the installed MAIRA contract: "
        f"{bridge.columns}"
    )

passage_counts = bridge.groupBy("ikf_document_id").agg(
    F.count("passage_id").alias("passages")
)
missing_passages = resolved_documents.join(
    passage_counts,
    on="ikf_document_id",
    how="left",
).filter(F.coalesce(F.col("passages"), F.lit(0)) == 0)
if missing_passages.count():
    display(missing_passages)
    raise ValueError("One or more matched MAIRA documents have no passages.")

duplicate_passage_ids = (
    bridge.groupBy("passage_id")
    .count()
    .filter(F.col("count") > 1)
)
if duplicate_passage_ids.count():
    display(duplicate_passage_ids)
    raise ValueError("Duplicate MAIRA passage IDs found in the bridge.")

required_fields = (
    "analysis_id",
    "ikf_document_id",
    "maira_document_id",
    "report_package_id",
    "passage_id",
    "passage_text",
    "text_sha256",
    "source_document_sha256",
    "chunking_method",
    "chunking_version",
)
null_condition = F.lit(False)
for field in required_fields:
    null_condition = null_condition | F.col(field).isNull()

invalid_rows = bridge.filter(
    null_condition
    | (F.length(F.trim(F.col("passage_text"))) == 0)
    | (F.col("page_start") < 1)
    | (F.col("page_end") < F.col("page_start"))
    | (F.col("passage_order") < 1)
    | (F.sha2(F.col("passage_text"), 256) != F.col("text_sha256"))
)
if invalid_rows.count():
    display(invalid_rows)
    raise ValueError("MAIRA passage contract integrity validation failed.")

bridge.createOrReplaceTempView("maira_ikf_passage_bridge")

display(
    bridge.select(
        "ikf_document_id",
        "maira_document_id",
        "passage_id",
        "page_start",
        "page_end",
        "chunking_method",
        "chunking_version",
        F.length("passage_text").alias("characters"),
    ).orderBy("ikf_document_id", "passage_order")
)

print("Documents validated:", passage_counts.count())
print("Passages validated:", bridge.count())
print("Temporary view: maira_ikf_passage_bridge")
if CONTRACT_SOURCE == "MAIRA_PACKAGE":
    print("PASS —", PASSAGE_CONTRACT_VERSION)
else:
    print("PASS — DATA BRIDGE —", PASSAGE_CONTRACT_VERSION)
    print("PENDING — restore the MAIRA package contract import")
