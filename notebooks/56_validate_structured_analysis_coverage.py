# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 56 — Validate structured-analysis coverage
# MAGIC
# MAGIC Read-only diagnostic for the IKF analysis pipeline.
# MAGIC
# MAGIC It compares the evidence-grounded candidate concepts produced by notebook 16
# MAGIC with the concepts actually published to the analysis knowledge graph.
# MAGIC
# MAGIC Purpose: determine whether missing Events / Contributing Factors / Findings /
# MAGIC Safety Issues / Recommendations were:
# MAGIC 1. never extracted as candidates, or
# MAGIC 2. extracted but lost/merged during consolidation or graph publication.
# MAGIC
# MAGIC This notebook does not call an LLM and does not modify Delta or Neo4j.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

import re
from collections import Counter

from neo4j import GraphDatabase
from pyspark.sql import Row
from pyspark.sql import functions as F

ANALYSIS_CANDIDATE_TABLE = (
    "bdw_analysis_prod.kg_poc.analysis_candidate"
)

TRACKED_KINDS = (
    "Event",
    "ContributingFactor",
    "Finding",
    "SafetyIssue",
    "Recommendation",
)

analysis_id = dbutils.widgets.get("analysis_id").strip()

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError(
        "Enter a valid IKF analysis_id in the form analysis_<32 hex>."
    )

print("Analysis:", analysis_id)

# COMMAND ----------

if not spark.catalog.tableExists(ANALYSIS_CANDIDATE_TABLE):
    raise RuntimeError(
        "analysis_candidate table does not exist. Run notebook 16 first."
    )

candidate_rows = [
    row.asDict(recursive=True)
    for row in (
        spark.table(ANALYSIS_CANDIDATE_TABLE)
        .filter(F.col("analysis_id") == analysis_id)
        .select(
            "candidate_id",
            "extraction_batch",
            "node_kind",
            "label",
            "description",
            "passage_ids",
            "evidence_text",
            "evidence_class",
            "model_service",
            "analysis_version",
        )
        .collect()
    )
]

if not candidate_rows:
    raise ValueError(
        "No analysis candidates were found for this analysis."
    )

print("Candidate concepts:", len(candidate_rows))

# COMMAND ----------

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

with driver.session() as session:
    graph_records = session.run(
        """
        MATCH (n:KGNode {analysis_id: $analysis_id})
        RETURN properties(n) AS props
        """,
        analysis_id=analysis_id,
    ).data()

driver.close()

graph_rows = [
    record["props"]
    for record in graph_records
]

print("Published graph concepts:", len(graph_rows))

# COMMAND ----------

def normalise_label(value):
    value = str(value or "").casefold().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def graph_kind(item):
    return (
        item.get("node_kind")
        or item.get("kind")
        or item.get("type")
        or "Other"
    )


def graph_label(item):
    return (
        item.get("label")
        or item.get("name")
        or item.get("title")
        or ""
    )


candidate_by_kind = Counter(
    item.get("node_kind") or "Other"
    for item in candidate_rows
)

graph_by_kind = Counter(
    graph_kind(item)
    for item in graph_rows
)

summary_rows = []

for kind in TRACKED_KINDS:
    candidate_count = candidate_by_kind.get(kind, 0)
    graph_count = graph_by_kind.get(kind, 0)
    summary_rows.append(
        {
            "node_kind": kind,
            "candidate_count": candidate_count,
            "published_graph_count": graph_count,
            "count_delta": candidate_count - graph_count,
        }
    )

summary_df = spark.createDataFrame(
    [Row(**item) for item in summary_rows]
)

display(summary_df.orderBy("node_kind"))

# COMMAND ----------

# Exact normalised-label comparison is intentionally conservative.
# A candidate absent here may have been legitimately merged into a differently
# worded canonical concept; this notebook flags it for review rather than
# declaring it lost.

graph_keys = {
    (
        graph_kind(item),
        normalise_label(graph_label(item)),
    )
    for item in graph_rows
    if normalise_label(graph_label(item))
}

candidate_comparison = []

for item in candidate_rows:
    kind = item.get("node_kind") or "Other"
    if kind not in TRACKED_KINDS:
        continue

    label = item.get("label") or ""
    normalised = normalise_label(label)
    exact_graph_match = (
        kind,
        normalised,
    ) in graph_keys

    candidate_comparison.append(
        {
            "node_kind": kind,
            "candidate_id": item.get("candidate_id"),
            "extraction_batch": item.get("extraction_batch"),
            "candidate_label": label,
            "exact_normalised_graph_match": exact_graph_match,
            "evidence_class": item.get("evidence_class"),
            "passage_count": len(item.get("passage_ids") or []),
            "passage_ids": item.get("passage_ids") or [],
            "evidence_text": item.get("evidence_text") or "",
        }
    )

comparison_schema = (
    "node_kind STRING, candidate_id STRING, extraction_batch INT, "
    "candidate_label STRING, exact_normalised_graph_match BOOLEAN, "
    "evidence_class STRING, passage_count INT, passage_ids ARRAY<STRING>, "
    "evidence_text STRING"
)

comparison_df = spark.createDataFrame(
    candidate_comparison,
    schema=comparison_schema,
)

display(
    comparison_df.orderBy(
        "node_kind",
        "exact_normalised_graph_match",
        "candidate_label",
    )
)

# COMMAND ----------

unmatched_df = comparison_df.filter(
    ~F.col("exact_normalised_graph_match")
)

unmatched_count = unmatched_df.count()

print("")
print("COVERAGE DIAGNOSTIC")
print("Tracked candidate concepts:", comparison_df.count())
print("Candidate labels without exact graph label match:", unmatched_count)

for kind in TRACKED_KINDS:
    candidate_count = candidate_by_kind.get(kind, 0)
    graph_count = graph_by_kind.get(kind, 0)
    print(
        f"{kind}: candidates={candidate_count} | graph={graph_count} | "
        f"delta={candidate_count - graph_count}"
    )

print("")
print(
    "Interpretation: if expected contributing factors are absent from the "
    "candidate table, improve extraction/coverage. If they are present as "
    "candidates but absent from the graph, inspect consolidation/publication."
)
print(
    "Exact label mismatch is a review signal, not proof of loss, because "
    "legitimate canonicalisation may change wording."
)
print("")
print("PASS — STRUCTURED ANALYSIS COVERAGE DIAGNOSTIC COMPLETED")
