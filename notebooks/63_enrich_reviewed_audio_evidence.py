# Databricks notebook source
# MAGIC %md
# MAGIC # 63 — Enrich reviewed Type D audio evidence
# MAGIC
# MAGIC Deterministic, no-LLM post-processing for analyses created from a **human-reviewed**
# MAGIC Type-D transcript.
# MAGIC
# MAGIC The notebook maps timestamp markers already preserved in the reviewed transcript
# MAGIC passages back to the original audio and adds those locations to Findings/Evidence and
# MAGIC Knowledge Graph provenance. It never upgrades an unreviewed transcript and never
# MAGIC transcribes audio.

# COMMAND ----------

dbutils.widgets.text("analysis_id", "", "Analysis ID")

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase
from pyspark.sql import Row

analysis_id = dbutils.widgets.get("analysis_id").strip()
if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError("Enter a valid IKF analysis_id")

current_notebook_path = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
workspace_notebook_path = (
    "/Workspace" + current_notebook_path
    if current_notebook_path.startswith("/Users/")
    else current_notebook_path
)
ikf_repo_root = workspace_notebook_path.rsplit("/notebooks/", 1)[0]
ikf_src_path = os.path.join(ikf_repo_root, "src")
if ikf_src_path not in sys.path:
    sys.path.insert(0, ikf_src_path)

from ikf.audio_evidence import (
    AudioEvidenceLocation,
    audio_evidence_reference,
    extract_audio_time_range,
)

ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"
AUDIO_LOCATION_TABLE = "bdw_analysis_prod.kg_poc.analysis_audio_passage_location"
TRANSCRIPT_ROOT = Path(
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/type_d_transcripts"
)
ENRICHMENT_VERSION = "IKF_AUDIO_EVIDENCE_V0.1"

# COMMAND ----------

try:
    NEO4J_URI
    NEO4J_USERNAME
    NEO4J_PASSWORD
except NameError:
    NEO4J_URI = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_uri")
    NEO4J_USERNAME = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_username")
    NEO4J_PASSWORD = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_password")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

# COMMAND ----------

with driver.session() as session:
    record = session.run(
        """
        MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
        OPTIONAL MATCH (a)-[:DERIVED_FROM_REVIEWED_TRANSCRIPT]->(r:TypeDTranscriptReview)
        RETURN
            properties(a)["information_class"] AS information_class,
            properties(a)["audio_source_sha256"] AS audio_source_sha256,
            properties(a)["transcript_model"] AS transcript_model,
            properties(a)["transcript_reviewed_text_sha256"] AS reviewed_text_sha256,
            r.status AS review_status,
            r.reviewed_by AS reviewed_by,
            toString(r.reviewed_at) AS reviewed_at
        """,
        analysis_id=analysis_id,
    ).single()

if record is None:
    raise ValueError(f"AnalysisGroup not found: {analysis_id}")

meta = record.data()
if meta.get("information_class") != "D":
    raise ValueError("Audio evidence enrichment is restricted to Class D analyses")
if meta.get("review_status") != "HUMAN_REVIEWED":
    raise ValueError(
        "The analysis is not linked to a HUMAN_REVIEWED transcript. "
        "Machine-generated unverified text cannot be enriched as evidence."
    )

source_sha256 = str(meta.get("audio_source_sha256") or "").lower()
model_name = str(meta.get("transcript_model") or "").strip()
reviewed_text_sha256 = str(meta.get("reviewed_text_sha256") or "").lower()

if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
    raise ValueError("Analysis is missing a valid audio source SHA-256")
if not model_name:
    raise ValueError("Analysis is missing transcript model provenance")
if not re.fullmatch(r"[0-9a-f]{64}", reviewed_text_sha256):
    raise ValueError("Analysis is missing reviewed transcript text provenance")

