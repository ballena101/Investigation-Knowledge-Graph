# Databricks notebook source
# MAGIC %md
# MAGIC # 26 — Create one controlled MAIRA bridge-test analysis
# MAGIC
# MAGIC Registers one existing MAIRA investigation document in the IKF Delta
# MAGIC metadata tables so notebook 25 can validate the passage bridge.
# MAGIC
# MAGIC The notebook does not copy the source file, create passages, invoke a
# MAGIC model or modify Neo4j. Reruns are idempotent for the selected document.

# COMMAND ----------

dbutils.widgets.text(
    "maira_document_id",
    "",
    "MAIRA document ID (optional)",
)
dbutils.widgets.dropdown(
    "confirm_create",
    "NO",
    ["NO", "YES"],
    "Create controlled analysis",
)

# COMMAND ----------

import hashlib

from pyspark.sql import functions as F
from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


PASSAGE_CONTRACT_VERSION = "MAIRA_IKF_PASSAGE_V0.1"
MAIRA_DOCUMENT_TABLE = "bdw_analysis_prod.maira.documents"
MAIRA_PASSAGE_TABLE = "bdw_analysis_prod.maira.passages"
IKF_ANALYSIS_GROUP_TABLE = "bdw_analysis_prod.kg_poc.analysis_group"
IKF_ANALYSIS_DOCUMENT_TABLE = "bdw_analysis_prod.kg_poc.analysis_document"

requested_document_id = dbutils.widgets.get(
    "maira_document_id"
).strip()
confirm_create = dbutils.widgets.get("confirm_create").strip().upper()

# COMMAND ----------

passage_summary = (
    spark.table(MAIRA_PASSAGE_TABLE)
    .groupBy("document_id")
    .agg(
        F.count("passage_id").alias("passage_count"),
        F.max("end_page").cast("int").alias("page_count"),
    )
)

eligible_documents = (
    spark.table(MAIRA_DOCUMENT_TABLE)
    .filter(F.col("corpus_type") == "INVESTIGATION")
    .filter(F.col("processing_status") == "PARSED")
    .join(passage_summary, on="document_id", how="inner")
    .filter(F.col("passage_count") > 0)
    .select(
        "document_id",
        "report_package_id",
        "report_title",
        "document_role",
        "source_filename",
        "file_path",
        "file_size_bytes",
        F.lower(F.col("sha256")).alias("sha256"),
        "page_count",
        "passage_count",
    )
)

if requested_document_id:
    eligible_documents = eligible_documents.filter(
        F.col("document_id") == requested_document_id
    )

selected_rows = (
    eligible_documents.orderBy(
        F.col("report_title").asc_nulls_last(),
        F.col("document_id"),
    )
    .limit(1)
    .collect()
)

if not selected_rows:
    if requested_document_id:
        raise ValueError(
            "The requested MAIRA document is not a parsed investigation "
            "document with persisted passages."
        )
    raise ValueError(
        "No eligible parsed MAIRA investigation document with passages exists."
    )

selected = selected_rows[0]

display(
    spark.createDataFrame([selected.asDict()]).select(
        "document_id",
        "report_title",
        "document_role",
        "source_filename",
        "page_count",
        "passage_count",
        "sha256",
    )
)

if confirm_create != "YES":
    dbutils.notebook.exit(
        "Preview only. Set 'Create controlled analysis' to YES and run all "
        "again to register this document in IKF."
    )

# COMMAND ----------

if not selected.sha256 or len(selected.sha256) != 64:
    raise ValueError("The selected MAIRA document does not have a valid SHA-256.")

identity_source = (
    f"{PASSAGE_CONTRACT_VERSION}|"
    f"{selected.document_id}|{selected.sha256}"
)
analysis_id = "analysis_" + hashlib.sha256(
    identity_source.encode("utf-8")
).hexdigest()[:32]
ikf_document_id = "doc_" + selected.sha256[:24]

current_user = spark.sql(
    "SELECT current_user() AS current_user"
).first()["current_user"]

print("Controlled analysis ID:", analysis_id)
print("IKF document ID:", ikf_document_id)
print("MAIRA document ID:", selected.document_id)

# COMMAND ----------

analysis_group_schema = StructType([
    StructField("analysis_id", StringType(), False),
    StructField("analysis_title", StringType(), False),
    StructField("analysis_objective", StringType(), True),
    StructField("created_by", StringType(), True),
    StructField("created_at", TimestampType(), False),
    StructField("status", StringType(), False),
    StructField("document_count", IntegerType(), True),
    StructField("pipeline_version", StringType(), True),
    StructField("graph_version", StringType(), True),
    StructField("error_message", StringType(), True),
])

