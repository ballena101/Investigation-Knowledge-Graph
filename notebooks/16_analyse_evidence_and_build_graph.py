# Databricks notebook source
# MAGIC %md
# MAGIC # 16 — Analyse evidence group and build the generic graph
# MAGIC
# MAGIC Converts an EVIDENCE_READY analysis into an evidence-grounded,
# MAGIC cross-document Investigation Knowledge Graph.
# MAGIC
# MAGIC Method:
# MAGIC 1. read persisted passages;
# MAGIC 2. extract evidence-grounded candidate concepts/relationships in batches;
# MAGIC 3. resolve duplicate concepts across all selected documents;
# MAGIC 4. consolidate only already-supported relationships;
# MAGIC 5. publish one analysis graph to Neo4j;
# MAGIC 6. store a concise analytical summary on the AnalysisGroup.
# MAGIC
# MAGIC Chronology is never promoted automatically to causality.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)

dbutils.widgets.text(
    "model_service",
    "system.ai.gpt-5-6-sol",
    "Databricks model service / endpoint",
)

dbutils.widgets.text(
    "model_run_key",
    "PRIMARY",
    "Model run key",
)

dbutils.widgets.text(
    "model_label",
    "Primary model",
    "Model label",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 databricks-sdk==0.139.0

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

analysis_id = dbutils.widgets.get("analysis_id").strip()
model_service = dbutils.widgets.get("model_service").strip()
model_run_key = dbutils.widgets.get("model_run_key").strip() or "PRIMARY"
model_label = dbutils.widgets.get("model_label").strip() or model_run_key
comparison_mode = model_run_key != "PRIMARY"
model_run_started = time.perf_counter()
model_usage_totals = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}

# COMMAND ----------

import hashlib
import json
import re
import time
import uuid
import urllib.request
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ChatMessage,
    ChatMessageRole,
)
from neo4j import GraphDatabase
from pyspark.sql import Row

ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"
CANDIDATE_TABLE = "bdw_analysis_prod.kg_poc.analysis_candidate"
CANDIDATE_REL_TABLE = (
    "bdw_analysis_prod.kg_poc.analysis_candidate_relationship"
)
SUMMARY_TABLE = "bdw_analysis_prod.kg_poc.analysis_summary"

ANALYSIS_VERSION = "GROUP_ANALYSIS_LLM_V0.2"
PRIVACY_OUTPUT_MODE = "DE_IDENTIFIED_BY_DEFAULT"
MAX_PASSAGES = 500
MAX_BATCH_CHARS = 14000
MAX_BATCH_PASSAGES = 8

ALLOWED_NODE_KINDS = {
    "Event",
    "ContributingFactor",
    "Finding",
    "SafetyIssue",
    "Recommendation",
    "Actor",
    "Vessel",
    "System",
    "Claim",
}

ALLOWED_RELATIONSHIPS = {
    "FOLLOWED_BY",
    "CONTRIBUTED_TO",
    "RESULTED_IN",
    "AFFECTED",
    "SUPPORTS",
}

ALLOWED_EVIDENCE_CLASSES = {
    "DIRECT",
    "NORMALISED",
    "INFERRED",
    "SYNTHESISED",
    "INSUFFICIENT_EVIDENCE",
}

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError(
        "Enter a valid analysis_id created by the App."
    )

print("Analysis:", analysis_id)
print("Model service:", model_service)
print("Model run:", model_run_key)
print("Comparison mode:", comparison_mode)

if model_service == "__SKIP__":
    print("Model run skipped by policy.")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------

try:
    NEO4J_URI
    NEO4J_USERNAME
    NEO4J_PASSWORD
except NameError:
    NEO4J_URI = dbutils.secrets.get(
        scope="kg-poc-app",
        key="neo4j_uri",
    )
    NEO4J_USERNAME = dbutils.secrets.get(
        scope="kg-poc-app",
        key="neo4j_username",
    )
    NEO4J_PASSWORD = dbutils.secrets.get(
        scope="kg-poc-app",
        key="neo4j_password",
    )

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

w = WorkspaceClient()

print("Neo4j connection: OK")
print("Databricks WorkspaceClient: ready")

