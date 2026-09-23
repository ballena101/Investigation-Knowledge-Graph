# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # 38 — Type D audio transcription with ai_transcribe()
# MAGIC
# MAGIC Purpose: transcribe protected Type D audio using Databricks `ai_transcribe()`
# MAGIC while preserving the existing IKF Type D / Article 9 control boundary.
# MAGIC
# MAGIC This notebook deliberately does NOT:
# MAGIC - translate the transcript;
# MAGIC - call any LLM analysis endpoint;
# MAGIC - write to Neo4j;
# MAGIC - publish transcript content;
# MAGIC - downgrade the Type D classification;
# MAGIC - alter the existing document pipeline.
# MAGIC
# MAGIC Databricks `ai_transcribe()` currently supports English and Spanish audio,
# MAGIC returns timestamped segments, and applies speaker diarization automatically
# MAGIC when enabled for the workspace.

# COMMAND ----------
from pyspark.sql import functions as F
import hashlib
import uuid
from datetime import datetime, timezone

# COMMAND ----------
# CONFIGURATION — set only these values for a controlled test.
# Use a Type D-controlled Unity Catalog Volume path.
AUDIO_PATH = ""  # e.g. /Volumes/<catalog>/<schema>/<volume>/type_d_audio/interview_001.mp3
SOURCE_ID = ""   # existing IKF source/evidence identifier if available
LANGUAGE_EXPECTED = ""  # advisory only: "en" or "es"

# Safety default: preview only. Set to True only when you intentionally want to persist
# into the governed Type D transcript tables after reviewing the schema below.
PERSIST = False

# Governed target tables. Creation is isolated from existing document tables.
AUDIO_TABLE = "bdw_analysis_prod.kg_poc.type_d_audio_source"
SEGMENT_TABLE = "bdw_analysis_prod.kg_poc.type_d_transcript_segment"

# COMMAND ----------
if not AUDIO_PATH.strip():
    raise ValueError("Set AUDIO_PATH to one controlled Type D audio file before running.")

if LANGUAGE_EXPECTED and LANGUAGE_EXPECTED not in {"en", "es"}:
    raise ValueError(
        "Current ai_transcribe Beta is validated only for English (en) and Spanish (es)."
    )

# COMMAND ----------
# Read one audio file as binary from a governed Unity Catalog Volume.
audio_df = (
    spark.read.format("binaryFile")
    .load(AUDIO_PATH)
    .select("path", "length", "modificationTime", "content")
)

rows = audio_df.count()
if rows != 1:
    raise RuntimeError(f"Expected exactly one audio file; found {rows}.")

meta = audio_df.select("path", "length", "modificationTime").first()
if meta["length"] is not None and int(meta["length"]) > 512 * 1024 * 1024:
    raise RuntimeError("ai_transcribe input exceeds the current 512 MB per-call limit.")

# COMMAND ----------
# Compute a source hash locally for provenance.
content = audio_df.select("content").first()["content"]
source_sha256 = hashlib.sha256(bytes(content)).hexdigest()
audio_source_id = f"audio_{source_sha256[:24]}"
transcription_run_id = f"transcription_{uuid.uuid4().hex}"
created_at = datetime.now(timezone.utc)

print("TYPE D AUDIO SOURCE")
print("audio_source_id:", audio_source_id)
print("sha256:", source_sha256)
print("path:", meta["path"])
print("bytes:", meta["length"])
print("transcription_run_id:", transcription_run_id)

# COMMAND ----------
# Call Databricks ai_transcribe().
# Output is VARIANT with response.duration_seconds and response.segments.
transcribed = audio_df.select(
    "path",
    F.expr("ai_transcribe(content)").alias("transcription_result"),
)

display(
    transcribed.select(
        "path",
        F.col("transcription_result:error_message").cast("string").alias("error_message"),
        F.col("transcription_result:response.duration_seconds").cast("double").alias("duration_seconds"),
    )
)

# COMMAND ----------
error = (
    transcribed
    .select(F.col("transcription_result:error_message").cast("string").alias("error_message"))
    .first()["error_message"]
)
if error:
    raise RuntimeError(f"ai_transcribe failed: {error}")

# COMMAND ----------
# Explode into one governed evidence row per timestamped segment.
# variant_explode is used in the documented SQL table-valued form for compatibility.
transcribed.createOrReplaceTempView("ikf_type_d_transcribed_audio")

segments = spark.sql("""
SELECT
  t.path,
  t.transcription_result:response.duration_seconds::DOUBLE AS duration_seconds,
  s.pos AS segment_index,
  s.value:start::DOUBLE AS start_seconds,
  s.value:end::DOUBLE AS end_seconds,
  s.value:speaker_id::STRING AS speaker_id,
  s.value:text::STRING AS transcript_text
FROM ikf_type_d_transcribed_audio t,
LATERAL variant_explode(t.transcription_result:response.segments) s
ORDER BY s.pos
""")

