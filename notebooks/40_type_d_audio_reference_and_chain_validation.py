# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # 40 — Type D audio evidence reference resolver + end-to-end chain validation
# MAGIC
# MAGIC Purpose:
# MAGIC 1. provide one canonical evidence-reference view for both document passages and
# MAGIC    Type D audio transcript segments;
# MAGIC 2. validate the controlled Type D audio chain after notebooks 38 → 39 → 16;
# MAGIC 3. prove that any LLM candidate/relationship that cites transcript evidence can
# MAGIC    still be resolved to the exact protected audio timestamp and speaker.
# MAGIC
# MAGIC This notebook does not call an LLM, transcribe, translate, publish content,
# MAGIC or write to Neo4j. The only persistent object it may create is a SQL VIEW.

# COMMAND ----------
dbutils.widgets.text("analysis_id", "", "Type D analysis ID")
dbutils.widgets.dropdown("create_reference_view", "true", ["true", "false"], "Create/update evidence reference view")

# COMMAND ----------
import re

from pyspark.sql import functions as F

ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"
SEGMENT_TABLE = "bdw_analysis_prod.kg_poc.type_d_transcript_segment"
CANDIDATE_TABLE = "bdw_analysis_prod.kg_poc.analysis_candidate"
CANDIDATE_REL_TABLE = "bdw_analysis_prod.kg_poc.analysis_candidate_relationship"
REFERENCE_VIEW = "bdw_analysis_prod.kg_poc.analysis_evidence_reference"

analysis_id = dbutils.widgets.get("analysis_id").strip()
CREATE_VIEW = dbutils.widgets.get("create_reference_view").strip().lower() == "true"

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError("Enter a valid Type D analysis_id.")

for table_name in [ANALYSIS_PASSAGE_TABLE, SEGMENT_TABLE]:
    if not spark.catalog.tableExists(table_name):
        raise RuntimeError(f"Required table does not exist: {table_name}")

# COMMAND ----------
# A single stable resolver for every evidence passage.
# Document evidence keeps page references; audio transcript evidence resolves by
# exact timestamp and, when available, speaker. The transcript text itself remains
# unchanged in analysis_passage.
if CREATE_VIEW:
    spark.sql(f"""
    CREATE OR REPLACE VIEW {REFERENCE_VIEW} AS
    SELECT
        p.analysis_id,
        p.document_id,
        p.passage_id,
        p.passage_order,
        p.page_start,
        p.page_end,
        p.extraction_version,
        CASE
            WHEN t.transcript_segment_id IS NOT NULL THEN 'TYPE_D_AUDIO_TRANSCRIPT'
            ELSE 'DOCUMENT'
        END AS source_locator_type,
        CASE
            WHEN t.transcript_segment_id IS NOT NULL THEN t.classification
            ELSE NULL
        END AS source_classification,
        t.audio_source_id,
        t.transcription_run_id,
        t.start_seconds,
        t.end_seconds,
        t.speaker_id,
        CASE
            WHEN t.transcript_segment_id IS NOT NULL THEN concat(
                lpad(cast(floor(t.start_seconds / 3600) as string), 2, '0'), ':',
                lpad(cast(floor((t.start_seconds % 3600) / 60) as string), 2, '0'), ':',
                lpad(cast(floor(t.start_seconds % 60) as string), 2, '0'),
                '–',
                lpad(cast(floor(t.end_seconds / 3600) as string), 2, '0'), ':',
                lpad(cast(floor((t.end_seconds % 3600) / 60) as string), 2, '0'), ':',
                lpad(cast(floor(t.end_seconds % 60) as string), 2, '0'),
                CASE
                    WHEN t.speaker_id IS NOT NULL AND trim(t.speaker_id) <> ''
                    THEN concat(' · Speaker ', t.speaker_id)
                    ELSE ''
                END
            )
            WHEN p.page_start IS NULL THEN 'source location unavailable'
            WHEN p.page_end IS NULL OR p.page_end = p.page_start
                THEN concat('p. ', cast(p.page_start as string))
            ELSE concat(
                'pp. ', cast(p.page_start as string), '–', cast(p.page_end as string)
            )
        END AS source_reference
    FROM {ANALYSIS_PASSAGE_TABLE} p
    LEFT JOIN {SEGMENT_TABLE} t
      ON p.passage_id = t.transcript_segment_id
     AND p.document_id = t.audio_source_id
    """)
    print("Evidence reference view ready:", REFERENCE_VIEW)