# COMMAND ----------

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {CANDIDATE_TABLE} (
        analysis_id STRING NOT NULL,
        candidate_id STRING NOT NULL,
        extraction_batch INT NOT NULL,
        node_kind STRING NOT NULL,
        label STRING NOT NULL,
        description STRING,
        passage_ids ARRAY<STRING>,
        evidence_text STRING,
        evidence_class STRING,
        model_service STRING,
        analysis_version STRING,
        created_at TIMESTAMP NOT NULL
    )
    USING DELTA
    """
)

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {CANDIDATE_REL_TABLE} (
        analysis_id STRING NOT NULL,
        candidate_relationship_id STRING NOT NULL,
        extraction_batch INT NOT NULL,
        source_candidate_id STRING NOT NULL,
        relationship STRING NOT NULL,
        target_candidate_id STRING NOT NULL,
        passage_ids ARRAY<STRING>,
        evidence_text STRING,
        evidence_class STRING,
        model_service STRING,
        analysis_version STRING,
        created_at TIMESTAMP NOT NULL
    )
    USING DELTA
    """
)

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {SUMMARY_TABLE} (
        analysis_id STRING NOT NULL,
        model_service STRING,
        analysis_version STRING,
        output_language STRING,
        overview STRING,
        key_findings_json STRING,
        uncertainties_json STRING,
        source_conflicts_json STRING,
        created_at TIMESTAMP NOT NULL
    )
    USING DELTA
    """
)

print("Analysis persistence tables: ready")

# COMMAND ----------

def update_analysis(
    *,
    status,
    stage,
    batches_total=None,
    batches_processed=None,
    error_message=None,
):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
    SET
        a.status = $status,
        a.processing_stage = $stage,
        a.processing_updated_at = datetime(),
        a.processing_error = $error_message
    FOREACH (_ IN CASE WHEN $batches_total IS NULL THEN [] ELSE [1] END |
        SET a.analysis_batches_total = $batches_total
    )
    FOREACH (_ IN CASE WHEN $batches_processed IS NULL THEN [] ELSE [1] END |
        SET a.analysis_batches_processed = $batches_processed
    )
    """

    with driver.session() as session:
        session.run(
            query,
            analysis_id=analysis_id,
            status=status,
            stage=stage,
            batches_total=batches_total,
            batches_processed=batches_processed,
            error_message=error_message,
        ).consume()


def load_analysis_meta():
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
    OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
    WITH a, collect({
        document_id: d.document_id,
        filename: d.filename
    }) AS documents
    RETURN
        a.analysis_id AS analysis_id,
        a.analysis_title AS analysis_title,
        a.analysis_objective AS analysis_objective,
        a.status AS status,
        a.language_mode AS language_mode,
        a.output_language AS output_language,
        documents
    """

    with driver.session() as session:
        record = session.run(
            query,
            analysis_id=analysis_id,
        ).single()

    return record.data() if record else None


analysis = load_analysis_meta()

if not analysis:
    raise ValueError(
        f"AnalysisGroup not found: {analysis_id}"
    )

if analysis["status"] not in {
    "EVIDENCE_READY",
    "ANALYSING",
    "FAILED",
    "COMPLETED",
}:
    raise ValueError(
        "Evidence is not ready. Run notebook 15 first. "
        f"Current status: {analysis['status']}"
    )

document_names = {
    item["document_id"]: item["filename"]
    for item in analysis["documents"]
    if item.get("document_id")
}

print("Title:", analysis["analysis_title"])
print("Output language:", analysis["output_language"])

model_run_id = (
    analysis_id
    + "__"
    + model_run_key.lower()
)

with driver.session() as session:
    session.run(
        """
        MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
        MERGE (m:ModelRun {model_run_id: $model_run_id})
        ON CREATE SET
            m.created_at = datetime()
        SET
            m.analysis_id = $analysis_id,
            m.model_key = $model_run_key,
            m.model_label = $model_label,
            m.model_service = $model_service,
            m.status = 'ANALYSING',
            m.updated_at = datetime()
        MERGE (a)-[:HAS_MODEL_RUN]->(m)
        """,
        analysis_id=analysis_id,
        model_run_id=model_run_id,
        model_run_key=model_run_key,
        model_label=model_label,
        model_service=model_service,
    ).consume()

# COMMAND ----------

passage_rows = (
    spark.table(ANALYSIS_PASSAGE_TABLE)
    .filter(f"analysis_id = '{analysis_id}'")
    .select(
        "document_id",
        "passage_id",
        "page_start",
        "page_end",
        "passage_order",
        "detected_language",
        "passage_text",
    )
    .orderBy(
        "document_id",
        "passage_order",
    )
    .collect()
)

if not passage_rows:
    raise ValueError(
        "No evidence passages exist for this analysis. "
        "Run notebook 15 first."
    )

if len(passage_rows) > MAX_PASSAGES:
    raise ValueError(
        f"This PoC analysis stage currently supports up to "
        f"{MAX_PASSAGES} passages; found {len(passage_rows)}. "
        "Use a smaller document group or increase the controlled limit "
        "after validating cost and quality."
    )

print("Evidence passages:", len(passage_rows))

# COMMAND ----------

def build_batches(rows):
    batches = []
    current = []
    chars = 0

    for row in rows:
        text = row["passage_text"] or ""
        estimated = len(text) + 250

        if current and (
            len(current) >= MAX_BATCH_PASSAGES
            or chars + estimated > MAX_BATCH_CHARS
        ):
            batches.append(current)
            current = []
            chars = 0

        current.append(row)
        chars += estimated

    if current:
        batches.append(current)

    return batches


batches = build_batches(passage_rows)

print("Analysis batches:", len(batches))

# COMMAND ----------

def strip_code_fences(text):
    value = (text or "").strip()
    fence = chr(96) * 3

    if value.startswith(fence):
        value = re.sub(
            r"^.{3}(?:json)?\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"\s*.{3}$",
            "",
            value,
        )

    return value.strip()


def query_model_json(
    *,
    system_prompt,
    user_prompt,
    max_tokens,
):
    last_error = None

    for attempt in range(2):
        if attempt == 0:
            active_user_prompt = user_prompt
        else:
            active_user_prompt = (
                user_prompt
                + "\n\nIMPORTANT: Your previous response could not be "
                  "parsed as JSON. Return one valid JSON object only, with "
                  "no Markdown fences or commentary."
            )

        if model_run_key == "LLAMA70":
            if not model_service.startswith(("http://", "https://")):
                raise ValueError(
                    "The Ollama Llama 3.3 70B route requires the controlled "
                    "Ollama service base URL."
                )

            ollama_url = model_service.rstrip("/") + "/api/chat"
            request_body = json.dumps(
                {
                    "model": "llama3.3:70b",
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": active_user_prompt,
                        },
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.0,
                    },
                }
            ).encode("utf-8")

            request = urllib.request.Request(
                ollama_url,
                data=request_body,
                headers={
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(
                request,
                timeout=600,
            ) as ollama_response:
                payload = json.loads(
                    ollama_response.read().decode("utf-8")
                )

            text = (
                payload.get("message", {})
                .get("content", "")
            )
        else:
            response = w.serving_endpoints.query(
                name=model_service,
                messages=[
                    ChatMessage(
                        role=ChatMessageRole.SYSTEM,
                        content=system_prompt,
                    ),
                    ChatMessage(
                        role=ChatMessageRole.USER,
                        content=active_user_prompt,
                    ),
                ],
                temperature=0.0,
                max_tokens=max_tokens,
            )

            usage = getattr(
            response,
            "usage",
            None,
        )
        if usage is not None:
            model_usage_totals["prompt_tokens"] += int(
                getattr(
                    usage,
                    "prompt_tokens",
                    0,
                )
                or 0
            )
            model_usage_totals["completion_tokens"] += int(
                getattr(
                    usage,
                    "completion_tokens",
                    0,
                )
                or 0
            )
            model_usage_totals["total_tokens"] += int(
                getattr(
                    usage,
                    "total_tokens",
                    0,
                )
                or 0
            )

        text = response.choices[0].message.content

        try:
            return json.loads(
                strip_code_fences(text)
            )
        except Exception as exc:
            last_error = exc

    raise ValueError(
        f"Model response was not valid JSON after retry: {last_error}"
    )


EXTRACTION_SYSTEM_PROMPT = """
You are an evidence extraction component for a maritime investigation
knowledge graph.