analysis_group_stage = spark.createDataFrame(
    [(
        analysis_id,
        f"MAIRA bridge test — {selected.report_title or selected.document_id}",
        "Validate the read-only MAIRA-to-IKF passage contract.",
        current_user,
        spark.sql("SELECT current_timestamp() AS ts").first()["ts"],
        "BRIDGE_TEST_READY",
        1,
        PASSAGE_CONTRACT_VERSION,
        None,
        None,
    )],
    schema=analysis_group_schema,
)
analysis_group_stage.createOrReplaceTempView(
    "ikf_maira_bridge_analysis_group_stage"
)

spark.sql(f"""
MERGE INTO {IKF_ANALYSIS_GROUP_TABLE} AS target
USING ikf_maira_bridge_analysis_group_stage AS source
ON target.analysis_id = source.analysis_id
WHEN NOT MATCHED THEN INSERT (
    analysis_id,
    analysis_title,
    analysis_objective,
    created_by,
    created_at,
    status,
    document_count,
    pipeline_version,
    graph_version,
    error_message
)
VALUES (
    source.analysis_id,
    source.analysis_title,
    source.analysis_objective,
    source.created_by,
    source.created_at,
    source.status,
    source.document_count,
    source.pipeline_version,
    source.graph_version,
    source.error_message
)
""")

# COMMAND ----------

analysis_document_schema = StructType([
    StructField("analysis_id", StringType(), False),
    StructField("document_id", StringType(), False),
    StructField("original_filename", StringType(), False),
    StructField("mime_type", StringType(), True),
    StructField("byte_size", LongType(), True),
    StructField("sha256", StringType(), False),
    StructField("storage_uri", StringType(), True),
    StructField("source_type", StringType(), True),
    StructField("page_count", IntegerType(), True),
    StructField("uploaded_by", StringType(), True),
    StructField("uploaded_at", TimestampType(), False),
    StructField("extraction_status", StringType(), True),
    StructField("extraction_version", StringType(), True),
    StructField("error_message", StringType(), True),
])

analysis_document_stage = spark.createDataFrame(
    [(
        analysis_id,
        ikf_document_id,
        selected.source_filename or f"{selected.document_id}.pdf",
        "application/pdf",
        selected.file_size_bytes,
        selected.sha256,
        selected.file_path,
        "PDF",
        selected.page_count,
        current_user,
        spark.sql("SELECT current_timestamp() AS ts").first()["ts"],
        "MAIRA_CANONICAL",
        PASSAGE_CONTRACT_VERSION,
        None,
    )],
    schema=analysis_document_schema,
)
analysis_document_stage.createOrReplaceTempView(
    "ikf_maira_bridge_analysis_document_stage"
)

spark.sql(f"""
MERGE INTO {IKF_ANALYSIS_DOCUMENT_TABLE} AS target
USING ikf_maira_bridge_analysis_document_stage AS source
ON target.analysis_id = source.analysis_id
AND target.document_id = source.document_id
WHEN NOT MATCHED THEN INSERT (
    analysis_id,
    document_id,
    original_filename,
    mime_type,
    byte_size,
    sha256,
    storage_uri,
    source_type,
    page_count,
    uploaded_by,
    uploaded_at,
    extraction_status,
    extraction_version,
    error_message
)
VALUES (
    source.analysis_id,
    source.document_id,
    source.original_filename,
    source.mime_type,
    source.byte_size,
    source.sha256,
    source.storage_uri,
    source.source_type,
    source.page_count,
    source.uploaded_by,
    source.uploaded_at,
    source.extraction_status,
    source.extraction_version,
    source.error_message
)
""")

# COMMAND ----------

verification = spark.sql(f"""
SELECT
    ag.analysis_id,
    ag.analysis_title,
    ag.status,
    ad.document_id AS ikf_document_id,
    md.document_id AS maira_document_id,
    ad.sha256,
    COUNT(p.passage_id) AS maira_passages
FROM {IKF_ANALYSIS_GROUP_TABLE} ag
JOIN {IKF_ANALYSIS_DOCUMENT_TABLE} ad
    ON ag.analysis_id = ad.analysis_id
JOIN {MAIRA_DOCUMENT_TABLE} md
    ON LOWER(ad.sha256) = LOWER(md.sha256)
JOIN {MAIRA_PASSAGE_TABLE} p
    ON md.document_id = p.document_id
WHERE ag.analysis_id = '{analysis_id}'
GROUP BY
    ag.analysis_id,
    ag.analysis_title,
    ag.status,
    ad.document_id,
    md.document_id,
    ad.sha256
""")

if verification.count() != 1:
    display(verification)
    raise ValueError(
        "Controlled analysis registration did not produce exactly one "
        "MAIRA document match."
    )

display(verification)
print("CREATED —", analysis_id)
print("Next: enter this analysis_id in notebook 25 and run all.")