if not spark.catalog.tableExists(REFERENCE_VIEW):
    raise RuntimeError(
        f"Reference view does not exist: {REFERENCE_VIEW}. Run with create_reference_view=true."
    )

# COMMAND ----------
refs = (
    spark.table(REFERENCE_VIEW)
    .filter(F.col("analysis_id") == analysis_id)
    .orderBy("document_id", "passage_order")
)

if refs.count() == 0:
    raise RuntimeError("No evidence references found for this analysis.")

display(refs)

# COMMAND ----------
# Fail closed on Type D transcript integrity.
audio_refs = refs.filter(F.col("source_locator_type") == "TYPE_D_AUDIO_TRANSCRIPT")
audio_count = audio_refs.count()

if audio_count == 0:
    raise RuntimeError(
        "This analysis contains no bound Type D audio transcript passages. Run notebooks 38 and 39 first."
    )

non_d = audio_refs.filter(F.upper(F.col("source_classification")) != "TYPE_D").count()
missing_start = audio_refs.filter(F.col("start_seconds").isNull()).count()
missing_end = audio_refs.filter(F.col("end_seconds").isNull()).count()
invalid_ranges = audio_refs.filter(F.col("end_seconds") < F.col("start_seconds")).count()
missing_reference = audio_refs.filter(
    F.col("source_reference").isNull() | (F.trim(F.col("source_reference")) == "")
).count()

print("TYPE D AUDIO REFERENCE VALIDATION")
print("audio transcript passages:", audio_count)
print("non-Type-D passages:", non_d)
print("missing start timestamps:", missing_start)
print("missing end timestamps:", missing_end)
print("invalid timestamp ranges:", invalid_ranges)
print("missing rendered references:", missing_reference)

if any([non_d, missing_start, missing_end, invalid_ranges, missing_reference]):
    raise RuntimeError(
        "FAIL — Type D audio reference integrity check failed. "
        f"non_d={non_d}, missing_start={missing_start}, missing_end={missing_end}, "
        f"invalid_ranges={invalid_ranges}, missing_reference={missing_reference}"
    )

# COMMAND ----------
# Optional downstream validation: every LLM candidate/relationship passage ID that
# belongs to this analysis must still resolve through the same canonical reference view.
# This does not require that notebook 16 has already been run; if candidate tables are
# empty, the evidence chain itself can still PASS.
referenced_ids = None

if spark.catalog.tableExists(CANDIDATE_TABLE):
    candidate_ids = (
        spark.table(CANDIDATE_TABLE)
        .filter(F.col("analysis_id") == analysis_id)
        .select(F.explode_outer("passage_ids").alias("passage_id"))
        .filter(F.col("passage_id").isNotNull())
    )
    referenced_ids = candidate_ids

if spark.catalog.tableExists(CANDIDATE_REL_TABLE):
    rel_ids = (
        spark.table(CANDIDATE_REL_TABLE)
        .filter(F.col("analysis_id") == analysis_id)
        .select(F.explode_outer("passage_ids").alias("passage_id"))
        .filter(F.col("passage_id").isNotNull())
    )
    referenced_ids = rel_ids if referenced_ids is None else referenced_ids.unionByName(rel_ids)

if referenced_ids is not None:
    referenced_ids = referenced_ids.distinct()
    downstream_count = referenced_ids.count()

    unresolved = (
        referenced_ids.alias("r")
        .join(
            refs.select("passage_id", "source_reference").distinct().alias("v"),
            F.col("r.passage_id") == F.col("v.passage_id"),
            "left_anti",
        )
    )
    unresolved_count = unresolved.count()

    print("DOWNSTREAM LLM TRACEABILITY")
    print("distinct cited passage IDs:", downstream_count)
    print("unresolved cited passage IDs:", unresolved_count)

    if unresolved_count:
        display(unresolved)
        raise RuntimeError(
            f"FAIL — {unresolved_count} downstream LLM evidence passage ID(s) cannot be resolved to source evidence."
        )
else:
    print("No candidate tables available yet; downstream LLM traceability check skipped.")

# COMMAND ----------
print("PASS — Type D audio evidence remains traceable by timestamp and speaker through the IKF evidence contract.")
print("Use analysis_evidence_reference.source_reference in the app instead of page-only rendering.")
print("No translation was performed. No LLM call, Neo4j write, or publication action was performed by this notebook.")
