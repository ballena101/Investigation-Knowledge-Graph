# Databricks notebook source
# MAGIC %md
# MAGIC # 10 — Create raw source document volume
# MAGIC
# MAGIC Creates the managed Unity Catalog volume used to persist source PDFs
# MAGIC and other uploaded analysis documents.
# MAGIC
# MAGIC One analysis group will use a subdirectory:
# MAGIC
# MAGIC /Volumes/bdw_analysis_prod/kg_poc/investigation_sources/<analysis_id>/

# COMMAND ----------

CATALOG = "bdw_analysis_prod"
SCHEMA = "kg_poc"
VOLUME = "investigation_sources"

spark.sql(f"""
CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}
COMMENT 'Raw source documents for Investigation Knowledge Graph analyses'
""")

VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

print("Volume ready:", f"{CATALOG}.{SCHEMA}.{VOLUME}")
print("Volume path:", VOLUME_PATH)

# COMMAND ----------

display(
    spark.sql(
        f"DESCRIBE VOLUME {CATALOG}.{SCHEMA}.{VOLUME}"
    )
)
