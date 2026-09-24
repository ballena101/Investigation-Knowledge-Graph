# Databricks notebook source
# MAGIC %md
# MAGIC # 64 — Create IKF Timeline Delta schema
# MAGIC
# MAGIC **Purpose:** create the Unity Catalog / Delta analytical snapshot table for
# MAGIC human-validated IKF timeline events.
# MAGIC
# MAGIC This notebook performs **no LLM inference**, **no Whisper transcription** and
# MAGIC **no Neo4j mutation**. It is schema-only and idempotent (`IF NOT EXISTS`).
# MAGIC
# MAGIC Timeline V0.1 interactive writes remain in the existing Neo4j transaction
# MAGIC path. A later sync notebook/job can materialize those validated records into
# MAGIC this table for cross-case analytics without rerunning any model.

# COMMAND ----------

TIMELINE_TABLE = "bdw_analysis_prod.kg_poc.ikf_timeline_event"
TIMELINE_SCHEMA_VERSION = "IKF_TIMELINE_DELTA_V0.1"

print("Timeline Delta target:", TIMELINE_TABLE)
print("Schema version:", TIMELINE_SCHEMA_VERSION)

# COMMAND ----------

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {TIMELINE_TABLE} (
        timeline_event_id STRING NOT NULL,
        analysis_id STRING NOT NULL,
        case_id STRING,
        timeline_version STRING NOT NULL,
        summary STRING NOT NULL,
        event_type STRING NOT NULL,
        phase STRING NOT NULL,
        time_basis STRING NOT NULL,
        time_precision STRING NOT NULL,
        event_time_start TIMESTAMP,
        event_time_end TIMESTAMP,
        relative_start_s DOUBLE,
        relative_end_s DOUBLE,
        source_node_id STRING,
        evidence_references ARRAY<STRING>,
        evidence_locations ARRAY<STRING>,
        review_status STRING NOT NULL,
        reviewed_by STRING,
        reviewed_at TIMESTAMP,
        source_system STRING NOT NULL,
        snapshot_at TIMESTAMP NOT NULL
    )
    USING DELTA
    TBLPROPERTIES (
        'ikf.contract' = '{TIMELINE_SCHEMA_VERSION}',
        'ikf.authority' = 'HUMAN_VALIDATED_TIMELINE',
        'ikf.model_inference_required' = 'false',
        'delta.enableChangeDataFeed' = 'true'
    )
    """
)

# COMMAND ----------

columns = spark.sql(f"DESCRIBE TABLE {TIMELINE_TABLE}")
display(columns)

print("PASS — Timeline Delta schema is available.")
print("No timeline rows were created or changed by this notebook.")