Use ONLY the passages supplied by the user.

Method rules:
1. Never convert chronology, proximity, correlation or sequence into causality.
2. A causal or contributory relationship may be emitted only when the supplied
   text supports that relationship.
3. Keep conflicting statements as evidence/claims; do not resolve conflicts by
   guessing.
4. Do not create facts from general maritime knowledge.
5. Preserve source provenance through passage_ids.
6. Relationship vocabulary is limited to:
   FOLLOWED_BY, CONTRIBUTED_TO, RESULTED_IN, AFFECTED, SUPPORTS.
7. Node kinds are limited to:
   Event, ContributingFactor, Finding, SafetyIssue, Recommendation, Actor,
   Vessel, System, Claim.
8. Evidence class is one of:
   DIRECT, NORMALISED, INFERRED, SYNTHESISED, INSUFFICIENT_EVIDENCE.
9. Prefer DIRECT or NORMALISED. Use INFERRED sparingly and never for unsupported
   causality.
10. Protect personal and confidential information in analytical outputs.
11. Do not reproduce personal names, email addresses, phone numbers, home
    addresses, personal identifiers, dates of birth, medical details or other
    unnecessary identifying information in labels, descriptions, summaries or
    findings.
12. When a person must be represented analytically, use a functional role
    such as "master", "chief engineer", "passenger", "witness" or
    "investigator" rather than the person's name.
13. Do not combine otherwise innocuous details in a way that makes a person
    identifiable unless that identity is strictly necessary for the authorised
    safety-analysis purpose.
14. Vessel names, equipment names and organisations are not automatically
    personal data, but still minimise them when they are irrelevant to the
    analytical purpose.
15. Return JSON only.

Required JSON shape:
{
  "candidates": [
    {
      "candidate_id": "c1",
      "kind": "Event",
      "label": "short canonical label",
      "description": "concise description grounded in the passage",
      "passage_ids": ["passage_..."],
      "evidence_text": "short evidence excerpt or faithful condensed wording",
      "evidence_class": "DIRECT"
    }
  ],
  "relationships": [
    {
      "relationship_id": "r1",
      "source_candidate_id": "c1",
      "relationship": "RESULTED_IN",
      "target_candidate_id": "c2",
      "passage_ids": ["passage_..."],
      "evidence_text": "short support for the relationship",
      "evidence_class": "DIRECT"
    }
  ]
}

