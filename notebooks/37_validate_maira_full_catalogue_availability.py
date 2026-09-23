# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # 37 — Validate full MAIRA catalogue availability to IKF
# MAGIC
# MAGIC Purpose: perform a read-only, no-LLM validation that investigation material already
# MAGIC registered/processed by MAIRA is available to IKF through the canonical MAIRA tables.
# MAGIC
# MAGIC This notebook does **not** download documents, call an LLM, write Delta tables,
# MAGIC modify Neo4j, or deploy the app.
# MAGIC
# MAGIC Availability rules:
# MAGIC - `MAIN_REPORT` documents are IKF-query-ready only when they have at least one MAIRA passage.
# MAGIC - Supplementary files (`ANNEX`, `APPENDIX`, `OTHER_SUPPORTING_DOCUMENT`) are audited separately,
# MAGIC   because the current IKF query runner intentionally scopes analytical queries to
# MAGIC   `INVESTIGATION` + `MAIN_REPORT`.
# MAGIC - A registered/downloaded document with zero passages is a processing gap, not an IKF bridge success.

# COMMAND ----------
from pyspark.sql import functions as F

DOCUMENTS = "bdw_analysis_prod.maira.documents"
PASSAGES = "bdw_analysis_prod.maira.passages"

required_document_columns = {
    "document_id",
    "report_package_id",
    "corpus_type",
    "document_role",
}
required_passage_columns = {
    "document_id",
    "passage_id",
}


def require_columns(df, required: set[str], table_name: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise RuntimeError(
            f"{table_name} is missing required columns: {missing}"
        )


documents = spark.table(DOCUMENTS)
passages = spark.table(PASSAGES)
require_columns(documents, required_document_columns, DOCUMENTS)
require_columns(passages, required_passage_columns, PASSAGES)

# COMMAND ----------
# Restrict to the governed investigation corpus. Keep every document role for the audit.
investigation_documents = (
    documents
    .filter(F.col("corpus_type") == "INVESTIGATION")
)

passage_counts = (
    passages
    .groupBy("document_id")
    .agg(
        F.countDistinct("passage_id").alias("passage_count"),
    )
)

availability = (
    investigation_documents
    .join(passage_counts, on="document_id", how="left")
    .withColumn("passage_count", F.coalesce(F.col("passage_count"), F.lit(0)))
    .withColumn(
        "ikf_query_ready",
        (F.col("document_role") == "MAIN_REPORT") & (F.col("passage_count") > 0),
    )
    .withColumn(
        "availability_status",
        F.when(
            (F.col("document_role") == "MAIN_REPORT") & (F.col("passage_count") > 0),
            F.lit("AVAILABLE_TO_IKF"),
        )
        .when(
            (F.col("document_role") == "MAIN_REPORT") & (F.col("passage_count") == 0),
            F.lit("MAIN_REPORT_WITHOUT_PASSAGES"),
        )
        .when(
            (F.col("document_role") != "MAIN_REPORT") & (F.col("passage_count") > 0),
            F.lit("SUPPLEMENTARY_PROCESSED_NOT_IN_CURRENT_IKF_QUERY_SCOPE"),
        )
        .otherwise(F.lit("SUPPLEMENTARY_WITHOUT_PASSAGES")),
    )
)

# COMMAND ----------
summary = (
    availability
    .groupBy("document_role", "availability_status")
    .agg(
        F.countDistinct("document_id").alias("documents"),
        F.countDistinct("report_package_id").alias("report_packages"),
        F.sum("passage_count").alias("passages"),
    )
    .orderBy("document_role", "availability_status")
)

display(summary)

# COMMAND ----------
main_reports = availability.filter(F.col("document_role") == "MAIN_REPORT")
main_report_totals = main_reports.agg(
    F.countDistinct("document_id").alias("main_reports_registered"),
    F.countDistinct(
        F.when(F.col("passage_count") > 0, F.col("document_id"))
    ).alias("main_reports_available_to_ikf"),
    F.countDistinct(
        F.when(F.col("passage_count") == 0, F.col("document_id"))
    ).alias("main_reports_missing_passages"),
).first()

registered = int(main_report_totals["main_reports_registered"] or 0)
available_count = int(main_report_totals["main_reports_available_to_ikf"] or 0)
missing = int(main_report_totals["main_reports_missing_passages"] or 0)

print("MAIRA → IKF FULL-CATALOGUE AVAILABILITY CHECK")
print(f"MAIN_REPORT documents registered in MAIRA: {registered}")
print(f"MAIN_REPORT documents available to IKF: {available_count}")
print(f"MAIN_REPORT documents missing MAIRA passages: {missing}")

# COMMAND ----------
# Show exact gaps. These are the documents requiring MAIRA processing before IKF can query them.
gaps = (
    main_reports
    .filter(F.col("passage_count") == 0)
    .select(*[
        c for c in [
            "document_id",
            "report_package_id",
            "report_title",
            "vessel_name",
            "country_code",
            "investigation_body",
            "source_filename",
            "source_url",
            "file_path",
            "processing_status",
            "passage_count",
            "availability_status",
        ] if c in main_reports.columns
    ])
    .orderBy("report_package_id", "document_id")
)

display(gaps)

# COMMAND ----------
# Supplementary material is visible in the audit but is not currently included by
# src/ikf/query_runner.py, which intentionally filters to MAIN_REPORT.
supplementary = (
    availability
    .filter(F.col("document_role") != "MAIN_REPORT")
    .select(*[
        c for c in [
            "document_id",
            "report_package_id",
            "document_role",
            "report_title",
            "source_filename",
            "passage_count",
            "availability_status",
        ] if c in availability.columns
    ])
    .orderBy("report_package_id", "document_role", "document_id")
)

display(supplementary)

# COMMAND ----------
# Fail closed: a PASS means every MAIRA MAIN_REPORT currently registered has canonical passages
# and is therefore addressable by the current IKF MAIRA-backed query path.
if registered == 0:
    raise RuntimeError(
        "No MAIRA INVESTIGATION MAIN_REPORT documents were found; cannot validate catalogue availability."
    )

if missing:
    raise RuntimeError(
        f"FAIL — {missing} MAIRA MAIN_REPORT document(s) have no canonical passages and are not yet query-ready in IKF."
    )

print("PASS — every MAIRA INVESTIGATION MAIN_REPORT currently registered is available to the current IKF query path.")
print("No LLM calls, app deployment, Neo4j writes, or Delta writes were performed.")
