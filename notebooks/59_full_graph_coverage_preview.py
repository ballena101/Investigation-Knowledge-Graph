# Databricks notebook source
# MAGIC %md
# MAGIC # 59 — Full graph coverage preview
# MAGIC
# MAGIC Extends the coverage-preserving analytical inventory from notebook 57 with
# MAGIC supporting graph-only candidate kinds required by candidate relationships.
# MAGIC Read-only with respect to Neo4j.
# MAGIC
# MAGIC Design:
# MAGIC - analytical inventory kinds (Event, ContributingFactor, Finding,
# MAGIC   SafetyIssue, Recommendation) come from the coverage-preserving preview;
# MAGIC - supporting graph kinds (Actor, Vessel, System, Claim) are carried through
# MAGIC   deterministically as passthrough nodes when referenced by candidate
# MAGIC   relationships;
# MAGIC - every candidate relationship must resolve to a source and target node;
# MAGIC - no relationship is silently discarded.

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

CANDIDATE_TABLE = "bdw_analysis_prod.kg_poc.analysis_candidate"
CANDIDATE_REL_TABLE = "bdw_analysis_prod.kg_poc.analysis_candidate_relationship"
NODE_PREVIEW_TABLE = "bdw_analysis_prod.kg_poc.coverage_resolution_preview"
FULL_NODE_PREVIEW_TABLE = "bdw_analysis_prod.kg_poc.full_graph_node_preview"
FULL_REL_PREVIEW_TABLE = "bdw_analysis_prod.kg_poc.full_graph_relationship_preview"

RESOLUTION_VERSION = "COVERAGE_PRESERVING_RESOLUTION_V0.1"
FULL_GRAPH_PREVIEW_VERSION = "FULL_GRAPH_COVERAGE_PREVIEW_V0.1"

INVENTORY_KINDS = {
    "Event",
    "ContributingFactor",
    "Finding",
    "SafetyIssue",
    "Recommendation",
}
SUPPORTING_KINDS = {
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
    "INVOLVED_IN",
}

# COMMAND ----------

preview_nodes = [
    row.asDict(recursive=True)
    for row in (
        spark.table(NODE_PREVIEW_TABLE)
        .filter(f"analysis_id = '{analysis_id}'")
        .filter(f"resolution_version = '{RESOLUTION_VERSION}'")
        .select(
            "preview_node_id",
            "node_kind",
            "label",
            "description",
            "member_candidate_ids",
            "passage_ids",
        )
        .collect()
    )
]

if not preview_nodes:
    raise ValueError("No coverage-preserving node preview exists. Run notebook 57 first.")

all_candidates = {
    row["candidate_id"]: row.asDict(recursive=True)
    for row in (
        spark.table(CANDIDATE_TABLE)
        .filter(f"analysis_id = '{analysis_id}'")
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
        .collect()
    )
}

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

# COMMAND ----------

full_nodes = []
candidate_to_node = {}

for node in preview_nodes:
    full_nodes.append({
        "analysis_id": analysis_id,
        "preview_version": FULL_GRAPH_PREVIEW_VERSION,
        "preview_node_id": node["preview_node_id"],
        "node_kind": node["node_kind"],
        "label": node["label"],
        "description": node.get("description") or "",
        "member_candidate_ids": sorted(node.get("member_candidate_ids") or []),
        "passage_ids": sorted(set(node.get("passage_ids") or [])),
        "inventory_visible": True,
        "passthrough": False,
        "created_at": datetime.now(timezone.utc),
    })
    for candidate_id in node.get("member_candidate_ids") or []:
        if candidate_id in candidate_to_node:
            raise RuntimeError(
                f"Candidate {candidate_id} appears in more than one preview node."
            )
        candidate_to_node[candidate_id] = node["preview_node_id"]

referenced_candidate_ids = {
    str(rel.get("source_candidate_id") or "").strip()
    for rel in relationship_rows
} | {
    str(rel.get("target_candidate_id") or "").strip()
    for rel in relationship_rows
}
referenced_candidate_ids.discard("")

unmapped_referenced_ids = sorted(
    candidate_id
    for candidate_id in referenced_candidate_ids
    if candidate_id not in candidate_to_node
)

passthrough_counts = {}
unknown_unmapped = []

for candidate_id in unmapped_referenced_ids:
    candidate = all_candidates.get(candidate_id)
    if candidate is None:
        unknown_unmapped.append(candidate_id)
        continue

    kind = str(candidate.get("node_kind") or "").strip()
    if kind not in SUPPORTING_KINDS:
        unknown_unmapped.append(candidate_id)
        continue

    label = str(candidate.get("label") or candidate_id).strip()
    raw = f"{analysis_id}|passthrough|{kind}|{candidate_id}|{label}"
    preview_node_id = (
        "preview_support_node_"
        + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    )

    full_nodes.append({
        "analysis_id": analysis_id,
        "preview_version": FULL_GRAPH_PREVIEW_VERSION,
        "preview_node_id": preview_node_id,
        "node_kind": kind,
        "label": label,
        "description": str(candidate.get("description") or "").strip(),
        "member_candidate_ids": [candidate_id],
        "passage_ids": sorted(set(candidate.get("passage_ids") or [])),
        "inventory_visible": False,
        "passthrough": True,
        "created_at": datetime.now(timezone.utc),
    })
    candidate_to_node[candidate_id] = preview_node_id
    passthrough_counts[kind] = passthrough_counts.get(kind, 0) + 1

