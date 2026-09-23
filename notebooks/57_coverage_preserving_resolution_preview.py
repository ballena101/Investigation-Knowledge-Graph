# Databricks notebook source
# MAGIC %md
# MAGIC # 57 — Coverage-preserving resolution preview
# MAGIC
# MAGIC Read-only with respect to Neo4j. Builds a coverage-preserving preview from
# MAGIC persisted notebook-16 candidates. Every tracked candidate must be assigned
# MAGIC to exactly one resolved concept. Clear duplicates may be merged, but no
# MAGIC candidate may disappear silently.

# COMMAND ----------

dbutils.widgets.text("analysis_id", "", "Analysis ID")
dbutils.widgets.text(
    "model_service",
    "system.ai.meta-llama-3-3-70b-instruct",
    "Databricks model service",
)

# COMMAND ----------

# MAGIC %pip install databricks-sdk==0.139.0

# COMMAND ----------

import hashlib
import json
import re
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient

analysis_id = dbutils.widgets.get("analysis_id").strip()
model_service = dbutils.widgets.get("model_service").strip()

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError("Enter a valid analysis_id in the form analysis_<32 hex>.")

CANDIDATE_TABLE = "bdw_analysis_prod.kg_poc.analysis_candidate"
PREVIEW_TABLE = "bdw_analysis_prod.kg_poc.coverage_resolution_preview"
TRACKED_KINDS = {
    "Event",
    "ContributingFactor",
    "Finding",
    "SafetyIssue",
    "Recommendation",
}
RESOLUTION_VERSION = "COVERAGE_PRESERVING_RESOLUTION_V0.1"

w = WorkspaceClient()

# COMMAND ----------

candidates = [
    row.asDict(recursive=True)
    for row in (
        spark.table(CANDIDATE_TABLE)
        .filter(f"analysis_id = '{analysis_id}'")
        .filter("node_kind IN ('Event','ContributingFactor','Finding','SafetyIssue','Recommendation')")
        .select(
            "candidate_id",
            "node_kind",
            "label",
            "description",
            "passage_ids",
            "evidence_text",
            "evidence_class",
            "extraction_batch",
        )
        .orderBy("node_kind", "extraction_batch", "candidate_id")
        .collect()
    )
]

if not candidates:
    raise ValueError("No tracked candidates found for this analysis.")

print("Tracked candidates:", len(candidates))

# COMMAND ----------

SYSTEM_PROMPT = """
You are a coverage-preserving resolution component for a maritime safety
investigation knowledge graph.

Input candidates were already extracted from source evidence. Your task is only
to resolve duplicates and canonicalise labels.

Hard rules:
1. EVERY input candidate_id must appear in exactly one member_candidate_ids list.
2. Never omit a candidate because it seems unimportant.
3. Merge candidates only when they clearly refer to the same underlying concept.
4. Keep distinct concepts separate even when related.
5. Never change a candidate's node kind during resolution.
6. Do not invent new facts or concepts.
7. Preserve the union of passage_ids from all merged members.
8. Prefer concise canonical labels, but retain the full analytical meaning in the description.
9. Return JSON only.

Required JSON:
{
  "nodes": [
    {
      "resolution_id": "n1",
      "kind": "ContributingFactor",
      "label": "canonical label",
      "description": "concise evidence-grounded description",
      "member_candidate_ids": ["b001_c1"],
      "passage_ids": ["passage_..."]
    }
  ]
}
"""

payload = {
    "analysis_id": analysis_id,
    "candidates": candidates,
}

request = {
    "model": model_service,
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Resolve this candidate ledger while preserving complete candidate coverage.\n\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
        },
    ],
    "temperature": 0.0,
    "max_tokens": 8000,
}

import urllib.request

