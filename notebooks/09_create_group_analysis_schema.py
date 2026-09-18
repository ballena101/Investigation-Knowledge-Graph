# Databricks notebook source
# MAGIC %md
# MAGIC # 09 — Create group-analysis metadata model
# MAGIC
# MAGIC Creates the initial Delta / Unity Catalog structures for generic
# MAGIC document-group analyses.
# MAGIC
# MAGIC One uploaded group = one analysis_id.

# COMMAND ----------

CATALOG = "bdw_analysis_prod"
SCHEMA = "kg_poc"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.analysis_group (
    analysis_id STRING NOT NULL,
    analysis_title STRING NOT NULL,
    analysis_objective STRING,
    created_by STRING,
    created_at TIMESTAMP NOT NULL,
    status STRING NOT NULL,
    document_count INT,
    pipeline_version STRING,
    graph_version STRING,
    error_message STRING
)
USING DELTA
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.analysis_document (
    analysis_id STRING NOT NULL,
    document_id STRING NOT NULL,
    original_filename STRING NOT NULL,
    mime_type STRING,
    byte_size BIGINT,
    sha256 STRING NOT NULL,
    storage_uri STRING,
    source_type STRING,
    page_count INT,
    uploaded_by STRING,
    uploaded_at TIMESTAMP NOT NULL,
    extraction_status STRING,
    extraction_version STRING,
    error_message STRING
)
USING DELTA
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.analysis_passage (
    analysis_id STRING NOT NULL,
    document_id STRING NOT NULL,
    passage_id STRING NOT NULL,
    page_start INT,
    page_end INT,
    passage_order INT,
    passage_text STRING NOT NULL,
    text_sha256 STRING NOT NULL,
    extraction_version STRING,
    created_at TIMESTAMP NOT NULL
)
USING DELTA
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.analysis_run (
    run_id STRING NOT NULL,
    analysis_id STRING NOT NULL,
    run_type STRING NOT NULL,
    run_status STRING NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    model_endpoint STRING,
    model_version STRING,
    pipeline_version STRING,
    error_message STRING
)
USING DELTA
""")

# COMMAND ----------

for table in [
    "analysis_group",
    "analysis_document",
    "analysis_passage",
    "analysis_run",
]:
    count = spark.table(f"{CATALOG}.{SCHEMA}.{table}").count()
    print(f"{table}: ready ({count} rows)")
