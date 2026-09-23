# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # 39 — Bind a Type D transcript to the existing IKF LLM analysis pipeline
# MAGIC
# MAGIC Purpose: adapt persisted `ai_transcribe()` transcript segments to the existing
# MAGIC `kg_poc.analysis_passage` evidence contract consumed by notebook 16.
# MAGIC
# MAGIC The transcript remains **TYPE_D**. This notebook does not call an LLM, translate
# MAGIC content, write to Neo4j graph knowledge, or alter the document extraction logic.
# MAGIC It only prepares evidence for the already-governed Type D LLM workflow.
# MAGIC
# MAGIC Evidence semantics:
# MAGIC - `document_id` = stable audio source ID;
# MAGIC - `passage_id` = stable transcript segment ID;
# MAGIC - `passage_text` = exact transcript segment text;
# MAGIC - page fields remain NULL because audio evidence is located by timestamp, not page;
# MAGIC - timestamp/speaker provenance remains in `type_d_transcript_segment` and is joined by
# MAGIC   `passage_id = transcript_segment_id` whenever a source reference is rendered.

# COMMAND ----------
dbutils.widgets.text("analysis_id", "", "Existing Type D analysis ID")
dbutils.widgets.text("transcription_run_id", "", "Type D transcription run ID")
dbutils.widgets.dropdown("persist", "false", ["false", "true"], "Persist binding")

# COMMAND ----------
import re
from datetime import datetime, timezone

from neo4j import GraphDatabase
from pyspark.sql import functions as F

ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"
AUDIO_TABLE = "bdw_analysis_prod.kg_poc.type_d_audio_source"
SEGMENT_TABLE = "bdw_analysis_prod.kg_poc.type_d_transcript_segment"
BINDING_VERSION = "TYPE_D_AUDIO_TO_ANALYSIS_PASSAGE_V0.1"

analysis_id = dbutils.widgets.get("analysis_id").strip()
transcription_run_id = dbutils.widgets.get("transcription_run_id").strip()
PERSIST = dbutils.widgets.get("persist").strip().lower() == "true"

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError("Enter a valid existing IKF analysis_id.")
if not re.fullmatch(r"transcription_[0-9a-f]{32}", transcription_run_id):
    raise ValueError("Enter a valid transcription_run_id produced by notebook 38.")

for table_name in [ANALYSIS_PASSAGE_TABLE, AUDIO_TABLE, SEGMENT_TABLE]:
    if not spark.catalog.tableExists(table_name):
        raise RuntimeError(f"Required table does not exist: {table_name}")

# COMMAND ----------
# Validate that the destination analysis is already governed as Type D.
NEO4J_URI = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_uri")
NEO4J_USERNAME = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_username")
NEO4J_PASSWORD = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_password")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

with driver.session() as session:
    record = session.run(
        """
        MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
        RETURN
            a.analysis_id AS analysis_id,
            coalesce(properties(a)["information_class"], "") AS information_class,
            a.status AS status,
            a.analysis_title AS analysis_title
        """,
        analysis_id=analysis_id,
    ).single()

if record is None:
    driver.close()
    raise ValueError(f"AnalysisGroup not found: {analysis_id}")

analysis_meta = record.data()
information_class = str(analysis_meta.get("information_class") or "").upper().strip()
if information_class not in {"D", "TYPE_D"}:
    driver.close()
    raise RuntimeError(
        "Fail closed: transcript evidence may only be bound to an analysis already classified as Type D. "
        f"Found information_class={information_class!r}."
    )

print("Analysis:", analysis_id)
print("Title:", analysis_meta.get("analysis_title"))
print("Information class:", information_class)

# COMMAND ----------
# Validate the source and all derivative segments are still Type D.
source_rows = (
    spark.table(AUDIO_TABLE)
    .filter(F.col("transcription_run_id") == transcription_run_id)
    .select(
        "audio_source_id",
        "source_id",
        "source_sha256",
        "source_path",
        "classification",
        "transcription_engine",
        "language_expected",
    )
    .distinct()
    .collect()
)

if len(source_rows) != 1:
    driver.close()
    raise RuntimeError(
        f"Expected exactly one Type D audio source for {transcription_run_id}; found {len(source_rows)}."
    )

source = source_rows[0]
if str(source["classification"] or "").upper() != "TYPE_D":
    driver.close()
    raise RuntimeError("Fail closed: audio source is not classified TYPE_D.")

segments = (
    spark.table(SEGMENT_TABLE)
    .filter(F.col("transcription_run_id") == transcription_run_id)
)

segment_count = segments.count()
if segment_count == 0:
    driver.close()
    raise RuntimeError("No persisted transcript segments found for this transcription run.")

