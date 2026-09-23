# Databricks notebook source
# MAGIC %md
# MAGIC # 60 — Validate persisted release-candidate read paths
# MAGIC
# MAGIC **Gate-0 follow-up only.** Run this notebook only after the billing audit
# MAGIC has produced a GO decision.
# MAGIC
# MAGIC This is the cheapest first integration check for the current IKF release
# MAGIC candidate. It is read-only and performs **no model inference, no Job
# MAGIC trigger, no Neo4j write, no corpus rebuild and no pip installation**.
# MAGIC
# MAGIC It reuses persisted artefacts to verify that the main Delta/MAIRA read
# MAGIC paths required by the App still exist before considering a fresh analysis
# MAGIC or QuestionRun.

# COMMAND ----------

from pyspark.sql import functions as F

ANALYSIS_ID = "analysis_6b330c0e0ce24b6caebb40e041038c55"
BENCHMARK_ID = "maira_benchmark_9e059930506d33295105addcd06e821d"
SNAPSHOT_ID = "snapshot_742f8e0adbccbbf8bf3610015e824415"

TABLES = {
    "maira_documents": "bdw_analysis_prod.maira.documents",
    "maira_passages": "bdw_analysis_prod.maira.passages",
    "analysis_passage": "bdw_analysis_prod.kg_poc.analysis_passage",
    "analysis_candidate": "bdw_analysis_prod.kg_poc.analysis_candidate",
    "analysis_relationship": "bdw_analysis_prod.kg_poc.analysis_candidate_relationship",
    "analysis_summary": "bdw_analysis_prod.kg_poc.analysis_summary",
    "benchmark_runs": "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_runs",
    "benchmark_candidates": "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_candidates",
    "benchmark_gold": "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_gold",
}

rows = []
errors = []
warnings = []

# COMMAND ----------

# 1. Required persisted tables
for logical_name, table_name in TABLES.items():
    exists = spark.catalog.tableExists(table_name)
    rows.append({
        "area": "table",
        "item": logical_name,
        "status": "PASS" if exists else "FAIL",
        "detail": table_name,
    })
    if not exists:
        errors.append(f"Missing table: {table_name}")

if errors:
    display(spark.createDataFrame(rows))
    raise RuntimeError(
        "Persisted read-path validation cannot continue because required tables are missing."
    )

# COMMAND ----------

# 2. Existing IKF analysis artefacts
analysis_tables = (
    "analysis_passage",
    "analysis_candidate",
    "analysis_relationship",
    "analysis_summary",
)

for logical_name in analysis_tables:
    table_name = TABLES[logical_name]
    df = spark.table(table_name)
    if "analysis_id" not in df.columns:
        rows.append({
            "area": "analysis",
            "item": logical_name,
            "status": "FAIL",
            "detail": "analysis_id column missing",
        })
        errors.append(f"{table_name} has no analysis_id column")
        continue

    count = df.filter(F.col("analysis_id") == ANALYSIS_ID).count()
    status = "PASS" if count > 0 else "WARN"
    rows.append({
        "area": "analysis",
        "item": logical_name,
        "status": status,
        "detail": f"analysis_id={ANALYSIS_ID}; rows={count}",
    })
    if count == 0:
        warnings.append(
            f"No persisted rows for {ANALYSIS_ID} in {table_name}. "
            "This may reflect retention cleanup; do not rerun inference automatically."
        )

# COMMAND ----------

# 3. Persisted MAIRA benchmark / retrieval lineage
benchmark_specs = (
    ("benchmark_runs", True),
    ("benchmark_candidates", True),
    ("benchmark_gold", False),
)

for logical_name, must_have_rows in benchmark_specs:
    table_name = TABLES[logical_name]
    df = spark.table(table_name)
    count = df.filter(F.col("benchmark_id") == BENCHMARK_ID).count()
    status = "PASS" if count > 0 else ("FAIL" if must_have_rows else "WARN")
    rows.append({
        "area": "benchmark",
        "item": logical_name,
        "status": status,
        "detail": f"benchmark_id={BENCHMARK_ID}; rows={count}",
    })
    if must_have_rows and count == 0:
        errors.append(f"Missing persisted benchmark rows in {table_name}")
    elif count == 0:
        warnings.append(f"No persisted gold rows in {table_name}")

runs = (
    spark.table(TABLES["benchmark_runs"])
    .filter(F.col("benchmark_id") == BENCHMARK_ID)
)

if runs.count() > 0 and "retrieval_snapshot_id" in runs.columns:
    snapshots = {
        row["retrieval_snapshot_id"]
        for row in runs.select("retrieval_snapshot_id").distinct().collect()
        if row["retrieval_snapshot_id"]
    }
    snapshot_ok = SNAPSHOT_ID in snapshots
    rows.append({
        "area": "benchmark",
        "item": "retrieval_snapshot_lineage",
        "status": "PASS" if snapshot_ok else "FAIL",
        "detail": "persisted snapshots=" + ", ".join(sorted(snapshots)),
    })
    if not snapshot_ok:
        errors.append(
            f"Expected retrieval snapshot {SNAPSHOT_ID} is not present in persisted benchmark lineage."
        )

# COMMAND ----------

# 4. MAIRA canonical source layer is readable and non-empty
for logical_name in ("maira_documents", "maira_passages"):
    table_name = TABLES[logical_name]
    count = spark.table(table_name).limit(1).count()
    rows.append({
        "area": "MAIRA source",
        "item": logical_name,
        "status": "PASS" if count > 0 else "FAIL",
        "detail": table_name,
    })
    if count == 0:
        errors.append(f"Canonical MAIRA table is empty or unreadable: {table_name}")

# COMMAND ----------

result_df = spark.createDataFrame(rows).orderBy("area", "item")
display(result_df)

print("")
print("Warnings:", len(warnings))
for warning in warnings:
    print("WARNING —", warning)

print("")
print("Errors:", len(errors))
for error in errors:
    print("ERROR —", error)

if errors:
    raise RuntimeError(
        "IKF persisted release-candidate read-path validation FAILED. "
        "Do not trigger fresh inference merely to replace missing artefacts; "
        "first determine whether the issue is retention, permissions or schema drift."
    )

print("")
print("PASS — IKF PERSISTED RELEASE-CANDIDATE READ PATHS")
print(
    "No inference or processing Job was triggered. "
    "Proceed to App deployment/read-path verification only if Gate 0 remains GO."
)
