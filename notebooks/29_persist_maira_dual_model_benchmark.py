# Databricks notebook source
# MAGIC %md
# MAGIC # 29 — Persist MAIRA dual-model benchmark review
# MAGIC
# MAGIC Persists the already-executed and human-reviewed MAIRA dual-model run
# MAGIC created by notebook 28.
# MAGIC
# MAGIC **Important:** this notebook must be executed inline from notebook 28
# MAGIC with `%run ./29_persist_maira_dual_model_benchmark`. It does not call
# MAGIC either model and must not be run as a replacement for notebook 28.
# MAGIC
# MAGIC The benchmark keeps separate:
# MAGIC
# MAGIC - execution success;
# MAGIC - structured-output / contract compliance;
# MAGIC - standalone relationship correctness;
# MAGIC - evidence-quote compliance;
# MAGIC - requested-relationship task adherence;
# MAGIC - governed MAIRA gold/reference relationships.
# MAGIC
# MAGIC No Neo4j write is performed.

# COMMAND ----------

import hashlib

from pyspark.sql import functions as F


RUN_VIEW = "maira_ikf_dual_model_runs"
CANDIDATE_VIEW = "maira_ikf_dual_model_candidates"
HUMAN_REVIEW_VIEW = "maira_ikf_dual_model_human_review"
SNAPSHOT_VIEW = "maira_ikf_retrieval_snapshot"

QUERY_SPEC_TABLE = "bdw_analysis_prod.maira.query_specifications"
ASSESSMENT_TABLE = "bdw_analysis_prod.maira.query_relationship_assessments"

BENCHMARK_RUN_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_runs"
)
BENCHMARK_CANDIDATE_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_candidates"
)
BENCHMARK_GOLD_TABLE = (
    "bdw_analysis_prod.kg_poc.ikf_maira_benchmark_gold"
)

BENCHMARK_VERSION = "IKF_MAIRA_BENCHMARK_V0.1"
HUMAN_REVIEW_VERSION = "HUMAN_REVIEW_V0.1"

required_views = [
    RUN_VIEW,
    CANDIDATE_VIEW,
    HUMAN_REVIEW_VIEW,
    SNAPSHOT_VIEW,
]
missing_views = [
    name
    for name in required_views
    if not spark.catalog.tableExists(name)
]

if missing_views:
    raise RuntimeError(
        "Notebook 29 requires notebook 28's current-session temporary views. "
        "Run notebook 28 through the human-review checkpoint, then execute "
        "notebook 29 inline with %run. Missing: "
        + ", ".join(missing_views)
    )

run_df = spark.table(RUN_VIEW)
candidate_df = spark.table(CANDIDATE_VIEW)
review_df = spark.table(HUMAN_REVIEW_VIEW)
snapshot_df = spark.table(SNAPSHOT_VIEW)

if run_df.count() != 2:
    raise RuntimeError(
        "Expected exactly two model-run rows from notebook 28."
    )

if review_df.count() != candidate_df.count():
    raise RuntimeError(
        "Every model candidate must have one human-review row before "
        "benchmark persistence."
    )

# COMMAND ----------

run_identity = (
    run_df.select(
        "analysis_id",
        "retrieval_snapshot_id",
        "query_spec_id",
        "query_id",
        "prompt_version",
        "prompt_sha256",
    )
    .dropDuplicates()
    .collect()
)

if len(run_identity) != 1:
    raise RuntimeError(
        "The temporary run view does not represent one frozen benchmark item."
    )

identity = run_identity[0].asDict()

benchmark_material = "|".join(
    [
        identity["analysis_id"],
        identity["retrieval_snapshot_id"],
        identity["query_spec_id"],
        identity["query_id"],
        identity["prompt_version"],
        identity["prompt_sha256"],
    ]
)

benchmark_id = "maira_benchmark_" + hashlib.sha256(
    benchmark_material.encode("utf-8")
).hexdigest()[:32]