non_d = segments.filter(F.upper(F.col("classification")) != "TYPE_D").count()
if non_d:
    driver.close()
    raise RuntimeError(f"Fail closed: {non_d} transcript segment(s) are not TYPE_D.")

source_ids = [r["audio_source_id"] for r in segments.select("audio_source_id").distinct().collect()]
if source_ids != [source["audio_source_id"]]:
    driver.close()
    raise RuntimeError("Transcript segments do not resolve to exactly the validated Type D audio source.")

print("Audio source:", source["audio_source_id"])
print("Transcript segments:", segment_count)
print("Transcription engine:", source["transcription_engine"])

# COMMAND ----------
# Map to the exact evidence fields consumed by notebook 16.
# We deliberately do not fabricate page numbers for audio.
language_name = (
    "English" if str(source["language_expected"] or "").lower() == "en"
    else "Spanish" if str(source["language_expected"] or "").lower() == "es"
    else "UNKNOWN"
)

binding_rows = (
    segments
    .select(
        F.lit(analysis_id).alias("analysis_id"),
        F.col("audio_source_id").alias("document_id"),
        F.col("transcript_segment_id").alias("passage_id"),
        F.lit(None).cast("int").alias("page_start"),
        F.lit(None).cast("int").alias("page_end"),
        (F.col("segment_index").cast("int") + F.lit(1)).alias("passage_order"),
        F.col("transcript_text").alias("passage_text"),
        F.col("segment_text_sha256").alias("text_sha256"),
        F.lit(BINDING_VERSION).alias("extraction_version"),
        F.current_timestamp().alias("created_at"),
        F.lit(language_name).alias("detected_language"),
    )
    .orderBy("passage_order")
)

display(binding_rows)

# COMMAND ----------
# Validate hash and locator integrity before exposing the transcript to LLM analysis.
invalid_hashes = (
    binding_rows
    .filter(F.sha2(F.coalesce(F.col("passage_text"), F.lit("")), 256) != F.col("text_sha256"))
    .count()
)
invalid_order = binding_rows.filter(F.col("passage_order") < 1).count()
null_text = binding_rows.filter(F.col("passage_text").isNull()).count()

if invalid_hashes or invalid_order or null_text:
    driver.close()
    raise RuntimeError(
        "Transcript binding validation failed: "
        f"invalid_hashes={invalid_hashes}, invalid_order={invalid_order}, null_text={null_text}."
    )

print("Binding validation: PASS")
print("Target evidence contract:", ANALYSIS_PASSAGE_TABLE)

# COMMAND ----------
# Preview by default. On persistence, replace only prior transcript-bound evidence for this
# analysis/audio source. Do not delete document evidence belonging to other sources.
if PERSIST:
    audio_source_id = source["audio_source_id"]

    spark.sql(
        f"""
        DELETE FROM {ANALYSIS_PASSAGE_TABLE}
        WHERE analysis_id = '{analysis_id}'
          AND document_id = '{audio_source_id}'
          AND extraction_version LIKE 'TYPE_D_AUDIO_TO_ANALYSIS_PASSAGE_%'
        """
    )

    binding_rows.write.mode("append").saveAsTable(ANALYSIS_PASSAGE_TABLE)

    with driver.session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            SET
                a.status = 'EVIDENCE_READY',
                a.processing_stage = 'EVIDENCE_READY',
                a.processing_error = NULL,
                a.input_mode = 'TYPE_D_AUDIO_TRANSCRIPT',
                a.audio_source_id = $audio_source_id,
                a.transcription_run_id = $transcription_run_id,
                a.transcript_binding_version = $binding_version,
                a.transcript_segment_count = $segment_count,
                a.transcript_bound_at = datetime(),
                a.processing_updated_at = datetime()
            """,
            analysis_id=analysis_id,
            audio_source_id=audio_source_id,
            transcription_run_id=transcription_run_id,
            binding_version=BINDING_VERSION,
            segment_count=segment_count,
        ).consume()

    print("PERSISTED — transcript is now EVIDENCE_READY for the existing notebook 16 LLM pipeline.")
    print("Type D classification has not been changed or downgraded.")
else:
    print("PREVIEW ONLY — no evidence rows or AnalysisGroup state changed.")
    print("Set persist=true after reviewing this mapping to make the transcript available to notebook 16.")

# COMMAND ----------
# Timestamp reference audit. Notebook 16 can resolve these by joining passage_id to this table.
audit = (
    segments
    .select(
        "transcript_segment_id",
        "audio_source_id",
        "segment_index",
        "start_seconds",
        "end_seconds",
        "speaker_id",
        "classification",
        "human_review_status",
    )
    .orderBy("segment_index")
)
display(audit)

driver.close()