If no supported relationship is present, return an empty relationships array.
"""


def passage_block(row):
    filename = document_names.get(
        row["document_id"],
        row["document_id"],
    )

    return (
        f"[PASSAGE_ID: {row['passage_id']}]\n"
        f"[DOCUMENT: {filename}]\n"
        f"[DOCUMENT_ID: {row['document_id']}]\n"
        f"[PAGE: {row['page_start']}]\n"
        f"[LANGUAGE: {row['detected_language']}]\n"
        f"{row['passage_text']}"
    )


def validate_candidate(candidate):
    kind = candidate.get("kind")

    if kind not in ALLOWED_NODE_KINDS:
        return False

    if not candidate.get("candidate_id"):
        return False

    if not candidate.get("label"):
        return False

    evidence_class = candidate.get(
        "evidence_class",
        "NORMALISED",
    )

    if evidence_class not in ALLOWED_EVIDENCE_CLASSES:
        candidate["evidence_class"] = "NORMALISED"

    return True


def validate_relationship(relationship):
    if (
        relationship.get("relationship")
        not in ALLOWED_RELATIONSHIPS
    ):
        return False

    if not relationship.get("source_candidate_id"):
        return False

    if not relationship.get("target_candidate_id"):
        return False

    evidence_class = relationship.get(
        "evidence_class",
        "NORMALISED",
    )

    if evidence_class not in ALLOWED_EVIDENCE_CLASSES:
        relationship["evidence_class"] = "NORMALISED"

    return True

# COMMAND ----------

created_at = datetime.now(timezone.utc)
candidate_rows = []
candidate_relationship_rows = []
candidate_payloads = []
relationship_payloads = []

try:
    update_analysis(
        status="ANALYSING",
        stage="CANDIDATE_EXTRACTION",
        batches_total=len(batches),
        batches_processed=0,
        error_message=None,
    )

    if not comparison_mode:
        spark.sql(
            f"""
            DELETE FROM {CANDIDATE_TABLE}
            WHERE analysis_id = '{analysis_id}'
            """
        )
        spark.sql(
            f"""
            DELETE FROM {CANDIDATE_REL_TABLE}
            WHERE analysis_id = '{analysis_id}'
            """
        )

    for batch_index, batch in enumerate(
        batches,
        start=1,
    ):
        print(
            f"Analysing evidence batch "
            f"{batch_index}/{len(batches)}"
        )

        user_prompt = (
            f"Analysis title: {analysis['analysis_title']}\n"
            f"Analysis objective: "
            f"{analysis.get('analysis_objective') or 'General investigation analysis'}\n\n"
            "Extract evidence-grounded candidate concepts and supported "
            "relationships from these passages:\n\n"
            + "\n\n---\n\n".join(
                passage_block(row)
                for row in batch
            )
        )

        result = query_model_json(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=4000,
        )

        local_candidates = {}

        for raw_candidate in result.get(
            "candidates",
            [],
        ):
            if not validate_candidate(raw_candidate):
                continue

            local_id = str(
                raw_candidate["candidate_id"]
            )
            global_id = (
                f"b{batch_index:03d}_{local_id}"
            )

            local_candidates[local_id] = global_id

            payload = {
                "candidate_id": global_id,
                "kind": raw_candidate["kind"],
                "label": str(
                    raw_candidate["label"]
                ).strip(),
                "description": str(
                    raw_candidate.get(
                        "description",
                        "",
                    )
                ).strip(),
                "passage_ids": [
                    str(x)
                    for x in raw_candidate.get(
                        "passage_ids",
                        [],
                    )
                ],
                "evidence_text": str(
                    raw_candidate.get(
                        "evidence_text",
                        "",
                    )
                ).strip()[:1200],
                "evidence_class": (
                    raw_candidate.get(
                        "evidence_class",
                        "NORMALISED",
                    )
                ),
                "batch": batch_index,
            }

            candidate_payloads.append(
                payload
            )

            candidate_rows.append(
                Row(
                    analysis_id=analysis_id,
                    candidate_id=global_id,
                    extraction_batch=batch_index,
                    node_kind=payload["kind"],
                    label=payload["label"],
                    description=payload["description"],
                    passage_ids=payload["passage_ids"],
                    evidence_text=payload["evidence_text"],
                    evidence_class=payload["evidence_class"],
                    model_service=model_service,
                    analysis_version=ANALYSIS_VERSION,
                    created_at=created_at,
                )
            )

        for raw_relationship in result.get(
            "relationships",
            [],
        ):
            if not validate_relationship(
                raw_relationship
            ):
                continue

            source_local = str(
                raw_relationship[
                    "source_candidate_id"
                ]
            )
            target_local = str(
                raw_relationship[
                    "target_candidate_id"
                ]
            )

            if (
                source_local not in local_candidates
                or target_local
                not in local_candidates
            ):
                continue

            relation_local_id = str(
                raw_relationship.get(
                    "relationship_id",
                    uuid.uuid4().hex[:8],
                )
            )

            relationship_id = (
                f"b{batch_index:03d}_"
                f"{relation_local_id}"
            )

            payload = {
                "candidate_relationship_id": relationship_id,
                "source_candidate_id": local_candidates[
                    source_local
                ],
                "relationship": raw_relationship[
                    "relationship"
                ],
                "target_candidate_id": local_candidates[
                    target_local
                ],
                "passage_ids": [
                    str(x)
                    for x in raw_relationship.get(
                        "passage_ids",
                        [],
                    )
                ],
                "evidence_text": str(
                    raw_relationship.get(
                        "evidence_text",
                        "",
                    )
                ).strip()[:1200],
                "evidence_class": (
                    raw_relationship.get(
                        "evidence_class",
                        "NORMALISED",
                    )
                ),
                "batch": batch_index,
            }

            relationship_payloads.append(
                payload
            )

            candidate_relationship_rows.append(
                Row(
                    analysis_id=analysis_id,
                    candidate_relationship_id=relationship_id,
                    extraction_batch=batch_index,
                    source_candidate_id=payload[
                        "source_candidate_id"
                    ],
                    relationship=payload[
                        "relationship"
                    ],
                    target_candidate_id=payload[
                        "target_candidate_id"
                    ],
                    passage_ids=payload[
                        "passage_ids"
                    ],
                    evidence_text=payload[
                        "evidence_text"
                    ],
                    evidence_class=payload[
                        "evidence_class"
                    ],
                    model_service=model_service,
                    analysis_version=ANALYSIS_VERSION,
                    created_at=created_at,
                )
            )

        update_analysis(
            status="ANALYSING",
            stage="CANDIDATE_EXTRACTION",
            batches_total=len(batches),
            batches_processed=batch_index,
        )

    if candidate_rows and not comparison_mode:
        candidate_df = spark.createDataFrame(
            candidate_rows,
            schema=spark.table(
                CANDIDATE_TABLE
            ).schema,
        )
        candidate_df.write.mode(
            "append"
        ).saveAsTable(
            CANDIDATE_TABLE
        )

    if candidate_relationship_rows and not comparison_mode:
        relationship_df = spark.createDataFrame(
            candidate_relationship_rows,
            schema=spark.table(
                CANDIDATE_REL_TABLE
            ).schema,
        )
        relationship_df.write.mode(
            "append"
        ).saveAsTable(
            CANDIDATE_REL_TABLE
        )

    print("Candidates:", len(candidate_payloads))
    print(
        "Candidate relationships:",
        len(relationship_payloads),
    )

except Exception as exc:
    update_analysis(
        status="FAILED",
        stage="CANDIDATE_EXTRACTION_FAILED",
        error_message=f"{type(exc).__name__}: {exc}",
    )
    driver.close()
    raise

# COMMAND ----------

RESOLUTION_SYSTEM_PROMPT = """
You are the cross-document resolution component for a maritime investigation
knowledge graph.

