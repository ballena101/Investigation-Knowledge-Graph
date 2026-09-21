# Databricks notebook source
# MAGIC %md
# MAGIC # 30 — Verify persisted MAIRA benchmark and descriptive metrics
# MAGIC
# MAGIC Reads only the persisted MAIRA benchmark tables created by notebook 29.
# MAGIC It does not depend on notebook-session temporary views, does not call
# MAGIC either model, and does not modify Neo4j.
# MAGIC
# MAGIC Metrics are descriptive for this benchmark item only. Standalone
# MAGIC relationship correctness, contract compliance and governed-query
# MAGIC adherence remain separate.

# COMMAND ----------

dbutils.widgets.text(
    "benchmark_id",
    "maira_benchmark_9e059930506d33295105addcd06e821d",
    "Persisted MAIRA benchmark ID",
)

# COMMAND ----------

from pyspark.sql import functions as F


BENCHMARK_RUN_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_runs"
)
BENCHMARK_CANDIDATE_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_candidates"
)
BENCHMARK_GOLD_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_gold"
)

benchmark_id = dbutils.widgets.get("benchmark_id").strip()

if not benchmark_id:
    raise ValueError("Enter a persisted MAIRA benchmark ID.")

# COMMAND ----------

runs = (
    spark.table(BENCHMARK_RUN_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
)

candidates = (
    spark.table(BENCHMARK_CANDIDATE_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
)

gold = (
    spark.table(BENCHMARK_GOLD_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
)

run_count = runs.count()
candidate_count = candidates.count()
gold_count = gold.count()

if run_count == 0:
    raise ValueError(
        f"No persisted model runs found for benchmark {benchmark_id}."
    )

if candidate_count == 0:
    raise ValueError(
        f"No persisted reviewed candidates found for benchmark {benchmark_id}."
    )

benchmark_versions = [
    row["benchmark_version"]
    for row in runs.select("benchmark_version").distinct().collect()
]
prompt_hashes = [
    row["prompt_sha256"]
    for row in runs.select("prompt_sha256").distinct().collect()
]
snapshot_ids = [
    row["retrieval_snapshot_id"]
    for row in runs.select("retrieval_snapshot_id").distinct().collect()
]
query_ids = [
    row["query_id"]
    for row in runs.select("query_id").distinct().collect()
]
requested_relationships = [
    row["requested_relationship"]
    for row in runs.select("requested_relationship").distinct().collect()
]

if len(benchmark_versions) != 1:
    raise RuntimeError("Persisted benchmark has multiple benchmark versions.")
if len(prompt_hashes) != 1:
    raise RuntimeError("Persisted benchmark has multiple prompt hashes.")
if len(snapshot_ids) != 1:
    raise RuntimeError("Persisted benchmark has multiple retrieval snapshots.")
if len(query_ids) != 1:
    raise RuntimeError("Persisted benchmark has multiple query IDs.")
if len(requested_relationships) != 1:
    raise RuntimeError(
        "Persisted benchmark has multiple requested relationships."
    )

print("Benchmark ID:", benchmark_id)
print("Benchmark version:", benchmark_versions[0])
print("Query:", query_ids[0])
print("Requested relationship:", requested_relationships[0])
print("Retrieval snapshot:", snapshot_ids[0])
print("Prompt SHA-256:", prompt_hashes[0])
print("Persisted model runs:", run_count)
print("Persisted reviewed candidates:", candidate_count)
print("Persisted governed gold relationships:", gold_count)

# COMMAND ----------

display(
    runs.select(
        "model_key",
        "configured_model",
        "underlying_model",
        "api_method",
        "execution_status",
        "frozen_passage_count",
        "candidate_count",
        "candidate_validation_error_count",
        "schema_valid",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "answer_summary",
    ).orderBy("model_key")
)

# COMMAND ----------

display(
    candidates.select(
        "model_key",
        "candidate_position",
        "source_label",
        "relationship",
        "target_label",
        "relationship_supported",
        "relationship_direction_correct",
        "passage_supports_relationship",
        "evidence_reference_valid",
        "evidence_quote_exact",
        "quote_supports_relationship",
        "schema_valid",
        "requested_relationship",
        "requested_relationship_label_match",
        "gold_match_status",
        "causal_overreach",
        "relationship_review_decision",
        "output_review_decision",
        "review_note",
    ).orderBy(
        "model_key",
        "candidate_position",
    )
)

# COMMAND ----------

if gold_count:
    display(
        gold.select(
            "assessment_id",
            "query_id",
            "report_package_id",
            "document_id",
            "passage_number",
            "start_page",
            "end_page",
            "subject_code_idcode",
            "subject_evidence_term",
            "requested_relationship",
            "object_code_idcode",
            "object_evidence_term",
            "relationship_assessment",
            "evidence_classification",
            "validation_method",
            "relation_cue",
            "relation_direction",
        ).orderBy(
            "report_package_id",
            "document_id",
            "passage_number",
            "assessment_id",
        )
    )
else:
    print(
        "No governed supported relationship was persisted for this frozen "
        "snapshot. Governed-query recall is therefore not defined."
    )

# COMMAND ----------

metrics = (
    candidates.groupBy(
        "model_key",
        "configured_model",
    )
    .agg(
        F.count("*").alias("generated_candidates"),
        F.sum(
            F.col("schema_valid").cast("int")
        ).alias("contract_valid_candidates"),
        F.sum(
            F.col("relationship_supported").cast("int")
        ).alias("standalone_supported_candidates"),
        F.sum(
            F.col("relationship_direction_correct").cast("int")
        ).alias("direction_correct_candidates"),
        F.sum(
            F.col("evidence_reference_valid").cast("int")
        ).alias("valid_reference_candidates"),
        F.sum(
            F.col("evidence_quote_exact").cast("int")
        ).alias("exact_quote_candidates"),
        F.sum(
            F.col("quote_supports_relationship").cast("int")
        ).alias("quote_support_candidates"),
        F.sum(
            F.col(
                "requested_relationship_label_match"
            ).cast("int")
        ).alias("requested_label_candidates"),
        F.sum(
            F.col("causal_overreach").cast("int")
        ).alias("causal_overreach_candidates"),
        F.sum(
            (
                F.col("relationship_review_decision")
                == "VALIDATED"
            ).cast("int")
        ).alias("validated_relationship_candidates"),
        F.sum(
            (
                F.col("output_review_decision")
                == "AMENDED"
            ).cast("int")
        ).alias("amended_output_candidates"),
    )
    .withColumn(
        "contract_valid_rate",
        F.col("contract_valid_candidates")
        / F.col("generated_candidates"),
    )
    .withColumn(
        "standalone_relationship_support_rate",
        F.col("standalone_supported_candidates")
        / F.col("generated_candidates"),
    )
    .withColumn(
        "evidence_reference_valid_rate",
        F.col("valid_reference_candidates")
        / F.col("generated_candidates"),
    )
    .withColumn(
        "exact_quote_rate",
        F.col("exact_quote_candidates")
        / F.col("generated_candidates"),
    )
    .withColumn(
        "quote_support_rate",
        F.col("quote_support_candidates")
        / F.col("generated_candidates"),
    )
    .withColumn(
        "requested_relationship_label_match_rate",
        F.col("requested_label_candidates")
        / F.col("generated_candidates"),
    )
    .withColumn(
        "governed_gold_relationships",
        F.lit(gold_count),
    )
    .withColumn(
        "requested_relationship_recall",
        F.when(
            (F.lit(gold_count) > 0)
            & (F.col("requested_label_candidates") == 0),
            F.lit(0.0),
        ).otherwise(F.lit(None).cast("double")),
    )
    .withColumn(
        "recall_interpretation",
        F.when(
            F.lit(gold_count) == 0,
            F.lit("NOT_DEFINED_NO_GOLD_RELATIONSHIP"),
        ).when(
            F.col("requested_label_candidates") == 0,
            F.lit(
                "ZERO_REQUESTED_LABEL_CANDIDATES_SO_ZERO_GOLD_RECOVERY"
            ),
        ).otherwise(
            F.lit(
                "CANONICAL_GOLD_MATCH_REVIEW_REQUIRED_BEFORE_RECALL"
            )
        ),
    )
)

display(metrics.orderBy("model_key"))

# COMMAND ----------

unreviewed = candidates.filter(
    F.col("relationship_review_decision").isNull()
    | F.col("output_review_decision").isNull()
).count()

distinct_model_keys = candidates.select(
    "model_key"
).distinct().count()

if run_count != 2:
    raise RuntimeError(
        f"Expected two persisted model runs; found {run_count}."
    )

if distinct_model_keys != 2:
    raise RuntimeError(
        "Expected reviewed candidates from two model routes."
    )

if unreviewed:
    raise RuntimeError(
        f"Found {unreviewed} persisted candidates without complete review."
    )

print("")
print("PASS — PERSISTED MAIRA BENCHMARK VERIFIED")
print(
    "All verification and descriptive metrics were reproduced from "
    "persisted Delta tables only."
)
print(
    "No session-local notebook 28 view, model invocation or Neo4j write "
    "was required."
)