query_spec_rows = (
    spark.table(QUERY_SPEC_TABLE)
    .filter(
        F.col("query_spec_id") == identity["query_spec_id"]
    )
    .select(
        "query_spec_id",
        "query_id",
        "user_query",
        "relationship",
    )
    .dropDuplicates()
    .collect()
)

if len(query_spec_rows) != 1:
    raise RuntimeError(
        "The governed MAIRA query specification could not be resolved "
        "uniquely."
    )

query_spec = query_spec_rows[0].asDict()
requested_relationship = str(
    query_spec["relationship"] or ""
).upper()

print("Benchmark ID:", benchmark_id)
print("Benchmark version:", BENCHMARK_VERSION)
print("Query:", identity["query_id"])
print("Question:", query_spec["user_query"])
print("Requested relationship:", requested_relationship)

# COMMAND ----------

# Freeze the governed MAIRA supported relationship assessments that are
# actually represented in the frozen snapshot. This is the benchmark gold
# reference; the source evidence remains in MAIRA and is not duplicated here.

snapshot_keys = (
    snapshot_df.select(
        "report_package_id",
        F.col("maira_document_id").alias("document_id"),
        F.col("passage_order").alias("passage_number"),
    )
    .dropDuplicates()
)

gold_df = (
    spark.table(ASSESSMENT_TABLE)
    .filter(
        F.col("query_spec_id") == identity["query_spec_id"]
    )
    .filter(
        F.col("relationship_assessment")
        == "SUPPORTED_REQUESTED_RELATIONSHIP"
    )
    .join(
        snapshot_keys,
        on=[
            "report_package_id",
            "document_id",
            "passage_number",
        ],
        how="inner",
    )
    .select(
        "assessment_id",
        "query_spec_id",
        "query_id",
        "report_package_id",
        "document_id",
        "passage_number",
        "start_page",
        "end_page",
        "subject_code_idcode",
        "requested_relationship",
        "object_code_idcode",
        "relationship_assessment",
        "evidence_classification",
        "validation_method",
        "relation_cue",
        "evidence_text_sha256",
        "subject_evidence_term",
        "object_evidence_term",
        "relation_direction",
    )
    .dropDuplicates(["assessment_id"])
)

gold_count = gold_df.count()

print("Governed supported relationships in frozen snapshot:", gold_count)

if gold_count == 0:
    print(
        "NOTE — no governed supported relationship is present in this "
        "snapshot. Recall is not computed from an empty gold set."
    )

# COMMAND ----------

# Add benchmark task-adherence metadata to the human-reviewed candidates.
#
# relationship_supported answers:
#   "Is this candidate edge itself supported by the passage?"
#
# requested_relationship_label_match answers:
#   "Did the candidate even use the governed relationship label requested by
#    this benchmark?"
#
# These are intentionally different measurements.

reviewed_candidates = (
    review_df.alias("h")
    .join(
        candidate_df.select(
            "model_key",
            "candidate_signature",
            "evidence_quote",
            "evidence_class",
            "evidence_reference_valid",
            "requires_causal_review",
            "validation_errors",
            "explanation",
        ).alias("c"),
        on=["model_key", "candidate_signature"],
        how="inner",
    )
    .withColumn(
        "requested_relationship",
        F.lit(requested_relationship),
    )
    .withColumn(
        "requested_relationship_label_match",
        F.upper(F.col("relationship"))
        == F.lit(requested_relationship),
    )
    .withColumn(
        "gold_match_status",
        F.when(
            F.upper(F.col("relationship"))
            != F.lit(requested_relationship),
            F.lit("NO_REQUESTED_RELATIONSHIP_LABEL_MATCH"),
        ).otherwise(
            F.lit("REQUIRES_CANONICAL_GOLD_MATCH_REVIEW")
        ),
    )
)