The input contains candidate concepts and candidate relationships that were
already extracted from source passages.

Your job is to:
1. merge candidates that clearly refer to the same real concept/event/factor;
2. retain genuinely distinct concepts separately;
3. consolidate candidate relationships;
4. produce a concise analysis summary in the requested output language.

Critical rules:
- Do NOT create a causal/contributory relationship that is not already present
  in the supplied candidate_relationships.
- Do NOT convert FOLLOWED_BY into RESULTED_IN or CONTRIBUTED_TO.
- Do NOT invent facts from outside the supplied candidates.
- Preserve all supporting passage_ids.
- Conflicting source claims must be listed in source_conflicts instead of
  silently resolved.
- Node kinds must remain within the supplied controlled node-kind vocabulary.
- Relationship labels must remain within the supplied controlled relationship
  vocabulary.
- Protect personal/confidential information in the resolved graph and summary.
- Do not reproduce personal names or other unnecessary personal identifiers.
- Represent people by functional role wherever possible.
- Do not introduce identifying details that were not required for the
  analytical purpose.
- Return JSON only.

Required JSON shape:
{
  "nodes": [
    {
      "resolution_id": "n1",
      "kind": "Event",
      "label": "canonical label",
      "description": "concise evidence-grounded description",
      "member_candidate_ids": ["b001_c1"],
      "passage_ids": ["passage_..."]
    }
  ],
  "relationships": [
    {
      "source_resolution_id": "n1",
      "relationship": "RESULTED_IN",
      "target_resolution_id": "n2",
      "supporting_candidate_relationship_ids": ["b001_r1"],
      "passage_ids": ["passage_..."],
      "evidence_class": "DIRECT"
    }
  ],
  "summary": {
    "overview": "concise overall description",
    "key_findings": ["..."],
    "uncertainties": ["..."],
    "source_conflicts": ["..."]
  }
}
"""

try:
    update_analysis(
        status="ANALYSING",
        stage="RESOLVING",
        batches_total=len(batches),
        batches_processed=len(batches),
    )

    resolution_input = {
        "analysis_title": analysis[
            "analysis_title"
        ],
        "analysis_objective": analysis.get(
            "analysis_objective"
        ),
        "output_language": analysis.get(
            "output_language"
        ) or "English",
        "candidates": candidate_payloads,
        "candidate_relationships": relationship_payloads,
    }

    resolution = query_model_json(
        system_prompt=RESOLUTION_SYSTEM_PROMPT,
        user_prompt=(
            "Resolve the following evidence-grounded candidate set. "
            "Return the summary in "
            f"{resolution_input['output_language']}.\n\n"
            + json.dumps(
                resolution_input,
                ensure_ascii=False,
            )
        ),
        max_tokens=7000,
    )

except Exception as exc:
    update_analysis(
        status="FAILED",
        stage="RESOLUTION_FAILED",
        error_message=f"{type(exc).__name__}: {exc}",
    )
    driver.close()
    raise

# COMMAND ----------

candidate_by_id = {
    item["candidate_id"]: item
    for item in candidate_payloads
}

candidate_relationship_by_id = {
    item["candidate_relationship_id"]: item
    for item in relationship_payloads
}

resolved_nodes = []
resolution_to_node_id = {}

for node in resolution.get(
    "nodes",
    [],
):
    kind = node.get("kind")

    if kind not in ALLOWED_NODE_KINDS:
        continue

    resolution_id = str(
        node.get("resolution_id", "")
    )

    label = str(
        node.get("label", "")
    ).strip()

    if not resolution_id or not label:
        continue

    raw_id = (
        f"{analysis_id}|{model_run_key}|{kind}|"
        f"{label.casefold()}"
    )

    node_id = (
        "analysis_node_"
        + hashlib.sha256(
            raw_id.encode("utf-8")
        ).hexdigest()[:24]
    )

    member_ids = [
        str(x)
        for x in node.get(
            "member_candidate_ids",
            [],
        )
        if str(x) in candidate_by_id
    ]

    passage_ids = set(
        str(x)
        for x in node.get(
            "passage_ids",
            [],
        )
    )

    for member_id in member_ids:
        passage_ids.update(
            candidate_by_id[
                member_id
            ].get(
                "passage_ids",
                [],
            )
        )

    payload = {
        "resolution_id": resolution_id,
        "node_id": node_id,
        "kind": kind,
        "label": label,
        "description": str(
            node.get(
                "description",
                "",
            )
        ).strip(),
        "member_candidate_ids": member_ids,
        "passage_ids": sorted(
            passage_ids
        ),
    }

    resolved_nodes.append(payload)
    resolution_to_node_id[
        resolution_id
    ] = node_id


resolved_relationships = []

for relationship in resolution.get(
    "relationships",
    [],
):
    rel_type = relationship.get(
        "relationship"
    )

    if rel_type not in ALLOWED_RELATIONSHIPS:
        continue

    source_resolution_id = str(
        relationship.get(
            "source_resolution_id",
            "",
        )
    )
    target_resolution_id = str(
        relationship.get(
            "target_resolution_id",
            "",
        )
    )

    if (
        source_resolution_id
        not in resolution_to_node_id
        or target_resolution_id
        not in resolution_to_node_id
    ):
        continue

    support_ids = [
        str(x)
        for x in relationship.get(
            "supporting_candidate_relationship_ids",
            [],
        )
        if str(x)
        in candidate_relationship_by_id
    ]

    if not support_ids:
        continue

    support_types = {
        candidate_relationship_by_id[
            support_id
        ]["relationship"]
        for support_id in support_ids
    }

    if rel_type not in support_types:
        continue

    passage_ids = set(
        str(x)
        for x in relationship.get(
            "passage_ids",
            [],
        )
    )

    evidence_classes = []

    for support_id in support_ids:
        support = candidate_relationship_by_id[
            support_id
        ]
        passage_ids.update(
            support.get(
                "passage_ids",
                [],
            )
        )
        evidence_classes.append(
            support.get(
                "evidence_class",
                "NORMALISED",
            )
        )

    evidence_class = (
        "DIRECT"
        if "DIRECT" in evidence_classes
        else (
            evidence_classes[0]
            if evidence_classes
            else "NORMALISED"
        )
    )

    source_node_id = resolution_to_node_id[
        source_resolution_id
    ]
    target_node_id = resolution_to_node_id[
        target_resolution_id
    ]

    edge_raw = (
        f"{analysis_id}|{source_node_id}|"
        f"{rel_type}|{target_node_id}"
    )

    edge_id = (
        "analysis_edge_"
        + hashlib.sha256(
            edge_raw.encode("utf-8")
        ).hexdigest()[:24]
    )

    resolved_relationships.append(
        {
            "edge_id": edge_id,
            "source_node_id": source_node_id,
            "relationship": rel_type,
            "target_node_id": target_node_id,
            "support_ids": support_ids,
            "passage_ids": sorted(
                passage_ids
            ),
            "evidence_class": evidence_class,
        }
    )

print("Resolved nodes:", len(resolved_nodes))
print(
    "Resolved relationships:",
    len(resolved_relationships),
)

# COMMAND ----------

# Privacy validation runs before graph publication. It does not alter source
# evidence; it only minimises personal identifiers in analytical derivatives.

EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"
)
PERSONAL_ID_RE = re.compile(
    r"\b(?:passport|national\s+id|identity\s+card|id\s+number)\s*[:#-]?\s*[A-Z0-9-]{4,}\b",
    re.IGNORECASE,
)


def redact_direct_identifiers(value):
    text = str(value or "")
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = PERSONAL_ID_RE.sub("[REDACTED_PERSONAL_ID]", text)
    return text


update_analysis(
    status="ANALYSING",
    stage="PRIVACY_VALIDATION",
    batches_total=len(batches),
    batches_processed=len(batches),
)

privacy_redaction_count = 0

for node in resolved_nodes:
    before_label = node["label"]
    before_description = node["description"]
    node["label"] = redact_direct_identifiers(
        node["label"]
    )
    node["description"] = redact_direct_identifiers(
        node["description"]
    )

    privacy_redaction_count += int(
        node["label"] != before_label
    )
    privacy_redaction_count += int(
        node["description"] != before_description
    )

# COMMAND ----------

summary = resolution.get(
    "summary",
    {},
)

overview_raw = str(
    summary.get(
        "overview",
        "",
    )
).strip()
overview = redact_direct_identifiers(
    overview_raw
)
privacy_redaction_count += int(
    overview != overview_raw
)

key_findings_raw = [
    str(x).strip()
    for x in summary.get(
        "key_findings",
        [],
    )
    if str(x).strip()
]
key_findings = [
    redact_direct_identifiers(x)
    for x in key_findings_raw
]
privacy_redaction_count += sum(
    1
    for before, after in zip(
        key_findings_raw,
        key_findings,
    )
    if before != after
)

uncertainties_raw = [
    str(x).strip()
    for x in summary.get(
        "uncertainties",
        [],
    )
    if str(x).strip()
]
uncertainties = [
    redact_direct_identifiers(x)
    for x in uncertainties_raw
]
privacy_redaction_count += sum(
    1
    for before, after in zip(
        uncertainties_raw,
        uncertainties,
    )
    if before != after
)

source_conflicts_raw = [
    str(x).strip()
    for x in summary.get(
        "source_conflicts",
        [],
    )
    if str(x).strip()
]
source_conflicts = [
    redact_direct_identifiers(x)
    for x in source_conflicts_raw
]
privacy_redaction_count += sum(
    1
    for before, after in zip(
        source_conflicts_raw,
        source_conflicts,
    )
    if before != after
)

privacy_validation_status = (
    "PASSED_WITH_AUTOMATIC_REDACTION"
    if privacy_redaction_count > 0
    else "PASSED"
)

print(
    "Privacy validation:",
    privacy_validation_status,
    "| redactions:",
    privacy_redaction_count,
)

if not comparison_mode:
    spark.sql(
        f"""
        DELETE FROM {SUMMARY_TABLE}
        WHERE analysis_id = '{analysis_id}'
        """
    )

summary_row = Row(
    analysis_id=analysis_id,
    model_service=model_service,
    analysis_version=ANALYSIS_VERSION,
    output_language=(
        analysis.get(
            "output_language"
        )
        or "English"
    ),
    overview=overview,
    key_findings_json=json.dumps(
        key_findings,
        ensure_ascii=False,
    ),
    uncertainties_json=json.dumps(
        uncertainties,
        ensure_ascii=False,
    ),
    source_conflicts_json=json.dumps(
        source_conflicts,
        ensure_ascii=False,
    ),
    created_at=datetime.now(
        timezone.utc
    ),
)

if not comparison_mode:
    spark.createDataFrame(
        [summary_row],
        schema=spark.table(
            SUMMARY_TABLE
        ).schema,
    ).write.mode("append").saveAsTable(
        SUMMARY_TABLE
    )

# COMMAND ----------

try:
    update_analysis(
        status="ANALYSING",
        stage="BUILDING_GRAPH",
        batches_total=len(batches),
        batches_processed=len(batches),
    )

    with driver.session() as session:
        session.run(
            """
            MATCH (n:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id
            })
            DETACH DELETE n
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
        ).consume()

        for node in resolved_nodes:
            session.run(
                """
                MATCH (a:AnalysisGroup {
                    analysis_id: $analysis_id
                })
                CREATE (n:KGNode {
                    analysis_id: $analysis_id,
                    model_run_id: $model_run_id,
                    node_id: $node_id,
                    node_kind: $node_kind,
                    label: $label,
                    description: $description,
                    evidence_passage_ids: $passage_ids,
                    assistant_review_status: 'ASSISTANT_CANDIDATE',
                    privacy_output_mode: $privacy_output_mode,
                    analysis_version: $analysis_version,
                    model_service: $model_service,
                    created_at: datetime()
                })
                CREATE (a)-[:HAS_GRAPH_NODE]->(n)
                """,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
                node_id=node["node_id"],
                node_kind=node["kind"],
                label=node["label"],
                description=node["description"],
                passage_ids=node["passage_ids"],
                privacy_output_mode=PRIVACY_OUTPUT_MODE,
                analysis_version=ANALYSIS_VERSION,
                model_service=model_service,
            ).consume()

        for relationship in resolved_relationships:
            rel_type = relationship[
                "relationship"
            ]

            if rel_type not in ALLOWED_RELATIONSHIPS:
                continue

            cypher = f"""
            MATCH (source:KGNode {{
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $source_node_id
            }})
            MATCH (target:KGNode {{
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $target_node_id
            }})
            CREATE (source)-[r:{rel_type} {{
                edge_id: $edge_id,
                edge_class: 'REPORT_DERIVED',
                evidence_status: 'ASSISTANT_CANDIDATE',
                evidence_class: $evidence_class,
                evidence_passage_ids: $passage_ids,
                supporting_candidate_relationship_ids: $support_ids,
                analysis_version: $analysis_version,
                model_service: $model_service,
                created_at: datetime()
            }}]->(target)
            """

            session.run(
                cypher,
                analysis_id=analysis_id,
                model_run_id=model_run_id,
                source_node_id=relationship[
                    "source_node_id"
                ],
                target_node_id=relationship[
                    "target_node_id"
                ],
                edge_id=relationship[
                    "edge_id"
                ],
                evidence_class=relationship[
                    "evidence_class"
                ],
                passage_ids=relationship[
                    "passage_ids"
                ],
                support_ids=relationship[
                    "support_ids"
                ],
                analysis_version=ANALYSIS_VERSION,
                model_service=model_service,
            ).consume()

        model_run_duration_seconds = (
            time.perf_counter()
            - model_run_started
        )

        session.run(
            """
            MATCH (m:ModelRun {model_run_id: $model_run_id})
            SET
                m.status = 'COMPLETED',
                m.overview = $overview,
                m.key_findings = $key_findings,
                m.uncertainties = $uncertainties,
                m.source_conflicts = $source_conflicts,
                m.graph_node_count = $graph_node_count,
                m.graph_relationship_count = $graph_relationship_count,
                m.analysis_version = $analysis_version,
                m.privacy_output_mode = $privacy_output_mode,
                m.privacy_validation_status = $privacy_validation_status,
                m.privacy_redaction_count = $privacy_redaction_count,
                m.duration_seconds = $duration_seconds,
                m.prompt_tokens = $prompt_tokens,
                m.completion_tokens = $completion_tokens,
                m.total_tokens = $total_tokens,
                m.completed_at = datetime(),
                m.updated_at = datetime()
            """,
            model_run_id=model_run_id,
            overview=overview,
            key_findings=key_findings,
            uncertainties=uncertainties,
            source_conflicts=source_conflicts,
            graph_node_count=len(resolved_nodes),
            graph_relationship_count=len(resolved_relationships),
            analysis_version=ANALYSIS_VERSION,
            privacy_output_mode=PRIVACY_OUTPUT_MODE,
            privacy_validation_status=privacy_validation_status,
            privacy_redaction_count=privacy_redaction_count,
            duration_seconds=model_run_duration_seconds,
            prompt_tokens=model_usage_totals["prompt_tokens"],
            completion_tokens=model_usage_totals["completion_tokens"],
            total_tokens=model_usage_totals["total_tokens"],
        ).consume()

        if not comparison_mode:
            session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            SET
                a.status = 'COMPLETED',
                a.processing_stage = 'COMPLETED',
                a.analysis_summary = $overview,
                a.key_findings = $key_findings,
                a.uncertainties = $uncertainties,
                a.source_conflicts = $source_conflicts,
                a.graph_node_count = $graph_node_count,
                a.graph_relationship_count = $graph_relationship_count,
                a.analysis_version = $analysis_version,
                a.model_service = $model_service,
                a.privacy_output_mode = $privacy_output_mode,
                a.privacy_validation_status = $privacy_validation_status,
                a.privacy_redaction_count = $privacy_redaction_count,
                a.completed_at = datetime(),
                a.processing_updated_at = datetime(),
                a.processing_error = NULL
            """,
            analysis_id=analysis_id,
            overview=overview,
            key_findings=key_findings,
            uncertainties=uncertainties,
            source_conflicts=source_conflicts,
            graph_node_count=len(
                resolved_nodes
            ),
            graph_relationship_count=len(
                resolved_relationships
            ),
            privacy_output_mode=PRIVACY_OUTPUT_MODE,
            privacy_validation_status=privacy_validation_status,
            privacy_redaction_count=privacy_redaction_count,
            analysis_version=ANALYSIS_VERSION,
            model_service=model_service,
        ).consume()

    print("")
    print("ANALYSIS COMPLETE")
    print("status: COMPLETED")
    print("nodes:", len(resolved_nodes))
    print(
        "relationships:",
        len(resolved_relationships),
    )
    print("")
    print("OVERVIEW")
    print(overview)

except Exception as exc:
    update_analysis(
        status="FAILED",
        stage="GRAPH_BUILD_FAILED",
        error_message=f"{type(exc).__name__}: {exc}",
    )
    raise

finally:
    driver.close()

# COMMAND ----------

print("")
print("KEY FINDINGS")
for item in key_findings:
    print(" -", item)

print("")
print("UNCERTAINTIES")
for item in uncertainties:
    print(" -", item)

print("")
print("SOURCE CONFLICTS")
for item in source_conflicts:
    print(" -", item)

print("")
print(
    "Open the App > Analyses > Refresh status "
    "to inspect the completed result."
)
