# Databricks notebook source
# MAGIC %md
# MAGIC # 31 — Persist canonical gold matches for MAIRA benchmark
# MAGIC
# MAGIC Human-reviewed canonical matching for the first persisted MAIRA
# MAGIC benchmark. This notebook reads only persisted benchmark tables.
# MAGIC
# MAGIC The three governed MAIRA gold rows for the current benchmark are
# MAGIC passage-level evidence assessments of one canonical relationship:
# MAGIC
# MAGIC TA-196-TCL-TC-1 failure
# MAGIC     FOLLOWED_BY
# MAGIC TA-520-TCL-TC-25 fire
# MAGIC
# MAGIC Both reviewed model candidates are semantically equivalent to that
# MAGIC canonical relationship.
# MAGIC
# MAGIC This notebook does not modify the original model output, MAIRA source
# MAGIC assessments, or Neo4j.

# COMMAND ----------

dbutils.widgets.text(
    "benchmark_id",
    "maira_benchmark_9e059930506d33295105addcd06e821d",
    "Persisted MAIRA benchmark ID",
)

# COMMAND ----------

from pyspark.sql import functions as F


BENCHMARK_CANDIDATE_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_candidates"
)
BENCHMARK_GOLD_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_gold"
)
CANONICAL_MATCH_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_canonical_matches"
)

MATCH_REVIEW_VERSION = "HUMAN_CANONICAL_MATCH_V0.1"

benchmark_id = dbutils.widgets.get("benchmark_id").strip()

if not benchmark_id:
    raise ValueError("Enter a persisted MAIRA benchmark ID.")