transcript_path = TRANSCRIPT_ROOT / f"{source_sha256}__{model_name}.json"
if not transcript_path.is_file():
    raise FileNotFoundError(
        "The machine transcript JSON is unavailable for source-name provenance: "
        + str(transcript_path)
    )

with transcript_path.open(encoding="utf-8") as handle:
    transcript_record = json.load(handle)

if transcript_record.get("classification") != "D":
    raise ValueError("Transcript JSON is not Class D")
if transcript_record.get("source_sha256") != source_sha256:
    raise ValueError("Transcript JSON source hash does not match the analysis")

source_name = str(
    transcript_record.get("source_name")
    or ("Audio " + source_sha256[:12])
)

print("Analysis:", analysis_id)
print("Audio source:", source_name)
print("Transcript model:", model_name)
print("Human review status:", meta.get("review_status"))

# COMMAND ----------

passages = (
    spark.table(ANALYSIS_PASSAGE_TABLE)
    .filter(f"analysis_id = '{analysis_id}'")
    .select("passage_id", "passage_text")
    .collect()
)

if not passages:
    raise ValueError("No persisted analysis passages were found")

created_at = datetime.now(timezone.utc)
location_rows = []
location_by_passage = {}

for passage in passages:
    time_range = extract_audio_time_range(passage["passage_text"] or "")
    if time_range is None:
        continue

    location = AudioEvidenceLocation(
        source_sha256=source_sha256,
        start_s=time_range[0],
        end_s=time_range[1],
    )
    reference = audio_evidence_reference(
        source_name=source_name,
        location=location,
    )
    location_by_passage[passage["passage_id"]] = {
        "location": location.serialise(),
        "reference": reference,
        "start_s": location.start_s,
        "end_s": location.end_s,
    }
    location_rows.append(
        Row(
            analysis_id=analysis_id,
            passage_id=passage["passage_id"],
            source_audio_sha256=source_sha256,
            source_name=source_name,
            start_s=float(location.start_s),
            end_s=float(location.end_s),
            transcript_model=model_name,
            reviewed_text_sha256=reviewed_text_sha256,
            enrichment_version=ENRICHMENT_VERSION,
            created_at=created_at,
        )
    )

if not location_rows:
    raise ValueError(
        "The reviewed transcript passages contain no [HH:MM:SS–HH:MM:SS] markers. "
        "Audio evidence provenance cannot be reconstructed safely."
    )

print("Passages with audio locations:", len(location_rows), "/", len(passages))

