# Databricks notebook source
# MAGIC %md
# MAGIC # 58 — Coverage-preserving relationship preview
# MAGIC
# MAGIC Read-only with respect to Neo4j. Re-maps persisted notebook-16 candidate
# MAGIC relationships onto the coverage-preserving node preview created by notebook 57.
# MAGIC Every candidate relationship must resolve to one source preview node and one
# MAGIC target preview node. Duplicate resolved relationships may be consolidated,
# MAGIC but no supported candidate relationship may disappear silently.

# COMMAND ----------

dbutils.widgets.text("analysis_id", "", "Analysis ID")

# COMMAND ----------

import hashlib
import re
from datetime import datetime, timezone

from pyspark.sql import Row

analysis_id = dbutils.widgets.get("analysis_id").strip()

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError("Enter a valid analysis_id in the form analysis_<32 hex>.")

NODE_PREVIEW_TABLE = "bdw_analysis_prod.kg_poc.coverage_resolution_preview"
CANDIDATE_REL_TABLE = "bdw_analysis_prod.kg_poc.analysis_candidate_relationship"
REL_PREVIEW_TABLE = "bdw_analysis_prod.kg_poc.coverage_relationship_preview"
RESOLUTION_VERSION = "COVERAGE_PRESERVING_RESOLUTION_V0.1"
RELATIONSHIP_PREVIEW_VERSION = "COVERAGE_PRESERVING_RELATIONSHIP_V0.1"

ALLOWED_RELATIONSHIPS = {
    "FOLLOWED_BY",
    "CONTRIBUTED_TO",
    "RESULTED_IN",
    "AFFECTED",
    "SUPPORTS",
    "INVOLVED_IN",
}

# COMMAND ----------

node_rows = [
    row.asDict(recursive=True)
    for row in (
        spark.table(NODE_PREVIEW_TABLE)
        .filter(f"analysis_id = '{analysis_id}'")
        .filter(f"resolution_version = '{RESOLUTION_VERSION}'")
        .select(
            "preview_node_id",
            "node_kind",
            "label",
            "member_candidate_ids",
            "passage_ids",
        )
        .collect()
    )
]

if not node_rows:
    raise ValueError(
        "No coverage-preserving node preview exists for this analysis. Run notebook 57 first."
    )

candidate_to_node = {}
duplicate_candidate_owners = {}

for node in node_rows:
    for candidate_id in node.get("member_candidate_ids") or []:
        if candidate_id in candidate_to_node:
            duplicate_candidate_owners.setdefault(candidate_id, []).extend(
                [candidate_to_node[candidate_id], node["preview_node_id"]]
            )
        else:
            candidate_to_node[candidate_id] = node["preview_node_id"]

if duplicate_candidate_owners:
    raise RuntimeError(
        "Candidate-to-node mapping is not one-to-one. Re-run/fix notebook 57 before continuing. "
        + str(duplicate_candidate_owners)
    )

node_by_id = {row["preview_node_id"]: row for row in node_rows}

print("Preview nodes:", len(node_rows))
print("Mapped candidate IDs:", len(candidate_to_node))

# COMMAND ----------

relationship_rows = [
    row.asDict(recursive=True)
    for row in (
        spark.table(CANDIDATE_REL_TABLE)
        .filter(f"analysis_id = '{analysis_id}'")
        .select(
            "candidate_relationship_id",
            "source_candidate_id",
            "relationship",
            "target_candidate_id",
            "passage_ids",
            "evidence_text",
            "evidence_class",
            "extraction_batch",
        )
        .orderBy("extraction_batch", "candidate_relationship_id")
        .collect()
    )
]

if not relationship_rows:
    raise ValueError("No candidate relationships found for this analysis.")

print("Candidate relationships:", len(relationship_rows))

# COMMAND ----------

errors = []
resolved_groups = {}

for rel in relationship_rows:
    rel_id = str(rel.get("candidate_relationship_id") or "").strip()
    rel_type = str(rel.get("relationship") or "").strip()
    source_candidate_id = str(rel.get("source_candidate_id") or "").strip()
    target_candidate_id = str(rel.get("target_candidate_id") or "").strip()

    if not rel_id:
        errors.append("Candidate relationship without ID")
        continue
    if rel_type not in ALLOWED_RELATIONSHIPS:
        errors.append(f"{rel_id}: unsupported relationship {rel_type}")
        continue
    if source_candidate_id not in candidate_to_node:
        errors.append(f"{rel_id}: unmapped source candidate {source_candidate_id}")
        continue
    if target_candidate_id not in candidate_to_node:
        errors.append(f"{rel_id}: unmapped target candidate {target_candidate_id}")
        continue

    source_node_id = candidate_to_node[source_candidate_id]
    target_node_id = candidate_to_node[target_candidate_id]

    # Preserve self-relations for review rather than silently dropping them.
    key = (source_node_id, rel_type, target_node_id)
    bucket = resolved_groups.setdefault(
        key,
        {
            "candidate_relationship_ids": [],
            "passage_ids": set(),
            "evidence_texts": [],
            "evidence_classes": set(),
        },
    )

    bucket["candidate_relationship_ids"].append(rel_id)
    bucket["passage_ids"].update(rel.get("passage_ids") or [])
    evidence_text = str(rel.get("evidence_text") or "").strip()
    if evidence_text:
        bucket["evidence_texts"].append(evidence_text)
    evidence_class = str(rel.get("evidence_class") or "NORMALISED").strip()
    if evidence_class:
        bucket["evidence_classes"].add(evidence_class)