display(
    reviewed_candidates.select(
        "model_key",
        "source_label",
        "relationship",
        "target_label",
        "relationship_supported",
        "schema_valid",
        "evidence_quote_exact",
        "quote_supports_relationship",
        "requested_relationship",
        "requested_relationship_label_match",
        "gold_match_status",
        "relationship_review_decision",
        "output_review_decision",
        "review_note",
    ).orderBy("model_key", "candidate_position")
)

# COMMAND ----------

# For the current benchmark, a model with zero candidates carrying the
# requested relationship label cannot have recovered any governed gold
# relationship. If at least one requested-label candidate exists, semantic
# canonical matching remains a separate human-review step and recall is left
# unresolved rather than guessed.

model_task_metrics = (
    reviewed_candidates.groupBy("model_key", "configured_model")
    .agg(
        F.count("*").alias("generated_candidates"),
        F.sum(
            F.col("schema_valid").cast("int")
        ).alias("contract_valid_candidates"),
        F.sum(
            F.col("relationship_supported").cast("int")
        ).alias("standalone_supported_candidates"),
        F.sum(
            F.col("evidence_quote_exact").cast("int")
        ).alias("exact_quote_candidates"),
        F.sum(
            F.col(
                "requested_relationship_label_match"
            ).cast("int")
        ).alias("requested_label_candidates"),
    )
    .withColumn(
        "governed_gold_relationships",
        F.lit(gold_count),
    )
    .withColumn(
        "governed_gold_recovered",
        F.when(
            F.col("requested_label_candidates") == 0,
            F.lit(0),
        ).otherwise(F.lit(None).cast("int")),
    )
    .withColumn(
        "requested_relationship_recall",
        F.when(
            (F.col("governed_gold_relationships") > 0)
            & F.col("governed_gold_recovered").isNotNull(),
            F.col("governed_gold_recovered")
            / F.col("governed_gold_relationships"),
        ).otherwise(F.lit(None).cast("double")),
    )
)

display(model_task_metrics.orderBy("model_key"))