candidates = (
    spark.table(BENCHMARK_CANDIDATE_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
)

gold = (
    spark.table(BENCHMARK_GOLD_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
)

if candidates.count() != 2:
    raise RuntimeError(
        "Expected exactly two reviewed candidates for this benchmark."
    )

if gold.count() == 0:
    raise RuntimeError(
        "No governed gold assessments exist for this benchmark."
    )

# COMMAND ----------

# Canonical gold relationships are distinct semantic triples.
# Passage-level assessment rows are supporting evidence instances and must not
# inflate the relationship-recall denominator.

canonical_gold = (
    gold.select(
        "subject_code_idcode",
        "requested_relationship",
        "object_code_idcode",
    )
    .dropDuplicates()
)

canonical_gold_count = canonical_gold.count()
evidence_assessment_count = gold.count()

print("Passage-level governed gold assessments:", evidence_assessment_count)
print("Distinct canonical gold relationships:", canonical_gold_count)

display(canonical_gold)

if canonical_gold_count != 1:
    raise RuntimeError(
        "This human-reviewed notebook is scoped to the current benchmark, "
        "which is expected to contain one canonical gold relationship."
    )

gold_row = canonical_gold.first()

gold_subject_code = gold_row["subject_code_idcode"]
gold_relationship = gold_row["requested_relationship"]
gold_object_code = gold_row["object_code_idcode"]

# COMMAND ----------

# Human canonical adjudication already completed from the displayed benchmark:
#
# MODEL_A:
#   catastrophic engine failure FOLLOWED_BY fire
# MODEL_B:
#   Machinery failure FOLLOWED_BY Fire in the engine room
#
# Both are semantically equivalent to the governed canonical relation:
#   failure FOLLOWED_BY fire
#
# This canonical match is separate from evidence-quote quality. MODEL_A and
# MODEL_B both failed exact quotation compliance, and MODEL_B's selected quote
# did not itself support the relationship.

reviewed_matches = (
    candidates.select(
        "benchmark_id",
        "benchmark_version",
        "human_review_version",
        "model_key",
        "configured_model",
        "candidate_position",
        "candidate_signature",
        "source_label",
        "relationship",
        "target_label",
        "evidence_quote_exact",
        "quote_supports_relationship",
        "schema_valid",
        "relationship_supported",
    )
    .withColumn(
        "gold_subject_code_idcode",
        F.lit(gold_subject_code),
    )
    .withColumn(
        "gold_relationship",
        F.lit(gold_relationship),
    )
    .withColumn(
        "gold_object_code_idcode",
        F.lit(gold_object_code),
    )
    .withColumn(
        "canonical_match",
        F.lit(True),
    )
    .withColumn(
        "match_review_version",
        F.lit(MATCH_REVIEW_VERSION),
    )
    .withColumn(
        "match_review_note",
        F.when(
            F.col("model_key") == "MODEL_A",
            F.lit(
                "Human semantic review: 'catastrophic engine failure' is a "
                "specific instance of governed failure and target 'fire' "
                "matches the governed fire concept; FOLLOWED_BY direction "
                "matches the canonical relationship."
            ),
        ).otherwise(
            F.lit(
                "Human semantic review: 'Machinery failure' maps to the "
                "governed failure concept and 'Fire in the engine room' is a "
                "specific instance of governed fire; FOLLOWED_BY direction "
                "matches the canonical relationship."
            )
        ),
    )
    .withColumn("reviewer", F.current_user())
    .withColumn("reviewed_at", F.current_timestamp())
)

display(
    reviewed_matches.select(
        "model_key",
        "source_label",
        "relationship",
        "target_label",
        "gold_subject_code_idcode",
        "gold_relationship",
        "gold_object_code_idcode",
        "canonical_match",
        "schema_valid",
        "evidence_quote_exact",
        "quote_supports_relationship",
        "match_review_note",
    ).orderBy("model_key")
)

# COMMAND ----------

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {CANONICAL_MATCH_TABLE} (
        benchmark_id STRING,
        benchmark_version STRING,
        human_review_version STRING,
        match_review_version STRING,
        model_key STRING,
        configured_model STRING,
        candidate_position INT,
        candidate_signature STRING,
        source_label STRING,
        relationship STRING,
        target_label STRING,
        gold_subject_code_idcode STRING,
        gold_relationship STRING,
        gold_object_code_idcode STRING,
        canonical_match BOOLEAN,
        schema_valid BOOLEAN,
        evidence_quote_exact BOOLEAN,
        quote_supports_relationship BOOLEAN,
        relationship_supported BOOLEAN,
        match_review_note STRING,
        reviewer STRING,
        reviewed_at TIMESTAMP
    )
    USING DELTA
    """
)

reviewed_matches.select(
    "benchmark_id",
    "benchmark_version",
    "human_review_version",
    "match_review_version",
    "model_key",
    "configured_model",
    "candidate_position",
    "candidate_signature",
    "source_label",
    "relationship",
    "target_label",
    "gold_subject_code_idcode",
    "gold_relationship",
    "gold_object_code_idcode",
    "canonical_match",
    "schema_valid",
    "evidence_quote_exact",
    "quote_supports_relationship",
    "relationship_supported",
    "match_review_note",
    "reviewer",
    "reviewed_at",
).createOrReplaceTempView(
    "maira_ikf_canonical_matches_to_persist"
)

spark.sql(
    f"""
    MERGE INTO {CANONICAL_MATCH_TABLE} AS t
    USING maira_ikf_canonical_matches_to_persist AS s
      ON t.benchmark_id = s.benchmark_id
     AND t.model_key = s.model_key
     AND t.candidate_signature = s.candidate_signature
     AND t.match_review_version = s.match_review_version
    WHEN NOT MATCHED THEN INSERT *
    """
)

# COMMAND ----------

persisted_matches = (
    spark.table(CANONICAL_MATCH_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
    .filter(
        F.col("match_review_version") == MATCH_REVIEW_VERSION
    )
)

if persisted_matches.count() != candidates.count():
    raise RuntimeError(
        "Canonical-match persistence validation failed."
    )

# Candidate-level canonical precision:
# matched generated canonical candidates / generated candidates.
#
# Canonical relationship recall:
# distinct gold semantic triples recovered / distinct gold semantic triples.
#
# Because the current benchmark has one canonical gold triple and each model
# has one human-confirmed matching candidate, both measures are 1.0.
#
# This does NOT erase the separate quotation/contract failures.

model_metrics = (
    persisted_matches.groupBy(
        "model_key",
        "configured_model",
    )
    .agg(
        F.count("*").alias("generated_candidates"),
        F.sum(
            F.col("canonical_match").cast("int")
        ).alias("canonical_matched_candidates"),
        F.sum(
            F.col("schema_valid").cast("int")
        ).alias("contract_valid_candidates"),
        F.sum(
            F.col("evidence_quote_exact").cast("int")
        ).alias("exact_quote_candidates"),
        F.sum(
            F.col("quote_supports_relationship").cast("int")
        ).alias("quote_support_candidates"),
    )
    .withColumn(
        "canonical_relationship_precision",
        F.col("canonical_matched_candidates")
        / F.col("generated_candidates"),
    )
    .withColumn(
        "canonical_gold_relationships",
        F.lit(canonical_gold_count),
    )
    .withColumn(
        "canonical_gold_recovered",
        F.when(
            F.col("canonical_matched_candidates") > 0,
            F.lit(1),
        ).otherwise(F.lit(0)),
    )
    .withColumn(
        "canonical_relationship_recall",
        F.col("canonical_gold_recovered")
        / F.col("canonical_gold_relationships"),
    )
    .withColumn(
        "passage_level_gold_evidence_assessments",
        F.lit(evidence_assessment_count),
    )
)

display(model_metrics.orderBy("model_key"))

# COMMAND ----------

print("")
print("PASS — CANONICAL GOLD MATCHES PERSISTED")
print("Benchmark ID:", benchmark_id)
print(
    "Gold denominator: distinct canonical semantic relationships, not "
    "passage-level evidence-assessment rows."
)
print(
    "Quotation/contract compliance remains separate from canonical "
    "relationship precision and recall."
)
print("No model was rerun and no Neo4j graph was modified.")