if errors:
    print("\nVALIDATION ERRORS")
    for error in errors:
        print(" -", error)
    raise RuntimeError(
        "Coverage-preserving relationship validation failed. Nothing was published to Neo4j."
    )

# COMMAND ----------

preview_rows = []
created_at = datetime.now(timezone.utc)

for (source_node_id, rel_type, target_node_id), payload in sorted(
    resolved_groups.items(),
    key=lambda item: item[0],
):
    candidate_relationship_ids = sorted(set(payload["candidate_relationship_ids"]))
    passage_ids = sorted(set(payload["passage_ids"]))
    evidence_texts = list(dict.fromkeys(payload["evidence_texts"]))
    evidence_classes = sorted(payload["evidence_classes"])

    raw = (
        analysis_id
        + "|"
        + source_node_id
        + "|"
        + rel_type
        + "|"
        + target_node_id
        + "|"
        + "|".join(candidate_relationship_ids)
    )
    preview_edge_id = "preview_edge_" + hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:24]

    preview_rows.append(
        Row(
            analysis_id=analysis_id,
            relationship_preview_version=RELATIONSHIP_PREVIEW_VERSION,
            preview_edge_id=preview_edge_id,
            source_preview_node_id=source_node_id,
            source_node_kind=node_by_id[source_node_id]["node_kind"],
            source_label=node_by_id[source_node_id]["label"],
            relationship=rel_type,
            target_preview_node_id=target_node_id,
            target_node_kind=node_by_id[target_node_id]["node_kind"],
            target_label=node_by_id[target_node_id]["label"],
            candidate_relationship_ids=candidate_relationship_ids,
            passage_ids=passage_ids,
            evidence_texts=evidence_texts,
            evidence_classes=evidence_classes,
            candidate_relationship_count=len(candidate_relationship_ids),
            self_relation=(source_node_id == target_node_id),
            created_at=created_at,
        )
    )

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {REL_PREVIEW_TABLE} (
    analysis_id STRING NOT NULL,
    relationship_preview_version STRING NOT NULL,
    preview_edge_id STRING NOT NULL,
    source_preview_node_id STRING NOT NULL,
    source_node_kind STRING,
    source_label STRING,
    relationship STRING NOT NULL,
    target_preview_node_id STRING NOT NULL,
    target_node_kind STRING,
    target_label STRING,
    candidate_relationship_ids ARRAY<STRING>,
    passage_ids ARRAY<STRING>,
    evidence_texts ARRAY<STRING>,
    evidence_classes ARRAY<STRING>,
    candidate_relationship_count INT,
    self_relation BOOLEAN,
    created_at TIMESTAMP NOT NULL
)
USING DELTA
""")

spark.sql(
    f"DELETE FROM {REL_PREVIEW_TABLE} "
    f"WHERE analysis_id = '{analysis_id}' "
    f"AND relationship_preview_version = '{RELATIONSHIP_PREVIEW_VERSION}'"
)

preview_df = spark.createDataFrame(
    preview_rows,
    schema=spark.table(REL_PREVIEW_TABLE).schema,
)
preview_df.write.mode("append").saveAsTable(REL_PREVIEW_TABLE)

# COMMAND ----------

mapped_candidate_relationship_ids = {
    rel_id
    for row in preview_rows
    for rel_id in row.candidate_relationship_ids
}
expected_relationship_ids = {
    str(row["candidate_relationship_id"])
    for row in relationship_rows
}

missing_relationship_ids = sorted(
    expected_relationship_ids - mapped_candidate_relationship_ids
)

print("Resolved preview relationships:", len(preview_rows))
print(
    "Mapped candidate relationships:",
    len(mapped_candidate_relationship_ids),
    "/",
    len(expected_relationship_ids),
)
print(
    "Self-relations after node consolidation:",
    sum(1 for row in preview_rows if row.self_relation),
)

if missing_relationship_ids:
    raise RuntimeError(
        "Candidate relationships were lost during preview mapping: "
        + ", ".join(missing_relationship_ids)
    )

# COMMAND ----------

display(
    preview_df.select(
        "source_node_kind",
        "source_label",
        "relationship",
        "target_node_kind",
        "target_label",
        "candidate_relationship_count",
        "self_relation",
        "candidate_relationship_ids",
        "passage_ids",
    ).orderBy(
        "source_node_kind",
        "source_label",
        "relationship",
        "target_label",
    )
)

print("")
print("PASS — COVERAGE-PRESERVING RELATIONSHIP PREVIEW COMPLETED")
print("Every candidate relationship was mapped to resolved preview nodes.")
print("Neo4j graph was NOT modified.")