# COMMAND ----------
# Type D inheritance is explicit on every derived segment.
segments = (
    segments
    .withColumn("audio_source_id", F.lit(audio_source_id))
    .withColumn("source_id", F.lit(SOURCE_ID or None).cast("string"))
    .withColumn("source_sha256", F.lit(source_sha256))
    .withColumn("transcription_run_id", F.lit(transcription_run_id))
    .withColumn("classification", F.lit("TYPE_D"))
    .withColumn("derivative_type", F.lit("TRANSCRIPT_SEGMENT"))
    .withColumn("transcription_engine", F.lit("DATABRICKS_AI_TRANSCRIBE"))
    .withColumn("translation_status", F.lit("NOT_PERFORMED"))
    .withColumn("human_review_status", F.lit("NOT_REVIEWED"))
    .withColumn("created_at", F.lit(created_at).cast("timestamp"))
    .withColumn(
        "segment_text_sha256",
        F.sha2(F.coalesce(F.col("transcript_text"), F.lit("")), 256),
    )
    .withColumn(
        "transcript_segment_id",
        F.concat(
            F.lit("tseg_"),
            F.substring(
                F.sha2(
                    F.concat_ws(
                        "|",
                        F.lit(source_sha256),
                        F.col("segment_index").cast("string"),
                        F.col("start_seconds").cast("string"),
                        F.col("end_seconds").cast("string"),
                        F.coalesce(F.col("speaker_id"), F.lit("")),
                        F.coalesce(F.col("transcript_text"), F.lit("")),
                    ),
                    256,
                ),
                1,
                24,
            ),
        ),
    )
    .select(
        "transcript_segment_id",
        "audio_source_id",
        "source_id",
        "source_sha256",
        "transcription_run_id",
        "classification",
        "derivative_type",
        "transcription_engine",
        "translation_status",
        "human_review_status",
        "path",
        "duration_seconds",
        "segment_index",
        "start_seconds",
        "end_seconds",
        "speaker_id",
        "transcript_text",
        "segment_text_sha256",
        "created_at",
    )
)

display(segments)

# COMMAND ----------
# Basic integrity checks before any persistence.
segment_count = segments.count()
null_text = segments.filter(F.col("transcript_text").isNull()).count()
invalid_times = segments.filter(
    (F.col("start_seconds") < 0)
    | (F.col("end_seconds") < F.col("start_seconds"))
).count()

print("SEGMENT VALIDATION")
print("segments:", segment_count)
print("null transcript text:", null_text)
print("invalid timestamp ranges:", invalid_times)

if segment_count == 0:
    raise RuntimeError("Transcription returned zero segments.")
if invalid_times:
    raise RuntimeError(f"Found {invalid_times} invalid timestamp range(s).")

# COMMAND ----------
# Optional governed persistence. Disabled by default.
# Tables are deliberately separate from public/published-document material.
if PERSIST:
    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {AUDIO_TABLE} (
      audio_source_id STRING NOT NULL,
      source_id STRING,
      source_sha256 STRING NOT NULL,
      source_path STRING NOT NULL,
      source_size_bytes BIGINT,
      source_modification_time TIMESTAMP,
      classification STRING NOT NULL,
      transcription_engine STRING NOT NULL,
      transcription_run_id STRING NOT NULL,
      language_expected STRING,
      created_at TIMESTAMP NOT NULL
    ) USING DELTA
    """)

    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SEGMENT_TABLE} (
      transcript_segment_id STRING NOT NULL,
      audio_source_id STRING NOT NULL,
      source_id STRING,
      source_sha256 STRING NOT NULL,
      transcription_run_id STRING NOT NULL,
      classification STRING NOT NULL,
      derivative_type STRING NOT NULL,
      transcription_engine STRING NOT NULL,
      translation_status STRING NOT NULL,
      human_review_status STRING NOT NULL,
      path STRING NOT NULL,
      duration_seconds DOUBLE,
      segment_index BIGINT,
      start_seconds DOUBLE,
      end_seconds DOUBLE,
      speaker_id STRING,
      transcript_text STRING,
      segment_text_sha256 STRING NOT NULL,
      created_at TIMESTAMP NOT NULL
    ) USING DELTA
    """)

    source_row = spark.createDataFrame([
        (
            audio_source_id,
            SOURCE_ID or None,
            source_sha256,
            str(meta["path"]),
            int(meta["length"]) if meta["length"] is not None else None,
            meta["modificationTime"],
            "TYPE_D",
            "DATABRICKS_AI_TRANSCRIBE",
            transcription_run_id,
            LANGUAGE_EXPECTED or None,
            created_at,
        )
    ], schema="""
        audio_source_id string,
        source_id string,
        source_sha256 string,
        source_path string,
        source_size_bytes long,
        source_modification_time timestamp,
        classification string,
        transcription_engine string,
        transcription_run_id string,
        language_expected string,
        created_at timestamp
    """)

    # Insert-only semantics for the source hash/run combination.
    source_row.createOrReplaceTempView("ikf_new_type_d_audio_source")
    spark.sql(f"""
    INSERT INTO {AUDIO_TABLE}
    SELECT n.*
    FROM ikf_new_type_d_audio_source n
    WHERE NOT EXISTS (
      SELECT 1 FROM {AUDIO_TABLE} e
      WHERE e.audio_source_id = n.audio_source_id
        AND e.transcription_run_id = n.transcription_run_id
    )
    """)

    segments.createOrReplaceTempView("ikf_new_type_d_transcript_segments")
    spark.sql(f"""
    INSERT INTO {SEGMENT_TABLE}
    SELECT n.*
    FROM ikf_new_type_d_transcript_segments n
    WHERE NOT EXISTS (
      SELECT 1 FROM {SEGMENT_TABLE} e
      WHERE e.transcript_segment_id = n.transcript_segment_id
        AND e.transcription_run_id = n.transcription_run_id
    )
    """)

    print("PERSISTED — Type D audio source and transcript segments stored in governed tables.")
else:
    print("PREVIEW ONLY — no Delta writes performed. Set PERSIST=True only after reviewing the transcript and target tables.")

print("TYPE D inheritance preserved. Translation was not performed.")