# COMMAND ----------

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {BENCHMARK_RUN_TABLE} (
        benchmark_id STRING,
        benchmark_version STRING,
        analysis_id STRING,
        retrieval_snapshot_id STRING,
        query_spec_id STRING,
        query_id STRING,
        requested_relationship STRING,
        prompt_version STRING,
        prompt_sha256 STRING,
        frozen_passage_count INT,
        model_key STRING,
        configured_model STRING,
        underlying_model STRING,
        api_method STRING,
        execution_status STRING,
        latency_ms BIGINT,
        input_tokens INT,
        output_tokens INT,
        total_tokens INT,
        candidate_count INT,
        candidate_validation_error_count INT,
        schema_valid BOOLEAN,
        answer_summary STRING,
        uncertainties_json STRING,
        response_json STRING,
        persisted_at TIMESTAMP
    )
    USING DELTA
    """
)

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {BENCHMARK_CANDIDATE_TABLE} (
        benchmark_id STRING,
        benchmark_version STRING,
        human_review_version STRING,
        analysis_id STRING,
        retrieval_snapshot_id STRING,
        query_spec_id STRING,
        query_id STRING,
        prompt_version STRING,
        prompt_sha256 STRING,
        model_key STRING,
        configured_model STRING,
        candidate_position INT,
        candidate_signature STRING,
        source_label STRING,
        relationship STRING,
        target_label STRING,
        evidence_passage_ids ARRAY<STRING>,
        evidence_quote STRING,
        evidence_class STRING,
        explanation STRING,
        evidence_reference_valid BOOLEAN,
        evidence_quote_exact BOOLEAN,
        requires_causal_review BOOLEAN,
        schema_valid BOOLEAN,
        validation_errors ARRAY<STRING>,
        relationship_supported BOOLEAN,
        relationship_direction_correct BOOLEAN,
        passage_supports_relationship BOOLEAN,
        quote_supports_relationship BOOLEAN,
        causal_overreach BOOLEAN,
        relationship_review_decision STRING,
        output_review_decision STRING,
        requested_relationship STRING,
        requested_relationship_label_match BOOLEAN,
        gold_match_status STRING,
        review_note STRING,
        reviewer STRING,
        reviewed_at TIMESTAMP,
        persisted_at TIMESTAMP
    )
    USING DELTA
    """
)

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {BENCHMARK_GOLD_TABLE} (
        benchmark_id STRING,
        benchmark_version STRING,
        assessment_id STRING,
        query_spec_id STRING,
        query_id STRING,
        report_package_id STRING,
        document_id STRING,
        passage_number INT,
        start_page INT,
        end_page INT,
        subject_code_idcode STRING,
        requested_relationship STRING,
        object_code_idcode STRING,
        relationship_assessment STRING,
        evidence_classification STRING,
        validation_method STRING,
        relation_cue STRING,
        evidence_text_sha256 STRING,
        subject_evidence_term STRING,
        object_evidence_term STRING,
        relation_direction STRING,
        persisted_at TIMESTAMP
    )
    USING DELTA
    """
)

# COMMAND ----------

run_persist_df = (
    run_df
    .withColumn("benchmark_id", F.lit(benchmark_id))
    .withColumn("benchmark_version", F.lit(BENCHMARK_VERSION))
    .withColumn(
        "requested_relationship",
        F.lit(requested_relationship),
    )
    .withColumn("persisted_at", F.current_timestamp())
    .select(
        "benchmark_id",
        "benchmark_version",
        "analysis_id",
        "retrieval_snapshot_id",
        "query_spec_id",
        "query_id",
        "requested_relationship",
        "prompt_version",
        "prompt_sha256",
        "frozen_passage_count",
        "model_key",
        "configured_model",
        "underlying_model",
        "api_method",
        "execution_status",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "candidate_count",
        "candidate_validation_error_count",
        "schema_valid",
        "answer_summary",
        "uncertainties_json",
        "response_json",
        "persisted_at",
    )
)

run_persist_df.createOrReplaceTempView(
    "maira_ikf_benchmark_runs_to_persist"
)

spark.sql(
    f"""
    MERGE INTO {BENCHMARK_RUN_TABLE} AS t
    USING maira_ikf_benchmark_runs_to_persist AS s
      ON t.benchmark_id = s.benchmark_id
     AND t.model_key = s.model_key
    WHEN NOT MATCHED THEN INSERT *
    """
)

# COMMAND ----------

candidate_persist_df = (
    reviewed_candidates
    .withColumn("benchmark_id", F.lit(benchmark_id))
    .withColumn("benchmark_version", F.lit(BENCHMARK_VERSION))
    .withColumn(
        "human_review_version",
        F.lit(HUMAN_REVIEW_VERSION),
    )
    .withColumn(
        "query_spec_id",
        F.lit(identity["query_spec_id"]),
    )
    .withColumn(
        "query_id",
        F.lit(identity["query_id"]),
    )
    .withColumn(
        "prompt_version",
        F.lit(identity["prompt_version"]),
    )
    .withColumn(
        "prompt_sha256",
        F.lit(identity["prompt_sha256"]),
    )
    .withColumn("reviewer", F.current_user())
    .withColumn("reviewed_at", F.current_timestamp())
    .withColumn("persisted_at", F.current_timestamp())
    .select(
        "benchmark_id",
        "benchmark_version",
        "human_review_version",
        "analysis_id",
        "retrieval_snapshot_id",
        "query_spec_id",
        "query_id",
        "prompt_version",
        "prompt_sha256",
        "model_key",
        "configured_model",
        "candidate_position",
        "candidate_signature",
        "source_label",
        "relationship",
        "target_label",
        "evidence_passage_ids",
        "evidence_quote",
        "evidence_class",
        "explanation",
        "evidence_reference_valid",
        "evidence_quote_exact",
        "requires_causal_review",
        "schema_valid",
        "validation_errors",
        "relationship_supported",
        "relationship_direction_correct",
        "passage_supports_relationship",
        "quote_supports_relationship",
        "causal_overreach",
        "relationship_review_decision",
        "output_review_decision",
        "requested_relationship",
        "requested_relationship_label_match",
        "gold_match_status",
        "review_note",
        "reviewer",
        "reviewed_at",
        "persisted_at",
    )
)

candidate_persist_df.createOrReplaceTempView(
    "maira_ikf_benchmark_candidates_to_persist"
)

spark.sql(
    f"""
    MERGE INTO {BENCHMARK_CANDIDATE_TABLE} AS t
    USING maira_ikf_benchmark_candidates_to_persist AS s
      ON t.benchmark_id = s.benchmark_id
     AND t.model_key = s.model_key
     AND t.candidate_signature = s.candidate_signature
     AND t.human_review_version = s.human_review_version
    WHEN NOT MATCHED THEN INSERT *
    """
)

# COMMAND ----------

gold_persist_df = (
    gold_df
    .withColumn("benchmark_id", F.lit(benchmark_id))
    .withColumn("benchmark_version", F.lit(BENCHMARK_VERSION))
    .withColumn("persisted_at", F.current_timestamp())
    .select(
        "benchmark_id",
        "benchmark_version",
        "assessment_id",
        "query_spec_id",
        "query_id",
        "report_package_id",
        "document_id",
        "passage_number",
        "start_page",
        "end_page",
        "subject_code_idcode",
        "requested_relationship",
        "object_code_idcode",
        "relationship_assessment",
        "evidence_classification",
        "validation_method",
        "relation_cue",
        "evidence_text_sha256",
        "subject_evidence_term",
        "object_evidence_term",
        "relation_direction",
        "persisted_at",
    )
)

if gold_count:
    gold_persist_df.createOrReplaceTempView(
        "maira_ikf_benchmark_gold_to_persist"
    )
    spark.sql(
        f"""
        MERGE INTO {BENCHMARK_GOLD_TABLE} AS t
        USING maira_ikf_benchmark_gold_to_persist AS s
          ON t.benchmark_id = s.benchmark_id
         AND t.assessment_id = s.assessment_id
        WHEN NOT MATCHED THEN INSERT *
        """
    )

# COMMAND ----------

persisted_runs = (
    spark.table(BENCHMARK_RUN_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
)

persisted_candidates = (
    spark.table(BENCHMARK_CANDIDATE_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
    .filter(
        F.col("human_review_version")
        == HUMAN_REVIEW_VERSION
    )
)

persisted_gold = (
    spark.table(BENCHMARK_GOLD_TABLE)
    .filter(F.col("benchmark_id") == benchmark_id)
)

print("Persisted model runs:", persisted_runs.count())
print(
    "Persisted reviewed candidates:",
    persisted_candidates.count(),
)
print("Persisted governed gold relationships:", persisted_gold.count())

if persisted_runs.count() != 2:
    raise RuntimeError(
        "Benchmark persistence validation failed: expected two model runs."
    )

if persisted_candidates.count() != candidate_df.count():
    raise RuntimeError(
        "Benchmark persistence validation failed: candidate count mismatch."
    )

if persisted_gold.count() != gold_count:
    raise RuntimeError(
        "Benchmark persistence validation failed: governed-gold count mismatch."
    )

display(
    persisted_candidates.select(
        "benchmark_id",
        "model_key",
        "relationship",
        "relationship_supported",
        "schema_valid",
        "evidence_quote_exact",
        "requested_relationship",
        "requested_relationship_label_match",
        "gold_match_status",
        "relationship_review_decision",
        "output_review_decision",
    ).orderBy("model_key", "candidate_position")
)

print("")
print("PASS — MAIRA HUMAN-REVIEW BENCHMARK PERSISTED")
print("Benchmark ID:", benchmark_id)
print(
    "Raw model output, contract compliance, standalone relationship "
    "correctness and governed-query adherence remain separate."
)
print("No Neo4j graph was modified.")
