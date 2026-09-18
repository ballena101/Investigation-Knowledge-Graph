# Databricks notebook source
# MAGIC %md
# MAGIC # 12 — Add multilingual metadata
# MAGIC
# MAGIC Adds language metadata required by the generic group-analysis App.
# MAGIC
# MAGIC Design:
# MAGIC - source language handling is independent from output language;
# MAGIC - documents may be in different languages;
# MAGIC - original source text is always preserved;
# MAGIC - detected language is metadata, not a replacement for source text.

# COMMAND ----------

CATALOG = "bdw_analysis_prod"
SCHEMA = "kg_poc"

GROUP_TABLE = f"{CATALOG}.{SCHEMA}.analysis_group"
DOCUMENT_TABLE = f"{CATALOG}.{SCHEMA}.analysis_document"
PASSAGE_TABLE = f"{CATALOG}.{SCHEMA}.analysis_passage"

# COMMAND ----------

def add_column_if_missing(table_name, column_name, data_type):
    existing = {
        field.name
        for field in spark.table(table_name).schema.fields
    }

    if column_name in existing:
        print(f"{table_name}.{column_name}: already present")
        return

    spark.sql(
        f"ALTER TABLE {table_name} "
        f"ADD COLUMNS ({column_name} {data_type})"
    )
    print(f"{table_name}.{column_name}: added")


add_column_if_missing(
    GROUP_TABLE,
    "language_mode",
    "STRING",
)

add_column_if_missing(
    GROUP_TABLE,
    "output_language",
    "STRING",
)

add_column_if_missing(
    DOCUMENT_TABLE,
    "detected_language",
    "STRING",
)

add_column_if_missing(
    DOCUMENT_TABLE,
    "language_confidence",
    "DOUBLE",
)

add_column_if_missing(
    PASSAGE_TABLE,
    "detected_language",
    "STRING",
)

# COMMAND ----------

print("\nMultilingual metadata ready.")

for table_name in [
    GROUP_TABLE,
    DOCUMENT_TABLE,
    PASSAGE_TABLE,
]:
    print("\n", table_name)
    for field in spark.table(table_name).schema.fields:
        if "language" in field.name:
            print(" -", field.name, field.dataType.simpleString())