# COMMAND ----------

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {AUDIO_LOCATION_TABLE} (
        analysis_id STRING NOT NULL,
        passage_id STRING NOT NULL,
        source_audio_sha256 STRING NOT NULL,
        source_name STRING NOT NULL,
        start_s DOUBLE NOT NULL,
        end_s DOUBLE NOT NULL,
        transcript_model STRING NOT NULL,
        reviewed_text_sha256 STRING NOT NULL,
        enrichment_version STRING NOT NULL,
        created_at TIMESTAMP NOT NULL
    )
    USING DELTA
    """
)

location_df = spark.createDataFrame(location_rows)
location_df.createOrReplaceTempView("ikf_audio_location_updates")

spark.sql(
    f"""
    MERGE INTO {AUDIO_LOCATION_TABLE} AS target
    USING ikf_audio_location_updates AS source
      ON target.analysis_id = source.analysis_id
     AND target.passage_id = source.passage_id
    WHEN MATCHED THEN UPDATE SET
        target.source_audio_sha256 = source.source_audio_sha256,
        target.source_name = source.source_name,
        target.start_s = source.start_s,
        target.end_s = source.end_s,
        target.transcript_model = source.transcript_model,
        target.reviewed_text_sha256 = source.reviewed_text_sha256,
        target.enrichment_version = source.enrichment_version,
        target.created_at = source.created_at
    WHEN NOT MATCHED THEN INSERT *
    """
)

# COMMAND ----------


def audio_provenance_for_passages(passage_ids):
    locations = []
    references = []
    seen_locations = set()
    seen_references = set()

    for passage_id in passage_ids or []:
        item = location_by_passage.get(passage_id)
        if item is None:
            continue
        if item["location"] not in seen_locations:
            seen_locations.add(item["location"])
            locations.append(item["location"])
        if item["reference"] not in seen_references:
            seen_references.add(item["reference"])
            references.append(item["reference"])

    return locations, references


def append_unique(existing, additions):
    result = list(existing or [])
    for value in additions or []:
        if value not in result:
            result.append(value)
    return result


with driver.session() as session:
    node_rows = [
        row.data()
        for row in session.run(
            """
            MATCH (n:KGNode {analysis_id: $analysis_id})
            RETURN
                n.node_id AS node_id,
                n.model_run_id AS model_run_id,
                coalesce(properties(n)["evidence_passage_ids"], []) AS passage_ids,
                coalesce(properties(n)["evidence_references"], []) AS evidence_references
            """,
            analysis_id=analysis_id,
        )
    ]

    nodes_enriched = 0
    for node in node_rows:
        audio_locations, audio_references = audio_provenance_for_passages(
            node["passage_ids"]
        )
        if not audio_locations:
            continue
        session.run(
            """
            MATCH (n:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $node_id
            })
            SET n.audio_evidence_locations = $audio_locations,
                n.audio_evidence_references = $audio_references,
                n.evidence_references = $all_references,
                n.audio_evidence_enrichment_version = $version
            """,
            analysis_id=analysis_id,
            model_run_id=node["model_run_id"],
            node_id=node["node_id"],
            audio_locations=audio_locations,
            audio_references=audio_references,
            all_references=append_unique(
                node["evidence_references"],
                audio_references,
            ),
            version=ENRICHMENT_VERSION,
        ).consume()
        nodes_enriched += 1

    relationship_rows = [
        row.data()
        for row in session.run(
            """
            MATCH (source:KGNode {analysis_id: $analysis_id})-[r]->(target:KGNode {analysis_id: $analysis_id})
            WHERE properties(r)["edge_id"] IS NOT NULL
            RETURN
                r.edge_id AS edge_id,
                source.model_run_id AS model_run_id,
                coalesce(properties(r)["evidence_passage_ids"], []) AS passage_ids,
                coalesce(properties(r)["evidence_references"], []) AS evidence_references
            """,
            analysis_id=analysis_id,
        )
    ]

    relationships_enriched = 0
    for relationship in relationship_rows:
        audio_locations, audio_references = audio_provenance_for_passages(
            relationship["passage_ids"]
        )
        if not audio_locations:
            continue
        session.run(
            """
            MATCH (source:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id
            })-[r]->(target:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id
            })
            WHERE r.edge_id = $edge_id
            SET r.audio_evidence_locations = $audio_locations,
                r.audio_evidence_references = $audio_references,
                r.evidence_references = $all_references,
                r.audio_evidence_enrichment_version = $version
            """,
            analysis_id=analysis_id,
            model_run_id=relationship["model_run_id"],
            edge_id=relationship["edge_id"],
            audio_locations=audio_locations,
            audio_references=audio_references,
            all_references=append_unique(
                relationship["evidence_references"],
                audio_references,
            ),
            version=ENRICHMENT_VERSION,
        ).consume()
        relationships_enriched += 1

    session.run(
        """
        MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
        SET a.audio_evidence_enrichment_version = $version,
            a.audio_evidence_enriched_at = datetime(),
            a.audio_evidence_passages = $passages
        """,
        analysis_id=analysis_id,
        version=ENRICHMENT_VERSION,
        passages=len(location_rows),
    ).consume()

print("KG nodes enriched:", nodes_enriched)
print("KG relationships enriched:", relationships_enriched)
print("PASS — REVIEWED TYPE D AUDIO EVIDENCE ENRICHED")
print("No model endpoint was called by this notebook.")