if unknown_unmapped:
    raise RuntimeError(
        "Referenced candidates remain unmapped and are not supported passthrough kinds: "
        + ", ".join(unknown_unmapped)
    )

print("Inventory preview nodes:", len(preview_nodes))
print("Supporting passthrough nodes:", sum(passthrough_counts.values()))
print("Passthrough by kind:", passthrough_counts)
print("Mapped candidate IDs:", len(candidate_to_node))

# COMMAND ----------

node_by_id = {node["preview_node_id"]: node for node in full_nodes}
resolved_groups = {}
errors = []

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
    raise RuntimeError("Relationship mapping errors: " + " | ".join(errors))

# COMMAND ----------

created_at = datetime.now(timezone.utc)
full_relationships = []

for (source_node_id, rel_type, target_node_id), payload in sorted(
    resolved_groups.items(),
    key=lambda item: item[0],
):
    candidate_relationship_ids = sorted(set(payload["candidate_relationship_ids"]))
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
    preview_edge_id = (
        "preview_full_edge_"
        + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    )

    full_relationships.append({
        "analysis_id": analysis_id,
        "preview_version": FULL_GRAPH_PREVIEW_VERSION,
        "preview_edge_id": preview_edge_id,
        "source_preview_node_id": source_node_id,
        "source_node_kind": node_by_id[source_node_id]["node_kind"],
        "source_label": node_by_id[source_node_id]["label"],
        "relationship": rel_type,
        "target_preview_node_id": target_node_id,
        "target_node_kind": node_by_id[target_node_id]["node_kind"],
        "target_label": node_by_id[target_node_id]["label"],
        "candidate_relationship_ids": candidate_relationship_ids,
        "passage_ids": sorted(set(payload["passage_ids"])),
        "evidence_texts": list(dict.fromkeys(payload["evidence_texts"])),
        "evidence_classes": sorted(payload["evidence_classes"]),
        "candidate_relationship_count": len(candidate_relationship_ids),
        "self_relation": source_node_id == target_node_id,
        "created_at": created_at,
    })

mapped_relationship_ids = {
    rel_id
    for row in full_relationships
    for rel_id in row["candidate_relationship_ids"]
}
expected_relationship_ids = {
    str(row["candidate_relationship_id"])
    for row in relationship_rows
}
missing_relationship_ids = sorted(
    expected_relationship_ids - mapped_relationship_ids
)
if missing_relationship_ids:
    raise RuntimeError(
        "Candidate relationships were lost during full-graph preview mapping: "
        + ", ".join(missing_relationship_ids)
    )

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {FULL_NODE_PREVIEW_TABLE} (
    analysis_id STRING NOT NULL,
    preview_version STRING NOT NULL,
    preview_node_id STRING NOT NULL,
    node_kind STRING NOT NULL,
    label STRING NOT NULL,
    description STRING,
    member_candidate_ids ARRAY<STRING>,
    passage_ids ARRAY<STRING>,
    inventory_visible BOOLEAN,
    passthrough BOOLEAN,
    created_at TIMESTAMP NOT NULL
)
USING DELTA
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {FULL_REL_PREVIEW_TABLE} (
    analysis_id STRING NOT NULL,
    preview_version STRING NOT NULL,
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
    f"DELETE FROM {FULL_NODE_PREVIEW_TABLE} WHERE analysis_id = '{analysis_id}' "
    f"AND preview_version = '{FULL_GRAPH_PREVIEW_VERSION}'"
)
spark.sql(
    f"DELETE FROM {FULL_REL_PREVIEW_TABLE} WHERE analysis_id = '{analysis_id}' "
    f"AND preview_version = '{FULL_GRAPH_PREVIEW_VERSION}'"
)

node_df = spark.createDataFrame(
    [Row(**row) for row in full_nodes],
    schema=spark.table(FULL_NODE_PREVIEW_TABLE).schema,
)
rel_df = spark.createDataFrame(
    [Row(**row) for row in full_relationships],
    schema=spark.table(FULL_REL_PREVIEW_TABLE).schema,
)
node_df.write.mode("append").saveAsTable(FULL_NODE_PREVIEW_TABLE)
rel_df.write.mode("append").saveAsTable(FULL_REL_PREVIEW_TABLE)

# COMMAND ----------

print("Full preview nodes:", len(full_nodes))
print("Full preview relationships:", len(full_relationships))
print(
    "Mapped candidate relationships:",
    len(mapped_relationship_ids),
    "/",
    len(expected_relationship_ids),
)
print(
    "Self-relations after node consolidation:",
    sum(1 for row in full_relationships if row["self_relation"]),
)

print("\nNode kinds")
display(
    node_df.groupBy("node_kind", "inventory_visible", "passthrough")
    .count()
    .orderBy("inventory_visible", "node_kind")
)

print("\nRelationships")
display(
    rel_df.select(
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
print("PASS — FULL GRAPH COVERAGE PREVIEW COMPLETED")
print("Every candidate relationship was mapped to a resolved or passthrough node.")
print("Neo4j graph was NOT modified.")