req = urllib.request.Request(
    w.config.host.rstrip("/") + "/ai-gateway/mlflow/v1/chat/completions",
    data=json.dumps(request).encode("utf-8"),
    headers={**w.config.authenticate(), "Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=600) as response:
    model_payload = json.loads(response.read().decode("utf-8"))

text = model_payload["choices"][0]["message"]["content"]
if isinstance(text, list):
    text = "\n".join(
        str(item.get("text") or "")
        for item in text
        if isinstance(item, dict)
    )
text = str(text).strip()
if text.startswith("```"):
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
resolution = json.loads(text)

# COMMAND ----------

candidate_by_id = {row["candidate_id"]: row for row in candidates}
expected_ids = set(candidate_by_id)
seen = {}
errors = []
preview_rows = []

for node in resolution.get("nodes", []):
    resolution_id = str(node.get("resolution_id") or "").strip()
    kind = str(node.get("kind") or "").strip()
    label = str(node.get("label") or "").strip()
    description = str(node.get("description") or "").strip()
    members = [str(x) for x in node.get("member_candidate_ids", [])]

    if not resolution_id or not label or kind not in TRACKED_KINDS:
        errors.append(f"Invalid resolved node: {node}")
        continue

    if not members:
        errors.append(f"{resolution_id}: no member_candidate_ids")
        continue

    member_kinds = {
        candidate_by_id[mid]["node_kind"]
        for mid in members
        if mid in candidate_by_id
    }
    unknown_members = [mid for mid in members if mid not in candidate_by_id]
    if unknown_members:
        errors.append(f"{resolution_id}: unknown candidate ids {unknown_members}")
        continue
    if member_kinds != {kind}:
        errors.append(
            f"{resolution_id}: node kind {kind} does not match member kinds {sorted(member_kinds)}"
        )

    for mid in members:
        seen.setdefault(mid, []).append(resolution_id)

    passage_ids = sorted({
        pid
        for mid in members
        for pid in (candidate_by_id[mid].get("passage_ids") or [])
    })

    node_id = "preview_node_" + hashlib.sha256(
        f"{analysis_id}|{kind}|{label}|{'|'.join(sorted(members))}".encode("utf-8")
    ).hexdigest()[:24]

    preview_rows.append({
        "analysis_id": analysis_id,
        "resolution_version": RESOLUTION_VERSION,
        "resolution_id": resolution_id,
        "preview_node_id": node_id,
        "node_kind": kind,
        "label": label,
        "description": description,
        "member_candidate_ids": sorted(members),
        "passage_ids": passage_ids,
        "member_count": len(members),
        "created_at": datetime.now(timezone.utc),
    })

missing = sorted(expected_ids - set(seen))
duplicated = sorted(mid for mid, owners in seen.items() if len(owners) != 1)

if missing:
    errors.append("Unmapped candidate IDs: " + ", ".join(missing))
if duplicated:
    errors.append(
        "Candidate IDs mapped more than once: "
        + ", ".join(f"{mid} -> {seen[mid]}" for mid in duplicated)
    )

print("Resolved preview nodes:", len(preview_rows))
print("Mapped candidates:", len(seen), "/", len(expected_ids))
print("Missing candidate mappings:", len(missing))
print("Duplicate candidate mappings:", len(duplicated))

if errors:
    print("\nVALIDATION ERRORS")
    for error in errors:
        print(" -", error)
    raise RuntimeError(
        "Coverage-preserving resolution validation failed. Nothing was published to Neo4j."
    )

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {PREVIEW_TABLE} (
    analysis_id STRING NOT NULL,
    resolution_version STRING NOT NULL,
    resolution_id STRING NOT NULL,
    preview_node_id STRING NOT NULL,
    node_kind STRING NOT NULL,
    label STRING NOT NULL,
    description STRING,
    member_candidate_ids ARRAY<STRING>,
    passage_ids ARRAY<STRING>,
    member_count INT,
    created_at TIMESTAMP NOT NULL
)
USING DELTA
""")

spark.sql(
    f"DELETE FROM {PREVIEW_TABLE} WHERE analysis_id = '{analysis_id}' "
    f"AND resolution_version = '{RESOLUTION_VERSION}'"
)

preview_df = spark.createDataFrame(
    preview_rows,
    schema=spark.table(PREVIEW_TABLE).schema,
)
preview_df.write.mode("append").saveAsTable(PREVIEW_TABLE)

# COMMAND ----------

summary_df = (
    preview_df
    .groupBy("node_kind")
    .count()
    .orderBy("node_kind")
)

display(summary_df)
display(
    preview_df.select(
        "node_kind",
        "label",
        "member_count",
        "member_candidate_ids",
        "passage_ids",
    ).orderBy("node_kind", "label")
)

print("")
print("PASS — COVERAGE-PRESERVING RESOLUTION PREVIEW COMPLETED")
print("Every tracked candidate was mapped exactly once.")
print("Neo4j graph was NOT modified.")
